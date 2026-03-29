from pathlib import Path
from datetime import datetime

from flask import Flask, abort, redirect, render_template, request, url_for
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload

from models import Competition, Event, Sport, Stage, Team, Venue, db

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "events.db"


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{DATABASE_PATH.as_posix()}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)

    @app.get("/")
    def index():
        return redirect(url_for("list_events"))

    @app.get("/health")
    def health_check():
        return {"status": "ok"}, 200

    @app.get("/events")
    def list_events():
        warning = None
        selected_sport = request.args.get("sport", "").strip()
        selected_status = request.args.get("status", "").strip().lower()
        try:
            query = Event.query.options(
                joinedload(Event.competition).joinedload(Competition.sport),
                joinedload(Event.stage),
                joinedload(Event.home_team),
                joinedload(Event.away_team),
                joinedload(Event.venue),
            )

            if selected_sport:
                query = query.join(Event.competition).join(Competition.sport).filter(
                    Sport.name == selected_sport
                )
            if selected_status:
                query = query.filter(Event.status == selected_status)

            events = (
                query
                .order_by(Event.kickoff_at.asc())
                .all()
            )

            sport_options = [
                row[0]
                for row in db.session.query(Sport.name)
                .order_by(Sport.name.asc())
                .all()
            ]
            status_options = [
                row[0]
                for row in db.session.query(Event.status)
                .distinct()
                .order_by(Event.status.asc())
                .all()
            ]
        except OperationalError:
            events = []
            sport_options = []
            status_options = []
            warning = (
                "Database is not initialized yet. Run `python init_db.py` and "
                "`python seed_data.py`, then refresh this page."
            )

        return render_template(
            "events_list.html",
            events=events,
            warning=warning,
            sport_options=sport_options,
            status_options=status_options,
            selected_sport=selected_sport,
            selected_status=selected_status,
        )

    @app.get("/events/<int:event_id>")
    def event_detail(event_id: int):
        event = (
            Event.query.options(
                joinedload(Event.competition).joinedload(Competition.sport),
                joinedload(Event.stage),
                joinedload(Event.home_team),
                joinedload(Event.away_team),
                joinedload(Event.venue),
            )
            .filter(Event.id == event_id)
            .first()
        )
        if event is None:
            abort(404, description=f"Event with id {event_id} was not found.")

        return render_template("event_detail.html", event=event)

    @app.route("/events/new", methods=["GET", "POST"])
    def create_event():
        errors = []
        form_data = {
            "kickoff_at": "",
            "status": "scheduled",
            "competition_id": "",
            "stage_id": "",
            "home_team_id": "",
            "away_team_id": "",
            "venue_id": "",
            "home_goals": "",
            "away_goals": "",
            "description": "",
        }

        try:
            competitions = (
                Competition.query.options(joinedload(Competition.sport))
                .order_by(Competition.name.asc())
                .all()
            )
            stages = Stage.query.order_by(Stage.name.asc()).all()
            teams = Team.query.order_by(Team.name.asc()).all()
            venues = Venue.query.order_by(Venue.name.asc()).all()
        except OperationalError:
            return (
                render_template(
                    "event_form.html",
                    errors=["Database is not initialized yet. Run `python init_db.py` first."],
                    form=form_data,
                    competitions=[],
                    stages=[],
                    teams=[],
                    venues=[],
                    status_options=["scheduled", "live", "finished", "postponed", "cancelled"],
                ),
                503,
            )

        status_options = ["scheduled", "live", "finished", "postponed", "cancelled"]

        if request.method == "POST":
            form_data = {
                "kickoff_at": request.form.get("kickoff_at", "").strip(),
                "status": request.form.get("status", "scheduled").strip().lower(),
                "competition_id": request.form.get("competition_id", "").strip(),
                "stage_id": request.form.get("stage_id", "").strip(),
                "home_team_id": request.form.get("home_team_id", "").strip(),
                "away_team_id": request.form.get("away_team_id", "").strip(),
                "venue_id": request.form.get("venue_id", "").strip(),
                "home_goals": request.form.get("home_goals", "").strip(),
                "away_goals": request.form.get("away_goals", "").strip(),
                "description": request.form.get("description", "").strip(),
            }

            if not form_data["kickoff_at"]:
                errors.append("Kickoff date/time is required.")
            if form_data["status"] not in status_options:
                errors.append("Status is invalid.")
            if not form_data["competition_id"]:
                errors.append("Competition is required.")
            if not form_data["home_team_id"]:
                errors.append("Home team is required.")
            if not form_data["away_team_id"]:
                errors.append("Away team is required.")
            if not form_data["venue_id"]:
                errors.append("Venue is required.")

            kickoff_at = None
            if form_data["kickoff_at"]:
                try:
                    kickoff_at = datetime.fromisoformat(form_data["kickoff_at"])
                except ValueError:
                    errors.append("Kickoff date/time format is invalid.")

            def parse_id(value: str, field_name: str) -> int | None:
                if not value:
                    return None
                try:
                    return int(value)
                except ValueError:
                    errors.append(f"{field_name} must be a valid selection.")
                    return None

            competition_id = parse_id(form_data["competition_id"], "Competition")
            stage_id = parse_id(form_data["stage_id"], "Stage") if form_data["stage_id"] else None
            home_team_id = parse_id(form_data["home_team_id"], "Home team")
            away_team_id = parse_id(form_data["away_team_id"], "Away team")
            venue_id = parse_id(form_data["venue_id"], "Venue")

            if home_team_id is not None and away_team_id is not None and home_team_id == away_team_id:
                errors.append("Home team and away team must be different.")

            home_goals = None
            away_goals = None
            if form_data["home_goals"]:
                try:
                    home_goals = int(form_data["home_goals"])
                    if home_goals < 0:
                        errors.append("Home goals cannot be negative.")
                except ValueError:
                    errors.append("Home goals must be an integer.")
            if form_data["away_goals"]:
                try:
                    away_goals = int(form_data["away_goals"])
                    if away_goals < 0:
                        errors.append("Away goals cannot be negative.")
                except ValueError:
                    errors.append("Away goals must be an integer.")

            competition = db.session.get(Competition, competition_id) if competition_id else None
            stage = db.session.get(Stage, stage_id) if stage_id else None
            home_team = db.session.get(Team, home_team_id) if home_team_id else None
            away_team = db.session.get(Team, away_team_id) if away_team_id else None
            venue = db.session.get(Venue, venue_id) if venue_id else None

            if competition_id and competition is None:
                errors.append("Selected competition does not exist.")
            if stage_id and stage is None:
                errors.append("Selected stage does not exist.")
            if home_team_id and home_team is None:
                errors.append("Selected home team does not exist.")
            if away_team_id and away_team is None:
                errors.append("Selected away team does not exist.")
            if venue_id and venue is None:
                errors.append("Selected venue does not exist.")

            if not errors:
                event = Event(
                    kickoff_at=kickoff_at,
                    status=form_data["status"],
                    _competition_id=competition.id,
                    _stage_id=stage.id if stage else None,
                    _home_team_id=home_team.id,
                    _away_team_id=away_team.id,
                    _venue_id=venue.id,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    description=form_data["description"] or None,
                )
                db.session.add(event)
                db.session.commit()
                return redirect(url_for("event_detail", event_id=event.id))

        return render_template(
            "event_form.html",
            errors=errors,
            form=form_data,
            competitions=competitions,
            stages=stages,
            teams=teams,
            venues=venues,
            status_options=status_options,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
