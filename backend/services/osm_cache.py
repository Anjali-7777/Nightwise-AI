import sqlite3
import json
import time
import math
from pathlib import Path
from typing import Optional, List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "osm_cache.db"

class OSMTileCache:
    """
    SQLite tile-based cache for OpenStreetMap features.
    Tiles are indexed at 0.01 degree resolution (~1.1 km x 1.1 km in India).
    Features are cached with a configurable TTL (default 7 days).
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS osm_tiles (
                    tile_key TEXT PRIMARY KEY,
                    lat_idx INTEGER,
                    lon_idx INTEGER,
                    data_json TEXT,
                    timestamp REAL,
                    ttl_days REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tile_coords ON osm_tiles(lat_idx, lon_idx)")
            conn.commit()

    @staticmethod
    def get_tile_indices(lat: float, lon: float) -> tuple[int, int]:
        """Returns (lat_idx, lon_idx) for 0.01 degree tiles."""
        return int(math.floor(lat * 100)), int(math.floor(lon * 100))

    @staticmethod
    def tile_bounds(lat_idx: int, lon_idx: int) -> tuple[float, float, float, float]:
        """Returns (min_lat, min_lon, max_lat, max_lon) for tile."""
        min_lat = lat_idx / 100.0
        min_lon = lon_idx / 100.0
        max_lat = (lat_idx + 1) / 100.0
        max_lon = (lon_idx + 1) / 100.0
        return min_lat, min_lon, max_lat, max_lon

    def get_tile(self, lat_idx: int, lon_idx: int) -> Optional[Dict[str, Any]]:
        tile_key = f"{lat_idx},{lon_idx}"
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data_json, timestamp, ttl_days FROM osm_tiles WHERE tile_key = ?",
                (tile_key,)
            )
            row = cursor.fetchone()
            if row:
                data_json, timestamp, ttl_days = row
                if (now - timestamp) <= ttl_days * 86400:
                    try:
                        return json.loads(data_json)
                    except Exception:
                        return None
        return None

    def save_tile(self, lat_idx: int, lon_idx: int, data: Dict[str, Any], ttl_days: float = 7.0):
        tile_key = f"{lat_idx},{lon_idx}"
        data_json = json.dumps(data)
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO osm_tiles (tile_key, lat_idx, lon_idx, data_json, timestamp, ttl_days)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tile_key, lat_idx, lon_idx, data_json, now, ttl_days)
            )
            conn.commit()

    def get_tiles_for_bbox(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> List[tuple[int, int]]:
        """Returns all (lat_idx, lon_idx) pairs intersecting the bbox."""
        min_lat_idx, min_lon_idx = self.get_tile_indices(min_lat, min_lon)
        max_lat_idx, max_lon_idx = self.get_tile_indices(max_lat, max_lon)
        tiles = []
        for la in range(min_lat_idx, max_lat_idx + 1):
            for lo in range(min_lon_idx, max_lon_idx + 1):
                tiles.append((la, lo))
        return tiles

# Global singleton
osm_cache = OSMTileCache()
