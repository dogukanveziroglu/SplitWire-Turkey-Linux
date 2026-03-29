#!/usr/bin/env python3
"""
End-to-end bypass test for SplitWire services.

Starts services and tests whether discord.com/roblox.com become accessible.

Phases:
  1. Baseline (no services) — measure DNS, TCP, HTTPS
  2. DNS fix only (Cloudflare) — re-test
  3. ByeDPI proxy (ciadpi SOCKS5) — re-test through proxy
  4. Zapret nfqws (DPI bypass) — re-test direct
  5. Summary & latency comparison

Run inside Docker with --privileged:
    docker run --rm --privileged --runtime=runc \
        --entrypoint /app/.venv/bin/python \
        splitwire-test tests/e2e_bypass_test.py
"""

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

# ─── Config ─────────────────────────────────────────────────────────

TARGETS = ["discord.com", "cdn.discordapp.com", "roblox.com", "www.roblox.com"]
CONTROL = "google.com"
DNS_ITERATIONS = 5
CONNECT_TIMEOUT = 8


# ─── Helpers ────────────────────────────────────────────────────────

def run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command and return result."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )


def tcp_connect(host: str, port: int = 443) -> dict:
    """TCP connect test with latency."""
    t0 = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
        ms = round((time.monotonic() - t0) * 1000, 1)
        sock.close()
        return {"ok": True, "ms": ms}
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"ok": False, "ms": ms, "err": str(e)[:60]}


def dns_resolve(domain: str, server: str | None = None) -> dict:
    """DNS resolve with latency."""
    t0 = time.monotonic()
    try:
        cmd = ["nslookup", domain]
        if server:
            cmd.append(server)
        r = run(cmd, timeout=10)
        ms = round((time.monotonic() - t0) * 1000, 1)
        ips = []
        for line in r.stdout.split("\n"):
            s = line.strip()
            if s.startswith("Address:") and "#53" not in s:
                ip = s.split("Address:")[-1].strip()
                if ip and not ip.startswith("127."):
                    ips.append(ip)
        return {"ok": len(ips) > 0, "ms": ms, "ips": ips}
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"ok": False, "ms": ms, "err": str(e)[:60]}


def curl_https(url: str, proxy: str | None = None, timeout: int = 15) -> dict:
    """HTTPS request via curl, optionally through proxy."""
    t0 = time.monotonic()
    cmd = [
        "curl", "-sS", "-o", "/dev/null",
        "-w", "%{http_code} %{time_total} %{time_namelookup} %{time_connect}",
        "--max-time", str(timeout),
        "-L", url,
    ]
    if proxy:
        cmd.extend(["--proxy", proxy])
    try:
        r = run(cmd, timeout=timeout + 5)
        ms = round((time.monotonic() - t0) * 1000, 1)
        parts = r.stdout.strip().split()
        if len(parts) >= 4:
            code = int(parts[0])
            return {
                "ok": 200 <= code < 400,
                "code": code,
                "total_ms": round(float(parts[1]) * 1000, 1),
                "dns_ms": round(float(parts[2]) * 1000, 1),
                "connect_ms": round(float(parts[3]) * 1000, 1),
            }
        return {"ok": False, "ms": ms, "stderr": r.stderr[:100]}
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"ok": False, "ms": ms, "err": str(e)[:60]}


def dns_latency_avg(domain: str, server: str | None, n: int = 5) -> float | None:
    """Average DNS latency over n iterations."""
    times = []
    for _ in range(n):
        r = dns_resolve(domain, server)
        if r["ok"]:
            times.append(r["ms"])
        time.sleep(0.1)
    return round(sum(times) / len(times), 1) if times else None


def hdr(text: str) -> None:
    """Print section header."""
    print(f"\n{'='*65}")
    print(f"  {text}")
    print(f"{'='*65}")


def row(label: str, result: dict) -> None:
    """Print result row."""
    s = "OK" if result.get("ok") else "FAIL"
    ms = result.get("ms") or result.get("total_ms") or "?"
    extra = ""
    if "code" in result:
        extra = f"  HTTP {result['code']}"
    elif "err" in result:
        extra = f"  [{result['err'][:40]}]"
    print(f"  {label:<40} {s:<5} {ms:>8} ms{extra}")


# ─── DNS Fix ────────────────────────────────────────────────────────

