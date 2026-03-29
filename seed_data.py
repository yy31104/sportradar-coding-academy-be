from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from init_db import create_app
from models import Competition, Event, Sport, Stage, Team, Venue, db

JSON_CANDIDATES = (
    Path("data/events.json"),
    Path("data/sportData.json"),
    Path("materials/sportData.json"),
    Path("sportData.json"),
)

STATUS_NORMALIZATION = {
    "played": "finished",
    "complete": "finished",
    "completed": "finished",
    "in_progress": "live",
    "ongoing": "live",
    "canceled": "cancelled",
}

SPORT_KEYS = ("sport", "sport_name", "sportName")
COMPETITION_KEYS = (
    "competition",
    "competition_name",
    "competitionName",
    "league",
    "originCompetitionName",
)
STAGE_KEYS = ("stage", "stage_name", "stageName", "round")
HOME_TEAM_KEYS = ("home_team", "homeTeam", "home", "team1", "participant1")
AWAY_TEAM_KEYS = ("away_team", "awayTeam", "away", "team2", "participant2")
VENUE_KEYS = ("venue", "venue_name", "venueName", "stadium")
KICKOFF_KEYS = ("kickoff_at", "kickoff", "start_time", "startTime", "scheduled", "datetime", "date_time")
HOME_GOALS_KEYS = ("home_goals", "homeGoals", "home_score", "homeScore")
AWAY_GOALS_KEYS = ("away_goals", "awayGoals", "away_score", "awayScore")

FALLBACK_EVENTS = [
    {
        "sport": "Football",
        "competition": "Premier League",
        "stage": "Matchday 30",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "venue": {"name": "Emirates Stadium", "city": "London", "country": "England"},
        "status": "scheduled",
        "kickoff_at": "2026-04-12T15:30:00Z",
        "description": "London derby weekend fixture.",
    },
    {
        "sport": "Football",
        "competition": "Bundesliga",
        "stage": "Matchday 28",
        "home_team": "Bayern Munich",
        "away_team": "Borussia Dortmund",
        "venue": {"name": "Allianz Arena", "city": "Munich", "country": "Germany"},
        "status": "finished",
        "kickoff_at": "2026-04-10T18:45:00Z",
        "home_goals": 2,
        "away_goals": 1,
        "description": "High-profile domestic rivalry match.",
    },
    {
        "sport": "Basketball",
        "competition": "NBA",
        "stage": "Regular Season",
        "home_team": "Los Angeles Lakers",
        "away_team": "Boston Celtics",
        "venue": {
            "name": "Crypto.com Arena",
            "city": "Los Angeles",
            "country": "USA",
        },
        "status": "live",
        "kickoff_at": "2026-04-08T02:00:00Z",
        "home_goals": 89,
        "away_goals": 92,
        "description": "National TV game.",
    },
    {
        "sport": "Tennis",
        "competition": "ATP Tour",
        "stage": "Quarterfinal",
        "home_team": "Novak Djokovic",
        "away_team": "Carlos Alcaraz",
        "venue": {
            "name": "Court Philippe-Chatrier",
            "city": "Paris",
            "country": "France",
        },
        "status": "scheduled",
        "kickoff_at": "2026-04-14T12:00:00Z",
        "description": "Projected marquee quarterfinal matchup.",
    },
    {
        "sport": "Football",
        "competition": "UEFA Champions League",
        "stage": None,
        "home_team": "Inter Milan",
        "away_team": "Manchester City",
        "venue": {"name": None, "city": "Milan", "country": "Italy"},
        "status": "scheduled",
        "kickoff_at": "2026-04-16T19:00:00Z",
        "description": "Stage intentionally null to validate optional stage support.",
    },
]


def first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return None


def normalize_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        nested = first_present(
            value,
            ("name", "full_name", "short_name", "title", "value"),
        )
        return normalize_name(nested)
    text = str(value).strip()
    return text or None


def infer_sport_name(raw: dict[str, Any]) -> str | None:
    sport_name = normalize_name(first_present(raw, SPORT_KEYS))
    if sport_name is not None:
        return sport_name

    if first_present(raw, ("originCompetitionName", "originCompetitionId")) is not None:
        # Assumption for official Sportradar sample: if sport is omitted, treat dataset as football.
        return "Football"
    return None


