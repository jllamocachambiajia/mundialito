#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor Unificado HTTP + WebSocket para Mundialito en llamoca.enlace.ink.
Sirve la plataforma web interactiva y coordina el multijugador en tiempo real.
"""

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
import random
import struct
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("LlamocaServer")

MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
STATIC_DIR = Path(__file__).resolve().parent / "public_html"


class WebSocketConnection:
    """Manejador de conexión WebSocket RFC 6455."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.peername = writer.get_extra_info('peername')
        self.closed = False

    async def recv_json(self):
        while not self.closed:
            try:
                head = await self.reader.readexactly(2)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                self.closed = True
                return None

            b1, b2 = head[0], head[1]
            opcode = b1 & 0x0F
            masked = (b2 & 0x80) != 0
            payload_len = b2 & 0x7F

            if opcode == 0x8:  # Close
                self.closed = True
                return None
            elif opcode == 0x9:  # Ping
                pong = bytearray([0x8A, 0])
                self.writer.write(pong)
                await self.writer.drain()
                continue
            elif opcode == 0xA:
                continue

            if payload_len == 126:
                ext = await self.reader.readexactly(2)
                payload_len = struct.unpack("!H", ext)[0]
            elif payload_len == 127:
                ext = await self.reader.readexactly(8)
                payload_len = struct.unpack("!Q", ext)[0]

            mask_key = None
            if masked:
                mask_key = await self.reader.readexactly(4)

            payload = await self.reader.readexactly(payload_len)
            if masked:
                unmasked = bytearray(payload_len)
                for i in range(payload_len):
                    unmasked[i] = payload[i] ^ mask_key[i % 4]
                payload = bytes(unmasked)

            try:
                text = payload.decode("utf-8")
                return json.loads(text)
            except Exception:
                return None

    async def send_json(self, data):
        if self.closed:
            return False
        try:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            length = len(raw)
            header = bytearray([0x81])

            if length <= 125:
                header.append(length)
            elif length <= 65535:
                header.append(126)
                header.extend(struct.pack("!H", length))
            else:
                header.append(127)
                header.extend(struct.pack("!Q", length))

            self.writer.write(header + raw)
            await self.writer.drain()
            return True
        except Exception:
            self.closed = True
            return False

    def close(self):
        self.closed = True
        try:
            self.writer.close()
        except Exception:
            pass


class GameRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = [None, None]
        self.teams = ["Argentina", "Brasil"]
        self.started = False
        self.created_at = time.time()
        self.last_activity = time.time()

    def is_full(self):
        return self.players[0] is not None and self.players[1] is not None

    def is_empty(self):
        return self.players[0] is None and self.players[1] is None

    def add_player(self, conn, team_name):
        self.last_activity = time.time()
        if self.players[0] is None:
            self.players[0] = conn
            self.teams[0] = team_name
            return 0
        elif self.players[1] is None:
            self.players[1] = conn
            self.teams[1] = team_name
            return 1
        return -1

    def remove_player(self, conn):
        for idx in (0, 1):
            if self.players[idx] == conn:
                self.players[idx] = None
                return idx
        return -1

    def get_opponent(self, player_idx):
        return self.players[1 - player_idx]


