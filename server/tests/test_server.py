import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from app import database, match as M, physics as P

database.reset_for_tests(os.path.join(tempfile.mkdtemp(), "t.db"))
from app.main import app


def run(m, secs):
    for _ in range(int(secs * 60)):
        m.update(1 / 60)


def test_cooldowns_son_independientes_por_equipo():
    m = M.Match("amistoso", ["a", "b"], ["Brasil", "Chile"])
    m.kickoff = 0
    assert m.shoot(0, 3, 50, 0)
    assert m.shoot(1, 3, -50, 0)          # el rival no queda bloqueado por mi tiro
    assert not m.shoot(0, 4, 50, 0)       # mi recarga de 1 s sigue
    run(m, 1.05)
    assert m.shoot(0, 4, 50, 0)


def test_saque_solo_del_equipo_que_saca():
    m = M.Match("amistoso", ["a", "b"], ["Brasil", "Chile"])
    m.kickoff = 1
    assert not m.shoot(0, 3, 50, 0)


def test_fuego_dura_dos_segundos_y_recarga_20():
    m = M.Match("amistoso", ["a", "b"], ["Brasil", "Chile"]); m.kickoff = 0
    assert m.ability(0, "fire")
    assert m.shoot(0, 3, 160, 0)
    assert m.fire["shot"] is not None
    run(m, 2.1)
    assert m.fire["shot"] is None
    assert not m.ability(0, "fire")
    assert abs(m.fire["ready"][0] - 20.0) < 0.01


def test_pausa_congela_al_rival():
    m = M.Match("amistoso", ["a", "b"], ["Brasil", "Chile"]); m.kickoff = 1
    assert m.ability(0, "pausa")
    assert not m.shoot(1, 3, -50, 0)


def test_campo_magnetico_bloquea_al_rival_22s():
    m = M.Match("amistoso", ["a", "b"], ["Brasil", "Chile"])
    assert m.ability(0, "magnet")
    assert not m.ability(1, "magnet")


def test_gol_suma_y_ranked_cambia_elo():
    c = TestClient(app)
    a = c.post("/api/registro", json={"usuario": "jose_1", "contrasena": "secreto1"}).json()
    b = c.post("/api/registro", json={"usuario": "rival", "contrasena": "secreto1"}).json()
    assert c.post("/api/registro", json={"usuario": "con espacio", "contrasena": "secreto1"}).status_code == 400
    ka = database.account_by_token(a["token"])["llave_maestra"]
    kb = database.account_by_token(b["token"])["llave_maestra"]
    m = M.Match("ranked", [ka, kb], ["Brasil", "Chile"])
    m.ball.x, m.ball.vx = P.FX1 + 5, 8
    run(m, 0.1)
    assert m.score == [1, 0]
    m._finish(0)
    assert database.save_match(m) == 16
    assert database.save_match(m) == 0     # no se cuenta dos veces
    top = c.get("/api/podio").json()
    assert top[0]["usuario"] == "jose_1" and top[0]["elo"] == 1016


def test_websocket_empareja_y_envia_estados():
    """Servidor uvicorn real (un solo bucle, como en Docker) + dos clientes WebSocket."""
    import json, socket, threading, time, uvicorn
    from websockets.sync.client import connect
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True); th.start()
    while not server.started:
        time.sleep(0.05)
    c = TestClient(app)
    t1 = c.post("/api/registro", json={"usuario": "ws_uno", "contrasena": "secreto1"}).json()["token"]
    t2 = c.post("/api/registro", json={"usuario": "ws_dos", "contrasena": "secreto1"}).json()["token"]
    url = f"ws://127.0.0.1:{port}/ws/game?token="
    rx = lambda w: json.loads(w.recv(timeout=5))
    with connect(url + t1) as w1, connect(url + t2) as w2:
        assert rx(w1)["type"] == "hello"; rx(w2)
        w1.send(json.dumps({"type": "queue", "mode": "amistoso", "team": "Brasil"}))
        assert rx(w1)["type"] == "queued"
        w2.send(json.dumps({"type": "queue", "mode": "amistoso", "team": "Chile"}))
        s1, s2 = rx(w1), rx(w2)
        assert s1["type"] == s2["type"] == "match_start" and {s1["side"], s2["side"]} == {0, 1}
        st = rx(w1)
        assert st["type"] == "state" and len(st["bodies"]) == 12
        w2.send(json.dumps({"type": "surrender"}))
        while (msg := rx(w1))["type"] != "match_end":
            pass
        assert msg["winner"] == s1["side"] and msg["me"]["victorias"] == 1
    server.should_exit = True; th.join(5)
