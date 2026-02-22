# SplitWire-Turkey Linux

An open-source network privacy and traffic management toolkit for Linux. Provides VPN split tunneling, DNS-over-HTTPS configuration, traffic analysis tools, and application-specific routing capabilities.

## Intended Use Cases

This software is a **general-purpose, dual-use network toolkit** designed for the following legitimate purposes:

- **Privacy protection** - Encrypt and route network traffic to protect user privacy
- **Network security research** - Analyze DPI (Deep Packet Inspection) behavior and test network resilience
- **DNS security** - Configure encrypted DNS (DoH) to prevent DNS spoofing and surveillance
- **Split tunneling** - Route only specific application traffic through VPN for bandwidth optimization
- **Application-specific routing** - Direct individual application traffic through SOCKS5 proxies
- **Network diagnostics** - Troubleshoot connectivity issues with Discord and other applications
- **Educational use** - Learn about networking protocols, VPN tunneling, packet analysis, and Linux system administration

## Features

- **WireGuard VPN** with split tunneling support via Cloudflare WARP
- **Traffic analysis tools** using Zapret/nfqws for DPI inspection and packet management
- **ByeDPI Proxy** for application-specific routing via cgroups
- **DNS Management** with DoH (DNS over HTTPS) support
- **Discord diagnostics** and alternative client installation
- **Modern GTK4/Libadwaita** interface
- **Multi-language** support (Turkish, English, Russian, Spanish)
- **systemd integration** for persistent services

## Screenshots

*Coming soon*

## System Requirements

- **OS**: Ubuntu 22.04+, Debian 12+, Linux Mint 21+, Pop!_OS 22.04+
- **Architecture**: x86_64 (amd64)
- **Python**: 3.10+
- **Desktop**: GTK4 + Libadwaita support

## Installation

### Quick Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/cagritaskn/SplitWire-Turkey/main/linux/scripts/install.sh | sudo bash
```

### Manual Installation

1. **Install dependencies:**
   ```bash
   sudo ./scripts/setup-deps.sh
   ```

2. **Run installer:**
   ```bash
   sudo ./scripts/install.sh
   ```

### Debian Package

```bash
# Build the package
dpkg-buildpackage -us -uc -b

# Install
sudo dpkg -i ../splitwire-turkey_1.0.0_all.deb
sudo apt-get install -f  # Install dependencies
```

## Usage

### Starting the Application

```bash
# From terminal
splitwire

# Or from application menu
# Search for "SplitWire"
```

### Network Tools

#### 1. WireGuard (Split Tunneling)

Uses Cloudflare WARP via WireGuard with split tunneling to route only specific applications through VPN.

1. Open SplitWire
2. Go to "Ana Sayfa" (Main Page)
3. Click "WireGuard Kur" (Install WireGuard)
4. Select applications for split tunneling

#### 2. Zapret (Traffic Analysis & Management)

Uses nfqws for network packet analysis and traffic management.

1. Go to "Zapret" page
2. Choose a preset or run "Otomatik Tarama" (Auto Scan)
3. Click "Hizmet Kur" (Install Service)

**Presets:**
- `general` - General purpose configuration
- `split` - Split mode
- `fake` - Fake packet mode
- `disorder` - Disorder mode

#### 3. ByeDPI (Application-specific Routing)

Routes specific applications through a local SOCKS5 proxy.

1. Go to "ByeDPI" page
2. Select applications to route
3. Click "Baslat" (Start)

### DNS Configuration

1. Go to "Gelismis" (Advanced) page
2. Select DNS provider (Cloudflare, Google, Quad9)
3. Enable/disable DoH (DNS over HTTPS)
4. Click "DNS Uygula" (Apply DNS)

### Discord Diagnostics

If Discord is stuck on "Checking for updates":

1. Go to "Onarim" (Repair) page
2. Try "Discord Onar" (Repair Discord)
3. If unsuccessful, try installing alternative clients

## Services

SplitWire creates the following systemd services:

| Service | Description |
|---------|-------------|
| `splitwire-wg.service` | WireGuard VPN tunnel |
| `splitwire-wg-refresh.timer` | Periodic connection refresh |
| `splitwire-zapret.service` | Zapret traffic management |
| `splitwire-byedpi.service` | ByeDPI proxy |
| `splitwire-cgproxy.service` | Application routing |

**Managing services:**
```bash
# Check status
systemctl status splitwire-wg

