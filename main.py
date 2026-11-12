#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COPA MUNDIAL DE CHAPAS  v11 APK  -  Python 3 + Kivy (empaquetable como APK con Buildozer)
Funciona en PC y en Android (Pydroid 3). Se adapta a cualquier pantalla:
en vertical la cancha se gira para aprovechar el espacio.

Controles: toca/haz clic sobre una de tus fichas, arrastra hacia donde quieras
tirar (más lejos = más potencia) y suelta.
v4 - JUEGO LIBRE: no hay turnos. Cualquier equipo puede tirar en cualquier momento,
con recarga INDEPENDIENTE de 1 s por equipo (sin congelar el balón ni la física).
Solo el saque inicial es exclusivo del equipo que saca.
Tiempo a escala (v7): 90 min = 5 min reales (cada tiempo 2:30); prórroga 20 min ~ 1:07
(dos periodos de ~33,3 s).
Penales: cuenta 3-2-1-¡PREPÁRATE!; apunta con A/D o flechas (PC) o con los
botones táctiles bajo la portería (celular).
v3: celebraciones sonoras propias de cada selección, zona táctil ampliada
y dorsales aleatorios (el arquero siempre lleva el 1).
v7: 24 selecciones (8 nuevas con bandera, camiseta, uniforme de arquero y sonido propio),
control avanzado del arquero (botón ARQUERO: cámara lenta x0,75, DASH lateral con barra de
potencia, estela y posesión del balón tras atajar), DASH también en los penales,
y 15 % menos deslizamiento de las fichas.
v8: en partido y prórroga el arquero se arrastra como cualquier ficha (sin botón ni flechas);
al agarrarlo el juego va al 50 % hasta que el arquero toca el balón y este rebota.
El arquero no puede salir de su área grande (barrera invisible solo para él), su potencia
máxima es la mitad de la de un jugador de campo y tiene su propia recarga de 1 s.
IA rival separada: arquero que lee la trayectoria del balón y jugadores de campo que
pasan, atacan, defienden y rematan con potencia variable. Los penales no cambian.
v9: música de fondo (musica_fondo.mp3 junto a main.py) con fade-in al 15 % y fade-out en
penales, y botón de PAUSA (CONTINUAR / REINICIAR TORNEO) que congela todo, también la música.
"""
import math
import random
import time

# ------------------------------------------------------------------ mundo (coordenadas lógicas)
FX0, FY0, FX1, FY1 = 60, 80, 1040, 680          # campo
MY = (FY0 + FY1) / 2
GOAL_H = 140
GY0, GY1 = MY - GOAL_H / 2, MY + GOAL_H / 2      # palos
GD = 40                                          # profundidad portería
WX0, WX1, WY0, WY1 = FX0 - GD - 10, FX1 + GD + 10, FY0 - 12, FY1 + 12   # zona visible
RW, RH = WX1 - WX0, WY1 - WY0
PR, BR = 18, 10                                  # radios ficha / balón
PM, BM = 3.0, 1.0                                # masas
FRICTION = 0.985                                 # balón (sin cambios)
# v7: 15 % menos deslizamiento en las fichas (la distancia que resbalan baja un 15 %)
PLAYER_FRICTION = 1 - (1 - FRICTION) / 0.85
SUB = 4
MAX_DRAG = 160
POWER = 0.14
# Tiempo a escala (regla de tres): 90 min de fútbol = 300 s reales -> 1 min = 3,33 s reales
REAL_PER_MIN = 300.0 / 90.0
HALF_REAL = 45 * REAL_PER_MIN                    # 150 s = 2:30
ET_REAL = 20 * REAL_PER_MIN                      # 66,7 s ~ 1:07 (2 x 33,3 s)
MARKS = [HALF_REAL, 2 * HALF_REAL, 2 * HALF_REAL + ET_REAL / 2, 2 * HALF_REAL + ET_REAL]
COOLDOWN = 1.0                                   # recarga propia de cada equipo (s)
CD_STEP = 0.8                                    # duración de cada número del conteo de penales
PEN_GOAL_SCALE = 1.5
PEN_GY0, PEN_GY1 = MY - GOAL_H * PEN_GOAL_SCALE / 2, MY + GOAL_H * PEN_GOAL_SCALE / 2
PEN_GD = GD * PEN_GOAL_SCALE
PEN_WX1 = FX1 + PEN_GD + 10
PEN_X0 = FX1 - 330                               # zona visible en penales
# --- v7: arquero
SMALL_W, SMALL_H = 55, 70                        # área chica (profundidad, media altura)
GK_OUT_SPEED = 0.10                              # fuera del área chica: 10 % de su velocidad
SLOWMO = 0.75                                    # cámara lenta del arquero en PENALES (sin cambios)
# --- v8: arquero en partido / prórroga
SLOWMO_MATCH = 0.50                              # cámara lenta al arrastrar al arquero
BIG_W, BIG_H = 150, 150                          # área grande (profundidad, media altura): barrera
GK_POWER = 0.50 # potencia máxima del arquero = 50 % de la de campo
# --- v10: IA del arquero CPU
GK_CPU_SPEED = 7.0                               # velocidad normal (px por fotograma)
GK_CPU_SPEED_URGENT = 12.0                       # al lanzarse a un tiro
GK_CPU_BRAKE = 0.25                              # frena al acercarse a su objetivo
GK_CPU_ACCEL = 0.25                              # aceleración suave por fotograma
GK_SLOW_MAX = 3.0                                # seguro: s reales máx. de cámara lenta tras soltar
DASH_CHARGE = 0.5                                # s para llegar a potencia máxima
DASH_MIN, DASH_MAX = 22, 150                     # distancia del DASH (mundo)
DASH_V_MIN, DASH_V_MAX = 8.0, 17.0               # velocidad del DASH (mundo / fotograma)
# --- v9: música de fondo (ajusta estos valores a tu gusto)
MUSIC_FILE = "assets/sounds/music/musica_fondo.mp3"                  # debe estar en la misma carpeta que main.py
MUSIC_VOL = 0.15                                 # volumen objetivo: 15 % del máximo del archivo
MUSIC_PEN_VOL = 0.05                             # en penales baja (fade-out) hasta este nivel
MUSIC_FADE_IN = 4.0                              # s del fade-in al empezar el partido
MUSIC_FADE_OUT = 3.0                             # s del fade-out al llegar a los penales
MUSIC_END_FADE = 2.0                             # s del fade final al terminar el partido

# Reloj de juego (v9): igual que time.monotonic() pero se detiene mientras hay PAUSA,
# así cronómetro, recargas, conteos, cámara lenta y mensajes siguen exactos al reanudar.
_PAUSE = {"total": 0.0, "since": None}


def vnow():
    t = time.monotonic()
    if _PAUSE["since"] is not None:
        t = _PAUSE["since"]
    return t - _PAUSE["total"]


def clock_pause(on):
    t = time.monotonic()
    if on and _PAUSE["since"] is None:
        _PAUSE["since"] = t
    elif not on and _PAUSE["since"] is not None:
        _PAUSE["total"] += t - _PAUSE["since"]
        _PAUSE["since"] = None


TRAIL_T = 0.35                                   # duración de cada imagen de la estela
# Gancho para el pase del arquero (se implementará aparte):
#   def mi_pase(game, keeper): ...  y luego  game.release_ball(vx, vy)
PASE_ARQUERO = None
PASE_DELAY_MS = 700

# Equipaciones: patrón, color 1, color 2, borde, rating, extra
# patrones: solid, vstripes, hoops, sash, half, checks, chestband
TEAMS = {
    "España":         ("chestband", "#ff1a2e", "#ffd400", "#ffd400", 88, ["#ffd400", "#ff1a2e", "#ffd400"]),
    "Francia":        ("chestband", "#2453ff", "#ffffff", "#ff2b3a", 90, ["#2453ff", "#ffffff", "#ff2b3a"]),
    "Alemania":       ("chestband", "#ffffff", "#111111", "#111111", 87, ["#222222", "#ff2020", "#ffcc00"]),
    "Inglaterra":     ("sash",      "#ffffff", "#ff1f3d", "#1d3cff", 88, None),
    "Italia":         ("chestband", "#1e90ff", "#ffffff", "#ffd700", 85, ["#00c853", "#ffffff", "#ff1744"]),
    "Portugal":       ("half",      "#ff1f3d", "#00c853", "#ffd400", 87, None),
    "Países Bajos":   ("solid",     "#ff7a00", "#ffffff", "#1b1b6b", 86, None),
    "Bélgica":        ("sash",      "#ff2020", "#ffd400", "#111111", 84, None),
    "Croacia":        ("checks",    "#ffffff", "#ff1f2f", "#1e4bff", 84, None),
    "Argentina":      ("vstripes",  "#ffffff", "#5ec8ff", "#1a2a6c", 91, None),
    "Brasil":         ("chestband", "#ffe600", "#00b84f", "#00b84f", 90, ["#00b84f", "#ffe600", "#2b5cff"]),
    "Uruguay":        ("solid",     "#4fc3ff", "#ffffff", "#ffffff", 83, None),
    "Colombia":       ("hoops",     "#ffd60a", "#2a5bff", "#ff1f3d", 82, None),
    "México":         ("sash",      "#00b560", "#ff2b3a", "#ffffff", 81, None),
    "Estados Unidos": ("hoops",     "#ffffff", "#ff2b3a", "#1f4dff", 80, None),
    "Chile":          ("half",      "#ff2a1f", "#1f55ff", "#ffffff", 79, None),
    # --- v7: 8 selecciones nuevas
    "Suecia":         ("chestband", "#ffd800", "#1a5cff", "#1a5cff", 80, ["#1a5cff", "#ffd800", "#1a5cff"]),
    "Dinamarca":      ("pinstripes", "#ff1f2f", "#ffffff", "#ffffff", 81, None),
    "Suiza":          ("cross",     "#ff1a1a", "#ffffff", "#ffffff", 80, None),
    "Polonia":        ("hhalf",     "#ffffff", "#ff1f3d", "#ff1f3d", 79, None),
    "Hungría":        ("chestband", "#ff2030", "#ffffff", "#00b050", 78, ["#ffffff", "#00c060", "#ffffff"]),
    "Paraguay":       ("vstripes",  "#ffffff", "#ff1f2f", "#1f4dff", 78, None),
    "Perú":           ("sash",      "#ffffff", "#ff1f2f", "#ff1f2f", 79, None),
    "Ecuador":        ("chestband", "#ffe100", "#1f4dff", "#1f4dff", 78, ["#1f4dff", "#ff1f2f", "#1f4dff"]),
}
ABBR = {"España": "ESP", "Francia": "FRA", "Alemania": "ALE", "Inglaterra": "ING", "Italia": "ITA",
        "Portugal": "POR", "Países Bajos": "PBA", "Bélgica": "BEL", "Croacia": "CRO",
        "Argentina": "ARG", "Brasil": "BRA", "Uruguay": "URU", "Colombia": "COL",
        "México": "MEX", "Estados Unidos": "USA", "Chile": "CHI",
        "Suecia": "SUE", "Dinamarca": "DIN", "Suiza": "SUI", "Polonia": "POL", "Hungría": "HUN",
        "Paraguay": "PAR", "Perú": "PER", "Ecuador": "ECU"}
# v7: nombre completo y nombre corto (espacios reducidos)
FULL_NAME = {t: f"Selección de {t}" for t in TEAMS}
FULL_NAME.update({"Países Bajos": "Selección de los Países Bajos",
                  "Estados Unidos": "Selección de los Estados Unidos"})
SHORT = {t: t for t in TEAMS}
SHORT.update({"Países Bajos": "P. Bajos", "Estados Unidos": "EE. UU."})
# v7: banderas  (tipo, franjas, detalles)
#   "h"/"v" = franjas horizontales/verticales; detalles: canton, dot, cross, nordic, swiss, diamond
FLAGS = {
    "España":         ("h", ["#c60b1e", "#ffc400", "#ffc400", "#c60b1e"], []),
    "Francia":        ("v", ["#0055a4", "#ffffff", "#ef4135"], []),
    "Alemania":       ("h", ["#000000", "#dd0000", "#ffce00"], []),
    "Inglaterra":     ("h", ["#ffffff"], [("cross", "#ce1124", 0.2)]),
    "Italia":         ("v", ["#009246", "#ffffff", "#ce2b37"], []),
    "Portugal":       ("v", ["#006600", "#006600", "#ff0000", "#ff0000", "#ff0000"], [("dot", "#ffcc00", 0.4, 0.5, 0.2)]),
    "Países Bajos":   ("h", ["#ae1c28", "#ffffff", "#21468b"], []),
    "Bélgica":        ("v", ["#000000", "#fdda24", "#ef3340"], []),
    "Croacia":        ("h", ["#ff0000", "#ffffff", "#171796"], [("dot", "#ff0000", 0.5, 0.5, 0.15)]),
    "Argentina":      ("h", ["#74acdf", "#ffffff", "#74acdf"], [("dot", "#f6b40e", 0.5, 0.5, 0.12)]),
    "Brasil":         ("h", ["#009c3b"], [("diamond", "#ffdf00"), ("dot", "#002776", 0.5, 0.5, 0.2)]),
    "Uruguay":        ("h", ["#ffffff", "#0038a8"] * 4 + ["#ffffff"], [("canton", "#ffffff", 0.4, 5 / 9),
                                                                         ("dot", "#fcd116", 0.2, 0.28, 0.14)]),
    "Colombia":       ("h", ["#fcd116", "#fcd116", "#003893", "#ce1126"], []),
    "México":         ("v", ["#006847", "#ffffff", "#ce1126"], [("dot", "#8b5a2b", 0.5, 0.5, 0.13)]),
    "Estados Unidos": ("h", ["#b22234", "#ffffff"] * 3 + ["#b22234"], [("canton", "#3c3b6e", 0.42, 4 / 7)]),
    "Chile":          ("h", ["#ffffff", "#d52b1e"], [("canton", "#0039a6", 1 / 3, 0.5), ("dot", "#ffffff", 1 / 6, 0.25, 0.1)]),
    "Suecia":         ("h", ["#006aa7"], [("nordic", "#fecc00", 0.2)]),
    "Dinamarca":      ("h", ["#c8102e"], [("nordic", "#ffffff", 0.14)]),
    "Suiza":          ("h", ["#ff0000"], [("swiss", "#ffffff")]),
    "Polonia":        ("h", ["#ffffff", "#dc143c"], []),
    "Hungría":        ("h", ["#cd2a3e", "#ffffff", "#436f4d"], []),
    "Paraguay":       ("h", ["#d52b1e", "#ffffff", "#0038a8"], [("dot", "#fcd116", 0.5, 0.5, 0.11)]),
    "Perú":           ("v", ["#d91023", "#ffffff", "#d91023"], []),
    "Ecuador":        ("h", ["#ffdd00", "#ffdd00", "#034ea2", "#ed1c24"], [("dot", "#8b5a2b", 0.5, 0.5, 0.12)]),
}
# v7: uniforme propio del arquero para las nuevas selecciones (base, franja, borde).
# Las 16 originales conservan su uniforme de arquero de siempre.
GK_KIT = {
    "Suecia":    ("#9b4dff", "#ffd800", "#ffd800"),
    "Dinamarca": ("#00e5ff", "#111111", "#ff1f2f"),
    "Suiza":     ("#28d17c", "#ffffff", "#c40000"),
    "Polonia":   ("#00d26a", "#ffffff", "#111111"),
    "Hungría":   ("#ffb000", "#111111", "#111111"),
    "Paraguay":  ("#ff8c00", "#1f4dff", "#ffffff"),
    "Perú":      ("#2ad4ff", "#ff1f2f", "#ffffff"),
    "Ecuador":   ("#ff3fa4", "#ffffff", "#1f4dff"),
}

# ------------------------------------------------------------------ SONIDO (sintetizado aquí mismo)
# Todos los sonidos se generan matemáticamente al ejecutar el juego: son 100 % originales,
# sin archivos externos ni derechos de autor. Melodías inventadas para este juego.
import os
import sys
sys.modules.setdefault("main", sys.modules[__name__])
import wave
import array
import tempfile
import threading
import subprocess

# ====================================================================== capa Kivy
# El juego original usaba tkinter. Para que pueda empaquetarse como APK (Buildozer /
# python-for-android no incluye tkinter), esta capa imita la parte de tkinter que usa
# el juego (Canvas, after, bind) dibujando con Kivy. La lógica, la física y las
# mecánicas del juego son exactamente las mismas.
import os as _os
_os.environ.setdefault("KIVY_NO_ARGS", "1")
_os.environ.setdefault("KIVY_LOG_MODE", "PYTHON")
from kivy.app import App as _App
from kivy.clock import Clock as _Clock
from kivy.core.window import Window as _Window
from kivy.core.text import Label as _CoreLabel
from kivy.uix.widget import Widget as _Widget
from kivy.graphics import (Color as _Color, Rectangle as _Rect, Ellipse as _Ellipse,
                           Line as _Line, Mesh as _Mesh)

_COL_CACHE = {}


def _rgb(c):
    if not c:
        return None
    if c in _COL_CACHE:
        return _COL_CACHE[c]
    h = c.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    try:
        v = (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)
    except ValueError:
        v = {"white": (1, 1, 1), "black": (0, 0, 0)}.get(c, (1, 1, 1))
    _COL_CACHE[c] = v
    return v


class _Ev:
    def __init__(self, x=0, y=0, width=0, height=0):
        self.x, self.y, self.width, self.height = x, y, width, height


class _TclError(Exception):
    pass


class _CanvasWidget(_Widget):
    """Lienzo con la misma interfaz que tk.Canvas (lo que usa el juego).
    Coordenadas como tkinter: origen arriba a la izquierda, y hacia abajo."""
    TEX = {}

    def __init__(self, root, **kw):
        super().__init__(**kw)
        self.root = root
        self.handlers = {}
        self.bind(size=self._resized)

    # --- tk API
    def pack(self, **kw):
        pass

    def bind(self, *a, **kw):
        if a and isinstance(a[0], str) and a[0].startswith("<"):
            self.handlers[a[0]] = a[1]
            return
        return super().bind(*a, **kw)

    def winfo_width(self):
        return int(self.width)

    def winfo_height(self):
        return int(self.height)

    def delete(self, what="all"):
        self.canvas.clear()

    def cached(self, key, draw):
        from kivy.graphics import Canvas
        if not hasattr(self, '_groups'):
            self._groups = {}
        group = self._groups.get(key)
        if group is None:
            target = self.canvas
            group = Canvas()
            self.canvas = group
            try:
                draw()
            finally:
                self.canvas = target
            if len(self._groups) > 160:
                self._groups.clear()
            self._groups[key] = group
        self.canvas.add(group)

    def _Y(self, y):
        return self.height - y

    def _wd(self, kw, default=1.0):
        w = kw.get("width", default)
        return float(w) if w else 0.0

    def create_rectangle(self, x0, y0, x1, y1, fill="", outline="#000000", width=1, **kw):
        xa, xb = min(x0, x1), max(x0, x1)
        ya, yb = self._Y(max(y0, y1)), self._Y(min(y0, y1))
        with self.canvas:
            f = _rgb(fill)
            if f:
                _Color(*f, kw.get("alpha", 1.0))
                _Rect(pos=(xa, ya), size=(xb - xa, yb - ya))
            w = float(width or 0)
            o = _rgb(outline)
            if w > 0 and o:
                _Color(*o)
                _Line(rectangle=(xa, ya, xb - xa, yb - ya), width=max(1.0, w / 2), joint="miter")

    def create_oval(self, x0, y0, x1, y1, fill="", outline="#000000", width=1, **kw):
        xa, xb = min(x0, x1), max(x0, x1)
        ya, yb = self._Y(max(y0, y1)), self._Y(min(y0, y1))
        with self.canvas:
            f = _rgb(fill)
            if f:
                _Color(*f, kw.get("alpha", 1.0))
                _Ellipse(pos=(xa, ya), size=(xb - xa, yb - ya))
            w = float(width or 0)
            o = _rgb(outline)
            if w > 0 and o:
                _Color(*o)
                _Line(ellipse=(xa, ya, xb - xa, yb - ya), width=max(1.0, w / 2))

    def create_polygon(self, flat, fill="#000000", outline="", width=1, **kw):
        pts = [(flat[i], self._Y(flat[i + 1])) for i in range(0, len(flat) - 1, 2)]
        if len(pts) < 3:
            return
        with self.canvas:
            f = _rgb(fill)
            if f:                                 # los polígonos del juego son convexos
                verts = []
                for x, y in pts:
                    verts += [x, y, 0, 0]
                _Color(*f, kw.get('alpha', 1.0))
                _Mesh(vertices=verts, indices=list(range(len(pts))), mode="triangle_fan")
            w = float(width or 0)
            o = _rgb(outline)
            if w > 0 and o:
                line = []
                for x, y in pts:
                    line += [x, y]
                _Color(*o)
                _Line(points=line, width=max(1.0, w / 2), close=True, joint="miter")

    def create_line(self, *coords, fill="#000000", width=1, arrow=None, arrowshape=None, dash=None, **kw):
        if len(coords) == 1:
            coords = coords[0]
        x0, y0, x1, y1 = coords[0], self._Y(coords[1]), coords[2], self._Y(coords[3])
        w = max(1.0, float(width or 1) / 2)
        c = _rgb(fill) or (0, 0, 0)
        import math as _m
        L = _m.hypot(x1 - x0, y1 - y0)
        with self.canvas:
            _Color(*c)
            ux, uy = ((x1 - x0) / L, (y1 - y0) / L) if L > 1e-6 else (0, 0)
            ex, ey = x1, y1
            if arrow == "last" and L > 1e-6:
                a, b, cc = arrowshape or (8, 10, 3)
                ex, ey = x1 - ux * a * 0.8, y1 - uy * a * 0.8
            if dash and L > 1e-6:
                on, off = dash[0] * 1.5, dash[1] * 1.5
                t, Ld = 0.0, _m.hypot(ex - x0, ey - y0)
                while t < Ld:
                    t2 = min(Ld, t + on)
                    _Line(points=[x0 + ux * t, y0 + uy * t, x0 + ux * t2, y0 + uy * t2], width=w)
                    t = t2 + off
            else:
                _Line(points=[x0, y0, ex, ey], width=w)
            if arrow == "last" and L > 1e-6:
                a, b, cc = arrowshape or (8, 10, 3)
                px, py = -uy, ux
                hw = cc + float(width or 1) / 2
                bx, by = x1 - ux * b, y1 - uy * b
                _Mesh(vertices=[x1, y1, 0, 0, bx + px * hw, by + py * hw, 0, 0,
                                bx - px * hw, by - py * hw, 0, 0],
                      indices=[0, 1, 2], mode="triangles")

    def create_arc(self, x0, y0, x1, y1, start=0, extent=90, style="arc", outline="#000000",
                   width=1, **kw):
        xa, xb = min(x0, x1), max(x0, x1)
        ya, yb = self._Y(max(y0, y1)), self._Y(min(y0, y1))
        o = _rgb(outline)
        if not o:
            return
        a0, a1 = 90 - start - extent, 90 - start      # tk: grados antihorario desde el este
        with self.canvas:
            _Color(*o)
            _Line(ellipse=(xa, ya, xb - xa, yb - ya, a0, a1), width=max(1.0, float(width or 1) / 2))

    def _texture(self, text, font, fill, width):
        size = 12
        bold = False
        if isinstance(font, tuple):
            size = abs(int(font[1])) if len(font) > 1 else 12
            bold = len(font) > 2 and "bold" in str(font[2])
        size = max(6, size)
        wrap = int(width) if width else None
        key = (text, size, bold, fill, wrap)
        tex = self.TEX.get(key)
        if tex is None:
            if len(self.TEX) > 900:
                for old in list(self.TEX)[:150]:
                    self.TEX.pop(old, None)
            c = _rgb(fill) or (0, 0, 0)
            lab = _CoreLabel(text=str(text), font_size=size, bold=bold, color=(*c, 1),
                             halign="center", text_size=(wrap, None) if wrap else (None, None))
            lab.refresh()
            tex = lab.texture
            self.TEX[key] = tex
        return tex

    def create_text(self, x, y, text="", fill="#000000", font=None, anchor="center",
                    width=None, justify="center", **kw):
        if text is None or str(text) == "":
            return
        tex = self._texture(text, font, fill, width)
        tw, th = tex.size
        if anchor == "e":
            px = x - tw
        elif anchor == "w":
            px = x
        else:
            px = x - tw / 2
        with self.canvas:
            _Color(1, 1, 1, 1)
            _Rect(texture=tex, pos=(px, self._Y(y) - th / 2), size=(tw, th))

    # --- entrada
    def _resized(self, *a):
        h = self.handlers.get("<Configure>")
        if h:
            h(_Ev(width=int(self.width), height=int(self.height)))

    def _fire(self, name, touch):
        h = self.handlers.get(name)
        if h:
            h(_Ev(touch.x - self.x, self.height - (touch.y - self.y)))

    def on_touch_down(self, touch):
        if getattr(touch, "button", "left") in ("scrollup", "scrolldown", "right"):
            return True
        self._fire("<ButtonPress-1>", touch)
        return True

    def on_touch_move(self, touch):
        self._fire("<B1-Motion>", touch)
        return True

    def on_touch_up(self, touch):
        self._fire("<ButtonRelease-1>", touch)
        return True


class _Root:
    """Imita tk.Tk: after(), bind() de teclas, tamaño de pantalla."""
    KEYS = {97: "a", 100: "d", 276: "Left", 275: "Right", 32: "space", 13: "Return", 271: "Return"}

    def __init__(self):
        self.keys = {}
        self.widget = None
        _Window.bind(on_key_down=self._key)
        _Window.bind(on_key_up=self._keyup)

    def title(self, *a):
        pass

    def geometry(self, *a):
        pass

    def attributes(self, *a):
        pass

    def configure(self, **kw):
        bg = kw.get("bg")
        if bg:
            _Window.clearcolor = (*_rgb(bg), 1)

    def winfo_screenwidth(self):
        return int(_Window.width)

    def winfo_screenheight(self):
        return int(_Window.height)

    def winfo_width(self):
        return int(_Window.width)

    def winfo_height(self):
        return int(_Window.height)

    def after(self, ms, fn):
        _Clock.schedule_once(lambda dt: fn(), ms / 1000.0)

    def bind(self, seq, fn):
        self.keys[seq] = fn

    def _key(self, win, key, scancode, codepoint, mods):
        if key == 27:                       # Atrás (Android) / Esc: deja que Kivy lo gestione
            return False
        name = self.KEYS.get(key)
        if name:
            for seq in (f"<KeyPress-{name}>", f"<KeyPress-{name.upper()}>"):
                fn = self.keys.get(seq)
                if fn:
                    fn(_Ev())
                    return True
        return False


    def _keyup(self, win, key, *a):
        name = self.KEYS.get(key)
        if name:
            for seq in (f"<KeyRelease-{name}>", f"<KeyRelease-{name.upper()}>"):
                fn = self.keys.get(seq)
                if fn:
                    fn(_Ev())
                    return True
        return False


class tk:                                   # espacio de nombres compatible con "tk."
    TclError = _TclError
    Tk = _Root

    @staticmethod
    def Canvas(root, **kw):
        w = _CanvasWidget(root)
        root.widget = w
        return w


SR = 16000                                           # muestras por segundo (ligero para móviles)
SND_DIR = os.path.join(os.environ.get("ANDROID_PRIVATE") or tempfile.gettempdir(), "mundial_chapas_snd_v7")

# Identidad sonora por selección: tempo, nota base (Hz), instrumento, percusión, melodía
# melodía: "semitono:duración_en_tiempos" ; "r" = silencio
SOUND_ID = {
    "España":         (132, 293.7, "trumpet",   "pasodoble", "0:.5 4:.5 7:.5 12:1.5 11:.5 9:.5 7:1 r:.5 7:.5 12:2"),
    "Francia":        (112, 261.6, "brass",     "march",     "0:1 0:.5 5:.5 7:1 9:1 7:.5 5:.5 7:2 12:2"),
    "Alemania":       (104, 220.0, "brass",     "stomp",     "0:1 0:1 7:1 7:1 5:.5 4:.5 2:1 0:2"),
    "Inglaterra":     (96,  246.9, "organ",     "stomp",     "0:1.5 2:.5 4:1 4:1 2:1 0:1 2:2 7:2"),
    "Italia":         (120, 349.2, "accordion", "march",     "0:.5 2:.5 4:.5 5:.5 7:1 9:.5 7:.5 5:1 4:1 0:2"),
    "Portugal":       (118, 311.1, "guitar",    "clap",      "0:.5 1:.5 4:1 5:.5 4:.5 1:1 0:.5 r:.5 7:2"),
    "Países Bajos":   (128, 329.6, "organ",     "oompah",    "0:.5 4:.5 7:.5 4:.5 0:.5 4:.5 7:1 9:.5 7:.5 5:.5 4:.5 0:2"),
    "Bélgica":        (122, 277.2, "brass",     "oompah",    "0:1 4:.5 4:.5 7:1 12:1 9:1 7:2"),
    "Croacia":        (100, 233.1, "voice",     "stomp",     "0:1 3:1 5:1 7:2 5:.5 3:.5 0:2"),
    "Argentina":      (138, 293.7, "voice",     "bombo",     "0:.5 0:.5 3:.5 5:.5 7:1 5:.5 3:.5 0:1 r:.5 7:.5 10:.5 12:1.5"),
    "Brasil":         (150, 329.6, "whistle",   "samba",     "0:.25 4:.25 7:.5 9:.5 7:.25 4:.25 7:.5 12:.5 9:.5 7:1 4:1"),
    "Uruguay":        (116, 261.6, "voice",     "candombe",  "0:1 3:.5 5:.5 7:1 3:.5 5:.5 0:2"),
    "Colombia":       (126, 349.2, "accordion", "cumbia",    "0:.5 2:.5 4:.5 7:.5 9:1 7:.5 4:.5 2:.5 4:.5 0:2"),
    "México":         (110, 392.0, "mariachi",  "huapango",  "0:.5 4:.5 7:1.5 4:.5 5:.5 9:.5 7:1.5 4:.5 0:2"),
    "Estados Unidos": (118, 293.7, "synth",     "rock",      "0:.5 7:.5 12:1 11:.5 12:.5 14:1 12:2"),
    "Chile":          (124, 311.1, "voice",     "clap",      "0:.5 0:.5 0:.5 r:.5 5:.5 5:.5 5:.5 r:.5 7:.5 7:.5 5:.5 3:.5 0:2"),
    # --- v7: identidades sonoras nuevas (melodías originales)
    "Suecia":         (108, 261.6, "alphorn",   "march",     "0:1 4:1 7:1 12:2 11:.5 9:.5 7:1 4:1 7:2"),
    "Dinamarca":      (126, 293.7, "organ",     "clap",      "0:.5 2:.5 4:1 2:.5 0:.5 7:1 5:.5 4:.5 2:.5 4:.5 0:2"),
    "Suiza":          (96,  233.1, "alphorn",   "waltz",     "0:1.5 7:.5 12:1 9:1 7:1 4:1 7:3"),
    "Polonia":        (134, 311.1, "accordion", "polka",     "0:.5 4:.5 7:.5 4:.5 9:.5 7:.5 4:.5 0:.5 2:.5 4:.5 2:.5 0:2"),
    "Hungría":        (112, 277.2, "violin",    "clap",      "0:.5 1:.5 4:.5 5:.5 7:1 8:.5 7:.5 5:.5 4:.5 1:.5 0:2"),
    "Paraguay":       (120, 329.6, "harp",      "galopa",    "0:.5 4:.5 7:.5 9:.5 12:1 9:.5 7:.5 4:.5 7:.5 0:2"),
    "Perú":           (114, 392.0, "flute",     "huayno",    "0:.5 3:.5 5:.5 7:1 5:.5 3:.5 0:.5 -2:.5 0:2"),
    "Ecuador":        (124, 261.6, "marimba",   "bomba",     "0:.5 4:.5 7:.5 4:.5 9:1 7:.5 4:.5 5:.5 2:.5 0:2"),
}

HARM = {   # (lista de armónicos (n, amplitud), vibrato, ataque s)
    "trumpet":   ([(1, 1), (2, .8), (3, .6), (4, .45), (5, .3), (6, .2)], 0.004, 0.03),
    "brass":     ([(1, 1), (2, .6), (3, .45), (4, .3), (5, .15)], 0.002, 0.05),
    "organ":     ([(1, 1), (2, .5), (4, .3), (8, .1)], 0.0, 0.01),
    "accordion": ([(1, 1), (3, .5), (5, .3), (7, .15)], 0.006, 0.02),
    "guitar":    ([(1, 1), (2, .5), (3, .3), (4, .15)], 0.0, 0.003),
    "voice":     ([(1, 1), (2, .7), (3, .5), (4, .25), (6, .15)], 0.012, 0.06),
    "whistle":   ([(1, 1), (2, .1)], 0.02, 0.01),
    "mariachi":  ([(1, 1), (2, .9), (3, .7), (4, .5), (5, .35), (6, .2)], 0.009, 0.02),
    "synth":     ([(1, 1), (2, .5), (3, .33), (4, .25), (5, .2)], 0.003, 0.01),
    # --- v7
    "alphorn":   ([(1, 1), (2, .45), (3, .2)], 0.003, 0.12),
    "violin":    ([(1, 1), (2, .7), (3, .55), (4, .4), (5, .3), (6, .2), (7, .1)], 0.016, 0.04),
    "harp":      ([(1, 1), (2, .35), (3, .15)], 0.0, 0.002),
    "flute":     ([(1, 1), (2, .25), (3, .08)], 0.011, 0.05),
    "marimba":   ([(1, 1), (4, .3), (10, .08)], 0.0, 0.002),
}
DRUMS = {  # golpes por compás de 4 tiempos: (tiempo, tipo)
    "pasodoble": [(0, "k"), (1, "s"), (2, "k"), (3, "s")],
    "march":     [(0, "k"), (1, "s"), (1.5, "s"), (2, "k"), (3, "s"), (3.5, "s")],
    "stomp":     [(0, "k"), (1, "k"), (2, "c")],
    "clap":      [(0, "k"), (0.5, "c"), (1.5, "c"), (2, "k"), (3, "c")],
    "oompah":    [(0, "k"), (1, "h"), (2, "k"), (3, "h")],
    "bombo":     [(0, "b"), (0.75, "b"), (1.5, "b"), (2, "b"), (2.5, "h"), (3, "b"), (3.5, "b")],
    "samba":     [(t / 4, "h") for t in range(16)] + [(0, "b"), (1, "b"), (2, "b"), (2.5, "s"), (3, "b"), (3.5, "s")],
    "candombe":  [(0, "b"), (0.75, "s"), (1.5, "b"), (2, "s"), (2.75, "b"), (3.5, "s")],
    "cumbia":    [(t / 2, "h") for t in range(8)] + [(0, "k"), (1, "s"), (2, "k"), (3, "s"), (3.5, "s")],
    "huapango":  [(0, "k"), (0.75, "c"), (1.5, "c"), (2, "k"), (2.75, "c"), (3.5, "c")],
    "rock":      [(t / 2, "h") for t in range(8)] + [(0, "k"), (1, "s"), (1.5, "k"), (2, "k"), (3, "s")],
    # --- v7
    "waltz":     [(0, "k"), (1, "h"), (2, "h"), (3, "k")],
    "polka":     [(0, "k"), (0.5, "h"), (1, "s"), (1.5, "h"), (2, "k"), (2.5, "h"), (3, "s"), (3.5, "h")],
    "galopa":    [(0, "b"), (1.5, "c"), (2, "b"), (3, "c"), (3.5, "c")],
    "huayno":    [(0, "b"), (0.75, "b"), (1, "s"), (2, "b"), (2.75, "b"), (3, "s")],
    "bomba":     [(0, "b"), (1, "c"), (1.5, "b"), (2.5, "c"), (3, "b"), (3.5, "c")],
}
PLUCK = {"guitar": 6, "harp": 4, "marimba": 11}


def _buf(sec):
    return [0.0] * int(SR * sec)


def _tone(buf, t0, dur, f, inst, vol):
    harm, vib, att = HARM[inst]
    i0, n = int(t0 * SR), int(dur * SR)
    rel = min(0.08, dur * 0.4)
    pluck = PLUCK.get(inst, 0)
    ph = 0.0
    for i in range(n):
        j = i0 + i
        if j >= len(buf):
            break
        t = i / SR
        env = min(1.0, t / att) if att else 1.0
        if pluck:
            env *= math.exp(-t * pluck)
        if t > dur - rel:
            env *= max(0.0, (dur - t) / rel)
        ph += math.tau * f * (1 + vib * math.sin(math.tau * 5.5 * t)) / SR
        s = 0.0
        for k, a in harm:
            s += a * math.sin(ph * k)
        buf[j] += s * env * vol


def _noise(buf, t0, dur, vol, smooth=0.0, decay=0.0, swell=False):
    i0, n = int(t0 * SR), int(dur * SR)
    y = 0.0
    rnd = random.random
    for i in range(n):
        j = i0 + i
        if j >= len(buf):
            break
        t = i / SR
        x = rnd() * 2 - 1
        y = y * smooth + x * (1 - smooth)
        if swell:
            env = min(1.0, t / 0.25) * min(1.0, (dur - t) / (dur * 0.5))
        else:
            env = math.exp(-t * decay) if decay else 1.0
        buf[j] += y * env * vol


def _drum(buf, t0, kind, vol):
    if kind in ("k", "b"):                           # bombo / surdo: seno con caída de tono
        f0, f1, d = (120, 45, 0.25) if kind == "k" else (90, 55, 0.35)
        i0, ph = int(t0 * SR), 0.0
        for i in range(int(d * SR)):
            j = i0 + i
            if j >= len(buf):
                break
            t = i / SR
            ph += math.tau * (f1 + (f0 - f1) * math.exp(-t * 25)) / SR
            buf[j] += math.sin(ph) * math.exp(-t * 9) * vol * 1.3
    elif kind == "s":
        _noise(buf, t0, 0.15, vol * 0.6, 0.3, 22)
    elif kind == "c":
        for o in (0, 0.012, 0.024):
            _noise(buf, t0 + o, 0.08, vol * 0.45, 0.2, 40)
    else:
        _noise(buf, t0, 0.05, vol * 0.25, 0.0, 70)


def _melody(buf, t0, team, vol=0.32, reps=1, cut=None, transpose=0):
    bpm, root, inst, drums, mel = SOUND_ID[team]
    beat = 60 / bpm
    notes = []
    for tok in mel.split():
        p, d = tok.split(":")
        notes.append((None if p == "r" else int(p), float(d)))
    if cut:
        notes = notes[:cut]
    t = t0
    for _ in range(reps):
        for p, d in notes:
            if p is not None:
                f = root * 2 ** ((p + transpose) / 12)
                _tone(buf, t, d * beat * 0.92, f, inst, vol)
                if inst in ("mariachi", "voice"):        # segunda voz / coro
                    _tone(buf, t, d * beat * 0.92, f * 2 ** (-5 / 12) if inst == "voice" else f * 1.26, inst, vol * 0.45)
            t += d * beat
    end = t
    bar = beat * 4
    b = t0
    while b < end - 0.01:
        for pos, k in DRUMS[drums]:
            if b + pos * beat < end:
                _drum(buf, b + pos * beat, k, 0.35)
        b += bar
    return end


def _write(path, buf, gain=0.9):
    peak = max(1e-6, max(abs(v) for v in buf))
    k = 32000 * gain / peak
    data = array.array("h", (int(v * k) for v in buf))
    if sys.byteorder == "big":
        data.byteswap()
    tmp = path + ".part"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())
    os.replace(tmp, path)


def gen_common():
    out = {}
    def mk(name, fn, sec, gain=0.9):
        p = os.path.join(SND_DIR, name + ".wav")
        if not os.path.exists(p):
            b = _buf(sec); fn(b); _write(p, b, gain)
        out[name] = p
    def whistle(b, blasts):
        for t0, d in blasts:
            for i in range(int(d * SR)):
                j = int(t0 * SR) + i
                t = i / SR
                trill = 1 + 0.5 * (math.sin(math.tau * 28 * t) > 0)
                env = min(1, t / 0.02) * min(1, (d - t) / 0.04)
                b[j] += (math.sin(math.tau * 2800 * t + 6 * math.sin(math.tau * 28 * t)) * 0.8 * trill
                         + (random.random() - .5) * 0.25) * env * 0.5
    mk("pito", lambda b: whistle(b, [(0, 0.55)]), 0.65, 0.55)
    mk("pito_medio", lambda b: whistle(b, [(0, 0.25), (0.35, 0.6)]), 1.05, 0.55)
    mk("pito_final", lambda b: whistle(b, [(0, 0.3), (0.4, 0.3), (0.8, 0.9)]), 1.8, 0.6)
    mk("toque", lambda b: (_drum(b, 0, "k", 0.6), _noise(b, 0, 0.04, 0.4, 0.5, 80)), 0.2, 0.35)
    def ooh(b):                                       # "uyyy" del público
        _noise(b, 0, 1.2, 0.5, 0.93, swell=True)
        for f in (180, 230, 270):
            _tone(b, 0.05, 1.1, f * 1.0, "voice", 0.05)
    mk("uy", ooh, 1.3, 0.55)
    def lose(b):                                      # trombón triste + suspiro
        for i, p in enumerate((0, -1, -2, -4)):
            _tone(b, i * 0.42, 0.4 if i < 3 else 1.0, 233 * 2 ** (p / 12), "brass", 0.3)
        _noise(b, 0, 2.2, 0.15, 0.95, swell=True)
    mk("derrota", lose, 2.3, 0.6)
    return out


def gen_team(team):
    out = {}
    key = ABBR[team]
    def mk(name, fn, sec, gain=0.9):
        p = os.path.join(SND_DIR, f"{key}_{name}.wav")
        if not os.path.exists(p):
            b = _buf(sec); fn(b); _write(p, b, gain)
        out[name] = p
    bpm = SOUND_ID[team][0]
    def gol(b):
        _noise(b, 0, 2.6, 0.55, 0.85, swell=True)     # rugido del estadio
        _melody(b, 0.25, team, cut=7)
    def penal(b):
        _noise(b, 0, 1.2, 0.4, 0.85, swell=True)
        _melody(b, 0.1, team, cut=3)
    def gana(b):
        _noise(b, 0, 3.4, 0.35, 0.88, swell=True)
        _melody(b, 0.1, team)
    def campeon(b):
        t = 0.0
        for p in (0, 4, 7, 12):                       # fanfarria
            _tone(b, t, 0.22, 392 * 2 ** (p / 12), "brass", 0.3); t += 0.2
        _tone(b, t, 0.7, 392 * 2, "brass", 0.32); _tone(b, t, 0.7, 392 * 1.5, "brass", 0.25)
        _noise(b, t, 0.9, 0.3, 0.1, 3)                # platillo
        end = _melody(b, t + 0.75, team, reps=2, transpose=2)
        _noise(b, 0.3, end + 0.6, 0.45, 0.86, swell=True)
    mk("gol", gol, 2.7)
    mk("penal", penal, 1.3)
    mk("gana", gana, 3.6 if bpm > 110 else 4.6)
    mk("campeon", campeon, 7.5 if bpm > 110 else 9.5)
    return out


class Sound:
    """Reproductor sin pygame: Android (Pydroid 3, MediaPlayer), Windows, macOS y Linux."""
    PRIO = {"toque": 0, "uy": 1, "pito": 2, "pito_medio": 2, "penal": 3, "pito_final": 3,
            "gol": 4, "gana": 4, "derrota": 4, "campeon": 5, "pausa_inicio": 6}

    def __init__(self):
        self.on = True
        self.files = {}
        self.busy_until, self.busy_prio = 0.0, -1
        self.players = []
        self.backend = self._detect()
        self.on_event = None
        self.files.update({('', k): asset('sounds', 'effects', k+'.wav')
                           for k in ('pito','pito_medio','pito_final','toque','uy','derrota','fuego','pausa_inicio')})
        for team in TEAMS:
            for kind in ('gol','penal','gana','campeon'):
                self.files[(team,kind)] = asset('sounds','victory',ABBR[team]+'_'+kind+'.wav')

    def _detect(self):
        try:
            from kivy.core.audio import SoundLoader
            self.SL = SoundLoader
            self.cache = {}
            return "kivy"
        except Exception:
            pass
        if "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ or hasattr(sys, "getandroidapilevel"):
            try:
                from jnius import autoclass
                self.MP = autoclass("android.media.MediaPlayer")
                return "android"
            except Exception:
                return None
        if sys.platform.startswith("win"):
            try:
                import winsound
                self.ws = winsound
                return "win"
            except ImportError:
                return None
        if sys.platform == "darwin":
            return "afplay"
        for cmd in ("paplay", "aplay", "pw-play"):
            for d in os.environ.get("PATH", "").split(os.pathsep):
                if os.path.exists(os.path.join(d, cmd)):
                    return cmd
        return None

    def _bg(self, fn):
        def run():
            try:
                fn()
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def prepare(self, *teams):
        # Load a few clips before play; all 24 countries already ship as WAV assets.
        if self.backend == 'kivy':
            for team in teams:
                for kind in ('gol','penal','gana','campeon'):
                    path=self.files.get((team,kind))
                    if path and path not in self.cache:
                        self.cache[path]=self.SL.load(path)

    def play(self, name, team="", dur=1.0):
        if self.on_event:
            self.on_event(name, team)
        if not (self.on and self.backend):
            return
        path = self.files.get((team, name))
        if not path:
            return                                    # aún generándose: se omite sin trabar el juego
        now = time.monotonic()
        prio = self.PRIO.get(name, 1)
        if now < self.busy_until and prio < self.busy_prio:
            return                                    # no tapar una celebración con un toque
        self.busy_until, self.busy_prio = now + dur, prio
        try:
            if self.backend == "kivy":
                s = self.cache.get(path)
                if s is None:
                    s = self.SL.load(path)
                    self.cache[path] = s
                if s:
                    s.stop()
                    s.play()
            elif self.backend == "android":
                for mp in self.players[:-3]:
                    mp.release()
                self.players = self.players[-3:]
                mp = self.MP()
                mp.setDataSource(path)
                mp.prepare()
                mp.start()
                self.players.append(mp)
            elif self.backend == "win":
                self.ws.PlaySound(path, self.ws.SND_FILENAME | self.ws.SND_ASYNC | self.ws.SND_NODEFAULT)
            else:
                if prio >= 3:
                    for p in self.players:
                        if p.poll() is None:
                            p.terminate()
                self.players = [p for p in self.players if p.poll() is None]
                self.players.append(subprocess.Popen([self.backend, path], stdout=subprocess.DEVNULL,
                                                     stderr=subprocess.DEVNULL))
        except Exception:
            pass


class Music:
    """v9: música de fondo en bucle con fundidos de volumen que avanzan con el reloj de juego
    (se congelan en la pausa) y pausa/reanudación desde la misma posición."""

    def __init__(self, snd):
        self.snd = snd
        self.s = None
        self.vol, self.target, self.rate = 0.0, 0.0, 0.0
        self.stop_at_zero = False
        self.paused_pos = None
        self.path = None
        base = os.path.dirname(os.path.abspath(__file__))
        for name in (MUSIC_FILE, "musica_fondo.ogg", "musica_fondo.wav"):
            for d in (base, os.getcwd()):
                p = os.path.join(d, name)
                if os.path.exists(p):
                    self.path = p
                    break
            if self.path:
                break

    def _load(self):
        if self.s is None and self.path:
            try:
                from kivy.core.audio import SoundLoader
                self.s = SoundLoader.load(self.path)
                if self.s:
                    self.s.loop = True
            except Exception:
                self.s = None
        return self.s

    def _apply(self):
        if self.s:
            try:
                self.s.volume = self.vol if self.snd.on else 0.0
            except Exception:
                pass

    def fade_to(self, target, secs):
        self.target = max(0.0, min(1.0, target))
        self.rate = abs(self.target - self.vol) / max(0.05, secs)

    def start(self):                                  # comienzo de cada partido: desde 0 %
        s = self._load()
        if not s:
            return
        self.paused_pos = None
        self.stop_at_zero = False
        self.vol = 0.0
        self._apply()
        try:
            s.stop()
            s.play()
            s.seek(0)
        except Exception:
            pass
        self._apply()
        self.fade_to(MUSIC_VOL, MUSIC_FADE_IN)

    def fade_out_end(self):
        if self.s:
            self.stop_at_zero = True
            self.fade_to(0.0, MUSIC_END_FADE)

    def stop(self):
        self.vol, self.target, self.rate = 0.0, 0.0, 0.0
        self.paused_pos = None
        self.stop_at_zero = False
        if self.s:
            try:
                self.s.stop()
            except Exception:
                pass

    def update(self, dt):                             # solo se llama cuando NO hay pausa
        if not self.s or self.paused_pos is not None:
            return
        if self.vol != self.target:
            step = self.rate * dt
            if abs(self.target - self.vol) <= step:
                self.vol = self.target
            else:
                self.vol += step if self.target > self.vol else -step
        self._apply()
        if self.stop_at_zero and self.vol <= 0.0:
            self.stop()

    def pause(self):
        if not self.s or self.paused_pos is not None:
            return
        try:
            if self.s.state == "play":
                self.paused_pos = max(0.0, self.s.get_pos() or 0.0)
                self.s.stop()
        except Exception:
            self.paused_pos = None

    def resume(self):                                 # sigue desde el mismo punto y mismo fundido
        if not self.s or self.paused_pos is None:
            return
        pos, self.paused_pos = self.paused_pos, None
        try:
            self.s.play()
            self._apply()
            if pos > 0:
                self.s.seek(pos)
        except Exception:
            pass


FORMATION = [(0.04, 0.5), (0.18, 0.3), (0.18, 0.7), (0.32, 0.38), (0.32, 0.62), (0.44, 0.5)]
ROUND_NAMES = ["Octavos de final", "Cuartos de final", "Semifinales", "FINAL"]
BG = "#0a5a2a"


def rating(t):
    return TEAMS[t][4]


def lum(hx):
    r, g, b = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def text_on(hx):
    return "#111111" if lum(hx) > 150 else "#ffffff"


class Body:
    def __init__(self, x, y, r, m, team=None, keeper=False, num=0):
        self.x, self.y, self.vx, self.vy = x, y, 0.0, 0.0
        self.r, self.m, self.team, self.keeper, self.num = r, m, team, keeper, num

    def speed(self):
        return math.hypot(self.vx, self.vy)


# ------------------------------------------------------------------ física
def walls(b, is_ball, goal=None):
    gy0, gy1, depth = (GY0, GY1, GD) if goal is None else goal
    if b.y - b.r < FY0 and not (is_ball and (b.x < FX0 or b.x > FX1)):
        b.y = FY0 + b.r; b.vy = -b.vy * 0.8
    if b.y + b.r > FY1 and not (is_ball and (b.x < FX0 or b.x > FX1)):
        b.y = FY1 - b.r; b.vy = -b.vy * 0.8
    in_goal = is_ball and gy0 < b.y < gy1
    for side in (-1, 1):
        line = FX0 if side < 0 else FX1
        past = (b.x - b.r < line) if side < 0 else (b.x + b.r > line)
        if not past:
            continue
        if in_goal:
            back = line - depth if side < 0 else line + depth
            if side < 0 and b.x - b.r < back:
                b.x = back + b.r; b.vx = -b.vx * 0.3
            if side > 0 and b.x + b.r > back:
                b.x = back - b.r; b.vx = -b.vx * 0.3
            if (side < 0 and b.x < line) or (side > 0 and b.x > line):
                if b.y - b.r < gy0: b.y = gy0 + b.r; b.vy = -b.vy * 0.5
                if b.y + b.r > gy1: b.y = gy1 - b.r; b.vy = -b.vy * 0.5
        else:
            b.x = line + b.r if side < 0 else line - b.r
            b.vx = -b.vx * 0.8


def collide(a, b):
    dx, dy = b.x - a.x, b.y - a.y
    d = math.hypot(dx, dy)
    mind = a.r + b.r
    if d == 0 or d >= mind:
        return
    nx, ny = dx / d, dy / d
    over = mind - d
    ta = b.m / (a.m + b.m)
    a.x -= nx * over * ta; a.y -= ny * over * ta
    b.x += nx * over * (1 - ta); b.y += ny * over * (1 - ta)
    rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
    if rv > 0:
        return
    j = -(1 + 0.92) * rv / (1 / a.m + 1 / b.m)
    a.vx -= j * nx / a.m; a.vy -= j * ny / a.m
    b.vx += j * nx / b.m; b.vy += j * ny / b.m


def step(bodies, ball, scale=1.0, zone=None, catcher=None, limit=None, touch=None, collision_policy=None, goal=None, body_scale=None):
    """Avanza la física un fotograma.
    scale: velocidad del tiempo (0,75 = cámara lenta). zone(b): factor de velocidad del arquero
    según esté dentro/fuera del área chica. catcher: arquero que puede atrapar el balón.
    limit(b): barrera del área grande (solo se llama para arqueros).
    touch: dict {"k": arquero, "hit": False}; marca hit=True si ese arquero toca el balón.
    body_scale(b): factor por cuerpo (PAUSA). 0 = congelado.
    Devuelve True si `catcher` atrapó el balón en este fotograma."""
    caught = False
    for _ in range(SUB):
        for b in bodies:
            k = scale / SUB
            if body_scale is not None:
                f_b = body_scale(b)
                if f_b == 0.0:
                    b.vx = b.vy = 0.0          # rival congelado: no se desliza
                k *= f_b
            if zone is not None and b.keeper:
                k *= zone(b)
            b.x += b.vx * k; b.y += b.vy * k
            walls(b, b is ball, goal)
            if limit is not None and b.keeper:
                limit(b)
        if touch is not None and not touch["hit"]:
            tk_ = touch["k"]
            if math.hypot(ball.x - tk_.x, ball.y - tk_.y) <= tk_.r + ball.r + 1.0:
                touch["hit"] = True
        if catcher is not None and not caught:
            if math.hypot(ball.x - catcher.x, ball.y - catcher.y) <= catcher.r + ball.r + 1.5:
                caught = True
                ball.vx = ball.vy = 0.0
        for i in range(len(bodies)):
            for k in range(i + 1, len(bodies)):
                if collision_policy is None or collision_policy(bodies[i], bodies[k]):
                    collide(bodies[i], bodies[k])
    for b in bodies:
        f = FRICTION if b is ball else PLAYER_FRICTION
        if scale != 1.0:
            f = f ** scale
        b.vx *= f; b.vy *= f
        if b.speed() < 0.06:
            b.vx = b.vy = 0.0
    return caught
    

def mix(c1, c2, t):
    t = min(1.0, max(0.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------ geometría de camisetas
CIRCLE = [(math.cos(i * math.tau / 32), math.sin(i * math.tau / 32)) for i in range(32)]


def clip(poly, nx, ny, c):
    """Conserva la parte del polígono con p·n <= c (Sutherland-Hodgman)."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp, dq = p[0] * nx + p[1] * ny - c, q[0] * nx + q[1] * ny - c
        if dp <= 0:
            out.append(p)
        if (dp < 0) != (dq < 0) and dp != dq:
            t = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def band(nx, ny, u0, u1, extra=None):
    poly = clip(clip(CIRCLE, nx, ny, u1), -nx, -ny, -u0)
    if extra:
        for e in extra:
            poly = clip(poly, *e)
    return poly