def fix_dns_cloudflare() -> bool:
    """Switch DNS to Cloudflare 1.1.1.1."""
    print("  Writing /etc/resolv.conf with Cloudflare DNS...")
    try:
        # Backup
        resolv = Path("/etc/resolv.conf")
        backup = Path("/etc/resolv.conf.splitwire.bak")
        if resolv.exists() and not backup.exists():
            shutil.copy2(resolv, backup)

        # Disable systemd-resolved stub if active
        run(["systemctl", "stop", "systemd-resolved"], timeout=10)

        resolv.write_text(
            "# SplitWire test - Cloudflare DNS\n"
            "nameserver 1.1.1.1\n"
            "nameserver 1.0.0.1\n"
            "nameserver 8.8.8.8\n"
        )
        time.sleep(1)

        # Verify
        r = dns_resolve("google.com", "1.1.1.1")
        print(f"  DNS verify (google.com via 1.1.1.1): "
              f"{'OK' if r['ok'] else 'FAIL'}")
        return r["ok"]
    except Exception as e:
        print(f"  DNS fix failed: {e}")
        return False


def restore_dns() -> None:
    """Restore original DNS."""
    backup = Path("/etc/resolv.conf.splitwire.bak")
    if backup.exists():
        shutil.copy2(backup, "/etc/resolv.conf")
        backup.unlink()
    run(["systemctl", "start", "systemd-resolved"], timeout=10)


# ─── ByeDPI (ciadpi) ───────────────────────────────────────────────

def get_arch() -> str:
    """Get architecture string for ciadpi download."""
    machine = platform.machine()
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "armv7l": "armv7l",
        "i686": "i686",
    }
    return arch_map.get(machine, machine)


def install_byedpi() -> Path | None:
    """Download and install ciadpi binary."""
    binary = Path("/opt/byedpi/ciadpi")
    if binary.exists():
        print(f"  ciadpi already exists at {binary}")
        return binary

    print("  Downloading ciadpi from GitHub...")
    try:
        arch = get_arch()
        api_url = "https://api.github.com/repos/hufrea/byedpi/releases/latest"
        req = urllib.request.Request(api_url)
        req.add_header("User-Agent", "SplitWire-Test")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        download_url = None
        for asset in data.get("assets", []):
            name = asset["name"]
            if arch in name and name.endswith(".tar.gz"):
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            for asset in data.get("assets", []):
                name = asset["name"]
                if "linux" in name.lower() and name.endswith(".tar.gz"):
                    download_url = asset["browser_download_url"]
                    break

        if not download_url:
            print(f"  No ciadpi binary found for arch {arch}")
            return None

        print(f"  Downloading: {download_url}")
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            urllib.request.urlretrieve(download_url, tmp.name)  # noqa: S310
            tmp_path = tmp.name

        binary.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp_path) as tar:
            members = tar.getmembers()
            print(f"  Archive contents: {[m.name for m in members]}")
            for member in members:
                if "ciadpi" in member.name and member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        binary.write_bytes(f.read())
                        binary.chmod(0o755)
                        print(f"  Installed: {binary}")
                        return binary
            # Fallback: extract all and find ciadpi
            with tempfile.TemporaryDirectory() as extract_dir:
                tar.extractall(extract_dir)
                for p in Path(extract_dir).rglob("ciadpi"):
                    if p.is_file():
                        shutil.copy2(p, binary)
                        binary.chmod(0o755)
                        print(f"  Installed (fallback): {binary}")
                        return binary

        print("  ciadpi binary not found in archive")
        return None
    except Exception as e:
        print(f"  Download failed: {e}")
        return None


BYEDPI_PRESETS = {
    "discord": [
        "--disorder", "3", "--auto=torst", "--tlsrec", "1+s",
        "--fake", "-1", "--ttl", "8",
    ],
    "default": [
        "--disorder", "1", "--auto=torst", "--tlsrec", "1+s",
    ],
    "fake": ["--fake", "-1", "--ttl", "8"],
    "split": ["--split", "1", "--tlsrec", "1+s"],
}


