"""
BlockcheckService - Zapret blockcheck integration for SplitWire Linux.

Runs scans to detect optimal DPI bypass parameters.
Equivalent to "Zapret Otomatik Kurulum" in Windows version.
"""

import json
import logging
import re
import subprocess
import threading
import time
from collections.abc import Callable

from splitwire.core import get_shell

from .constants import (
    BLOCKCHECK_RESULTS,
    BLOCKCHECK_SCRIPT,
    FULL_TARGETS,
    QUICK_TARGETS,
    STANDARD_TARGETS,
)
from .models import BlockcheckResult, ScanMode, ScanProgress, ScanStatus
from .strategies import generate_strategies


class BlockcheckService:
    """
    Service for running Zapret's blockcheck to detect optimal
    packet processing parameters.

    Provides:
    - Three scan modes (quick, standard, full)
    - Progress callbacks during scanning
    - Results parsing for recommended parameters
    - Strategy ranking based on success rate
    """

    # Blockcheck-specific timeouts (seconds)
    TIMEOUT_CANCEL = 5  # process termination on cancel
    TIMEOUT_QUICK_TEST = 15  # curl quick test
    TIMEOUT_STRATEGY_TEST = 10  # curl strategy test

    def __init__(self) -> None:
        """Initialize the blockcheck service with default state."""
        self._logger = logging.getLogger(__name__)
        self._shell = get_shell()
        self._progress = ScanProgress()
        self._result: BlockcheckResult | None = None
        self._process: subprocess.Popen | None = None
        self._progress_callbacks: list[Callable[[ScanProgress], None]] = []
        self._scan_thread: threading.Thread | None = None
        self._cancelled = False

        BLOCKCHECK_RESULTS.parent.mkdir(parents=True, exist_ok=True)

    # -- Public API --

    def is_available(self) -> bool:
        """Check if blockcheck is available."""
        return BLOCKCHECK_SCRIPT.exists()

    def is_running(self) -> bool:
        """Check if a scan is currently running."""
        return self._progress.status == ScanStatus.RUNNING

    def get_progress(self) -> ScanProgress:
        """Get current scan progress."""
        return self._progress

    def get_last_result(self) -> BlockcheckResult | None:
        """Get result from last scan."""
        if self._result:
            return self._result
        return self._load_saved_result()

    def add_progress_callback(self, callback: Callable[[ScanProgress], None]) -> None:
        """Add callback for progress updates."""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[ScanProgress], None]) -> None:
        """Remove progress callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def start_scan(
        self,
        mode: ScanMode = ScanMode.STANDARD,
        targets: list[str] | None = None,
        async_mode: bool = True,
    ) -> bool:
        """
        Start a blockcheck scan.

        Args:
            mode: Scan mode (quick, standard, full)
            targets: Custom target domains (optional)
            async_mode: Run in background thread

        Returns:
            True if scan started successfully
        """
        if self.is_running():
            self._logger.warning("A scan is already running")
            return False
        if not self.is_available():
            self._logger.error("Blockcheck is not available")
            return False

        self._cancelled = False
        self._progress = ScanProgress(status=ScanStatus.RUNNING)
        self._result = None

        if targets is None:
            targets = _get_targets_for_mode(mode)

        if async_mode:
            self._scan_thread = threading.Thread(
                target=self._run_scan,
                args=(mode, targets),
                daemon=True,
            )
            self._scan_thread.start()
            return True
        return self._run_scan(mode, targets)

    def cancel_scan(self) -> bool:
        """Cancel a running scan."""
        if not self.is_running():
            return False

        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=self.TIMEOUT_CANCEL)
            except subprocess.TimeoutExpired:
                self._process.kill()

        self._progress.status = ScanStatus.CANCELLED
        self._notify_progress()
        return True

    def run_quick_test(self, target: str, strategy: str) -> bool:
        """Test a specific strategy against a target."""
        self._logger.info(f"Testing strategy '{strategy}' against {target}")
        cmd = [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--connect-timeout",
            "10",
            f"https://{target}",
        ]
        result = self._shell.run(cmd, timeout=self.TIMEOUT_QUICK_TEST)
        if result.success and result.stdout.strip() in ["200", "301", "302", "403"]:
            self._logger.info(f"Strategy works for {target}")
            return True
        self._logger.info(f"Strategy failed for {target}")
        return False

    # -- Internal Methods --

    def _run_scan(self, mode: ScanMode, targets: list[str]) -> bool:
        """Run the actual blockcheck scan."""
        start_time = time.time()
        self._logger.info(f"Starting blockcheck scan (mode: {mode.value}, targets: {len(targets)})")

        try:
            result = BlockcheckResult(scan_mode=mode)
            strategies = generate_strategies(mode)
            total = len(strategies) * len(targets)
            self._progress.tests_total = total

            working, failed = self._execute_strategies(strategies, targets, result, start_time)

            result.working_strategies = working
            result.failed_strategies = failed
            result.duration_seconds = time.time() - start_time

            _select_best_strategy(result, working)

            self._result = result
            self._save_result(result)
            self._finalize_progress(result)

            self._logger.info(
                f"Blockcheck completed: {len(working)} working, {len(failed)} failed strategies"
            )
            return result.success

        except Exception as e:
            self._logger.error(f"Blockcheck scan failed: {e}")
            self._progress.status = ScanStatus.FAILED
            self._notify_progress()
            if self._result is None:
                self._result = BlockcheckResult(
                    success=False,
                    error_message=str(e),
                    duration_seconds=time.time() - start_time,
                )
            return False

    def _execute_strategies(
        self,
        strategies: list[dict],
        targets: list[str],
        result: BlockcheckResult,
        start_time: float,
    ) -> tuple[list[dict], list[dict]]:
        """Execute all strategies against all targets."""
        working: list[dict] = []
        failed: list[dict] = []

        for i, strategy in enumerate(strategies):
            if self._cancelled:
                break

            strategy_results = self._test_strategy_against_targets(
                strategy, targets, i, result, start_time
            )
            if strategy_results["all_passed"]:
                working.append(strategy_results)
            else:
                failed.append(strategy_results)

        return working, failed

    def _test_strategy_against_targets(
        self,
        strategy: dict,
        targets: list[str],
        strategy_idx: int,
        result: BlockcheckResult,
        start_time: float,
    ) -> dict:
        """Test one strategy against all targets."""
        strategy_works = True
        strategy_results: dict = {
            "strategy": strategy,
            "targets": {},
            "all_passed": True,
        }

        for target in targets:
            if self._cancelled:
                break

            self._update_progress(
                strategy,
                target,
                strategy_idx,
                targets,
                result,
                start_time,
            )
            success = self._test_strategy(strategy, target)
            strategy_results["targets"][target] = success

            if not success:
                strategy_works = False

            result.tested_strategies.append(
                {
                    "strategy": strategy["name"],
                    "target": target,
                    "success": success,
                }
            )

        strategy_results["all_passed"] = strategy_works
        return strategy_results

    def _update_progress(
        self,
        strategy: dict,
        target: str,
        strategy_idx: int,
        targets: list[str],
        result: BlockcheckResult,
        start_time: float,
    ) -> None:
        """Update and notify scan progress."""
        total = self._progress.tests_total
        completed = strategy_idx * len(targets) + targets.index(target)
        self._progress.current_test = f"{strategy['name']} -> {target}"
        self._progress.tests_completed = completed
        self._progress.percent = int((completed / total) * 100) if total else 0
        self._progress.elapsed_seconds = time.time() - start_time
        self._notify_progress()

    def _finalize_progress(self, result: BlockcheckResult) -> None:
        """Set final progress state after scan completion."""
        self._progress.status = (
            ScanStatus.COMPLETED if not self._cancelled else ScanStatus.CANCELLED
        )
        self._progress.percent = 100
        self._progress.elapsed_seconds = result.duration_seconds
        self._notify_progress()

    def _test_strategy(self, strategy: dict, target: str) -> bool:
        """Test a specific strategy against a target."""
        try:
            cmd = [
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--connect-timeout",
                "5",
                "-k",
                f"https://{target}",
            ]
            result = self._shell.run(cmd, timeout=self.TIMEOUT_STRATEGY_TEST)
            http_code = result.stdout.strip()
            return http_code in ["200", "301", "302", "403", "000"]
        except Exception as e:
            self._logger.debug(f"Strategy test error: {e}")
            return False

    def _notify_progress(self) -> None:
        """Notify all progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(self._progress)
            except Exception as e:  # noqa: PERF203 -- per-callback isolation
                self._logger.warning(f"Progress callback error: {e}")

    def _save_result(self, result: BlockcheckResult) -> None:
        """Save scan result to file."""
        try:
            data = {
                "success": result.success,
                "scan_mode": result.scan_mode.value,
                "duration_seconds": result.duration_seconds,
                "recommended_args": result.recommended_args,
                "recommended_mode": result.recommended_mode,
                "working_count": len(result.working_strategies),
                "failed_count": len(result.failed_strategies),
                "timestamp": time.time(),
            }
            BLOCKCHECK_RESULTS.write_text(json.dumps(data, indent=2))
        except Exception as e:
            self._logger.error(f"Failed to save result: {e}")

    def _load_saved_result(self) -> BlockcheckResult | None:
        """Load saved result from file."""
        if not BLOCKCHECK_RESULTS.exists():
            return None
        try:
            data = json.loads(BLOCKCHECK_RESULTS.read_text())
            return BlockcheckResult(
                success=data.get("success", False),
                scan_mode=ScanMode(data.get("scan_mode", "quick")),
                duration_seconds=data.get("duration_seconds", 0),
                recommended_args=data.get("recommended_args", ""),
                recommended_mode=data.get("recommended_mode", "nfqws"),
            )
        except Exception as e:
            self._logger.warning(f"Failed to load saved result: {e}")
            return None

    def parse_blockcheck_output(self, output: str) -> BlockcheckResult:
        """Parse output from zapret's blockcheck.sh script."""
        result = BlockcheckResult()
        result.raw_output = output

        passed_pattern = re.compile(
            r"(nfqws|tpws)\s+([^:]+):\s*(PASSED|OK|SUCCESS)",
            re.IGNORECASE,
        )

        for match in passed_pattern.finditer(output):
            mode = match.group(1).lower()
            args = match.group(2).strip()
            result.working_strategies.append({"mode": mode, "args": args})

        if result.working_strategies:
            best = result.working_strategies[0]
            result.success = True
            result.recommended_mode = best["mode"]
            result.recommended_args = best["args"]

        return result


def _get_targets_for_mode(mode: ScanMode) -> list[str]:
    """Get target domains for scan mode."""
    if mode == ScanMode.QUICK:
        return QUICK_TARGETS
    if mode == ScanMode.STANDARD:
        return STANDARD_TARGETS
    return FULL_TARGETS


def _select_best_strategy(result: BlockcheckResult, working: list[dict]) -> None:
    """Select the best strategy from working results."""
    if working:
        best = working[0]["strategy"]
        result.success = True
        result.recommended_args = best.get("args", "")
        result.recommended_mode = best.get("mode", "nfqws")
    else:
        result.success = False
        result.error_message = "No working strategies found"
