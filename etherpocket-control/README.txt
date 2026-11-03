EtherPocket Control dla Windows
==============================

Uruchom EtherPocketControl.exe albo skrót „EtherPocket Control” w menu Start lub na pulpicie.
Podłącz telefon przez USB, uruchom etherPocket i wybierz „Połącz”.
Program wymaga działającego OpenSSH w Windows i skonfigurowanego klucza telefonu.
Python nie jest wymagany dla zbudowanego pliku EXE. Zachowaj cały katalog
aplikacji razem z podkatalogiem _internal.

Funkcje:
- podgląd prawdziwego pulpitu telefonu, domyślnie 8 klatek/s;
- kliknięcia, przeciąganie, przewijanie i klawiatura;
- tryb tylko do podglądu: odznacz „Sterowanie”;
- zapisywanie obrazu do pliku PNG na komputerze;
- skalowanie obrazu do okna i wybór 1–15 klatek/s w ustawieniach.

Kliknij obraz, aby skierować klawiaturę do telefonu. Po wyjściu z obrazu lub
rozłączeniu przytrzymane przyciski i klawisze są zwalniane. Program pokazuje
pulpit sesji mobian, nie ekran Androida. Zrzut ma rozdzielczość strumienia
(720 pikseli szerokości). Brak nagrywania wideo, dźwięku i synchronizacji schowka.

Połączenie działa przez SSH z weryfikacją znanego klucza hosta. Nie otwiera
nowego portu serwera. Klucz prywatny nie jest wbudowany w EXE ani kopiowany do
folderu aplikacji; connection.json wskazuje istniejący klucz z tego komputera.
Ustawienia użytkownika są zapisane w %LOCALAPPDATA%\EtherPocketControl.
Na innym komputerze wybierz własny autoryzowany klucz i plik known_hosts.
Połączenie przez sieć jest możliwe po wpisaniu adresu telefonu i dodaniu jego
zweryfikowanego klucza do wskazanego pliku known_hosts.

Program przygotowuje małego agenta w /usr/local/lib/etherpocket-control/agent.py.
Agent działa jako użytkownik mobian tylko podczas połączenia, przechwytuje X11
przez FFmpeg i przyjmuje zdarzenia XTest przez ten sam tunel SSH. Niczego nie
instaluje w autostarcie telefonu. Zablokowany telefon nadal wymaga odblokowania.

Budowanie ze źródeł:
  python -m pip install pillow pyinstaller
  powershell -NoProfile -File etherpocket-control\build.ps1

Źródła: app.py, transport.py, agent.py. Testy: test_transport.py.
