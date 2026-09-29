# Daladala Route and Fare Finder (Dar es Salaam)

A Django web system that helps commuters find which daladala to take between two stops,
where to change, and the total fare.

## Modules
0. Accounts: every page needs login. Sign up / log in with a phone number and password.
   Saves each person's profile, search history, saved trips and problem reports.
1. Home: search form (with stop autocomplete) and a map of all stops
2. Results: journey options, cheapest first, drawn on the map
3. Routes list and route detail (stops in order)
4. Stop detail (which routes pass a stop)
5. Feedback (report wrong or missing information)
6. Admin panel (manage stops, routes, stop order, fares, feedback) at /admin/

## How to run (Windows, in VS Code)
1. Unzip the folder and open it in VS Code: File > Open Folder > daladala_finder
2. Open the terminal: Terminal > New Terminal
3. Create a virtual environment:            python -m venv venv
4. Activate it:                              venv\Scripts\activate
   (If PowerShell blocks it, run: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)
5. Install Django:                           pip install -r requirements.txt
6. Create the database tables:               python manage.py migrate
7. Load the sample stops and routes:         python manage.py load_sample_data
8. Create your admin account:                python manage.py createsuperuser
9. Start the server:                         python manage.py runserver
10. Open http://127.0.0.1:8000 (site) and http://127.0.0.1:8000/admin (admin panel)

On macOS/Linux use `python3` and `source venv/bin/activate` instead.

Run the automated tests any time with:      python manage.py test routes

## Project structure
```
daladala_finder/            project settings and main urls
routes/
  models.py                 Stop, Route, RouteStop, Fare, Feedback (database tables)
  services/route_finder.py  the route-finding algorithm (BFS by number of transfers)
  views.py                  one view per module
  forms.py                  search and feedback forms
  urls.py                   page addresses
  admin.py                  admin panel setup
  templates/routes/         HTML pages
  static/routes/            CSS and JavaScript (Leaflet map helper)
  management/commands/load_sample_data.py   sample data loader
  tests.py                  automated tests
```

## IMPORTANT: sample data
The stops, coordinates and fares in `load_sample_data.py` are APPROXIMATE EXAMPLES so you can
test the system. Replace them with the data you collect in the field and LATRA's official fares.

## Next steps
- Import your field data from Excel (pandas/openpyxl script)
- Real road paths on the map using OSRM
- SMS/USSD search with Africa's Talking

## Languages (English / Kiswahili)
- The site opens in the browser's language (Swahili phones get Swahili, everyone else English).
  The **EN | SW** switch in the header changes it and is remembered.
- All Swahili text is in `locale/sw/LC_MESSAGES/django.po`. To change a translation, edit the
  `msgstr` line, then run `python manage.py compilemessages` (needs gettext: `brew install gettext`).
  Commit both `django.po` and `django.mo`, so the server does not need gettext.
- After adding new text to a page: wrap it in `{% translate "..." %}` (templates) or `_("...")`
  (Python), run `python manage.py makemessages -l sw --ignore=venv`, translate the empty `msgstr`, and compile.
- Words on the map (location button, pins) come from `window.DALADALA_TEXT` in `base.html`.
- The admin panel stays in English, with Django's own Swahili for its built-in words.

## Map
The maps use Leaflet (bundled in `routes/static/routes/vendor/leaflet`) with free
OpenStreetMap tiles. No API key or account is needed.
OpenStreetMap blocks sites that do not send their address with tile requests, so keep
`SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"` in `settings.py`.
Their free servers are for light use: fine for development and a student project.

### Route lines follow the roads
Route lines on the map follow the real roads. The road path between each pair of
neighbouring stops comes from OSRM (free, open-source routing on OpenStreetMap data,
no key needed) and is saved in the `RoadSegment` table, so it is downloaded only once.
- `run_mac.sh` downloads them automatically, or run: `python manage.py fetch_road_paths`
- After moving stops or changing routes: `python manage.py fetch_road_paths --refresh`
- If OSRM cannot be reached, the map draws straight lines and tries again later.
- The public OSRM server is a free demo for light use, fine for this project. For a real
  launch, run your own OSRM server or use a paid routing service.