def normalize_status(raw: dict[str, Any]) -> str:
    status_raw = normalize_name(first_present(raw, ("status",))) or "scheduled"
    return STATUS_NORMALIZATION.get(status_raw.lower(), status_raw.lower())


def extract_venue_fields(raw: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    venue_value = first_present(raw, VENUE_KEYS)
    venue_name = normalize_name(venue_value)
    venue_city = None
    venue_country = None
    if isinstance(venue_value, dict):
        venue_city = normalize_name(first_present(venue_value, ("city",)))
        venue_country = normalize_name(first_present(venue_value, ("country",)))
    return venue_name, venue_city, venue_country


def build_kickoff_raw(raw: dict[str, Any]) -> Any:
    kickoff_raw = first_present(raw, KICKOFF_KEYS)
    if kickoff_raw is not None:
        return kickoff_raw

    date_venue = normalize_name(first_present(raw, ("dateVenue", "date_venue")))
    time_venue_utc = normalize_name(first_present(raw, ("timeVenueUTC", "time_venue_utc")))
    if date_venue:
        return f"{date_venue} {time_venue_utc}" if time_venue_utc else date_venue
    return None


def extract_goal_values(raw: dict[str, Any]) -> tuple[Any, Any]:
    home_goals_value = first_present(raw, HOME_GOALS_KEYS)
    away_goals_value = first_present(raw, AWAY_GOALS_KEYS)

    result_data = first_present(raw, ("result",))
    if isinstance(result_data, dict):
        if home_goals_value is None:
            home_goals_value = first_present(result_data, ("homeGoals", "home_goals"))
        if away_goals_value is None:
            away_goals_value = first_present(result_data, ("awayGoals", "away_goals"))

    return home_goals_value, away_goals_value


def parse_kickoff(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        candidate = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(candidate)
        except ValueError as exc:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(candidate, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Unsupported kickoff datetime format: {value}") from exc
    else:
        raise ValueError(f"Unsupported kickoff value type: {type(value).__name__}")

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def extract_events_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        for key in ("events", "data", "matches", "fixtures"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]

    raise ValueError("Unsupported JSON format. Expected a list or a dict with an events-like list.")


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    sport_name = infer_sport_name(raw)
    competition_name = normalize_name(first_present(raw, COMPETITION_KEYS))
    stage_name = normalize_name(first_present(raw, STAGE_KEYS))
    home_team_name = normalize_name(first_present(raw, HOME_TEAM_KEYS))
    away_team_name = normalize_name(first_present(raw, AWAY_TEAM_KEYS))

    venue_name, venue_city, venue_country = extract_venue_fields(raw)
    status = normalize_status(raw)

    kickoff_raw = build_kickoff_raw(raw)
    kickoff_at = parse_kickoff(kickoff_raw)

    home_goals_value, away_goals_value = extract_goal_values(raw)

    home_goals = parse_int_or_none(home_goals_value)
    away_goals = parse_int_or_none(away_goals_value)
    description = normalize_name(first_present(raw, ("description", "notes")))

    required_values = {
        "sport": sport_name,
        "competition": competition_name,
        "home_team": home_team_name,
        "away_team": away_team_name,
    }
    missing = [field for field, value in required_values.items() if value is None]
    if kickoff_raw is None:
        missing.append("kickoff_at")
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    if home_team_name == away_team_name:
        raise ValueError("home_team and away_team must be different")

    return {
        "sport": sport_name,
        "competition": competition_name,
        "stage": stage_name,
        "home_team": home_team_name,
        "away_team": away_team_name,
        "venue_name": venue_name,
        "venue_city": venue_city,
        "venue_country": venue_country,
        "status": status.lower(),
        "kickoff_at": kickoff_at,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "description": description,
    }


def resolve_json_path(explicit_path: str | None) -> Path | None:
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
        return path

    for candidate in JSON_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_event_rows(explicit_path: str | None) -> tuple[list[dict[str, Any]], str]:
    json_path = resolve_json_path(explicit_path)
    if json_path is None:
        return FALLBACK_EVENTS, "built-in fallback dataset"

    with json_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    rows = extract_events_payload(payload)
    if not rows:
        raise ValueError(f"No event rows found in JSON file: {json_path}")
    return rows, f"JSON file: {json_path}"


def get_or_create_sport(name: str) -> tuple[Sport, bool]:
    sport = Sport.query.filter_by(name=name).first()
    if sport:
        return sport, False
    sport = Sport(name=name)
    db.session.add(sport)
    db.session.flush()
    return sport, True


def get_or_create_competition(name: str, sport_id: int) -> tuple[Competition, bool]:
    competition = Competition.query.filter_by(name=name, _sport_id=sport_id).first()
    if competition:
        return competition, False
    competition = Competition(name=name, _sport_id=sport_id)
    db.session.add(competition)
    db.session.flush()
    return competition, True


def get_or_create_stage(name: str | None) -> tuple[Stage | None, bool]:
    if name is None:
        return None, False
    stage = Stage.query.filter_by(name=name).first()
    if stage:
        return stage, False
    stage = Stage(name=name)
    db.session.add(stage)
    db.session.flush()
    return stage, True


def get_or_create_team(name: str) -> tuple[Team, bool]:
    team = Team.query.filter_by(name=name).first()
    if team:
        return team, False
    team = Team(name=name)
    db.session.add(team)
    db.session.flush()
    return team, True


def get_or_create_venue(name: str | None, city: str | None, country: str | None) -> tuple[Venue, bool]:
    venue = Venue.query.filter_by(name=name, city=city, country=country).first()
    if venue:
        return venue, False
    venue = Venue(name=name, city=city, country=country)
    db.session.add(venue)
    db.session.flush()
    return venue, True


def upsert_event(
    competition_id: int,
    stage_id: int | None,
    home_team_id: int,
    away_team_id: int,
    venue_id: int,
    kickoff_at: datetime,
    status: str,
    home_goals: int | None,
    away_goals: int | None,
    description: str | None,
) -> bool:
    event = Event.query.filter_by(
        _competition_id=competition_id,
        _home_team_id=home_team_id,
        _away_team_id=away_team_id,
        _venue_id=venue_id,
        kickoff_at=kickoff_at,
    ).first()

    if event is None:
        db.session.add(
            Event(
                _competition_id=competition_id,
                _stage_id=stage_id,
                _home_team_id=home_team_id,
                _away_team_id=away_team_id,
                _venue_id=venue_id,
                kickoff_at=kickoff_at,
                status=status,
                home_goals=home_goals,
                away_goals=away_goals,
                description=description,
            )
        )
        return True

    event._stage_id = stage_id
    event.status = status
    event.home_goals = home_goals
    event.away_goals = away_goals
    event.description = description
    return False


def seed_database(explicit_json_path: str | None = None, app=None) -> None:
    app_obj = app or create_app()
    with app_obj.app_context():
        db.create_all()

        rows, source_label = load_event_rows(explicit_json_path)
        counters = {
            "sports_created": 0,
            "competitions_created": 0,
            "stages_created": 0,
            "teams_created": 0,
            "venues_created": 0,
            "events_created": 0,
            "events_updated": 0,
            "events_skipped": 0,
        }

        for raw in rows:
            try:
                event_data = normalize_event(raw)
            except Exception as exc:
                counters["events_skipped"] += 1
                print(f"Skipping invalid record: {exc}")
                continue

            sport, created = get_or_create_sport(event_data["sport"])
            counters["sports_created"] += int(created)

            competition, created = get_or_create_competition(event_data["competition"], sport.id)
            counters["competitions_created"] += int(created)

            stage, created = get_or_create_stage(event_data["stage"])
            counters["stages_created"] += int(created)

            home_team, created = get_or_create_team(event_data["home_team"])
            counters["teams_created"] += int(created)
            away_team, created = get_or_create_team(event_data["away_team"])
            counters["teams_created"] += int(created)

            venue, created = get_or_create_venue(
                event_data["venue_name"],
                event_data["venue_city"],
                event_data["venue_country"],
            )
            counters["venues_created"] += int(created)

            created = upsert_event(
                competition_id=competition.id,
                stage_id=stage.id if stage else None,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                venue_id=venue.id,
                kickoff_at=event_data["kickoff_at"],
                status=event_data["status"],
                home_goals=event_data["home_goals"],
                away_goals=event_data["away_goals"],
                description=event_data["description"],
            )
            counters["events_created" if created else "events_updated"] += 1

        db.session.commit()

    print(f"Seed source: {source_label}")
    print("Seed summary:")
    for key, value in counters.items():
        print(f"- {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed SQLite database with sample sports events.")
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Optional path to a JSON file containing events.",
    )
    args = parser.parse_args()
    seed_database(args.json_path)


if __name__ == "__main__":
    main()
