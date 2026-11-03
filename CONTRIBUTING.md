# Praca nad EtherPocket

## Przygotowanie

Sklonuj repozytorium i utwórz gałąź, np. `git switch -c docs/opis-modulu`. Przeczytaj README modułu, jego `CMakeLists.txt` oraz odpowiedni skrypt budowania. Biblioteki Qt, zależności systemowe i toolchain ARM64 zależą od komponentu. Zwykłe testy hosta nie wymagają dostępu administratora do telefonu.

## Testy bez urządzenia

Na Windows i Linux:

```sh
python -m unittest discover -s tests -p test_x11.py
python -m unittest discover -s etherpocket-control -p test_transport.py
```

Na Linux, dodatkowo:

```sh
python3 -m unittest discover -s tests -p test_mobile_data_status.py
PYTHONPATH=scripts python3 -m unittest discover -s tests -p test_ethermobile_data_cleanup.py
```

Druga grupa korzysta z założeń POSIX, w tym `O_NOFOLLOW`. Nie należy osłabiać zabezpieczeń kodu produkcyjnego, aby uruchamiać ją na Windows. CI uruchamia wskazane testy na Linux oraz testy przenośne na Windows. Nie buduje całego obrazu, nie uruchamia telefonu i nie potwierdza funkcji sprzętu.

## Zmiany i przegląd

- Opisz konkretny problem i zachowanie po zmianie.
- Podaj wykonane testy, środowisko i ograniczenia wyniku.
- Przy zmianach sprzętowych dodaj datowany raport w `docs/`, model urządzenia oraz procedurę odzyskania.
- Aktualizuj `docs/STATUS.pl.md`, gdy nowe dowody zmieniają gotowość funkcji.
- Zachowuj UTF-8. Kod Python, powłoki i pliki Linux mają LF. Skrypty Windows mają CRLF.

## Urządzenie i dane lokalne

Nie uruchamiaj skryptów flashowania, partycjonowania, aktywacji ani testów połączeń na podstawie samej nazwy. Najpierw sprawdź ich kod, identyfikację sprzętu i założenia. Skrypty często wskazują istniejące lokalne ścieżki do kluczy i adres USB autora. Nowe stanowisko wymaga własnego dostępu SSH i weryfikacji hosta.

Nie dodawaj kluczy, tokenów, haseł Wi-Fi, profili NetworkManager, kopii partycji, baz kontaktów ani prywatnych mediów. Surowe wyniki przechowuj lokalnie w `evidence/`. Materiał do publikacji przejrzyj i zanonimizuj przed przeniesieniem do `docs/`. `.gitignore` ogranicza przypadkowe dodanie, ale nie zastępuje kontroli `git diff --cached`.

## Licencja

Nie dodawaj jednej licencji do całego projektu bez ustalenia praw do komponentów i kodu zewnętrznego. Zachowuj istniejące informacje o autorach i warunki wykorzystania.
