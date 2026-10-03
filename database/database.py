from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Ścieżka do pliku bazy danych SQLite (stworzy plik sql_app.db)
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/sql_app.db"

# check_same_thread=False jest wymagane tylko dla SQLite w połączeniu z FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency (zależność) do pobierania sesji bazy danych w endpointach
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()