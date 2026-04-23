import json
import tempfile
import unittest
from datetime import datetime, timedelta
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
                "kickoff_at": self._datetime_local_from_now(timedelta(days=1)),
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

    def _datetime_local_from_now(self, delta: timedelta) -> str:
        dt = datetime.utcnow() + delta
        dt = dt.replace(second=0, microsecond=0)
        return dt.strftime("%Y-%m-%dT%H:%M")

    def _seed_from_json_payload(self, payload: dict) -> None:
        json_path = Path(self.temp_dir.name) / "official_events.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            seed_database(explicit_json_path=str(json_path), app=self.app)

    def test_get_events_returns_200(self):
        response = self.client.get("/events")
        self.assertEqual(response.status_code, 200)

    def test_get_events_filter_by_sport_returns_matching_rows(self):
        response = self.client.get("/events?sport=Football")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Premier League", html)
        self.assertIn("Bundesliga", html)
        self.assertNotIn("NBA", html)
        self.assertNotIn("ATP Tour", html)
        self.assertIn('value="Football" selected', html)

    def test_get_events_filter_by_status_returns_matching_rows(self):
        response = self.client.get("/events?status=live")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("NBA", html)
        self.assertNotIn("Premier League", html)
        self.assertNotIn("Bundesliga", html)
        self.assertIn('value="live" selected', html)

    def test_get_events_filter_by_sport_and_status_supports_combined_filters(self):
        response = self.client.get("/events?sport=Football&status=finished")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Bundesliga", html)
        self.assertNotIn("Premier League", html)
        self.assertNotIn("NBA", html)
        self.assertIn('value="Football" selected', html)
        self.assertIn('value="finished" selected', html)

    def test_get_events_filtered_empty_state_is_helpful(self):
        response = self.client.get("/events?sport=Tennis&status=finished")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No events found.", html)
        self.assertIn("Try adjusting filters", html)

    def test_get_existing_event_returns_200(self):
        event_id = self._first_event_id()
        response = self.client.get(f"/events/{event_id}")
        self.assertEqual(response.status_code, 200)

    def test_get_missing_event_returns_404(self):
        response = self.client.get("/events/999999")
        self.assertEqual(response.status_code, 404)

    def test_get_edit_existing_event_returns_200_with_prefilled_values(self):
        event_id = self._first_event_id()
        with self.app.app_context():
            event = db.session.get(Event, event_id)
            kickoff_value = event.kickoff_at.strftime("%Y-%m-%dT%H:%M")

        response = self.client.get(f"/events/{event_id}/edit")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Edit Event", html)
        self.assertIn(kickoff_value, html)

    def test_get_missing_edit_event_returns_404(self):
        response = self.client.get("/events/999999/edit")
        self.assertEqual(response.status_code, 404)

    def test_post_missing_edit_event_returns_404(self):
        payload = self._form_base_payload()
        response = self.client.post("/events/999999/edit", data=payload, follow_redirects=False)
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

    def test_valid_event_edit_updates_event_and_redirects(self):
        event_id = self._first_event_id()
        payload = self._form_base_payload()
        payload["description"] = "edited event description"
        payload["status"] = "scheduled"
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(days=2))

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post(f"/events/{event_id}/edit", data=payload, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/events/{event_id}", response.headers.get("Location", ""))

        with self.app.app_context():
            after_count = Event.query.count()
            updated = db.session.get(Event, event_id)
        self.assertEqual(after_count, before_count)
        self.assertEqual(updated.description, "edited event description")
        self.assertEqual(updated.status, "scheduled")

    def test_delete_event_removes_record_and_redirects_to_events_list(self):
        event_id = self._first_event_id()
        with self.app.app_context():
            before_count = Event.query.count()
            remaining_event = Event.query.order_by(Event.id.desc()).first()
            remaining_event_id = remaining_event.id

        response = self.client.post(f"/events/{event_id}/delete", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/events", response.headers.get("Location", ""))

        with self.app.app_context():
            after_count = Event.query.count()
            deleted = db.session.get(Event, event_id)
            still_exists = db.session.get(Event, remaining_event_id)
        self.assertEqual(after_count, before_count - 1)
        self.assertIsNone(deleted)
        self.assertIsNotNone(still_exists)

    def test_delete_missing_event_returns_404(self):
        response = self.client.post("/events/999999/delete", follow_redirects=False)
        self.assertEqual(response.status_code, 404)

    def test_get_delete_route_returns_405(self):
        event_id = self._first_event_id()
        response = self.client.get(f"/events/{event_id}/delete")
        self.assertEqual(response.status_code, 405)

    def test_invalid_edit_same_home_away_shows_validation_and_does_not_update(self):
        event_id = self._first_event_id()
        payload = self._form_base_payload()
        payload["away_team_id"] = payload["home_team_id"]
        payload["description"] = "should not be saved"

        with self.app.app_context():
            before = db.session.get(Event, event_id)
            before_home_team_id = before._home_team_id
            before_away_team_id = before._away_team_id
            before_description = before.description

        response = self.client.post(f"/events/{event_id}/edit", data=payload, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("must be different", response.get_data(as_text=True))

        with self.app.app_context():
            after = db.session.get(Event, event_id)
        self.assertEqual(after._home_team_id, before_home_team_id)
        self.assertEqual(after._away_team_id, before_away_team_id)
        self.assertEqual(after.description, before_description)

    def test_invalid_edit_finished_in_future_shows_validation_and_does_not_update(self):
        event_id = self._first_event_id()
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(hours=3))
        payload["status"] = "finished"
        payload["home_goals"] = "1"
        payload["away_goals"] = "0"
        payload["description"] = "should not save"

        with self.app.app_context():
            before = db.session.get(Event, event_id)
            before_status = before.status
            before_description = before.description

        response = self.client.post(f"/events/{event_id}/edit", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("A finished event cannot have a future kickoff date/time.", html)

        with self.app.app_context():
            after = db.session.get(Event, event_id)
        self.assertEqual(after.status, before_status)
        self.assertEqual(after.description, before_description)

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

    def test_invalid_scheduled_in_past_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(hours=-1))
        payload["status"] = "scheduled"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("A scheduled event must have a future kickoff date/time.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_finished_in_future_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(hours=2))
        payload["status"] = "finished"
        payload["home_goals"] = "1"
        payload["away_goals"] = "0"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("A finished event cannot have a future kickoff date/time.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_finished_without_scores_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(hours=-1))
        payload["status"] = "finished"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Finished events must include both home and away goals.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_scheduled_with_scores_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(hours=2))
        payload["status"] = "scheduled"
        payload["home_goals"] = "2"
        payload["away_goals"] = "1"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Scheduled events should not include scores.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_live_too_far_in_past_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(hours=-5))
        payload["status"] = "live"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("A live event cannot be too far in the past.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_live_too_far_in_future_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(hours=1))
        payload["status"] = "live"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("A live event cannot be too far in the future.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_one_sided_score_pair_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(days=1))
        payload["status"] = "scheduled"
        payload["home_goals"] = "1"
        payload["away_goals"] = ""

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Scores must include both home and away goals, or neither.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_postponed_with_scores_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(days=1))
        payload["status"] = "postponed"
        payload["home_goals"] = "1"
        payload["away_goals"] = "1"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Postponed events should not include scores.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

    def test_invalid_cancelled_with_scores_shows_validation_error(self):
        payload = self._form_base_payload()
        payload["kickoff_at"] = self._datetime_local_from_now(timedelta(days=1))
        payload["status"] = "cancelled"
        payload["home_goals"] = "2"
        payload["away_goals"] = "0"

        with self.app.app_context():
            before_count = Event.query.count()

        response = self.client.post("/events/new", data=payload, follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Cancelled events should not include scores.", html)

        with self.app.app_context():
            after_count = Event.query.count()
        self.assertEqual(after_count, before_count)

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

    def test_negative_home_goals_rule_enforced_by_db(self):
        payload = self._form_base_payload()
        with self.app.app_context():
            competition_id = int(payload["competition_id"])
            home_team_id = int(payload["home_team_id"])
            away_team_id = int(payload["away_team_id"])
            venue_id = int(payload["venue_id"])

            bad_event = Event(
                kickoff_at=Event.query.order_by(Event.id.desc()).first().kickoff_at,
                status="finished",
                _competition_id=competition_id,
                _stage_id=None,
                _home_team_id=home_team_id,
                _away_team_id=away_team_id,
                _venue_id=venue_id,
                home_goals=-1,
                away_goals=0,
            )
            db.session.add(bad_event)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_official_sportradar_json_mapping_is_supported(self):
        sample_payload = {
            "data": [
                {
                    "season": 2024,
                    "status": "played",
                    "timeVenueUTC": "00:00:00",
                    "dateVenue": "2024-01-03",
                    "stadium": None,
                    "homeTeam": {"name": "Al Shabab"},
                    "awayTeam": {"name": "Nasaf"},
                    "result": {"homeGoals": 1, "awayGoals": 2},
                    "stage": {"id": "ROUND OF 16", "name": "ROUND OF 16"},
                    "originCompetitionId": "afc-champions-league",
                    "originCompetitionName": "AFC Champions League",
                },
                {
                    "season": 2024,
                    "status": "scheduled",
                    "timeVenueUTC": "00:00:00",
                    "dateVenue": "2024-01-19",
                    "stadium": None,
                    "homeTeam": None,
                    "awayTeam": {"name": "Urawa Reds"},
                    "result": None,
                    "stage": {"id": "FINAL", "name": "FINAL"},
                    "originCompetitionId": "afc-champions-league",
                    "originCompetitionName": "AFC Champions League",
                },
            ]
        }

        self._seed_from_json_payload(sample_payload)

        with self.app.app_context():
            events = Event.query.order_by(Event.id.asc()).all()
            self.assertEqual(len(events), 1)

            event = events[0]
            self.assertEqual(event.status, "finished")
            self.assertEqual(event.home_goals, 1)
            self.assertEqual(event.away_goals, 2)
            self.assertEqual(event.competition.name, "AFC Champions League")
            self.assertEqual(event.stage.name, "ROUND OF 16")
            self.assertEqual(event.home_team.name, "Al Shabab")
            self.assertEqual(event.away_team.name, "Nasaf")
            self.assertEqual(event.competition.sport.name, "Football")
            self.assertEqual(event.kickoff_at.strftime("%Y-%m-%d %H:%M:%S"), "2024-01-03 00:00:00")
            self.assertIsNone(event.venue.name)


if __name__ == "__main__":
    unittest.main()
