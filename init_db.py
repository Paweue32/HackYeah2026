import json
import sqlite3

DB_PATH = 'hackathon_map.db'


def create_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # one row per OSM way; nodes, geometry and tags are stored as JSON text
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ways (
        id INTEGER PRIMARY KEY,
        name TEXT,
        highway_type TEXT,
        surface TEXT,
        maxspeed TEXT,
        nodes TEXT NOT NULL,
        geometry TEXT NOT NULL,
        tags TEXT NOT NULL DEFAULT '{}',
        sum_ratings INTEGER DEFAULT 0,
        ratings_count INTEGER DEFAULT 0,
        avg_rating REAL DEFAULT 3.0
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ways_highway ON ways(highway_type)')

    conn.commit()
    conn.close()
    print("Successfully created database and ways table")


def upsert_ways(conn, ways):
    # updates only the OSM columns, so ratings survive a re-download
    conn.executemany('''
        INSERT INTO ways (id, name, highway_type, surface, maxspeed, nodes, geometry, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            highway_type = excluded.highway_type,
            surface = excluded.surface,
            maxspeed = excluded.maxspeed,
            nodes = excluded.nodes,
            geometry = excluded.geometry,
            tags = excluded.tags
    ''', [
        (
            way['id'],
            way.get('name'),
            way.get('highway_type'),
            way.get('surface'),
            way.get('maxspeed'),
            json.dumps(way['nodes']),
            json.dumps(way['geometry']),
            json.dumps(way.get('tags', {}), ensure_ascii=False),
        )
        for way in ways
    ])
    conn.commit()


def row_to_way(row):
    # row in ways column order -> dict in the OSM way format
    (way_id, name, highway_type, surface, maxspeed, nodes, geometry, tags,
     sum_ratings, ratings_count, avg_rating) = row
    return {
        'id': way_id,
        'name': name,
        'highway_type': highway_type,
        'surface': surface,
        'maxspeed': maxspeed,
        'nodes': json.loads(nodes),
        'geometry': json.loads(geometry),
        'tags': json.loads(tags),
        'sum_ratings': sum_ratings,
        'ratings_count': ratings_count,
        'avg_rating': avg_rating,
    }


if __name__ == "__main__":
    create_database()
