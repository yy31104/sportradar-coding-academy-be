# Sports Event Calendar

A Flask and SQLite calendar for creating, editing, and filtering sports fixtures. Events share competition, team, stage, and venue records; the list sorts by kickoff time.

Backend coding-academy exercise, with its original reflection retained in docs. Built with AI assistance.

![Sports event list with sport and status filters](docs/images/events.png)

The local app showing its built-in sample dataset.

## Run it

Requires Python 3.12. On macOS or Linux:

```bash
git clone https://github.com/yy31104/sportradar-coding-academy-be.git
cd sportradar-coding-academy-be
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python init_db.py
.venv/bin/python seed_data.py
.venv/bin/python app.py
```

Open [127.0.0.1:5000/events](http://127.0.0.1:5000/events) to filter fixtures or choose Add Event. The ignored `instance/events.db` holds local data.

On Windows, use `.venv\Scripts\python.exe` for the commands after environment creation.

Tests take about a second after installation; run them in another terminal while the app is open:

```bash
.venv/bin/python -m unittest -v tests.test_app
```

[app.py](app.py) uses the same validation for creation and editing, checking kickoff time, status, teams, and paired scores. [models.py](models.py) also rejects identical home/away teams and negative scores at the database level.

The event queries load related records together with `joinedload`, trading a larger query for fewer lookups while rendering the list. The [seed loader](seed_data.py) reuses matching records on repeated imports.

This local demo lets visitors edit and delete events. Kickoff times display as UTC, and the built-in fixtures use fixed sample dates.

For the schema and assignment background, see the [database design](docs/ERD.md), [Mermaid diagram](docs/erd.mmd), and [reflection](docs/AI_Reflection.txt).
