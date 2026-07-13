import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-zmien-mnie-w-produkcji')

    # Baza danych - PostgreSQL (podglądana np. w DBeaver)
    # Ustaw zmienną środowiskową DATABASE_URL albo edytuj wartość domyślną poniżej.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql+psycopg2://gameplan:gameplan@localhost:5432/gameplan'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB na plik
