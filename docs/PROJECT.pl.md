# EtherPocket — szczegółowy opis projektu

## Cel i odbiorcy

EtherPocket to projekt natywnego środowiska Linux dla telefonu ARM64. Łączy port systemu na konkretny sprzęt, pulpit dostosowany do dotyku i zestaw współpracujących aplikacji. Telefon może pełnić funkcję mobilnego terminala, przeglądarki plików, aparatu lub urządzenia do pracy z aplikacjami Linuksa. Rozszerzenie pracy na zewnętrzne ekrany i okulary stanowi kierunek rozwoju wymagający dalszych testów.

Projekt jest obecnie przeznaczony przede wszystkim dla programistów, osób zajmujących się portowaniem Linuksa i zaawansowanych testerów. Obsługa jednego urządzenia referencyjnego nie oznacza obsługi innych modeli OnePlus. Weryfikowany wariant to GM1920, OnePlus 7 Pro 5G.

## Środowisko uruchomieniowe

Własny kernel ARM64 uruchamia natywny userspace Mobian/Debian. systemd zarządza usługami. Sesja graficzna korzysta z Xorg, a EtherShell z Qt 6/QML i integracji z menedżerem okien. Aplikacje XDG można uruchamiać z launchera. XFCE pozostaje środowiskiem odzyskiwania. Konfiguracja dual boot pozwala wybrać Linux lub Android, z osobnym kernelem każdego systemu.

Kod uwzględnia sprzęt Qualcomm i specyfikę istniejącego kernela producenta. Sama obecność DRM/KMS, węzła renderującego albo wyjścia DisplayPort nie potwierdza poprawnego działania grafiki czy okularów. Udokumentowany pulpit korzystał z llvmpipe, a akceleracja GPU pozostaje niezweryfikowana.

## Interfejs i aplikacje

**EtherShell** udostępnia ekran główny, launcher, obsługę okien, ustawienia i szybkie przełączniki. Interfejs ma warianty jasny i ciemny, a układy są sprawdzane przy kilku szerokościach. **EtherKeyboard** otwiera się przy edycji, gdy system nie wykrywa klawiatury do pisania. Natywne pola Qt współpracują z mechanizmem metod wprowadzania, a dostępne aplikacje zewnętrzne z AT-SPI. Fizyczne podłączanie klawiatur pozostaje oddzielnym testem sprzętowym.

**EtherFiles** zarządza plikami, koszem, podglądem i wyszukiwaniem. Ma układy kieszonkowe i desktopowe, karty oraz podział okna. Obsługuje SFTP, SMB i WebDAV. Testy serwerów kontrolowanych obejmowały błędne hasła, zmienione klucze SSH i odrzucanie niezaufanego TLS. Dysk USB ETHERPOCKET umożliwia wymianę plików z Windows. Synchronizacja powrotna następuje po wysunięciu dysku i zachowuje kopie konfliktów.

**EtherCamera** obejmuje aplikację, prywatną bibliotekę mediów i natywny tor kamery Spectra. Dla tylnego Sony IMX586 zweryfikowano klatkę RAW 4000 × 3000, podgląd, zdjęcie JPEG oraz finalizację nagrania H.264. Tor korzysta z buforów DMA i programowego przetwarzania obrazu. Autofocus, OIS, HDR, lampa, przedni aparat i jakość fabrycznego ISP nie są potwierdzonym zakresem.

**EtherMAP** wyświetla mapy rastrowe online i lokalne MBTiles, obsługuje zapisane miejsca, ślady i GPX. Dostawcy geokodowania i tras wymagają konfiguracji oraz odpowiednich warunków użycia. Mapa offline działa niezależnie od uzyskania pozycji. **EtherLocation** zarządza uprawnieniami, dokładnością, opcjonalną historią i geofencingiem. Raporty potwierdzają sesje GNSS i obserwację satelitów, ale nie poprawny fix pozycji.

## Sieć i komunikacja

**EtherMobile** integruje ustawienia modemu i połączeń. Dla sprzętowego toru IPA/QMI kontroluje dedykowaną usługę `ethermobile-data.service`. Pozostałe modemy zachowują ścieżkę NetworkManager. Interfejs pokazuje etapy od karty SIM i rejestracji do sesji APN, adresacji i DNS. Sprawdza PID usługi oraz rzeczywisty interfejs przed zadeklarowaniem sesji. Zapisany test z 3 listopada 2026 potwierdza HTTPS przez `epcell0`. Obecny adapter IPA jest ograniczony do udokumentowanego APN giffgaff.com/IPv4 i blokuje roaming. Nie oznacza to uniwersalnej obsługi operatorów.

**EtherShare** zawiera mechanizmy współdzielenia łącza, ale pełna akceptacja hotspotu pozostaje otwarta. Historyczne niepowodzenia LTE trzeba odróżniać od późniejszego testu działającej transmisji. **EtherBluetooth** integruje BlueZ i diagnostykę sterownika. Wykrywanie pobliskich urządzeń potwierdzono, a audio, HID i wszystkie scenariusze parowania wymagają dalszej akceptacji.

**EtherPhone** zapewnia wybieranie numeru, nakładkę rozmowy, historię i wspólne kontakty. Raport z 21 października potwierdza odpowiedź drugiej strony i stan Active, ale opisuje brak lub jednostronność dźwięku. Kalibracja toru głosowego DSP pozostaje istotną zależnością. VoLTE, rozmowy alarmowe i pełna obsługa audio rozmów nie mają potwierdzenia.

