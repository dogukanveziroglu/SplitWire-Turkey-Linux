# SplitWire-Turkey Linux

Linux icin acik kaynakli bir ag gizliligi ve trafik yonetimi araci. VPN ayrik tunelleme, DNS-over-HTTPS yapilandirmasi, trafik analiz araclari ve uygulamaya ozel yonlendirme ozellikleri saglar.

## Kullanim Amaci

Bu yazilim asagidaki mesru amaclar icin tasarlanmis **genel amacli, cift kullanimli (dual-use) bir ag aracidir**:

- **Gizlilik korumasi** - Kullanici gizliligini korumak icin ag trafigini sifreleme ve yonlendirme
- **Ag guvenlik arastirmasi** - DPI (Derin Paket Incelemesi) davranisini analiz etme ve ag dayanikliligini test etme
- **DNS guvenligi** - DNS sahteciligi ve gozetlemeyi onlemek icin sifreli DNS (DoH) yapilandirmasi
- **Ayrik tunelleme** - Bant genisligi optimizasyonu icin yalnizca belirli uygulama trafigini VPN uzerinden yonlendirme
- **Uygulamaya ozel yonlendirme** - Bireysel uygulama trafigini SOCKS5 proxy'ler uzerinden yonlendirme
- **Ag teshisi** - Discord ve diger uygulamalarla baglanti sorunlarini giderme
- **Egitim amacli kullanim** - Ag protokolleri, VPN tunelleme, paket analizi ve Linux sistem yonetimi hakkinda ogrenme

## Ozellikler

- **WireGuard VPN** - Cloudflare WARP ile ayrik tunelleme destegi
- **Trafik analiz araclari** - DPI incelemesi ve paket yonetimi icin Zapret/nfqws
- **ByeDPI Proxy** - cgroups ile uygulamaya ozel yonlendirme
- **DNS Yonetimi** - DoH (DNS over HTTPS) destegi
- **Discord teshis araclari** ve alternatif istemci kurulumu
- **Modern GTK4/Libadwaita** arayuzu
- **Coklu dil** destegi (Turkce, Ingilizce, Rusca, Ispanyolca)
- **systemd entegrasyonu** - Kalici hizmetler

## Ekran Goruntuleri

*Yakinda*

## Sistem Gereksinimleri

- **Isletim Sistemi**: Ubuntu 22.04+, Debian 12+, Linux Mint 21+, Pop!_OS 22.04+
- **Mimari**: x86_64 (amd64)
- **Python**: 3.10+
- **Masaustu**: GTK4 + Libadwaita destegi

## Kurulum

### Hizli Kurulum (Onerilen)

```bash
curl -sSL https://raw.githubusercontent.com/cagritaskn/SplitWire-Turkey/main/linux/scripts/install.sh | sudo bash
```

### Manuel Kurulum

1. **Bagimliliklari yukleyin:**
   ```bash
   sudo ./scripts/setup-deps.sh
   ```

2. **Kurulum scriptini calistirin:**
   ```bash
   sudo ./scripts/install.sh
   ```

### Debian Paketi

```bash
# Paketi derleyin
dpkg-buildpackage -us -uc -b

# Yukleyin
sudo dpkg -i ../splitwire-turkey_1.0.0_all.deb
sudo apt-get install -f  # Bagimliliklari yukle
```

## Kullanim

### Uygulamayi Baslatma

```bash
# Terminalden
splitwire

# Veya uygulama menusunden
# "SplitWire" arayin
```

### Ag Araclari

#### 1. WireGuard (Ayrik Tunelleme)

Cloudflare WARP'i WireGuard ile kullanarak yalnizca belirli uygulamalari VPN uzerinden yonlendirir.

1. SplitWire'i acin
2. "Ana Sayfa"ya gidin
3. "WireGuard Kur" butonuna tiklayin
4. Ayrik tunelleme icin uygulamalari secin

#### 2. Zapret (Trafik Analizi ve Yonetimi)

Ag paketi analizi ve trafik yonetimi icin nfqws kullanir.

