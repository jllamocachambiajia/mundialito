"""Modo EN LÍNEA de Mundialito de Chapas (Kivy puro, se superpone al juego existente).
Pantallas: acceso, vestuario (lobby), búsqueda de rival, partido en vivo, resultado y podio mundial.
El partido solo DIBUJA lo que manda el servidor autoritario e interpola entre estados."""
import math
import os
import threading
import time

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel, LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle, PushMatrix, PopMatrix, Rotate
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from network_client import NetError, NetworkClient, load_server_url

HERE = os.path.dirname(os.path.abspath(__file__))
FX0, FY0, FX1, FY1 = 60, 80, 1040, 680          # mismas medidas que el servidor / main.py
MY = (FY0 + FY1) / 2
GOAL_H, GD, PR, BR, MAX_DRAG = 140, 40, 18, 10, 160
WX0, WX1, WY0, WY1 = FX0 - GD - 10, FX1 + GD + 10, FY0 - 12, FY1 + 12

C = {"night": "#041f15", "deep": "#052d20", "grass": "#0f7a3a", "grass2": "#0c6b33", "lime": "#b5f65a",
     "orange": "#ff761b", "gold": "#ffd52a", "chalk": "#f4f7ef", "ink": "#0b261b", "red": "#ff3b30",
     "sky": "#5ec8ff", "violet": "#b98cff"}
FALLBACK_TEAMS = ["Argentina", "Brasil", "España", "Francia", "Alemania", "Inglaterra", "Italia", "Portugal",
                  "Países Bajos", "Bélgica", "Croacia", "Uruguay", "Colombia", "México", "Estados Unidos",
                  "Chile", "Suecia", "Dinamarca", "Suiza", "Polonia", "Hungría", "Paraguay", "Perú", "Ecuador"]


KIT = {'España': ('#ff1a2e', '#ffd400'), 'Francia': ('#2453ff', '#ffffff'), 'Alemania': ('#ffffff', '#111111'), 'Inglaterra': ('#ffffff', '#ff1f3d'), 'Italia': ('#1e90ff', '#ffffff'), 'Portugal': ('#ff1f3d', '#00c853'), 'Países Bajos': ('#ff7a00', '#ffffff'), 'Bélgica': ('#ff2020', '#ffd400'), 'Croacia': ('#ffffff', '#ff1f2f'), 'Argentina': ('#ffffff', '#5ec8ff'), 'Brasil': ('#ffe600', '#00b84f'), 'Uruguay': ('#4fc3ff', '#ffffff'), 'Colombia': ('#ffd60a', '#2a5bff'), 'México': ('#00b560', '#ff2b3a'), 'Estados Unidos': ('#ffffff', '#ff2b3a'), 'Chile': ('#ff2a1f', '#1f55ff'), 'Suecia': ('#ffd800', '#1a5cff'), 'Dinamarca': ('#ff1f2f', '#ffffff'), 'Suiza': ('#ff1a1a', '#ffffff'), 'Polonia': ('#ffffff', '#ff1f3d'), 'Hungría': ('#ff2030', '#ffffff'), 'Paraguay': ('#ffffff', '#ff1f2f'), 'Perú': ('#ffffff', '#ff1f2f'), 'Ecuador': ('#ffe100', '#1f4dff')}


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


def team_colors(name):
    """Usa los colores de camiseta del juego (TEAMS en main.py) si existe; si no, un respaldo."""
    try:
        import main
        t = main.TEAMS.get(name)
        if t:
            return t[1], t[2]
    except Exception:
        pass
    return KIT.get(name, ("#ffffff", "#1f4dff"))


def team_list():
    try:
        import main
        return list(main.TEAMS.keys())
    except Exception:
        return list(KIT) or FALLBACK_TEAMS


