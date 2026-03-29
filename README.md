# Sportradar Coding Academy 2026 BE Assignment

Simple sports event calendar web app built with Flask, SQLite, SQLAlchemy, and Jinja templates.

## Project Overview

This project implements a minimal backend-first sports event calendar that supports:

- listing events
- viewing one event
- adding a new event

The focus is on clear relational modeling, efficient event queries, and simple interview-friendly code.

## Features Implemented

- Relational schema design with normalized entities (`sports`, `competitions`, `stages`, `teams`, `venues`, `events`)
- ERD documentation in:
  - `docs/ERD.md`
  - `docs/erd.mmd`
- SQLite + SQLAlchemy models and relationships
- Database initialization script
- Seed script with:
  - optional JSON import support (if a local JSON file is available)
  - built-in fallback sample dataset for demo use
- Event list page (`GET /events`) with eager loading and kickoff-time sorting
- Event detail page (`GET /events/<id>`)
- Event creation page (`GET/POST /events/new`) with simple validation
- Shared base template and consistent navigation

## Tech Stack

- Python
- Flask
- SQLite
- SQLAlchemy / Flask-SQLAlchemy
- Jinja templates

## Project Structure

```text
.
|-- app.py
|-- models.py
|-- init_db.py
|-- seed_data.py
|-- requirements.txt
|-- docs/
|   |-- ERD.md
|   `-- erd.mmd
|-- templates/
|   |-- base.html
|   |-- events_list.html
|   |-- event_detail.html
|   `-- event_form.html
`-- materials/
    `-- assignment source PDFs
```

## Database Design Summary

Main tables:

- `sports`
- `competitions` (FK `_sport_id`)
- `stages`
- `teams`
- `venues`
- `events` (FKs: `_competition_id`, `_stage_id`, `_home_team_id`, `_away_team_id`, `_venue_id`)

Design notes:

- All FK columns use the required underscore prefix.
- `events` stores references, not redundant competition/stage names.
- `events._stage_id` is nullable (stage optional).
- `venues.name` is nullable.
- `events.home_goals`, `events.away_goals`, `events.description` are nullable.
- `events` has:
  - index on `kickoff_at` (sorting/filtering support)
  - check constraint to prevent same home/away team

## Setup Instructions

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Database Initialization

Create SQLite database and tables:

```powershell
python init_db.py
```

This creates `instance/events.db`.

## Seed Sample Data

Load sample data:

```powershell
python seed_data.py
```

Optional JSON path:

```powershell
python seed_data.py --json path\to\events.json
```

Fallback behavior:

- If no usable local JSON is found, the script uses a built-in sample dataset.
- Seed script is designed to be practical for repeated runs (updates existing matching events rather than duplicating them in normal usage).

## Run Locally

```powershell
python app.py
```

Open in browser:

- `http://127.0.0.1:5000/events`

## Run Tests

```powershell
python -m unittest -v tests.test_app
```

or:

```powershell
python -m unittest discover -s tests -v
```

## Main Routes

- `GET /`  
  Redirects to `/events`

- `GET /health`  
  Basic health check

- `GET /events`  
  Event list page (ordered by kickoff time).  
  Uses eager loading (`joinedload`) to avoid N+1 query issues.

- `GET /events/<event_id>`  
  Single event detail page.  
  Returns 404 if event is missing.

- `GET /events/new`  
  Event creation form page.

- `POST /events/new`  
  Creates a new event and redirects to detail page on success.

## Assumptions and Key Decisions

- Current event model is two-sided (`home_team` vs `away_team`) for simplicity.
- Stage is optional on event creation.
- Form validation is intentionally simple and server-side:
  - required relationship fields
  - valid IDs
  - different home/away teams
  - valid datetime and non-negative integer scores
- Query efficiency was prioritized for event listing and detail rendering through relationship eager loading.
- UI is intentionally minimal to keep the implementation easy to explain in an interview.
