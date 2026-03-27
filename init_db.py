from pathlib import Path

from flask import Flask

from models import db

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "events.db"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH.as_posix()}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def initialize_database() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    app = create_app()

    with app.app_context():
        db.create_all()

    print(f"Database initialized: {DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()