## Login and user data
- Everyone must log in before using the site (Django's `LoginRequiredMiddleware`).
  Only the Log in, Sign up and admin login pages are open.
- People sign up with **full name, phone number and password** (email and home area optional).
  Phone numbers are stored as `+255XXXXXXXXX`, so `0712 345 678`, `712345678` and `+255712345678` all work.
- Passwords are stored as secure hashes (Django's default), never as plain text.
- Saved for each person (app `accounts`):
  - `Profile`: full name, home area
  - `SearchHistory`: every trip they searched (shown on **My trips**, can be cleared)
  - `SavedTrip`: trips they starred with **Save trip** (shown on the home page and My trips, can be renamed)
  - `Feedback.user`: the problems they reported
- Admin account: `python manage.py createsuperuser` and use a phone number like `+255712345678` as the username.
  In the admin panel you can see users, profiles, search history and saved trips.

## Databases
| Where | Database | How |
|-------|----------|-----|
| Development (your laptop) | SQLite (`db.sqlite3`) | Nothing to set up. Used when `DATABASE_URL` is not set. |
| Deployment (server) | PostgreSQL | Set `DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/NAME` |

### PostgreSQL on this Mac (Postgres.app 18)
This laptop uses PostgreSQL through **Postgres.app** (keep the app running, elephant icon in the menu bar).
- Database `daladala`, login `daladala`, on `localhost:5432`.
- The connection is in the file `.env` next to `manage.py` (`DATABASE_URL=...`). Django reads it
  automatically. It holds the database password, so it is in `.gitignore`: never upload it.
- To go back to SQLite, delete or comment out the `DATABASE_URL` line in `.env`.
- Open the database directly: `/Applications/Postgres.app/Contents/Versions/18/bin/psql -h localhost -U daladala daladala`

Test the project on PostgreSQL on your laptop (optional):
```
pip install -r requirements-prod.txt
export DATABASE_URL=postgres://daladala:password@localhost:5432/daladala
python manage.py migrate
python manage.py test
```

Move your data from SQLite to PostgreSQL:
```
# 1. with SQLite (DATABASE_URL not set): make a backup file
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e admin.logentry -e sessions -o backup.json
# 2. with PostgreSQL (DATABASE_URL set): create the tables and load the backup
python manage.py migrate
python manage.py loaddata backup.json
```

## Deployment: put the site online (free: Render + Neon)
The project is ready for Render.com (web server) with a Neon.tech PostgreSQL database.
Files used: `render.yaml` (settings for Render) and `build.sh` (runs on every deploy).

1. **GitHub**: put the project in a GitHub repository (VS Code: Source Control > Publish to GitHub).
   `db.sqlite3`, `venv/` and secrets are not uploaded (see `.gitignore`).
2. **Neon** (neon.tech, free, no card): create a project, region *AWS Europe (Frankfurt)*.
   Copy the connection string (`postgresql://...neon.tech/neondb?sslmode=require`).
3. **Render** (render.com, free, no card): New > Blueprint > choose your GitHub repository.
   Fill in:
   - `DATABASE_URL`: the Neon connection string
   - `DJANGO_SUPERUSER_USERNAME`: your phone number as `+255712345678` (admin login)
   - `DJANGO_SUPERUSER_PASSWORD`: a strong password for the admin panel
4. Click **Apply**. After a few minutes the site is live at `https://daladala-finder.onrender.com`
   (or similar). Every `git push` deploys the new version automatically.

Notes about the free plans:
- Render free: the site sleeps after 15 minutes without visitors; the next visit takes about 1 minute to wake it.
- Neon free: 0.5 GB of data (plenty for this project) and it does not expire.
- `build.sh` loads the sample routes only on the first deploy, and creates the admin only once.
