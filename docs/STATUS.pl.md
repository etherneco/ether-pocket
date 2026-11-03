# Stan możliwości EtherPocket

Opracowanie: **3 listopada 2026 r.** Tabela odzwierciedla ostatnie znalezione raporty, a nie nową sesję testów sprzętu. Daty odnoszą się do dowodów. Starsze fragmenty `README.rst` stanowią historię i mogą opisywać rozwiązane blokady.

| Funkcja | Potwierdzony zakres | Pozostałe ograniczenia | Źródło |
| --- | --- | --- | --- |
| Linux i dual boot | Natywny boot ARM64, dotyk, wybór Android/Linux | Port konkretnego GM1920, brak uniwersalnego obrazu | [15.10](dualboot-2026-10-15.rst) |
| EtherShell i wygląd | Dotykowe ustawienia, układy w kilku rozmiarach, jasny/ciemny motyw | Dalsza adaptacja aplikacji | [29.10](ui-polish-2026-10-29.rst) |
| Klawiatura ekranowa | Automatyczne otwieranie, testowana polityka fokus/klawiatura | Test fizycznego podłączenia pozostaje oddzielny | [29.10](etherkeyboard-2026-10-29.rst) |
| LTE | Start/stop przez backend UI i HTTPS 200 przez epcell0 | giffgaff.com/IPv4, blokada roamingu, bez kolejnego rebootu w tym teście | [03.11](mobile-data-progress-2026-11-03.rst) |
| Rozmowy | Realna rozmowa osiągnęła Active | Dwukierunkowy dźwięk, VoLTE i połączenia alarmowe niepotwierdzone | [21.10](etherphone-real-call-2026-10-21.rst) |
| Pliki i serwery | Operacje lokalne i kontrolowane testy SFTP/SMB/WebDAV | Dalsza akceptacja dotyku i serwerów docelowych | [17.10](etherfiles-network-2026-10-17.rst) |
| USB Storage | Dwukierunkowa wymiana z Windows, obsługa konfliktów | Konieczne poprawne wysunięcie dysku | [16.10](usb-storage-2026-10-16.rst) |
| Aparat | Tylny IMX586, RAW, JPEG i nagranie H.264 | Brak potwierdzenia AF/OIS/HDR/lampy i pozostałych aparatów | [20.10](ethercamera-spectra-driver-2026-10-20.rst) |
| Mapy offline | Renderowanie na ARM64, MBTiles, ślady i GPX | Dostawcy usług online i publikacja wymagają konfiguracji | [21.10](ethermap-device-delivery-2026-10-21.rst) |
| Lokalizacja GNSS | Sesje i wykrycie satelitów | Brak zweryfikowanego fixa pozycji | [20.10](etherlocation-delivery-2026-10-20.rst) |
| Bluetooth | Włączenie/wyłączenie i wykrywanie pobliskich urządzeń | Parowanie, audio/HID i cold boot wymagają akceptacji | [17.10](bluetooth-driver-2026-10-17.rst) |
| Energia | Jasność, profile, wygaszanie i wybudzenie ekranu | Suspend zablokowany, brak testu pełnej wytrzymałości baterii | [19.10](etherpower-delivery-2026-10-19.rst) |
| Czujniki | Usługa, uprawnienia i diagnostyka | Brak potwierdzonego ruchu, światła, bliskości i automatycznej rotacji | [21.10](ethersensors-delivery-2026-10-21.rst) |
| Kopie | Szyfrowanie Restic i testy wybranych odtworzeń | Nośnik/hasło wymagają konfiguracji, brak pełnego recovery systemu | [21.10](etherbackup-delivery-2026-10-21.rst) |
| Aktualizacje | Koordynator i niezależne zaufanie Ed25519 | Brak wydania produkcyjnego, kluczy i mapowań | [Opis](etherupdate.rst) |
| Windows Control | Podgląd, wejście, Unicode, PNG i reconnect | Brak audio, schowka i nagrywania wideo | [29.10](etherpocket-control-2026-10-29.rst) |
| Okulary / zewnętrzny ekran | Kod konfiguracji i poprawki | Brak potwierdzonego obrazu na okularach | [Historia](../README.rst) |
| GPU | Pulpit uruchomiony z llvmpipe | Akceleracja sprzętowa niezweryfikowana | [Historia](../README.rst) |

## Jak aktualizować tabelę

Nowy wpis powinien wskazywać datowany raport, konfigurację urządzenia, wynik testu i granice wniosku. Test symulowany, fixture QML i obecność interfejsu systemowego nie zastępują próby funkcji na fizycznym urządzeniu. Nie sumujemy historycznych testów jako jednego aktualnego wyniku.
