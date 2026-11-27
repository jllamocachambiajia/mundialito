"""Modo EN LÍNEA de Mundialito de Chapas (Kivy puro, se superpone al juego existente).

Pantallas: acceso, vestuario (lobby), búsqueda de rival, partido en vivo, resultado y podio.
El partido solo DIBUJA lo que manda el servidor autoritario e interpola entre estados:
los clientes nunca calculan física, solo envían intenciones (tiro y habilidades).

v2 (estilo original):
- Flecha de tiro igual que sin conexión: nace en la chapita, la sigue mientras se mueve,
  apunta hacia el dedo y respeta el mismo límite de estiramiento (MAX_DRAG / full_drag).
- Camisetas, banderas y abreviaturas originales de main.py (kit_for / FLAGS / ABBR).
- Habilidades con sus PNG originales (fuego.png, pausa.png, campo.png) sin deformarse,
  anillo de recarga y efectos reales en la cancha: llamas, partículas de PAUSA, campo
  magnético con puntos orbitando y chispas del arquero electrocutado.
- Marcador estilo TV con nombres que nunca chocan con los goles; recarga dentro del marcador.
- Horizontal: habilidades en columna a la derecha y cancha más grande. Vertical: abajo.
"""
import math
import os
import random
import threading
import time

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel, LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Mesh, Rectangle, RoundedRectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput

from network_client import NetError, NetworkClient, load_server_url

HERE = os.path.dirname(os.path.abspath(__file__))
FX0, FY0, FX1, FY1 = 60, 80, 1040, 680          # mismas medidas que el servidor / main.py
MY = (FY0 + FY1) / 2
GOAL_H, GD, PR, BR, MAX_DRAG = 140, 40, 18, 10, 160
GY0, GY1 = MY - GOAL_H / 2, MY + GOAL_H / 2
WX0, WX1, WY0, WY1 = FX0 - GD - 10, FX1 + GD + 10, FY0 - 12, FY1 + 12
HALF_REAL = 150.0                                 # 45' = 2:30 reales (igual que el servidor)
MAG_RADIUS = 2.0                                  # RADIUS_FACTOR de campo_magnetico.py
TOTAL_CD = {"fire": 20.0, "pausa": 60.0, "magnet": 30.0}

C = {"night": "#041f15", "deep": "#052d20", "grass": "#2fae4f", "grass2": "#3cc45e", "lime": "#b5f65a",
     "orange": "#ff761b", "gold": "#ffd52a", "chalk": "#f4f7ef", "ink": "#0b261b", "red": "#ff3b30",
     "sky": "#5ec8ff", "violet": "#b98cff", "hud": "#062612", "cyan": "#35eaff", "pink": "#ff65b5"}
FALLBACK_TEAMS = ["Argentina", "Brasil", "España", "Francia", "Alemania", "Inglaterra", "Italia", "Portugal",
                  "Países Bajos", "Bélgica", "Croacia", "Uruguay", "Colombia", "México", "Estados Unidos",
                  "Chile", "Suecia", "Dinamarca", "Suiza", "Polonia", "Hungría", "Paraguay", "Perú", "Ecuador"]


def rgba(hx, a=1.0):
    hx = hx.lstrip("#")
    return (int(hx[0:2], 16) / 255, int(hx[2:4], 16) / 255, int(hx[4:6], 16) / 255, a)


def _font(name, file):
    path = os.path.join(HERE, "assets", "fonts", file)
    if os.path.exists(path):
        try:
            LabelBase.register(name=name, fn_regular=path)
            return name
        except Exception:
            pass
    return "Roboto"


TITLE = _font("TekoOnline", "Teko-Bold.ttf")
BODY = _font("OswaldOnline", "Oswald.ttf")


# ---------------------------------------------------------------- recursos del juego original
def _main():
    try:
        import main
        return main
    except Exception:
        return None


def team_list():
    m = _main()
    if m is not None and getattr(m, "TEAMS", None):
        return list(m.TEAMS.keys())
    return list(FALLBACK_TEAMS)


def kit(team, keeper=False, side=0):
    """(color base, [(polígono unidad, color)], borde) -> mismo diseño que el modo offline."""
    m = _main()
    if m is not None and team in getattr(m, "TEAMS", {}):
        try:
            return m.kit_for(team, keeper, side)
        except Exception:
            pass
    return ("#b6ff00" if keeper else "#ffffff", [], "#111111")


def abbr(team):
    m = _main()
    try:
        return m.ABBR[team]
    except Exception:
        return (team or "???")[:3].upper()


def flag_def(team):
    m = _main()
    try:
        return m.FLAGS[team]
    except Exception:
        return None


def lum(hx):
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _asset(*parts):
    return os.path.join(HERE, "assets", *parts)


def _sound(name):
    try:
        from kivy.core.audio import SoundLoader
        for sub in ("effects", ""):
            p = _asset("sounds", sub, name) if sub else _asset("sounds", name)
            if os.path.exists(p):
                return SoundLoader.load(p)
    except Exception:
        pass
    return None


_TEX = {}


def texture(name):
    """Textura PNG cacheada (None si falta el archivo: se dibuja un respaldo)."""
    if name not in _TEX:
        tex = None
        try:
            from kivy.core.image import Image as CoreImage
            p = _asset("images", name)
            if os.path.exists(p):
                tex = CoreImage(p).texture
        except Exception:
            tex = None
        _TEX[name] = tex
    return _TEX[name]


def contain(tex_w, tex_h, box_w, box_h):
    """Tamaño que cabe en la caja SIN deformar (modo contain)."""
    if tex_w <= 0 or tex_h <= 0:
        return box_w, box_h
    k = min(box_w / tex_w, box_h / tex_h)
    return tex_w * k, tex_h * k


def aim_vector(dx, dy, full):
    """Igual que drag_vec() offline: dirección unitaria y potencia 0..1 (límite de estiramiento)."""
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return 0.0, 0.0, 0.0
    return dx / d, dy / d, min(d / full, 1.0)


# ====================================================================== botones / textos
class Btn:
    def __init__(self, rect, text, action, color, fg=C["ink"], enabled=True):
        self.rect, self.text, self.action, self.color, self.fg, self.enabled = rect, text, action, color, fg, enabled

    def hit(self, x, y):
        bx, by, bw, bh = self.rect
        return self.enabled and bx <= x <= bx + bw and by <= y <= by + bh


