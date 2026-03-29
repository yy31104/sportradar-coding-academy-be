import tempfile
import unittest
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from app import create_app
from models import Competition, Event, Team, Venue, db
from seed_data import seed_database


class EventAppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(cls.temp_dir.name) / "test_events.db"
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            }
        )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            seed_database(app=self.app)

    def _first_event_id(self) -> int:
        with self.app.app_context():
            event = Event.query.order_by(Event.id.asc()).first()
            self.assertIsNotNone(event)
            return event.id

    def _form_base_payload(self) -> dict:
        with self.app.app_context():
            competition = Competition.query.order_by(Competition.id.asc()).first()
            teams = Team.query.order_by(Team.id.asc()).limit(2).all()
            venue = Venue.query.order_by(Venue.id.asc()).first()

            self.assertIsNotNone(competition)
            self.assertEqual(len(teams), 2)
            self.assertIsNotNone(venue)

            return {
                "kickoff_at": "2026-06-01T19:30",
                "status": "scheduled",
                "competition_id": str(competition.id),
                "stage_id": "",
                "home_team_id": str(teams[0].id),
                "away_team_id": str(teams[1].id),
                "venue_id": str(venue.id),
                "home_goals": "",
                "away_goals": "",
                "description": "test-created event",
            }

    def test_get_events_returns_200(self):
        response = self.client.get("/events")
        self.assertEqual(response.status_code, 200)

    def test_get_existing_event_returns_200(self):
        event_id = self._first_event_id()
        response = self.client.get(f"/events/{event_id}")
        self.assertEqual(response.status_code, 200)

    def test_get_missing_event_returns_404(self):
        response = self.client.get("/events/999999")
        self.assertEqual(response.status_code, 404)

    def test_valid_event_creation_creates_new_event_and_redirects(self):
        payload = self._form_base_payload()
        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        location = response.headers.get("Location", "")
        self.assertIn("/events/", location)

        with self.app.app_context():
            after_count = Event.query.count()
            created_event_id = int(location.rstrip("/").split("/")[-1])
            created_event = db.session.get(Event, created_event_id)
        self.assertEqual(after_count, before_count + 1)
        self.assertIsNotNone(created_event)
        self.assertEqual(created_event.description, "test-created event")

    def test_invalid_same_home_away_shows_validation_and_does_not_create(self):
        payload = self._form_base_payload()
        payload["away_team_id"] = payload["home_team_id"]

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("must be different", response.get_data(as_text=True))

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_missing_required_fields_shows_validation_error(self):
        response = self.client.post("/events/new", data={}, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Kickoff date/time is required.", html)
        self.assertIn("Competition is required.", html)
        self.assertIn("Home team is required.", html)
        self.assertIn("Away team is required.", html)
        self.assertIn("Venue is required.", html)

    def test_repeated_seed_does_not_duplicate_events_in_normal_use(self):
        with self.app.app_context():
            initial_count = Event.query.count()
            seed_database(app=self.app)
            repeated_count = Event.query.count()
        self.assertEqual(initial_count, repeated_count)

    def test_home_team_cannot_equal_away_team_rule_enforced_by_db(self):
        payload = self._form_base_payload()
        with self.app.app_context():
            home_team_id = int(payload["home_team_id"])
            competition_id = int(payload["competition_id"])
            venue_id = int(payload["venue_id"])

            bad_event = Event(
                kickoff_at=Event.query.order_by(Event.id.desc()).first().kickoff_at,
                status="scheduled",
                _competition_id=competition_id,
                _stage_id=None,
                _home_team_id=home_team_id,
                _away_team_id=home_team_id,
                _venue_id=venue_id,
            )
            db.session.add(bad_event)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
