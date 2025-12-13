<p align="center">
  <img width="auto" height="128" src="https://github.com/cagritaskn/SplitWire-Turkey/blob/main/src/SplitWireTurkey/Resources/splitwire-logo-128.png">
</p>

# <p align="center"><strong>SplitWire-Turkey Linux</strong></p>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GTK4](https://img.shields.io/badge/GTK-4.0+-green.svg)](https://www.gtk.org/)
[![Ubuntu 22.04+](https://img.shields.io/badge/Ubuntu-22.04+-orange.svg)](https://ubuntu.com/)

<strong>Multilingual README (TR/EN/RU/ES)</strong>

[![TR](https://img.shields.io/badge/README-TR-blue.svg)](https://github.com/cagritaskn/SplitWire-Turkey/blob/main/README.md)
[![EN](https://img.shields.io/badge/README-EN-blue.svg)](https://github.com/cagritaskn/SplitWire-Turkey/blob/main/.github/README_EN.md)
[![RU](https://img.shields.io/badge/README-RU-blue.svg)](https://github.com/cagritaskn/SplitWire-Turkey/blob/main/.github/README_RU.md)
[![ES](https://img.shields.io/badge/README-ES-blue.svg)](https://github.com/cagritaskn/SplitWire-Turkey/blob/main/.github/README_ES.md)

</div>

---

**SplitWire-Turkey**, Turkiye'deki internet kullanicilari icin ozel olarak tasarlanmis bir DPI asimi ve tunelleme otomasyon projesidir. Internet baglanti hizinizi etkilemeden kisit asimi yapmaya yarayan acik kaynak bir **Linux** uygulamasidir. Bu arac, tek bir arayuzden bircok kisit asim yontemini otomatik olarak kurmaya ve yonetmeye yarar. Hizmet kurulumu yaptigi icin bilgisayarinizi yeniden baslattiginizda ilgili uygulamalara erismek icin fazladan bir islem yapmaniza gerek kalmaz.

**SplitWire-Turkey** is a DPI bypass and tunneling automation project specifically designed for internet users in Turkey. It is an open-source **Linux** application that bypasses restrictions without affecting your internet connection speed. This tool automates the installation and management of multiple bypass methods from a single interface. Since it installs services, you don't need to take any extra steps to access related applications after restarting your computer.

---

## Ozellikler / Features

| Ozellik | Aciklama |
|---------|----------|
| **WireGuard VPN** | Cloudflare WARP uzerinden split tunneling destegi |
| **Zapret DPI Bypass** | nfqws/tpws ile sistem geneli DPI asimi |
| **ByeDPI Proxy** | cgproxy ile uygulama bazli yonlendirme |
| **DNS Yonetimi** | DoH (DNS over HTTPS) destegi |
| **Discord Onarim** | Discord onarim ve alternatif istemci kurulumu |
| **Modern Arayuz** | GTK4/Libadwaita ile modern Linux arayuzu |
| **Coklu Dil** | Turkce, Ingilizce, Rusca, Ispanyolca |
| **systemd Entegrasyonu** | Kalici hizmetler icin systemd destegi |

---

## Ekran Goruntuleri / Screenshots

*Yakinda eklenecek / Coming soon*

---

## Sistem Gereksinimleri / System Requirements

| Gereksinim | Minimum |
|------------|---------|
| **Isletim Sistemi** | Ubuntu 22.04+, Debian 12+, Linux Mint 21+, Pop!_OS 22.04+ |
| **Mimari** | x86_64 (amd64) |
| **Python** | 3.10+ |
| **Masaustu** | GTK4 + Libadwaita destegi (GNOME 42+) |

---

## Kurulum / Installation

### Hizli Kurulum (Onerilir) / Quick Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/cagritaskn/SplitWire-Turkey/main/linux/scripts/install.sh | sudo bash
```

### Manuel Kurulum / Manual Installation

1. **Bagimliliklari yukleyin / Install dependencies:**
   ```bash
   sudo ./linux/scripts/setup-deps.sh
   ```

2. **Kurulum scriptini calistirin / Run installer:**
   ```bash
   sudo ./linux/scripts/install.sh
   ```

### Debian Paketi / Debian Package

```bash
# Paketi derleyin / Build the package
cd linux
dpkg-buildpackage -us -uc -b

# Yukleyin / Install
sudo dpkg -i ../splitwire-turkey_1.0.0_all.deb
sudo apt-get install -f  # Bagimliliklari yukle
```

### Gelistirici Kurulumu / Development Setup

```bash
# Repoyu klonlayin
git clone https://github.com/cagritaskn/SplitWire-Turkey.git
cd SplitWire-Turkey/linux

# Bagimliliklari yukleyin
sudo ./scripts/setup-deps.sh

# Gelistirici modunda yukleyin
pip install -e .

# Calistirin
splitwire
# veya
python -m splitwire
```

---

## Kullanim Rehberi / Usage Guide

### Uygulamayi Baslatma / Starting the Application

```bash
# Terminalden
splitwire

# Debug modu ile
splitwire --debug

# Veya uygulama menusunden "SplitWire" arayin
```

---

## Asim Yontemleri / Bypass Methods

### 1. WireGuard (Split Tunneling)

Cloudflare WARP uzerinden WireGuard kullanarak yalnizca secili uygulamalar icin tunelleme yapar.

**Kurulum:**
1. SplitWire'i acin
2. "Ana Sayfa" sekmesine gidin
3. "WireGuard Kur" butonuna tiklayin
4. Split tunneling icin uygulamalari secin

**Not:** Bu yontem yalnizca secili uygulamalar icin calisir (Discord, tarayicilar vb.)

---

### 2. Zapret (Sistem Geneli DPI Asimi)

nfqws kullanarak paket manipulasyonu ile DPI incelemesini atlatir. GoodbyeDPI'nin Linux karsiligi.

**Kurulum:**
1. "Zapret" sekmesine gidin
2. Hazir ayarlardan birini secin veya "Otomatik Tarama" yapin
3. "Hizmet Kur" butonuna tiklayin

**Hazir Ayarlar:**
| Preset | Aciklama |
|--------|----------|
| `turkey_discord` | Discord icin optimize edilmis |
| `turkey_general` | Genel amacli |
| `turkey_youtube` | YouTube icin optimize edilmis |
| `preset_split` | Split modu |
| `preset_fake` | Fake paket modu |
| `preset_disorder` | Disorder modu |
| `preset_tpws` | Transparent proxy |
| `preset_combined` | Kombinasyon modu |

**Tarama Hizlari:**
- **Hizli:** 2-10 dakika
- **Standart:** 5-30 dakika
- **Tam:** 10-50 dakika

---

### 3. ByeDPI (Uygulama Bazli)

Secili uygulamalari yerel SOCKS5 proxy uzerinden yonlendirir.

**Kurulum:**
1. "ByeDPI" sekmesine gidin
2. Yonlendirilecek uygulamalari secin
3. Preset secin (disorder, split, fake, oob)
4. "Baslat" butonuna tiklayin

---

### 4. GoodbyeDPI Sayfasi

Windows GoodbyeDPI'a benzer arayuz ile Zapret konfigurasyonu.

**Kurulum:**
1. "GoodbyeDPI" sekmesine gidin
2. Hazir ayar secin
3. Blacklist kullanmak isterseniz aktiflesirin
4. "Hizmet Kur" butonuna tiklayin

---

## DNS Ayarlari / DNS Configuration

1. "Gelismis" sekmesine gidin
2. DNS saglayici secin:
   - **Google** (8.8.8.8, 8.8.4.4)
   - **Cloudflare** (1.1.1.1, 1.0.0.1)
   - **Quad9** (9.9.9.9)
   - **OpenDNS** (208.67.222.222)
   - **AdGuard** (94.140.14.14)
   - **Turk Telekom** (195.175.39.39)
3. DoH (DNS over HTTPS) aktiflesirin/kapatin
4. "DNS Uygula" butonuna tiklayin

---

## Discord Onarim / Discord Repair

Discord "Checking for updates" veya "Starting..." ekraninda kaliyorsa:

1. "Onarim" sekmesine gidin
2. "Discord Onar" butonunu deneyin
3. Basarisiz olursa "Discord PTB Yukle" deneyin
4. Alternatif olarak "WebCord Yukle" deneyin

**Desteklenen Discord Versiyonlari:**
- Discord (Standart)
- Discord PTB (Public Test Build)
- Discord Canary
- WebCord (Alternatif istemci)

---

## Hizmetler / Services

SplitWire asagidaki systemd hizmetlerini olusturur:

| Hizmet | Aciklama |
|--------|----------|
| `splitwire-wg.service` | WireGuard VPN tuneli |
| `splitwire-wg-refresh.timer` | 30 dakikada bir baglanti yenileme |
| `splitwire-zapret.service` | Zapret DPI asimi |
| `splitwire-byedpi.service` | ByeDPI proxy |
| `splitwire-cgproxy.service` | Uygulama yonlendirme |

**Hizmet Yonetimi:**
```bash
# Durum kontrolu
systemctl status splitwire-wg

# Loglari goruntule
journalctl -u splitwire-zapret -f

# Tum hizmetleri durdur
sudo systemctl stop splitwire-wg splitwire-zapret splitwire-byedpi

# Hizmetleri baslat
sudo systemctl start splitwire-wg

# Otomatik baslatmayi etkinlestir
sudo systemctl enable splitwire-wg
```

---

## Kaldirma / Uninstallation

### Kaldirma Scripti / Uninstaller Script

```bash
sudo ./linux/scripts/uninstall.sh
```

### Secenekler / Options

```bash
# Konfigurasyonu koru
sudo ./linux/scripts/uninstall.sh --keep-config

# Zapret kurulumunu koru
sudo ./linux/scripts/uninstall.sh --keep-zapret

# Tam kaldirma (kullanici verileri dahil)
sudo ./linux/scripts/uninstall.sh --purge
```

### Debian Paketi / Debian Package

```bash
# Paketi kaldir
sudo apt remove splitwire-turkey

# Konfigurasyonla birlikte kaldir
sudo apt purge splitwire-turkey
```

---

## Sorun Giderme / Troubleshooting

### "Register failed" Hatasi

Cloudflare API bolgenizde engellenebilir:
1. Kayit icin gecici olarak VPN kullanin
2. Alternatif yontemleri deneyin (Zapret, ByeDPI)

### Discord "Checking for updates" Ekraninda Kaliyor

1. Modeminizi kapatip 15-30 saniye bekleyin
2. Bilgisayarinizi yeniden baslatin
3. SplitWire'da Discord Onar butonunu kullanin
4. Discord PTB veya WebCord yukleyin

### Hizmetler Baslamiyor

```bash
# Hizmet durumunu kontrol edin
systemctl status splitwire-wg

# Loglari kontrol edin
journalctl -u splitwire-wg -n 50

# systemd'yi yeniden yukleyin
sudo systemctl daemon-reload
```

### Yetki Sorunlari

```bash
# splitwire grubuna eklendiginizden emin olun
sudo usermod -aG splitwire $USER
# Cikis yapin ve tekrar giris yapin
```

---

## Konfigürasyon / Configuration

Konfigurasyon dosyalari:
- **Sistem:** `/etc/splitwire/`
- **Kullanici:** `~/.config/splitwire/`
- **Loglar:** `~/.cache/splitwire/logs/`

### Ana Konfigurasyon (`config.json`)

```json
{
    "theme": "system",
    "language": "tr",
    "minimize_to_tray": true,
    "auto_start": false,
    "check_updates": true,
    "dns": {
        "enabled": false,
        "primary": "1.1.1.1",
        "secondary": "1.0.0.1",
        "doh_enabled": false
    },
    "wireguard": {
        "auto_connect": false,
        "split_tunnel_enabled": true,
        "allowed_apps": ["Discord", "Firefox"]
    },
    "zapret": {
        "enabled": false,
        "mode": "nfqws",
        "strategy": "default"
    },
    "byedpi": {
        "enabled": false,
        "port": 10080,
        "strategy": "disorder"
    }
}
```

### Blacklist (`blacklist.txt`)

DPI asimi icin domainler (satirda bir tane):
```
discord.com
discord.gg
discordapp.com
discord.media
discordapp.net
```

---

## Proje Yapisi / Project Structure

```
linux/
├── src/splitwire/          # Ana Python paketi
│   ├── core/               # Config, Logger, Shell, Language
│   ├── services/           # WireGuard, Zapret, ByeDPI, DNS, Discord
│   ├── ui/                 # GTK4 arayuzu
│   │   ├── pages/          # Sayfa bileşenleri
│   │   └── widgets/        # Ortak UI bileşenleri
│   └── utils/              # Sistem yardimcilari
├── tests/                  # Test dosyalari
├── systemd/                # systemd hizmet dosyalari
├── scripts/                # Kurulum/kaldirma scriptleri
├── debian/                 # Debian paketleme
└── config/                 # Varsayilan konfigurasyonlar
```

---

## Testler / Testing

```bash
# Tum testleri calistir
cd linux
pytest

# Coverage raporu ile
pytest --cov=splitwire --cov-report=html

# Belirli bir test dosyasi
pytest tests/test_config.py -v
```

---

## Dil Secenekleri / Language Options

SplitWire 4 dili destekler:

- **Turkce** - Varsayilan
- **English** - Ingilizce
- **Русский** - Rusca
- **Español** - Ispanyolca

Dil degistirmek icin Ayarlar sekmesinden dil secin.

---

## Tesekkurler ve Atiflar / Credits and Attributions

- **[wgcf](https://github.com/ViRb3/wgcf)** by **[ViRb3](https://github.com/ViRb3)** - Cloudflare WARP kayit
- **[zapret](https://github.com/bol-van/zapret)** by **[bol-van](https://github.com/bol-van)** - DPI bypass toolkit
- **[ciadpi/ByeDPI](https://github.com/hufrea/byedpi)** by **[hufrea](https://github.com/hufrea/)** - SOCKS5 proxy
- **[cgproxy](https://github.com/springzfx/cgproxy)** - Uygulama yonlendirme konsepti
- **[WebCord](https://github.com/ArmCord/ArmCord)** - Alternatif Discord istemcisi
- **[Techolay.net](https://techolay.net/sosyal/)** kurucusu **[Recep Baltas](https://www.youtube.com/@Techolay/)**'a tesekkurler
- **[Bal Porsugu](https://www.youtube.com/@sauali)**'na Zapret presetleri icin tesekkurler

---

## Telif Hakki / Copyright

```
Copyright (c) 2025 Cagri Taskin

Bu proje MIT lisansi altinda lisanslanmistir.
Detaylar icin LICENSE dosyasina bakin.

This project is licensed under the MIT License.
See LICENSE file for details.
```

---

## Bagis ve Destek / Donations and Support

Bu programi kullanmak tamamen ucretsizdir. Calismalara destek olmak icin:

**GitHub Sponsor:**

[![Sponsor](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86)](https://github.com/sponsors/cagritaskn)

**Patreon:**

[![Static Badge](https://img.shields.io/badge/cagritaskn-purple?logo=patreon&label=Patreon)](https://www.patreon.com/cagritaskn/membership)

---

## Sorumluluk Reddi Beyani / Disclaimer

**Bu yazilim egitim amacli olusturulmustur.**

- Bu arac sadece kodlama egitimi ve kisisel kullanim amaclidir
- Ticari kullanim icin uygun degildir
- Gelistirici, bu yazilimin kullanimindan dogabilecek herhangi bir zarardan sorumlu degildir
- Kullanicilar bu yazilimi kendi sorumluluklarinda kullanirlar
- Yasal duzenlemelere uygun kullanim kullanicinin sorumluluğundadir

> [!IMPORTANT]
> Bu programin kullanimindan dogan her turlu yasal sorumluluk kullanan kisiye aittir. Uygulama yalnizca egitim ve arastirma amaclari ile yazilmis olup; bu uygulamayi bu sartlar altinda kullanmak ya da kullanmamak kullanicinin kendi secimidir.

---

## Hata Bildirimi / Bug Reports

Hata bildirmek icin [SplitWire-Turkey Issues](https://github.com/cagritaskn/SplitWire-Turkey/issues) sayfasina gidin ve:

1. **New Issue** butonuna tiklayin
2. Sorunuzu detayli aciklayin
3. Log dosyalarini ekleyin (`~/.cache/splitwire/logs/`)
4. Sistem bilgilerinizi paylasın (`splitwire --check-system`)
