# Sports Event Calendar Database Design

## Scope of this step
This document materializes the database design before model implementation.

- No SQLAlchemy models are implemented in this step.
- No DB initialization is implemented in this step.
- No routes are implemented in this step.

## Source data check (sample JSON)
I inspected the repository materials before finalizing the schema:

- `materials/DATA. JSON file.pdf`
- `materials/Sportradar Coding Academy BE.pdf`
- `materials/Warsaw Sportradar&#39_s Coding Academy 2026.pdf`

In the current repository, there is no directly readable `*.json` file yet.  
`DATA. JSON file.pdf` metadata indicates a source named `sportData.json`, but field-level JSON structure is not directly extractable from available local tools.  
Because of that, the schema below keeps the approved simple lookup-based `stages` design for now.

## Finalized normalized schema

All foreign key columns follow the required underscore prefix convention:

- `_sport_id`
- `_competition_id`
- `_stage_id`
- `_home_team_id`
- `_away_team_id`
- `_venue_id`

### 1) `sports`
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL UNIQUE

### 2) `competitions`
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL
- `_sport_id` INTEGER NOT NULL FK -> `sports.id`

### 3) `stages`
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL UNIQUE

### 4) `teams`
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL UNIQUE

### 5) `venues`
- `id` INTEGER PRIMARY KEY
- `name` TEXT NULL
- `city` TEXT NULL
- `country` TEXT NULL

### 6) `events`
- `id` INTEGER PRIMARY KEY
- `kickoff_at` DATETIME NOT NULL
- `status` TEXT NOT NULL DEFAULT `'scheduled'`
- `home_goals` INTEGER NULL
- `away_goals` INTEGER NULL
- `description` TEXT NULL
- `_competition_id` INTEGER NOT NULL FK -> `competitions.id`
- `_stage_id` INTEGER NULL FK -> `stages.id`
- `_home_team_id` INTEGER NOT NULL FK -> `teams.id`
- `_away_team_id` INTEGER NOT NULL FK -> `teams.id`
- `_venue_id` INTEGER NOT NULL FK -> `venues.id`

Recommended integrity constraints:

- CHECK `_home_team_id <> _away_team_id`
- Index on `events.kickoff_at` for calendar sorting/filtering

## Relationships
- One `sport` has many `competitions`
- One `competition` has many `events`
- One `stage` can be used by many `events` (optional on event)
- One `team` appears in many events as home or away
- One `venue` hosts many events

See Mermaid ERD: `docs/erd.mmd`.

## Why this schema is close to 3NF
- Lookup entities (`sports`, `competitions`, `stages`, `teams`, `venues`) are separated from `events`.
- `events` stores only event-specific attributes and foreign keys to related entities.
- This avoids redundant attributes like `competition_name` or `stage_name` repeated per event row.
- Non-key attributes depend on the key of their own table, minimizing update anomalies.

## Performance note for later route implementation
When implementing `GET /events`, avoid N+1 queries:

- Use SQLAlchemy eager loading with `.options(joinedload(...))`
- Do not run SQL queries inside loops

## Planned future check
If later JSON parsing clearly shows stage values are competition-specific, revise `stages` to include `_competition_id` in a later step.
