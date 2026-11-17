"""Offline private SQLite storage; result and streak update are one transaction."""
import json
import os
from pathlib import Path

try:
    import sqlite3
except Exception:  # APK compilado sin sqlite3 en requirements
    sqlite3 = None


class LocalStore:
    def __new__(cls, directory):
        if sqlite3 is None:
            return JsonStore(directory)
        try:
            obj = super().__new__(cls)
            obj._open(directory)
            return obj
        except Exception:
            return JsonStore(directory)

    def __init__(self, directory):
        pass  # la apertura real ocurre en _open

    def _open(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(directory / 'mundialito.sqlite3'))
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS friendly_results(
                match_id TEXT PRIMARY KEY, country TEXT NOT NULL, opponent TEXT NOT NULL,
                won INTEGER NOT NULL CHECK(won IN (0,1)), score TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS friendly_stats(
                id INTEGER PRIMARY KEY CHECK(id=1), wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0,
                best INTEGER NOT NULL DEFAULT 0);
            INSERT OR IGNORE INTO friendly_stats(id) VALUES(1);
        ''')
        self.connection.commit()

    def stats(self):
        row = self.connection.execute('SELECT wins,losses,streak,best FROM friendly_stats WHERE id=1').fetchone()
        return dict(zip(('wins', 'losses', 'streak', 'best'), row))

    def record(self, match_id, country, opponent, won, score):
        with self.connection:
            cursor = self.connection.execute(
                'INSERT OR IGNORE INTO friendly_results(match_id,country,opponent,won,score) VALUES(?,?,?,?,?)',
                (match_id, country, opponent, int(won), score))
            if not cursor.rowcount:
                return False
            if won:
                self.connection.execute('UPDATE friendly_stats SET wins=wins+1,streak=streak+1,best=MAX(best,streak+1) WHERE id=1')
            else:
                self.connection.execute('UPDATE friendly_stats SET losses=losses+1,streak=0 WHERE id=1')
        return True

    def get(self, key, default=None):
        row = self.connection.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (key, json.dumps(value)))

    def close(self):
        self.connection.close()


class JsonStore:
    """Respaldo privado en JSON con la misma interfaz; IDs únicos evitan doble conteo."""

    def __init__(self, directory):
        self.path = None
        self.data = {'settings': {}, 'results': [], 'stats': {'wins': 0, 'losses': 0, 'streak': 0, 'best': 0}}
        try:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            self.path = directory / 'mundialito.json'
            if self.path.is_file():
                loaded = json.loads(self.path.read_text(encoding='utf-8'))
                self.data.update(loaded)
        except Exception:
            pass

    def _save(self):
        if self.path is None:
            return
        try:
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.data), encoding='utf-8')
            os.replace(str(tmp), str(self.path))
        except Exception:
            pass

    def stats(self):
        return dict(self.data['stats'])

    def record(self, match_id, country, opponent, won, score):
        if match_id in self.data['results']:
            return False
        self.data['results'].append(match_id)
        st = self.data['stats']
        if won:
            st['wins'] += 1
            st['streak'] += 1
            st['best'] = max(st['best'], st['streak'])
        else:
            st['losses'] += 1
            st['streak'] = 0
        self._save()
        return True

    def get(self, key, default=None):
        return self.data['settings'].get(key, default)

    def set(self, key, value):
        self.data['settings'][key] = value
        self._save()

    def close(self):
        self._save()