def _sound(name):
    try:
        from kivy.core.audio import SoundLoader
        for sub in ("effects", ""):
            p = os.path.join(HERE, "assets", "sounds", sub, name)
            if os.path.exists(p):
                return SoundLoader.load(p)
    except Exception:
        pass
    return None


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
        self.labels = []
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
        self.anim_t = 0.0
        self.sounds = {k: _sound(f) for k, f in (("fire", "fuego.wav"), ("pausa", "pausa_inicio.wav"),
                                                   ("magnet", "campo.wav"), ("goal", "avanzar_nivel.wav"),
                                                   ("lose", "perder.wav"), ("load", "carga.wav"))}
        self.user_in = self._input("usuario", False)
        self.pass_in = self._input("contraseña", True)
        self.bind(size=lambda *_: self.redraw(), pos=lambda *_: self.redraw())
        self._ev = Clock.schedule_interval(self._tick, 1 / 60)
        self.redraw()

    # ------------------------------------------------------------ utilidades UI
    def _input(self, hint, secret):
        t = TextInput(hint_text=hint, password=secret, multiline=False, font_name=BODY,
                      size_hint=(None, None), write_tab=False, padding=(14, 12),
                      background_color=rgba("#f4f7ef"), foreground_color=rgba(C["ink"]),
                      cursor_color=rgba(C["orange"]))
        return t

    @property
    def u(self):
        return max(8.0, min(self.width / 30.0, self.height / 22.0))

    def text(self, x, y, s, size, color=C["chalk"], font=None, anchor="center", shadow=True):
        lab = CoreLabel(text=s, font_name=font or BODY, font_size=size, color=rgba(color))
        lab.refresh()
        w, h = lab.texture.size
        px = x - w / 2 if anchor == "center" else (x if anchor == "left" else x - w)
        py = y - h / 2
        if shadow:
            Color(*rgba(C["night"], .85))
            Rectangle(texture=lab.texture, pos=(px + 2, py - 2), size=(w, h))
        Color(1, 1, 1, 1)
        Rectangle(texture=lab.texture, pos=(px, py), size=(w, h))

    def button(self, cx, cy, w, h, label, action, color=C["gold"], fg=C["ink"], enabled=True):
        x, y = cx - w / 2, cy - h / 2
        Color(*rgba(C["night"], .6))
        RoundedRectangle(pos=(x + 3, y - 4), size=(w, h), radius=[h / 2])
        Color(*rgba(color if enabled else "#55635a"))
        RoundedRectangle(pos=(x, y), size=(w, h), radius=[h / 2])
        Color(1, 1, 1, .18)
        RoundedRectangle(pos=(x + 6, y + h * .52), size=(w - 12, h * .38), radius=[h / 3])
        self.text(cx, cy, label, h * .5, fg if enabled else "#c9d2cc", TITLE, shadow=False)
        self.buttons.append(Btn((x, y, w, h), label, action, color, fg, enabled))

    def pitch_bg(self):
        """Fondo de estadio: césped a franjas, cal y focos."""
        w, h = self.width, self.height
        Color(*rgba(C["deep"]))
        Rectangle(pos=self.pos, size=self.size)
        n = 10
        for i in range(n):
            Color(*rgba(C["grass"] if i % 2 else C["grass2"], .55))
            Rectangle(pos=(self.x + i * w / n, self.y), size=(w / n + 1, h))
        Color(*rgba(C["chalk"], .14))
        Line(circle=(self.center_x, self.center_y, min(w, h) * .22), width=2)
        Line(points=[self.center_x, self.y, self.center_x, self.top], width=2)
        for fx in (.08, .92):
            Color(1, 1, 1, .05)
            Ellipse(pos=(self.x + w * fx - w * .25, self.top - h * .35), size=(w * .5, h * .6))
        Color(*rgba(C["night"], .55))
        Rectangle(pos=self.pos, size=(w, h * .12))
        Rectangle(pos=(self.x, self.top - h * .1), size=(w, h * .1))

    def header(self, title, sub=None, col=C["lime"]):
        self.text(self.center_x, self.top - self.height * .1, title, self.u * 2.6, col, TITLE)
        if sub:
            self.text(self.center_x, self.top - self.height * .1 - self.u * 2.1, sub, self.u * .85, C["chalk"])

    def toast(self, s, col=C["gold"]):
        self.toasts.append([s, col, time.time()])

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
        self.text(self.center_x, self.top - h * .13, "MUNDIAL", u * 3.4, C["lime"], TITLE)
        self.text(self.center_x + u * 1.5, self.top - h * .13 - u * 2.8, "EN LÍNEA", u * 2.4, C["orange"], TITLE)
        bw, bh = min(w * .78, 420), max(44, min(60, h * .07))
        for i, t in enumerate((self.user_in, self.pass_in)):
            t.size = (bw, bh)
            t.font_size = bh * .38
            t.pos = (self.center_x - bw / 2, self.y + h * .56 - i * bh * 1.3)
            if t.parent is None:
                self.add_widget(t)
        self.text(self.center_x, self.y + h * .56 + bh * 1.45, "Usuario: 3-16 letras, números o _", u * .7, C["chalk"])
        y = self.y + h * .56 - bh * 2.6
        self.button(self.center_x, y, bw, bh, "ENTRAR", lambda: self.auth(False), enabled=not self.busy)
        self.button(self.center_x, y - bh * 1.3, bw, bh, "CREAR CUENTA", lambda: self.auth(True), C["orange"],
                    enabled=not self.busy)
        self.button(self.center_x, y - bh * 2.6, bw * .6, bh * .8, "VOLVER", self.exit, "#e6c98e")
        if self.msg:
            self.text(self.center_x, y - bh * 3.6, self.msg, u * .8, "#ffb3a8")
        if self.busy:
            self.spinner(self.center_x, y - bh * 3.6, u)

    def draw_lobby(self):
        self.pitch_bg()
        a = self.net.account or {}
        u, w, h = self.u, self.width, self.height
        self.header("VESTUARIO", f"Hola, {a.get('usuario', '')}")
        cw, ch = min(w * .86, 520), u * 4.2
        cx, cy = self.center_x, self.top - h * .33
        Color(*rgba(C["night"], .8))
        RoundedRectangle(pos=(cx - cw / 2, cy - ch / 2), size=(cw, ch), radius=[18])
        Color(*rgba(C["lime"], .9))
        Line(rounded_rectangle=(cx - cw / 2, cy - ch / 2, cw, ch, 18), width=1.6)
        stats = [("ELO", a.get("elo", 1000), C["gold"]), ("V", a.get("victorias", 0), C["lime"]),
                 ("D", a.get("derrotas", 0), "#ff8a7a"), ("%", f"{a.get('porcentaje_victoria', 0):.0f}", C["sky"])]
        for i, (k, v, col) in enumerate(stats):
            x = cx - cw / 2 + cw * (i + .5) / 4
            self.text(x, cy + u * .7, str(v), u * 1.7, col, TITLE)
            self.text(x, cy - u * 1.1, k, u * .7, C["chalk"])
        # selector de selección
        team = self.teams[self.team_i]
        ty = self.top - h * .52
        self.token(self.center_x, ty, u * 1.6, team, 7, glow=C["gold"])
        self.text(self.center_x, ty - u * 2.4, team.upper(), u * 1.3, C["chalk"], TITLE)
        self.button(self.center_x - u * 5, ty, u * 2.2, u * 2.2, "<", lambda: self.pick(-1), C["lime"])
        self.button(self.center_x + u * 5, ty, u * 2.2, u * 2.2, ">", lambda: self.pick(1), C["lime"])
        bw, bh = min(w * .8, 420), max(44, min(62, h * .07))
        y = self.top - h * .7
        self.button(self.center_x, y, bw, bh, "AMISTOSO ALEATORIO", lambda: self.search("amistoso"))
        self.button(self.center_x, y - bh * 1.25, bw, bh, "RANKED", lambda: self.search("ranked"), C["orange"])
        self.button(self.center_x - bw * .26, y - bh * 2.5, bw * .48, bh * .85, "PODIO MUNDIAL", self.open_podium,
                    "#e6c98e")
        self.button(self.center_x + bw * .26, y - bh * 2.5, bw * .48, bh * .85, "SALIR", self.exit, "#9fb7a8")

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
        self.ball_icon(cx, cy + math.sin(t * 5) * u * .6, u * 1.6, t * 3)
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
        for idx, side, ph, col in spots:
            x = self.center_x + side * u * 6.2
            Color(*rgba(col))
            Rectangle(pos=(x - u * 2.8, floor), size=(u * 5.6, ph))
            self.text(x, floor + ph - u * 1.2, str(idx + 1), u * 2, C["ink"], TITLE, shadow=False)
            if idx < len(self.podium):
                p = self.podium[idx]
                self.token(x, floor + ph + u * 1.6, u * 1.2, None, idx + 1, glow=col)
                self.text(x, floor + ph + u * 3.5, p["usuario"], u * .9, C["chalk"], TITLE)
                self.text(x, floor + ph + u * 4.6, str(p["elo"]), u * .75, col)
        y = floor - u * 1.6
        for p in self.podium[3:10]:
            if y < self.y + h * .17:
                break
            Color(*rgba(C["night"], .7))
            RoundedRectangle(pos=(self.center_x - min(w * .42, 260), y - u * .75), size=(min(w * .84, 520), u * 1.5),
                             radius=[10])
            self.text(self.center_x - min(w * .38, 236), y, f"{p['puesto']}.  {p['usuario']}", u * .8, C["chalk"],
                      anchor="left", shadow=False)
            self.text(self.center_x + min(w * .38, 236), y,
                      f"{p['elo']}  ·  {p['porcentaje_victoria']:.0f}%", u * .8, C["gold"], anchor="right",
                      shadow=False)
            y -= u * 1.75
        self.button(self.center_x, self.y + h * .07, min(w * .6, 300), max(42, u * 2.2), "VOLVER",
                    lambda: self.set_state("lobby"), "#e6c98e")

    def draw_result(self):
        self.pitch_bg()
        r = self.result or {}
        u = self.u
        side = self.match["side"] if self.match else 0
        win = r.get("winner")
        title, col = ("¡VICTORIA!", C["lime"]) if win == side else ("EMPATE", C["gold"]) if win is None else \
            ("DERROTA", "#ff8a7a")
        self.text(self.center_x, self.top - self.height * .22, title, u * 3.6, col, TITLE)
        sc = r.get("score", [0, 0])
        mine, theirs = sc[side], sc[1 - side]
        self.text(self.center_x, self.center_y + u * 2, f"{mine}  -  {theirs}", u * 3, C["chalk"], TITLE)
        d = r.get("elo_change", 0)
        if self.match and self.match.get("mode") == "ranked":
            self.text(self.center_x, self.center_y - u * .6, f"ELO {'+' if d >= 0 else ''}{d}", u * 1.4,
                      C["lime"] if d >= 0 else "#ff8a7a", TITLE)
        bw, bh = min(self.width * .7, 360), max(48, u * 2.6)
        self.button(self.center_x, self.y + self.height * .3, bw, bh, "JUGAR OTRA",
                    lambda: self.search(self.match.get("mode", "amistoso")))
        self.button(self.center_x, self.y + self.height * .3 - bh * 1.3, bw, bh, "VESTUARIO",
                    lambda: self.set_state("lobby"), "#e6c98e")

    # ------------------------------------------------------------ partido
    def view(self):
        """Proyección mundo -> pantalla; en vertical la cancha se gira 90° como en el juego."""
        w, h = self.width, self.height - self.u * 7.5      # espacio para marcador y habilidades
        rot = h > w
        rw, rh = (WY1 - WY0, WX1 - WX0) if rot else (WX1 - WX0, WY1 - WY0)
        s = min(w / rw, h / rh)
        ox = self.x + (w - rw * s) / 2
        oy = self.y + self.u * 4.5 + (h - rh * s) / 2
        return rot, s, ox, oy

    def w2s(self, x, y):
        rot, s, ox, oy = self.view()
        if self.match and self.match["side"] == 1:
            x = FX0 + FX1 - x                                   # mi equipo siempre ataca hacia la derecha
        if rot:
            return ox + (y - WY0) * s, oy + (x - WX0) * s
        return ox + (x - WX0) * s, oy + (WY1 - y) * s

    def s2w_delta(self, dx, dy):
        rot, s, _, _ = self.view()
        wx, wy = (dy / s, dx / s) if rot else (dx / s, -dy / s)
        if self.match and self.match["side"] == 1:
            wx = -wx
        return wx, wy

    def positions(self):
        if self.cur is None:
            return None, None
        if self.prev is None:
            return self.cur["bodies"], self.cur["ball"]
        k = min(1.0, (time.time() - self.cur_at) * 30)
        lerp = lambda a, b: [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]
        return [lerp(a, b) for a, b in zip(self.prev["bodies"], self.cur["bodies"])], \
            lerp(self.prev["ball"], self.cur["ball"])

    def draw_match(self):
        Color(*rgba(C["night"]))
        Rectangle(pos=self.pos, size=self.size)
        st = self.cur
        rot, s, _, _ = self.view()
        # césped a franjas
        n = 14
        for i in range(n):
            x0 = FX0 + (FX1 - FX0) * i / n
            x1 = FX0 + (FX1 - FX0) * (i + 1) / n
            self.quad(x0, FY0, x1, FY1, C["grass"] if i % 2 else C["grass2"])
        fx = st["fx"] if st else {}
        if fx.get("fire") is not None:
            self.quad(FX0, FY0, FX1, FY1, C["red"], .12 + .06 * math.sin(time.time() * 12))
        if fx.get("pausa") is not None:
            self.quad(FX0, FY0, FX1, FY1, C["sky"], .14)
        # cal
        Color(*rgba(C["chalk"], .9))
        self.wline([(FX0, FY0), (FX1, FY0), (FX1, FY1), (FX0, FY1), (FX0, FY0)])
        self.wline([((FX0 + FX1) / 2, FY0), ((FX0 + FX1) / 2, FY1)])
        cx, cy = self.w2s((FX0 + FX1) / 2, MY)
        Line(circle=(cx, cy, 80 * s), width=1.4)
        for side in (0, 1):
            ln = FX0 if side == 0 else FX1
            sgn = 1 if side == 0 else -1
            self.wline([(ln, MY - 150), (ln + sgn * 150, MY - 150), (ln + sgn * 150, MY + 150), (ln, MY + 150)])
            self.wline([(ln, MY - 70), (ln + sgn * 55, MY - 70), (ln + sgn * 55, MY + 70), (ln, MY + 70)])
            back = ln - sgn * GD
            self.quad(min(ln, back), MY - GOAL_H / 2, max(ln, back), MY + GOAL_H / 2, "#e9efe6", .25)
            Color(1, 1, 1, 1)
            self.wline([(ln, MY - GOAL_H / 2), (back, MY - GOAL_H / 2), (back, MY + GOAL_H / 2), (ln, MY + GOAL_H / 2)],
                       3)
        bodies, ball = self.positions()
        if bodies:
            me = self.match["side"]
            for i, (x, y) in enumerate(bodies):
                team_side = i // 6
                sx, sy = self.w2s(x, y)
                glow = None
                if fx.get("magnet", [False, False])[team_side]:
                    Color(*rgba(C["violet"], .22 + .1 * math.sin(time.time() * 6)))
                    Ellipse(pos=(sx - PR * s * 2, sy - PR * s * 2), size=(PR * s * 4, PR * s * 4))
                if team_side == me and self.drag and self.drag["i"] == i:
                    glow = C["gold"]
                if team_side == me and fx.get("fire_armed", [False, False])[me] and i % 6:
                    glow = C["red"]
                stunned = i % 6 == 0 and fx.get("stun", [False, False])[team_side]
                self.token(sx, sy, PR * s, self.match["teams"][team_side], 1 if i % 6 == 0 else i % 6 + 1,
                           keeper=i % 6 == 0, glow=glow, dim=stunned)
            bx, by = self.w2s(*ball)
            if fx.get("fire") is not None:
                Color(*rgba(C["orange"], .55))
                Ellipse(pos=(bx - BR * s * 2.2, by - BR * s * 2.2), size=(BR * s * 4.4, BR * s * 4.4))
            self.ball_icon(bx, by, BR * s, 0)
        if self.drag and self.drag.get("cur"):
            x0, y0 = self.drag["sx"], self.drag["sy"]
            x1, y1 = self.drag["cur"]
            dx, dy = x0 - x1, y0 - y1
            Color(*rgba(C["gold"], .9))
            Line(points=[x0, y0, x0 + dx, y0 + dy], width=2.5, dash_length=8, dash_offset=4)
            p = min(1, math.hypot(*self.s2w_delta(dx, dy)) / MAX_DRAG)
            Color(*rgba(C["lime"] if p < .7 else C["orange"]))
            Ellipse(pos=(x0 + dx - 6, y0 + dy - 6), size=(12, 12))
        self.draw_scoreboard()
        self.draw_abilities()
        if st and st.get("kick_lock"):
            who = "SACAS TÚ" if st["kickoff"] == self.match["side"] else "SACA EL RIVAL"
            self.text(self.center_x, self.center_y, who, self.u * 1.6, C["gold"], TITLE)
        if getattr(self, "goal_flash", 0) > time.time():
            self.text(self.center_x, self.center_y + self.u * 2, "¡GOOOL!", self.u * 4.5, C["lime"], TITLE)

    def quad(self, x0, y0, x1, y1, col, a=1.0):
        (ax, ay), (bx, by) = self.w2s(x0, y0), self.w2s(x1, y1)
        Color(*rgba(col, a))
        Rectangle(pos=(min(ax, bx), min(ay, by)), size=(abs(bx - ax), abs(by - ay)))

    def wline(self, pts, width=1.6):
        flat = []
        for p in pts:
            flat.extend(self.w2s(*p))
        Line(points=flat, width=width)

    def draw_scoreboard(self):
        st, m, u = self.cur, self.match, self.u
        if not m:
            return
        me = m["side"]
        sc = st["score"] if st else [0, 0]
        h = u * 2.6
        y = self.top - h - 6
        w = min(self.width * .96, 760)
        x = self.center_x - w / 2
        Color(*rgba("#071a12", .92))
        RoundedRectangle(pos=(x, y), size=(w, h), radius=[h / 2])
        for k, side in ((0, me), (1, 1 - me)):
            c1, c2 = team_colors(m["teams"][side])
            px = x + h * .7 if k == 0 else x + w - h * .7
            Color(*rgba(c1)); Ellipse(pos=(px - h * .32, y + h * .18), size=(h * .64, h * .64))
            Color(*rgba(c2)); Line(circle=(px, y + h / 2, h * .32), width=2)
            name = m["names"][side][:9].upper()
            self.text(px + (h * .6 if k == 0 else -h * .6), y + h / 2, name, h * .4, C["chalk"], TITLE,
                      "left" if k == 0 else "right", shadow=False)
        self.text(self.center_x - h * 1.1, y + h / 2, str(sc[me]), h * .8, C["gold"], TITLE, shadow=False)
        self.text(self.center_x, y + h / 2, "-", h * .6, C["chalk"], TITLE, shadow=False)
        self.text(self.center_x + h * 1.1, y + h / 2, str(sc[1 - me]), h * .8, C["gold"], TITLE, shadow=False)
        if st:
            minute = int(st["t"] / (300.0 / 90.0))
            lbl = {"extra": "PRÓRROGA", "golden": "GOL DE ORO"}.get(st["phase"], "")
            self.text(self.center_x, y - u * .6, f"{minute}'  {lbl}", u * .8, C["lime"], shadow=False)
            cd = st["cd"]["shot"][me]
            bw = w * .3
            Color(1, 1, 1, .15); Rectangle(pos=(self.center_x - bw / 2, y - u * 1.4), size=(bw, 4))
            Color(*rgba(C["lime"] if cd <= 0 else C["orange"]))
            Rectangle(pos=(self.center_x - bw / 2, y - u * 1.4), size=(bw * (1 - min(1, cd)), 4))
        self.button(self.x + u * 1.4, self.y + u * 1.6, u * 2.2, u * 2.2, "X",
                    self.ask_surrender, "#e6c98e")

    def draw_abilities(self):
        st, m, u = self.cur, self.match, self.u
        if not st:
            return
        me = m["side"]
        defs = [("fire", "FUEGO", C["red"], 20), ("pausa", "PAUSA", C["sky"], 60), ("magnet", "CAMPO", C["violet"], 30)]
        r = u * 1.5
        for i, (key, label, col, total) in enumerate(defs):
            cx = self.center_x + (i - 1) * r * 3
            cy = self.y + u * 2.2
            cd = st["cd"][key][me]
            ready = cd <= 0
            Color(*rgba(C["night"], .9)); Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            Color(*rgba(col, 1 if ready else .35)); Ellipse(pos=(cx - r * .82, cy - r * .82), size=(1.64 * r, 1.64 * r))
            if not ready:
                Color(*rgba(C["chalk"], .9))
                Line(circle=(cx, cy, r * .95, 0, 360 * (1 - min(1, cd / total))), width=2.5)
                self.text(cx, cy, str(int(math.ceil(cd))), r * .8, C["chalk"], TITLE)
            else:
                self.text(cx, cy, label, r * .48, C["ink"], TITLE, shadow=False)
            self.buttons.append(Btn((cx - r, cy - r, 2 * r, 2 * r), key, lambda k=key: self.use_ability(k), col))

    # ------------------------------------------------------------ dibujos reutilizables
    def token(self, x, y, r, team, num, keeper=False, glow=None, dim=False):
        c1, c2 = team_colors(team) if team else ("#ffd52a", "#0b261b")
        if keeper:
            c1, c2 = "#ffd400", "#111111"
        if glow:
            Color(*rgba(glow, .55)); Ellipse(pos=(x - r * 1.45, y - r * 1.45), size=(r * 2.9, r * 2.9))
        Color(0, 0, 0, .35); Ellipse(pos=(x - r + 2, y - r - 3), size=(2 * r, 2 * r))
        Color(*rgba(c2)); Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
        Color(*rgba(c1)); Ellipse(pos=(x - r * .8, y - r * .8), size=(1.6 * r, 1.6 * r))
        Color(1, 1, 1, .35); Ellipse(pos=(x - r * .5, y + r * .05), size=(r * .7, r * .45))
        self.text(x, y, str(num), r * 1.0, c2 if c2 != c1 else C["ink"], TITLE, shadow=False)
        if dim:
            Color(*rgba(C["sky"], .5)); Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
            Color(*rgba("#ffffff")); Line(points=[x - r * .5, y + r * .7, x, y + r * .2, x + r * .4, y + r * .8], width=1.5)

    def ball_icon(self, x, y, r, spin):
        Color(0, 0, 0, .35); Ellipse(pos=(x - r + 1.5, y - r - 2), size=(2 * r, 2 * r))
        Color(1, 1, 1, 1); Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
        Color(*rgba("#172a20"))
        Ellipse(pos=(x - r * .35, y - r * .35), size=(r * .7, r * .7))
        for i in range(5):
            a = spin + i * math.tau / 5
            px, py = x + math.cos(a) * r * .68, y + math.sin(a) * r * .68
            Ellipse(pos=(px - r * .16, py - r * .16), size=(r * .32, r * .32))
        Color(*rgba("#163b25")); Line(circle=(x, y, r), width=1.2)

    def spinner(self, x, y, u):
        t = time.time()
        for i in range(8):
            a = t * 4 + i * math.tau / 8
            Color(*rgba(C["lime"], (i + 1) / 8))
            Ellipse(pos=(x + math.cos(a) * u - 3, y + math.sin(a) * u - 3), size=(6, 6))

    def draw_toasts(self):
        now = time.time()
        self.toasts = [t for t in self.toasts if now - t[2] < 2.4]
        for i, (s, col, at) in enumerate(self.toasts[-3:]):
            y = self.y + self.u * (5.6 + i * 1.6)
            self.text(self.center_x, y, s, self.u * .95, col, TITLE)

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
        if self.state in ("match", "search", "login") or self.toasts:
            self.redraw()

    def handle(self, msg):
        kind = msg.get("type")
        if kind == "match_start":
            self.match = msg
            self.state = "match"
            rival = msg["names"][1 - msg["side"]]
            self.toast(f"¡RIVAL ENCONTRADO! {rival}", C["lime"])
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
            self.play("goal")
        elif name in ("fire_start", "pausa_start", "magnet_start"):
            key = name.split("_")[0]
            self.play(key)
            label = {"fire": "FUEGO", "pausa": "PAUSA", "magnet": "CAMPO MAGNÉTICO"}[key]
            self.toast(f"{label} {'TUYO' if mine else 'DEL RIVAL'}", C["lime"] if mine else C["orange"])
        elif name == "keeper_stun":
            self.toast("¡ARQUERO ELECTROCUTADO!", C["sky"])
        elif name == "half_time":
            self.toast("SEGUNDO TIEMPO", C["gold"])
        elif name == "extra_time":
            self.toast("PRÓRROGA", C["gold"])
        elif name == "golden_goal":
            self.toast("GOL DE ORO", C["gold"])

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
            best = None
            for i in range(me * 6, me * 6 + 6):
                sx, sy = self.w2s(*bodies[i])
                d = math.hypot(sx - touch.x, sy - touch.y)
                rot, s, _, _ = self.view()
                if d < max(PR * s * 2.2, 34) and (best is None or d < best[0]):
                    best = (d, i, sx, sy)
            if best:
                self.drag = {"i": best[1], "sx": best[2], "sy": best[3], "cur": touch.pos}
        return True

    def on_touch_move(self, touch):
        if self.drag:
            self.drag["cur"] = touch.pos
        return True

    def on_touch_up(self, touch):
        if self.drag and self.state == "match":
            dx, dy = self.drag["sx"] - touch.x, self.drag["sy"] - touch.y
            wx, wy = self.s2w_delta(dx, dy)
            self.net.shoot(self.drag["i"] % 6, wx, wy)      # el servidor valida y simula
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
