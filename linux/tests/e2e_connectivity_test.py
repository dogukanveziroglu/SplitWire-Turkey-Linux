#!/usr/bin/env python3
"""
End-to-end connectivity test for SplitWire services.

Tests whether the program can actually reach discord.com, roblox.com
and measures DNS latency impact of different configurations.

Run inside Docker with --privileged:
    docker run --rm --privileged --runtime=runc \
        splitwire-test python tests/e2e_connectivity_test.py
"""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ─── Helpers ────────────────────────────────────────────────────────

TARGET_SITES = [
    ("discord.com", 443),
    ("cdn.discordapp.com", 443),
    ("gateway.discord.gg", 443),
    ("roblox.com", 443),
    ("www.roblox.com", 443),
    ("google.com", 443),
    ("1.1.1.1", 443),
]

DNS_SERVERS = {
    "system_default": None,
    "cloudflare": "1.1.1.1",
    "google": "8.8.8.8",
    "quad9": "9.9.9.9",
}


def tcp_connect(host: str, port: int, timeout: float = 5.0) -> dict:
    """Test TCP connectivity and measure latency."""
    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        elapsed = (time.monotonic() - start) * 1000
        sock.close()
        return {"ok": True, "latency_ms": round(elapsed, 1)}
    except (socket.timeout, socket.error, OSError) as e:
        elapsed = (time.monotonic() - start) * 1000
        return {"ok": False, "latency_ms": round(elapsed, 1), "error": str(e)}


def dns_resolve(domain: str, dns_server: str | None = None) -> dict:
    """Resolve a domain and measure DNS latency."""
    start = time.monotonic()
    try:
        if dns_server:
            cmd = ["nslookup", domain, dns_server]
        else:
            cmd = ["nslookup", domain]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        elapsed = (time.monotonic() - start) * 1000
        ips = []
        for line in result.stdout.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Address:") and not stripped.endswith("#53"):
                ip = stripped.split("Address:")[-1].strip()
                if ip and not ip.startswith("127."):
                    ips.append(ip)
        return {
            "ok": result.returncode == 0 and len(ips) > 0,
            "latency_ms": round(elapsed, 1),
            "ips": ips,
        }
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return {"ok": False, "latency_ms": round(elapsed, 1), "error": "timeout"}
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return {"ok": False, "latency_ms": round(elapsed, 1), "error": str(e)}


