# Database design

[models.py](../models.py) defines six tables. [erd.mmd](erd.mmd) shows their relationships.

| Table | Fields and relationships |
| --- | --- |
| `sports` | Unique sport name; referenced by competitions |
| `competitions` | Name and required `_sport_id`; referenced by events |
| `stages` | Unique name; an event can omit its stage |
| `teams` | Unique name; referenced independently as home and away team |
| `venues` | Optional name, city, and country; referenced by events |
| `events` | Kickoff, status, optional scores/description, and relationship IDs |

Event foreign keys are `_competition_id`, `_home_team_id`, `_away_team_id`, `_venue_id`, and optional `_stage_id`. Competition's sport key is `_sport_id`.

## Checks and indexes

- The home and away team IDs must differ.
- Each score is either NULL or non-negative.
- Event indexes cover `kickoff_at` and `(status, kickoff_at)`.
- Relationship ID columns are indexed.
- `status` has the SQLAlchemy default `scheduled`; its database column default is unset.

Names shared across fixtures stay in the referenced tables. Stage and venue details can remain incomplete while an event still has its required relationships.

## Application behavior

[app.py](../app.py) loads competition/sport, stage, teams, and venue with `joinedload` before rendering list/detail pages. Filters use sport name and event status; the list sorts by ascending kickoff time.

Create/edit forms share validation for relationship IDs, date/time, distinct teams, paired scores, and status consistency. Kickoff values are treated as UTC. [tests/test_app.py](../tests/test_app.py) exercises routes, form rules, database checks, and repeated seed runs.

[init_db.py](../init_db.py) creates the schema in `instance/events.db`. [seed_data.py](../seed_data.py) normalizes supported local JSON fields or loads its built-in sample fixtures, reusing matching records on later runs.
