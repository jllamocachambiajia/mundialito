import os

DB_PATH = os.environ.get("MUNDIALITO_DB", "/data/mundialito.db")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
TICK_HZ = 60            # física: igual que los fotogramas del juego original
SNAPSHOT_HZ = 30        # estados enviados a los clientes
TOKEN_HOURS = 24 * 7
ELO_START = 1000
ELO_K = 32
