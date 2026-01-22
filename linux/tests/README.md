# SplitWire-Turkey Linux Integration Tests

Bu dizin, SplitWire-Turkey Linux'un kapsamlı entegrasyon testlerini içerir.

## Kritik Uyarı

**Network operasyonları sırasında internet bağlantısı kesilirse Claude müdahale edemez!**

Bu nedenle:
1. Kill switch mekanizması her zaman aktif
2. Her testten sonra otomatik cleanup
3. Manuel kurtarma scripti mevcut

## Test Aşamaları (Risk Sırasına Göre)

| Aşama | Testler | Risk | Kill Switch |
|-------|---------|------|-------------|
| 0-3 | Config, language, backup, discord | YOK | Gerekmez |
| 4 | DNS testleri | ORTA | 60s timeout |
| 5 | ByeDPI testleri | ORTA | 60s timeout |
| 6 | WireGuard testleri | ORTA-YÜKSEK | 90s timeout |
| 7 | Zapret testleri | YÜKSEK | 45s/5s strict |

## Çalıştırma Sırası

### 1. Önce Emergency Restore Test Et
```bash
# Script'in çalıştığından emin ol
sudo ./tests/emergency_restore.sh
```

### 2. Güvenli Testler (Kill Switch Gerekmez)
```bash
# Root gerekmez
pytest tests/test_integration_safe.py -v

# Veya marker ile
pytest tests/ -m "phase0 or phase1 or phase2 or phase3" -v
```

### 3. DNS Testleri (Phase 4)
```bash
sudo pytest tests/test_integration_dns.py -v
```

### 4. ByeDPI Testleri (Phase 5)
```bash
sudo pytest tests/test_integration_byedpi.py -v
```

### 5. WireGuard Testleri (Phase 6)
```bash
sudo pytest tests/test_integration_wireguard.py -v
```

### 6. Zapret Testleri (Phase 7) - EN RİSKLİ
```bash
# EN SON çalıştır!
sudo pytest tests/test_integration_zapret.py -v
```

### 7. Her Aşamadan Sonra Connectivity Doğrula
```bash
ping -c 3 8.8.8.8
nslookup google.com
```

## Tüm Testleri Sırayla Çalıştırma

```bash
# Güvenli testler
pytest tests/ -m "phase0 or phase1 or phase2 or phase3" -v

# Riskli testler (root gerekli)
sudo pytest tests/test_integration_dns.py tests/test_integration_byedpi.py tests/test_integration_wireguard.py tests/test_integration_zapret.py -v
```

## Kill Switch Kullanımı

Kill switch otomatik olarak pytest fixtures aracılığıyla yönetilir.

### Manuel Kullanım

```python
from kill_switch import KillSwitchContext

with KillSwitchContext(timeout=60, threshold=10) as ks:
    # Riskli network operasyonları
    pass
```

### Kill Switch Parametreleri

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `timeout` | Maksimum çalışma süresi (saniye) | 60 |
| `threshold` | Bağlantı kaybı eşiği (saniye) | 10 |
| `nuclear_enabled` | Son çare tam temizlik | True |

### Manuel Tetikleme

```bash
# PID'yi bul
ps aux | grep kill_switch

# SIGUSR1 ile tetikle
kill -USR1 <PID>
```

## Acil Kurtarma

Test başarısız olursa veya bağlantı kesilirse:

```bash
# 1. Otomatik kurtarma
sudo ./tests/emergency_restore.sh

# 2. Daha agresif kurtarma
sudo ./tests/emergency_restore.sh --nuclear

# 3. Manuel kurtarma
sudo pkill -9 nfqws tpws ciadpi
sudo iptables -t mangle -F POSTROUTING
sudo iptables -t nat -F OUTPUT
sudo wg-quick down splitwire
sudo rm -f /etc/systemd/resolved.conf.d/splitwire.conf
sudo systemctl restart systemd-resolved
```

## Test Dosyaları

| Dosya | Amaç |
|-------|------|
| `kill_switch.py` | Connectivity watchdog daemon |
| `emergency_restore.sh` | Manuel kurtarma scripti |
| `helpers.py` | Test yardımcı fonksiyonları |
| `conftest.py` | pytest configuration & fixtures |
| `fixtures/pre_test.py` | Test öncesi kontroller |
| `fixtures/post_test.py` | Test sonrası kurtarma |
| `test_integration_safe.py` | Phase 0-3 güvenli testler |
| `test_integration_dns.py` | Phase 4 DNS testleri |
| `test_integration_byedpi.py` | Phase 5 ByeDPI testleri |
| `test_integration_wireguard.py` | Phase 6 WireGuard testleri |
| `test_integration_zapret.py` | Phase 7 Zapret testleri |

## Pytest Markers

```bash
# Belirli bir phase çalıştır
pytest -m phase0 -v
pytest -m phase7 -v

# Root gerektiren testleri atla
pytest -m "not requires_root" -v

# Yavaş testleri atla
pytest -m "not slow" -v

# Integration testleri
pytest -m integration -v
```

## Hata Ayıklama

### Bağlantı Problemi

```bash
# DNS kontrol
resolvectl status
cat /etc/resolv.conf

# iptables kontrol
sudo iptables -t mangle -L -n -v
sudo iptables -t nat -L -n -v

# Process kontrol
ps aux | grep -E "nfqws|tpws|ciadpi"

# WireGuard kontrol
ip link show
wg show
```

### Log Dosyaları

```bash
# Kill switch logu
tail -f /tmp/kill_switch.log

# Test output
pytest -v --tb=long 2>&1 | tee test_output.log
```

## Güvenlik Notları

1. **Kill switch HER ZAMAN çalışmalı** (Phase 4-7 için)
2. **Zapret testleri EN SON** - diğer servisler doğrulandıktan sonra
3. **Her değişiklikten HEMEN sonra connectivity test et**
4. **finally bloklarında force cleanup** - servis metodlarına güvenme
5. **emergency_restore.sh her zaman erişilebilir olmalı**