1. "Zapret" sayfasina gidin
2. Hazir ayar secin veya "Otomatik Tarama" calistirin
3. "Hizmet Kur" butonuna tiklayin

**Hazir Ayarlar:**
- `general` - Genel amacli yapilandirma
- `split` - Split modu
- `fake` - Sahte paket modu
- `disorder` - Disorder modu

#### 3. ByeDPI (Uygulamaya Ozel Yonlendirme)

Belirli uygulamalari yerel SOCKS5 proxy uzerinden yonlendirir.

1. "ByeDPI" sayfasina gidin
2. Yonlendirilecek uygulamalari secin
3. "Baslat" butonuna tiklayin

### DNS Yapilandirmasi

1. "Gelismis" sayfasina gidin
2. DNS saglayicisini secin (Cloudflare, Google, Quad9)
3. DoH'u (DNS over HTTPS) etkinlestirin/devre disi birakin
4. "DNS Uygula" butonuna tiklayin

### Discord Teshis Araclari

Discord "Checking for updates" ekraninda takiliyorsa:

1. "Onarim" sayfasina gidin
2. "Discord Onar" secenegini deneyin
3. Basarisiz olursa alternatif istemcileri kurun

## Hizmetler

SplitWire asagidaki systemd hizmetlerini olusturur:

| Hizmet | Aciklama |
|--------|----------|
| `splitwire-wg.service` | WireGuard VPN tuneli |
| `splitwire-wg-refresh.timer` | Periyodik baglanti yenileme |
| `splitwire-zapret.service` | Zapret trafik yonetimi |
| `splitwire-byedpi.service` | ByeDPI proxy |
| `splitwire-cgproxy.service` | Uygulama yonlendirme |

**Hizmetleri yonetme:**
```bash
# Durumu kontrol et
systemctl status splitwire-wg

# Loglari goruntule
journalctl -u splitwire-zapret -f

# Tum hizmetleri durdur
sudo systemctl stop splitwire-wg splitwire-zapret splitwire-byedpi
```

## Kaldirma

### Kaldirma Scripti Kullanarak

```bash
sudo ./scripts/uninstall.sh
```

### Secenekler

```bash
# Yapilandirma dosyalarini koru
sudo ./scripts/uninstall.sh --keep-config

# Zapret kurulumunu koru
sudo ./scripts/uninstall.sh --keep-zapret

# Kullanici verileri dahil tam kaldirma
sudo ./scripts/uninstall.sh --purge
```

### Debian Paketi

```bash
# Paketi kaldir
sudo apt remove splitwire-turkey

# Yapilandirma ile birlikte kaldir
sudo apt purge splitwire-turkey
```

## Sorun Giderme

### "Register failed" Hatasi

Cloudflare API bolgenizden erisilemeyebilir. Deneyin:
1. Ag baglantinizi kontrol edin
2. Alternatif ag araclarini kullanin (Zapret, ByeDPI)

### Discord "Checking for updates" Ekraninda Takili Kalma

1. Modeminizi yeniden baslatin (15-30 saniye bekleyin)
2. Bilgisayarinizi yeniden baslatin
3. SplitWire'daki Discord teshis araclarini kullanin
4. Discord PTB veya WebCord kurmayi deneyin

### Hizmetler Baslamiyor

```bash
# Hizmet durumunu kontrol et
systemctl status splitwire-wg

# Loglari kontrol et
journalctl -u splitwire-wg -n 50

# systemd'yi yeniden yukle
sudo systemctl daemon-reload
```

### Izin Sorunlari

`splitwire` grubunda oldugunuzdan emin olun:
```bash
sudo usermod -aG splitwire $USER
# Cikis yapin ve tekrar giris yapin
```

## Yapilandirma

Yapilandirma dosyalari:
- Sistem: `/etc/splitwire/`
- Kullanici: `~/.config/splitwire/`

### Ana Yapilandirma (`config.json`)

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

### Domain Listesi (`blacklist.txt`)

Trafik yonetimi icin domainler (satirda bir tane):
```
discord.com
discord.gg
discordapp.com
```

## Kaynaktan Derleme

### Gereksinimler

- Python 3.10+
- GTK4 gelistirme kutuphaneleri
- PyGObject