def kit_shapes(pattern, c1, c2, extra):
    """Lista de (polígono en círculo unidad, color) a pintar sobre el color base."""
    shapes = []
    if pattern == "vstripes":
        w = 2 / 5
        for k in (1, 3):
            shapes.append((band(1, 0, -1 + k * w, -1 + (k + 1) * w), c2))
    elif pattern == "hoops":
        w = 2 / 6
        for k in (1, 3, 5):
            shapes.append((band(0, 1, -1 + k * w, -1 + (k + 1) * w), c2))
    elif pattern == "sash":
        s = math.sqrt(0.5)
        shapes.append((band(s, s, -0.28, 0.28), c2))
    elif pattern == "half":
        shapes.append((band(1, 0, 0, 1.1), c2))
    elif pattern == "checks":
        w = 2 / 4
        for i in range(4):
            for j in range(4):
                if (i + j) % 2:
                    shapes.append((band(1, 0, -1 + i * w, -1 + (i + 1) * w,
                                        [(0, 1, -1 + (j + 1) * w), (0, -1, 1 - j * w)]), c2))
    elif pattern == "chestband" and extra:
        h = 0.16
        for k, col in enumerate(extra):
            u = -0.05 + (k - 1) * h
            shapes.append((band(0, 1, u - h / 2, u + h / 2), col))
    elif pattern == "pinstripes":                     # v7: rayas finas
        for u in (-0.75, -0.375, 0.0, 0.375, 0.75):
            shapes.append((band(1, 0, u - 0.05, u + 0.05), c2))
    elif pattern == "cross":                          # v7: cruz al pecho
        shapes.append((band(1, 0, -0.17, 0.17, [(0, 1, 0.55), (0, -1, 0.75)]), c2))
        shapes.append((band(0, 1, -0.17, 0.17, [(1, 0, 0.6), (-1, 0, 0.6)]), c2))
    elif pattern == "hhalf":                          # v7: mitad superior / inferior
        shapes.append((band(0, 1, 0, 1.1), c2))
    return [(p, c) for p, c in shapes if len(p) >= 3]


