#!/bin/bash
#
# Emergency Network Restore Script for SplitWire-Turkey Integration Tests
#
# This script forcefully restores network connectivity when the kill switch
# fails or when manual intervention is required after a failed test.
#
# Usage:
#   sudo ./tests/emergency_restore.sh
#   sudo ./tests/emergency_restore.sh --nuclear   # Force full cleanup
#
# IMPORTANT: This script requires root privileges!
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

NUCLEAR=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --nuclear)
            NUCLEAR=true
            shift
            ;;
    esac
done

echo "============================================================"
echo "  SPLITWIRE-TURKEY EMERGENCY NETWORK RESTORE"
echo "============================================================"
echo ""

# Check for root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Function to run command and report status
run_cmd() {
    local description="$1"
    shift
    echo -n "  $description... "
    if "$@" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${YELLOW}SKIPPED${NC}"
        return 0  # Don't fail on individual command failures
    fi
}

echo "Phase 1: Killing bypass processes"
echo "-------------------------------------------"
run_cmd "Killing nfqws" pkill -9 nfqws
run_cmd "Killing tpws" pkill -9 tpws
run_cmd "Killing ciadpi" pkill -9 ciadpi
run_cmd "Killing goodbyedpi" pkill -9 goodbyedpi
echo ""

echo "Phase 2: Cleaning iptables rules"
echo "-------------------------------------------"
run_cmd "Flushing mangle POSTROUTING" iptables -t mangle -F POSTROUTING
run_cmd "Flushing nat OUTPUT" iptables -t nat -F OUTPUT
run_cmd "Flushing nat PREROUTING" iptables -t nat -F PREROUTING
echo ""

echo "Phase 3: Stopping WireGuard"
echo "-------------------------------------------"
run_cmd "Stopping WireGuard (wg-quick)" wg-quick down splitwire
run_cmd "Deleting WireGuard interface" ip link delete splitwire
echo ""

echo "Phase 4: Restoring DNS"
echo "-------------------------------------------"
run_cmd "Removing SplitWire DNS config" rm -f /etc/systemd/resolved.conf.d/splitwire.conf
run_cmd "Restarting systemd-resolved" systemctl restart systemd-resolved
echo ""

echo "Phase 5: Stopping SplitWire systemd services"
echo "-------------------------------------------"
for service in splitwire-zapret splitwire-byedpi splitwire-dns splitwire-wireguard; do
    run_cmd "Stopping ${service}.service" systemctl stop ${service}.service
done
echo ""

if $NUCLEAR; then
    echo "Phase 6: NUCLEAR CLEANUP (--nuclear flag)"
    echo "-------------------------------------------"
    echo -e "${YELLOW}WARNING: Flushing ALL iptables rules!${NC}"
    run_cmd "Flushing filter table" iptables -F
    run_cmd "Flushing nat table" iptables -t nat -F
    run_cmd "Flushing mangle table" iptables -t mangle -F
    run_cmd "Flushing raw table" iptables -t raw -F
    run_cmd "Resetting filter chains" iptables -X
    run_cmd "Resetting nat chains" iptables -t nat -X
    run_cmd "Resetting mangle chains" iptables -t mangle -X
    echo ""

    echo "Phase 7: Restarting network services"
    echo "-------------------------------------------"
    run_cmd "Restarting NetworkManager" systemctl restart NetworkManager
    run_cmd "Restarting systemd-networkd" systemctl restart systemd-networkd
    run_cmd "Restarting systemd-resolved" systemctl restart systemd-resolved
    echo ""
fi

echo "Phase 8: Connectivity verification"
echo "-------------------------------------------"
echo -n "  Checking connectivity to 8.8.8.8... "
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo -n "  Checking connectivity to 1.1.1.1... "
if ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo -n "  Checking DNS resolution (google.com)... "
if nslookup google.com >/dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo ""
echo "============================================================"

# Final connectivity check
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: Network connectivity restored!${NC}"
    exit 0
else
    echo -e "${RED}WARNING: Network connectivity NOT restored!${NC}"
    echo ""
    echo "Manual steps to try:"
    echo "  1. sudo systemctl restart NetworkManager"
    echo "  2. sudo dhclient -r && sudo dhclient"
    echo "  3. Reboot the system"
    exit 1
fi