class OnlineScreen(FloatLayout):
    """Se agrega sobre la ventana; on_exit() se llama al volver al menú principal."""

    def __init__(self, on_exit=None, data_dir=None, **kw):
        super().__init__(**kw)
        self.on_exit = on_exit
        self.net = NetworkClient(load_server_url(data_dir))
        self.state = "login"
        self.msg = ""
        self.busy = False
        self.buttons = []
        self.teams = team_list()
        self.team_i = self.teams.index("Argentina") if "Argentina" in self.teams else 0
        self.mode = "amistoso"
        self.match = None
        self.prev = self.cur = None
        self.cur_at = 0.0
        self.drag = None
        self.result = None
        self.podium = []
        self.toasts = []
        self.banner = None
        self.goal_flash = 0.0
        self.goal_team = None
        self.particles = []
        self.ball_scale = 1.0
        self.fire_started = 0.0
        self.stun_started = [0.0, 0.0]
        self._tex_cache = {}
        self._last_draw = time.time()
        self.sounds = {k: _sound(f) for k, f in (("fire", "fuego.wav"), ("pausa", "pausa_inicio.wav"),
                                                   ("magnet", "campo.wav"), ("goal", "avanzar_nivel.wav"),
                                                   ("lose", "perder.wav"), ("load", "carga.wav"),
                                                   ("stun", "electrocucion.wav"), ("kick", "toque.wav"),
                                                   ("whistle", "pito_medio.wav"), ("end", "pito_final.wav"),
                                                   ("start", "pito.wav"))}
        self.user_in = self._input("usuario", False)
        self.pass_in = self._input("contraseña", True)
        self.bind(size=lambda *_: self.redraw(), pos=lambda *_: self.redraw())
        self._ev = Clock.schedule_interval(self._tick, 1 / 60)
        self.redraw()

    # ------------------------------------------------------------ utilidades UI
    def _input(self, hint, secret):
        return TextInput(hint_text=hint, password=secret, multiline=False, font_name=BODY,
                         size_hint=(None, None), write_tab=False, padding=(14, 12),
                         background_color=rgba("#f4f7ef"), foreground_color=rgba(C["ink"]),
                         cursor_color=rgba(C["orange"]))

    @property
    def u(self):
        return max(8.0, min(self.width / 30.0, self.height / 22.0))

    def _label(self, s, size, color, font):
        key = (s, int(size), color, font)
        tex = self._tex_cache.get(key)
        if tex is None:
            lab = CoreLabel(text=s, font_name=font, font_size=max(6, int(size)), color=rgba(color))
            lab.refresh()
            tex = lab.texture
            if len(self._tex_cache) > 600:
                self._tex_cache.clear()
            self._tex_cache[key] = tex
        return tex

    def measure(self, s, size, font=None):
        return self._label(s, size, C["chalk"], font or BODY).size

    def fit(self, s, size, max_w, font=None, min_ratio=.8):
        """Reduce la letra y, si aún no cabe, recorta con '…' para que nunca choque."""
        font = font or BODY
        if max_w <= 0:
            return "", size
        sz = size
        while self.measure(s, sz, font)[0] > max_w and sz > size * min_ratio:
            sz *= .92
        if self.measure(s, sz, font)[0] <= max_w:
            return s, sz
        while len(s) > 1 and self.measure(s + "…", sz, font)[0] > max_w:
            s = s[:-1]
        return s.rstrip() + "…", sz

    def text(self, x, y, s, size, color=C["chalk"], font=None, anchor="center", shadow=True, max_w=None):
        font = font or BODY
        if max_w:
            s, size = self.fit(s, size, max_w, font)
        if not s:
            return 0
        tex = self._label(s, size, color, font)
        w, h = tex.size
        px = x - w / 2 if anchor == "center" else (x if anchor == "left" else x - w)
        py = y - h / 2
        if shadow:
            Color(*rgba(C["night"], .85))
            Rectangle(texture=tex, pos=(px + 2, py - 2), size=(w, h))
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(px, py), size=(w, h))
        return w

    def button(self, cx, cy, w, h, label, action, color=C["gold"], fg=C["ink"], enabled=True):
        x, y = cx - w / 2, cy - h / 2
        Color(*rgba(C["night"], .6))
        RoundedRectangle(pos=(x + 3, y - 4), size=(w, h), radius=[h / 2])
        Color(*rgba(color if enabled else "#55635a"))
        RoundedRectangle(pos=(x, y), size=(w, h), radius=[h / 2])
        Color(1, 1, 1, .18)
        RoundedRectangle(pos=(x + 6, y + h * .52), size=(max(1, w - 12), h * .38), radius=[h / 3])
        self.text(cx, cy, label, h * .5, fg if enabled else "#c9d2cc", TITLE, shadow=False, max_w=w - h * .6)
        self.buttons.append(Btn((x, y, w, h), label, action, color, fg, enabled))

    def poly(self, pts, col, a=1.0):
        """Polígono convexo relleno (abanico de triángulos)."""
        if len(pts) < 3:
            return
        verts = []
        for x, y in pts:
            verts += [x, y, 0, 0]
        Color(*rgba(col, a))
        Mesh(vertices=verts, indices=list(range(len(pts))), mode="triangle_fan")

    def image(self, name, cx, cy, box_w, box_h, alpha=1.0):
        """Dibuja un PNG centrado SIN deformar. Devuelve False si falta el archivo."""
        tex = texture(name)
        if tex is None:
            return False
        w, h = contain(tex.width, tex.height, box_w, box_h)
        Color(1, 1, 1, alpha)
        Rectangle(texture=tex, pos=(cx - w / 2, cy - h / 2), size=(w, h))
        return True

    def pitch_bg(self):
        """Fondo de estadio: tribunas oscuras, césped a franjas, cal y focos."""
        w, h = self.width, self.height
        Color(*rgba(C["deep"]))
        Rectangle(pos=self.pos, size=self.size)
        n = 12
        for i in range(n):
            Color(*rgba(C["grass"] if i % 2 else C["grass2"], .32))
            Rectangle(pos=(self.x + i * w / n, self.y), size=(w / n + 1, h))
        Color(*rgba(C["chalk"], .16))
        Line(circle=(self.center_x, self.center_y, min(w, h) * .22), width=2)
        Line(points=[self.center_x, self.y, self.center_x, self.top], width=2)
        for fx in (.08, .92):
            Color(1, 1, 1, .06)
            Ellipse(pos=(self.x + w * fx - w * .25, self.top - h * .35), size=(w * .5, h * .6))
        Color(*rgba(C["night"], .6))
        Rectangle(pos=self.pos, size=(w, h * .1))
        Rectangle(pos=(self.x, self.top - h * .08), size=(w, h * .08))

    def header(self, title, sub=None, col=C["lime"]):
        self.text(self.center_x, self.top - self.height * .1, title, self.u * 2.6, col, TITLE,
                  max_w=self.width * .92)
        if sub:
            self.text(self.center_x, self.top - self.height * .1 - self.u * 2.1, sub, self.u * .85, C["chalk"],
                      max_w=self.width * .9)

    def toast(self, s, col=C["gold"]):
        self.toasts.append([s, col, time.time()])

    # ------------------------------------------------------------ dibujos reutilizables
    def jersey(self, x, y, r, team, keeper=False, side=0, num=None, alpha=1.0):
        """Chapita con la camiseta ORIGINAL (kit_for de main.py)."""
        base, shapes, edge = kit(team, keeper, side)
        Color(*rgba("#062b14", .55 * alpha))
        Ellipse(pos=(x - r + r * .15, y - r - r * .25), size=(2 * r, 2 * r))          # sombra
        Color(*rgba(base, alpha))
        Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
        for pts, col in shapes:                                                         # y del dibujo offline va hacia abajo
            self.poly([(x + px * r, y - py * r) for px, py in pts], col, alpha)
        Color(*rgba(edge, alpha))
        Line(ellipse=(x - r * .45, y + r * .1, r * .9, r * .85, 20, 160), width=max(1, r * .06))  # cuello
        Line(circle=(x, y, r - max(.75, r * .08)), width=max(1.2, r * .08))
        Color(1, 1, 1, .55 * alpha)
        Line(circle=(x, y, r * .8, 280, 350), width=max(1, r * .05))                    # brillo
        if num is not None and r >= 7:
            fg = ("#111111" if lum(base) > 150 else "#ffffff")
            self.text(x, y - r * .2, str(num), r * .95, fg, TITLE, shadow=True)

    def flag(self, x, y, w, h, team):
        """Bandera original (FLAGS de main.py); x,y = esquina inferior izquierda."""
        fd = flag_def(team)
        if fd is None:
            base, _, edge = kit(team)
            Color(*rgba(base)); Rectangle(pos=(x, y), size=(w, h))
            Color(*rgba(edge)); Rectangle(pos=(x, y), size=(w, h * .3))
        else:
            kind, cols, extras = fd
            n = len(cols)
            for i, c in enumerate(cols):
                Color(*rgba(c))
                if kind == "h":
                    Rectangle(pos=(x, y + h - (i + 1) * h / n), size=(w, h / n + .5))
                else:
                    Rectangle(pos=(x + i * w / n, y), size=(w / n + .5, h))
            for e in extras:
                t = e[0]
                Color(*rgba(e[1]))
                if t == "canton":
                    Rectangle(pos=(x, y + h - h * e[3]), size=(w * e[2], h * e[3]))
                elif t == "dot":
                    rr = h * e[4]
                    Ellipse(pos=(x + w * e[2] - rr, y + h - h * e[3] - rr), size=(2 * rr, 2 * rr))
                elif t == "cross":
                    th = h * e[2]
                    Rectangle(pos=(x, y + h / 2 - th / 2), size=(w, th))
                    Rectangle(pos=(x + w / 2 - th / 2, y), size=(th, h))
                elif t == "nordic":
                    th = h * e[2]
                    Rectangle(pos=(x, y + h / 2 - th / 2), size=(w, th))
                    Rectangle(pos=(x + w * .37 - th / 2, y), size=(th, h))
                elif t == "swiss":
                    s, a = h * .6, h * .18
                    Rectangle(pos=(x + w / 2 - s / 2, y + h / 2 - a / 2), size=(s, a))
                    Rectangle(pos=(x + w / 2 - a / 2, y + h / 2 - s / 2), size=(a, s))
                elif t == "diamond":
                    self.poly([(x + w * .5, y + h * .9), (x + w * .92, y + h * .5),
                               (x + w * .5, y + h * .1), (x + w * .08, y + h * .5)], e[1])
        Color(1, 1, 1, .9)
        Line(rectangle=(x, y, w, h), width=1)

    def ball_icon(self, x, y, r, spin):
        Color(*rgba("#062b14", .5)); Ellipse(pos=(x - r + 2, y - r - 3), size=(2 * r, 2 * r))
        Color(1, 1, 1, 1); Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
        Color(*rgba("#111111"))
        for k in range(5):
            a = spin + k * math.tau / 5
            px, py = x + math.cos(a) * r * .55, y + math.sin(a) * r * .55
            Ellipse(pos=(px - r * .2, py - r * .2), size=(r * .4, r * .4))
        Ellipse(pos=(x - r * .25, y - r * .25), size=(r * .5, r * .5))
        Line(circle=(x, y, r), width=max(1, r * .1))

    def spinner(self, x, y, u):
        t = time.time()
        for i in range(8):
            a = t * 4 + i * math.tau / 8
            Color(*rgba(C["lime"], (i + 1) / 8))
            Ellipse(pos=(x + math.cos(a) * u - 3, y + math.sin(a) * u - 3), size=(6, 6))

    def draw_toasts(self):
        now = time.time()
        self.toasts = [t for t in self.toasts if now - t[2] < 2.4]
        base = self.layout()["pitch"][1] + self.u * 1.6 if self.state == "match" else self.y + self.u * 5.6
        for i, (s, col, at) in enumerate(self.toasts[-3:]):
            y = base + i * self.u * 1.7
            w = self.measure(s, self.u * .95, TITLE)[0]
            w = min(w, self.width * .86)
            Color(*rgba(C["night"], .72))
            RoundedRectangle(pos=(self.center_x - w / 2 - self.u * .7, y - self.u * .7),
                             size=(w + self.u * 1.4, self.u * 1.4), radius=[self.u * .7])
            self.text(self.center_x, y, s, self.u * .95, col, TITLE, shadow=False, max_w=self.width * .86)

    # ------------------------------------------------------------ pantallas
    def redraw(self):
        self.canvas.before.clear()
        self.buttons = []
        for t in (self.user_in, self.pass_in):
            if t.parent is not None and self.state != "login":
                self.remove_widget(t)
        with self.canvas.before:
            getattr(self, "draw_" + self.state)()
            self.draw_toasts()

    def draw_login(self):
        self.pitch_bg()
        u, w, h = self.u, self.width, self.height
        top = self.top - h * .12
        self.text(self.center_x, top, "MUNDIAL", u * 3.4, C["lime"], TITLE, max_w=w * .9)
        self.text(self.center_x, top - u * 2.9, "EN LÍNEA", u * 2.4, C["orange"], TITLE, max_w=w * .9)
        bw, bh = min(w * .78, 420), max(40, min(58, h * .07))
        first = min(self.y + h * .58, top - u * 5.2 - bh)
        self.text(self.center_x, first + bh * 1.35, "Usuario: 3-16 letras, números o _", max(12, u * .75), C["chalk"],
                  max_w=bw)
        for i, t in enumerate((self.user_in, self.pass_in)):
            t.size = (bw, bh)
            t.font_size = bh * .38
            t.pos = (self.center_x - bw / 2, first - i * bh * 1.25)
            if t.parent is None:
                self.add_widget(t)
        y = first - bh * 2.3
        self.button(self.center_x, y, bw, bh, "ENTRAR", lambda: self.auth(False), enabled=not self.busy)
        self.button(self.center_x, y - bh * 1.25, bw, bh, "CREAR CUENTA", lambda: self.auth(True), C["orange"],
                    enabled=not self.busy)
        self.button(self.center_x, y - bh * 2.45, bw * .6, bh * .8, "VOLVER", self.exit, "#e6c98e")
        if self.msg:
            self.text(self.center_x, y - bh * 3.4, self.msg, u * .8, "#ffb3a8", max_w=w * .9)
        if self.busy:
            self.spinner(self.center_x, y - bh * 3.4, u)

    def draw_lobby(self):
        self.pitch_bg()
        a = self.net.account or {}
        u, w, h = self.u, self.width, self.height
        self.header("VESTUARIO", f"Hola, {a.get('usuario', '')}")
        wide = w > h * 1.25                       # horizontal: datos a la izquierda, botones a la derecha
        top = self.top - h * .1 - u * 3.4         # bajo el título
        colw = w * .46 if wide else w
        lx = self.x + w * .26 if wide else self.center_x
        cw, ch = min(colw * .9, 520), max(u * 3.4, 52)
        cy = top - ch / 2
        Color(*rgba(C["night"], .8))
        RoundedRectangle(pos=(lx - cw / 2, cy - ch / 2), size=(cw, ch), radius=[18])
        Color(*rgba(C["lime"], .9))
        Line(rounded_rectangle=(lx - cw / 2, cy - ch / 2, cw, ch, 18), width=1.6)
        stats = [("ELO", a.get("elo", 1000), C["gold"]), ("VICTORIAS", a.get("victorias", 0), C["lime"]),
                 ("DERROTAS", a.get("derrotas", 0), "#ff8a7a"),
                 ("% VICT.", f"{a.get('porcentaje_victoria', 0):.0f}", C["sky"])]
        for i, (k, v, col) in enumerate(stats):
            x = lx - cw / 2 + cw * (i + .5) / 4
            self.text(x, cy + ch * .16, str(v), ch * .4, col, TITLE, max_w=cw / 4 - 8)
            self.text(x, cy - ch * .27, k, max(10, ch * .2), C["chalk"], max_w=cw / 4 - 6)
        team = self.teams[self.team_i]
        r = max(u * 1.4, 22)
        name_h = max(14, u * 1.1)
        sel_top = cy - ch / 2 - u * .8
        bottom_btns = self.y + h * .05
        if wide:
            ty = (sel_top + bottom_btns) / 2 + name_h
        else:
            ty = sel_top - r * 1.35
        Color(*rgba(C["gold"], .35 + .15 * math.sin(time.time() * 4)))
        Line(circle=(lx, ty, r * 1.3), width=2)
        self.jersey(lx, ty, r, team, num=10)
        fw = r * 1.1
        self.flag(lx - fw / 2, ty - r * 1.3 - fw * .66, fw, fw * .66, team)
        name_y = ty - r * 1.3 - fw * .66 - name_h * .8
        self.text(lx, name_y, team.upper(), name_h, C["chalk"], TITLE, max_w=min(colw * .8, u * 12))
        bs = max(40, r * 1.4)
        self.button(lx - r * 3.4, ty, bs, bs, "<", lambda: self.pick(-1), C["lime"])
        self.button(lx + r * 3.4, ty, bs, bs, ">", lambda: self.pick(1), C["lime"])
        if wide:
            rx = self.x + w * .74
            bw = min(w * .42, 420)
            avail = top - bottom_btns
            bh = max(38, min(60, avail / 4.6))
            y = top - bh / 2
        else:
            rx = self.center_x
            bw = min(w * .84, 420)
            avail = name_y - name_h - bottom_btns
            bh = max(38, min(60, avail / 4.2))
            y = name_y - name_h * .9 - bh / 2
        self.button(rx, y, bw, bh, "AMISTOSO ALEATORIO", lambda: self.search("amistoso"))
        self.button(rx, y - bh * 1.22, bw, bh, "RANKED", lambda: self.search("ranked"), C["orange"])
        self.button(rx - bw * .26, y - bh * 2.44, bw * .48, bh * .85, "PODIO MUNDIAL", self.open_podium, "#e6c98e")
        self.button(rx + bw * .26, y - bh * 2.44, bw * .48, bh * .85, "SALIR", self.exit, "#9fb7a8")

    def draw_search(self):
        self.pitch_bg()
        u = self.u
        self.header("BUSCANDO RIVAL", "RANKED · por nivel ELO" if self.mode == "ranked" else "AMISTOSO ALEATORIO",
                    C["orange"] if self.mode == "ranked" else C["lime"])
        t = time.time()
        cx, cy = self.center_x, self.center_y
        for i in range(12):
            a = t * 2.5 + i * math.tau / 12
            Color(*rgba(C["lime"], .15 + .7 * (i / 12)))
            Ellipse(pos=(cx + math.cos(a) * u * 4 - u * .3, cy + math.sin(a) * u * 4 - u * .3), size=(u * .6, u * .6))
        self.jersey(cx - u * 1.2, cy, u * 1.1, self.teams[self.team_i], num=10)
        self.ball_icon(cx + u * 1.3, cy + math.sin(t * 5) * u * .5, u * .7, t * 3)
        self.text(cx, cy - u * 6, f"{int(t - self.search_at)} s", u * 1.2, C["chalk"], TITLE)
        self.button(cx, self.y + self.height * .15, min(self.width * .6, 300), max(44, u * 2.4), "CANCELAR",
                    self.cancel_search, "#e6c98e")

    def draw_podium(self):
        self.pitch_bg()
        u, w, h = self.u, self.width, self.height
        self.header("PODIO MUNDIAL", "Ranking ELO de todos los jugadores", C["gold"])
        base = self.y + h * .44
        spots = [(0, 0, u * 6, C["gold"]), (1, -1, u * 4.4, "#d9dde3"), (2, 1, u * 3.2, "#d08a4a")]
        floor = base - u * 2
        col_w = min(u * 6.2, w / 3.2)
        for idx, side, ph, col in spots:
            x = self.center_x + side * col_w
            Color(*rgba(col))
            Rectangle(pos=(x - col_w * .45, floor), size=(col_w * .9, ph))
            self.text(x, floor + ph - u * 1.2, str(idx + 1), u * 2, C["ink"], TITLE, shadow=False)
            if idx < len(self.podium):
                p = self.podium[idx]
                Color(*rgba(col, .8)); Line(circle=(x, floor + ph + u * 1.6, u * 1.45), width=2)
                self.ball_icon(x, floor + ph + u * 1.6, u * 1.1, idx)
                self.text(x, floor + ph + u * 3.5, p["usuario"], max(13, u * .9), C["chalk"], TITLE, max_w=col_w * .98)
                self.text(x, floor + ph + u * 4.6, str(p["elo"]), u * .75, col)
        y = floor - u * 1.6
        rw = min(w * .84, 520)
        for p in self.podium[3:10]:
            if y < self.y + h * .17:
                break
            Color(*rgba(C["night"], .7))
            RoundedRectangle(pos=(self.center_x - rw / 2, y - u * .75), size=(rw, u * 1.5), radius=[10])
            right = f"{p['elo']}  ·  {p['porcentaje_victoria']:.0f}%"
            rwid = self.measure(right, u * .8)[0]
            self.text(self.center_x - rw / 2 + u * .8, y, f"{p['puesto']}.  {p['usuario']}", u * .8, C["chalk"],
                      anchor="left", shadow=False, max_w=rw - rwid - u * 2.4)
            self.text(self.center_x + rw / 2 - u * .8, y, right, u * .8, C["gold"], anchor="right", shadow=False)
            y -= u * 1.75
        self.button(self.center_x, self.y + h * .07, min(w * .6, 300), max(42, u * 2.2), "VOLVER",
                    lambda: self.set_state("lobby"), "#e6c98e")

    def draw_result(self):
        self.pitch_bg()
        r = self.result or {}
        u, w = self.u, self.width
        m = self.match or {"side": 0, "teams": [None, None], "names": ["", ""]}
        side = m["side"]
        win = r.get("winner")
        title, col = ("¡VICTORIA!", C["lime"]) if win == side else ("EMPATE", C["gold"]) if win is None else \
            ("DERROTA", "#ff8a7a")
        self.text(self.center_x, self.top - self.height * .2, title, u * 3.6, col, TITLE, max_w=w * .9)
        sc = r.get("score", [0, 0])
        cy = self.center_y + u * 2
        self.text(self.center_x, cy, f"{sc[side]}  -  {sc[1 - side]}", u * 3, C["chalk"], TITLE)
        for k, sd in ((-1, side), (1, 1 - side)):
            x = self.center_x + k * min(w * .3, u * 7)
            self.jersey(x, cy + u * .3, u * 1.3, m["teams"][sd], side=sd)
            self.text(x, cy - u * 1.9, (m["names"][sd] or "").upper(), max(13, u * .95), C["chalk"], TITLE,
                      max_w=min(w * .3, u * 8))
        d = r.get("elo_change", 0)
        if m.get("mode") == "ranked":
            self.text(self.center_x, self.center_y - u * 1.4, f"ELO {'+' if d >= 0 else ''}{d}", u * 1.4,
                      C["lime"] if d >= 0 else "#ff8a7a", TITLE)
        bw, bh = min(w * .7, 360), max(46, u * 2.5)
        self.button(self.center_x, self.y + self.height * .28, bw, bh, "JUGAR OTRA",
                    lambda: self.search(m.get("mode", "amistoso")))
        self.button(self.center_x, self.y + self.height * .28 - bh * 1.25, bw, bh, "VESTUARIO",
                    lambda: self.set_state("lobby"), "#e6c98e")

    # ------------------------------------------------------------ distribución del partido
    def layout(self):
        """Zonas del partido. Horizontal: marcador arriba + columna de habilidades a la derecha.
        Vertical: marcador arriba + fila de habilidades abajo. La cancha nunca se deforma."""
        u, w, h = self.u, self.width, self.height
        hud_h = max(46.0, min(u * 3.0, h * .13))
        land = w >= h
        if land:
            col_w = max(64.0, min(w * .13, h * .2))
            pitch = (self.x, self.y, w - col_w, h - hud_h)
            size = min(col_w * .78, (h - hud_h) / 3.6)
            cx = self.x + w - col_w / 2
            mid = self.y + (h - hud_h) / 2
            slots = [(cx, mid + (1 - i) * size * 1.18, size) for i in range(3)]
        else:
            bar_h = max(70.0, min(h * .13, w * .24))
            pitch = (self.x, self.y + bar_h, w, h - hud_h - bar_h)
            size = min(bar_h * .78, w / 4.6)
            slots = [(self.center_x + (i - 1) * size * 1.35, self.y + bar_h / 2, size) for i in range(3)]
        return {"land": land, "hud": (self.x, self.top - hud_h, w, hud_h), "pitch": pitch, "slots": slots}

    def view(self):
        """Proyección mundo -> pantalla; en vertical la cancha se gira 90° como en el juego."""
        px, py, pw, ph = self.layout()["pitch"]
        rot = ph > pw
        rw, rh = (WY1 - WY0, WX1 - WX0) if rot else (WX1 - WX0, WY1 - WY0)
        s = min(pw / rw, ph / rh) * .97
        ox = px + (pw - rw * s) / 2
        oy = py + (ph - rh * s) / 2
        return rot, s, ox, oy

    def _flip(self):
        return bool(self.match and self.match.get("side") == 1)

    def w2s(self, x, y, v=None):
        rot, s, ox, oy = v or self.view()
        if self._flip():
            x = FX0 + FX1 - x                                   # mi equipo siempre ataca hacia la derecha / arriba
        if rot:
            return ox + (y - WY0) * s, oy + (x - WX0) * s
        return ox + (x - WX0) * s, oy + (WY1 - y) * s

    def s2w(self, sx, sy, v=None):
        """Inversa exacta de w2s (pantalla -> mundo)."""
        rot, s, ox, oy = v or self.view()
        if rot:
            y, x = WY0 + (sx - ox) / s, WX0 + (sy - oy) / s
        else:
            x, y = WX0 + (sx - ox) / s, WY1 - (sy - oy) / s
        if self._flip():
            x = FX0 + FX1 - x
        return x, y

    def full_drag(self):
        """Igual que el offline: 100 % de potencia al estirar ~22 % del lado menor (máx. MAX_DRAG)."""
        px, py, pw, ph = self.layout()["pitch"]
        _, s, _, _ = self.view()
        return min(MAX_DRAG, min(pw, ph) * .22 / s)

    def positions(self):
        if self.cur is None:
            return None, None
        if self.prev is None:
            return self.cur["bodies"], self.cur["ball"]
        k = min(1.0, (time.time() - self.cur_at) * 30)
        lerp = lambda a, b: [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]
        return [lerp(a, b) for a, b in zip(self.prev["bodies"], self.cur["bodies"])], \
            lerp(self.prev["ball"], self.cur["ball"])

    def aim(self, bodies=None):
        """Flecha actual: (origen mundo, ux, uy, potencia). Sigue SIEMPRE a la chapita."""
        if not self.drag:
            return None
        if bodies is None:
            bodies, _ = self.positions()
        if not bodies:
            return None
        bx, by = bodies[self.drag["i"]]
        wx, wy = self.s2w(*self.drag["cur"])
        ux, uy, pw = aim_vector(wx - bx, wy - by, self.full_drag())
        return bx, by, ux, uy, pw

    def can_shoot(self):
        st, m = self.cur, self.match
        if not st or not m:
            return False
        me = m["side"]
        if st.get("kick_lock") and st.get("kickoff") != me:
            return False
        fx = st.get("fx", {})
        if fx.get("pausa") is not None and fx.get("pausa") != me:
            return False
        return st["cd"]["shot"][me] <= 0

    # ------------------------------------------------------------ partido
    def draw_match(self):
        now = time.time()
        dt = max(0.0, min(.1, now - self._last_draw))
        self._last_draw = now
        Color(*rgba("#08401f"))
        Rectangle(pos=self.pos, size=self.size)
        st = self.cur
        v = self.view()
        rot, s, _, _ = v
        fx = st["fx"] if st else {}
        me = self.match["side"]
        self.draw_pitch(v)
        if fx.get("fire") is not None:                                 # aura roja de FUEGO (offline: 15 %)
            self.quad(FX0, FY0, FX1, FY1, "#ff261c", .15, v)
        bodies, ball = self.positions()
        if bodies:
            active = self.can_shoot()
            pulse = 1.25 + .1 * math.sin(now * 8)
            armed = fx.get("fire_armed", [False, False])
            fire_body = fx.get("fire_body")
            for i, (x, y) in enumerate(bodies):
                team_side = i // 6
                keeper = i % 6 == 0
                sx, sy = self.w2s(x, y, v)
                R = PR * s
                if team_side == me and self.drag and self.drag["i"] == i:
                    Color(*rgba("#fff36b", .45)); Ellipse(pos=(sx - R * 1.5, sy - R * 1.5), size=(R * 3, R * 3))
                elif active and team_side == me:
                    Color(*rgba("#fff36b"))
                    Line(circle=(sx, sy, R * pulse), width=max(1.5, R * .14))
                flaming = (fx.get("fire") == team_side and fire_body == i % 6) or \
                          (armed[team_side] and not keeper and fx.get("fire") is None)
                if flaming:
                    self.flame_ring(sx, sy, R, now, small=fx.get("fire") is None)
                self.jersey(sx, sy, R, self.match["teams"][team_side], keeper, team_side,
                            self.num(i))
            self.draw_magnet(bodies, fx, v, now)
            self.draw_stun(bodies, fx, v, now)
            self.draw_ball(ball, fx, v, now, dt)
        self.draw_pausa(fx, v, now, dt)
        self.draw_aim(bodies, v)
        self.draw_scoreboard()
        self.draw_abilities()
        self.draw_center_messages(now)

    def num(self, i):
        """Dorsal fijo por posición (arquero siempre 1); el servidor no manda dorsales."""
        return (1, 2, 4, 6, 8, 10)[i % 6]

    def draw_pitch(self, v):
        _, s, _, _ = v
        stripe = (FX1 - FX0) / 10
        for i in range(10):
            self.quad(FX0 + i * stripe, FY0, FX0 + (i + 1) * stripe, FY1,
                      C["grass"] if i % 2 else C["grass2"], 1, v)
        lw = max(1.3, 2.4 * s)
        Color(1, 1, 1, .95)
        self.wline([(FX0, FY0), (FX1, FY0), (FX1, FY1), (FX0, FY1), (FX0, FY0)], lw, v)
        self.wline([((FX0 + FX1) / 2, FY0), ((FX0 + FX1) / 2, FY1)], lw, v)
        cx, cy = self.w2s((FX0 + FX1) / 2, MY, v)
        Line(circle=(cx, cy, 80 * s), width=lw)
        Ellipse(pos=(cx - 4 * s, cy - 4 * s), size=(8 * s, 8 * s))
        for side in (-1, 1):
            ln = FX0 if side < 0 else FX1
            Color(1, 1, 1, .95)
            self.wline([(ln, MY - 150), (ln - side * 150, MY - 150), (ln - side * 150, MY + 150), (ln, MY + 150)],
                       lw, v)
            self.wline([(ln, MY - 70), (ln - side * 55, MY - 70), (ln - side * 55, MY + 70), (ln, MY + 70)], lw, v)
            px, py = self.w2s(ln - side * 105, MY, v)
            Ellipse(pos=(px - 3 * s, py - 3 * s), size=(6 * s, 6 * s))
            back = ln + side * GD
            self.quad(min(ln, back), GY0, max(ln, back), GY1, "#e8e8e8", 1, v)
            Color(*rgba("#9a9a9a"))
            for k in range(1, 7):                                   # red
                yy = GY0 + k * GOAL_H / 7
                self.wline([(ln, yy), (back, yy)], 1, v)
            for k in range(1, 4):
                xx = ln + side * GD * k / 4
                self.wline([(xx, GY0), (xx, GY1)], 1, v)
            Color(1, 1, 1, 1)
            self.wline([(ln, GY0), (back, GY0), (back, GY1), (ln, GY1)], lw, v)
            for yy in (GY0, GY1):
                px, py = self.w2s(ln, yy, v)
                Ellipse(pos=(px - 4 * s, py - 4 * s), size=(8 * s, 8 * s))

    def flame_ring(self, sx, sy, R, now, small=False):
        """Lenguas de fuego animadas alrededor de la chapita (como draw_fire_ring offline)."""
        k = .6 if small else 1.0
        for i in range(28):
            a = i * math.tau / 28
            height = (.3 + .18 * math.sin(now * 12 + i * 1.7)) * k
            inner, outer = R * 1.08, R * (1.1 + .3 * k + height)
            da = math.tau / 65
            wob = .025 * math.sin(now * 9 + i)
            self.poly([(sx + math.cos(a - da) * inner, sy + math.sin(a - da) * inner),
                       (sx + math.cos(a + wob) * outer, sy + math.sin(a + wob) * outer),
                       (sx + math.cos(a + da) * inner, sy + math.sin(a + da) * inner)],
                      "#ff5a12" if i % 2 else "#ffd400")

    def draw_ball(self, ball, fx, v, now, dt):
        _, s, _, _ = v
        sx, sy = self.w2s(*ball, v)
        R0 = BR * s
        if fx.get("fire") is not None:                       # elevación visual 1x -> 2x -> 1x (radio físico intacto)
            prog = min(1.0, (now - self.fire_started) / 2.0)
            self.ball_scale = 1.0 + math.sin(math.pi * prog)
        else:
            self.ball_scale = 1.0 + (self.ball_scale - 1.0) * math.exp(-dt * 10)
            if self.ball_scale < 1.003:
                self.ball_scale = 1.0
        R = R0 * self.ball_scale
        lift = (self.ball_scale - 1) * R0 * 2.2
        if fx.get("fire") is not None:                       # textura original fuego.png detrás del balón
            size = R * 4.2
            if not self.image("fuego.png", sx, sy + lift + R * .4, size, size, .95):
                Color(*rgba(C["orange"], .55)); Ellipse(pos=(sx - R * 2, sy + lift - R * 2), size=(R * 4, R * 4))
        Color(*rgba("#062b14", 1 - .45 * (self.ball_scale - 1)))
        sh = R0 * (1 + .25 * (self.ball_scale - 1))
        Ellipse(pos=(sx - sh + 2 + lift * .35, sy - sh - 3 - lift * .2), size=(2 * sh, 2 * sh))
        spin = (ball[0] + ball[1]) * .08
        by = sy + lift
        Color(1, 1, 1, 1); Ellipse(pos=(sx - R, by - R), size=(2 * R, 2 * R))
        Color(*rgba("#111111"))
        for k in range(5):
            a = spin + k * math.tau / 5
            px, py = sx + math.cos(a) * R * .55, by + math.sin(a) * R * .55
            Ellipse(pos=(px - R * .2, py - R * .2), size=(R * .4, R * .4))
        Ellipse(pos=(sx - R * .25, by - R * .25), size=(R * .5, R * .5))
        Line(circle=(sx, by, R), width=max(1, R * .12))

    def draw_magnet(self, bodies, fx, v, now):
        _, s, _, _ = v
        mag = fx.get("magnet", [False, False])
        me = self.match["side"]
        for side in (0, 1):
            if not mag[side]:
                continue
            col = C["cyan"] if side == me else C["pink"]
            for i in range(side * 6, side * 6 + 6):
                x, y = self.w2s(*bodies[i], v)
                r = PR * s * MAG_RADIUS
                Color(*rgba(col, .07 + .03 * math.sin(now * 5)))
                Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
                Color(*rgba(col))
                Line(circle=(x, y, r), width=max(1.5, r * .04))
                for k in range(5):
                    a = now * 1.8 + k * math.tau / 5
                    px, py = x + math.cos(a) * r * .96, y + math.sin(a) * r * .96
                    d = max(1.2, r * .045)
                    Ellipse(pos=(px - d, py - d), size=(2 * d, 2 * d))

    def draw_stun(self, bodies, fx, v, now):
        _, s, _, _ = v
        for side in (0, 1):
            if not fx.get("stun", [False, False])[side]:
                continue
            x, y = self.w2s(*bodies[side * 6], v)
            R = PR * s
            fade = min(1.0, (now - self.stun_started[side]) / .3) if self.stun_started[side] else 1.0
            Color(*rgba("#7df9ff", .35 * fade)); Ellipse(pos=(x - R, y - R), size=(2 * R, 2 * R))
            Color(*rgba("#7df9ff", fade))
            for i in range(7):
                ang = i * math.tau / 7 + .16 * math.sin(now * 8 + i)
                r = R * (.45 if i % 3 == 0 else 1.1)
                blink = .5 + .5 * math.sin(now * 17 + i * 2)
                ln = R * .45 * fade * blink
                if ln < .4:
                    continue
                px, py = x + math.cos(ang) * r, y + math.sin(ang) * r
                Line(points=[px, py, px + ln * .3, py + ln * .35, px - ln * .15, py + ln * .65,
                             px + ln * .35, py + ln], width=max(1, R * .07))

    def draw_pausa(self, fx, v, now, dt):
        """Partículas y velo violeta de PAUSA sobre la cancha (como draw_pausa_effect offline)."""
        if fx.get("pausa") is None:
            self.particles = []
            return
        px, py, pw, ph = self.layout()["pitch"]
        left = float(self.cur.get("fx", {}).get("pausa_left", 10.0))
        fade = max(0.0, min(1.0, (10 - left) / .4, left / .6))
        if not self.particles:
            rng = random.Random()
            self.particles = [dict(x=rng.random(), y=rng.random(), vx=rng.uniform(-.012, .012),
                                   vy=rng.uniform(.006, .03), r=rng.uniform(.7, 2.1), ph=rng.uniform(0, math.tau),
                                   c=rng.choice(("#7df9ff", "#c58bff", "#ffffff", "#ff7ad9"))) for _ in range(70)]
        Color(*rgba("#3a1aff", .10 * fade)); Rectangle(pos=(px, py), size=(pw, ph))
        u = self.u
        for p in self.particles:
            p["x"] = (p["x"] + p["vx"] * dt) % 1.0
            p["y"] = (p["y"] + p["vy"] * dt) % 1.0
            tw = .55 + .45 * math.sin(now * 3 + p["ph"])
            r = p["r"] * u * .32 * (.7 + .5 * tw)
            x, y = px + p["x"] * pw, py + p["y"] * ph
            Color(*rgba(p["c"], .12 * fade * tw)); Ellipse(pos=(x - r * 2.2, y - r * 2.2), size=(r * 4.4, r * 4.4))
            Color(*rgba(p["c"], .55 * fade * tw)); Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
        cx, cy, rr = px + pw - u * 2.2, py + ph - u * 2.2, u * 1.4
        Color(*rgba(C["night"], .6)); Ellipse(pos=(cx - rr, cy - rr), size=(2 * rr, 2 * rr))
        Color(*rgba("#7df9ff"))
        Line(circle=(cx, cy, rr, 0, 360 * max(0.0, left) / 10), width=max(2, u * .25))
        self.text(cx, cy, str(int(math.ceil(max(0.0, left)))), u * 1.0, C["chalk"], TITLE, shadow=False)

    def draw_aim(self, bodies, v):
        a = self.aim(bodies)
        if not a:
            return
        bx, by, ux, uy, pw = a
        _, s, _, _ = v
        L = max(pw, .05) * MAX_DRAG
        x0, y0 = self.w2s(bx, by, v)
        x1, y1 = self.w2s(bx + ux * L, by + uy * L, v)
        col = "#3cff6e" if pw < .5 else ("#ffd400" if pw < .85 else "#ff3b3b")
        Color(*rgba("#000000", .35))
        Line(points=[x0 + 2, y0 - 2, x1 + 2, y1 - 2], width=max(2, 2.6 * s))
        Color(*rgba(col))
        Line(points=[x0, y0, x1, y1], width=max(2, 2.6 * s))
        ang = math.atan2(y1 - y0, x1 - x0)
        hl, hw = 16 * s + 6, 7 * s + 3
        bxp, byp = x1 - math.cos(ang) * hl, y1 - math.sin(ang) * hl
        nx, ny = -math.sin(ang), math.cos(ang)
        self.poly([(x1 + math.cos(ang) * 2, y1 + math.sin(ang) * 2), (bxp + nx * hw, byp + ny * hw),
                   (bxp - nx * hw, byp - ny * hw)], col)
        fx = self.cur.get("fx", {}) if self.cur else {}
        maximum = 150 if fx.get("fire_armed", [False, False])[self.match["side"]] and self.drag["i"] % 6 else \
            (50 if self.drag["i"] % 6 == 0 else 100)
        self.text(x0, y0 + (PR + 22) * s + 6, f"{int(pw * maximum)}%", self.u * .9, col, TITLE)

    def quad(self, x0, y0, x1, y1, col, a=1.0, v=None):
        (ax, ay), (bx, by) = self.w2s(x0, y0, v), self.w2s(x1, y1, v)
        Color(*rgba(col, a))
        Rectangle(pos=(min(ax, bx), min(ay, by)), size=(abs(bx - ax), abs(by - ay)))

    def wline(self, pts, width=1.6, v=None):
        flat = []
        for p in pts:
            flat.extend(self.w2s(*p, v))
        Line(points=flat, width=width)

    def clock_text(self, t):
        gs = int(t * 5400 / (2 * HALF_REAL))                # 90' = 5 min reales
        return f"{gs // 60:02d}:{gs % 60:02d}"

    def draw_scoreboard(self):
        """Marcador estilo TV: banderas, nombres ajustados, goles, reloj y recarga integrados."""
        st, m, u = self.cur, self.match, self.u
        if not m:
            return
        me = m["side"]
        sc = st["score"] if st else [0, 0]
        hx, hy, hw, hh = self.layout()["hud"]
        Color(*rgba(C["hud"])); Rectangle(pos=(hx, hy), size=(hw, hh))
        Color(*rgba(C["gold"], .9)); Rectangle(pos=(hx, hy), size=(hw, 2))
        # botón rendirse (izquierda, dentro del HUD)
        bs = hh * .62
        self.button(hx + bs * .5 + u * .4, hy + hh / 2, bs, bs, "X", self.ask_surrender, "#e6c98e")
        cap_w = min(hw - bs * 2 - u * 2, u * 30)
        cx = hx + hw / 2
        row = hy + hh * .58
        ch = hh * .62
        x0 = cx - cap_w / 2
        Color(*rgba("#020d08", .95)); RoundedRectangle(pos=(x0, row - ch / 2), size=(cap_w, ch), radius=[ch / 2])
        box_w = ch * 2.3                                         # caja central de goles
        Color(*rgba(C["gold"])); RoundedRectangle(pos=(cx - box_w / 2, row - ch / 2), size=(box_w, ch),
                                                  radius=[ch * .25])
        self.text(cx, row, f"{sc[me]} - {sc[1 - me]}", ch * .78, C["ink"], TITLE, shadow=False, max_w=box_w * .92)
        fw = ch * .9
        fh = fw * .66
        gap = ch * .25
        for k, side in ((-1, me), (1, 1 - me)):
            team = m["teams"][side]
            col1 = kit(team)[0]
            edge = x0 if k < 0 else x0 + cap_w
            # franja de color de la selección al borde
            Color(*rgba(col1)); RoundedRectangle(pos=(edge - (0 if k < 0 else ch * .3), row - ch / 2),
                                                 size=(ch * .3, ch), radius=[ch * .15])
            fx = edge + (ch * .45 + fw / 2) * (1 if k < 0 else -1)
            self.flag(fx - fw / 2, row - fh / 2, fw, fh, team)
            inner = fx + (fw / 2 + gap) * (1 if k < 0 else -1)
            limit = cx + (-box_w / 2 - gap if k < 0 else box_w / 2 + gap)
            max_w = abs(limit - inner)
            name = (m["names"][side] or abbr(team)).upper()
            label = name if max_w > self.measure(abbr(team), ch * .5, TITLE)[0] * 2.2 else abbr(team)
            self.text(inner, row, label, ch * .5, C["chalk"], TITLE,
                      anchor="left" if k < 0 else "right", shadow=False, max_w=max_w)
        # segunda fila: periodo, reloj, recarga integrada
        if st:
            per = {"first": "1T", "second": "2T", "extra": "PRÓRROGA", "golden": "GOL DE ORO"}.get(st["phase"], "")
            cd = st["cd"]["shot"][me]
            paused_by = st.get("fx", {}).get("pausa")
            if paused_by is not None and paused_by != me:
                who, frac, col = "CONGELADO POR PAUSA", 1.0, "#c58bff"
            elif st.get("kick_lock"):
                who, frac, col = ("SACAS TÚ" if st["kickoff"] == me else "SACA EL RIVAL"), 1.0, "#ffd400"
            elif cd > 0:
                who, frac, col = f"RECARGA {cd:.1f}s", max(0.0, 1 - cd), "#ff9f3c"
            else:
                who, frac, col = "¡TIRA!", 1.0, "#3cff6e"
            info = f"{per}  ·  {self.clock_text(st['t'])}  ·  {who}"
            bar_w = cap_w * .62
            bh = max(3.0, hh * .06)
            by = hy + hh * .07
            Color(1, 1, 1, .12); RoundedRectangle(pos=(cx - bar_w / 2, by), size=(bar_w, bh), radius=[bh / 2])
            Color(*rgba(col)); RoundedRectangle(pos=(cx - bar_w / 2, by), size=(max(bh, bar_w * frac), bh),
                                               radius=[bh / 2])
            self.text(cx, row - ch / 2 - (row - ch / 2 - by - bh) / 2, info, max(10, hh * .17), col, BODY, shadow=True,
                      max_w=bar_w)

    def draw_abilities(self):
        st, m, u = self.cur, self.match, self.u
        if not st:
            return
        me = m["side"]
        fx = st.get("fx", {})
        defs = [("fire", "fuego.png", "#ffd400", C["red"], "FUEGO"),
                ("pausa", "pausa.png", "#ff5cc8", C["sky"], "PAUSA"),
                ("magnet", "campo.png", C["cyan"], C["violet"], "CAMPO")]
        lay = self.layout()
        if lay["land"]:
            hx, hy, hw, hh = lay["pitch"]
            Color(*rgba(C["hud"])); Rectangle(pos=(hx + hw, self.y), size=(self.width - hw, hh))
        else:
            bh = lay["pitch"][1] - self.y
            Color(*rgba(C["hud"])); Rectangle(pos=(self.x, self.y), size=(self.width, bh))
        for (key, img, ring, fallback, label), (cx, cy, size) in zip(defs, lay["slots"]):
            cd = st["cd"][key][me]
            active = {"fire": fx.get("fire_armed", [False, False])[me] or fx.get("fire") == me,
                      "pausa": fx.get("pausa") == me,
                      "magnet": fx.get("magnet", [False, False])[me]}[key]
            r = size / 2
            Color(*rgba(C["night"], .9)); Ellipse(pos=(cx - r, cy - r), size=(size, size))
            if not self.image(img, cx, cy, size * .92, size * .92):
                Color(*rgba(fallback)); Ellipse(pos=(cx - r * .85, cy - r * .85), size=(r * 1.7, r * 1.7))
                self.text(cx, cy, label, r * .45, C["ink"], TITLE, shadow=False, max_w=size * .8)
            if cd > 0 and not active:
                Color(*rgba("#071b13", .55)); Ellipse(pos=(cx - r, cy - r), size=(size, size))
                total = max(TOTAL_CD[key], cd)
                Color(1, 1, 1, 1)
                Line(circle=(cx, cy, r * .93, 0, 360 * (cd / total)), width=max(2, size * .05))
                self.text(cx, cy, str(int(math.ceil(cd))), size * .36, C["chalk"], TITLE)
            elif active:
                Color(*rgba(ring, .7 + .3 * math.sin(time.time() * 8)))
                Line(circle=(cx, cy, r + 3), width=4)
            else:
                Color(*rgba(ring, .9)); Line(circle=(cx, cy, r + 1), width=2)
            self.buttons.append(Btn((cx - r, cy - r, size, size), key, lambda k=key: self.use_ability(k), fallback))

    def draw_center_messages(self, now):
        st = self.cur
        px, py, pw, ph = self.layout()["pitch"]
        cx, cy = px + pw / 2, py + ph / 2
        u = self.u
        if self.goal_flash > now:
            k = 1 - (self.goal_flash - now) / 2.2
            size = u * (3.2 + 1.6 * min(1, k * 4))
            mine = self.goal_team == self.match["side"]
            Color(*rgba(C["night"], .55)); Rectangle(pos=(px, cy - u * 2.6), size=(pw, u * 5.2))
            self.text(cx, cy + u * .4, "¡GOOOL!", size, C["lime"] if mine else C["orange"], TITLE, max_w=pw * .9)
            team = self.match["teams"][self.goal_team] if self.goal_team is not None else ""
            self.text(cx, cy - u * 1.8, (team or "").upper(), u * 1.1, C["chalk"], TITLE, max_w=pw * .8)
        elif self.banner and self.banner[1] > now:
            Color(*rgba(C["night"], .6)); Rectangle(pos=(px, cy - u * 1.6), size=(pw, u * 3.2))
            self.text(cx, cy, self.banner[0], u * 2.2, C["gold"], TITLE, max_w=pw * .9)
        elif st and st.get("kick_lock"):
            who = "SACAS TÚ" if st["kickoff"] == self.match["side"] else "SACA EL RIVAL"
            self.text(cx, cy + u * 3.2, who, u * 1.5, C["gold"], TITLE, max_w=pw * .8)

    # ------------------------------------------------------------ acciones
    def set_state(self, s):
        self.state = s
        self.msg = ""
        if s == "lobby" and self.net.token:
            self._bg(self.net.refresh_account, lambda _r: self.redraw())
        self.redraw()

    def _bg(self, fn, ok, fail=None):
        def work():
            try:
                res = fn()
                Clock.schedule_once(lambda _dt: ok(res), 0)
            except NetError as e:
                msg = str(e)
                Clock.schedule_once(lambda _dt: (fail or self._fail)(msg), 0)
        threading.Thread(target=work, daemon=True).start()

    def _fail(self, msg):
        self.busy = False
        self.msg = msg
        if self.state != "login":
            self.toast(msg, "#ffb3a8")
        self.redraw()

    def auth(self, create):
        user, pw = self.user_in.text, self.pass_in.text
        self.busy = True
        self.msg = ""
        fn = (lambda: self.net.register(user, pw)) if create else (lambda: self.net.login(user, pw))

        def ok(_acc):
            self.busy = False
            self.pass_in.text = ""
            try:
                self.net.connect()
            except NetError as e:
                return self._fail(str(e))
            self.set_state("lobby")
        self._bg(fn, ok)
        self.redraw()

    def pick(self, d):
        self.team_i = (self.team_i + d) % len(self.teams)
        self.redraw()

    def search(self, mode):
        self.mode = mode
        self.search_at = time.time()
        self.match = None
        self.prev = self.cur = None
        self.net.queue_match(mode, self.teams[self.team_i])
        self.play("load")
        self.set_state("search")

    def cancel_search(self):
        self.net.cancel()
        self.set_state("lobby")

    def open_podium(self):
        self._bg(self.net.leaderboard, lambda rows: (setattr(self, "podium", rows), self.set_state("podium")))

    def use_ability(self, key):
        if self.state == "match":
            self.net.ability(key)

    def ask_surrender(self):
        if getattr(self, "surrender_at", 0) > time.time() - 2:
            self.net.surrender()
        else:
            self.surrender_at = time.time()
            self.toast("Toca X otra vez para rendirte", "#ffb3a8")

    def exit(self):
        self.net.close()
        Clock.unschedule(self._ev)
        if self.parent is not None:
            self.parent.remove_widget(self)
        if self.on_exit:
            self.on_exit()

    def play(self, key):
        snd = self.sounds.get(key)
        if snd is not None:
            try:
                snd.stop(); snd.play()
            except Exception:
                pass

    # ------------------------------------------------------------ mensajes del servidor
    def _tick(self, _dt):
        for msg in self.net.poll():
            self.handle(msg)
        if self.state in ("match", "search", "login", "lobby") or self.toasts:
            self.redraw()

    def handle(self, msg):
        kind = msg.get("type")
        if kind == "match_start":
            self.match = msg
            self.state = "match"
            self.prev = self.cur = None
            self.drag = None
            rival = msg["names"][1 - msg["side"]]
            self.toast(f"¡RIVAL ENCONTRADO! {rival}", C["lime"])
            self.play("start")
        elif kind == "state" and self.match:
            self.prev, self.cur, self.cur_at = self.cur, msg, time.time()
            for ev in msg.get("events", []):
                self.event(ev)
        elif kind == "match_end":
            self.result = msg
            self.toasts = []
            self.net.account = msg.get("me", self.net.account)
            self.play("goal" if msg.get("winner") == (self.match or {}).get("side") else "lose")
            self.drag = None
            self.set_state("result")
        elif kind in ("disconnected", "net_error"):
            if self.state in ("match", "search", "lobby"):
                self.toast("Conexión perdida con el servidor", "#ffb3a8")
                self.state = "login"
                self.redraw()

    def event(self, ev):
        me = self.match["side"]
        name = ev.get("name")
        mine = ev.get("team") == me
        if name == "goal":
            self.goal_flash = time.time() + 2.2
            self.goal_team = ev.get("team")
            self.play("goal" if mine else "lose")
        elif name == "shot":
            self.play("kick")
        elif name in ("fire_start", "pausa_start", "magnet_start"):
            key = name.split("_")[0]
            if key == "fire":
                self.fire_started = time.time()
            self.play(key)
            label = {"fire": "FUEGO", "pausa": "PAUSA", "magnet": "CAMPO MAGNÉTICO"}[key]
            self.toast(f"{label} {'TUYO' if mine else 'DEL RIVAL'}", C["lime"] if mine else C["orange"])
        elif name == "fire_armed" and mine:
            self.play("fire")
        elif name == "keeper_stun":
            t = ev.get("team")
            if t in (0, 1):
                self.stun_started[t] = time.time()
            self.play("stun")
            self.toast("¡ARQUERO ELECTROCUTADO!", C["sky"])
        elif name == "magnet_broken":
            self.toast("¡EL FUEGO ROMPIÓ EL CAMPO!", C["orange"])
        elif name == "half_time":
            self.banner = ("SEGUNDO TIEMPO", time.time() + 2.0)
            self.play("whistle")
        elif name == "extra_time":
            self.banner = ("PRÓRROGA", time.time() + 2.0)
            self.play("whistle")
        elif name == "golden_goal":
            self.banner = ("GOL DE ORO", time.time() + 2.0)
            self.play("whistle")
        elif name == "match_end":
            self.play("end")

    # ------------------------------------------------------------ toques
    def on_touch_down(self, touch):
        if self.state == "login" and any(t.collide_point(*touch.pos) for t in (self.user_in, self.pass_in)):
            return super().on_touch_down(touch)
        for b in reversed(self.buttons):
            if b.hit(*touch.pos):
                b.action()
                return True
        if self.state == "match" and self.cur:
            bodies, _ = self.positions()
            me = self.match["side"]
            v = self.view()
            best = None
            for i in range(me * 6, me * 6 + 6):
                sx, sy = self.w2s(*bodies[i], v)
                d = math.hypot(sx - touch.x, sy - touch.y)
                if d < max(PR * v[1] * 2.2, 34) and (best is None or d < best[0]):
                    best = (d, i)
            if best:
                self.drag = {"i": best[1], "cur": touch.pos}
        return True

    def on_touch_move(self, touch):
        if self.drag:
            self.drag["cur"] = touch.pos
        return True

    def on_touch_up(self, touch):
        if self.drag and self.state == "match":
            self.drag["cur"] = touch.pos
            a = self.aim()
            if a:
                bx, by, ux, uy, pw = a
                wx, wy = self.s2w(*touch.pos)
                if math.hypot(wx - bx, wy - by) >= 6:                   # arrastre mínimo, como offline
                    self.net.shoot(self.drag["i"] % 6, ux * pw * MAX_DRAG, uy * pw * MAX_DRAG)
        self.drag = None
        return True


def open_online(on_exit=None, data_dir=None):
    """Llamar desde el menú: abre el modo EN LÍNEA sobre la ventana actual."""
    screen = OnlineScreen(on_exit=on_exit, data_dir=data_dir, size=Window.size)
    Window.bind(size=lambda _w, s: setattr(screen, "size", s))
    Window.add_widget(screen)
    return screen


if __name__ == "__main__":          # prueba rápida en PC: python online_view.py
    from kivy.app import App

    class OnlineTest(App):
        def build(self):
            root = FloatLayout()
            root.add_widget(OnlineScreen(on_exit=self.stop, data_dir=self.user_data_dir))
            return root
    OnlineTest().run()
