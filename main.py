#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COPA MUNDIAL DE CHAPAS  v6 APK  -  Python 3 + Kivy (empaquetable como APK con Buildozer)
Funciona en PC y en Android (Pydroid 3). Se adapta a cualquier pantalla:
en vertical la cancha se gira para aprovechar el espacio.

Controles: toca/haz clic sobre una de tus fichas, arrastra hacia donde quieras
tirar (más lejos = más potencia) y suelta.
v4 - JUEGO LIBRE: no hay turnos. Cualquier equipo puede tirar en cualquier momento,
con recarga INDEPENDIENTE de 1 s por equipo (sin congelar el balón ni la física).
Solo el saque inicial es exclusivo del equipo que saca.
Tiempo a escala: 90 min = 3 min reales (cada tiempo 1:30), prórroga 20 min = 40 s.
Penales: cuenta 3-2-1-¡PREPÁRATE!; apunta con A/D o flechas (PC) o con los
botones táctiles bajo la portería (celular).
v3: celebraciones sonoras propias de cada selección, zona táctil ampliada
y dorsales aleatorios (el arquero siempre lleva el 1).
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
FRICTION = 0.985
SUB = 4
MAX_DRAG = 160
POWER = 0.14
# Tiempo a escala (regla de tres): 90 min de fútbol = 180 s reales -> 1 min = 2 s reales
REAL_PER_MIN = 180.0 / 90.0
HALF_REAL = 45 * REAL_PER_MIN                    # 90 s
ET_REAL = 20 * REAL_PER_MIN                      # 40 s
MARKS = [HALF_REAL, 2 * HALF_REAL, 2 * HALF_REAL + ET_REAL]   # 90 s, 180 s, 220 s
COOLDOWN = 1.0                                   # recarga propia de cada equipo (s)
CD_STEP = 0.8                                    # duración de cada número del conteo de penales
PEN_X0 = FX1 - 330                               # zona visible en penales

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
}
ABBR = {"España": "ESP", "Francia": "FRA", "Alemania": "ALE", "Inglaterra": "ING", "Italia": "ITA",
        "Portugal": "POR", "Países Bajos": "PBA", "Bélgica": "BEL", "Croacia": "CRO",
        "Argentina": "ARG", "Brasil": "BRA", "Uruguay": "URU", "Colombia": "COL",
        "México": "MEX", "Estados Unidos": "USA", "Chile": "CHI"}

# ------------------------------------------------------------------ SONIDO (sintetizado aquí mismo)
# Todos los sonidos se generan matemáticamente al ejecutar el juego: son 100 % originales,
# sin archivos externos ni derechos de autor. Melodías inventadas para este juego.
import os
import sys
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
                _Color(*f)
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
                _Color(*f)
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
                _Color(*f)
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
            if len(self.TEX) > 600:
                self.TEX.clear()
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


class tk:                                   # espacio de nombres compatible con "tk."
    TclError = _TclError
    Tk = _Root

    @staticmethod
    def Canvas(root, **kw):
        w = _CanvasWidget(root)
        root.widget = w
        return w


SR = 16000                                           # muestras por segundo (ligero para móviles)
SND_DIR = os.path.join(os.environ.get("ANDROID_PRIVATE") or tempfile.gettempdir(), "mundial_chapas_snd_v3")

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
}


def _buf(sec):
    return [0.0] * int(SR * sec)