KIT_CACHE = {}


def kit_for(team, keeper=False, side=0):
    key = (team, keeper, side)
    if key not in KIT_CACHE:
        pat, c1, c2, edge, _, extra = TEAMS[team]
        if keeper and team in GK_KIT:                 # v7: arquero propio de las nuevas
            base, stripe, gedge = GK_KIT[team]
            KIT_CACHE[key] = (base, [(band(0, 1, -0.12, 0.12), stripe),
                                     (band(1, 0, -0.07, 0.07, [(0, 1, -0.12)]), stripe)], gedge)
        elif keeper:
            base = "#b6ff00" if side == 0 else "#ff4fd8"
            if abs(lum(base) - lum(c1)) < 20:
                base = "#00e5ff"
            KIT_CACHE[key] = (base, [(band(0, 1, -0.12, 0.12), edge)], edge)
        else:
            KIT_CACHE[key] = (c1, kit_shapes(pat, c1, c2, extra), edge)
    return KIT_CACHE[key]


# ------------------------------------------------------------------ juego
from tournament import TournamentView
from presentation import VisualResources, asset, screen_change


from fire import FireAbility, POWER_FACTOR, ANDROID_SAFE_BOTTOM_DP
from pausa_power import PausaAbility, combined_scale
from abilities import AbilityBar, ability_layout


