from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index

db = SQLAlchemy()


class Sport(db.Model):
    __tablename__ = "sports"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    competitions = db.relationship("Competition", back_populates="sport")


class Competition(db.Model):
    __tablename__ = "competitions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    _sport_id = db.Column(
        db.Integer, db.ForeignKey("sports.id"), nullable=False, index=True
    )

    sport = db.relationship("Sport", back_populates="competitions")
    events = db.relationship("Event", back_populates="competition")


class Stage(db.Model):
    __tablename__ = "stages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    events = db.relationship("Event", back_populates="stage")


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, unique=True)

    home_events = db.relationship(
        "Event",
        foreign_keys="Event._home_team_id",
        back_populates="home_team",
    )
    away_events = db.relationship(
        "Event",
        foreign_keys="Event._away_team_id",
        back_populates="away_team",
    )


class Venue(db.Model):
    __tablename__ = "venues"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(120), nullable=True)

    events = db.relationship("Event", back_populates="venue")


class Event(db.Model):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "_home_team_id <> _away_team_id",
            name="ck_events_home_away_different",
        ),
        CheckConstraint(
            "(home_goals IS NULL OR home_goals >= 0)",
            name="ck_events_home_goals_non_negative",
        ),
        CheckConstraint(
            "(away_goals IS NULL OR away_goals >= 0)",
            name="ck_events_away_goals_non_negative",
        ),
        Index("ix_events_kickoff_at", "kickoff_at"),
        Index("ix_events_status_kickoff_at", "status", "kickoff_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    kickoff_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(60), nullable=False, default="scheduled")
    home_goals = db.Column(db.Integer, nullable=True)
    away_goals = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)

    _competition_id = db.Column(
        db.Integer, db.ForeignKey("competitions.id"), nullable=False, index=True
    )
    _stage_id = db.Column(db.Integer, db.ForeignKey("stages.id"), nullable=True, index=True)
    _home_team_id = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True
    )
    _away_team_id = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True
    )
    _venue_id = db.Column(db.Integer, db.ForeignKey("venues.id"), nullable=False, index=True)

    competition = db.relationship("Competition", back_populates="events")
    stage = db.relationship("Stage", back_populates="events")
    home_team = db.relationship(
        "Team",
        foreign_keys=[_home_team_id],
        back_populates="home_events",
    )
    away_team = db.relationship(
        "Team",
        foreign_keys=[_away_team_id],
        back_populates="away_events",
    )
    venue = db.relationship("Venue", back_populates="events")
