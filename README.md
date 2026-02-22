# SAN Zone Designer v1.2

Cisco/Brocade SAN Config Generator — Python CLI + Web GUI.

Generuje konfiguracje VSAN, device-alias/alias, zoning oraz zoneset/CFG dla przelacznikow Cisco MDS NX-OS i Brocade FOS. Wiernie odwzorowuje logike oryginalnego skryptu `zonedesigner.sh`, rozszerzajac go o interfejs webowy, walidacje, import zon, migracje formatow i porownanie konfiguracji.

---

## Spis tresci

- [Instalacja](#instalacja)
- [Szybki start](#szybki-start)
- [Architektura projektu](#architektura-projektu)
- [CLI — Interfejs wiersza polecen](#cli--interfejs-wiersza-polecen)
  - [init](#init--tryb-batch)
  - [expand](#expand--tryb-interaktywny)
  - [migrate](#migrate--migracja-txt--yaml)
  - [diff](#diff--porownanie-zon)
  - [web](#web--serwer-webowy)
- [Web GUI — Interfejs graficzny](#web-gui--interfejs-graficzny)
  - [Logowanie i sesje](#logowanie-i-sesje)
  - [Zakladka Generate](#zakladka-generate)
  - [Zakladka Expand](#zakladka-expand)
  - [Zakladka Migrate](#zakladka-migrate)
  - [Zakladka Diff](#zakladka-diff)
  - [Sidebar — przegladarka plikow](#sidebar--przegladarka-plikow)
  - [Manage Files — zarzadzanie plikami](#manage-files--zarzadzanie-plikami)
  - [Zakladka Editor — edycja plikow](#zakladka-editor--edycja-plikow)
  - [Zmiana hasla](#zmiana-hasla)
  - [Manage Users — zarzadzanie uzytkownikami](#manage-users--zarzadzanie-uzytkownikami)
  - [Zakladka Configuration](#zakladka-configuration)
  - [Zakladka Logs](#zakladka-logs)
- [Zabezpieczenia](#zabezpieczenia)
  - [Uwierzytelnianie i sesje](#uwierzytelnianie-i-sesje)
  - [Role i kontrola dostepu](#role-i-kontrola-dostepu)
  - [Ochrona sciezek plikow](#ochrona-sciezek-plikow)
  - [Limity uploadu](#limity-uploadu)
  - [Soft-delete — archiwizacja zamiast usuwania](#soft-delete--archiwizacja-zamiast-usuwania)
- [Walidacja danych wejsciowych](#walidacja-danych-wejsciowych)
- [API REST — endpointy](#api-rest--endpointy)
  - [Auth API](#auth-api)
  - [Files API](#files-api)
  - [Generate API](#generate-api)
  - [Migrate API](#migrate-api)
  - [Diff API](#diff-api)
  - [Config API](#config-api)
  - [Logs API](#logs-api)
- [Formaty plikow wejsciowych](#formaty-plikow-wejsciowych)
- [Generatory konfiguracji](#generatory-konfiguracji)
- [System parsowania plikow](#system-parsowania-plikow)
- [Import zon z przelacznika](#import-zon-z-przelacznika)
- [Struktura katalogow bazy danych](#struktura-katalogow-bazy-danych)
- [System logowania](#system-logowania)
  - [Log aplikacyjny](#log-aplikacyjny)
  - [Audit log — rejestr zdarzen](#audit-log--rejestr-zdarzen)
  - [Zakladka Logs w GUI](#zakladka-logs-w-gui)
  - [Logs API](#logs-api)
- [Testy](#testy)
- [Changelog](#changelog)

---

## Instalacja

```bash
# Instalacja podstawowa (tylko CLI)
pip install -e .

# Instalacja z interfejsem webowym
pip install -e ".[web]"

# Instalacja z narzedziami deweloperskimi (pytest, ruff, mypy)
pip install -e ".[dev]"

# Pelna instalacja (web + dev)
pip install -e ".[web,dev]"
```

**Wymagania:** Python >= 3.10

**Zaleznosci podstawowe:**

| Pakiet | Wersja | Funkcja |
|--------|--------|---------|
| `typer` | >= 0.9 | Framework CLI |
| `rich` | >= 13 | Kolorowy output w terminalu |
| `InquirerPy` | >= 0.3 | Interaktywne prompty multi-select |
| `pyyaml` | >= 6 | Parsowanie plikow YAML |
| `cryptography` | >= 41.0 | Weryfikacja licencji Ed25519 |

**Zaleznosci web (`[web]`):**

| Pakiet | Wersja | Funkcja |
|--------|--------|---------|
| `fastapi` | >= 0.104 | Framework web API |
| `uvicorn[standard]` | >= 0.24 | Serwer ASGI |
| `python-multipart` | >= 0.0.6 | Obsluga uploadu plikow |
| `bcrypt` | >= 4.0 | Hashowanie hasel |
| `pydantic` | >= 2.0 | Modele danych request/response |

---

## Szybki start

```bash
# Pomoc
san-zone-designer --help

# Generacja Cisco (batch, all x all)
san-zone-designer init -i initiators.txt -t targets.txt --vsan 100

# Generacja Brocade
san-zone-designer init -i initiators.txt -t targets.txt --vendor brocade

# Tryb interaktywny — wybor par z listy
san-zone-designer expand -i initiators.txt -t targets.txt --vsan 100

# Migracja txt na yaml
san-zone-designer migrate -i initiators.txt -o initiators.yaml

# Porownanie z istniejaca konfiguracja switcha
san-zone-designer diff -i initiators.txt -t targets.txt -e show_zoneset.txt --vsan 100

# Uruchomienie interfejsu webowego
san-zone-designer web --port 8000
```

---

## Architektura projektu

```
san_zone_designer/
  __init__.py              # __version__ = "1.1.0"
  __main__.py              # python -m san_zone_designer
  cli.py                   # Typer CLI — komendy init, expand, migrate, diff, web
  models.py                # Dataclasses: HBA, Target, Zone, Configuration, enumy
  parser.py                # Parsery TXT i YAML dla initiators/targets
  validator.py             # Walidacja WWPN, aliasow, detekcja duplikatow
  selector.py              # Generowanie par zona (batch + interaktywny)
  colorizer.py             # Kolorowanie outputu w terminalu (Rich markup)
  differ.py                # Silnik porownania zon (diff)
  importer.py              # Import zon z outputu przelacznika (show zoneset, cfgshow)
  migrator.py              # Konwersja TXT na YAML z auto-detekcja metadanych
  generators/
    __init__.py            # Eksportuje CiscoGenerator, BrocadeGenerator
    base.py                # AbstractGenerator — bazowa klasa generatora
    cisco.py               # CiscoGenerator — Cisco MDS NX-OS
    brocade.py             # BrocadeGenerator — Brocade FOS
  exporters/
    config_writer.py       # Zapis .cfg
    csv_writer.py          # Zapis .csv
  web/
    app.py                 # FastAPI application factory + AuthMiddleware
    auth.py                # Uwierzytelnianie: bcrypt, sesje, role, kontrola dostepu
    audit.py               # Strukturalny audit log (JSON-lines)
    dependencies.py        # Helpery: resolve_db_path, build_web_config, autosave, soft_delete
    schemas.py             # Pydantic modele request/response
    logging_config.py      # Konfiguracja logowania (RotatingFileHandler)
    routers/
      auth.py              # /api/auth/* — login, logout, CRUD uzytkownikow
      files.py             # /api/files/* — projekty, upload, preview, delete
      generate.py          # /api/generate/* — preview, init, expand
      migrate.py           # /api/migrate/* — preview, migrate
      diff.py              # /api/diff/* — porownanie zon
      config.py            # /api/config/* — licencja
      logs.py              # /api/logs/* — przegladanie logow (admin)
    static/
      index.html           # SPA — Alpine.js + Tailwind CSS (dark mode)
      app.js               # Logika frontendu — Alpine.js store
      style.css            # Kolorowanie skladni, animacje, custom scrollbar
tests/                     # 100 testow pytest
examples/                  # Przykladowe pliki initiators/targets (TXT + YAML)
database/                  # Katalog roboczy (projekty, logi, archiwum)
```

---

## CLI — Interfejs wiersza polecen

### `init` — Tryb batch

Generuje zony dla wszystkich iniciatorow x wszystkich targetow (lub grup). Tryb nieinteraktywny.

```bash
san-zone-designer init [OPCJE]
```

| Opcja | Skrot | Typ | Domyslnie | Opis |
|-------|-------|-----|-----------|------|
| `--initiators` | `-i` | TEXT | **wymagany** | Plik iniciatorow (txt lub yaml) |
| `--targets` | `-t` | TEXT | **wymagany** | Plik targetow (txt lub yaml) |
| `--vsan` | | INT | `0` | Numer VSAN (wymagany dla Cisco) |
| `--vsn` | | TEXT | `VSAN_<N>` | Nazwa VSAN |
| `--if` / `--iface` | | TEXT | `1-32` | Zakres interfejsow FC |
| `--zs` / `--zoneset` | | TEXT | `zoneset_vsan_<N>` / `cfg` | Nazwa zoneset/CFG |
| `--output` | `-o` | TEXT | stdout | Plik wyjsciowy konfiguracji |
| `--csv` | | TEXT | brak | Plik eksportu CSV |
| `--vendor` | | TEXT | `cisco` | Vendor: `cisco` lub `brocade` |
| `--mode` | | TEXT | `single` | Tryb: `single` (1:1) lub `many` (1:N z grupami) |
| `--order` | | TEXT | `ti` | Kolejnosc nazwy: `ti` (target_initiator) lub `it` |
| `--sep` / `--ul` | | TEXT | `two` | Separator: `one` (_) lub `two` (__) |
| `--dry` | | FLAG | false | Dry-run — tylko podsumowanie bez generowania |
| `--rollback` | | FLAG | false | Generuj pliki rollback (.cfg + .csv) |
| `--plain` | | FLAG | false | Wylacz kolorowy output |
| `--fabric` | | TEXT | brak | Filtruj po nazwie fabric (np. `Fabric_A`) |

**Przyklady:**

```bash
# Cisco MDS — podstawowe uzycie
san-zone-designer init -i examples/initiators.txt -t examples/targets.txt --vsan 100

# Cisco MDS — pelne opcje
san-zone-designer init \
  -i examples/initiators.yaml \
  -t examples/targets.yaml \
  --vsan 100 --vsn PROD_VSAN --if 1-16 --zs my_zoneset \
  --vendor cisco --mode many --order ti --sep two \
  -o output.cfg --csv zones.csv --rollback

# Brocade FOS
san-zone-designer init -i examples/initiators.txt -t examples/targets.txt --vendor brocade

# Dry-run (podglad bez generowania)
san-zone-designer init -i examples/initiators.txt -t examples/targets.txt --vsan 100 --dry

# Filtrowanie po fabric
san-zone-designer init -i examples/initiators.yaml -t examples/targets.yaml --vsan 100 --fabric Fabric_A
```

---

### `expand` — Tryb interaktywny

Interaktywny wybor par iniciator-target z podgladem przed generacja. Wykorzystuje InquirerPy do wielokrotnego wyboru z listy.

```bash
san-zone-designer expand [OPCJE]
```

Opcje identyczne jak `init`, plus:

| Opcja | Opis |
|-------|------|
| `--batch` | Tryb nieinteraktywny all x all (identyczny z `init`) |

**Przebieg interaktywny:**
1. Wyswietla liste iniciatorow z checkboxami (grupowane wg hosta)
2. Dla kazdego wybranego iniciatora wyswietla liste targetow (grupowane wg storage_array/group)
3. Pokazuje tabele podgladu wybranych zon
4. Prosi o potwierdzenie przed generacja

```bash
# Interaktywny (domyslny)
san-zone-designer expand -i examples/initiators.txt -t examples/targets.txt --vsan 100

# Batch (identyczny z init)
san-zone-designer expand --batch -i examples/initiators.txt -t examples/targets.txt --vsan 100
```

---

### `migrate` — Migracja txt na yaml

Konwertuje pliki TXT (format `ALIAS WWPN`) na rozszerzony format YAML z automatycznym wykrywaniem metadanych.

```bash
san-zone-designer migrate [OPCJE]
```

| Opcja | Skrot | Typ | Domyslnie | Opis |
|-------|-------|-----|-----------|------|
| `--input` | `-i` | TEXT | **wymagany** | Plik wejsciowy txt |
| `--output` | `-o` | TEXT | **wymagany** | Plik wyjsciowy yaml |
| `--type` | | TEXT | `auto` | Typ: `initiators`, `targets` lub `auto` |

**Auto-detekcja typu** na podstawie nazwy pliku:
- Nazwy zawierajace `init` lub `hba` → `initiators`
- Nazwy zawierajace `target` lub `tgt` → `targets`

**Auto-detekcja metadanych:**
- **Host** — z aliasu iniciatora: `AK_SRV_04_HBA0` → host: `AK_SRV_04` (strip `_HBA\d+`, `_FC\d+`)
- **Storage array** — z aliasu targetu: `AK_ARRAY_02_CT0_FC0` → storage_array: `AK_ARRAY_02` (strip `_CT\d+_FC\d+`, `_SVM_FC_\d+`, itp.)

```bash
san-zone-designer migrate -i examples/initiators.txt -o initiators.yaml
san-zone-designer migrate -i examples/targets.txt -o targets.yaml --type targets
```

---

### `diff` — Porownanie zon

Porownuje nowo wygenerowane zony z istniejaca konfiguracja przelacznika.

```bash
san-zone-designer diff [OPCJE]
```

Opcje jak `init`, plus:

| Opcja | Skrot | Opis |
|-------|-------|------|
| `--existing` | `-e` | **wymagany** — plik z istniejaca konfiguracja switcha |

**Obslugiwane formaty pliku `-e`:**

| Format | Vendor | Opis |
|--------|--------|------|
| `show zoneset active` | Cisco | Output z `show zoneset active vsan <N>` |
| Komendy `zone name` + `member` | Cisco | Plik konfiguracyjny |
| `cfgshow` | Brocade | Output z `cfgshow` (obsluguje multi-line) |
| Komendy `zonecreate` | Brocade | Plik z komendami Brocade |

**Wynik** — tabela z kolorowanymi wierszami:
- `+ ADD` (zielony) — nowa zona do dodania
- `- REMOVE` (czerwony) — zona do usuniecia
- `= UNCHANGED` (szary) — zona bez zmian
- `~ MODIFIED` (zolty) — zona ze zmienionymi czlonkami

```bash
san-zone-designer diff \
  -i examples/initiators.txt -t examples/targets.txt \
  -e show_zoneset_output.txt --vsan 100 --vendor cisco
```

---

### `web` — Serwer webowy

Uruchamia interfejs webowy (FastAPI + Alpine.js).

```bash
san-zone-designer web [OPCJE]
```

| Opcja | Domyslnie | Opis |
|-------|-----------|------|
| `--port` | `8000` | Port serwera |
| `--host` | `0.0.0.0` | Adres nasluchiwania |
| `--ssl-cert` | brak | Sciezka do certyfikatu SSL (PEM) |
| `--ssl-key` | brak | Sciezka do klucza prywatnego SSL (PEM) |
| `--ssl-key-password` | brak | Haslo do klucza prywatnego SSL |
| `--ssl-self-signed` | `false` | Generuj samopodpisany certyfikat (dev/test) |

```bash
# Domyslne ustawienia (HTTP)
san-zone-designer web

# Niestandardowy port
san-zone-designer web --port 9090

# Dostep tylko lokalny
san-zone-designer web --host 127.0.0.1 --port 8080

# HTTPS z wlasnym certyfikatem
san-zone-designer web --ssl-cert cert.pem --ssl-key key.pem

# HTTPS z samopodpisanym certyfikatem (dev)
san-zone-designer web --ssl-self-signed
```

Po uruchomieniu otworz przegladarke: `http://localhost:8000` (lub `https://` przy wlaczonym SSL)

**Domyslne konto administratora:** `admin` / `admin` (tworzone automatycznie przy pierwszym uruchomieniu — zmien haslo!).

---

## Web GUI — Interfejs graficzny

Aplikacja SPA (Single Page Application) z ciemnym motywem, oparta na Alpine.js i Tailwind CSS.

### Logowanie i sesje

Po uruchomieniu serwera (`san-zone-designer web`) wyswietlany jest ekran logowania.

- Wpisz nazwe uzytkownika i haslo
- Po udanym logowaniu ustawiane jest ciasteczko sesji (`session_token`, httponly, samesite=strict)
- Sesja wygasa po **15 minutach** nieaktywnosci (sliding window — kazde zapytanie API przedluza sesje)
- Przycisk **Logout** w naglowku koncczy sesje
- Przy pierwszym uruchomieniu tworzone jest domyslne konto `admin`/`admin`

### Zakladka Generate

Sluzy do generowania konfiguracji batch (all x all).

**Formularz konfiguracji:**
- Wybor pliku iniciatorow i targetow z dropdowna (lub przez sidebar)
- Vendor: Cisco / Brocade (radio button)
- VSAN (wymagany dla Cisco)
- Mode: Single / Many
- Order: TI (target_initiator) / IT
- Separator: Double (__) / Single (_)
- Rollback: checkbox
- Opcjonalne: VSAN Name, Interface Range, Zoneset Name, Fabric Filter

**Przyciski akcji:**
- **Preview (dry-run)** — laduje pliki, oblicza zony, wyswietla tabele podgladu (nazwa zony, iniciator, target(y)). Nie generuje konfiguracji.
- **Generate** — pelna generacja. Wyswietla kolorowana konfiguracje, tabele zon, przyciski pobierania.

**Wyniki:**
- Kolorowana konfiguracja z podswietlaniem skladni (komendy = zielony, WWPN = zolty, komentarze = szary)
- Przyciski: **Copy** (do schowka), **Download .cfg**, **Download CSV**, **Download Rollback**
- Banner z lista auto-zapisanych plikow (np. `MyProject/_output/initial_2026-02-21_14-30-00.cfg`)
- **Czerwony panel ostrzezen** — wyswietla bledy walidacji (nieprawidlowy WWPN, duplikaty aliasow/WWPN, podejrzane zakresy NAA)

### Zakladka Expand

Sluzy do selektywnego generowania wybranych par iniciator-target.

**Przebieg:**
1. Kliknij **Load & Preview** — laduje pliki i buduje siatke checkboxow
2. Siatka pokazuje kazdego iniciatora z lista jego targetow jako checkboxy
3. Przy kazdym iniciatorze przyciski **All** / **None** do szybkiego zaznaczania
4. Odznacz niepotrzebne pary
5. Kliknij **Generate Selected** — generuje konfiguracje tylko z wybranych par

Wyniki identyczne jak w zakladce Generate (kolorowana konfiguracja, CSV, rollback, auto-save).

### Zakladka Migrate

Konwersja plikow TXT na format YAML z podgladem.

**Pola formularza:**
- Input file — dropdown z plikami .txt ze wszystkich projektow
- File type — `auto` / `initiators` / `targets`
- Output project — dropdown z istniejacymi projektami
- Output filename — nazwa pliku docelowego (np. `initiators.yaml`)

**Przyciski:**
- **Preview** — wyswietla podglad wygenerowanego YAML i liczbe wpisow
- **Migrate & Save** — zapisuje plik YAML do wybranego projektu

### Zakladka Diff

Porownanie wygenerowanych zon z istniejaca konfiguracja przelacznika.

**Dodatkowe pole:** Existing zone file — plik z outputem `show zoneset active` lub `cfgshow`

**Wynik** — tabela z kolorowanymi wierszami:
- Zielony = zona do dodania
- Czerwony = zona do usuniecia
- Zolty = zona ze zmienionymi czlonkami
- Szary = zona bez zmian
- Podsumowanie: liczba dodanych, usunietych, niezmienionych, zmodyfikowanych

### Sidebar — przegladarka plikow

Panel boczny (lewa strona) wyswietla drzewo projektow i plikow.

- Projekty wyswietlane jako foldery (klik rozwijaja zawartosc)
- Pliki kolorowane wg typu: **zielony** = iniciatory, **niebieski** = targety, **szary** = inne
- **Klik na projekt** — ustawia go jako aktywny i automatycznie wybiera pierwszy plik iniciatorow i targetow
- **Przycisk "Use"** — recznie przypisuje plik jako iniciatory, targety lub istniejacy plik zon
- Na dole sidebara wyswietlane sa aktualnie wybrane pliki

### Manage Files — zarzadzanie plikami

Modal dostepny przez przycisk **Manage Files** w naglowku.

**Panel lewy:**
- **Create Project** — pole tekstowe + przycisk. Tworzy nowy katalog projektu. Non-admin automatycznie otrzymuje dostep.
- **Lista projektow** z plikami (wlacznie z `_output/`):
  - Drag & drop upload plikow (lub klik)
  - Po najechaniu na plik pojawiaja sie ikony akcji:
    - **Use** — przypisanie pliku jako iniciatory/targety/existing
    - **⬇ Download** — pobranie pliku na dysk lokalny
    - **🗑 Delete** — soft-delete (przeniesienie do archiwum)
  - Przycisk usuwania projektu (tylko admin, soft-delete)

**Panel prawy — podglad pliku:**
- Klik na plik wyswietla:
  - Tabele sparsowanych wpisow (Alias, WWPN)
  - **Czerwony panel ostrzezen** — jesli plik zawiera bledy:
    - Nieprawidlowy format WWPN (np. brakujacy oktet, niedozwolone znaki)
    - Duplikaty aliasow
    - Duplikaty adresow WWPN
    - Podejrzane zakresy WWPN (all-zero, broadcast, nietypowe NAA)
  - Surowa zawartosc pliku

**Dozwolone rozszerzenia uploadu:** `.yaml`, `.yml`, `.txt`, `.cfg`, `.csv`, `.json`

### Zakladka Editor — edycja plikow

Zakladka dostepna dla wszystkich uzytkownikow. Umozliwia bezposrednia edycje plikow iniciatorow i targetow w formacie YAML.

**Pasek plikow:**
- Wyswietla kontekst aktywnego projektu (ikona folderu + nazwa)
- Pliki wyswietlane jako kolorowe chipy: zielone (initiators), niebieskie (targets)
- Aktywny plik podswietlony pierścieniem i cieniem
- Jesli brakuje pliku danego typu — przycisk `+` do utworzenia nowego pliku
- Badge informacyjny z typem pliku i liczba wpisow
- Przycisk **Save** (zolty gdy sa niezapisane zmiany)

**Tabela edycji:**
- Naglowki kolumn: Alias\*, WWPN\*, Host/Group/Storage Array/Port (w zaleznosci od typu), Fabric, VSAN, Description
- Walidacja w czasie rzeczywistym — czerwone obramowanie blednych pol
- Automatyczne formatowanie WWPN (16 znakow hex → format `XX:XX:...`)
- Przycisk `+` dodaje nowy wiersz, `×` usuwa wiersz
- Ostrzezenie `beforeunload` przy probie zamkniecia strony z niezapisanymi zmianami

**Integracja z sidebarem:**
- Przycisk **Edit** przy plikach iniciatorow/targetow otwiera plik bezposrednio w edytorze
- Na zakladce Editor klik na plik w sidebarze laduje go do edytora

### Zmiana hasla

Kazdy zalogowany uzytkownik moze zmienic swoje haslo przez przycisk **🔒 Password** w naglowku.

- Modal z trzema polami: aktualne haslo, nowe haslo, potwierdzenie
- Walidacja po stronie klienta: minimalna dlugosc (4 znaki), zgodnosc hasel
- Walidacja po stronie serwera: weryfikacja aktualnego hasla (bcrypt)
- Zmiana logowana w audit logu (`auth.password_changed`)

### Manage Users — zarzadzanie uzytkownikami

Modal dostepny tylko dla **administratora** przez przycisk **Manage Users** w naglowku.

**Tworzenie uzytkownika:**
- Username, Password, Role (`admin` / `user`), Projects (lista oddzielona przecinkami)

**Lista uzytkownikow:**
- Nazwa z badge'em roli (czerwony = admin, niebieski = user)
- Badge'e przypisanych projektow
- Edycja projektow inline (klik na "Edit" → pole tekstowe → Save/Cancel)
- Przycisk Delete (z potwierdzeniem)

### Zakladka Configuration

Dostepna tylko dla administratora. Zakladka widoczna w nawigacji tylko po zalogowaniu na konto z rola `admin`.

**Zarzadzanie licencja:**
- Wyswietla aktualne informacje licencyjne (firma, data wydania, data wygasniecia, liczba stanowisk, liczba przelacznikow)
- Pole do wklejenia nowego klucza licencyjnego (Ed25519 signed)
- Przycisk **Save Configuration** weryfikuje podpis klucza i zapisuje go do `database/configuration.yaml`

### Zakladka Logs

Dostepna tylko dla administratora. Wyswietla dwa rodzaje logow:

**Audit Log** — strukturalny rejestr zdarzen (kto, co, kiedy):
- Tabela z kolumnami: Timestamp, Event, Actor, Project, Outcome, Details
- Zdarzenia kolorowane wg kategorii:
  - Niebieski = uwierzytelnianie (`auth.*`)
  - Zielony = generowanie konfiguracji (`config.*`)
  - Zolty = operacje na plikach (`file.*`)
  - Fioletowy = operacje na projektach (`project.*`)
  - Czerwony = zarzadzanie uzytkownikami (`user.*`)
- Filtry: Actor (dropdown), Event Type (dropdown), Project (dropdown), Outcome (success/failure)
- Przycisk **Clear Filters** resetuje wszystkie filtry
- Wpisy posortowane od najnowszych

**Application Log** — log systemowy aplikacji:
- Tabela z kolumnami: Timestamp, Level, Logger, Message
- Filtr Level: All / INFO / WARNING / ERROR
- Poziomy kolorowane: INFO = zielony, WARNING = zolty, ERROR = czerwony
- Przycisk **Refresh** odswierza dane

Wiecej szczegolow technicznych w sekcji [System logowania](#system-logowania).

---

## Zabezpieczenia

### Uwierzytelnianie i sesje

- **Hasla** hashowane algorytmem **bcrypt** (biblioteka `bcrypt>=4.0`)
- Hasla przechowywane w `database/.secrets.json` jako `password_hash` — nigdy w postaci jawnej
- **Sesje** przechowywane w pamieci serwera (`SESSION_STORE` — slownik Python)
- Token sesji to losowy 64-znakowy ciag hex (`secrets.token_hex(32)`)
- Ciasteczko `session_token` ustawiane z flagami:
  - `httponly` — niedostepne z JavaScript (ochrona przed XSS)
  - `samesite=strict` — ochrona przed CSRF
- **TTL sesji:** 15 minut, sliding window (kazde zapytanie API przedluza czas wygasniecia)
- Restart serwera invaliduje wszystkie sesje (in-memory store)

### Role i kontrola dostepu

System dwoch rol: **admin** i **user**.

| Operacja | Admin | User |
|----------|-------|------|
| Lista projektow (`GET /api/files/`) | Wszystkie | Tylko przypisane |
| Tworzenie projektu | Tak | Tak (auto-dostep) |
| Usuwanie projektu | Tak | Brak dostepu (403) |
| Upload/podglad/usuwanie plikow | Wszystkie projekty | Tylko przypisane |
| Generate/Expand/Migrate/Diff | Wszystkie projekty | Tylko przypisane |
| Zarzadzanie uzytkownikami | Tak | Brak dostepu (403) |
| Zmiana projektow uzytkownika | Tak | Brak dostepu (403) |
| Configuration (licencja) | Tak | Zakladka ukryta |
| Logs (przegladanie logow) | Tak | Zakladka ukryta + 403 na API |

**Przypisywanie projektow:**
- Admin przypisuje projekty uzytkownikowi przez Manage Users (PUT `/api/auth/users/{username}`)
- Przy tworzeniu projektu non-admin automatycznie otrzymuje do niego dostep
- Zmiana przypisanych projektow synchronizuje sie natychmiast ze wszystkimi aktywnymi sesjami uzytkownika

**Domyslne konto:** Przy pierwszym uruchomieniu (pusta baza) tworzone jest konto `admin`/`admin` z ostrzezeniem w logach.

### Ochrona sciezek plikow

Funkcja `resolve_db_path(relative_path)` chroni przed atakami path traversal:
- Rozwiazuje sciezke wzgledem `DATABASE_DIR`
- Sprawdza czy wynikowa sciezka absolutna zaczyna sie od `DATABASE_DIR`
- Blokuje proby uzycia `../`, `/etc/passwd`, itp. (HTTP 400)
- Loguje proby ataków

### Limity uploadu

- Maksymalny rozmiar pliku: **50 MB**
- Pliki czytane w fragmentach po 64 KB (nie laduja calego pliku do pamieci)
- Przekroczenie limitu zwraca HTTP **413** (Payload Too Large)
- Dozwolone rozszerzenia: `.yaml`, `.yml`, `.txt`, `.cfg`, `.csv`, `.json`
- Niedozwolone rozszerzenie zwraca HTTP **400**

### Soft-delete — archiwizacja zamiast usuwania

Wszystkie operacje usuwania sa odwracalne:

- **Usuwanie pliku** — plik przenoszony do `database/deleted/{project}/{nazwa}_{timestamp}.ext`
- **Usuwanie projektu** (admin) — caly katalog przenoszony do `database/deleted/{project}_{timestamp}/`
- Kolizje nazw rozwiazywane przez licznik (`_1`, `_2`, ...)
- Dane zawsze mozna odzyskac recznym przeniesieniem z katalogu `deleted/`

---

## Walidacja danych wejsciowych

System wielopoziomowej walidacji plikow wejsciowych. Ostrzezenia wyswietlane w czerwonym panelu zarowno w podgladzie pliku (Manage Files) jak i przy generowaniu/dry-run (Generate/Expand).

### Walidacja formatu WWPN

- Format wymagany: `XX:XX:XX:XX:XX:XX:XX:XX` (8 oktetow hex oddzielonych dwukropkami)
- Normalizacja: male litery, dopelnianie zer (`5:0:...` → `05:00:...`)
- Blad jezeli: brakujacy oktet, niedozwolone znaki (np. `0g`), za krotki/dlugi adres
- Komunikat: `Invalid WWPN '50:00:00:00:00:00:01' (alias: server2)`

### Walidacja zakresu WWPN

- All-zero (`00:00:00:00:00:00:00:00`) — nieprawidlowy
- Broadcast (`ff:ff:ff:ff:ff:ff:ff:ff`) — nieprawidlowy
- Nietypowy identyfikator NAA (pierwszy nibble hex) — ostrzezenie jesli nie jest `1`, `2`, `5` lub `6` (standardowe dla Fibre Channel)
- Komunikat: `server1: 00:00:00:00:00:00:00:00 — all-zero WWPN is invalid`

### Walidacja aliasow

- Dozwolone znaki: `a-zA-Z0-9_-`
- Maksymalna dlugosc: 64 znaki
- Nie moze byc pusty
- Komunikat: `Alias name contains invalid characters: srv@01`

### Detekcja duplikatow

Skanowanie surowego pliku (przed parsowaniem) w celu wykrycia:
- **Duplikat aliasu** — dwa wpisy z ta sama nazwa
- **Duplikat WWPN** — dwa wpisy z tym samym adresem WWPN
- Komunikat: `Duplicate alias: server1` / `Duplicate WWPN: 50:00:... (alias: server3)`

Parser (TXT i YAML) dodatkowo deduplikuje wpisy — duplikaty sa pomijane z logowaniem ostrzezenia.

### Gdzie wyswietlane sa ostrzezenia

| Miejsce | Kiedy |
|---------|-------|
| Manage Files — podglad pliku | Klik na plik w modalu Manage Files |
| Generate — po Preview (dry-run) | Czerwony panel pod przyciskami akcji |
| Generate — po Generate | Czerwony panel pod przyciskami akcji |
| Expand — po Load & Preview | Czerwony panel pod przyciskami akcji |
| Expand — po Generate Selected | Czerwony panel pod przyciskami akcji |

---

## API REST — endpointy

Wszystkie endpointy pod `/api/` wymagaja waznej sesji (ciasteczko `session_token`), z wyjatkiem `/api/auth/login`.

### Auth API

| Metoda | Sciezka | Autoryzacja | Opis |
|--------|---------|-------------|------|
| `POST` | `/api/auth/login` | Brak | Logowanie. Body: `{username, password}`. Ustawia ciasteczko sesji. Zwraca: `{username, role, projects}`. |
| `POST` | `/api/auth/logout` | User | Wylogowanie. Usuwa ciasteczko sesji. |
| `GET` | `/api/auth/me` | User | Dane zalogowanego uzytkownika: `{username, role, projects}`. |
| `PUT` | `/api/auth/password` | User | Zmiana hasla. Body: `{current_password, new_password}`. Weryfikuje aktualne haslo, waliduje nowe (min. 4 znaki). |
| `GET` | `/api/auth/users` | Admin | Lista wszystkich uzytkownikow: `[{username, role, projects}]`. |
| `POST` | `/api/auth/users` | Admin | Tworzenie uzytkownika. Body: `{username, password, role, projects}`. |
| `PUT` | `/api/auth/users/{username}` | Admin | Aktualizacja projektow uzytkownika. Body: `{projects: [...]}`. Synchronizuje aktywne sesje. |
| `DELETE` | `/api/auth/users/{username}` | Admin | Usuwanie uzytkownika. Invaliduje wszystkie jego sesje. Nie mozna usunac samego siebie. |

### Files API

| Metoda | Sciezka | Autoryzacja | Opis |
|--------|---------|-------------|------|
| `GET` | `/api/files/` | User | Lista projektow i plikow. `?include_output=true` wlacza pliki z `_output/`. Non-admin widzi tylko swoje projekty. |
| `POST` | `/api/files/project` | User | Tworzenie projektu. Body: `{name}`. Tworca automatycznie otrzymuje dostep. |
| `POST` | `/api/files/upload?project={name}` | User (dostep) | Upload plikow (multipart). Walidacja rozszerzenia i rozmiaru. |
| `GET` | `/api/files/{project}/{filename}` | User (dostep) | Podglad pliku: surowa zawartosc + sparsowane wpisy + ostrzezenia walidacji + wszystkie pola YAML. |
| `PUT` | `/api/files/{project}/{filename}` | User (dostep) | Zapis edytowanych wpisow. Body: `{entries: [...], file_type}`. Waliduje wpisy, wykrywa duplikaty, zapisuje YAML. |
| `DELETE` | `/api/files/{project}/{filename}` | User (dostep) | Soft-delete pliku (przeniesienie do archiwum). |
| `DELETE` | `/api/files/{project}` | Admin | Soft-delete projektu (archiwizacja calego katalogu). |

### Generate API

Wszystkie endpointy przyjmuja body JSON z konfiguracja generowania.

| Metoda | Sciezka | Autoryzacja | Opis |
|--------|---------|-------------|------|
| `POST` | `/api/generate/preview` | User (dostep) | Dry-run. Zwraca: `{initiators, targets, zones, summary, warnings}`. Bez zapisu plikow. |
| `POST` | `/api/generate/init` | User (dostep) | Pelna generacja all x all. Zwraca: `{config, summary, csv, rollback_cfg, zones, saved_files, warnings}`. Auto-zapis do `_output/`. |
| `POST` | `/api/generate/expand` | User (dostep) | Generacja z wybranych par. Dodatkowe pole: `selected_pairs: [{initiator, targets: [...]}]`. Auto-zapis do `_output/`. |

**Body konfiguracji (GenerateRequest):**
```json
{
  "initiators_path": "MyProject/initiators.yaml",
  "targets_path": "MyProject/targets.yaml",
  "vendor": "cisco",
  "mode": "single",
  "order": "ti",
  "separator": "two",
  "vsan": 100,
  "vsan_name": "",
  "iface_range": "1-32",
  "zoneset_name": "",
  "fabric_filter": "",
  "rollback": false
}
```

### Migrate API

| Metoda | Sciezka | Autoryzacja | Opis |
|--------|---------|-------------|------|
| `POST` | `/api/migrate/preview` | User (dostep) | Podglad YAML. Zwraca: `{yaml_content, entry_count, file_type}`. |
| `POST` | `/api/migrate/` | User (dostep) | Migracja i zapis. Zwraca: `{count, output, saved_files}`. |

### Diff API

| Metoda | Sciezka | Autoryzacja | Opis |
|--------|---------|-------------|------|
| `POST` | `/api/diff/` | User (dostep) | Porownanie zon. Zwraca: `{added, removed, unchanged, modified, summary, saved_files}`. Auto-zapis diff do `_output/`. |

### Config API

| Metoda | Sciezka | Autoryzacja | Opis |
|--------|---------|-------------|------|
| `GET` | `/api/config/license` | User | Pobranie aktualnej licencji i zdekodowanych informacji. Zwraca: `{license_key, info, error?}`. |
| `POST` | `/api/config/license` | User | Weryfikacja i zapis klucza licencyjnego. Body: `{license_key}`. Waliduje podpis Ed25519 przed zapisem do `database/configuration.yaml`. |

### Logs API

Pelny opis endpointow w sekcji [System logowania — Logs API](#logs-api).

| Metoda | Sciezka | Autoryzacja | Opis |
|--------|---------|-------------|------|
| `GET` | `/api/logs/audit` | Admin | Wpisy audit logu z filtrami (actor, event_type, project, outcome). |
| `GET` | `/api/logs/app` | Admin | Wpisy logu aplikacyjnego z filtrem level. |
| `GET` | `/api/logs/actors` | Admin | Lista unikalnych aktorow. |
| `GET` | `/api/logs/event-types` | Admin | Lista unikalnych typow zdarzen. |

---

## Formaty plikow wejsciowych

### TXT — format prosty (kompatybilny wstecz)

```
# Komentarz (ignorowany w single mode, nazwa grupy w many mode)
ALIAS_NAME 21:00:f4:e9:d4:53:a5:5a
```

**Targets w trybie `many`** — grupy oddzielone pusta linia, `#` definiuje nazwe grupy:
```
#Storage_A
ARRAY_01_CT0_FC0 52:4a:93:77:0a:d3:f8:00
ARRAY_01_CT0_FC1 52:4a:93:77:0a:d3:f8:01

#Storage_B
ARRAY_02_CT0_FC0 52:4a:93:77:0b:d3:f8:00
```

### YAML — format rozszerzony (v1.1)

```yaml
initiators:
  - alias: ESX01_HBA0
    wwpn: "21:00:f4:e9:d4:53:a5:5a"
    host: ESX01               # opcjonalne
    fabric: Fabric_A          # opcjonalne — do filtrowania
    vsan_id: 100              # opcjonalne
    description: "ESX host"   # opcjonalne

targets:
  - alias: ARRAY_01_CT0_FC0
    wwpn: "52:4a:93:77:0a:d3:f8:00"
    group: Storage_A            # opcjonalne — grupa (tryb many)
    storage_array: ARRAY_01     # opcjonalne
    port: CT0_FC0               # opcjonalne
    fabric: Fabric_A            # opcjonalne — do filtrowania
    vsan_id: 100                # opcjonalne
    description: "Controller 0" # opcjonalne
```

**Filtrowanie po fabric:** Pole `fabric` w YAML sluzy do filtrowania — opcja `--fabric Fabric_A` (CLI) lub pole `fabric_filter` (web) laduje tylko wpisy z pasujaca nazwa fabric (porownanie case-insensitive).

---

## Generatory konfiguracji

### Cisco MDS NX-OS (`CiscoGenerator`)

Generuje kompletna konfiguracje NX-OS:

1. **Konfiguracja VSAN** — `vsan database`, tworzenie VSAN, przypisanie do interfejsow, `no shutdown`
2. **Device-aliasy** — `device-alias database`, tworzenie aliasow z WWPN, `device-alias commit`
3. **Zony** — `zone name {zona} vsan {N}`, `member device-alias {alias}`
4. **Zoneset** — `zoneset name {nazwa} vsan {N}`, `member {zona}`, aktywacja, `copy running-config startup-config`
5. **Rollback** (opcjonalnie) — komendy `no device-alias name`, `no zone name`, `no zoneset name`

**Format CSV:** `ZoneName;InitiatorAlias;InitiatorWWPN;TargetAlias;TargetWWPN;VSAN`

### Brocade FOS (`BrocadeGenerator`)

Generuje komendy Brocade FOS:

1. **Aliasy** — `alicreate "{alias}","{wwpn}"`
2. **Zony** — `zonecreate "{zona}","{init};{tgt1};{tgt2}"`
3. **Konfiguracja CFG** — `cfgcreate`, `cfgadd`, `cfgenable`, `cfgsave`
4. **Rollback** (opcjonalnie) — `alidelete`, `zonedelete`, `cfgdelete`, `cfgdisable`, `cfgsave`

### Tryby zoningu

- **`single`** — Kazdy iniciator sparowany z kazdym targetem indywidualnie = 1 zona na pare (N iniciatorow x M targetow = N*M zon)
- **`many`** — Kazdy iniciator sparowany z kazda grupa targetow = 1 zona na grupe (N iniciatorow x G grup = N*G zon)

### Konwencja nazewnictwa zon

Format: `{target}{separator}{initiator}` (domyslnie TI order) lub `{initiator}{separator}{target}` (IT order).

Separator: `__` (domyslnie, double underscore) lub `_` (single underscore).

Przyklad: `AK_ARRAY_02_CT0_FC0__AK_SRV_04_HBA0` (TI, double underscore).

---

## System parsowania plikow

Parser obsluguje dwa formaty wejsciowe (TXT i YAML) i automatycznie wykrywa format na podstawie rozszerzenia pliku.

### Parsery TXT

**`parse_initiators_txt(path)`:**
- Czyta linie `ALIAS WWPN`
- Pomija komentarze (`#`) i puste linie
- Waliduje alias (znaki, dlugosc) i WWPN (format)
- **Deduplikuje** — pomija wpisy z powtorzonym aliasem lub WWPN (z logowaniem)
- Zwraca `list[HBA]`

**`parse_targets_txt(path, mode)`:**
- Tryb `single` — identycznie jak iniciatory
- Tryb `many` — `#NazwaGrupy` definiuje grupe, pusta linia konczy grupe, wpisy dziedzicza aktualna nazwe grupy
- **Deduplikuje** — pomija powtorzone aliasy/WWPN
- Zwraca `list[Target]`

### Parsery YAML

**`parse_initiators_yaml(path)`:**
- Czyta liste `data["initiators"]`
- Obsluguje wszystkie pola HBA (alias, wwpn, host, fabric, vsan_id, description)
- **Deduplikuje** — pomija powtorzone aliasy/WWPN (od v1.1)
- Zwraca `list[HBA]`

**`parse_targets_yaml(path)`:**
- Czyta liste `data["targets"]`
- Obsluguje wszystkie pola Target (alias, wwpn, group, storage_array, port, fabric, vsan_id, description)
- **Deduplikuje** — pomija powtorzone aliasy/WWPN (od v1.1)
- Zwraca `list[Target]`

### Automatyczna detekcja formatu

`load_initiators(path)` i `load_targets(path, mode)` wybieraja parser na podstawie rozszerzenia:
- `.yaml`, `.yml` → parser YAML
- Wszystko inne → parser TXT

---

## Import zon z przelacznika

Modul `importer.py` parsuje output z przelacznikow do obiektow `Zone` (uzywany przez komende `diff`).

### Cisco

- **`show zoneset active`** — rozpoznaje bloki `zone name X vsan N` + `member device-alias Y` / `member pwwn Z` + `exit`
- **Komendy konfiguracyjne** — rozpoznaje `zone name X vsan N` + `member device-alias Y`
- Auto-detekcja formatu na podstawie zawartosci pliku

### Brocade

- **`cfgshow`** — rozpoznaje `zone: ZONE_NAME\tALIAS1;ALIAS2;ALIAS3` (obsluguje kontynuacje wieloliniowa)
- **Komendy `zonecreate`** — rozpoznaje `zonecreate "ZONE","ALIAS1;ALIAS2"`
- Auto-detekcja formatu na podstawie zawartosci pliku

**Konwersja czlonkow:**
- Pierwszy czlonek = iniciator, pozostali = targety
- Jesli czlonek wyglada jak WWPN — uzywany bezposrednio
- Jesli czlonek to alias — tworzony wpis z placeholder WWPN (`00:00:00:00:00:00:00:00`)

---

## Struktura katalogow bazy danych

```
database/
  {NazwaProjektu}/              # Katalogi projektow uzytkownikow
    initiators.yaml             # Pliki wejsciowe
    targets.yaml
    existing_zones.cfg
    _output/                    # Auto-generowane pliki wyjsciowe
      initial_2026-02-21_14-30-00.cfg
      initial_2026-02-21_14-30-00.csv
      expand_2026-02-21_15-00-00.cfg
      diff_2026-02-21_16-00-00.json
      migrate_2026-02-21_17-00-00.yaml
  _generated/                   # Pliki wygenerowane bez kontekstu projektu
  deleted/                      # Archiwum soft-delete
    {Projekt}_{timestamp}/      # Usuniete projekty
    {Projekt}/                  # Usuniete pliki z projektu
      {plik}_{timestamp}.ext
  logs/
    san_zone_designer.log       # Log aplikacyjny — rotujacy (5 plikow x 5 MB)
    audit.log                   # Audit log — JSON-lines (10 plikow x 10 MB)
  .secrets.json                 # Uzytkownicy i hashe hasel
  configuration.yaml            # Konfiguracja licencji
```

**Ukryte katalogi** (niewidoczne w przegladarce plikow): `logs`, `_generated`, `deleted`, katalogi zaczynajace sie od `.`

---

## System logowania

Aplikacja posiada dwa niezalezne systemy logowania: **log aplikacyjny** (klasyczny Python logging) i **audit log** (strukturalny rejestr zdarzen JSON-lines). Oba zapisuja dane do osobnych plikow w katalogu `database/logs/`.

### Log aplikacyjny

Plik: `database/logs/san_zone_designer.log`

Konfiguracja w `logging_config.py`:

| Parametr | Wartosc |
|----------|---------|
| Format | `%(asctime)s %(levelname)-8s %(name)s — %(message)s` |
| Format daty | `%Y-%m-%d %H:%M:%S` |
| Handler konsoli | `StreamHandler` → stdout |
| Handler pliku | `RotatingFileHandler` |
| Rozmiar rotacji | 5 MB |
| Liczba kopii | 5 (backupCount) |
| Kodowanie | UTF-8 |
| uvicorn.access | Wyciszony do WARNING |

**Przykladowy wpis:**

```
2026-02-22 14:35:18 INFO     san_zone_designer.web.routers.generate — User 'admin' generated initial config for project 'Produkcja': 48 zones, vendor=cisco, saved=[...]
```

**Logowane zdarzenia (INFO/WARNING/ERROR):**
- Logowanie/wylogowanie uzytkownikow (udane i nieudane proby)
- Tworzenie/usuwanie uzytkownikow i projektow
- Upload/usuwanie plikow
- Generowanie konfiguracji (ile zon, vendor, zapisane pliki)
- Archiwizacja projektow/plikow (soft-delete)
- Proby nieautoryzowanego dostepu
- Proby ataków path traversal
- Bledy parsowania plikow (nieprawidlowe wpisy, duplikaty)
- Ostrzezenia walidacji WWPN

### Audit log — rejestr zdarzen

Plik: `database/logs/audit.log`

Modul: `web/audit.py`

Audit log to osobny, strukturalny rejestr zdarzen w formacie **JSON-lines** (jedna linia JSON = jedno zdarzenie). Przechowuje informacje kto, co, kiedy wykonal i jaki byl wynik. Jest niezalezny od logu aplikacyjnego — nie propaguje wpisow do konsoli ani do `san_zone_designer.log`.

| Parametr | Wartosc |
|----------|---------|
| Format | JSON-lines (jeden obiekt JSON na linie) |
| Handler | `RotatingFileHandler` |
| Rozmiar rotacji | 10 MB |
| Liczba kopii | 10 (backupCount) |
| Kodowanie | UTF-8 |
| Propagacja | Wylaczona (`propagate = False`) |
| Logger name | `san_zone_designer.audit` |

**Struktura wpisu:**

```json
{
  "timestamp": "2026-02-22T14:35:18.123456+00:00",
  "event_type": "config.generated",
  "actor": "admin",
  "actor_role": "admin",
  "project": "DC_Krakow",
  "detail": {"zones": 48, "vendor": "cisco", "mode": "single", "saved_files": ["DC_Krakow/_output/initial_2026-02-22_14-35-18.cfg"]},
  "outcome": "success"
}
```

**Pola wpisu:**

| Pole | Typ | Opis |
|------|-----|------|
| `timestamp` | string (ISO 8601) | Czas zdarzenia w UTC (`datetime.now(timezone.utc).isoformat()`) |
| `event_type` | string | Typ zdarzenia w notacji `kategoria.akcja` (np. `auth.login`, `config.generated`) |
| `actor` | string | Nazwa uzytkownika lub `"system"` dla zdarzen systemowych |
| `actor_role` | string | Rola aktora: `"admin"`, `"user"` lub `"system"` |
| `project` | string | Nazwa projektu (pusty string jesli zdarzenie nie dotyczy projektu) |
| `detail` | object | Dodatkowe dane zdarzenia (zawartosc zalezy od typu zdarzenia) |
| `outcome` | string | Wynik: `"success"` lub `"failure"` |

**Rejestrowane typy zdarzen:**

| `event_type` | Kiedy | `detail` |
|--------------|-------|----------|
| `auth.login` | Udane logowanie | `{}` |
| `auth.login_failed` | Nieudane logowanie | `{username}` |
| `auth.logout` | Wylogowanie | `{}` |
| `user.created` | Admin stworzyl uzytkownika | `{target_user, role, projects}` |
| `user.deleted` | Admin usunal uzytkownika | `{target_user, sessions_invalidated}` |
| `user.projects_updated` | Admin zmienil projekty usera | `{target_user, projects}` |
| `project.created` | Utworzenie projektu | `{}` |
| `project.deleted` | Archiwizacja projektu (admin) | `{archived_to}` |
| `file.uploaded` | Upload plikow | `{files, count}` |
| `file.deleted` | Archiwizacja pliku | `{filename, archived_to}` |
| `file.migrated` | Migracja TXT → YAML | `{input, output, entries, file_type}` |
| `config.generated` | Generacja init (all x all) | `{zones, vendor, mode, saved_files}` |
| `config.expanded` | Generacja expand (wybrane pary) | `{zones, pairs, vendor, saved_files}` |
| `config.diff` | Porownanie zon (diff) | `{added, removed, unchanged, modified}` |
| `audit.viewed` | Admin otworzyl zakladke Logs | `{}` |

**Uzycie w kodzie:**

```python
from ..audit import audit_log

# Zdarzenie uzytkownika
audit_log("config.generated", user, project="DC_Krakow",
          detail={"zones": 48, "vendor": "cisco"})

# Zdarzenie systemowe (brak usera)
audit_log("auth.login_failed", detail={"username": "hacker"}, outcome="failure")
```

Funkcja `audit_log()` przyjmuje:

| Parametr | Typ | Wymagany | Opis |
|----------|-----|----------|------|
| `event_type` | `str` | Tak | Typ zdarzenia w notacji `kategoria.akcja` |
| `user` | `dict \| None` | Tak | Dict z `get_current_user()` lub `None` dla zdarzen systemowych |
| `project` | `str` | Nie | Nazwa projektu (keyword-only) |
| `detail` | `dict \| None` | Nie | Dodatkowe dane (keyword-only) |
| `outcome` | `str` | Nie | `"success"` (domyslnie) lub `"failure"` (keyword-only) |

### Zakladka Logs w GUI

Zakladka **Logs** w interfejsie webowym (dostepna tylko dla administratora) odczytuje oba pliki logow i wyswietla je w tabelach z filtrami.

**Widok Audit Log:**
- Odczytuje ostatnie 2000 linii z `audit.log`, parsuje JSON, zwraca max 500 wpisow (najnowsze na gorze)
- Filtry: Actor, Event Type (prefiks kategorii), Project, Outcome
- Listy filtrów Actor i Event Type wypelniaja sie automatycznie z danych logu (endpointy `/api/logs/actors` i `/api/logs/event-types`)
- Zdarzenia kolorowane wg kategorii:
  - `auth.*` = niebieski
  - `config.*` = zielony
  - `file.*` = zolty
  - `project.*` = fioletowy
  - `user.*` = czerwony
  - `audit.*` = szary

**Widok Application Log:**
- Odczytuje ostatnie 2000 linii z `san_zone_designer.log`, parsuje format `TIMESTAMP LEVEL LOGGER — MESSAGE`
- Filtr Level: All / INFO / WARNING / ERROR
- Przycisk Refresh do recznego odswierzania

### Logs API

Wszystkie endpointy dostepne wylacznie dla administratora (`require_admin`).

| Metoda | Sciezka | Parametry query | Opis |
|--------|---------|-----------------|------|
| `GET` | `/api/logs/audit` | `limit` (1-2000, default 200), `actor`, `event_type`, `project`, `outcome` | Zwraca wpisy audit logu (najnowsze na gorze). Filtry: dokladne dopasowanie `actor`, `project`, `outcome`; prefiks `event_type` (np. `auth` filtruje `auth.login`, `auth.logout`). |
| `GET` | `/api/logs/app` | `limit` (1-2000, default 200), `level` | Zwraca wpisy logu aplikacyjnego (najnowsze na gorze). Filtr `level`: dokladne dopasowanie (`INFO`, `WARNING`, `ERROR`). |
| `GET` | `/api/logs/actors` | — | Zwraca posortowana liste unikalnych aktorow z audit logu: `{actors: ["admin", "konrad", "system"]}`. |
| `GET` | `/api/logs/event-types` | — | Zwraca posortowana liste unikalnych prefiksow zdarzen: `{event_types: ["auth", "config", "file", "project", "user"]}`. |

**Przyklad odpowiedzi `GET /api/logs/audit?actor=admin&event_type=config&limit=2`:**

```json
{
  "entries": [
    {
      "timestamp": "2026-02-22T14:35:18.123456+00:00",
      "event_type": "config.generated",
      "actor": "admin",
      "actor_role": "admin",
      "project": "DC_Krakow",
      "detail": {"zones": 48, "vendor": "cisco", "mode": "single"},
      "outcome": "success"
    },
    {
      "timestamp": "2026-02-22T14:30:05.654321+00:00",
      "event_type": "config.diff",
      "actor": "admin",
      "actor_role": "admin",
      "project": "DC_Krakow",
      "detail": {"added": 5, "removed": 2, "unchanged": 41, "modified": 0},
      "outcome": "success"
    }
  ],
  "total": 2
}
```

**Przyklad odpowiedzi `GET /api/logs/app?level=WARNING&limit=2`:**

```json
{
  "entries": [
    {
      "timestamp": "2026-02-22 14:36:01",
      "level": "WARNING",
      "logger": "san_zone_designer.web.routers.files",
      "message": "Validation warnings for 'DC_Krakow/initiators.yaml': ['Duplicate WWPN: 50:00:...']"
    }
  ],
  "total": 1
}
```

### Pliki logow — podsumowanie

| Plik | Format | Rozmiar rotacji | Kopie | Cel |
|------|--------|-----------------|-------|-----|
| `database/logs/san_zone_designer.log` | Tekst (linia na zdarzenie) | 5 MB | 5 | Log systemowy, debugging, ostrzerzenia |
| `database/logs/audit.log` | JSON-lines (obiekt JSON na linie) | 10 MB | 10 | Rejestr zdarzen audytowych (kto, co, kiedy, wynik) |

---

## Testy

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

**100 testow** w 8 modulach:

| Modul | Zakres |
|-------|--------|
| `test_models.py` | Walidacja WWPN, aliasow, tworzenie HBA/Target, budowanie nazw zon |
| `test_parser.py` | Parsowanie TXT/YAML, komentarze, duplikaty, normalizacja WWPN |
| `test_validator.py` | Walidacja WWPN, aliasow, detekcja duplikatow, blokowanie injection |
| `test_generators.py` | Generatory Cisco/Brocade, single/many mode, rollback, CSV |
| `test_selector.py` | Batch select, tryby single/many, kolejnosc nazw, separatory |
| `test_differ.py` | Rownowaznosc zon, compute_diff, scenariusze mixed |
| `test_importer.py` | Import Cisco show zoneset, Brocade cfgshow, komendy konfiguracyjne |
| `test_migrator.py` | Auto-detekcja host/storage, migracja TXT→YAML, detekcja typu pliku |

---

## Kolorowy output (CLI)

Output na terminalu jest kolorowany automatycznie (Rich markup):

- **Cyan (bold)** — naglowki sekcji (linie `!` z `---`)
- **Dim** — komentarze (linie `!`)
- **Green (bold)** — komendy konfiguracyjne (device-alias, zone, zonecreate itp.)
- **Yellow** — adresy WWPN

Kolorowanie jest wylaczane automatycznie gdy:
- Output idzie do pliku (`-o output.cfg`)
- Output jest pipe'owany (`| cat`)
- Uzyta flaga `--plain`

---

## Changelog

### v1.2.0
- **Zakladka Editor** — bezposrednia edycja plikow iniciatorow i targetow w GUI z walidacja w czasie rzeczywistym, auto-formatowaniem WWPN i ostrzezeniami o niezapisanych zmianach
- **Zmiana hasla** — kazdy uzytkownik moze zmienic wlasne haslo (przycisk 🔒 Password w naglowku, endpoint `PUT /api/auth/password`)
- **Pobieranie plikow** — przycisk ⬇ w Manage Files umozliwia pobranie dowolnego pliku na dysk
- **Ulepszony Manage Files** — ikony akcji (Use / Download / Delete) zamiast tekstowych przyciskow, skalowalny modal (`resize: both`)
- **Tworzenie plikow z edytora** — przycisk `+` do tworzenia nowych plikow iniciatorow/targetow bezposrednio w zakladce Editor
- **Endpoint PUT `/api/files/`** — zapis edytowanych wpisow z walidacja przez konstruktory HBA/Target i detekcja duplikatow
- **Poprawione zaleznosci** — dodano `cryptography>=41.0` (licencja Ed25519) i `pydantic>=2.0` (modele danych)
- **Responsywny interfejs** — zwijanay sidebar z animacja slide, hamburger menu, header z ikonami na mobilnych, poziomo przewijalna nawigacja zakladek
- **HTTPS / SSL** — wsparcie dla certyfikatow SSL (`--ssl-cert`, `--ssl-key`, `--ssl-key-password`) oraz samopodpisanych certyfikatow (`--ssl-self-signed`)
- **Bezpieczne ciasteczka** — `secure=True` i `samesite=strict` przy HTTPS; `samesite=lax` przy HTTP (kompatybilnosc z Safari/Chrome w dev)
- **Dynamiczna wersja** — endpoint `GET /api/version` zwraca wersje z `__version__`, wyswietlana w naglowku GUI zamiast hardcoded

### v1.1.0
- **Interfejs webowy** — FastAPI + Alpine.js SPA z ciemnym motywem
- **Uwierzytelnianie** — bcrypt, sesje, role admin/user
- **Kontrola dostepu per projekt** — non-admin widzi tylko przypisane projekty
- **Walidacja danych** — format WWPN, zakresy, duplikaty aliasow i WWPN, czerwone ostrzezenia w GUI
- **Soft-delete** — archiwizacja plikow i projektow zamiast usuwania
- **Limit uploadu** — 50 MB z chunked reading (ochrona przed DoS)
- **Audit log** — strukturalny rejestr zdarzen JSON-lines z 17 typami zdarzen, osobny plik `audit.log`
- **Zakladka Logs** — przegladanie audit logu i logu aplikacyjnego z filtrami (admin only)
- **Zakladka Configuration** — zarzadzanie licencja (admin only)
- **Logowanie** — RotatingFileHandler, logowanie wszystkich operacji
- **Auto-save** — kazda generacja/migracja/diff automatycznie zapisuje wyniki
- **Enhanced YAML** — nowe opcjonalne pola `vsan_id` i `description`
- **`migrate`** — konwersja txt na yaml z auto-detekcja host/storage_array
- **`diff`** — porownanie wygenerowanych zon z istniejaca konfiguracja switcha
- **Import zon** — parsery `show zoneset active` (Cisco) i `cfgshow` (Brocade)
- **Kolorowy output** — automatyczny Rich markup na TTY, podswietlanie skladni w GUI

### v1.0.0
- Komendy `init` (batch) i `expand` (interaktywny)
- Cisco MDS NX-OS i Brocade FOS
- Tryby `single` i `many`
- Eksport CSV i rollback
- Formaty txt i yaml

---

## Kompatybilnosc

Narzedzie produkuje output identyczny z oryginalnym skryptem `zonedesigner.sh`. Komenda `init` z tymi samymi parametrami generuje ta sama konfiguracje. Nowe funkcje (web, migrate, diff, walidacja, kolory) nie wplywaja na istniejace zachowanie.

---

## Licencja

Copyright (c) 2026 Konrad Łatkowski All Rights Reserved.

This software and associated documentation files (the "Software") are the proprietary information of Konrad Łatkowski.

You may not use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, without the express written permission of the copyright holder.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
