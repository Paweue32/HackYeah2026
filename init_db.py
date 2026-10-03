import sqlite3

def create_database():
    conn = sqlite3.connect('hackathon_map.db')
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

if __name__ == "__main__":
    create_database()