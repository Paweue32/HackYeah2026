from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

DB_FILE = "./database/sql_app.db"

# Deletes the db file if it exists
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

# Path to the SQLite database file (creates sql_app.db)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_FILE}"

# check_same_thread=False is required only for SQLite when used with FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# # Dependency for getting a database session in endpoints
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()