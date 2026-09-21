# GamePlan — panel drużyny esportowej CS2

Aplikacja Flask + PostgreSQL do zarządzania terminarzem, dostępnością graczy,
taktykami na mapy i meczami drużyny CS2.

## Funkcje

- Rejestracja / logowanie (Flask-Login, hasła hashowane).
- Dołączanie do drużyny kodem (jako gracz albo rezerwowy) lub linkiem `/j/<kod>`.
- Każdy użytkownik może należeć tylko do jednej drużyny naraz.
- **Kalendarz (14 dni do przodu)**: gracze wrzucają dostępność (dostępny/niedostępny + godziny)
  oraz dodają wydarzenia (trening / luźne granie / mecz). Najechanie kursorem na dzień
  pokazuje dostępność wszystkich graczy i rezerwowych (dostępny, niedostępny, brak informacji + godziny).
- **Taktyki**: pula map (Anubis, Ancient, Cache, Mirage, Dust2, Inferno, Nuke).
  Każdy gracz ustawia ranking map przeciąganiem (6 pkt najlepsza → 0 pkt najgorsza),
  a drużyna widzi zbiorczy ranking. Wejście w mapę pozwala opisać taktyki (tekst)
  i dodawać grafiki (callouty, nadyry itd.).
- **Mecze**: lista nadchodzących/zakończonych, dane match roomu, plan map, analiza
  przedmeczowa oraz galeria grafik (demy, staty).

## Wymagania

- Python 3.10+
- Serwer PostgreSQL

## Instalacja

```bash
cd gameplan
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Konfiguracja bazy danych (PostgreSQL + DBeaver)

1. Utwórz bazę i użytkownika w PostgreSQL, np.:

   ```sql
   CREATE USER gameplan WITH PASSWORD 'gameplan';
   CREATE DATABASE gameplan OWNER gameplan;
   ```

2. Skopiuj `.env.example` do `.env` i ustaw `DATABASE_URL`, np.:

   ```
   DATABASE_URL=postgresql+psycopg2://gameplan:gameplan@localhost:5432/gameplan
   SECRET_KEY=wygeneruj-losowy-ciag-znakow
   ```

   (Aplikacja czyta zmienne środowiskowe — możesz też ustawić je bezpośrednio w systemie
   zamiast pliku `.env`, wtedy dorzuć `python-dotenv` do wczytania albo `export` przed uruchomieniem.)

3. W **DBeaver** utwórz nowe połączenie typu PostgreSQL z tymi samymi danymi
   (host `localhost`, port `5432`, baza `gameplan`, użytkownik `gameplan`) —
   po pierwszym uruchomieniu aplikacji zobaczysz tam wszystkie tabele
   (`user`, `team`, `membership`, `availability`, `day_session`, `game_map`,
   `map_preference`, `map_tactic`, `tactic_image`, `match`, `match_image`).

## Uruchomienie

```bash
# jeśli używasz pliku .env, doładuj go np. przez:
export $(cat .env | xargs)   # Linux/Mac

python3 app.py
```

Aplikacja wystartuje na `http://localhost:5000`. Tabele i pula map
(Anubis, Ancient, Cache, Mirage, Dust2, Inferno, Nuke) tworzą się automatycznie
przy pierwszym starcie.

## Uruchomienie przez Dockera

Alternatywa dla venv + lokalnego Postgresa z sekcji wyżej — `docker-compose.yml`
stawia appkę (gunicorn) razem z jej własnym kontenerem Postgresa.

```bash
cd gameplan
cp .env.example .env
nano .env   # ustaw POSTGRES_PASSWORD, SECRET_KEY, SSO_SECRET

# sieć do komunikacji z panelem admina LoginHub (patrz README.md loginhub,
# sekcja "Podłączenie do sso_net") — utwórz raz, jeśli jeszcze nie istnieje:
docker network create sso_net

docker compose up -d --build
```

Aplikacja wystartuje na `http://localhost:5005` (wewnątrz kontenera gunicorn
słucha na `0.0.0.0:5005`, tabele i pula map tworzą się automatycznie jak wyżej).
Dane Postgresa i przesłane grafiki (`static/uploads/`) trzymane są w wolumenach
Dockera (`gameplan_pgdata`, `gameplan_uploads`), więc przeżywają restart/rebuild
kontenerów.

Kontener `web` łączy się z LoginHub przez `host.docker.internal:8011`
(`HUB_INTERNAL_URL` w `.env.example`) — działa to od razu, jeśli Hub jest
wystawiony na hoście na porcie 8011, tak jak w jego domyślnym `docker-compose.yml`.

## Struktura projektu

```
gameplan/
  Dockerfile          # obraz appki (python:3.12-slim + gunicorn)
  docker-compose.yml  # appka + kontener Postgresa
  app.py              # fabryka aplikacji, tworzenie tabel, seed map
  config.py           # konfiguracja (SECRET_KEY, DATABASE_URL)
  extensions.py       # instancje db / login_manager
  models.py           # modele SQLAlchemy
  routes/
    auth.py           # rejestracja, logowanie
    main.py           # zespół, dashboard/kalendarz
    tactics.py        # mapy, preferencje, taktyki
    matches.py        # mecze
  templates/          # szablony Jinja2
  static/css/style.css
  static/js/          # obsługa kalendarza (tooltipy, modale), drag&drop rankingu map
  static/uploads/     # przesłane grafiki (taktyki, mecze)
```

## Uwagi

- Zdjęcia (taktyki/mecze) trafiają do `static/uploads/` — w środowisku produkcyjnym
  warto podpiąć zewnętrzny storage (S3 itp.) zamiast dysku lokalnego.
- Do developmentu można tymczasowo podmienić `DATABASE_URL` na
  `sqlite:///dev.db`, jeśli nie masz pod ręką PostgreSQL — reszta kodu
  działa bez zmian (używane są wyłącznie standardowe funkcje SQLAlchemy).
#