from ai import RivalAI, ENHANCED_COOLDOWN


class Game(RivalAI, FireAbility, PausaAbility, AbilityBar, TournamentView):
    def __init__(self, root):
        self.root = root
        root.title("Copa Mundial de Chapas")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.mobile = ("ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ
                       or min(sw, sh) < 900)
        self.pen_btns = []
        self.pen_hold = 0
        self.ctrl_pad = 0
        self.lock = False
        self.pen_k = 0
        self.bodies = []
        self.ball = None
        self.keeper = None
        self.gk_reset()
        self.fire_reset()
        self.pausa_reset()
        self.ability_reset()
        if self.mobile:
            root.geometry(f"{sw}x{sh}+0+0")
            try:
                root.attributes("-fullscreen", True)
            except tk.TclError:
                pass
        else:
            root.geometry(f"{min(1100, sw - 40)}x{min(740, sh - 80)}")
        root.configure(bg=BG)
        self.cv = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.buttons = []
        self.state = "menu"
        self.drag = None
        self.mouse_w = (0, 0)
        self.msg, self.msg_until = "", 0
        self.cw, self.ch = 800, 600
        self.snd = Sound()
        self.recalc()
        self.cv.bind("<Configure>", self.on_resize)
        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_motion)
        self.cv.bind("<ButtonRelease-1>", self.on_release)
        root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
        for k in ("a", "A", "Left"):
            root.bind(f"<KeyPress-{k}>", lambda e: self.pen_key(-1))
        for k in ("d", "D", "Right"):
            root.bind(f"<KeyPress-{k}>", lambda e: self.pen_key(1))
        for k in ("space", "Return"):
            root.bind(f"<KeyPress-{k}>", lambda e: self.pen_key(0))
        for k in ("a", "A", "Left", "d", "D", "Right"):        # v7: soltar = ejecutar DASH
            root.bind(f"<KeyRelease-{k}>", lambda e: self.gk_release())
        self.paused = False
        self.gen = 0                                   # cambia al reiniciar: anula esperas viejas
        self.music = Music(self.snd)
        self.last_t = vnow()
        self.selected_country = None
        self.visual = VisualResources(self)
        self.snd.on_event = self.sound_visual_event
        self.render()
        self.tick()

    # ---------------- escala / adaptación
    def recalc(self):
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = self.root.winfo_width(), self.root.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 800, 600
        self.cw, self.ch = cw, ch
        self.u = max(7.0, min(cw, ch) / 36)              # unidad base de texto (px)
        self.hud = int(self.u * 3.6)
        w, h = cw, ch - self.hud
        self.rot = h > w * 1.05                           # pantalla vertical => cancha girada
        if self.state == "pens":
            # vista de penales: portería arriba, así izquierda/derecha son naturales
            self.rot = True
            self.pen_pad = self.u * 7.4                 # botones + barra de potencia
            hh = h - self.pen_pad
            span = min(RH, 2 * 230)                    # ancho visible: área grande y algo más
            self.s = min(w / span, hh / (PEN_WX1 - PEN_X0))
            self.ox = w / 2 - (MY - WY0) * self.s      # portería centrada
            self.oy = self.hud + (hh - (PEN_WX1 - PEN_X0) * self.s) / 2
            return
        # v7: franja inferior propia para los controles del arquero (no tapan la cancha)
        from kivy.metrics import dp
        self.safe_bottom = min(ch * .12, dp(ANDROID_SAFE_BOTTOM_DP)) if self.state == 'match' else 0
        if self.state == 'match':
            # Ability buttons = 4 x disc diameter at the final pitch scale.
            self.ability_size, self.ctrl_pad = ability_layout(cw, ch, self.hud, self.safe_bottom, self.rot, RW, RH, PR)
        else:
            self.ability_size, self.ctrl_pad = 0, 0
        h -= self.ctrl_pad + self.safe_bottom
        if self.rot:
            self.s = min(w / RH, h / RW)
            self.ox = (w - RH * self.s) / 2
            self.oy = self.hud + (h - RW * self.s) / 2
        else:
            self.s = min(w / RW, h / RH)
            self.ox = (w - RW * self.s) / 2
            self.oy = self.hud + (h - RH * self.s) / 2

    def on_resize(self, ev):
        if abs(ev.width - self.cw) > 2 or abs(ev.height - self.ch) > 2:
            self.recalc()
            self.render()

    def F(self, k, bold=True):
        return ("Helvetica", -max(8, int(k * self.u)), "bold" if bold else "normal")

    def to_s(self, x, y):
        if self.rot:   # el equipo del jugador (izquierda) queda abajo, atacando hacia arriba
            return self.ox + (y - WY0) * self.s, self.oy + ((PEN_WX1 if self.state == "pens" else WX1) - x) * self.s
        return self.ox + (x - WX0) * self.s, self.oy + (y - WY0) * self.s

    def to_w(self, sx, sy):
        if self.rot:
            return (PEN_WX1 if self.state == "pens" else WX1) - (sy - self.oy) / self.s, WY0 + (sx - self.ox) / self.s
        return WX0 + (sx - self.ox) / self.s, WY0 + (sy - self.oy) / self.s

    def poly_w(self, pts, **kw):
        flat = []
        for x, y in pts:
            flat += self.to_s(x, y)
        self.cv.create_polygon(flat, **kw)

    def rect_w(self, x0, y0, x1, y1, **kw):
        self.poly_w([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)

    def line_w(self, x0, y0, x1, y1, **kw):
        self.cv.create_line(*self.to_s(x0, y0), *self.to_s(x1, y1), **kw)

    def circle_w(self, x, y, r, **kw):
        sx, sy = self.to_s(x, y)
        R = r * self.s
        self.cv.create_oval(sx - R, sy - R, sx + R, sy + R, **kw)

    # ---------------- utilidades UI
    def render(self):
        self.cv.delete("all")
        self.buttons = []
        {"menu": self.draw_menu, "bracket": self.draw_bracket, "post": self.draw_post,
         "end": self.draw_end}.get(self.state, self.draw)()

    @screen_change
    def go(self, state):
        if state != self.state and "pens" in (state, self.state):
            self.state = state
            self.recalc()
        self.state = state
        self.render()

    def button(self, cx, cy, w, h, text, cmd, bg="#ffd400", fg="#111111", font=None, team=None, flag=None):
        x0,y0,x1,y1=cx-w/2,cy-h/2,cx+w/2,cy+h/2
        kind='selected' if team and team==self.selected_country else ('card' if team else 'gold')
        self.visual.png(kind+'.png',x0,y0,w,h,slot=('button',round(cx),round(cy)))
        tx=cx
        right=x1
        if team:
            r=min(h*.29,w*.12);jx=x0+r*1.5
            self.jersey(jx,cy,r,team)
            fw=min(h*.58,w*.18);fh=fw*.66
            right=x1-fw-h*.12
            self.draw_flag(right+h*.04,cy-fh/2,fw,fh,flag or team)
            tx=(jx+r+right)/2
        self.cv.create_text(tx,cy,text=text,fill=fg,font=font or self.F(1),width=max(12,(right-tx)*2-8))
        self.buttons.append((x0,y0,x1,y1,cmd))

    def jersey(self, sx, sy, R, team, keeper=False, side=0, num=None):
        key=('jersey',round(sx,3),round(sy,3),round(R,3),team,keeper,side,num)
        # Moving players are rendered normally; static menu/bracket tokens reuse vectors.
        if self.state in ('menu','post','end','bracket') and not getattr(self, '_moving_token',False):
            self.cv.cached(key,lambda:self._jersey(sx,sy,R,team,keeper,side,num))
        else:
            self._jersey(sx,sy,R,team,keeper,side,num)

    def _jersey(self, sx, sy, R, team, keeper=False, side=0, num=None):
        base, shapes, edge = kit_for(team, keeper, side)
        cv = self.cv
        cv.create_oval(sx - R + R * 0.15, sy - R + R * 0.25, sx + R + R * 0.15, sy + R + R * 0.25,
                       fill="#062b14", width=0)                                    # sombra
        cv.create_oval(sx - R, sy - R, sx + R, sy + R, fill=base, width=0)
        for poly, col in shapes:
            flat = []
            for px, py in poly:
                flat += (sx + px * R, sy + py * R)
            cv.create_polygon(flat, fill=col, width=0)
        cv.create_arc(sx - R * 0.45, sy - R * 0.95, sx + R * 0.45, sy - R * 0.1, start=200, extent=140,
                      style="arc", outline=edge, width=max(1, R * 0.12))           # cuello
        cv.create_oval(sx - R, sy - R, sx + R, sy + R, outline=edge, width=max(1.5, R * 0.16))
        cv.create_arc(sx - R * 0.8, sy - R * 0.8, sx + R * 0.8, sy + R * 0.8, start=100, extent=70,
                      style="arc", outline="#ffffff", width=max(1, R * 0.1))       # brillo
        if num is not None and R >= 9:
            fg = text_on(base) if not shapes else ("#111111" if lum(base) > 150 else "#ffffff")
            cv.create_text(sx + 1, sy + R * 0.25 + 1, text=str(num), fill="#000000",
                           font=("Helvetica", -int(R * 0.85), "bold"))
            cv.create_text(sx, sy + R * 0.25, text=str(num), fill=fg if fg != "#000000" else "#fff",
                           font=("Helvetica", -int(R * 0.85), "bold"))

    def pitch_bg(self):
        self.visual.png('stadium.png',0,0,self.cw,self.ch,slot='background')

    def title(self, y, text, size=2.2, col="#ffd400"):
        self.cv.create_text(self.cw / 2 + 2, y + 2, text=text, fill="#000000", font=self.F(size),
                            width=self.cw * 0.95, justify="center")
        self.cv.create_text(self.cw / 2, y, text=text, fill=col, font=self.F(size),
                            width=self.cw * 0.95, justify="center")

    # ---------------- menú
    def draw_menu(self):
        cw, ch, u = self.cw, self.ch, self.u
        self.pitch_bg()
        self.title(u * 2.2, "MUNDIALITO", 2.4)
        self.cv.create_text(cw / 2, u * 4.4, text="Elige tu selección", fill="#ffffff", font=self.F(1.2))
        cols = 3 if cw < ch else 4
        rows = math.ceil(len(TEAMS) / cols)
        top, bottom = u * 5.6, ch - u * 4.6
        gap = u * 0.5
        bw = (cw - gap * (cols + 1)) / cols
        bh = min((bottom - top - gap * (rows - 1)) / rows, u * 6)
        y0 = top + ((bottom - top) - (bh * rows + gap * (rows - 1))) / 2
        for i, n in enumerate(TEAMS):
            c = TEAMS[n][1]
            x = gap + (i % cols) * (bw + gap) + bw / 2
            y = y0 + (i // cols) * (bh + gap) + bh / 2
            sn = SHORT[n]
            fs = min(0.95, bh / u * 0.3, bw * 0.52 / (u * 0.62 * max(6, len(sn))))
            self.button(x, y, bw, bh, f"{sn}\n{ABBR[n]}", lambda n=n: self.select_country(n),
                        bg="#123d24", fg="#ffffff", font=self.F(fs), team=n, flag=n)
        self.button(cw*.27,ch-u*3,min(cw*.42,u*12),u*2.2,
                    "SONIDO: SÍ" if self.snd.on else "SONIDO: NO",self.toggle_sound,font=self.F(.8))
        self.button(cw*.73,ch-u*3,min(cw*.42,u*12),u*2.2,"CONFIRMAR",
                    lambda:self.start_tournament(self.selected_country) if self.selected_country else None,
                    font=self.F(.8))

    def select_country(self, country):
        self.selected_country = country
        self.render()
        from kivy.animation import Animation
        Animation.cancel_all(self.cv,'opacity')
        self.cv.opacity=.82
        Animation(opacity=1,duration=.18,t='out_quad').start(self.cv)

    def sound_visual_event(self, name, team):
        if name == 'gol' and team == getattr(self,'user',None):
            self.visual.show_goal(3)

    def toggle_sound(self):
        self.snd.on = not self.snd.on
        self.render()

    # ---------------- v9: esperas que respetan la pausa
    def later(self, ms, fn):
        due, gen = vnow() + ms / 1000.0, self.gen

        def check():
            if gen != self.gen:
                return                                 # torneo reiniciado: se descarta
            if self.paused or vnow() < due:
                self.root.after(30, check)
            else:
                fn()
        self.root.after(min(ms, 30), check)

    # ---------------- v9: pausa
    def pause_rect(self):
        h = self.hud * 0.62
        m = self.hud * 0.19
        return (m, m, m + h * 1.25, m + h)

    def toggle_pause(self):
        if self.state not in ("match", "pens"):
            return
        self.paused = not self.paused
        clock_pause(self.paused)
        if self.paused:
            self.drag = None
            self.fire_pressed = False
            self.pausa_pressed = False
            self.info_pressed = None
            self.pen_hold = 0
            self.music.pause()
        else:
            self.music.resume()
        self.last_t = vnow()
        self.draw()

    @screen_change
    def restart_tournament(self):
        self.paused = False
        clock_pause(False)
        self.gen += 1
        self.drag = None
        self.pen_hold = 0
        self.gk_mode = False
        self.fire_reset()
        self.pausa_reset()
        self.ability_reset()
        self.music.stop()
        self.visual.gif_until = 0
        if getattr(self, 'defeat_music', None):
            self.defeat_music.stop()
        if hasattr(self, 'bracket_event'):
            self.bracket_event = None
        if getattr(self, "bracket_sound", None):
            self.bracket_sound.stop()
        self.go("menu")

    def pause_menu_rects(self):
        cw, ch, u = self.cw, self.ch, self.u
        bw, bh = min(cw * 0.7, u * 16), max(u * 3.2, 48)
        cx, cy = cw / 2, ch / 2
        return [(cx - bw / 2, cy - bh * 0.15 - bh, cx + bw / 2, cy - bh * 0.15, "CONTINUAR", "#3cff6e",
                 self.toggle_pause),
                (cx - bw / 2, cy + bh * 0.55, cx + bw / 2, cy + bh * 1.55, "REINICIAR TORNEO", "#ff5a4a",
                 self.restart_tournament)]

    def draw_pause_button(self):
        cv = self.cv
        x0, y0, x1, y1 = self.pause_rect()
        cv.create_rectangle(x0, y0, x1, y1, fill="#ffd400", outline="#ffffff", width=2)
        bw, bh = (x1 - x0), (y1 - y0)
        if self.paused:                                # triángulo de "play"
            cv.create_polygon([x0 + bw * 0.35, y0 + bh * 0.22, x0 + bw * 0.35, y0 + bh * 0.78,
                               x0 + bw * 0.72, y0 + bh * 0.5], fill="#111111")
        else:                                          # dos barras de pausa
            for fx in (0.3, 0.56):
                cv.create_rectangle(x0 + bw * fx, y0 + bh * 0.22, x0 + bw * (fx + 0.14), y0 + bh * 0.78,
                                    fill="#111111", width=0)

    def draw_pause_overlay(self):
        cv,cw,ch,u=self.cv,self.cw,self.ch,self.u
        rects=self.pause_menu_rects()
        bx0=rects[0][0]-u*1.1;bx1=rects[0][2]+u*1.1
        by0=rects[0][1]-u*4.2;by1=rects[1][3]+u*1.3
        cv.create_rectangle(0,0,cw,ch,fill='#021f22',width=0,alpha=.6)
        self.visual.png('panel.png',bx0,by0,bx1-bx0,by1-by0,slot='pause')
        cv.create_text(cw/2,by0+u*2.2,text='PAUSA',fill='#ffd400',font=self.F(2))
        for x0,y0,x1,y1,txt,col,_ in rects:
            self.visual.png(('continue' if txt=='CONTINUAR' else 'restart')+'.png',x0,y0,x1-x0,y1-y0,slot=txt)
            cv.create_text((x0+x1)/2,(y0+y1)/2,text=txt,fill='#082d29',font=self.F(1.2))

    # ---------------- torneo
    @screen_change
    def start_tournament(self, team):
        self.user = team
        self.snd.prepare(team)                         # se genera en segundo plano
        # v7: 24 selecciones en el catálogo; a octavos van 16 (la tuya + 15 al azar)
        others = [t for t in TEAMS if t != team]
        random.shuffle(others)
        self.round_teams = [team] + others[:15]
        random.shuffle(self.round_teams)
        self.round = 0
        self.results = []
        self.init_bracket()
        self.go("bracket")

    def pairs(self):
        t = self.round_teams
        return [(t[i], t[i + 1]) for i in range(0, len(t), 2)]

    def sim_match(self, a, b):
        ra, rb = rating(a), rating(b)
        pa = 0.18 + (ra - rb) * 0.01
        pb = 0.18 + (rb - ra) * 0.01
        ga = sum(random.random() < pa for _ in range(8))
        gb = sum(random.random() < pb for _ in range(8))
        txt = f"{a} {ga}-{gb} {b}"
        if ga == gb:
            w = a if random.random() < 0.5 + (ra - rb) * 0.02 else b
            txt += f" (pen. {w})"
        else:
            w = a if ga > gb else b
        return w, txt

    def end_screen(self, msg, col):
        self.end_msg, self.end_col = msg, col
        self.go("end")

    def draw_end(self):
        cw, ch, u = self.cw, self.ch, self.u
        self.pitch_bg()
        self.jersey(cw / 2, ch * 0.18, u * 2.5, self.user, num=10)
        self.title(ch * 0.33, self.end_msg, 2.0, self.end_col)
        self.cv.create_text(cw / 2, ch * 0.39, text=FULL_NAME[self.user], fill="#d9ffe6",
                            font=self.F(0.9, False), width=cw * 0.95)
        y = ch * 0.45
        for r, res in enumerate(self.results):
            for line in res:
                if line.startswith("*"):
                    self.cv.create_text(cw / 2, y, text=f"{ROUND_NAMES[r]}: {line[2:]}", fill="#ffffff",
                                        font=self.F(0.95), width=cw * 0.95)
                    y += u * 1.6
        self.button(cw / 2, ch - u * 2.5, min(cw * 0.8, u * 16), u * 2.8, "Volver al menú",
                    lambda: self.go("menu"), font=self.F(1.2))

    # ---------------- partido
    @screen_change
    def start_match(self, opp):
        self.ai_reset()
        self.fire_reset()
        self.pausa_reset()
        self.ability_reset()
        if getattr(self, 'bracket_sound', None):
            self.bracket_sound.stop()                  # el avance suena completo hasta pulsar el botón
        self.visual.texture('fuego.png')
        self.visual.texture('pausa.png')
        if self.snd.backend == 'kivy':
            for name in ('fuego', 'pausa_inicio'):
                path = self.snd.files[('', name)]
                self.snd.cache[path] = self.snd.SL.load(path)
        self.teams = [self.user, opp]
        self.snd.prepare(self.user, opp)
        # dorsales: arquero fijo con el 1, los de campo al azar y sin repetir
        self.nums = [[1] + random.sample(range(2, 24), 5) for _ in (0, 1)]
        self.score = [0, 0]
        self.shots = 0
        self.clock = 0.0                               # segundos reales jugados
        self.mark = 0
        self.period = "1er tiempo"
        self.state = "match"
        self.recalc()
        self.reset_positions()
        self.kickoff(0)
        self.buttons = []
        self.snd.play("pito")
        self.paused = False
        clock_pause(False)
        self.music.start()                             # v9: fade-in desde 0 % hasta MUSIC_VOL

    def reset_positions(self):
        self.fire.clear()
        self.bodies = []
        for t in (0, 1):
            for i, (fx, fy) in enumerate(FORMATION):
                if t == 1:
                    fx = 1 - fx
                self.bodies.append(Body(FX0 + fx * (FX1 - FX0), FY0 + fy * (FY1 - FY0), PR, PM, t,
                                        keeper=(i == 0), num=self.nums[t][i]))
        self.ball = Body((FX0 + FX1) / 2, MY, BR, BM)
        self.bodies.append(self.ball)
        self.drag = None
        self.gk_reset()

    def clock_text(self):
        """Tiempo de juego a escala: cada segundo real = 30 s de fútbol."""
        gs = int(self.clock * 60 / REAL_PER_MIN)
        return f"{gs // 60:02d}:{gs % 60:02d}"

    def can_shoot(self, team, now=None, keeper=False):
        now = vnow() if now is None else now
        if self.phase != "play":
            return False
        if keeper:                                     # v8: el arquero tiene su propia recarga
            return self.kick_team is None and now >= self.gk_next[team]
        if self.kick_team is not None:                 # saque inicial: solo el que saca
            return team == self.kick_team
        return now >= self.next_shot_at[team]          # recarga propia de ESE equipo

    def flash(self, text, secs=1.5):
        self.msg, self.msg_until = text, vnow() + secs

    def kickoff(self, team):
        """Solo `team` puede hacer el primer tiro; luego el juego es libre."""
        now = vnow()
        self.phase = "play"
        self.kick_team = team
        self.next_shot_at = [now, now]                 # un temporizador por equipo
        self.gk_next = [now, now]                      # v8: recarga propia de cada arquero
        self.pending = None
        self.ai_at = now + random.uniform(0.7, 1.2)
        self.ai_gk_at = now + random.uniform(0.4, 0.8)

    def ai_delay(self):
        # reacción de la CPU tras terminar la recarga (mejor rating = más rápida)
        if self.ai_hard():
            return 0.0
        r = rating(self.teams[1])
        return random.uniform(0.25, 0.75) * (1.6 - r / 100)

    def shoot(self, body, vx, vy):
        sp = math.hypot(vx, vy)
        cap = MAX_DRAG * POWER
        selected = self.fire.selected(body)
        special = self.state == 'match' and not body.keeper and selected and selected['phase'] == 'aim' and not self.fire.executing()
        if special:
            cap *= POWER_FACTOR
        if self.state == "match" and body.keeper:
            cap *= GK_POWER                             # v8: arquero a la mitad de potencia
        if sp > cap:
            vx, vy = vx / sp * cap, vy / sp * cap
        if special:
            self.fire.launch(body, vx, vy, vnow(), self.round,
                             None if body.team == 0 else self.ai_fire_recharge())
        if self.state == "match" and self.held is body:
            # el arquero con el balón: el arrastre lo suelta en esa dirección (el arquero no se mueve)
            self.release_ball(vx * 1.3, vy * 1.3)
        else:
            body.vx, body.vy = vx, vy
        if self.state == "match":
            now = vnow()
            self.shots += 1
            self.shooter = body.team
            self.kick_team = None                       # desde aquí, juego libre
            t = body.team
            if body.keeper:                             # v8: el arquero no gasta la recarga del equipo
                self.gk_next[t] = now + COOLDOWN
                if t == 1:
                    self.ai_gk_at = self.gk_next[1] + random.uniform(0.1, 0.35)
            else:
                # solo se recarga el equipo que tiró; el rival NO se toca
                self.next_shot_at[t] = now + (ENHANCED_COOLDOWN if t == 1 and self.ai_hard() else COOLDOWN)
                if t == 1:
                    self.ai_at = self.next_shot_at[1] + self.ai_delay()
            self.snd.play("toque", dur=0.15)
        else:
            self.moving = True
            self.frames = 0

    def check_period(self):
        """Gestiona descanso / fin / prórroga. Devuelve True si el partido no continúa normal."""
        if self.mark >= len(MARKS) or self.clock < MARKS[self.mark]:
            return False
        i = self.mark
        self.clock = MARKS[i]
        self.mark += 1
        tie = self.score[0] == self.score[1]
        if i == 0:
            self.period = "2do tiempo"; self.flash("Descanso - ¡Segundo tiempo!", 2)
            self.snd.play("pito_medio")
            self.reset_positions(); self.kickoff(1)
        elif i == 1:
            if not tie:
                self.snd.play("pito_final", dur=1.8)
                self.match_over(); return True
            self.period = "PRÓRROGA 1"; self.flash("¡Empate! Vamos a la prórroga", 2)
            self.snd.play("pito_medio")
            self.reset_positions(); self.kickoff(0)
        elif i == 2:
            self.period = "PRÓRROGA 2"; self.flash("Cambio de lado: 2º tiempo de la prórroga", 2)
            self.snd.play("pito_medio")
            self.reset_positions(); self.kickoff(1)
        else:
            self.snd.play("pito_final", dur=1.8)
            if tie:
                self.start_penalties()
            else:
                self.match_over()
        return True

    # ---------------- IA (v8): campo y arquero separados
    def predict(self, b, t):
        k = (1 - FRICTION ** t) / (1 - FRICTION)
        return (min(max(b.x + b.vx * k, FX0 + 20), FX1 - 20),
                min(max(b.y + b.vy * k, FY0 + 20), FY1 - 20))

    def lane_free(self, x0, y0, x1, y1, team, gap=PR + BR + 4):
        """True si ningún rival de `team` corta la línea (x0,y0)-(x1,y1)."""
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy or 1
        for p in self.bodies:
            if p.team is None or p.team == team or p is self.ball:
                continue
            t = max(0.0, min(1.0, ((p.x - x0) * dx + (p.y - y0) * dy) / L2))
            if math.hypot(x0 + dx * t - p.x, y0 + dy * t - p.y) < gap:
                return False
        return True

    def strike(self, p, ax, ay, ball_v, noise):
        """Lanza la ficha p para llegar a (ax, ay) y darle al balón ~ball_v."""
        cap = MAX_DRAG * POWER
        if self.fire.selected(p):
            cap *= POWER_FACTOR
            ball_v *= POWER_FACTOR
        px, py = ax - p.x, ay - p.y
        dist = math.hypot(px, py) or 1
        # choque ficha(3)-balón(1) con e=0,92: el balón sale ~1,44 veces más rápido
        v = ball_v / 1.44 + dist * (1 - PLAYER_FRICTION) * 1.1
        v = min(max(v, cap * 0.35), cap)
        ang = math.atan2(py, px) + random.gauss(0, noise)
        self.shoot(p, math.cos(ang) * v, math.sin(ang) * v)
    def ai_shoot(self):
        """v11: CPU de campo. Tiro a portería con la máxima potencia y tiro con efecto si está listo.
        Pases hacia adelante con potencia variable, rebote, pase atrás solo con compañero en su vector,
        empuje al rival que va por el balón suelto, o espera."""
        now = vnow()
        b = self.ball
        hard = self.ai_hard()
        field = [p for p in self.bodies if p.team == 1 and not p.keeper]
        noise = (100 - rating(self.teams[1])) * (0.001 if hard else 0.005)
        cap = MAX_DRAG * POWER * self.cpu_normal_factor()
        plan = self.ai_fire_plan(field)
        if plan is not None:
            _, special_player, sx, sy, gy, bank = plan
            if self.fire_ai(special_player, "tiro", math.hypot(sx - FX0, sy - MY)):
                dx, dy = sx - special_player.x, sy - special_player.y
                distance = math.hypot(dx, dy)
                self.shoot(special_player, dx / distance * MAX_DRAG * POWER * self.cpu_fire_factor(),
                           dy / distance * MAX_DRAG * POWER * self.cpu_fire_factor())
                return
        # 1) rival que va por el balón suelto: a veces lo empujamos en vez de tirar al balón
        if b.speed() < 5 and random.random() < (0.7 if hard else 0.45) and self.push_rival(field):
            return
        bx, by = self.predict(b, 22)
        ukeep = next((p for p in self.bodies if p.team == 0 and p.keeper), None)
        if ukeep is not None and ukeep.y > MY:
            gy = random.uniform(GY0 + 12, MY - 10)
        elif ukeep is not None:
            gy = random.uniform(MY + 10, GY1 - 12)
        else:
            gy = MY + random.uniform(-45, 45)
        gdist = math.hypot(bx - FX0, by - MY)
        recv = None
        # 2) intento a portería si el carril está libre
        if gdist <= (480 if hard else 300) and self.lane_free(bx, by, FX0, gy, 1):
            target, kind = (FX0 - 15, gy), "tiro"
        else:
            # 3) pase hacia adelante, hacia donde estará el compañero (menos frecuente que antes)
            best_m = self.best_forward(field, bx, by)
            if best_m is not None and random.random() < (0.6 if hard else 0.45):
                target, kind, recv = self.lead_point(best_m, b.x, b.y), "pase", best_m
            else:
                # 4) rebote en banda, o 5) pase atrás solo si hay un compañero en su vector
                bank = self.bank_point(bx, by, gy)
                blocker = self.own_blocker(bx, by)
                if bank is not None and random.random() < 0.5:
                    target, kind = bank, "tiro"
                elif blocker is not None and random.random() < (0.8 if hard else 0.6):
                    target, kind, recv = self.lead_point(blocker, b.x, b.y), "pase", blocker
                else:
                    self.ai_at = now + random.uniform(0.2, 0.4)   # espera sin disparar
                    return
        tx, ty = target
        dx, dy = tx - bx, ty - by
        d = math.hypot(dx, dy) or 1
        ux, uy = dx / d, dy / d
        ax, ay = bx - ux * (PR + BR - 3), by - uy * (PR + BR - 3)
        best, bscore = None, 1e9
        for p in field:
            if p is recv:
                continue
            dist = math.hypot(ax - p.x, ay - p.y)
            ahead = (p.x - bx) * ux + (p.y - by) * uy
            score = dist + (500 if ahead > 0 else 0)
            if score < bscore:
                best, bscore = p, score
        if best is None:
            self.ai_at = now + random.uniform(0.2, 0.4)
            return
        if kind == "tiro":
            # máxima potencia: entre el 90 % y el 100 % del tiro normal más fuerte
            ball_v = cap * 1.44 * random.uniform(0.9, 1.0)
            if random.random() < (1.0 if hard else 0.9):
                self.fire_goal_ai(best)                  # tiro con efecto si está listo
        else:
            # pase con potencia variable: a veces más suave, a veces más fuerte, sin pasar del 85 %
            needed = d * (1 - FRICTION) * random.uniform(0.92, 1.12) + 2.0
            ball_v = min(needed, cap * 1.44 * 0.85)
        self.strike(best, ax, ay, ball_v, noise)
    

    def gk_target(self, k):
        """v10: a dónde va el arquero CPU: intercepta tiros, sale a despejar balones sueltos
        en su área grande o vuelve a su posición base, adelantándose según el balón."""
        b = self.ball
        right = k.team == 1
        line = FX1 if right else FX0
        sgn = -1 if right else 1                         # hacia dentro de la cancha
        gx = line + sgn * 28                             # línea de gol del arquero
        toward = (b.vx > 0.3) if right else (b.vx < -0.3)
        if toward:
            t = (k.x - b.x) / b.vx
            if t > 0:
                y = b.y + b.vy * t                       # trayectoria con rebotes en bandas
                h = FY1 - FY0
                y = (y - FY0) % (2 * h)
                y = FY0 + (y if y <= h else 2 * h - y)
                return gx, y, True
        dpen = abs(b.x - line)
        if dpen < BIG_W and abs(b.y - MY) < BIG_H and b.speed() < 4:
            return b.x, b.y, False                       # balón suelto en su área: sale a despejarlo
        f = 0.3 + 0.4 * max(0.0, 1 - dpen / 500)         # posición base: sigue al balón con cautela
        off = min(25, max(0.0, 300 - dpen) * 0.1)        # se adelanta si el balón está cerca
        return gx + sgn * off, MY + (b.y - MY) * f, False

    def ai_keeper(self):
        """v11: arquero CPU. Toma el balón que le llega y lo saca a un compañero con potencia real;
        si no, revisa el balón cada fotograma y acelera suavemente hacia su posición."""
        k = next((p for p in self.bodies if p.team == 1 and p.keeper), None)
        if k is None or self.state != "match" or self.phase != "play":
            return
        now = vnow()
        b = self.ball
        if (math.hypot(b.x - k.x, b.y - k.y) <= k.r + b.r + 3 and b.speed() < 6
                and self.can_shoot(1, now) and random.random() < (0.85 if self.ai_hard() else 0.6)):
            mates = [p for p in self.bodies if p.team == 1 and not p.keeper]
            best, bs = None, 1e9
            for m in mates:
                if not self.lane_free(b.x, b.y, m.x, m.y, 1):
                    continue
                tx, ty = self.lead_point(m, b.x, b.y)
                s = math.hypot(tx - FX0, ty - MY)          # el compañero más adelantado
                if s < bs:
                    best, bs = (tx, ty), s
            if best is not None:
                dx, dy = best[0] - b.x, best[1] - b.y
                d = math.hypot(dx, dy) or 1
                cap = MAX_DRAG * POWER * self.cpu_normal_factor() * 0.8   # saque fuerte, no al máximo
                v = min(cap * 1.44, d * (1 - FRICTION) * random.uniform(0.95, 1.1) + 2.0)
                b.vx, b.vy = dx / d * v, dy / d * v        # el arquero saca el balón a un compañero
                self.next_shot_at[1] = now + COOLDOWN
                return
        if self.gk_tx is None or now >= self.ai_gk_at:
            tx, ty, urgent = self.gk_target(k)
            if urgent and not self.gk_urgent and self.gk_tx is not None:
                # tiro nuevo: reacciona con un instante de retraso, como una persona
                self.gk_urgent = True
                self.ai_gk_at = now + (0.05 if self.ai_hard() else random.uniform(0.12, 0.22))
                return
            self.gk_urgent = urgent
            tx, ty = self.clamp_area(k, tx, ty)
            err = 0.0 if self.ai_hard() else (100 - rating(self.teams[1])) * 0.12   # error leve, en px
            self.gk_tx, self.gk_ty = tx, ty + random.gauss(0, err)
            self.ai_gk_at = now + random.uniform(0.06, 0.12)
        dx, dy = self.gk_tx - k.x, self.gk_ty - k.y
        d = math.hypot(dx, dy)
        if d < 2:
            return
        vmax = GK_CPU_SPEED_URGENT if self.gk_urgent else GK_CPU_SPEED
        want = min(vmax, d * GK_CPU_BRAKE)
        k.vx += (dx / d * want - k.vx) * GK_CPU_ACCEL
        k.vy += (dy / d * want - k.vy) * GK_CPU_ACCEL
                
        

    # ---------------- barrera del área grande (solo arqueros)
    def clamp_area(self, k, x, y):
        r = k.r
        if k.team == 1:
            x = min(max(x, FX1 - BIG_W + r), FX1 - r)
        else:
            x = min(max(x, FX0 + r), FX0 + BIG_W - r)
        y = min(max(y, MY - BIG_H + r), MY + BIG_H - r)
        return x, y

    def keeper_limit(self, k):
        nx, ny = self.clamp_area(k, k.x, k.y)
        if nx != k.x:
            k.x, k.vx = nx, -k.vx * 0.3
        if ny != k.y:
            k.y, k.vy = ny, -k.vy * 0.3

    def check_goal(self):
        b = self.ball
        if b.x + b.r < FX0:
            return 1
        if b.x - b.r > FX1:
            return 0
        return None

    def match_update(self, dt):
        now = vnow()
        self.ai_update_difficulty()
        self.fire_update(dt)
        fire_scale = self.fire.scale(dt)               # física: fuego (PAUSA va por cuerpo)
        lim = self.keeper_limit                        # v8: barrera del área grande
        if self.phase == "goal":
            step(self.bodies, self.ball, fire_scale, None, None, lim, body_scale=self.pausa_body_scale)
            if now >= self.resume_at:
                self.reset_positions()
                if not self.check_period():
                    self.kickoff(1 - self.scorer)
            return
        sl = min(self.slowmo(), fire_scale)            # física sin PAUSA
        self.clock += dt * min(sl, self.pausa_scale()) # cronómetro: también al 60 % con PAUSA
        if self.check_period():
            return
        touch = None
        if self.gk_mode and self.gk_released_at is not None:
            touch = {"k": self.ctrl_keeper(), "hit": False}
            flight = next((s for s in self.fire.shots.values() if s['phase'] == 'flight'), None)
            if flight and not self.fire.keeper_blocks(flight, touch['k'], (FX0+FX1)/2):
                touch = None
        step(self.bodies, self.ball, sl, None, None, lim, touch, self.fire_collision, body_scale=self.pausa_body_scale)
        self.fire_update(0)
        if touch and touch["hit"]:                      # bloqueo + rebote: velocidad normal
            self.gk_mode = False
            self.gk_released_at = None
            self.flash("¡BLOQUEO DEL ARQUERO!", 1.0)
            self.snd.play("uy", dur=0.8)
        elif (self.gk_mode and self.gk_released_at is not None
              and now - self.gk_released_at > GK_SLOW_MAX):
            self.gk_mode = False                        # seguro: no quedarse en cámara lenta
            self.gk_released_at = None
        g = self.check_goal()
        if g is not None:
            self.fire.clear()
            self.score[g] += 1
            self.ai_update_difficulty()
            self.scorer = g
            self.flash(f"¡¡GOOOOL de {self.teams[g]}!!", 2.0)
            self.snd.play("gol", self.teams[g], 2.6)
            self.phase = "goal"
            self.resume_at = now + 2.2
            self.drag = None
            self.gk_mode = False; self.gk_ctrl = False; self.dash = None; self.gk_hold = 0
            self.gk_released_at = None
            return
        # tiro del jugador soltado durante la recarga: sale apenas termina
        if self.pending and self.can_shoot(0, now, self.pending[0].keeper):
            p, vx, vy = self.pending
            self.pending = None
            self.shoot(p, vx, vy)
        self.pausa_ai()
        if self.can_shoot(1, now) and now >= self.ai_at:
            self.ai_shoot()
        self.ai_keeper()                                             # v10: arquero CPU en cada fotograma
        
            

    @screen_change
    def match_over(self, pen_text=""):
        self.fire.clear()
        self.pausa.finish()
        a, b = self.teams
        if pen_text:
            w = pen_text.split("gana ")[-1]
        else:
            w = a if self.score[0] > self.score[1] else b
        self.post_txt = f"{a} {self.score[0]}-{self.score[1]} {b}" + (f" ({pen_text})" if pen_text else "")
        self.post_w = w
        self.paused = False
        clock_pause(False)
        self.music.fade_out_end()
        self.go('post')
        self.later(1100, lambda: self.state == 'post' and self.snd.play('gana', w, 4))
        if False and not pen_text:                               # tras el pitazo, festeja el ganador
            self.later(1500, lambda: self.state == "post" and self.snd.play("gana", w, 4))

    def draw_post(self):
        cw, ch, u = self.cw, self.ch, self.u
        self.pitch_bg()
        self.title(ch * 0.25, "FINAL DEL PARTIDO", 2.0)
        a, b = self.teams
        self.jersey(cw * 0.3, ch * 0.42, u * 2, a, num=10)
        self.jersey(cw * 0.7, ch * 0.42, u * 2, b, num=10)
        self.cv.create_text(cw / 2, ch * 0.42, text=f"{self.score[0]} - {self.score[1]}", fill="#ffffff",
                            font=self.F(2.2))
        for x, t in ((cw * 0.3, a), (cw * 0.7, b)):
            self.cv.create_text(x, ch * 0.42 + u * 3, text=SHORT[t], fill="#ffffff", font=self.F(0.9))
        self.cv.create_text(cw / 2, ch * 0.56, text=self.post_txt, fill="#ffffff", font=self.F(1.1),
                            width=cw * 0.92, justify="center")
        self.button(cw / 2, ch * 0.72, min(cw * 0.7, u * 14), u * 2.8, "Continuar",
                    lambda: self.finish_user_match(self.post_w, self.post_txt), font=self.F(1.3))

    # ---------------- penales
    @screen_change
    def start_penalties(self):
        self.fire.clear()
        self.pausa.finish()
        self.pens = [[], []]
        self.pen_k = 0
        self.state = "pens"
        self.recalc()
        self.setup_kick()
        self.go("pens")
        self.buttons = []
        self.flash("¡TANDA DE PENALES!", 2)
        self.music.fade_to(MUSIC_PEN_VOL, MUSIC_FADE_OUT)   # v9: fade-out, sigue de fondo

    def setup_kick(self):
        shooter = self.pen_k % 2
        self.keeper = Body(FX1 - PR - 2, MY, PR, PM, 1 - shooter, keeper=True, num=1)
        self.ball = Body(FX1 - 130, MY, BR, BM)
        self.bodies = [self.keeper, self.ball]
        self.moving = False
        self.pen_wait = True
        self.lock = False
        self.drag = None
        self.aim_y = MY
        self.dived = False
        self.pen_hold = 0
        self.cd_start = vnow() + (2.0 if self.pen_k == 0 else 0.0)
        self.ai_kick_at = None
        self.ai_target = None
        self.gk_reset()
        if self.pen_k % 2 == 1:                         # v7: tú atajas -> arquero con DASH
            self.anchor_keeper()

    def countdown(self, now=None):
        """Devuelve (texto, listo). 3 -> 2 -> 1 -> ¡PREPÁRATE! (desde aquí se puede tirar)."""
        now = vnow() if now is None else now
        t = now - self.cd_start
        if t < 0:
            return None, False
        k = int(t / CD_STEP)
        if k < 3:
            return str(3 - k), False
        if k == 3:
            return "¡PREPÁRATE!", True
        return None, True

    def pen_ready(self):
        return self.pen_wait and not self.lock and self.countdown()[1]

    def pen_key(self, d):
        if self.paused:
            return
        """d=-1 izquierda, 1 derecha, 0 tirar. Como arquero: mantener = cargar DASH, soltar = DASH."""
        if self.state == "match":                       # v8: en partido el arquero se arrastra
            return
        if self.state != "pens":
            return
        if self.pen_k % 2 == 1:
            if d != 0:
                self.gk_press(d)
            return
        if not self.pen_ready():
            return
        if d == 0:
            self.pen_kick()
        else:
            self.move_aim(d * 14)

    def move_aim(self, dy):
        self.aim_y = min(max(self.aim_y + dy, PEN_GY0 - 25), PEN_GY1 + 25)
        # el balón también se desliza hacia ese lado
        self.ball.y = MY + (self.aim_y - MY) * 0.35

    def pen_kick(self, sp=15.5):
        dx, dy = FX1 + 30 - self.ball.x, self.aim_y - self.ball.y
        d = math.hypot(dx, dy)
        self.shoot(self.ball, dx / d * sp, dy / d * sp)
        self.pen_wait = False
        self.keeper.vy = random.choice([-1, 1]) * random.uniform(2, 8.5)

    def user_dive(self, wy):
        self.dived = True
        self.ai_penalty(wy)

    def pen_result(self, goal, msg=None):
        self.moving = False
        self.gk_hold = 0
        self.pens[self.pen_k % 2].append(goal)
        self.flash(msg or ("¡GOL!" if goal else "¡FALLÓ / ATAJADA!"), 1.3)
        if goal:
            self.snd.play("penal", self.teams[self.pen_k % 2], 1.2)
        else:
            self.snd.play("uy", dur=1.2)
        self.pen_k += 1
        self.lock = True
        self.later(1500, self.next_kick)

    def next_kick(self):
        if self.state != "pens":
            return
        a, b = sum(self.pens[0]), sum(self.pens[1])
        na, nb = len(self.pens[0]), len(self.pens[1])
        done = False
        if na <= 5 and nb <= 5 and (a + (5 - na) < b or b + (5 - nb) < a):
            done = True
        if na == nb and na >= 5 and a != b:
            done = True
        if done:
            w = self.teams[0] if a > b else self.teams[1]
            if w == self.user:
                self.snd.play("gana", w, 4)
            else:
                self.snd.play("derrota", dur=2.3)
            return self.match_over(f"penales {a}-{b}, gana {w}")
        self.setup_kick()

    def ai_penalty(self, dive_y):
        self.keeper.vy = max(-9, min(9, (dive_y - MY) * 0.09))
        ty = random.uniform(PEN_GY0 + 8, PEN_GY1 - 8) + random.gauss(0, 18)
        dx, dy = FX1 + 30 - self.ball.x, ty - self.ball.y
        d = math.hypot(dx, dy)
        sp = random.uniform(13, 17)
        self.ball.vx, self.ball.vy = dx / d * sp, dy / d * sp
        self.moving = True; self.frames = 0; self.pen_wait = False

    def cpu_kick(self):
        """La CPU tira el penal (tú atajas con DASH)."""
        ty = self.ai_target if self.ai_target is not None else MY
        dx, dy = FX1 + 30 - self.ball.x, ty - self.ball.y
        d = math.hypot(dx, dy)
        sp = random.uniform(8.5, 11.5)
        self.ball.vx, self.ball.vy = dx / d * sp, dy / d * sp
        self.moving = True; self.frames = 0; self.pen_wait = False
        self.snd.play("toque", dur=0.15)

    def pens_update(self):
        now = vnow()
        user_keeps = self.pen_k % 2 == 1
        sl = self.slowmo()
        if self.pen_wait and not self.lock and self.countdown(now)[1]:
            if self.pen_hold and not user_keeps:
                self.move_aim(self.pen_hold * 3)
            if user_keeps:                              # la CPU apunta y tira tras un instante
                if self.ai_kick_at is None:
                    self.ai_kick_at = now + random.uniform(1.2, 2.0)
                    self.ai_target = random.uniform(PEN_GY0 + 8, PEN_GY1 - 8) + random.gauss(0, 14)
                elif now >= self.ai_kick_at:
                    self.cpu_kick()
        self.gk_update(sl)
        if not self.moving and not self.dash:
            return
        catcher = self.keeper if (user_keeps and self.moving and self.held is None) else None
        caught = step(self.bodies, self.ball, sl, self.gk_zone_factor, catcher, goal=(PEN_GY0, PEN_GY1, PEN_GD))
        if caught:
            self.on_catch(self.keeper)
        self.gk_after_step()
        if not self.moving:
            return
        if caught:
            self.pen_result(False, "¡ATAJADA!")
            return
        self.frames += sl
        b = self.ball
        if b.x - b.r > FX1 and PEN_GY0 < b.y < PEN_GY1:
            self.pen_result(True)
        elif b.speed() == 0 or self.frames > 300 or (b.vx < -0.5 and b.x < FX1 - 160):
            self.pen_result(False)

    # ---------------- ARQUERO (v7): DASH lateral, cámara lenta y posesión
    def gk_reset(self):
        self.gk_mode = False        # control del arquero activo (cámara lenta)
        self.gk_ctrl = False        # arquero anclado: solo se mueve con DASH lateral
        self.gk_hold = 0            # flecha mantenida (-1 izquierda / 1 derecha)
        self.gk_t0 = 0.0
        self.gk_power = 0.0
        self.dash = None
        self.trail = []
        self.held = None            # arquero que tiene el balón (posesión)
        self.gk_ax = self.gk_ay = 0.0
        self.gk_btns = []
        self.gk_released_at = None  # v8: momento en que se soltó al arquero arrastrado
        self.gk_tx = self.gk_ty = None   # v10: destino actual del arquero CPU
        self.gk_urgent = False           # v10: reaccionando a un tiro
        

    def ctrl_keeper(self):
        """Arquero que controla el usuario."""
        if self.state == "pens":
            return self.keeper
        for b in self.bodies:
            if b.team == 0 and b.keeper:
                return b
        return None

    def slowmo(self):
        if self.state == "match":
            return SLOWMO_MATCH if self.gk_mode else 1.0
        if self.state == "pens" and self.pen_k % 2 == 1 and not self.lock and self.countdown()[1]:
            return SLOWMO
        return 1.0

    def gk_allowed(self):
        if self.state == "match":
            return self.gk_mode and self.phase == "play"
        if self.state == "pens":
            return self.pen_k % 2 == 1 and not self.lock and self.countdown()[1]
        return False

    def gk_zone_factor(self, b):
        """Arquero: velocidad normal dentro de su área chica, 10 % fuera de ella."""
        if self.state == "match" and b.team == 1:
            return 1.0                  # v10: el arquero CPU se mueve normal en toda su área grande        
        right = self.state == "pens" or b.team == 1
        m = b.r * 0.5
        if right:
            inx = FX1 - SMALL_W - m <= b.x <= FX1 + m
        else:
            inx = FX0 - m <= b.x <= FX0 + SMALL_W + m
        return 1.0 if (inx and abs(b.y - MY) <= SMALL_H * (PEN_GOAL_SCALE if self.state == "pens" else 1) + m) else GK_OUT_SPEED

    def anchor_keeper(self):
        k = self.ctrl_keeper()
        if k:
            self.gk_ctrl = True
            self.gk_ax, self.gk_ay = k.x, k.y
            k.vx = k.vy = 0.0

    def toggle_gk(self):
        if self.state != "match" or self.phase != "play":
            return
        if self.held:
            self.flash("Tu arquero tiene el balón", 1.2)
            return
        if self.gk_mode:
            self.gk_mode = False; self.gk_ctrl = False; self.dash = None; self.gk_hold = 0
        else:
            self.gk_mode = True
            self.anchor_keeper()
            if self.drag is not None and self.drag.keeper:
                self.drag = None

    def gk_charge(self, now=None):
        if not self.gk_hold:
            return self.gk_power
        now = vnow() if now is None else now
        return min(1.0, (now - self.gk_t0) / DASH_CHARGE)

    def gk_press(self, d):
        if not self.gk_allowed() or self.gk_hold == d:
            return
        self.gk_hold = d
        self.gk_t0 = vnow()

    def gk_release(self):
        if self.paused:
            return
        if not self.gk_hold:
            return
        d = self.gk_hold
        p = max(0.08, self.gk_charge())
        self.gk_hold = 0
        self.gk_power = p
        if self.gk_allowed():
            self.start_dash(d, p)

    def start_dash(self, d, p):
        """DASH lateral: izquierda = -y, derecha = +y (izquierda/derecha de la pantalla en vertical)."""
        k = self.ctrl_keeper()
        if k is None:
            return
        if not self.gk_ctrl:
            self.anchor_keeper()
        dist = DASH_MIN + (DASH_MAX - DASH_MIN) * p
        if self.state == "pens":
            lo, hi = PEN_GY0 - 30*PEN_GOAL_SCALE, PEN_GY1 + 30*PEN_GOAL_SCALE
        else:
            lo, hi = FY0 + k.r, FY1 - k.r
        ty = min(max(k.y + d * dist, lo), hi)
        self.dash = {"k": k, "ty": ty, "v": DASH_V_MIN + (DASH_V_MAX - DASH_V_MIN) * p, "f": 0.0}
        self.snd.play("toque", dur=0.1)

    def gk_update(self, scale):
        dsh = self.dash
        if not dsh:
            return
        k = dsh["k"]
        rem = dsh["ty"] - k.y
        dsh["f"] += scale
        if abs(rem) < 0.6 or dsh["f"] > 45:
            k.vy = 0.0
            self.dash = None
            return
        k.vx = 0.0
        k.vy = math.copysign(min(abs(rem), dsh["v"]), rem)
        self.trail.append((k.x, k.y, vnow(), k.team))

    def gk_after_step(self):
        """Mantiene al arquero donde terminó su DASH (no vuelve ni se mueve solo)."""
        if not self.gk_ctrl:
            return
        k = self.ctrl_keeper()
        if k is None:
            return
        k.x, k.vx = self.gk_ax, 0.0
        if self.dash:
            self.gk_ay = k.y
        else:
            k.y, k.vy = self.gk_ay, 0.0
        if self.held is k:
            self.pin_ball()

    def pin_ball(self):
        k, b = self.held, self.ball
        face = 1 if k.x < (FX0 + FX1) / 2 else -1
        b.x, b.y = k.x + face * (k.r + b.r + 1), k.y
        b.vx = b.vy = 0.0

    def on_catch(self, k):
        """Atajada: el arquero se queda con el balón y vuelve la velocidad normal."""
        self.held = k
        self.dash = None
        self.gk_hold = 0
        k.vy = 0.0
        self.gk_ctrl = True
        self.gk_ax, self.gk_ay = k.x, k.y
        self.pin_ball()
        if self.state == "match":
            self.gk_mode = False
            self.flash("¡ATAJADA! El arquero tiene el balón", 1.6)
            self.snd.play("uy", dur=1.0)
            if callable(PASE_ARQUERO):                  # pase automático: se conectará después
                self.later(PASE_DELAY_MS,
                                lambda: self.held is k and self.state == "match" and PASE_ARQUERO(self, k))

    def release_ball(self, vx, vy):
        """Suelta el balón que tiene el arquero con velocidad (vx, vy). Pensado para el pase futuro."""
        k = self.held
        if k is None:
            return
        b = self.ball
        sp = math.hypot(vx, vy) or 1.0
        gap = k.r + b.r + 2
        b.x, b.y = k.x + vx / sp * gap, k.y + vy / sp * gap
        b.vx, b.vy = vx, vy
        self.held = None
        self.gk_ctrl = False

    def draw_trail(self):
        if not self.trail:
            return
        now = vnow()
        self.trail = [g for g in self.trail if now - g[2] < TRAIL_T][-24:]
        for x, y, t, team in self.trail:
            a = 0.55 * (1 - (now - t) / TRAIL_T)
            base, _, edge = kit_for(self.teams[team], True, team)
            sx, sy = self.to_s(x, y)
            R = PR * self.s
            self.cv.create_oval(sx - R, sy - R, sx + R, sy + R, fill=base, width=0, alpha=a)

    def draw_power(self, x0, y0, x1, y1, p):
        """Barra horizontal verde -> amarillo -> rojo."""
        cv = self.cv
        cv.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2, fill="#111111", outline="#ffffff", width=2)
        n = 30
        w = (x1 - x0) / n
        for i in range(n):
            t = i / (n - 1)
            col = mix("#2ee65a", "#ffd400", t * 2) if t < 0.5 else mix("#ffd400", "#ff2a2a", (t - 0.5) * 2)
            on = (i + 0.5) / n <= p
            cv.create_rectangle(x0 + i * w, y0, x0 + (i + 1) * w + 0.6, y1, fill=col, width=0,
                                alpha=1.0 if on else 0.2)
        cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=f"DASH {int(p * 100)}%", fill="#ffffff",
                       font=self.F(0.6))

    def draw_gk_controls(self):
        """Franja inferior: botón ARQUERO, barra de potencia y flechas (fuera de la cancha)."""
        cv, u, P = self.cv, self.u, self.ctrl_pad
        top = self.ch - P
        cv.create_rectangle(0, top, self.cw, self.ch, fill="#062612", width=0)
        self.gk_btns = []
        bh = P * 0.56
        by = self.ch - bh / 2 - P * 0.08
        tw = min(self.cw * 0.2, u * 5.6)
        tx = tw / 2 + u * 0.4
        on = self.gk_mode
        held = self.held is not None
        fill = "#ffd400" if on else ("#4a4a4a" if held else "#1f6b3a")
        cv.create_rectangle(tx - tw / 2, by - bh / 2, tx + tw / 2, by + bh / 2, fill=fill,
                            outline="#ffffff", width=2)
        cv.create_text(tx, by, text="ARQUERO\nACTIVO" if on else "ARQUERO", fill="#111111" if on else "#ffffff",
                       font=self.F(0.75), justify="center", width=tw)
        self.gk_btns.append((tx - tw / 2, by - bh / 2, tx + tw / 2, by + bh / 2, "gk"))
        bw = min(self.cw * 0.24, u * 7)
        cx = max(self.cw / 2, tx + tw / 2 + u * 0.9 + bw)
        if on:
            labels = ("< IZQ", "DER >") if self.rot else ("^ IZQ", "v DER")
            for d, lab in ((-1, labels[0]), (1, labels[1])):
                x = cx + d * (bw / 2 + u * 0.3)
                act = self.gk_hold == d
                cv.create_rectangle(x - bw / 2, by - bh / 2, x + bw / 2, by + bh / 2,
                                    fill="#ffd400" if act else "#1f6b3a", outline="#ffffff", width=2)
                cv.create_text(x, by, text=lab, fill="#111111" if act else "#ffffff", font=self.F(1.3))
                self.gk_btns.append((x - bw / 2, by - bh / 2, x + bw / 2, by + bh / 2, d))
            b0 = top + P * 0.1
            self.draw_power(cx - bw - u * 0.3, b0, cx + bw + u * 0.3, b0 + P * 0.18, self.gk_charge())
        else:
            txt = ("Tu arquero tiene el balón: arrástralo para despejar" if held
                   else "Toca ARQUERO: cámara lenta + DASH lateral para atajar")
            cv.create_text((tx + tw / 2 + self.cw) / 2, by, text=txt, fill="#d9ffe6", font=self.F(0.8, False),
                           width=self.cw - tw - u * 2)

    def draw_flag(self, x, y, w, h, team):
        cv = self.cv
        kind, cols, extras = FLAGS[team]
        n = len(cols)
        for i, c in enumerate(cols):
            if kind == "h":
                cv.create_rectangle(x, y + i * h / n, x + w, y + (i + 1) * h / n + 0.5, fill=c, width=0)
            else:
                cv.create_rectangle(x + i * w / n, y, x + (i + 1) * w / n + 0.5, y + h, fill=c, width=0)
        for e in extras:
            t = e[0]
            if t == "canton":
                cv.create_rectangle(x, y, x + w * e[2], y + h * e[3], fill=e[1], width=0)
            elif t == "dot":
                r = h * e[4]
                cx, cy = x + w * e[2], y + h * e[3]
                cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=e[1], width=0)
            elif t == "cross":
                th = h * e[2]
                cv.create_rectangle(x, y + h / 2 - th / 2, x + w, y + h / 2 + th / 2, fill=e[1], width=0)
                cv.create_rectangle(x + w / 2 - th / 2, y, x + w / 2 + th / 2, y + h, fill=e[1], width=0)
            elif t == "nordic":
                th = h * e[2]
                cx = x + w * 0.37
                cv.create_rectangle(x, y + h / 2 - th / 2, x + w, y + h / 2 + th / 2, fill=e[1], width=0)
                cv.create_rectangle(cx - th / 2, y, cx + th / 2, y + h, fill=e[1], width=0)
            elif t == "swiss":
                s = h * 0.6
                a = s * 0.3
                cx, cy = x + w / 2, y + h / 2
                cv.create_rectangle(cx - s / 2, cy - a / 2, cx + s / 2, cy + a / 2, fill=e[1], width=0)
                cv.create_rectangle(cx - a / 2, cy - s / 2, cx + a / 2, cy + s / 2, fill=e[1], width=0)
            elif t == "diamond":
                cv.create_polygon([x + w * 0.5, y + h * 0.1, x + w * 0.92, y + h * 0.5,
                                   x + w * 0.5, y + h * 0.9, x + w * 0.08, y + h * 0.5], fill=e[1], width=0)
        cv.create_rectangle(x, y, x + w, y + h, fill="", outline="#ffffff", width=1)

    # ---------------- entrada (ratón / táctil)
    def on_press(self, ev):
        if self.visual.transitioning:
            return
        if self.state not in ("match", "pens"):
            for x0, y0, x1, y1, cmd in list(self.buttons):
                if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                    cmd()
                    return
            return
        px0, py0, px1, py1 = self.pause_rect()          # v9: botón de pausa (zona táctil ampliada)
        pad = self.u * 0.6
        if px0 - pad <= ev.x <= px1 + pad and py0 - pad <= ev.y <= py1 + pad:
            self.toggle_pause()
            return
        if self.paused:
            for x0, y0, x1, y1, _, _, cmd in self.pause_menu_rects():
                if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                    cmd()
                    return
            return
        if self.state == 'match' and self.ability_press(ev.x, ev.y):
            return
        if self.state == "pens":
            for x0, y0, x1, y1, d in self.pen_btns:
                if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                    if d == 0 or self.pen_k % 2 == 1:
                        self.pen_key(d)
                    else:
                        self.pen_hold = d
                        self.pen_key(d)
                    return
        wx, wy = self.to_w(ev.x, ev.y)
        self.mouse_w = (wx, wy)
        # zona táctil ampliada (no cambia el dibujo ni la física): ~2,3 veces el radio o 44 px
        reach = max(PR * 2.3, 44 / self.s)
        if self.state == "match":
            if self.phase != "play" or self.kick_team == 1:
                return
            best, bd = None, reach
            for p in self.bodies:
                if p.team == 0 and not (p.keeper and self.kick_team is not None):
                    d = math.hypot(p.x - wx, p.y - wy)
                    if d <= bd:
                        best, bd = p, d
            self.drag = best
            if best is not None and not best.keeper:
                self.fire.select(best, vnow())
            if best is not None and best.keeper:        # v8: agarrar al arquero = cámara lenta 50 %
                self.gk_mode = True
                self.gk_released_at = None
        elif self.pen_ready():
            if self.pen_k % 2 == 0:
                if math.hypot(self.ball.x - wx, self.ball.y - wy) <= max(BR * 4, 50 / self.s):
                    self.drag = self.ball

    def full_drag(self):
        """Distancia (mundo) que da 100 % de potencia: en pantallas chicas basta con
        estirar ~22 % del lado menor, así se alcanza la potencia máxima con comodidad."""
        return min(MAX_DRAG, min(self.cw, self.ch) * 0.22 / self.s)

    def drag_vec(self, p, wx, wy):
        dx, dy = wx - p.x, wy - p.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return 0, 0, 0
        pw = min(d / self.full_drag(), 1.0)
        return dx / d, dy / d, pw

    def on_motion(self, ev):
        if self.visual.transitioning: return
        if self.paused:
            return
        if self.state in ("match", "pens"):
            self.mouse_w = self.to_w(ev.x, ev.y)

    def on_release(self, ev):
        if self.visual.transitioning: return
        self.pen_hold = 0
        if self.paused:
            return
        if self.state == 'match' and self.ability_release(ev.x, ev.y):
            return
        if self.gk_hold:                                # v7: soltar la flecha = DASH
            self.gk_release()
            return
        if not self.drag:
            return
        p = self.drag
        self.drag = None
        wx, wy = self.to_w(ev.x, ev.y)
        if math.hypot(wx - p.x, wy - p.y) < 6:
            if self.state == "match" and p.keeper:
                self.gk_mode = False                    # arrastre cancelado: velocidad normal
            return
        if self.state == "match" and p.keeper:
            self.gk_released_at = vnow()      # la cámara lenta sigue hasta el bloqueo
        ux, uy, pw = self.drag_vec(p, wx, wy)
        dx, dy = ux * pw * MAX_DRAG, uy * pw * MAX_DRAG
        if self.state == "match":
            if self.phase != "play" or self.kick_team == 1:
                return
            if self.fire.selected(p):
                dx *= POWER_FACTOR; dy *= POWER_FACTOR
            if self.can_shoot(0, None, p.keeper):
                self.shoot(p, dx * POWER, dy * POWER)
            else:                                       # en recarga: se dispara al terminar
                self.pending = (p, dx * POWER, dy * POWER)
        elif self.state == "pens" and self.pen_ready():
            self.shoot(p, dx * POWER, dy * POWER)
            self.pen_wait = False
            self.keeper.vy = random.choice([-1, 1]) * random.uniform(2, 8.5)

    # ---------------- bucle
    def tick(self):
        stamp=time.perf_counter()
        now=vnow();elapsed=max(0,now-self.last_t);dt=min(.1,elapsed);self.last_t=now
        active=not self.paused and not self.visual.transitioning
        if active:
            if self.state=='match':self.match_update(dt)
            elif self.state=='pens':self.pens_update()
            elif self.state=='bracket':self.bracket_update(elapsed)
            self.music.update(dt)
        updated=time.perf_counter()
        # No redraw of frozen pause/static screens. Kivy animates opacity on its own.
        if active:
            if self.state in ('match','pens'):self.draw()
            elif self.state=='bracket' and (self.bracket_event or getattr(self,'bracket_dirty',False)):
                self.render()
                self.bracket_dirty=False
        self.visual.record(updated-stamp,time.perf_counter()-updated)
        self.root.after(16,self.tick)

    # ---------------- dibujo de partido
    def draw(self):
        cv = self.cv
        cv.delete("all")
        cv.cached(('pitch',self.cw,self.ch,self.state),self.draw_pitch)
        if self.state == 'match':
            self.draw_fire_aura()

        self.draw_trail()                               # v7: estela del DASH
        # resaltar fichas del equipo con turno
        active = self.state == "match" and self.can_shoot(0)
        ck = self.ctrl_keeper() if self.gk_ctrl else None
        for b in self.bodies:
            if b is self.ball:
                continue
            sx, sy = self.to_s(b.x, b.y)
            R = b.r * self.s
            if b is ck:
                cv.create_oval(sx - R * 1.45, sy - R * 1.45, sx + R * 1.45, sy + R * 1.45,
                               outline="#00e5ff", width=max(2, R * 0.16))
            if active and b.team == 0 and not self.fire.selected(b):
                pulse = 1.25 + 0.1 * math.sin(vnow() * 8)
                cv.create_oval(sx - R * pulse, sy - R * pulse, sx + R * pulse, sy + R * pulse,
                               outline="#fff36b", width=max(1.5, R * 0.14))
            if self.state == 'match':
                self.draw_fire_ring(b, sx, sy, R)
            self.jersey(sx, sy, R, self.teams[b.team], b.keeper, b.team, b.num)

        fx_now = vnow()
        fx_dt = max(0.0, min(.1, fx_now - getattr(self, '_fx_last', fx_now)))
        self._fx_last = fx_now
        if self.state == 'match':
            self.draw_pausa_effect(fx_dt)               # sobre las chapitas, bajo el balón
        # balón
        b = self.ball
        sx, sy = self.to_s(b.x, b.y)
        R0 = b.r * self.s
        lift_scale = self.fire_ball_scale(fx_dt) if self.state == 'match' else 1.0
        R = R0 * lift_scale                             # solo dibujo: radio físico intacto
        lift = (lift_scale - 1.0) * R0 * 2.2
        shadow = R0 * (1 + .25 * (lift_scale - 1))
        cv.create_oval(sx - shadow + 2 + lift * .35, sy - shadow + 3 + lift * .2, sx + shadow + 2 + lift * .35,
                       sy + shadow + 3 + lift * .2, fill="#062b14", width=0, alpha=1 - .45 * (lift_scale - 1))
        sy -= lift
        cv.create_oval(sx - R, sy - R, sx + R, sy + R, fill="#ffffff", outline="#111111", width=max(1, R * 0.12))
        rot = (b.x + b.y) * 0.08
        for k in range(5):
            a = rot + k * math.tau / 5
            px, py = sx + math.cos(a) * R * 0.55, sy + math.sin(a) * R * 0.55
            cv.create_oval(px - R * 0.2, py - R * 0.2, px + R * 0.2, py + R * 0.2, fill="#111111", width=0)
        cv.create_oval(sx - R * 0.25, sy - R * 0.25, sx + R * 0.25, sy + R * 0.25, fill="#111111", width=0)

        # guía de arrastre
        if self.drag:
            p = self.drag
            ux, uy, pw = self.drag_vec(p, *self.mouse_w)
            L = max(pw, 0.05) * MAX_DRAG
            ex, ey = p.x + ux * L, p.y + uy * L
            col = "#3cff6e" if pw < 0.5 else ("#ffd400" if pw < 0.85 else "#ff3b3b")
            self.line_w(p.x, p.y, ex, ey, fill=col, width=max(2, 5 * self.s), arrow="last",
                        arrowshape=(16 * self.s + 6, 20 * self.s + 7, 7 * self.s + 3))
            px, py = self.to_s(p.x, p.y)
            maximum = 150 if self.state == 'match' and self.fire.selected(p) else 100
            cv.create_text(px, py - (p.r + 22) * self.s - 6, text=f"{int(pw * maximum)}%", fill=col,
                           font=self.F(0.9))

        if self.state == "pens":
            self.draw_pens_overlay()
        self.draw_hud()
        if self.state == 'match':
            self.draw_abilities()
        self.draw_pause_button()

        cd = self.countdown()[0] if self.state == "pens" and self.pen_wait and not self.lock else None
        if cd:                                          # instrucción central sincronizada con el HUD
            fx, fy = self.to_s(FX1 - 200, MY)
            role = "Apunta y tira" if self.pen_k % 2 == 0 else "Prepárate para atajar"
            f = self.F(3.0 if len(cd) == 1 else 2.0)
            cv.create_text(fx + 3, fy + 3, text=cd, fill="#000000", font=f)
            cv.create_text(fx, fy, text=cd, fill="#ffd400", font=f)
            cv.create_text(fx, fy + self.u * 2.4, text=role, fill="#ffffff", font=self.F(1.0))
        elif self.msg and vnow() < self.msg_until:
            fx, fy = self.to_s((FX0 + FX1) / 2, MY)
            f = self.F(1.8)
            cv.create_text(fx + 3, fy + 3, text=self.msg, fill="#000000", font=f, width=self.cw * 0.9,
                           justify="center")
            cv.create_text(fx, fy, text=self.msg, fill="#ffd400", font=f, width=self.cw * 0.9,
                           justify="center")
        self.visual.draw_goal()
        if self.paused:
            self.draw_pause_overlay()

    def draw_pitch(self):
        cv=self.cv
        gy0, gy1, depth = (PEN_GY0, PEN_GY1, PEN_GD) if self.state == "pens" else (GY0, GY1, GD)
        cv.create_rectangle(0, 0, self.cw, self.ch, fill="#08401f", width=0)
        stripe = (FX1 - FX0) / 10
        for i in range(10):
            self.rect_w(FX0 + i * stripe, FY0, FX0 + (i + 1) * stripe, FY1,
                        fill="#2fae4f" if i % 2 else "#3cc45e", width=0)
        lw = max(1.5, 3 * self.s)
        L = dict(fill="", outline="#ffffff", width=lw)
        self.rect_w(FX0, FY0, FX1, FY1, **L)
        cx = (FX0 + FX1) / 2
        self.line_w(cx, FY0, cx, FY1, fill="#ffffff", width=lw)
        self.circle_w(cx, MY, 80, **L)
        self.circle_w(cx, MY, 4, fill="#ffffff", width=0)
        for side in (-1, 1):
            line = FX0 if side < 0 else FX1
            self.rect_w(line, MY - 150, line - side * 150, MY + 150, **L)
            self.rect_w(line, MY - 70, line - side * 55, MY + 70, **L)
            self.circle_w(line - side * 105, MY, 3, fill="#ffffff", width=0)
            back = line + side * depth
            self.rect_w(line, gy0, back, gy1, fill="#e8e8e8", outline="#ffffff", width=lw)
            for k in range(1, 7):                                   # red
                yy = gy0 + k * (gy1-gy0) / 7
                self.line_w(line, yy, back, yy, fill="#9a9a9a", width=1)
            for k in range(1, 4):
                xx = line + side * depth * k / 4
                self.line_w(xx, gy0, xx, gy1, fill="#9a9a9a", width=1)
            self.circle_w(line, gy0, 4, fill="#ffffff", width=0)
            self.circle_w(line, gy1, 4, fill="#ffffff", width=0)


    def draw_pens_overlay(self):
        cv, u = self.cv, self.u
        top = self.oy + (PEN_WX1 - PEN_X0) * self.s
        cv.create_rectangle(0, top, self.cw, self.ch, fill="#062612", width=0)
        self.pen_btns = []
        user_kicks = self.pen_k % 2 == 0
        ready = self.pen_ready()
        if user_kicks and self.pen_wait and not self.drag:   # mira de dirección
            ex = FX1 + 8
            col = "#3cff6e" if ready else "#888888"
            self.line_w(self.ball.x, self.ball.y, ex, self.aim_y, fill=col, width=max(2, 4 * self.s),
                        dash=(6, 4), arrow="last")
            self.circle_w(ex, self.aim_y, 9, outline=col, width=max(2, 3 * self.s), fill="")
        if (not user_kicks and self.pen_wait and self.ai_target is not None
                and vnow() >= self.ai_kick_at - 0.8):   # mira del lanzador CPU
            self.circle_w(FX1 + 8, self.ai_target, 10, outline="#ff3b3b", width=max(2, 3 * self.s), fill="")
        hint_y = top + u * 0.9
        if self.mobile or not user_kicks:
            bh = min(u * 4.0, (self.ch - top) - u * 3.2)
            bw = min(self.cw * 0.28, u * 7)
            by = self.ch - bh / 2 - u * 0.4
            gx = self.to_s(FX1, MY)[0]                 # centrado bajo la portería
            gx = min(max(gx, bw * 1.6), self.cw - bw * 1.6)
            if user_kicks:
                items = [(gx - bw * 1.1, "< IZQ", -1), (gx, "TIRAR", 0), (gx + bw * 1.1, "DER >", 1)]
            else:
                items = [(gx - bw * 0.6, "< IZQ", -1), (gx + bw * 0.6, "DER >", 1)]
            ok = self.gk_allowed()
            for x, txt, d in items:
                w = bw if d else bw * 0.95
                if user_kicks:
                    fill = ("#ffd400" if d == 0 else "#1f6b3a") if ready else "#3a3a3a"
                else:
                    fill = ("#ffd400" if self.gk_hold == d else "#1f6b3a") if ok else "#3a3a3a"
                cv.create_rectangle(x - w / 2, by - bh / 2, x + w / 2, by + bh / 2, fill=fill,
                                    outline="#ffffff", width=2)
                cv.create_text(x, by, text=txt, fill="#111111" if fill == "#ffd400" else "#ffffff",
                               font=self.F(1.8 if d else 1.1))
                self.pen_btns.append((x - w / 2, by - bh / 2, x + w / 2, by + bh / 2, d))
            hint_y = by - bh / 2 - u * 0.6
            if not user_kicks:                          # barra de potencia sobre las flechas
                b0 = by - bh / 2 - u * 1.5
                self.draw_power(gx - bw * 1.1, b0, gx + bw * 1.1, b0 + u * 0.9, self.gk_charge())
                hint_y = b0 - u * 0.6
            if user_kicks:
                hint = "Flechas: apuntar · TIRAR o arrastra el balón"
            elif self.mobile:
                hint = "Mantén una flecha para cargar y suelta: DASH"
            else:
                hint = "Mantén A/D, flechas o los botones y suelta: DASH"
        else:
            hint = ("A/D o flechas: apuntar · ESPACIO o arrastra el balón: tirar" if user_kicks
                    else "A/D o flechas (o clic en la portería): lánzate")
        cv.create_text(self.cw / 2, hint_y, text=hint, fill="#d9ffe6", font=self.F(0.8, False),
                       width=self.cw * 0.95)

    def draw_hud(self):
        cv, cw, u, hud = self.cv, self.cw, self.u, self.hud
        cv.create_rectangle(0, 0, cw, hud, fill="#062612", width=0)
        a, b = self.teams
        row1 = hud * 0.36
        R = u * 0.85
        if self.state == "match":
            sa, sb = self.score
        else:
            sa, sb = sum(self.pens[0]), sum(self.pens[1])
        cv.create_text(cw / 2, row1, text=f"{sa} - {sb}", fill="#ffffff", font=self.F(1.6))
        off = u * 3.2
        cv.create_text(cw / 2 - off, row1, text=ABBR[a], fill="#ffffff", font=self.F(1.2), anchor="e")
        cv.create_text(cw / 2 + off, row1, text=ABBR[b], fill="#ffffff", font=self.F(1.2), anchor="w")
        self.jersey(cw / 2 - off - u * 3.6, row1, R, a)
        self.jersey(cw / 2 + off + u * 3.6, row1, R, b)
        row2 = hud * 0.75
        if self.state == "match":
            now = vnow()
            if self.phase == "goal":
                who, frac, col = "¡GOL!", 0, "#ffd400"
            elif self.kick_team is not None:
                who = "SACAS TÚ" if self.kick_team == 0 else f"Saca {ABBR[b]}"
                frac, col = 1.0, "#ffd400"
            elif now < self.next_shot_at[0]:
                left = self.next_shot_at[0] - now
                who = f"Tu recarga {left:.1f}s"
                frac, col = 1 - left / COOLDOWN, "#ff9f3c"
            else:
                who, frac, col = "¡TIRA!", 1.0, "#3cff6e"
            info = f"{self.period}  ·  {self.clock_text()}  ·  {who}"
            if self.gk_mode:
                info += "  ·  CÁMARA LENTA"
            cv.create_rectangle(0, hud - u * 0.35, cw * frac, hud, fill=col, width=0)
        else:
            k = self.pen_k
            pa = " ".join("o" if g else "x" for g in self.pens[0]) or "-"
            pb = " ".join("o" if g else "x" for g in self.pens[1]) or "-"
            role = "TÚ TIRAS" if k % 2 == 0 else "TÚ ATAJAS"
            info = f"PENALES  {pa}  |  {pb}  ·  {role}"
            col = "#ffd400"
            cd = self.countdown()[0] if self.pen_wait and not self.lock else None
            if cd:                                       # contador junto al marcador
                bx = cw / 2 + u * 9.5
                rr = u * 1.15
                cv.create_oval(bx - rr * (2.6 if len(cd) > 1 else 1), row1 - rr,
                               bx + rr * (2.6 if len(cd) > 1 else 1), row1 + rr,
                               fill="#ffd400", outline="#ffffff", width=2)
                cv.create_text(bx, row1, text=cd, fill="#111111", font=self.F(1.2 if len(cd) == 1 else 0.7))
        cv.create_text(cw / 2, row2, text=info, fill=col, font=self.F(0.85), width=cw * 0.98)


class MundialApp(_App):
    title = "Mundialito"

    def build(self):
        root = tk.Tk()
        self.game = Game(root)
        return root.widget


if __name__ == "__main__":
    MundialApp().run()
