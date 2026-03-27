from pathlib import Path

from flask import Flask, abort, redirect, render_template, url_for
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload

from models import Competition, Event, db

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "events.db"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH.as_posix()}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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
        try:
            events = (
                Event.query.options(
                    joinedload(Event.competition).joinedload(Competition.sport),
                    joinedload(Event.stage),
                    joinedload(Event.home_team),
                    joinedload(Event.away_team),
                    joinedload(Event.venue),
                )
                .order_by(Event.kickoff_at.asc())
                .all()
            )
        except OperationalError:
            events = []
            warning = (
                "Database is not initialized yet. Run `python init_db.py` and "
                "`python seed_data.py`, then refresh this page."
            )

        return render_template("events_list.html", events=events, warning=warning)

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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
