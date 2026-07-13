import os
from datetime import date

from dotenv import load_dotenv
load_dotenv()  # wczytuje zmienne z pliku .env, jeśli istnieje

from flask import Flask

from extensions import db, login_manager
from models import User, GameMap, MAP_POOL


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.tactics import tactics_bp
    from routes.matches import matches_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(tactics_bp)
    app.register_blueprint(matches_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
        for key in MAP_POOL:
            if not GameMap.query.filter_by(key=key).first():
                db.session.add(GameMap(key=key, display_name=key.capitalize()))
        db.session.commit()

    @app.context_processor
    def inject_globals():
        return dict(today=date.today())

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
