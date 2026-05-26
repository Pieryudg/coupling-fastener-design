from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATABASE_PATH = DATA_DIR / "metric_bolts.sqlite"


@dataclass(frozen=True)
class BoltSize:
    designation: str
    diameter_mm: float
    pitch_mm: float
    tensile_area_mm2: float


@dataclass(frozen=True)
class PropertyClass:
    name: str
    ultimate_mpa: float
    yield_mpa: float
    proof_mpa: float


BOLT_SIZES = [
    ("M3", 3.0, 0.5, 5.03),
    ("M4", 4.0, 0.7, 8.78),
    ("M5", 5.0, 0.8, 14.2),
    ("M6", 6.0, 1.0, 20.1),
    ("M8", 8.0, 1.25, 36.6),
    ("M10", 10.0, 1.5, 58.0),
    ("M12", 12.0, 1.75, 84.3),
    ("M14", 14.0, 2.0, 115.0),
    ("M16", 16.0, 2.0, 157.0),
    ("M18", 18.0, 2.5, 192.0),
    ("M20", 20.0, 2.5, 245.0),
    ("M22", 22.0, 2.5, 303.0),
    ("M24", 24.0, 3.0, 353.0),
    ("M27", 27.0, 3.0, 459.0),
    ("M30", 30.0, 3.5, 561.0),
    ("M33", 33.0, 3.5, 694.0),
    ("M36", 36.0, 4.0, 817.0),
    ("M39", 39.0, 4.0, 976.0),
    ("M42", 42.0, 4.5, 1120.0),
    ("M45", 45.0, 4.5, 1300.0),
    ("M48", 48.0, 5.0, 1470.0),
]


PROPERTY_CLASSES = [
    ("8.8", 800.0, 640.0, 580.0),
    ("10.9", 1000.0, 900.0, 830.0),
    ("12.9", 1200.0, 1080.0, 970.0),
]


def connect(path: Path = DATABASE_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metric_bolt_sizes (
            designation TEXT PRIMARY KEY,
            diameter_mm REAL NOT NULL,
            pitch_mm REAL NOT NULL,
            tensile_area_mm2 REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS property_classes (
            name TEXT PRIMARY KEY,
            ultimate_mpa REAL NOT NULL,
            yield_mpa REAL NOT NULL,
            proof_mpa REAL NOT NULL
        );
        """
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO metric_bolt_sizes
            (designation, diameter_mm, pitch_mm, tensile_area_mm2)
        VALUES (?, ?, ?, ?)
        """,
        BOLT_SIZES,
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO property_classes
            (name, ultimate_mpa, yield_mpa, proof_mpa)
        VALUES (?, ?, ?, ?)
        """,
        PROPERTY_CLASSES,
    )
    conn.commit()


def list_bolt_sizes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT designation FROM metric_bolt_sizes ORDER BY diameter_mm"
    ).fetchall()
    return [row["designation"] for row in rows]


def list_property_classes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM property_classes ORDER BY yield_mpa"
    ).fetchall()
    return [row["name"] for row in rows]


def get_bolt_size(conn: sqlite3.Connection, designation: str) -> BoltSize:
    row = conn.execute(
        """
        SELECT designation, diameter_mm, pitch_mm, tensile_area_mm2
        FROM metric_bolt_sizes
        WHERE designation = ?
        """,
        (designation,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown bolt size: {designation}")
    return BoltSize(
        designation=row["designation"],
        diameter_mm=row["diameter_mm"],
        pitch_mm=row["pitch_mm"],
        tensile_area_mm2=row["tensile_area_mm2"],
    )


def get_property_class(conn: sqlite3.Connection, name: str) -> PropertyClass:
    row = conn.execute(
        """
        SELECT name, ultimate_mpa, yield_mpa, proof_mpa
        FROM property_classes
        WHERE name = ?
        """,
        (name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown property class: {name}")
    return PropertyClass(
        name=row["name"],
        ultimate_mpa=row["ultimate_mpa"],
        yield_mpa=row["yield_mpa"],
        proof_mpa=row["proof_mpa"],
    )


def recommend_bolt_size(
    conn: sqlite3.Connection,
    property_class: PropertyClass,
    required_initial_preload_n: float,
    max_yield_utilization: float,
) -> BoltSize | None:
    rows = conn.execute(
        """
        SELECT designation, diameter_mm, pitch_mm, tensile_area_mm2
        FROM metric_bolt_sizes
        ORDER BY diameter_mm
        """
    ).fetchall()
    for row in rows:
        yield_load = property_class.yield_mpa * row["tensile_area_mm2"]
        if required_initial_preload_n <= yield_load * max_yield_utilization:
            return BoltSize(
                designation=row["designation"],
                diameter_mm=row["diameter_mm"],
                pitch_mm=row["pitch_mm"],
                tensile_area_mm2=row["tensile_area_mm2"],
            )
    return None
