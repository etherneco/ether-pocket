# EtherPocket

**Natywny Linux ARM64 na telefonie, z dotykowym pulpitem i własnym zestawem aplikacji.**

EtherPocket rozwija telefon w kierunku kieszonkowego komputera z systemem Mobian/Debian. System uruchamia własny kernel Linuksa, sesję Xorg oraz EtherShell, interfejs napisany w Qt 6/QML. Aplikacje i usługi działają bezpośrednio w Linuksie. Projekt obejmuje również narzędzia integracji sprzętu, diagnostykę oraz sterowanie pulpitem z Windows przez SSH.

Obecnym urządzeniem referencyjnym jest **OnePlus 7 Pro 5G GM1920**. Repozytorium zawiera kod i dokumentację portu inżynierskiego. Gotowość funkcji zależy od konkretnego urządzenia, sterowników i konfiguracji.

## Zobacz projekt

- [Dokładny opis, architektura i scenariusze użycia](docs/PROJECT.pl.md)
- [Możliwości i ograniczenia według ostatnich raportów](docs/STATUS.pl.md)
- [Krótka prezentacja PowerPoint](docs/presentation/EtherPocket.pptx)
- [Treść prezentacji i scenariusz pokazu](docs/presentation/README.md)
- [Zasady pracy z repozytorium](CONTRIBUTING.md)
- [Historia wdrożeń i wcześniejsze raporty](README.rst)

## Co oferuje EtherPocket

| Obszar | Elementy projektu | Zakres |
| --- | --- | --- |
| Pulpit dotykowy | EtherShell, EtherKeyboard | Launcher aplikacji XDG, ustawienia, szybkie przełączniki, obsługa okien i klawiatura ekranowa |
| Pliki i wymiana danych | EtherFiles, USB Storage | Operacje na plikach, kosz, podgląd, SFTP/SMB/WebDAV i dysk wymiany USB |
| Internet | EtherMobile, EtherShare | Obsługa modemu i postępu połączenia, diagnostyka LTE, kontrolowane współdzielenie łącza |
| Multimedia | EtherCamera, EtherAudio | Podstawowe zdjęcia i wideo z tylnego IMX586, polityka audio i kontrola mikrofonu |
| Mapy | EtherMAP, EtherLocation | Mapy offline, zapisane miejsca, ślady i GPX, uprawnienia lokalizacji |
| Komunikacja | EtherPhone, EtherSMS, EtherNotifications | Interfejs rozmów i wiadomości, kontakty, historia i centrum powiadomień |
| Utrzymanie | EtherHardware, EtherPower, EtherSensors | Diagnostyka sprzętu, zarządzanie energią i rejestr możliwości czujników |
| Ochrona i aktualizacje | EtherLock, EtherCredentials, EtherBackup, EtherUpdate | Blokowanie sesji, poświadczenia, szyfrowane kopie i weryfikacja aktualizacji |
| Komputer z Windows | EtherPocket Control | Podgląd i sterowanie rzeczywistym pulpitem X11 przez SSH |

**Stan opisany 3 listopada 2026 r., na podstawie zapisanej dokumentacji:** raport z tego dnia potwierdza HTTPS przez interfejs LTE `epcell0`. Połączenie głosowe osiągnęło stan Active, lecz dwukierunkowy dźwięk pozostaje niepotwierdzony. GNSS bez zweryfikowanego fixa, okulary AR, akceleracja GPU i suspend nadal wymagają akceptacji. Obecność interfejsu w aplikacji nie oznacza ukończonej obsługi sprzętu. Szczegóły i daty podaje [tabela stanu](docs/STATUS.pl.md).

## Architektura w skrócie

System opiera się na Mobian/Debian ARM64, systemd i Xorg. EtherShell oraz aplikacje Qt/QML korzystają z osobnych usług i adapterów przez D-Bus. Integracje wykorzystują między innymi NetworkManager, ModemManager/QMI, BlueZ, PipeWire/WirePlumber, PAM i PolicyKit. Skrypty przygotowują pakiety Debian, kontrolują wdrożenia i zapisują wyniki testów. XFCE pełni rolę pulpitu odzyskiwania. Android zachowuje oddzielny system i kernel w konfiguracji dual boot.

## Rozpoczęcie pracy

```sh
git clone https://github.com/etherneco/ether-pocket.git
cd ether-pocket
python -m unittest discover -s tests -p test_x11.py
python -m unittest discover -s etherpocket-control -p test_transport.py
```

Te testy korzystają ze standardowej biblioteki Pythona i nie łączą się z telefonem. Testy stanu modemu wymagają Linux/POSIX:

```sh
python3 -m unittest discover -s tests -p test_mobile_data_status.py
PYTHONPATH=scripts python3 -m unittest discover -s tests -p test_ethermobile_data_cleanup.py
```

Pakiety urządzenia buduje się w środowisku Linux z Qt 6, CMake/Ninja i zależnościami danego modułu. Przykład budowania EtherFiles z konfiguracją cross-compilation znajduje się w `scripts/build-etherfiles-cross.sh`, a wymagania środowiska w [dokumentacji EtherFiles](etherfiles/README.rst). Nie ma jednego instalatora całego systemu. Skrypty wdrożeniowe mogą zawierać założenia dotyczące konkretnego urządzenia i lokalnego środowiska autora.

## Struktura repozytorium

- `ether*/` — aplikacje, usługi, definicje D-Bus, pakietowanie i testy modułów.
- `scripts/` — budowanie, diagnostyka, wdrożenia i weryfikacja.
- `kernel/`, `xorg/`, `config/` — poprawki i konfiguracja warstwy systemowej.
- `tests/` — testy narzędzi i integracji bez fizycznego urządzenia.
- `docs/` — opis projektu oraz datowane raporty techniczne.
- `assets/` — grafika projektu.

Lokalne katalogi `build/`, `sources/`, `tools/`, `recovery/` i surowe materiały `evidence/` nie są częścią publikowanego kodu. Historyczne raporty mogą wskazywać pliki dostępne wyłącznie w lokalnym archiwum. Firmware producenta, klucze i kopie partycji nie są dołączane.

## Rozwój i prawa do kodu

Zgłoszenia błędów i propozycje zmian można dodawać w [Issues](https://github.com/etherneco/ether-pocket/issues). Zasady opisywania zmian zawiera [CONTRIBUTING.md](CONTRIBUTING.md), a zgłaszania problemów bezpieczeństwa [SECURITY.md](SECURITY.md).

Nie ustalono jeszcze wspólnej licencji dla całego repozytorium. Nie należy zakładać, że cały kod można redystrybuować na jednej licencji. Przed dystrybucją trzeba sprawdzić prawa do poszczególnych komponentów i poprawek, w tym kodu pochodzącego z innych projektów. Ta konfiguracja repozytorium nie zmienia istniejących nagłówków licencyjnych.
