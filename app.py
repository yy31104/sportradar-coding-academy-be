from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get('/health')
    def health_check():
        return {'status': 'ok'}, 200

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
