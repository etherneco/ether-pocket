# EtherPocket — prezentacja możliwości

[Otwórz prezentację PowerPoint](EtherPocket.pptx). Sześć slajdów, około 3–5 minut. Stan opisu: 3 listopada 2026 r. Tekst na slajdach jest edytowalny, a źródła i istotne zastrzeżenia znajdują się w notatkach prelegenta.

## 1. EtherPocket: Linux w kieszeni

EtherPocket to natywny Linux ARM64 na telefonie z dotykowym pulpitem i aplikacjami Linuksa. Referencyjny sprzęt to OnePlus 7 Pro 5G GM1920. Projekt pozostaje portem inżynierskim.

## 2. Dotykowy pulpit Linuksa

EtherShell łączy launcher aplikacji, obsługę okien, ustawienia i szybkie przełączniki. Klawiatura ekranowa reaguje na edycję, a układy na szerokość ekranu. Pod spodem działają Mobian/Debian, systemd, Xorg i Qt 6. Android ma oddzielny system w konfiguracji dual boot.

## 3. Pliki i podstawowe multimedia

EtherFiles zarządza plikami, koszem i podglądem oraz obsługuje SFTP, SMB i WebDAV. Dysk wymiany USB umożliwia przesyłanie danych do Windows. EtherCamera wykorzystuje tylny IMX586 do podglądu, JPEG i H.264. Autofocus i pełna jakość fabrycznego aparatu pozostają poza potwierdzonym zakresem.

## 4. Mapy działające offline

EtherMAP korzysta z MBTiles, zapisanych miejsc, śladów i GPX. Dostawcy tras i wyszukiwania wymagają konfiguracji. Wyświetlenie mapy nie wymaga fixa GNSS. Sesje GNSS wykrywały satelity, lecz poprawna pozycja nie została potwierdzona.

## 5. Internet i współpraca z Windows

EtherMobile pokazuje postęp sesji LTE i rzeczywisty stan interfejsu. Raport z 3 listopada potwierdza HTTPS 200 przez epcell0. Test dotyczył obecnej konfiguracji giffgaff.com/IPv4 po restarcie usługi, bez kolejnego rebootu. EtherPocket Control zapewnia podgląd i sterowanie X11 z Windows przez SSH, wejście Unicode i zapis PNG. Nie przekazuje dźwięku.

## 6. Stan projektu i dalszy rozwój

Istnieją działające elementy pulpitu, plików, map offline, podstawowego aparatu i danych LTE. Do kolejnych bramek należą audio rozmów, fix GNSS, czujniki, suspend, GPU i okulary. Kopie i wydania wymagają konfiguracji. Projekt nie obiecuje dat ukończenia.

## Pochodzenie obrazów i źródła

Obrazy w `images/` są przejrzanymi kopiami zrzutów z izolowanych sesji testowych na telefonie z 29 października 2026. Nie przedstawiają nowej sesji demonstracyjnej. Oryginały pozostają w lokalnym archiwum `evidence/ui-polish/`. Ekran map zachowuje oznaczenie © OpenStreetMap contributors, ODbL 1.0. [Warunki danych mapowych](https://www.openstreetmap.org/copyright).

Podstawy techniczne opisują [projekt](../PROJECT.pl.md), [stan możliwości](../STATUS.pl.md), [interfejs](../ui-polish-2026-10-29.rst), [aparat](../ethercamera-spectra-driver-2026-10-20.rst), [mapy](../ethermap-device-delivery-2026-10-21.rst), [LTE](../mobile-data-progress-2026-11-03.rst) i [sterowanie Windows](../etherpocket-control-2026-10-29.rst). Dokładniejsze odnośniki umieszczono także w notatkach slajdów.
