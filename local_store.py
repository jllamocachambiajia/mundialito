"""Almacenamiento privado único: amistosos, ajustes, moneditas y tienda."""
import json
import os
import threading
from pathlib import Path

try:
    import sqlite3
except Exception:  # APK compilado sin sqlite3 en requirements
    sqlite3 = None


def _shop_data(value):
    return value if isinstance(value, dict) else {}


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
        pass

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
            CREATE TABLE IF NOT EXISTS reward_transactions(
                transaction_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount > 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT OR IGNORE INTO friendly_stats(id) VALUES(1);
        ''')
        self.connection.commit()
        self.last_reward = None

    def _read_shop_sql(self):
        row = self.connection.execute("SELECT value FROM settings WHERE key='shop_v1'").fetchone()
        try:
            return _shop_data(json.loads(row[0])) if row else {}
        except (TypeError, ValueError):
            return {}

    def _write_shop_sql(self, data):
        self.connection.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('shop_v1',?)",
                                (json.dumps(data, ensure_ascii=False),))

    def _claim_reward_sql(self, transaction_id, kind, amount):
        cursor = self.connection.execute(
            'INSERT OR IGNORE INTO reward_transactions(transaction_id,kind,amount) VALUES(?,?,?)',
            (transaction_id, kind, int(amount)))
        if not cursor.rowcount:
            return None
        data = self._read_shop_sql()
        data['balance'] = max(0, int(data.get('balance', 0))) + int(amount)
        self._write_shop_sql(data)
        return {'amount': int(amount), 'balance': data['balance'], 'kind': kind}

    def stats(self):
        row = self.connection.execute('SELECT wins,losses,streak,best FROM friendly_stats WHERE id=1').fetchone()
        return dict(zip(('wins', 'losses', 'streak', 'best'), row))

    def record(self, match_id, country, opponent, won, score):
        self.last_reward = None
        with self.connection:
            cursor = self.connection.execute(
                'INSERT OR IGNORE INTO friendly_results(match_id,country,opponent,won,score) VALUES(?,?,?,?,?)',
                (match_id, country, opponent, int(won), score))
            if not cursor.rowcount:
                return False
            if won:
                self.connection.execute('UPDATE friendly_stats SET wins=wins+1,streak=streak+1,best=MAX(best,streak+1) WHERE id=1')
                # Resultado, estadística y recompensa se confirman o revierten juntos.
                self.last_reward = self._claim_reward_sql(f'friendly:{match_id}', 'friendly', 200)
            else:
                self.connection.execute('UPDATE friendly_stats SET losses=losses+1,streak=0 WHERE id=1')
        return True

    def claim_reward(self, transaction_id, kind, amount):
        with self.connection:
            reward = self._claim_reward_sql(transaction_id, kind, int(amount))
        self.last_reward = reward
        return reward

    def mutate_shop(self, callback):
        """Una compra lee, valida, descuenta y guarda en la misma transacción."""
        with self.connection:
            data = self._read_shop_sql()
            result = callback(data)
            self._write_shop_sql(data)
        return result

    def get(self, key, default=None):
        row = self.connection.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (key, json.dumps(value)))

    def close(self):
        self.connection.close()


class JsonStore:
    """Respaldo privado del MISMO almacenamiento lógico si SQLite no está disponible."""
    def __init__(self, directory):
        self.path = None
        self.lock = threading.RLock()
        self.last_reward = None
        self.data = {'settings': {}, 'results': [], 'rewards': [],
                     'stats': {'wins': 0, 'losses': 0, 'streak': 0, 'best': 0}}
        try:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            self.path = directory / 'mundialito.json'
            if self.path.is_file():
                loaded = json.loads(self.path.read_text(encoding='utf-8'))
                self.data.update(loaded)
        except Exception:
            pass
        self.data.setdefault('rewards', [])

    def _save(self):
        if self.path is None:
            return
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        os.replace(str(tmp), str(self.path))

    def _shop(self):
        return _shop_data(self.data['settings'].get('shop_v1'))

    def _claim_reward(self, transaction_id, kind, amount):
        if transaction_id in self.data['rewards']:
            return None
        self.data['rewards'].append(transaction_id)
        data = self._shop()
        data['balance'] = max(0, int(data.get('balance', 0))) + int(amount)
        self.data['settings']['shop_v1'] = data
        return {'amount': int(amount), 'balance': data['balance'], 'kind': kind}

    def stats(self):
        return dict(self.data['stats'])

    def record(self, match_id, country, opponent, won, score):
        with self.lock:
            self.last_reward = None
            if match_id in self.data['results']:
                return False
            self.data['results'].append(match_id)
            st = self.data['stats']
            if won:
                st['wins'] += 1
                st['streak'] += 1
                st['best'] = max(st['best'], st['streak'])
                self.last_reward = self._claim_reward(f'friendly:{match_id}', 'friendly', 200)
            else:
                st['losses'] += 1
                st['streak'] = 0
            self._save()
            return True

    def claim_reward(self, transaction_id, kind, amount):
        with self.lock:
            reward = self._claim_reward(transaction_id, kind, int(amount))
            self._save()
            self.last_reward = reward
            return reward

    def mutate_shop(self, callback):
        with self.lock:
            data = self._shop()
            result = callback(data)
            self.data['settings']['shop_v1'] = data
            self._save()
            return result

    def get(self, key, default=None):
        return self.data['settings'].get(key, default)

    def set(self, key, value):
        with self.lock:
            self.data['settings'][key] = value
            self._save()

    def close(self):
        with self.lock:
            self._save()