### Adimlar

```bash
# Repoyu klonlayin
git clone https://github.com/cagritaskn/SplitWire-Turkey.git
cd SplitWire-Turkey/linux

# Bagimliliklari yukleyin
sudo ./scripts/setup-deps.sh

# Gelistirme modunda yukleyin
pip install -e .

# Calistirin
python -m splitwire
```

## Katki

1. Repoyu forklayim
2. Ozellik dali olusturun
3. Degisikliklerinizi yapin
4. Pull request gonderin

## Lisans

```
Telif Hakki (c) 2025 Cagri Taskin

Bu proje MIT Lisansi altinda lisanslanmistir.
Detaylar icin LICENSE dosyasina bakin.
```

## Tesekkurler

- **[wgcf](https://github.com/ViRb3/wgcf)** - ViRb3
- **[zapret](https://github.com/bol-van/zapret)** - bol-van
- **[ciadpi](https://github.com/hufrea/byedpi)** - hufrea
- **[cgproxy](https://github.com/springzfx/cgproxy)** konsepti

## Yasal Bildirim ve Sorumluluk Reddi

### Yazilimin Niteligiu

Bu yazilim **genel amacli, cift kullanimli (dual-use) bir ag aracidir**. Gizlilik korumasi, ag
guvenlik arastirmasi, DNS guvenlik yapilandirmasi ve trafik analizi gibi mesru amaclarla yaygin
olarak kullanilan acik kaynakli ag bilesenlerini (WireGuard, Zapret, ByeDPI) entegre eder.

Bu proje tarafindan kullanilan bireysel bilesenler bagimsiz olarak gelistirilmis, acik
platformlarda (GitHub) serbestce erisime acik, acik kaynakli projelerdir ve kurumsal,
akademik ve kisisel ortamlarda dunya capinda kullanilmaktadir.

### Amac

Bu yazilim asagidaki amaclarla gelistirilmis ve dagitilmistir:

1. **Ag gizliligi ve guvenlik arastirmasi** - DPI sistemlerini anlama ve analiz etme,
   sifreli DNS yapilandirmasi ve VPN ayrik tunelleme
2. **Egitim amacli kullanim** - Ag protokolleri, Linux sistem yonetimi, paket analizi
   ve acik kaynak yazilim gelistirme hakkinda ogrenme
3. **Kisisel gizlilik korumasi** - DNS sorgularini sifreleme, trafigi VPN tunelleri
   uzerinden yonlendirme ve uygulamaya ozel ag yapilandirmalarini yonetme

### Kullanici Sorumlulugu

- Kullanicilar, bu yazilimin kullaniminin yururlukteki tum yerel, ulusal ve uluslararasi
  yasa ve yonetmeliklere uygunlugunu saglamaktan yalnizca kendileri sorumludur
- Gelistiriciler, bu yazilimin yururlukteki yasalari ihlal edecek sekilde kullanimini
  desteklememekte, tesvik etmemekte ve hosgorememektedir
- Bu yazilim, MIT Lisansinda ayrintili olarak belirtildigi uzere, hicbir turde garanti
  olmaksizin "OLDUGU GIBI" saglammaktadir

### Acik Kaynak ve Seffaflik

Bu proje MIT Lisansi altinda tamamen acik kaynaklidir. Tum kaynak kodu inceleme, denetim
ve gozden gecirme icin kamuya aciktir. Bu projenin seffaf yapisi, mesru ve yasal amaclarla
gelistirildigini ortaya koymaktadir.

### Sorumluluk Reddi

YAZILIM, ACIK VEYA ZIMNI HICBIR TURDE GARANTI OLMAKSIZIN "OLDUGU GIBI" SAGLAMMAKTADIR.
YAZARLAR VEYA TELIF HAKKI SAHIPLERI, BU YAZILIMIN KULLANIMINDAN KAYNAKLANAN HICBIR TALEP,
HASAR VEYA DIGER SORUMLULUKTAN SORUMLU TUTULAMAZ. Tam kosullar icin [LICENSE](../LICENSE)
dosyasina bakin.