**EtherSMS** udostępnia aplikację wiadomości i współdzielone kontakty. **EtherNotifications** obsługuje standardowe powiadomienia Linuksa, historię SQLite, grupowanie, akcje i tryb nie przeszkadzać. Gotowość odbioru lub wysyłania komunikacji zależy także od modemu i usług operatora.

## Usługi systemowe

Moduły są rozdzielone na interfejsy i usługi. D-Bus zapewnia komunikację między aplikacjami, a operacje uprzywilejowane podlegają ograniczeniom PolicyKit lub osobnym helperom. Każdy komponent ma własne zależności i pakietowanie.

| Usługa | Odpowiedzialność | Istotne ograniczenie |
| --- | --- | --- |
| EtherAudio | Routing PipeWire/WirePlumber, skupienie audio, poziomy i zgody na nagrywanie | Działający tor multimediów nie potwierdza dźwięku rozmów modemu |
| EtherPower | Jasność, profile CPU/GPU, historia, diagnostyka termiczna i wygaszanie | Suspend pozostaje zablokowany do potwierdzenia wybudzania |
| EtherHardware | Wykrywanie możliwości i czytelne raporty diagnostyczne | Wykrycie urządzenia nie oznacza testu jego funkcji |
| EtherSensors | Rejestr sensorów, subskrypcje i kontrola dostępu | Brak potwierdzonych zmiennych próbek ruchu/światła/zbliżenia |
| EtherLock | Blokada XSecureLock, PAM i polityka dostępu | Raport opisuje wdrożenie etapowe i otwarte testy fizyczne |
| EtherCredentials | Oddzielna obsługa poświadczeń i integracja z blokadą | Zakres i model zagrożeń opisuje dokumentacja modułu |
| EtherBackup | Szyfrowanie Restic, kopie przyrostowe, eksport SQLite i próby odzyskania | Należy niezależnie skonfigurować nośnik i hasło odzyskiwania |
| EtherUpdate | Koordynator, podpisy Ed25519, historia i odzyskiwanie aplikacji | Produkcyjna publikacja wymaga kluczy i mapowań komponentów |

Raporty bezpieczeństwa wskazują również istniejące autologowanie, sudo bez hasła i nieszyfrowany ext4. Nie należy przedstawiać tego portu jako ukończonego, zabezpieczonego telefonu konsumenckiego.

## EtherPocket Control

Narzędzie dla Windows pokazuje rzeczywisty pulpit X11 telefonu i przekazuje kliknięcia, przeciąganie, przewijanie oraz tekst Unicode. Pozwala zmieniać częstotliwość przechwytywania w zakresie 1–15 FPS, przełączyć podgląd bez sterowania i zapisać PNG. Domyślne ustawienia to 8 FPS i szerokość 720 pikseli.

Transport korzysta z SSH i sprawdzania znanego klucza hosta. Agent pracuje na telefonie tylko podczas połączenia. Narzędzie wykorzystuje istniejący dostęp administratora do przygotowania agenta. Nie zapewnia nagrywania wideo, przekazywania audio ani synchronizacji schowka. Inny komputer wymaga własnego autoryzowanego klucza i poprawnego known_hosts.

## Przykładowy pokaz

1. Otwórz EtherShell i pokaż launcher, ustawienia oraz edycję z klawiaturą ekranową.
2. W EtherFiles utwórz testowy katalog i pokaż wariant układu dla szerszego okna.
3. W EtherMAP otwórz przygotowaną mapę offline. Wyjaśnij oddzielny stan GNSS.
4. W EtherCamera pokaż tylny aparat na zweryfikowanym urządzeniu, po uzyskaniu zgody.
5. W ustawieniach sieci pokaż faktyczny postęp i wynik połączenia LTE.
6. Z Windows połącz EtherPocket Control i pokaż sterowanie pulpitem.

Scenariusz wymaga przygotowanego urządzenia. Opis nie uruchamia żadnych operacji, połączeń ani nagrań automatycznie.

## Kierunek rozwoju

Najbliższe bramki techniczne to pełny tor audio rozmów, akceptacja GNSS na zewnątrz, czujniki, bezpieczne usypianie oraz zewnętrzny ekran. Równolegle potrzebne są uruchomienie docelowych kopii zapasowych, zarządzanie kluczami wydawcy i powtarzalne wydania pakietów. Kolejne etapy wymagają udokumentowanych testów na sprzęcie. Nie przypisano im obiecanych terminów.

## Podstawa opisu

Opis przygotowano 3 listopada 2026 r. na podstawie kodu i lokalnych raportów. Najważniejsze źródła to [LTE](mobile-data-progress-2026-11-03.rst), [rozmowa głosowa](etherphone-real-call-2026-10-21.rst), [aparat](ethercamera-spectra-driver-2026-10-20.rst), [mapy](ethermap-device-delivery-2026-10-21.rst), [interfejs](ui-polish-2026-10-29.rst), [klawiatura](etherkeyboard-2026-10-29.rst) i [sterowanie Windows](etherpocket-control-2026-10-29.rst). Przygotowanie dokumentacji nie jest ponownym testem urządzenia.
