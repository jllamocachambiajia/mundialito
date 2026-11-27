"""Cliente de red de Mundialito (APK y .exe). NO calcula física: solo envía intenciones
(disparos y habilidades) y entrega al juego los estados que dicta el servidor autoritario."""
import json
import os
import queue
import threading
import urllib.error
import urllib.parse
import urllib.request

try:
    import websocket          # paquete "websocket-client" (puro Python, compila en Buildozer)
except Exception:             # el juego offline sigue funcionando sin él
    websocket = None

DEFAULT_SERVER = "http://127.0.0.1:8000"   # cámbialo en online_config.json o aquí por la IP del VPS


def load_server_url(data_dir=None):
    if os.environ.get("MUNDIALITO_SERVER"):
        return os.environ["MUNDIALITO_SERVER"].rstrip("/")
    for folder in (data_dir, os.path.dirname(os.path.abspath(__file__))):
        if not folder:
            continue
        path = os.path.join(folder, "online_config.json")
        try:
            with open(path, encoding="utf-8") as fh:
                url = json.load(fh).get("server", "").strip()
                if url:
                    return url.rstrip("/")
        except (OSError, ValueError):
            pass
    return DEFAULT_SERVER


class NetError(Exception):
    pass


class NetworkClient:
    def __init__(self, server_url):
        self.http = server_url.rstrip("/")
        self.ws_url = self.http.replace("https://", "wss://").replace("http://", "ws://") + "/ws/game"
        self.token = None
        self.account = None
        self.inbox = queue.Queue()
        self.ws = None
        self._thread = None

    # ------------------------------------------------------------ REST
    def _post(self, path, payload):
        req = urllib.request.Request(self.http + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        return self._open(req)

    def _get(self, path, **params):
        q = ("?" + urllib.parse.urlencode(params)) if params else ""
        return self._open(urllib.request.Request(self.http + path + q))

    def _open(self, req):
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                raise NetError(json.loads(e.read().decode()).get("detail", "Error del servidor"))
            except ValueError:
                raise NetError("Error del servidor")
        except (urllib.error.URLError, OSError, ValueError):
            raise NetError("No se pudo conectar con el servidor")

    def register(self, user, password):
        return self._auth("/api/registro", user, password)

    def login(self, user, password):
        return self._auth("/api/login", user, password)

    def _auth(self, path, user, password):
        data = self._post(path, {"usuario": user.strip(), "contrasena": password})
        self.token, self.account = data["token"], data["cuenta"]
        return self.account

    def leaderboard(self):
        return self._get("/api/podio", limite=50)

    def refresh_account(self):
        self.account = self._get("/api/yo", token=self.token)
        return self.account

    # ------------------------------------------------------------ WebSocket
    def connect(self):
        if websocket is None:
            raise NetError("Falta el paquete websocket-client")
        if self.ws is not None:
            return
        url = self.ws_url + "?token=" + urllib.parse.quote(self.token or "")
        self.ws = websocket.WebSocketApp(
            url,
            on_message=lambda _ws, raw: self._incoming(raw),
            on_error=lambda _ws, err: self.inbox.put({"type": "net_error", "message": str(err)}),
            on_close=lambda *_: self._closed())
        self._thread = threading.Thread(target=self.ws.run_forever,
                                        kwargs={"ping_interval": 20, "ping_timeout": 10}, daemon=True)
        self._thread.start()

    def _incoming(self, raw):
        try:
            self.inbox.put(json.loads(raw))
        except ValueError:
            pass

    def _closed(self):
        self.ws = None
        self.inbox.put({"type": "disconnected"})

    def send(self, **msg):
        try:
            if self.ws is not None:
                self.ws.send(json.dumps(msg))
        except Exception:
            self.inbox.put({"type": "net_error", "message": "Conexión perdida"})

    def queue_match(self, mode, team):
        self.send(type="queue", mode=mode, team=team)

    def cancel(self):
        self.send(type="cancel")

    def shoot(self, body, dx, dy):
        self.send(type="shoot", body=body, dx=round(dx, 2), dy=round(dy, 2))

    def ability(self, name):
        self.send(type="ability", name=name)

    def surrender(self):
        self.send(type="surrender")

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def close(self):
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws = None