class UnifiedServer:
    def __init__(self):
        self.rooms = {}
        self.waiting_quick_room = None
        self.start_time = time.time()

    def generate_room_id(self):
        while True:
            code = f"{random.randint(1000, 9999)}"
            if code not in self.rooms:
                return code

    async def handle_request(self, reader, writer):
        """Atiende la conexión HTTP inicial y decide si sirve la web o hace handshake WebSocket."""
        header_data = b""
        while b"\r\n\r\n" not in header_data:
            try:
                chunk = await reader.read(1024)
            except Exception:
                chunk = None
            if not chunk:
                writer.close()
                return
            header_data += chunk
            if len(header_data) > 16384:
                writer.close()
                return

        lines = header_data.decode("utf-8", errors="ignore").split("\r\n")
        req_line = lines[0] if lines else ""
        parts = req_line.split(" ")
        method = parts[0].upper() if len(parts) > 0 else "GET"
        path = parts[1] if len(parts) > 1 else "/"

        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        # Comprobar si es solicitud WebSocket
        upgrade = headers.get("upgrade", "").lower()
        ws_key = headers.get("sec-websocket-key")

        if "websocket" in upgrade and ws_key:
            accept_val = base64.b64encode(
                hashlib.sha1((ws_key + MAGIC_GUID).encode("utf-8")).digest()
            ).decode("utf-8")
            resp = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_val}\r\n\r\n"
            )
            writer.write(resp.encode("utf-8"))
            await writer.drain()

            conn = WebSocketConnection(reader, writer)
            await self.handle_websocket(conn)
            return

        # Petición HTTP estándar
        await self.handle_http(writer, method, path)

    async def handle_http(self, writer, method, path):
        path = path.split("?")[0]

        # Endpoint API de estado
        if path == "/api/status":
            uptime = int(time.time() - self.start_time)
            data = {
                "status": "online",
                "service": "Mundialito Multiplayer Server",
                "uptime_seconds": uptime,
                "active_rooms": len(self.rooms),
                "waiting_match": self.waiting_quick_room is not None,
                "rooms_list": [
                    {"id": r.room_id, "teams": r.teams, "started": r.started}
                    for r in self.rooms.values()
                ]
            }
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            head = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Access-Control-Allow-Origin: *\r\n"
                "Connection: close\r\n\r\n"
            )
            writer.write(head.encode("utf-8") + body)
            await writer.drain()
            writer.close()
            return

        # Servir archivos estáticos
        if path == "/":
            filename = "index.html"
        else:
            filename = path.lstrip("/")

        file_path = (STATIC_DIR / filename).resolve()

        if not str(file_path).startswith(str(STATIC_DIR)) or not file_path.is_file():
            not_found = b"<h1>404 Not Found</h1>"
            resp = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(not_found)}\r\n"
                "Connection: close\r\n\r\n"
            )
            writer.write(resp.encode("utf-8") + not_found)
            await writer.drain()
            writer.close()
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        body = file_path.read_bytes()

        resp = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Cache-Control: public, max-age=3600\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(resp.encode("utf-8") + body)
        await writer.drain()
        writer.close()

    async def handle_websocket(self, conn):
        current_room = None
        player_idx = -1
        logger.info(f"Cliente WebSocket conectado desde {conn.peername}")

        try:
            while not conn.closed:
                msg = await conn.recv_json()
                if msg is None:
                    break

                action = msg.get("action")

                if action == "create_room":
                    team = msg.get("team", "Argentina")
                    room_id = self.generate_room_id()
                    room = GameRoom(room_id)
                    p_idx = room.add_player(conn, team)
                    self.rooms[room_id] = room
                    current_room = room
                    player_idx = p_idx

                    await conn.send_json({
                        "type": "room_created",
                        "room_id": room_id,
                        "player_idx": 0,
                        "team": team
                    })
                    logger.info(f"Sala {room_id} creada (Equipo: {team})")

                elif action == "join_room":
                    room_id = str(msg.get("room_id", "")).strip()
                    team = msg.get("team", "Brasil")

                    if room_id not in self.rooms:
                        await conn.send_json({
                            "type": "error",
                            "message": f"La sala {room_id} no existe."
                        })
                        continue

                    room = self.rooms[room_id]
                    if room.is_full():
                        await conn.send_json({
                            "type": "error",
                            "message": f"La sala {room_id} ya está completa."
                        })
                        continue

                    p_idx = room.add_player(conn, team)
                    current_room = room
                    player_idx = p_idx
                    room.started = True

                    logger.info(f"Iniciando sala {room_id}: {room.teams[0]} vs {room.teams[1]}")

                    if room.players[0]:
                        await room.players[0].send_json({
                            "type": "match_start",
                            "room_id": room_id,
                            "player_idx": 0,
                            "teams": room.teams,
                            "opponent_team": room.teams[1]
                        })

                    await conn.send_json({
                        "type": "match_start",
                        "room_id": room_id,
                        "player_idx": 1,
                        "teams": room.teams,
                        "opponent_team": room.teams[0]
                    })

                elif action == "quick_match":
                    team = msg.get("team", "Alemania")
                    if self.waiting_quick_room and not self.waiting_quick_room.is_full():
                        room = self.waiting_quick_room
                        p_idx = room.add_player(conn, team)
                        current_room = room
                        player_idx = p_idx
                        self.waiting_quick_room = None
                        room.started = True

                        if room.players[0]:
                            await room.players[0].send_json({
                                "type": "match_start",
                                "room_id": room.room_id,
                                "player_idx": 0,
                                "teams": room.teams,
                                "opponent_team": room.teams[1]
                            })
                        await conn.send_json({
                            "type": "match_start",
                            "room_id": room.room_id,
                            "player_idx": 1,
                            "teams": room.teams,
                            "opponent_team": room.teams[0]
                        })
                    else:
                        room_id = self.generate_room_id()
                        room = GameRoom(room_id)
                        p_idx = room.add_player(conn, team)
                        self.rooms[room_id] = room
                        self.waiting_quick_room = room
                        current_room = room
                        player_idx = p_idx
                        await conn.send_json({
                            "type": "waiting_opponent",
                            "room_id": room_id,
                            "player_idx": 0,
                            "team": team
                        })

                elif action in ("shoot", "sync", "goal", "reset_round", "chat", "ability"):
                    if current_room:
                        current_room.last_activity = time.time()
                        opp = current_room.get_opponent(player_idx)
                        if opp:
                            msg["from_player"] = player_idx
                            await opp.send_json(msg)

                elif action == "ping":
                    await conn.send_json({"type": "pong", "time": time.time()})

        finally:
            conn.close()
            if current_room:
                idx = current_room.remove_player(conn)
                opp = current_room.get_opponent(idx)
                if opp:
                    await opp.send_json({
                        "type": "opponent_disconnected",
                        "message": "Tu rival se ha desconectado."
                    })
                if current_room.is_empty():
                    if self.waiting_quick_room == current_room:
                        self.waiting_quick_room = None
                    self.rooms.pop(current_room.room_id, None)


async def main():
    server_mgr = UnifiedServer()
    server = await asyncio.start_server(server_mgr.handle_request, "0.0.0.0", 80)
    logger.info("=== Servidor llamoca.enlace.ink activo en puerto 80 ===")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Servidor detenido.")
