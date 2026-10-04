import sqlite3

DB_PATH = 'hackathon_map.db'


def create_database(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # node_id is a string with coordinates like "52.4065_16.9213"
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS nodes (
        node_id TEXT PRIMARY KEY,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        sum_ratings INTEGER DEFAULT 0,
        ratings_count INTEGER DEFAULT 0,
        avg_rating REAL DEFAULT 3.0
    )
    ''')

    conn.commit()
    conn.close()
    print("Successfully created database and nodes table")


def ensure_ways_rating_columns(db_path=DB_PATH):
    """Makes sure the ways table has everything rating-aware routing needs.

    way_rating    - AVERAGE rating of the way on a 1-10 scale (5.0 = unrated, neutral)
    ratings_count - how many ratings that average is built from (0 = unrated)

    A new rating g is folded in as: way_rating = (way_rating * n + g) / (n + 1), n += 1.
    Safe to run many times - columns are added only when missing.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Same layout as the table created by database_setup.py, plus ratings_count
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ways (
        way_id INTEGER NOT NULL,
        nodes JSON,
        coordinates JSON,
        distance INTEGER,
        way_rating FLOAT,
        ratings_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (way_id)
    )
    ''')

    columns = [r[1] for r in cursor.execute("PRAGMA table_info(ways)")]
    if "ratings_count" not in columns:
        cursor.execute("ALTER TABLE ways ADD COLUMN ratings_count INTEGER NOT NULL DEFAULT 0")
        print("Added ways.ratings_count")
    if "way_rating" not in columns:
        cursor.execute("ALTER TABLE ways ADD COLUMN way_rating FLOAT")
        print("Added ways.way_rating")

    conn.commit()
    conn.close()
    print("ways table has way_rating (average) and ratings_count")


if __name__ == "__main__":
    create_database()
    ensure_ways_rating_columns()
