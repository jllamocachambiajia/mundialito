#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente de Red WebSocket para Mundialito.
Se ejecuta en un hilo secundario y entrega eventos de forma thread-safe a Kivy.
"""

import base64
import json
import logging
import os
import queue
import random
import socket
import ssl
import struct
import threading
import time

logger = logging.getLogger("MundialitoNetwork")

DEFAULT_SERVER_HOST = "Llamoca.enlace.ink"
DEFAULT_SERVER_PORT = 8765


class NetworkClient:
    """Cliente WebSocket asíncrono en hilo de fondo para no bloquear el loop gráfico."""

    def __init__(self, host=DEFAULT_SERVER_HOST, port=DEFAULT_SERVER_PORT, use_ssl=False):
        self.host = host
        self.port = int(port)
        self.use_ssl = use_ssl
        self.sock = None
        self.running = False
        self.thread = None
        self.inbox = queue.Queue()
        self.connected = False
        self.player_idx = None   # 0 = Host (Local), 1 = Invitado (Visitante)
        self.room_id = None
        self.opponent_team = None

    def connect(self):
        """Inicia la conexión en segundo plano."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def disconnect(self):
        """Cierra la conexión y detiene el hilo."""
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _worker_loop(self):
        try:
            raw_sock = socket.create_connection((self.host, self.port), timeout=6.0)
            if self.use_ssl or self.port == 443:
                context = ssl.create_default_context()
                self.sock = context.wrap_socket(raw_sock, server_hostname=self.host)
            else:
                self.sock = raw_sock

            # Handshake WebSocket
            key = base64.b64encode(os.urandom(16)).decode('utf-8')
            req = (
                f"GET / HTTP/1.1\r\n"
                f"Host: {self.host}:{self.port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            )
            self.sock.sendall(req.encode('utf-8'))

            # Leer respuesta
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = self.sock.recv(1024)
                if not chunk:
                    raise ConnectionError("Servidor cerró conexión antes del handshake.")
                resp += chunk

            status_line = resp.split(b"\r\n")[0]
            if b"101" not in status_line:
                raise ConnectionError(f"Error en handshake: {status_line.decode('utf-8', errors='ignore')}")

            self.connected = True
            self.inbox.put({"type": "connected", "host": self.host, "port": self.port})

            # Bucle de recepción de frames
            while self.running:
                head = self._recv_exact(2)
                if not head:
                    break
                b1, b2 = head[0], head[1]
                opcode = b1 & 0x0F
                masked = (b2 & 0x80) != 0
                payload_len = b2 & 0x7F

                if opcode == 0x8:  # Close
                    break
                elif opcode == 0x9:  # Ping
                    pong = bytearray([0x8A, 0])
                    self.sock.sendall(pong)
                    continue

                if payload_len == 126:
                    payload_len = struct.unpack("!H", self._recv_exact(2))[0]
                elif payload_len == 127:
                    payload_len = struct.unpack("!Q", self._recv_exact(8))[0]

                mask_key = self._recv_exact(4) if masked else None
                payload = self._recv_exact(payload_len)

                if masked:
                    unmasked = bytearray(payload_len)
                    for i in range(payload_len):
                        unmasked[i] = payload[i] ^ mask_key[i % 4]
                    payload = bytes(unmasked)

                try:
                    data = json.loads(payload.decode('utf-8'))
                    self._handle_internal_msg(data)
                    self.inbox.put(data)
                except Exception as e:
                    logger.warning(f"Error parseando mensaje: {e}")

        except Exception as e:
            self.inbox.put({"type": "connection_error", "error": str(e)})
        finally:
            self.connected = False
            self.running = False
            self.inbox.put({"type": "disconnected"})

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def send_json(self, data):
        """Envía un frame de texto WebSocket enmascarado (cliente a servidor)."""
        if not self.connected or not self.sock:
            return False
        try:
            raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
            length = len(raw)
            header = bytearray([0x81])  # Text frame

            mask_bit = 0x80
            if length <= 125:
                header.append(mask_bit | length)
            elif length <= 65535:
                header.append(mask_bit | 126)
                header.extend(struct.pack("!H", length))
            else:
                header.append(mask_bit | 127)
                header.extend(struct.pack("!Q", length))

            mask_key = os.urandom(4)
            header.extend(mask_key)

            masked = bytearray(length)
            for i in range(length):
                masked[i] = raw[i] ^ mask_key[i % 4]

            self.sock.sendall(header + masked)
            return True
        except Exception:
            self.connected = False
            return False

    def _handle_internal_msg(self, data):
        mtype = data.get("type")
        if mtype in ("room_created", "match_start"):
            self.room_id = data.get("room_id")
            if "player_idx" in data:
                self.player_idx = data["player_idx"]
            if "opponent_team" in data:
                self.opponent_team = data["opponent_team"]

    def create_room(self, team_name):
        return self.send_json({"action": "create_room", "team": team_name})

    def join_room(self, room_id, team_name):
        return self.send_json({"action": "join_room", "room_id": room_id, "team": team_name})

    def quick_match(self, team_name):
        return self.send_json({"action": "quick_match", "team": team_name})

    def send_shoot(self, body_idx, vx, vy, is_keeper=False):
        return self.send_json({
            "action": "shoot",
            "body_idx": body_idx,
            "vx": float(vx),
            "vy": float(vy),
            "is_keeper": bool(is_keeper)
        })

    def send_sync(self, ball_x, ball_y, ball_vx, ball_vy, clock_val, score):
        return self.send_json({
            "action": "sync",
            "ball": [float(ball_x), float(ball_y), float(ball_vx), float(ball_vy)],
            "clock": float(clock_val),
            "score": list(score)
        })

    def send_goal(self, scoring_team):
        return self.send_json({
            "action": "goal",
            "scoring_team": int(scoring_team)
        })

    def poll_messages(self):
        """Retorna todos los mensajes acumulados en la cola sin bloquear."""
        msgs = []
        while not self.inbox.empty():
            try:
                msgs.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        return msgs