def start_byedpi(
    binary: Path, port: int = 1080, preset: str = "discord"
) -> int | None:
    """Start ciadpi SOCKS5 proxy, return PID."""
    args = BYEDPI_PRESETS.get(preset, BYEDPI_PRESETS["discord"])
    print(f"  Starting ciadpi preset={preset} on 127.0.0.1:{port}...")
    print(f"  Args: {' '.join(args)}")
    try:
        proc = subprocess.Popen(
            [str(binary), "-i", "127.0.0.1", "-p", str(port)] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        if proc.poll() is None:
            print(f"  ciadpi running (PID {proc.pid})")
            return proc.pid
        print("  ciadpi exited immediately")
        return None
    except Exception as e:
        print(f"  Start failed: {e}")
        return None


def stop_byedpi() -> None:
    """Kill ciadpi."""
    run(["pkill", "-9", "ciadpi"])
    time.sleep(1)


# ─── Zapret (nfqws) ────────────────────────────────────────────────

def install_zapret() -> Path | None:
    """Build and install nfqws."""
    nfqws = Path("/opt/zapret/nfq/nfqws")
    if nfqws.exists():
        print(f"  nfqws already exists at {nfqws}")
        return nfqws

    print("  Installing build dependencies...")
    r = run([
        "apt-get", "install", "-y", "--no-install-recommends",
        "libnetfilter-queue-dev", "libcap-dev",
        "libnfnetlink-dev", "zlib1g-dev",
    ], timeout=120)

    if r.returncode != 0:
        print(f"  apt-get failed: {r.stderr[:100]}")
        return None

    print("  Cloning zapret (depth=1)...")
    r = run([
        "git", "clone", "--depth=1", "-b", "master",
        "https://github.com/bol-van/zapret.git", "/opt/zapret",
    ], timeout=120)
    if r.returncode != 0:
        print(f"  Clone failed: {r.stderr[:100]}")
        return None

    print("  Building nfqws...")
    r = run(["make", "-C", "/opt/zapret/nfq", "-j2"], timeout=120)
    if r.returncode != 0:
        print(f"  Build failed: {r.stderr[:200]}")
        return None

    if nfqws.exists():
        print(f"  Built: {nfqws}")
        return nfqws

    print("  nfqws binary not found after build")
    return None


def start_zapret(nfqws: Path) -> int | None:
    """Start nfqws with iptables rules."""
    print("  Setting up iptables NFQUEUE rules...")
    # Add iptables rules
    for table_cmd in [
        ["iptables", "-t", "mangle", "-I", "POSTROUTING", "-p", "tcp",
         "--dport", "443", "-j", "NFQUEUE", "--queue-num", "200",
         "--queue-bypass"],
        ["iptables", "-t", "mangle", "-I", "POSTROUTING", "-p", "tcp",
         "--dport", "80", "-j", "NFQUEUE", "--queue-num", "200",
         "--queue-bypass"],
    ]:
        r = run(table_cmd)
        if r.returncode != 0:
            print(f"  iptables failed: {r.stderr[:80]}")
            return None

    print("  Starting nfqws...")
    try:
        proc = subprocess.Popen(
            [
                str(nfqws),
                "--qnum=200",
                "--dpi-desync=fake,split2",
                "--dpi-desync-ttl=5",
                "--dpi-desync-fooling=md5sig",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        if proc.poll() is None:
            print(f"  nfqws running (PID {proc.pid})")
            return proc.pid
        print(f"  nfqws exited (code {proc.poll()})")
        return None
    except Exception as e:
        print(f"  Start failed: {e}")
        return None


def stop_zapret() -> None:
    """Stop nfqws and clean iptables."""
    run(["pkill", "-9", "nfqws"])
    run(["iptables", "-t", "mangle", "-F", "POSTROUTING"])
    time.sleep(1)


# ─── Test Runner ────────────────────────────────────────────────────

def run_connectivity_test(
    label: str,
    proxy: str | None = None,
) -> dict:
    """Run full connectivity test suite."""
    results = {}

    print(f"\n  --- TCP Connect ---")
    for host in TARGETS + [CONTROL]:
        r = tcp_connect(host)
        results[f"tcp_{host}"] = r
        row(host, r)

    print(f"\n  --- HTTPS (curl{' via proxy' if proxy else ''}) ---")
    for host in TARGETS + [CONTROL]:
        url = f"https://{host}"
        r = curl_https(url, proxy=proxy)
        results[f"https_{host}"] = r
        row(url, r)

    print(f"\n  --- DNS Latency (discord.com, {DNS_ITERATIONS}x) ---")
    for name, server in [
        ("system", None),
        ("cloudflare", "1.1.1.1"),
        ("google", "8.8.8.8"),
    ]:
        avg = dns_latency_avg("discord.com", server, DNS_ITERATIONS)
        results[f"dns_{name}"] = avg
        if avg:
            print(f"  {name:<20} {avg:>7} ms avg")
        else:
            print(f"  {name:<20} FAILED")

    return results


# ─── Main ───────────────────────────────────────────────────────────

def main() -> None:
    """Run the full bypass test."""
    print("\n" + "=" * 65)
    print("  SPLITWIRE BYPASS TEST")
    print("  Testing: discord.com, roblox.com")
    print("=" * 65)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  UID: {os.geteuid()} ({'root' if os.geteuid() == 0 else 'user'})")

    all_results = {}

    # ── PHASE 1: Baseline ──
    hdr("PHASE 1: BASELINE (no services)")
    all_results["baseline"] = run_connectivity_test("baseline")

    # ── PHASE 2: DNS Fix ──
    hdr("PHASE 2: DNS FIX (Cloudflare 1.1.1.1)")
    dns_ok = fix_dns_cloudflare()
    if dns_ok:
        all_results["dns_fixed"] = run_connectivity_test("dns_fixed")
    else:
        print("  Skipping — DNS fix failed")
        all_results["dns_fixed"] = {"error": "dns fix failed"}

    # ── PHASE 3: ByeDPI (try multiple presets) ──
    binary = install_byedpi()
    for preset_name in ["discord", "default", "fake", "split"]:
        hdr(f"PHASE 3: BYEDPI preset={preset_name}")
        if binary:
            pid = start_byedpi(binary, preset=preset_name)
            if pid:
                proxy = "socks5://127.0.0.1:1080"
                result = run_connectivity_test(
                    f"byedpi_{preset_name}", proxy=proxy
                )
                all_results[f"byedpi_{preset_name}"] = result
                # If discord HTTPS works, note it
                discord_ok = result.get(
                    "https_discord.com", {}
                ).get("ok", False)
                roblox_ok = result.get(
                    "https_roblox.com", {}
                ).get("ok", False)
                if discord_ok or roblox_ok:
                    print(f"\n  ** BYPASS WORKING with preset={preset_name}! **")
                stop_byedpi()
            else:
                all_results[f"byedpi_{preset_name}"] = {"error": "start failed"}
        else:
            all_results[f"byedpi_{preset_name}"] = {
                "error": "binary not available"
            }
            break

    # ── PHASE 4: Zapret ──
    hdr("PHASE 4: ZAPRET (nfqws DPI bypass)")
    nfqws = install_zapret()
    if nfqws:
        pid = start_zapret(nfqws)
        if pid:
            all_results["zapret"] = run_connectivity_test("zapret")
            stop_zapret()
        else:
            print("  Skipping — nfqws failed to start")
            all_results["zapret"] = {"error": "start failed"}
    else:
        print("  Skipping — nfqws build failed")
        all_results["zapret"] = {"error": "build failed"}

    # ── Cleanup ──
    hdr("CLEANUP")
    stop_byedpi()
    stop_zapret()
    restore_dns()
    print("  All services stopped, DNS restored.")

    # ── SUMMARY ──
    hdr("SUMMARY: discord.com accessibility")
    print(f"\n  {'Phase':<25} {'TCP':>8} {'HTTPS':>8} {'DNS avg':>10}")
    print(f"  {'-'*55}")
    phases = ["baseline", "dns_fixed"]
    phases += [f"byedpi_{p}" for p in ["discord", "default", "fake", "split"]]
    phases.append("zapret")
    for phase in phases:
        data = all_results.get(phase, {})
        if isinstance(data, dict) and "error" not in data:
            tcp = "OK" if data.get("tcp_discord.com", {}).get("ok") else "FAIL"
            https = "OK" if data.get(
                "https_discord.com", {}
            ).get("ok") else "FAIL"
            dns_avg = data.get("dns_system")
            dns_str = f"{dns_avg} ms" if dns_avg else "?"
            print(f"  {phase:<25} {tcp:>8} {https:>8} {dns_str:>10}")
        else:
            err = data.get("error", "skipped") if isinstance(data, dict) else "?"
            print(f"  {phase:<25} {'—':>8} {'—':>8} {err:>10}")

    print(f"\n  {'Phase':<25} {'TCP':>8} {'HTTPS':>8}")
    print(f"  {'-'*45}")
    hdr("SUMMARY: roblox.com accessibility")
    phases = ["baseline", "dns_fixed"]
    phases += [f"byedpi_{p}" for p in ["discord", "default", "fake", "split"]]
    phases.append("zapret")
    for phase in phases:
        data = all_results.get(phase, {})
        if isinstance(data, dict) and "error" not in data:
            tcp = "OK" if data.get("tcp_roblox.com", {}).get("ok") else "FAIL"
            https = "OK" if data.get(
                "https_roblox.com", {}
            ).get("ok") else "FAIL"
            print(f"  {phase:<25} {tcp:>8} {https:>8}")
        else:
            err = data.get("error", "skipped") if isinstance(data, dict) else "?"
            print(f"  {phase:<25} {'—':>8} {err:>8}")

    # DNS latency comparison
    hdr("DNS LATENCY COMPARISON")
    baseline_dns = all_results.get("baseline", {}).get("dns_system")
    fixed_dns = all_results.get("dns_fixed", {}).get("dns_system")
    if baseline_dns and fixed_dns:
        diff = round(fixed_dns - baseline_dns, 1)
        sign = "+" if diff > 0 else ""
        print(f"  Baseline (ISP DNS):     {baseline_dns} ms")
        print(f"  Cloudflare (1.1.1.1):   {fixed_dns} ms ({sign}{diff} ms)")
        if abs(diff) > 50:
            print(f"  WARNING: Significant latency increase!")
        else:
            print(f"  Acceptable latency change.")
    else:
        print("  Insufficient data for comparison.")

    # Save
    results_file = Path(__file__).parent / "e2e_bypass_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to: {results_file}")
    print(f"\n{'='*65}\n")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ERROR: Must run as root (need iptables, DNS changes)")
        print("Usage: sudo python tests/e2e_bypass_test.py")
        sys.exit(1)
    main()
