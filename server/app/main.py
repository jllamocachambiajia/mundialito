"""API FastAPI: REST (cuentas/podio) + WebSocket autoritario /ws/game."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from . import database
from .rooms import Lobby, Player

TEAMS = ["España", "Francia", "Alemania", "Inglaterra", "Italia", "Portugal", "Países Bajos", "Bélgica",
         "Croacia", "Argentina", "Brasil", "Uruguay", "Colombia", "México", "Estados Unidos", "Chile",
         "Suecia", "Dinamarca", "Suiza", "Polonia", "Hungría", "Paraguay", "Perú", "Ecuador"]

lobby = Lobby()


@asynccontextmanager
async def lifespan(app):
    database.db()
    task = asyncio.create_task(lobby.retry_ranked())
    yield
    task.cancel()


app = FastAPI(title="Mundialito de Chapas - Servidor autoritario", version="1.0", lifespan=lifespan)


class Credentials(BaseModel):
    usuario: str
    contrasena: str


@app.get("/health")
def health():
    return {"ok": True, "salas": len(lobby.rooms)}


@app.post("/api/registro")
def registro(c: Credentials):
    try:
        database.register(c.usuario, c.contrasena)
        token, me = database.login(c.usuario, c.contrasena)
    except database.AuthError as e:
        raise HTTPException(400, str(e))
    return {"token": token, "cuenta": me}


@app.post("/api/login")
def login(c: Credentials):
    try:
        token, me = database.login(c.usuario, c.contrasena)
    except database.AuthError as e:
        raise HTTPException(401, str(e))
    return {"token": token, "cuenta": me}


@app.get("/api/yo")
def yo(token: str):
    row = database.account_by_token(token)
    if row is None:
        raise HTTPException(401, "Sesión vencida")
    return database.public(row)


@app.get("/api/podio")
def podio(limite: int = 50):
    return database.leaderboard(max(1, min(limite, 100)))


@app.websocket("/ws/game")
async def game(ws: WebSocket, token: str = ""):
    row = database.account_by_token(token)
    await ws.accept()
    if row is None:
        await ws.send_json({"type": "error", "message": "Sesión inválida"})
        await ws.close(code=4401)
        return
    player = Player(ws, row)
    database.set_online(player.key, True)
    await player.send({"type": "hello", "cuenta": database.public(database.account(player.key))})
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type") if isinstance(msg, dict) else None
            if kind == "queue" and player.room is None:
                team = msg.get("team")
                player.team = team if team in TEAMS else "Argentina"
                player.elo = database.account(player.key)["elo"]
                await lobby.enqueue(player, msg.get("mode", "amistoso"))
            elif kind == "cancel":
                lobby.remove(player)
                await player.send({"type": "cancelled"})
            elif kind == "ping":
                await player.send({"type": "pong", "c": msg.get("c")})
            elif player.room is not None:
                player.room.input(player, msg)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        lobby.remove(player)
        if player.room is not None:
            player.room.match.forfeit(player.side)   # abandonar = derrota
        database.set_online(player.key, False)