def _tone(buf, t0, dur, f, inst, vol):
    harm, vib, att = HARM[inst]
    i0, n = int(t0 * SR), int(dur * SR)
    rel = min(0.08, dur * 0.4)
    pluck = inst == "guitar"
    ph = 0.0
    for i in range(n):
        j = i0 + i
        if j >= len(buf):
            break
        t = i / SR
        env = min(1.0, t / att) if att else 1.0
        if pluck:
            env *= math.exp(-t * 6)
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
            "gol": 4, "gana": 4, "derrota": 4, "campeon": 5}

    def __init__(self):
        self.on = True
        self.files = {}
        self.busy_until, self.busy_prio = 0.0, -1
        self.players = []
        self.backend = self._detect()
        try:
            os.makedirs(SND_DIR, exist_ok=True)
        except OSError:
            self.backend = None
        if self.backend:
            self._bg(lambda: self.files.update({("", k): v for k, v in gen_common().items()}))

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
        if not self.backend:
            return
        for t in teams:
            if ("", t) not in self.files:
                self.files[("", t)] = True
                self._bg(lambda t=t: self.files.update({(t, k): v for k, v in gen_team(t).items()}))

    def play(self, name, team="", dur=1.0):
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
                if prio >= 3:
                    for s in self.cache.values():
                        if s and s.state == "play":
                            s.stop()
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
def walls(b, is_ball):
    if b.y - b.r < FY0 and not (is_ball and (b.x < FX0 or b.x > FX1)):
        b.y = FY0 + b.r; b.vy = -b.vy * 0.8
    if b.y + b.r > FY1 and not (is_ball and (b.x < FX0 or b.x > FX1)):
        b.y = FY1 - b.r; b.vy = -b.vy * 0.8
    in_goal = is_ball and GY0 < b.y < GY1
    for side in (-1, 1):
        line = FX0 if side < 0 else FX1
        past = (b.x - b.r < line) if side < 0 else (b.x + b.r > line)
        if not past:
            continue
        if in_goal:
            back = line - GD if side < 0 else line + GD
            if side < 0 and b.x - b.r < back:
                b.x = back + b.r; b.vx = -b.vx * 0.3
            if side > 0 and b.x + b.r > back:
                b.x = back - b.r; b.vx = -b.vx * 0.3
            if (side < 0 and b.x < line) or (side > 0 and b.x > line):
                if b.y - b.r < GY0: b.y = GY0 + b.r; b.vy = -b.vy * 0.5
                if b.y + b.r > GY1: b.y = GY1 - b.r; b.vy = -b.vy * 0.5
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


def step(bodies, ball):
    for _ in range(SUB):
        for b in bodies:
            b.x += b.vx / SUB; b.y += b.vy / SUB
            walls(b, b is ball)
        for i in range(len(bodies)):
            for k in range(i + 1, len(bodies)):
                collide(bodies[i], bodies[k])
    for b in bodies:
        b.vx *= FRICTION; b.vy *= FRICTION
        if b.speed() < 0.06:
            b.vx = b.vy = 0.0


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
    return [(p, c) for p, c in shapes if len(p) >= 3]


KIT_CACHE = {}


def kit_for(team, keeper=False, side=0):
    key = (team, keeper, side)
    if key not in KIT_CACHE:
        pat, c1, c2, edge, _, extra = TEAMS[team]
        if keeper:
            base = "#b6ff00" if side == 0 else "#ff4fd8"
            if abs(lum(base) - lum(c1)) < 20:
                base = "#00e5ff"
            KIT_CACHE[key] = (base, [(band(0, 1, -0.12, 0.12), edge)], edge)
        else:
            KIT_CACHE[key] = (c1, kit_shapes(pat, c1, c2, extra), edge)
    return KIT_CACHE[key]


