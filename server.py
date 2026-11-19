#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor Multijugador para Mundialito (Copa Mundial de Chapas).
Diseñado para ejecutarse en un VPS (por ejemplo en Llamoca.enlace.ink).
Permite que dos equipos/dispositivos jueguen simultáneamente en tiempo real.

Características:
- Implementación ligera y asíncrona sobre asyncio.
- Soporte para protocolo WebSocket nativo (RFC 6455) y mensajes JSON.
- Gestión de salas privadas por código (PIN de 4 dígitos) y emparejamiento rápido.
- Sincronización de disparos, posiciones periódicas, marcador y eventos.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import struct
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("MundialitoServer")

MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketConnection:
    """Manejador de conexión WebSocket RFC 6455 sobre asyncio stream."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.peername = writer.get_extra_info('peername')
        self.closed = False

    async def handshake(self):
        """Lee la solicitud HTTP inicial y completa el handshake WebSocket."""
        header_data = b""
        while b"\r\n\r\n" not in header_data:
            chunk = await self.reader.read(1024)
            if not chunk:
                return False
            header_data += chunk
            if len(header_data) > 8192:
                return False

        lines = header_data.decode("utf-8", errors="ignore").split("\r\n")
        ws_key = None
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                if k.strip().lower() == "sec-websocket-key":
                    ws_key = v.strip()
                    break

        if not ws_key:
            # Petición HTTP estándar de comprobación / health check
            resp = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n"
                "Content-Length: 35\r\n"
                "Connection: close\r\n\r\n"
                "Mundialito Multiplayer Server OK\n"
            )
            self.writer.write(resp.encode("utf-8"))
            await self.writer.drain()
            self.writer.close()
            return False

        accept_val = base64.b64encode(
            hashlib.sha1((ws_key + MAGIC_GUID).encode("utf-8")).digest()
        ).decode("utf-8")

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_val}\r\n\r\n"
        )
        self.writer.write(response.encode("utf-8"))
        await self.writer.drain()
        return True

    async def recv_json(self):
        """Lee un frame de texto WebSocket y lo decodifica como JSON."""
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

            if opcode == 0x8:  # Close frame
                self.closed = True
                return None
            elif opcode == 0x9:  # Ping frame
                # Responder pong
                pong = bytearray([0x8A, 0])
                self.writer.write(pong)
                await self.writer.drain()
                continue
            elif opcode == 0xA:  # Pong
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
            except Exception as e:
                logger.warning(f"Error decodificando payload JSON: {e}")
                return None

    async def send_json(self, data):
        """Codifica y envía un mensaje JSON en un frame WebSocket no enmascarado."""
        if self.closed:
            return False
        try:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            length = len(raw)
            header = bytearray([0x81])  # Fin + Text frame

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
    """Representa una sala de partido 1 vs 1 entre dos jugadores."""

    def __init__(self, room_id):
        self.room_id = room_id
        self.players = [None, None]  # [Player 0 (Host), Player 1 (Guest)]
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


class MatchmakingServer:
    """Servidor global que gestiona conexiones y salas de juego."""

    def __init__(self):
        self.rooms = {}  # room_id -> GameRoom
        self.waiting_quick_room = None

    def generate_room_id(self):
        while True:
            code = f"{random.randint(1000, 9999)}"
            if code not in self.rooms:
                return code

    async def handle_client(self, reader, writer):
        conn = WebSocketConnection(reader, writer)
        ok = await conn.handshake()
        if not ok:
            return

        current_room = None
        player_idx = -1
        logger.info(f"Nuevo cliente conectado desde {conn.peername}")

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
                    logger.info(f"Sala {room_id} creada por {conn.peername} (Equipo: {team})")

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
                            "message": f"La sala {room_id} ya está llena."
                        })
                        continue

                    p_idx = room.add_player(conn, team)
                    current_room = room
                    player_idx = p_idx

                    # Iniciar partido para ambos
                    room.started = True
                    logger.info(f"Partido iniciado en sala {room_id}: {room.teams[0]} vs {room.teams[1]}")

                    # Notificar al host (Player 0)
                    if room.players[0]:
                        await room.players[0].send_json({
                            "type": "match_start",
                            "room_id": room_id,
                            "player_idx": 0,
                            "teams": room.teams,
                            "opponent_team": room.teams[1]
                        })

                    # Notificar al invitado (Player 1)
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
                    # Retransmitir al oponente
                    if current_room:
                        current_room.last_activity = time.time()
                        opp = current_room.get_opponent(player_idx)
                        if opp:
                            msg["from_player"] = player_idx
                            await opp.send_json(msg)

                elif action == "ping":
                    await conn.send_json({"type": "pong", "time": time.time()})

        except Exception as e:
            logger.error(f"Excepción en cliente {conn.peername}: {e}")
        finally:
            conn.close()
            if current_room:
                idx = current_room.remove_player(conn)
                logger.info(f"Jugador {idx} salió de la sala {current_room.room_id}")
                opp = current_room.get_opponent(idx)
                if opp:
                    await opp.send_json({
                        "type": "opponent_disconnected",
                        "message": "Tu rival se ha desconectado del partido."
                    })
                if current_room.is_empty():
                    if self.waiting_quick_room == current_room:
                        self.waiting_quick_room = None
                    self.rooms.pop(current_room.room_id, None)
                    logger.info(f"Sala {current_room.room_id} eliminada.")


async def main_server(host="0.0.0.0", port=8765):
    server_mgr = MatchmakingServer()
    server = await asyncio.start_server(server_mgr.handle_client, host, port)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f"=== Servidor Mundialito iniciado en {addrs} ===")
    logger.info(f"Listo para recibir conexiones en ws://{host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    host = os.environ.get("HOST", "0.0.0.0")
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    try:
        asyncio.run(main_server(host, port))
    except KeyboardInterrupt:
        logger.info("Servidor detenido manualmente.")
