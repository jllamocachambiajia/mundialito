#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo Multijugador (Local y Online) para Mundialito.
Permite jugar con 2 equipos simultáneamente en el mismo dispositivo o a través de la red (VPS).
"""

import math
import random
import time
from network import NetworkClient, DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT


class MultiplayerMixin:
    """Mixin que añade capacidades para 2 equipos (local y online en red) a Game."""

    def multiplayer_init(self):
        self.two_players = False       # Partida local 1P vs 2P en la misma pantalla
        self.online_match = False      # Partida online a través de red
        self.local_player_idx = 0      # 0 = Equipo 0, 1 = Equipo 1
        self.team2_index = 1           # Selección de país para el jugador 2
        self.net_client = None
        self.net_server_host = DEFAULT_SERVER_HOST
        self.net_server_port = DEFAULT_SERVER_PORT
        self.net_status_text = ""
        self.net_room_code = ""
        self.net_input_code = ""
        self.net_last_sync = 0.0
        self.drags = {}                # touch_id -> Body (para soporte multitouch)

    def is_two_player_mode(self):
        return getattr(self, 'two_players', False)

    def is_online_mode(self):
        return getattr(self, 'online_match', False)

    def is_human_team(self, team):
        """Determina si un equipo específico está controlado por un jugador humano."""
        if self.is_two_player_mode():
            return True
        if self.is_online_mode():
            return team == self.local_player_idx
        return team == 0  # Modo individual normal: solo equipo 0 es humano

    def is_cpu_team(self, team):
        """Determina si el equipo está controlado por la IA."""
        return not self.is_human_team(team)

    def setup_2p_local(self):
        """Abre la pantalla de configuración para 2 jugadores locales."""
        self.two_players = False
        self.online_match = False
        self.state = 'local_2p_select'
        self.render()

    def change_team2(self, delta):
        from main import TEAMS
        from mode_rules import next_country
        self.team2_index = next_country(getattr(self, 'team2_index', 1), delta, len(TEAMS))
        self.render()

    def start_local_two_player(self, team0, team1):
        """Inicia un partido de 2 jugadores en la misma pantalla."""
        self.two_players = True
        self.online_match = False
        self.local_player_idx = 0
        self.user = team0
        self.round = 0
        self.results = []
        self.start_match(team1)
        self.flash(f"¡2 JUGADORES!\n{team0} vs {team1}", 2.2)

    def draw_local_2p_select(self):
        """Pantalla de selección de selecciones para el modo 2 Jugadores en la misma pantalla."""
        from main import TEAMS, FULL_NAME
        w, h = self.cw, self.ch
        u = self.u
        teams_list = tuple(TEAMS)

        self.cv.create_rectangle(0, 0, w, h, fill='#052118', width=0)
        self.title(h * 0.12, "2 JUGADORES (LOCAL)", size=1.8, col='#ffd400')

        t1_idx = getattr(self, 'friend_index', 0) % len(teams_list)
        t2_idx = getattr(self, 'team2_index', 1) % len(teams_list)
        team1 = teams_list[t1_idx]
        team2 = teams_list[t2_idx]

        r = min(w * 0.16, h * 0.09)
        y_team = h * 0.40

        # --- Panel Jugador 1 ---
        cx1 = w * 0.28
        self.cv.create_text(cx1, y_team - r * 1.65, text="JUGADOR 1", fill='#63dbff',
                            font=self.front_font(u * 1.0, True))
        if hasattr(self, 'jersey'):
            self.jersey(cx1, y_team, r, team1, num=10)
        btn_s = min(42, max(34, w * 0.09))
        self.front_button(cx1 - r * 1.35, y_team, btn_s, btn_s, "<", lambda: self.change_friend(-1), '#dbefda')
        self.front_button(cx1 + r * 1.35, y_team, btn_s, btn_s, ">", lambda: self.change_friend(1), '#dbefda')
        name1 = FULL_NAME.get(team1, team1)
        self.cv.create_text(cx1, y_team + r * 1.35, text=name1, fill='#ffffff',
                            font=self.front_font(u * 0.85, False))

        # --- VS central ---
        self.cv.create_text(w * 0.5, y_team, text="VS", fill='#ffd400',
                            font=self.front_font(u * 1.8, True))

        # --- Panel Jugador 2 ---
        cx2 = w * 0.72
        self.cv.create_text(cx2, y_team - r * 1.65, text="JUGADOR 2", fill='#ff7939',
                            font=self.front_font(u * 1.0, True))
        if hasattr(self, 'jersey'):
            self.jersey(cx2, y_team, r, team2, num=10)
        self.front_button(cx2 - r * 1.35, y_team, btn_s, btn_s, "<", lambda: self.change_team2(-1), '#dbefda')
        self.front_button(cx2 + r * 1.35, y_team, btn_s, btn_s, ">", lambda: self.change_team2(1), '#dbefda')
        name2 = FULL_NAME.get(team2, team2)
        self.cv.create_text(cx2, y_team + r * 1.35, text=name2, fill='#ffffff',
                            font=self.front_font(u * 0.85, False))

        # Indicador de controles simultáneos
        self.cv.create_text(w / 2, h * 0.64,
                            text="¡Ambos jugadores pueden arrastrar y disparar al mismo tiempo!",
                            fill='#7ee0b3', font=self.front_font(u * 0.75, False))

        # Botón INICIAR PARTIDO
        bw = min(w * 0.8, 380)
        bh = min(56, max(44, h * 0.07))
        self.front_button(w / 2, h * 0.76, bw, bh, "¡INICIAR PARTIDO!",
                          lambda: self.start_local_two_player(team1, team2), '#35c759')

        # Botón Volver
        self.front_button(w / 2, h * 0.88, min(w * 0.5, 220), min(44, bh), "VOLVER AL MENÚ",
                          lambda: setattr(self, 'state', 'home') or self.render(), '#e64646')

    def start_online_lobby(self):
        """Abre la pantalla de lobby multijugador."""
        self.two_players = False
        self.online_match = False
        self.state = 'online_lobby'
        self.net_status_text = "Selecciona una opción para conectar"
        self.net_room_code = ""
        self.net_input_code = ""
        if self.net_client:
            self.net_client.disconnect()
            self.net_client = None
        self.render()

    def connect_online_server(self):
        """Asegura la conexión con el servidor en el VPS."""
        if self.net_client and self.net_client.connected:
            return True
        self.net_status_text = f"Conectando a {self.net_server_host}..."
        self.net_client = NetworkClient(
            host=self.net_server_host,
            port=self.net_server_port,
            use_ssl=(self.net_server_port == 443)
        )
        self.net_client.connect()
        return True

    def online_create_room(self, team_name):
        self.connect_online_server()
        self.net_status_text = "Creando sala en el servidor..."
        self.render()
        # Se envía la solicitud al recibir confirmación de conexión

    def online_join_room(self, room_id, team_name):
        if not room_id:
            self.net_status_text = "Ingresa un código de 4 dígitos."
            self.render()
            return
        self.connect_online_server()
        self.net_status_text = f"Buscando sala {room_id}..."
        self.render()

    def multiplayer_tick(self):
        """Procesa mensajes de red en cada tick del juego."""
        if not self.net_client:
            return

        for msg in self.net_client.poll_messages():
            mtype = msg.get("type")

            if mtype == "connected":
                self.net_status_text = "¡Conectado al servidor!"
                if self.state == 'online_lobby_waiting':
                    self.net_client.create_room(self.selected_country or "Argentina")
                elif self.state == 'online_lobby_joining':
                    self.net_client.join_room(self.net_input_code, self.selected_country or "Brasil")
                self.render()

            elif mtype == "connection_error":
                self.net_status_text = f"Error de conexión: {msg.get('error', '')}"
                self.render()

            elif mtype == "room_created":
                self.net_room_code = msg.get("room_id", "")
                self.local_player_idx = 0
                self.net_status_text = f"SALA LISTA: {self.net_room_code}\nEsperando a que el rival se una..."
                self.render()

            elif mtype == "waiting_opponent":
                self.net_room_code = msg.get("room_id", "")
                self.local_player_idx = 0
                self.net_status_text = f"Buscando oponente rápido en línea...\n(Código: {self.net_room_code})"
                self.render()

            elif mtype == "match_start":
                teams = msg.get("teams", ["Argentina", "Brasil"])
                self.local_player_idx = msg.get("player_idx", 0)
                self.online_match = True
                self.two_players = False
                self.user = teams[0]
                self.round = 0
                self.results = []
                self.start_match(teams[1])
                rol = "LOCAL" if self.local_player_idx == 0 else "VISITANTE"
                self.flash(f"¡PARTIDO INICIADO! ({rol})\n{teams[0]} vs {teams[1]}", 2.5)

            elif mtype == "shoot":
                if self.state == "match" and msg.get("from_player") != self.local_player_idx:
                    body_idx = msg.get("body_idx")
                    vx = msg.get("vx", 0.0)
                    vy = msg.get("vy", 0.0)
                    if 0 <= body_idx < len(self.bodies):
                        body = self.bodies[body_idx]
                        self.shoot(body, vx, vy)

            elif mtype == "sync":
                if self.state == "match" and self.local_player_idx == 1:
                    # Invitado sincroniza suavemente el balón con el host
                    ball_data = msg.get("ball")
                    if ball_data and len(ball_data) == 4:
                        bx, by, bvx, bvy = ball_data
                        # Si hay discrepancia apreciable, ajustar suavemente
                        if math.hypot(self.ball.x - bx, self.ball.y - by) > 8:
                            self.ball.x = bx
                            self.ball.y = by
                            self.ball.vx = bvx
                            self.ball.vy = bvy

            elif mtype == "opponent_disconnected":
                if self.state in ("match", "pens"):
                    self.flash("¡Tu rival se ha desconectado!", 3.0)
                    self.post_txt = "RIVAL DESCONECTADO (VICTORIA)"
                    self.post_w = self.teams[self.local_player_idx]
                    self.match_over()

            elif mtype == "error":
                self.net_status_text = msg.get("message", "Error del servidor")
                self.render()

        # Si estamos en partido online y somos el Host, enviar sync periódica cada 0.8 s
        if self.is_online_mode() and self.state == "match" and self.local_player_idx == 0:
            now = time.monotonic()
            if now - self.net_last_sync > 0.8:
                self.net_last_sync = now
                self.net_client.send_sync(
                    self.ball.x, self.ball.y, self.ball.vx, self.ball.vy,
                    self.clock, self.score
                )

    def draw_online_lobby(self):
        """Dibuja el menú de emparejamiento online."""
        w, h = self.cw, self.ch
        u = self.u
        self.cv.create_rectangle(0, 0, w, h, fill='#052118', width=0)

        self.title(h * 0.12, "MULTIJUGADOR EN LÍNEA", size=1.8, col='#ffd400')

        self.cv.create_text(
            w / 2, h * 0.22,
            text=f"Servidor: {self.net_server_host}:{self.net_server_port}",
            fill='#7ee0b3', font=self.front_font(u * 0.9, False)
        )

        bw = min(w * 0.75, 380)
        bh = min(54, max(42, h * 0.065))

        # Botones de acción
        self.front_button(
            w / 2, h * 0.35, bw, bh, "CREAR SALA PRIVADA",
            self._action_create_room, '#35c759'
        )

        self.front_button(
            w / 2, h * 0.46, bw, bh, "PARTIDA RÁPIDA",
            self._action_quick_match, '#ff9500'
        )

        # Entrada de código de sala
        self.front_button(
            w / 2, h * 0.57, bw, bh,
            f"UNIRSE CON CÓDIGO {('[' + self.net_input_code + ']') if self.net_input_code else ''}",
            self._action_join_dialog, '#007aff'
        )

        # Teclado numérico rápido si está escribiendo código
        if getattr(self, '_typing_code', False):
            self._draw_numpad(w, h, u)

        # Mensaje de estado del servidor
        if self.net_status_text:
            self.cv.create_text(
                w / 2, h * 0.76, text=self.net_status_text,
                fill='#ffffff', font=self.front_font(u * 1.0, False), width=w * 0.9
            )

        # Botón Volver
        self.front_button(
            w / 2, h * 0.90, min(w * 0.5, 240), min(46, bh), "VOLVER AL MENÚ",
            self._action_back_home, '#e64646'
        )

    def _draw_numpad(self, w, h, u):
        btn_s = min(45, w * 0.12)
        start_x = w / 2 - btn_s * 1.6
        start_y = h * 0.63
        for digit in range(1, 10):
            r = (digit - 1) // 3
            c = (digit - 1) % 3
            x = start_x + c * (btn_s + 8)
            y = start_y + r * (btn_s + 6)
            self._digit_btn(x, y, btn_s, str(digit))
        # Botón 0 y borrar
        x0 = start_x + 1 * (btn_s + 8)
        y0 = start_y + 3 * (btn_s + 6)
        self._digit_btn(x0, y0, btn_s, "0")
        xb = start_x + 2 * (btn_s + 8)
        self._digit_btn(xb, y0, btn_s, "<", is_del=True)

    def _digit_btn(self, x, y, size, label, is_del=False):
        def on_press():
            if is_del:
                self.net_input_code = self.net_input_code[:-1]
            elif len(self.net_input_code) < 4:
                self.net_input_code += label
                if len(self.net_input_code) == 4:
                    self._action_submit_join()
            self.render()

        self.buttons.append((x - size / 2, y - size / 2, x + size / 2, y + size / 2, on_press))
        self.cv.create_oval(
            x - size / 2, y - size / 2, x + size / 2, y + size / 2,
            fill='#1b3f30', outline='#7ee0b3', width=1.5
        )
        self.cv.create_text(
            x, y, text=label, fill='#ffffff',
            font=self.front_font(self.u * 1.1, True)
        )

    def _action_create_room(self):
        self._typing_code = False
        self.state = 'online_lobby_waiting'
        self.connect_online_server()
        if self.net_client and self.net_client.connected:
            self.net_client.create_room(self.selected_country or "Argentina")
        self.net_status_text = "Generando código de sala..."
        self.render()

    def _action_quick_match(self):
        self._typing_code = False
        self.state = 'online_lobby_waiting'
        self.connect_online_server()
        if self.net_client and self.net_client.connected:
            self.net_client.quick_match(self.selected_country or "Alemania")
        self.net_status_text = "Buscando partida..."
        self.render()

    def _action_join_dialog(self):
        self._typing_code = not getattr(self, '_typing_code', False)
        if not self.net_input_code:
            self.net_status_text = "Toca los números para ingresar el código de 4 dígitos"
        self.render()

    def _action_submit_join(self):
        self._typing_code = False
        self.state = 'online_lobby_joining'
        self.connect_online_server()
        if self.net_client and self.net_client.connected:
            self.net_client.join_room(self.net_input_code, self.selected_country or "Brasil")
        self.net_status_text = f"Conectando a sala {self.net_input_code}..."
        self.render()

    def _action_back_home(self):
        self._typing_code = False
        if self.net_client:
            self.net_client.disconnect()
            self.net_client = None
        self.state = 'home'
        self.render()
