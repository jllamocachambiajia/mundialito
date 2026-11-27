"""SQLite (modo WAL) con cuentas, sesiones e historial. Ligero para un VPS de 1 GB."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid

from . import config

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cuentas (
    llave_maestra  TEXT PRIMARY KEY,
    usuario        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    contrasena     TEXT NOT NULL,
    elo            INTEGER NOT NULL DEFAULT 1000,
    victorias      INTEGER NOT NULL DEFAULT 0,
    derrotas       INTEGER NOT NULL DEFAULT 0,
    empates        INTEGER NOT NULL DEFAULT 0,
    porcentaje_victoria REAL GENERATED ALWAYS AS (
        CASE WHEN victorias + derrotas + empates = 0 THEN 0.0
        ELSE ROUND(100.0 * victorias / (victorias + derrotas + empates), 1) END) VIRTUAL,
    conectado      INTEGER NOT NULL DEFAULT 0,
    creado         INTEGER NOT NULL,
    ultima_conexion INTEGER
);
CREATE TABLE IF NOT EXISTS sesiones (
    token TEXT PRIMARY KEY,
    llave_maestra TEXT NOT NULL REFERENCES cuentas(llave_maestra) ON DELETE CASCADE,
    expira INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS partidos (
    id TEXT PRIMARY KEY,
    modo TEXT NOT NULL,
    jugador0 TEXT NOT NULL, jugador1 TEXT NOT NULL,
    pais0 TEXT, pais1 TEXT,
    goles0 INTEGER, goles1 INTEGER,
    ganador INTEGER,
    elo_cambio INTEGER DEFAULT 0,
    fecha INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_elo ON cuentas(elo DESC);
"""


def connect():
    d = os.path.dirname(config.DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


_con = None


def db():
    global _con
    if _con is None:
        _con = connect()
        _con.executescript(SCHEMA)
        _con.execute("UPDATE cuentas SET conectado = 0")
    return _con


def reset_for_tests(path):
    global _con
    config.DB_PATH = path
    _con = None
    db()


def hash_password(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"pbkdf2${salt}${h}"


def check_password(pw, stored):
    try:
        _, salt, h = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(pw, salt), stored)


class AuthError(Exception):
    pass


def register(username, password):
    if not USERNAME_RE.match(username or ""):
        raise AuthError("Usuario: 3-16 letras, números o _ (sin espacios ni símbolos)")
    if len(password or "") < 6:
        raise AuthError("La contraseña debe tener al menos 6 caracteres")
    key = str(uuid.uuid4())
    with _lock:
        try:
            db().execute("INSERT INTO cuentas(llave_maestra, usuario, contrasena, elo, creado) VALUES (?,?,?,?,?)",
                         (key, username, hash_password(password), config.ELO_START, int(time.time())))
        except sqlite3.IntegrityError:
            raise AuthError("Ese usuario ya existe")
    return key


def login(username, password):
    row = db().execute("SELECT * FROM cuentas WHERE usuario = ?", (username or "",)).fetchone()
    if row is None or not check_password(password or "", row["contrasena"]):
        raise AuthError("Usuario o contraseña incorrectos")
    token = secrets.token_urlsafe(32)
    with _lock:
        db().execute("INSERT INTO sesiones VALUES (?,?,?)",
                     (token, row["llave_maestra"], int(time.time() + config.TOKEN_HOURS * 3600)))
    return token, public(row)


def account_by_token(token):
    row = db().execute(
        "SELECT c.* FROM sesiones s JOIN cuentas c USING(llave_maestra) WHERE s.token = ? AND s.expira > ?",
        (token or "", int(time.time()))).fetchone()
    return row


def account(key):
    return db().execute("SELECT * FROM cuentas WHERE llave_maestra = ?", (key,)).fetchone()


def public(row):
    return {"usuario": row["usuario"], "elo": row["elo"], "victorias": row["victorias"],
            "derrotas": row["derrotas"], "empates": row["empates"],
            "porcentaje_victoria": row["porcentaje_victoria"], "conectado": bool(row["conectado"])}


def set_online(key, online):
    with _lock:
        db().execute("UPDATE cuentas SET conectado = ?, ultima_conexion = ? WHERE llave_maestra = ?",
                     (1 if online else 0, int(time.time()), key))


def elo_delta(ra, rb, score_a, k=None):
    k = k or config.ELO_K
    expected = 1 / (1 + 10 ** ((rb - ra) / 400))
    return round(k * (score_a - expected))


def save_match(match):
    """Guarda el resultado una sola vez (id único). Ranked actualiza ELO; ambos modos suman V/D/E."""
    a, b = match.players
    w = match.winner
    with _lock:
        con = db()
        con.execute("BEGIN IMMEDIATE")
        try:
            if con.execute("SELECT 1 FROM partidos WHERE id = ?", (match.id,)).fetchone():
                con.execute("ROLLBACK")
                return 0
            ra = con.execute("SELECT elo FROM cuentas WHERE llave_maestra=?", (a,)).fetchone()[0]
            rb = con.execute("SELECT elo FROM cuentas WHERE llave_maestra=?", (b,)).fetchone()[0]
            score_a = 0.5 if w is None else (1.0 if w == 0 else 0.0)
            delta = elo_delta(ra, rb, score_a) if match.mode == "ranked" else 0
            for key, s, d in ((a, score_a, delta), (b, 1 - score_a, -delta)):
                col = "empates" if s == 0.5 else ("victorias" if s == 1 else "derrotas")
                con.execute(f"UPDATE cuentas SET {col} = {col} + 1, elo = MAX(0, elo + ?) WHERE llave_maestra = ?",
                            (d, key))
            con.execute("INSERT INTO partidos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (match.id, match.mode, a, b, match.teams[0], match.teams[1],
                         match.score[0], match.score[1], w, delta, int(time.time())))
            con.execute("COMMIT")
            return delta
        except Exception:
            con.execute("ROLLBACK")
            raise


def leaderboard(limit=50):
    rows = db().execute("SELECT * FROM cuentas ORDER BY elo DESC, victorias DESC LIMIT ?", (limit,)).fetchall()
    return [dict(public(r), puesto=i + 1) for i, r in enumerate(rows)]