def ping_latency(host: str, count: int = 5) -> dict:
    """Measure ICMP ping latency."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", "3", host],
            capture_output=True,
            text=True,
            timeout=30,
        )
        for line in result.stdout.split("\n"):
            if "avg" in line:
                parts = line.split("=")[-1].strip().split("/")
                if len(parts) >= 2:
                    return {
                        "ok": True,
                        "min_ms": float(parts[0]),
                        "avg_ms": float(parts[1]),
                        "max_ms": float(parts[2]),
                    }
        return {"ok": result.returncode == 0, "raw": result.stdout[-200:]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def curl_test(url: str, timeout: int = 10) -> dict:
    """Test HTTP(S) connectivity via curl."""
    start = time.monotonic()
    try:
        result = subprocess.run(
            [
                "curl", "-sS", "-o", "/dev/null",
                "-w", "%{http_code} %{time_total} %{time_namelookup}",
                "--max-time", str(timeout),
                "-L", url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        elapsed = (time.monotonic() - start) * 1000
        parts = result.stdout.strip().split()
        if len(parts) >= 3:
            return {
                "ok": parts[0].startswith("2") or parts[0].startswith("3"),
                "http_code": int(parts[0]),
                "total_s": float(parts[1]),
                "dns_s": float(parts[2]),
                "total_ms": round(float(parts[1]) * 1000, 1),
                "dns_ms": round(float(parts[2]) * 1000, 1),
            }
        return {
            "ok": False,
            "elapsed_ms": round(elapsed, 1),
            "stderr": result.stderr[:200],
        }
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return {"ok": False, "elapsed_ms": round(elapsed, 1), "error": str(e)}


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_result(label: str, result: dict) -> None:
    """Print a test result row."""
    status = "OK" if result.get("ok") else "FAIL"
    latency = result.get("latency_ms") or result.get("total_ms") or "?"
    extra = ""
    if "error" in result:
        extra = f" [{result['error'][:50]}]"
    elif "http_code" in result:
        extra = f" [HTTP {result['http_code']}]"
    print(f"  {label:<35} {status:<6} {latency:>8} ms{extra}")


# ─── Test Sections ──────────────────────────────────────────────────

def test_baseline_connectivity() -> dict:
    """Test 1: Baseline TCP connectivity to target sites."""
    print_header("TEST 1: Baseline TCP Connectivity")
    results = {}
    for host, port in TARGET_SITES:
        r = tcp_connect(host, port)
        results[host] = r
        print_result(f"{host}:{port}", r)
    return results


def test_dns_resolution() -> dict:
    """Test 2: DNS resolution via different servers."""
    print_header("TEST 2: DNS Resolution (discord.com)")
    results = {}
    domains = ["discord.com", "roblox.com", "google.com"]

    for domain in domains:
        print(f"\n  --- {domain} ---")
        for name, server in DNS_SERVERS.items():
            r = dns_resolve(domain, server)
            key = f"{domain}_{name}"
            results[key] = r
            ips_str = ", ".join(r.get("ips", [])[:2]) or "none"
            print_result(
                f"  via {name:<18}",
                {**r, "latency_ms": r["latency_ms"]},
            )
            print(f"  {'':>41} IPs: {ips_str}")
    return results


def test_dns_latency_comparison() -> dict:
    """Test 3: DNS latency comparison across providers (5 iterations)."""
    print_header("TEST 3: DNS Latency Comparison (5 iterations each)")
    results = {}

    for name, server in DNS_SERVERS.items():
        latencies = []
        for _ in range(5):
            r = dns_resolve("discord.com", server)
            if r["ok"]:
                latencies.append(r["latency_ms"])
            time.sleep(0.2)
        if latencies:
            avg = round(sum(latencies) / len(latencies), 1)
            mn = round(min(latencies), 1)
            mx = round(max(latencies), 1)
            results[name] = {"avg_ms": avg, "min_ms": mn, "max_ms": mx}
            print(f"  {name:<20} avg={avg:>7} ms  "
                  f"min={mn:>7} ms  max={mx:>7} ms")
        else:
            results[name] = {"avg_ms": None, "error": "all failed"}
            print(f"  {name:<20} ALL FAILED")

    # Compare
    baseline = results.get("system_default", {}).get("avg_ms")
    if baseline:
        print(f"\n  Baseline (system): {baseline} ms")
        for name in ["cloudflare", "google", "quad9"]:
            avg = results.get(name, {}).get("avg_ms")
            if avg:
                diff = round(avg - baseline, 1)
                sign = "+" if diff > 0 else ""
                print(f"  {name:<20} {sign}{diff} ms vs baseline")

    return results


def test_https_access() -> dict:
    """Test 4: Full HTTPS access to target sites."""
    print_header("TEST 4: HTTPS Access (curl)")
    urls = [
        "https://discord.com",
        "https://cdn.discordapp.com",
        "https://roblox.com",
        "https://www.roblox.com",
        "https://google.com",
    ]
    results = {}
    for url in urls:
        r = curl_test(url)
        results[url] = r
        if r.get("ok"):
            print(f"  {url:<40} OK   "
                  f"total={r['total_ms']:>7} ms  "
                  f"dns={r['dns_ms']:>7} ms  "
                  f"HTTP {r['http_code']}")
        else:
            err = r.get("error") or r.get("stderr", "")[:60]
            print(f"  {url:<40} FAIL  {err}")
    return results


def test_ping_latency() -> dict:
    """Test 5: ICMP Ping latency to DNS servers."""
    print_header("TEST 5: Ping Latency (5 packets each)")
    targets = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
    results = {}
    for target in targets:
        r = ping_latency(target, count=5)
        results[target] = r
        if r.get("ok") and "avg_ms" in r:
            print(f"  {target:<20} avg={r['avg_ms']:>7} ms  "
                  f"min={r['min_ms']:>7} ms  max={r['max_ms']:>7} ms")
        else:
            print(f"  {target:<20} {'FAIL':>7}  "
                  f"{r.get('error', 'unknown')[:40]}")
    return results


# ─── Main ───────────────────────────────────────────────────────────

def main() -> None:
    """Run all E2E connectivity tests."""
    print("\n" + "=" * 60)
    print("  SPLITWIRE E2E CONNECTIVITY TEST")
    print("=" * 60)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    all_results = {}

    all_results["baseline_tcp"] = test_baseline_connectivity()
    all_results["dns_resolution"] = test_dns_resolution()
    all_results["dns_latency"] = test_dns_latency_comparison()
    all_results["https_access"] = test_https_access()
    all_results["ping_latency"] = test_ping_latency()

    # Summary
    print_header("SUMMARY")

    tcp_ok = sum(
        1 for r in all_results["baseline_tcp"].values() if r.get("ok")
    )
    tcp_total = len(all_results["baseline_tcp"])
    print(f"  TCP connectivity:  {tcp_ok}/{tcp_total} targets reachable")

    https_ok = sum(
        1 for r in all_results["https_access"].values() if r.get("ok")
    )
    https_total = len(all_results["https_access"])
    print(f"  HTTPS access:      {https_ok}/{https_total} sites accessible")

    dns_lat = all_results.get("dns_latency", {})
    for name in ["system_default", "cloudflare", "google", "quad9"]:
        avg = dns_lat.get(name, {}).get("avg_ms")
        if avg:
            print(f"  DNS latency ({name}): {avg} ms avg")

    # Check specific targets
    discord_tcp = all_results["baseline_tcp"].get("discord.com", {})
    roblox_tcp = all_results["baseline_tcp"].get("roblox.com", {})
    discord_https = all_results["https_access"].get(
        "https://discord.com", {}
    )
    roblox_https = all_results["https_access"].get(
        "https://roblox.com", {}
    )

    print(f"\n  discord.com: TCP={'OK' if discord_tcp.get('ok') else 'FAIL'}"
          f"  HTTPS={'OK' if discord_https.get('ok') else 'FAIL'}")
    print(f"  roblox.com:  TCP={'OK' if roblox_tcp.get('ok') else 'FAIL'}"
          f"  HTTPS={'OK' if roblox_https.get('ok') else 'FAIL'}")

    # Save results
    results_file = Path(__file__).parent / "e2e_results.json"
    try:
        with open(results_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n  Results saved to: {results_file}")
    except OSError:
        pass

    print(f"\n{'='*60}\n")

    # Exit code based on critical targets
    if not discord_tcp.get("ok") or not roblox_tcp.get("ok"):
        print("WARNING: Some target sites are not reachable via TCP")
        sys.exit(1)


if __name__ == "__main__":
    main()