# View logs
journalctl -u splitwire-zapret -f

# Stop all services
sudo systemctl stop splitwire-wg splitwire-zapret splitwire-byedpi
```

## Uninstallation

### Using Uninstaller

```bash
sudo ./scripts/uninstall.sh
```

### Options

```bash
# Keep configuration files
sudo ./scripts/uninstall.sh --keep-config

# Keep Zapret installation
sudo ./scripts/uninstall.sh --keep-zapret

# Full removal including user data
sudo ./scripts/uninstall.sh --purge
```

### Debian Package

```bash
# Remove package
sudo apt remove splitwire-turkey

# Remove with configuration
sudo apt purge splitwire-turkey
```

## Troubleshooting

### "Register failed" Error

Cloudflare API may be unreachable in your region. Try:
1. Check your network connectivity
2. Use alternative network tools (Zapret, ByeDPI)

### Discord Stuck on "Checking for updates"

1. Restart your router (wait 15-30 seconds)
2. Restart your computer
3. Use Discord Diagnostics in SplitWire
4. Try installing Discord PTB or WebCord

### Services Not Starting

```bash
# Check service status
systemctl status splitwire-wg

# Check logs
journalctl -u splitwire-wg -n 50

# Reload systemd
sudo systemctl daemon-reload
```

### Permission Issues

Ensure you're in the `splitwire` group:
```bash
sudo usermod -aG splitwire $USER
# Log out and back in
```

## Configuration

Configuration files are stored in:
- System: `/etc/splitwire/`
- User: `~/.config/splitwire/`

### Main Config (`config.json`)

```json
{
    "version": "1.0.0",
    "language": "tr",
    "theme": "system",
    "auto_dns": true,
    "dns_server": "cloudflare",
    "doh_enabled": true
}
```

### Domain List (`blacklist.txt`)

Domains for traffic management (one per line):
```
discord.com
discord.gg
discordapp.com
```

## Building from Source

### Requirements

- Python 3.10+
- GTK4 development libraries
- PyGObject

### Steps

```bash
# Clone repository
git clone https://github.com/cagritaskn/SplitWire-Turkey.git
cd SplitWire-Turkey/linux

# Install dependencies
sudo ./scripts/setup-deps.sh

# Install in development mode
pip install -e .

# Run
python -m splitwire
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

```
Copyright (c) 2025 Cagri Taskin

This project is licensed under the MIT License.
See LICENSE file for details.
```

## Credits

- **[wgcf](https://github.com/ViRb3/wgcf)** by ViRb3
- **[zapret](https://github.com/bol-van/zapret)** by bol-van
- **[ciadpi](https://github.com/hufrea/byedpi)** by hufrea
- **[cgproxy](https://github.com/springzfx/cgproxy)** concept

## Legal Notice & Disclaimer

### Nature of This Software

This software is a **general-purpose, dual-use network toolkit**. It integrates open-source networking
components (WireGuard, Zapret, ByeDPI) that are widely used for legitimate purposes including privacy
protection, network security research, DNS security configuration, and traffic analysis.

The individual components used by this project are independently developed, openly available
open-source projects hosted on public platforms (GitHub), and are used in corporate, academic,
and personal environments worldwide.

### Intended Purpose

This software is developed and distributed for the following purposes:

1. **Network privacy and security research** - Understanding and analyzing DPI systems, encrypted
   DNS configuration, and VPN split tunneling
2. **Educational use** - Learning about networking protocols, Linux system administration,
   packet analysis, and open-source software development
3. **Personal privacy protection** - Encrypting DNS queries, routing traffic through VPN tunnels,
   and managing application-specific network configurations

### User Responsibility

- Users are solely responsible for ensuring their use of this software complies with all
  applicable local, national, and international laws and regulations
- The developers do not endorse, encourage, or condone any use of this software that violates
  applicable laws
- This software is provided "AS IS" without warranty of any kind, as detailed in the MIT License

### Open Source & Transparency

This project is fully open-source under the MIT License. All source code is publicly available
for inspection, audit, and review. The transparent nature of this project demonstrates that it
is developed for legitimate, lawful purposes.

### No Liability

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY
ARISING FROM THE USE OF THIS SOFTWARE. See the [LICENSE](../LICENSE) file for complete terms.