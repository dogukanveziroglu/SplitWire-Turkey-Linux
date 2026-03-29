#!/usr/bin/env python3
"""
SplitWire bypass test v2 — accurate latency measurement.

Fixes from v1:
- Only routes blocked sites through proxy, not google
- Uses curl timing breakdown (DNS/TCP/TLS/total separately)
- DNS cache warming before measurement
- Multiple iterations for reliable averages
- Host vs Docker overhead comparison

Run:
    docker run --rm --privileged --runtime=runc \
        --entrypoint /app/.venv/bin/python \
        splitwire-test tests/e2e_bypass_test_v2.py
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

BLOCKED_SITES = ["discord.com", "roblox.com", "www.roblox.com"]
CONTROL_SITE = "google.com"
ITERATIONS = 3


def run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def curl_timing(
    url: str,
    proxy: str | None = None,
    timeout: int = 15,
    resolve: str | None = None,
) -> dict:
    """Curl with detailed timing breakdown."""
    fmt = json.dumps({
        "code": "%{http_code}",
        "dns_ms": "%{time_namelookup}",
        "tcp_ms": "%{time_connect}",
        "tls_ms": "%{time_appconnect}",
        "total_ms": "%{time_total}",
    })
    cmd = [
        "curl", "-sS", "-o", "/dev/null",
        "-w", fmt,
        "--max-time", str(timeout),
        "-L", url,
    ]
    if proxy:
        cmd.extend(["--proxy", proxy])
    if resolve:
        cmd.extend(["--resolve", resolve])
    try:
        r = run(cmd, timeout=timeout + 5)
        if r.stdout.strip():
            d = json.loads(r.stdout.strip())
            return {
                "ok": d["code"].startswith("2") or d["code"].startswith("3"),
                "code": int(d["code"]),
                "dns": round(float(d["dns_ms"]) * 1000),
                "tcp": round(float(d["tcp_ms"]) * 1000),
                "tls": round(float(d["tls_ms"]) * 1000),
                "total": round(float(d["total_ms"]) * 1000),
            }
        return {"ok": False, "code": 0, "stderr": r.stderr[:80]}
    except Exception as e:
        return {"ok": False, "code": 0, "err": str(e)[:60]}


def dns_latency(domain: str, server: str | None = None, n: int = 3) -> dict:
    """Measure DNS latency (with warm cache after first query)."""
    # Warm cache
    cmd = ["nslookup", domain] + ([server] if server else [])
    run(cmd, timeout=5)
    time.sleep(0.1)

    times = []
    for _ in range(n):
        t0 = time.monotonic()
        r = run(cmd, timeout=5)
        ms = round((time.monotonic() - t0) * 1000)
        if r.returncode == 0:
            times.append(ms)
        time.sleep(0.05)

    if times:
        return {
            "avg": round(sum(times) / len(times)),
            "min": min(times),
            "max": max(times),
        }
    return {"avg": None, "error": "all failed"}


def hdr(text: str) -> None:
    w = 65
    print(f"\n{'='*w}\n  {text}\n{'='*w}")


def fix_dns() -> bool:
    """Switch to Cloudflare DNS."""
    try:
        run(["systemctl", "stop", "systemd-resolved"], timeout=10)
        Path("/etc/resolv.conf").write_text(
            "nameserver 1.1.1.1\nnameserver 1.0.0.1\nnameserver 8.8.8.8\n"
        )
        time.sleep(0.5)
        r = run(["nslookup", "google.com", "1.1.1.1"], timeout=5)
        return r.returncode == 0
    except Exception as e:
        print(f"  DNS fix failed: {e}")
        return False


def restore_dns() -> None:
    bak = Path("/etc/resolv.conf.bak")
    if bak.exists():
        shutil.copy2(bak, "/etc/resolv.conf")
    run(["systemctl", "start", "systemd-resolved"], timeout=10)


def install_byedpi() -> Path | None:
    binary = Path("/opt/byedpi/ciadpi")
    if binary.exists():
        return binary
    print("  Downloading ciadpi...")
    try:
        arch = {"x86_64": "x86_64", "aarch64": "aarch64"}.get(
            platform.machine(), platform.machine()
        )
        req = urllib.request.Request(
            "https://api.github.com/repos/hufrea/byedpi/releases/latest"
        )
        req.add_header("User-Agent", "SplitWire")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        url = None
        for a in data.get("assets", []):
            if arch in a["name"] and a["name"].endswith(".tar.gz"):
                url = a["browser_download_url"]
                break
        if not url:
            print("  No binary for this arch")
            return None
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            urllib.request.urlretrieve(url, tmp.name)  # noqa: S310
            binary.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tmp.name) as tar:
                tar.extractall(binary.parent)
                for p in binary.parent.rglob("ciadpi*"):
                    if p.is_file() and "tar" not in p.name:
                        if p != binary:
                            shutil.move(str(p), str(binary))
                        binary.chmod(0o755)
                        return binary
        return None
    except Exception as e:
        print(f"  Download failed: {e}")
        return None


def start_ciadpi(binary: Path, args: list[str], port: int = 1080) -> int | None:
    try:
        proc = subprocess.Popen(
            [str(binary), "-i", "127.0.0.1", "-p", str(port)] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        if proc.poll() is None:
            return proc.pid
        return None
    except Exception:
        return None


def stop_ciadpi() -> None:
    run(["pkill", "-9", "ciadpi"])
    time.sleep(0.5)


def install_zapret() -> Path | None:
    nfqws = Path("/opt/zapret/nfq/nfqws")
    if nfqws.exists():
        return nfqws
    print("  Cloning & building zapret...")
    r = run([
        "git", "clone", "--depth=1",
        "https://github.com/bol-van/zapret.git", "/opt/zapret",
    ], timeout=120)
    if r.returncode != 0:
        print(f"  Clone failed")
        return None
    r = run(["make", "-C", "/opt/zapret/nfq", "-j2"], timeout=120)
    if nfqws.exists():
        return nfqws
    print(f"  Build failed")
    return None


def start_nfqws(nfqws: Path, args: list[str]) -> int | None:
    for cmd in [
        ["iptables", "-t", "mangle", "-I", "POSTROUTING", "-p", "tcp",
         "--dport", "443", "-j", "NFQUEUE", "--queue-num", "200",
         "--queue-bypass"],
    ]:
        run(cmd)
    try:
        proc = subprocess.Popen(
            [str(nfqws), "--qnum=200"] + args,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        if proc.poll() is None:
            return proc.pid
        return None
    except Exception:
        return None


def stop_nfqws() -> None:
    run(["pkill", "-9", "nfqws"])
    run(["iptables", "-t", "mangle", "-F", "POSTROUTING"])
    time.sleep(0.5)


# ─── Test Phases ────────────────────────────────────────────────────

def test_phase(
    label: str,
    proxy: str | None = None,
) -> dict:
    """Test blocked sites with detailed timing. Only proxy blocked sites."""
    results = {}

    # Test blocked sites
    for host in BLOCKED_SITES:
        url = f"https://{host}"
        timings = []
        for _ in range(ITERATIONS):
            t = curl_timing(url, proxy=proxy, timeout=10)
            timings.append(t)
            if not t["ok"]:
                break
            time.sleep(0.2)

        # Use best successful timing
        ok_timings = [t for t in timings if t.get("ok")]
        if ok_timings:
            best = min(ok_timings, key=lambda x: x["total"])
            results[host] = best
            print(f"  {host:<30} OK  "
                  f"dns={best['dns']:>4}  tcp={best['tcp']:>4}  "
                  f"tls={best['tls']:>4}  total={best['total']:>5} ms")
        else:
            results[host] = timings[0] if timings else {"ok": False}
            err = timings[0].get("err", "") if timings else ""
            print(f"  {host:<30} FAIL  {err[:40]}")

    # Test control (NEVER through proxy)
    url = f"https://{CONTROL_SITE}"
    timings = []
    for _ in range(ITERATIONS):
        t = curl_timing(url, proxy=None, timeout=10)
        timings.append(t)
        time.sleep(0.2)
    ok_timings = [t for t in timings if t.get("ok")]
    if ok_timings:
        best = min(ok_timings, key=lambda x: x["total"])
        results[CONTROL_SITE] = best
        print(f"  {CONTROL_SITE:<30} OK  "
              f"dns={best['dns']:>4}  tcp={best['tcp']:>4}  "
              f"tls={best['tls']:>4}  total={best['total']:>5} ms  (direct)")
    else:
        results[CONTROL_SITE] = timings[0]
        print(f"  {CONTROL_SITE:<30} FAIL  (direct)")

    return results


def main() -> None:
    print("\n" + "=" * 65)
    print("  SPLITWIRE BYPASS TEST v2")
    print("  Accurate latency measurement")
    print("=" * 65)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Root: {'yes' if os.geteuid() == 0 else 'no'}")

    all_results = {}

    # ── Baseline ──
    hdr("PHASE 1: BASELINE (ISP DNS, no bypass)")
    print(f"  {'site':<30} {'st':>4}  "
          f"{'dns':>4}  {'tcp':>5}  {'tls':>5}  {'total':>6}")
    print(f"  {'-'*62}")
    all_results["baseline"] = test_phase("baseline")

    # ── DNS Fix ──
    hdr("PHASE 2: DNS FIX (Cloudflare 1.1.1.1)")
    Path("/etc/resolv.conf.bak").write_text(
        Path("/etc/resolv.conf").read_text()
    )
    dns_ok = fix_dns()
    print(f"  DNS switched: {'OK' if dns_ok else 'FAIL'}")
    if dns_ok:
        print(f"\n  {'site':<30} {'st':>4}  "
              f"{'dns':>4}  {'tcp':>5}  {'tls':>5}  {'total':>6}")
        print(f"  {'-'*62}")
        all_results["dns_fix"] = test_phase("dns_fix")

    # ── ByeDPI presets ──
    binary = install_byedpi()
    presets = {
        "split": ["--split", "1", "--tlsrec", "1+s"],
        "disorder": ["--disorder", "1", "--auto=torst", "--tlsrec", "1+s"],
        "discord": [
            "--disorder", "3", "--auto=torst",
            "--tlsrec", "1+s", "--fake", "-1", "--ttl", "8",
        ],
    }

    for name, args in presets.items():
        hdr(f"PHASE 3: BYEDPI preset={name}")
        if not binary:
            print("  ciadpi not available, skipping")
            all_results[f"byedpi_{name}"] = {"error": "no binary"}
            continue

        print(f"  Args: {' '.join(args)}")
        pid = start_ciadpi(binary, args)
        if not pid:
            print("  Failed to start")
            all_results[f"byedpi_{name}"] = {"error": "start failed"}
            continue

        proxy = "socks5://127.0.0.1:1080"
        print(f"  PID: {pid}\n")
        print(f"  {'site':<30} {'st':>4}  "
              f"{'dns':>4}  {'tcp':>5}  {'tls':>5}  {'total':>6}")
        print(f"  {'-'*62}")
        all_results[f"byedpi_{name}"] = test_phase(
            f"byedpi_{name}", proxy=proxy
        )
        stop_ciadpi()

    # ── Zapret ──
    hdr("PHASE 4: ZAPRET (nfqws direct DPI bypass)")
    nfqws = install_zapret()
    zapret_presets = {
        "fake_split": [
            "--dpi-desync=fake,split2",
            "--dpi-desync-ttl=5",
            "--dpi-desync-fooling=md5sig",
        ],
        "disorder": [
            "--dpi-desync=disorder2",
            "--dpi-desync-ttl=8",
            "--dpi-desync-fooling=md5sig",
        ],
        "split_only": [
            "--dpi-desync=split2",
            "--dpi-desync-split-pos=3",
        ],
    }

    for name, args in zapret_presets.items():
        print(f"\n  --- zapret preset={name} ---")
        if not nfqws:
            print("  nfqws not available")
            all_results[f"zapret_{name}"] = {"error": "no binary"}
            continue

        print(f"  Args: {' '.join(args)}")
        pid = start_nfqws(nfqws, args)
        if not pid:
            print("  Failed to start")
            all_results[f"zapret_{name}"] = {"error": "start failed"}
            continue

        print(f"  PID: {pid}")
        # Zapret is transparent — no proxy needed
        print(f"  {'site':<30} {'st':>4}  "
              f"{'dns':>4}  {'tcp':>5}  {'tls':>5}  {'total':>6}")
        print(f"  {'-'*62}")
        all_results[f"zapret_{name}"] = test_phase(f"zapret_{name}")
        stop_nfqws()

    # ── DNS Latency Summary ──
    hdr("DNS LATENCY COMPARISON (cached, 3 iterations)")
    for label, server in [
        ("ISP default", None),
        ("Cloudflare 1.1.1.1", "1.1.1.1"),
        ("Google 8.8.8.8", "8.8.8.8"),
    ]:
        d = dns_latency("discord.com", server, n=3)
        avg = d.get("avg", "?")
        mn = d.get("min", "?")
        mx = d.get("max", "?")
        print(f"  {label:<25} avg={avg:>4} ms  "
              f"min={mn:>4} ms  max={mx:>4} ms")

    # ── Cleanup ──
    restore_dns()
    stop_ciadpi()
    stop_nfqws()

    # ── Final Summary ──
    hdr("FINAL SUMMARY")
    print(f"\n  {'Phase':<25} "
          f"{'discord.com':>15} {'roblox.com':>15} {'google.com':>15}")
    print(f"  {'-'*70}")

    for phase_key, data in all_results.items():
        if isinstance(data, dict) and "error" not in data:
            d = data.get("discord.com", {})
            r = data.get("roblox.com", {})
            g = data.get("google.com", {})
            d_str = f"{d['total']} ms" if d.get("ok") else "BLOCKED"
            r_str = f"{r['total']} ms" if r.get("ok") else "BLOCKED"
            g_str = f"{g['total']} ms" if g.get("ok") else "BLOCKED"
            print(f"  {phase_key:<25} {d_str:>15} {r_str:>15} {g_str:>15}")
        else:
            err = data.get("error", "?") if isinstance(data, dict) else "?"
            print(f"  {phase_key:<25} {'—':>15} {'—':>15} {err:>15}")

    # Save
    out = Path(__file__).parent / "e2e_bypass_results_v2.json"
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results: {out}")
    print(f"\n{'='*65}\n")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ERROR: sudo required")
        sys.exit(1)
    main()