# ------------------------------------------------------------------ juego
class Game:
    def __init__(self, root):
        self.root = root
        root.title("Copa Mundial de Chapas")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.mobile = ("ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ
                       or min(sw, sh) < 900)
        self.pen_btns = []
        self.pen_hold = 0
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
        self.last_t = time.monotonic()
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
            self.pen_pad = self.u * 6.2 if self.mobile else self.u * 2.6
            hh = h - self.pen_pad
            span = min(RH, 2 * 230)                    # ancho visible: área grande y algo más
            self.s = min(w / span, hh / (WX1 - PEN_X0))
            self.ox = w / 2 - (MY - WY0) * self.s      # portería centrada
            self.oy = self.hud + (hh - (WX1 - PEN_X0) * self.s) / 2
            return
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
            return self.ox + (y - WY0) * self.s, self.oy + (WX1 - x) * self.s
        return self.ox + (x - WX0) * self.s, self.oy + (y - WY0) * self.s

    def to_w(self, sx, sy):
        if self.rot:
            return WX1 - (sy - self.oy) / self.s, WY0 + (sx - self.ox) / self.s
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

    def go(self, state):
        if state != self.state and "pens" in (state, self.state):
            self.state = state
            self.recalc()
        self.state = state
        self.render()

    def button(self, cx, cy, w, h, text, cmd, bg="#ffd400", fg="#111111", font=None, team=None):
        cv = self.cv
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        sh = max(2, h * 0.08)
        cv.create_rectangle(x0 + sh, y0 + sh, x1 + sh, y1 + sh, fill="#04301a", width=0)
        cv.create_rectangle(x0, y0, x1, y1, fill=bg, outline="#ffffff", width=max(1, int(h * 0.05)))
        tx = cx
        if team:
            r = h * 0.3
            jx = x0 + h * 0.5
            self.jersey(jx, cy, r, team)
            tx = (jx + r + x1) / 2
        cv.create_text(tx, cy, text=text, fill=fg, font=font or self.F(1.0), justify="center",
                       width=max(10, (x1 - tx) * 2 - 8))
        self.buttons.append((x0, y0, x1, y1, cmd))

    def jersey(self, sx, sy, R, team, keeper=False, side=0, num=None):
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
        """Fondo decorativo con franjas para los menús."""
        n = 12
        for i in range(n):
            self.cv.create_rectangle(0, i * self.ch / n, self.cw, (i + 1) * self.ch / n,
                                     fill="#0c6b31" if i % 2 else "#0a5a2a", width=0)

    def title(self, y, text, size=2.2, col="#ffd400"):
        self.cv.create_text(self.cw / 2 + 2, y + 2, text=text, fill="#000000", font=self.F(size),
                            width=self.cw * 0.95, justify="center")
        self.cv.create_text(self.cw / 2, y, text=text, fill=col, font=self.F(size),
                            width=self.cw * 0.95, justify="center")

    # ---------------- menú
    def draw_menu(self):
        cw, ch, u = self.cw, self.ch, self.u
        self.pitch_bg()
        self.title(u * 2.2, "COPA MUNDIAL DE CHAPAS", 2.1)
        self.cv.create_text(cw / 2, u * 4.4, text="Elige tu selección", fill="#ffffff", font=self.F(1.2))
        cols = 2 if cw < ch else 4
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
            fs = min(1.05, bh / u * 0.32, bw / u / max(8, len(n) + 4) * 1.7)
            self.button(x, y, bw, bh, f"{n}\n{rating(n)}", lambda n=n: self.start_tournament(n),
                        bg="#123d24", fg="#ffffff", font=self.F(fs), team=n)
        self.button(cw / 2, ch - u * 3.5, min(cw * 0.6, u * 11), u * 1.6,
                    "Sonido: SÍ" if self.snd.on else "Sonido: NO", self.toggle_sound,
                    bg="#ffd400" if self.snd.on else "#555555", fg="#111111" if self.snd.on else "#ffffff",
                    font=self.F(0.85))
        self.cv.create_text(cw / 2, ch - u * 1.6, fill="#d9ffe6", font=self.F(0.8, False),
                            justify="center", width=cw * 0.94,
                            text="Arrastra desde tu ficha hacia donde quieras tirar: más estiras, más potencia.\n"
                                 "Juego libre: ambos equipos tiran cuando quieran, cada uno con su propia recarga de 1 s.")

    def toggle_sound(self):
        self.snd.on = not self.snd.on
        self.render()

    # ---------------- torneo
    def start_tournament(self, team):
        self.user = team
        self.snd.prepare(team)                         # se genera en segundo plano
        self.round_teams = list(TEAMS)
        random.shuffle(self.round_teams)
        self.round = 0
        self.results = []
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

    def draw_bracket(self):
        cw, ch, u = self.cw, self.ch, self.u
        self.pitch_bg()
        self.title(u * 2, ROUND_NAMES[self.round], 2.2)
        lines = []
        for r, res in enumerate(self.results):
            lines.append((ROUND_NAMES[r], "#9fffd0", True))
            lines += [(l, "#ffffff", False) for l in res]
        lines.append(("Partidos de esta ronda", "#9fffd0", True))
        for a, b in self.pairs():
            lines.append((f"{a}  vs  {b}", "#ffd400" if self.user in (a, b) else "#ffffff", True))
        top, bottom = u * 4, ch - u * 4.5
        lh = min(u * 1.5, (bottom - top) / max(1, len(lines)))
        y = top + lh / 2
        for text, col, bold in lines:
            self.cv.create_text(cw / 2, y, text=text, fill=col, width=cw * 0.95,
                                font=("Helvetica", -max(7, int(lh * 0.72)), "bold" if bold else "normal"))
            y += lh
        opp = next(b if a == self.user else a for a, b in self.pairs() if self.user in (a, b))
        self.button(cw / 2, ch - u * 2.3, min(cw * 0.8, u * 16), u * 2.8, "JUGAR PARTIDO",
                    lambda: self.start_match(opp), font=self.F(1.3))

    def finish_user_match(self, winner, text):
        res, winners = [], []
        for a, b in self.pairs():
            if self.user in (a, b):
                res.append("* " + text); winners.append(winner)
            else:
                w, t = self.sim_match(a, b)
                res.append(t); winners.append(w)
        self.results.append(res)
        if winner != self.user:
            return self.end_screen(f"Eliminado en {ROUND_NAMES[self.round]}", "#ff6b6b")
        if self.round == 3:
            self.snd.play("campeon", self.user, 9)
            return self.end_screen(f"¡{self.user} CAMPEÓN DEL MUNDO!", "#ffd400")
        self.round += 1
        self.round_teams = winners
        self.go("bracket")

    def end_screen(self, msg, col):
        self.end_msg, self.end_col = msg, col
        self.go("end")

    def draw_end(self):
        cw, ch, u = self.cw, self.ch, self.u
        self.pitch_bg()
        self.jersey(cw / 2, ch * 0.18, u * 2.5, self.user, num=10)
        self.title(ch * 0.33, self.end_msg, 2.0, self.end_col)
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
    def start_match(self, opp):
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

    def reset_positions(self):
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

    def clock_text(self):
        """Tiempo de juego a escala: cada segundo real = 30 s de fútbol."""
        gs = int(self.clock * 60 / REAL_PER_MIN)
        return f"{gs // 60:02d}:{gs % 60:02d}"

    def can_shoot(self, team, now=None):
        now = time.monotonic() if now is None else now
        if self.phase != "play":
            return False
        if self.kick_team is not None:                 # saque inicial: solo el que saca
            return team == self.kick_team
        return now >= self.next_shot_at[team]          # recarga propia de ESE equipo

    def flash(self, text, secs=1.5):
        self.msg, self.msg_until = text, time.monotonic() + secs

    def kickoff(self, team):
        """Solo `team` puede hacer el primer tiro; luego el juego es libre."""
        now = time.monotonic()
        self.phase = "play"
        self.kick_team = team
        self.next_shot_at = [now, now]                 # un temporizador por equipo
        self.pending = None
        self.ai_at = now + random.uniform(0.7, 1.2)

    def ai_delay(self):
        # reacción de la CPU tras terminar la recarga (mejor rating = más rápida)
        r = rating(self.teams[1])
        return random.uniform(0.25, 0.75) * (1.6 - r / 100)

    def shoot(self, body, vx, vy):
        sp = math.hypot(vx, vy)
        cap = MAX_DRAG * POWER
        if sp > cap:
            vx, vy = vx / sp * cap, vy / sp * cap
        body.vx, body.vy = vx, vy
        if self.state == "match":
            now = time.monotonic()
            self.shots += 1
            self.shooter = body.team
            self.kick_team = None                       # desde aquí, juego libre
            t = body.team
            # solo se recarga el equipo que tiró; el rival NO se toca
            self.next_shot_at[t] = now + COOLDOWN
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
        m = MARKS[self.mark]
        self.clock = m
        self.mark += 1
        tie = self.score[0] == self.score[1]
        if m == MARKS[0]:
            self.period = "2do tiempo"; self.flash("Descanso - ¡Segundo tiempo!", 2)
            self.snd.play("pito_medio")
            self.reset_positions(); self.kickoff(1)
        elif m == MARKS[1]:
            if not tie:
                self.snd.play("pito_final", dur=1.8)
                self.match_over(); return True
            self.period = "PRÓRROGA"; self.flash("¡Empate! Vamos a la prórroga", 2)
            self.snd.play("pito_medio")
            self.reset_positions(); self.kickoff(0)
        else:
            self.snd.play("pito_final", dur=1.8)
            if tie:
                self.start_penalties()
            else:
                self.match_over()
        return True

    def ai_shoot(self):
        b = self.ball
        t = 22
        k = (1 - FRICTION ** t) / (1 - FRICTION)          # predicción de posición del balón
        bx = min(max(b.x + b.vx * k, FX0 + 20), FX1 - 20)
        by = min(max(b.y + b.vy * k, FY0 + 20), FY1 - 20)
        gx, gy = FX0 - 10, MY + random.uniform(-40, 40)
        dx, dy = gx - bx, gy - by
        d = math.hypot(dx, dy) or 1
        ux, uy = dx / d, dy / d
        ax, ay = bx - ux * (PR + BR - 3), by - uy * (PR + BR - 3)
        best, bscore = None, 1e9
        for p in self.bodies:
            if p.team != 1:
                continue
            dist = math.hypot(ax - p.x, ay - p.y)
            ahead = (p.x - bx) * ux + (p.y - by) * uy
            score = dist + (600 if ahead > 0 else 0) + (250 if p.keeper else 0)
            if score < bscore:
                best, bscore = p, score
        px, py = ax - best.x, ay - best.y
        dist = math.hypot(px, py) or 1
        noise = (100 - rating(self.teams[1])) * 0.006
        ang = math.atan2(py, px) + random.gauss(0, noise)
        sp = min((dist + 240) * (1 - FRICTION), MAX_DRAG * POWER)
        self.shoot(best, math.cos(ang) * sp, math.sin(ang) * sp)

    def check_goal(self):
        b = self.ball
        if b.x + b.r < FX0:
            return 1
        if b.x - b.r > FX1:
            return 0
        return None

    def match_update(self, dt):
        now = time.monotonic()
        if self.phase == "goal":
            step(self.bodies, self.ball)
            if now >= self.resume_at:
                self.reset_positions()
                if not self.check_period():
                    self.kickoff(1 - self.scorer)
            return
        self.clock += dt                                # cronómetro automático
        if self.check_period():
            return
        step(self.bodies, self.ball)
        g = self.check_goal()
        if g is not None:
            self.score[g] += 1
            self.scorer = g
            self.flash(f"¡¡GOOOOL de {self.teams[g]}!!", 2.0)
            self.snd.play("gol", self.teams[g], 2.6)
            self.phase = "goal"
            self.resume_at = now + 2.2
            self.drag = None
            return
        # tiro del jugador soltado durante la recarga: sale apenas termina
        if self.pending and self.can_shoot(0, now):
            p, vx, vy = self.pending
            self.pending = None
            self.shoot(p, vx, vy)
        if self.can_shoot(1, now) and now >= self.ai_at:
            self.ai_shoot()

    def match_over(self, pen_text=""):
        a, b = self.teams
        if pen_text:
            w = pen_text.split("gana ")[-1]
        else:
            w = a if self.score[0] > self.score[1] else b
        self.post_txt = f"{a} {self.score[0]}-{self.score[1]} {b}" + (f" ({pen_text})" if pen_text else "")
        self.post_w = w
        self.go("post")
        if not pen_text:                               # tras el pitazo, festeja el ganador
            self.root.after(1500, lambda: self.state == "post" and self.snd.play("gana", w, 4))

    def draw_post(self):
        cw, ch, u = self.cw, self.ch, self.u
        self.pitch_bg()
        self.title(ch * 0.25, "FINAL DEL PARTIDO", 2.0)
        a, b = self.teams
        self.jersey(cw * 0.3, ch * 0.42, u * 2, a, num=10)
        self.jersey(cw * 0.7, ch * 0.42, u * 2, b, num=10)
        self.cv.create_text(cw / 2, ch * 0.42, text=f"{self.score[0]} - {self.score[1]}", fill="#ffffff",
                            font=self.F(2.2))
        self.cv.create_text(cw / 2, ch * 0.56, text=self.post_txt, fill="#ffffff", font=self.F(1.1),
                            width=cw * 0.92, justify="center")
        self.button(cw / 2, ch * 0.72, min(cw * 0.7, u * 14), u * 2.8, "Continuar",
                    lambda: self.finish_user_match(self.post_w, self.post_txt), font=self.F(1.3))

    # ---------------- penales
    def start_penalties(self):
        self.pens = [[], []]
        self.pen_k = 0
        self.state = "pens"
        self.recalc()
        self.setup_kick()
        self.go("pens")
        self.buttons = []
        self.flash("¡TANDA DE PENALES!", 2)

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
        self.cd_start = time.monotonic() + (2.0 if self.pen_k == 0 else 0.0)
        self.ai_kick_at = None

    def countdown(self, now=None):
        """Devuelve (texto, listo). 3 -> 2 -> 1 -> ¡PREPÁRATE! (desde aquí se puede tirar)."""
        now = time.monotonic() if now is None else now
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
        """d=-1 izquierda, 1 derecha, 0 tirar. Izquierda/derecha según el que mira a la portería."""
        if self.state != "pens" or not self.pen_ready():
            return
        if self.pen_k % 2 == 0:
            if d == 0:
                self.pen_kick()
            else:
                self.move_aim(d * 14)
        elif d != 0 and not self.dived:
            self.user_dive(MY + d * GOAL_H * 0.45)

    def move_aim(self, dy):
        self.aim_y = min(max(self.aim_y + dy, GY0 - 25), GY1 + 25)
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

    def pen_result(self, goal):
        self.moving = False
        self.pens[self.pen_k % 2].append(goal)
        self.flash("¡GOL!" if goal else "¡FALLÓ / ATAJADA!", 1.3)
        if goal:
            self.snd.play("penal", self.teams[self.pen_k % 2], 1.2)
        else:
            self.snd.play("uy", dur=1.2)
        self.pen_k += 1
        self.lock = True
        self.root.after(1500, self.next_kick)

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
        ty = random.uniform(GY0 + 8, GY1 - 8) + random.gauss(0, 18)
        dx, dy = FX1 + 30 - self.ball.x, ty - self.ball.y
        d = math.hypot(dx, dy)
        sp = random.uniform(13, 17)
        self.ball.vx, self.ball.vy = dx / d * sp, dy / d * sp
        self.moving = True; self.frames = 0; self.pen_wait = False

    def pens_update(self):
        if self.pen_wait and not self.lock and self.countdown()[1]:
            if self.pen_hold and self.pen_k % 2 == 0:
                self.move_aim(self.pen_hold * 3)
            if self.pen_k % 2 == 1:                     # si no te lanzas en 2,5 s, la CPU tira igual
                if self.ai_kick_at is None:
                    self.ai_kick_at = time.monotonic() + 2.5
                elif time.monotonic() >= self.ai_kick_at:
                    self.dived = True
                    self.ai_penalty(MY)
                    self.keeper.vy = 0
        if not self.moving:
            return
        step(self.bodies, self.ball)
        self.frames += 1
        b = self.ball
        if b.x - b.r > FX1 and GY0 < b.y < GY1:
            self.pen_result(True)
        elif b.speed() == 0 or self.frames > 300 or (b.vx < -0.5 and b.x < FX1 - 160):
            self.pen_result(False)

    # ---------------- entrada (ratón / táctil)
    def on_press(self, ev):
        if self.state not in ("match", "pens"):
            for x0, y0, x1, y1, cmd in list(self.buttons):
                if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                    cmd()
                    return
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
                if p.team == 0:
                    d = math.hypot(p.x - wx, p.y - wy)
                    if d <= bd:
                        best, bd = p, d
            self.drag = best
        elif self.pen_ready():
            if self.pen_k % 2 == 0:
                if math.hypot(self.ball.x - wx, self.ball.y - wy) <= max(BR * 4, 50 / self.s):
                    self.drag = self.ball
            elif not self.dived:
                self.user_dive(wy)

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
        if self.state in ("match", "pens"):
            self.mouse_w = self.to_w(ev.x, ev.y)

    def on_release(self, ev):
        self.pen_hold = 0
        if not self.drag:
            return
        p = self.drag
        self.drag = None
        wx, wy = self.to_w(ev.x, ev.y)
        if math.hypot(wx - p.x, wy - p.y) < 6:
            return
        ux, uy, pw = self.drag_vec(p, wx, wy)
        dx, dy = ux * pw * MAX_DRAG, uy * pw * MAX_DRAG
        if self.state == "match":
            if self.phase != "play" or self.kick_team == 1:
                return
            if self.can_shoot(0):
                self.shoot(p, dx * POWER, dy * POWER)
            else:                                       # en recarga: se dispara al terminar
                self.pending = (p, dx * POWER, dy * POWER)
        elif self.state == "pens" and self.pen_ready():
            self.shoot(p, dx * POWER, dy * POWER)
            self.pen_wait = False
            self.keeper.vy = random.choice([-1, 1]) * random.uniform(2, 8.5)

    # ---------------- bucle
    def tick(self):
        now = time.monotonic()
        dt = min(0.1, now - self.last_t)
        self.last_t = now
        if self.state == "match":
            self.match_update(dt)
        elif self.state == "pens":
            self.pens_update()
        if self.state in ("match", "pens"):
            self.draw()
        self.root.after(16, self.tick)

    # ---------------- dibujo de partido
    def draw(self):
        cv = self.cv
        cv.delete("all")
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
            back = line + side * GD
            self.rect_w(line, GY0, back, GY1, fill="#e8e8e8", outline="#ffffff", width=lw)
            for k in range(1, 7):                                   # red
                yy = GY0 + k * GOAL_H / 7
                self.line_w(line, yy, back, yy, fill="#9a9a9a", width=1)
            for k in range(1, 4):
                xx = line + side * GD * k / 4
                self.line_w(xx, GY0, xx, GY1, fill="#9a9a9a", width=1)
            self.circle_w(line, GY0, 4, fill="#ffffff", width=0)
            self.circle_w(line, GY1, 4, fill="#ffffff", width=0)

        # resaltar fichas del equipo con turno
        active = self.state == "match" and self.can_shoot(0)
        for b in self.bodies:
            if b is self.ball:
                continue
            sx, sy = self.to_s(b.x, b.y)
            R = b.r * self.s
            if active and b.team == 0:
                pulse = 1.25 + 0.1 * math.sin(time.monotonic() * 8)
                cv.create_oval(sx - R * pulse, sy - R * pulse, sx + R * pulse, sy + R * pulse,
                               outline="#fff36b", width=max(1.5, R * 0.14))
            self.jersey(sx, sy, R, self.teams[b.team], b.keeper, b.team, b.num)

        # balón
        b = self.ball
        sx, sy = self.to_s(b.x, b.y)
        R = b.r * self.s
        cv.create_oval(sx - R + 2, sy - R + 3, sx + R + 2, sy + R + 3, fill="#062b14", width=0)
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
            cv.create_text(px, py - (p.r + 22) * self.s - 6, text=f"{int(pw * 100)}%", fill=col,
                           font=self.F(0.9))

        if self.state == "pens":
            self.draw_pens_overlay()
        self.draw_hud()

        cd = self.countdown()[0] if self.state == "pens" and self.pen_wait and not self.lock else None
        if cd:                                          # instrucción central sincronizada con el HUD
            fx, fy = self.to_s(FX1 - 200, MY)
            role = "Apunta y tira" if self.pen_k % 2 == 0 else "Prepárate para atajar"
            f = self.F(3.0 if len(cd) == 1 else 2.0)
            cv.create_text(fx + 3, fy + 3, text=cd, fill="#000000", font=f)
            cv.create_text(fx, fy, text=cd, fill="#ffd400", font=f)
            cv.create_text(fx, fy + self.u * 2.4, text=role, fill="#ffffff", font=self.F(1.0))
        elif self.msg and time.monotonic() < self.msg_until:
            fx, fy = self.to_s((FX0 + FX1) / 2, MY)
            f = self.F(1.8)
            cv.create_text(fx + 3, fy + 3, text=self.msg, fill="#000000", font=f, width=self.cw * 0.9,
                           justify="center")
            cv.create_text(fx, fy, text=self.msg, fill="#ffd400", font=f, width=self.cw * 0.9,
                           justify="center")

    def draw_pens_overlay(self):
        cv, u = self.cv, self.u
        top = self.oy + (WX1 - PEN_X0) * self.s
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
        hint_y = top + u * 0.9
        if self.mobile:
            bh = min(u * 4.4, (self.ch - top) - u * 1.6)
            bw = min(self.cw * 0.28, u * 7)
            by = self.ch - bh / 2 - u * 0.4
            gx = self.to_s(FX1, MY)[0]                 # centrado bajo la portería
            gx = min(max(gx, bw * 1.6), self.cw - bw * 1.6)
            items = [(gx - bw * 1.1, "< IZQ", -1), (gx + bw * 1.1, "DER >", 1)]
            if user_kicks:
                items.insert(1, (gx, "TIRAR", 0))
            for x, txt, d in items:
                w = bw if d else bw * 0.95
                fill = ("#ffd400" if d == 0 else "#1f6b3a") if ready else "#3a3a3a"
                cv.create_rectangle(x - w / 2, by - bh / 2, x + w / 2, by + bh / 2, fill=fill,
                                    outline="#ffffff", width=2)
                cv.create_text(x, by, text=txt, fill="#111111" if d == 0 and ready else "#ffffff",
                               font=self.F(1.8 if d else 1.1))
                self.pen_btns.append((x - w / 2, by - bh / 2, x + w / 2, by + bh / 2, d))
            hint_y = by - bh / 2 - u * 0.6
            hint = "Flechas: apuntar · TIRAR o arrastra el balón" if user_kicks else "Flechas: lánzate a un lado"
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
            now = time.monotonic()
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
    title = "Copa Mundial de Chapas"

    def build(self):
        root = tk.Tk()
        self.game = Game(root)
        return root.widget


if __name__ == "__main__":
    MundialApp().run()
