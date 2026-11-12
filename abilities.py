"""Four-slot special ability bar: shared layout, press feedback and info badges."""
import math

SLOTS = 4
DISC_DIAMETERS = 4            # cada botón mide 4 diámetros de chapita
INFO_COLOR = '#2ec5ff'
INFO_DOWN = '#1a8fbd'


def ability_layout(cw, ch, hud, safe, rot, rw, rh, pr):
    """Solve button size and bar height together: the bar shrinks the pitch,
    so the size is 4 x the disc diameter of the FINAL pitch scale."""
    w, h = cw, ch - hud
    size = 2 * pr * DISC_DIAMETERS * min(w / (rh if rot else rw), h / (rw if rot else rh))
    pad = 0
    for _ in range(30):
        pad = size + max(14.0, size * .2)
        hh = max(10.0, h - pad - safe)
        s = min(w / rh, hh / rw) if rot else min(w / rw, hh / rh)
        size = min(2 * pr * DISC_DIAMETERS * s, cw / SLOTS - 4)
    return size, pad


def fire_info():
    from fire import POWER_FACTOR, TIME_FACTOR, MAX_DURATION, PLAYER_RECHARGE
    return ('FUEGO', [
        f'Potencia máx.: {POWER_FACTOR*100:.0f} %',
        f'Velocidad del juego: {TIME_FACTOR*100:.0f} %',
        f'Reducción: {(1-TIME_FACTOR)*100:.0f} %',
        f'Duración máx.: {MAX_DURATION:g} s tras el tiro',
        f'Recarga: {PLAYER_RECHARGE:g} s',
        'Atraviesa chapitas (arquero: según mitad)'])


def pausa_info():
    from pausa_power import SPEED, DURATION, PLAYER_RECHARGE
    return ('PAUSA', [
        f'Velocidad del juego: {SPEED*100:.0f} %',
        f'Reducción: {(1-SPEED)*100:.0f} %',
        f'Duración: {DURATION:g} s',
        f'Recarga: {PLAYER_RECHARGE:g} s'])


INFO = {0: fire_info, 1: pausa_info}


class AbilityBar:
    def ability_reset(self):
        self.info_open = None
        self.info_pressed = None

    def ability_rect(self, slot):
        size = getattr(self, 'ability_size', 0) or min(self.cw / 5.0, self.ctrl_pad - 10)
        cx = self.cw * (slot + .5) / SLOTS
        cy = self.ch - getattr(self, 'safe_bottom', 0) - self.ctrl_pad / 2
        return cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2

    def info_circle(self, slot):
        x0, y0, x1, y1 = self.ability_rect(slot)
        r = max(9.0, (x1 - x0) * .15)
        return x0 + r * .55, y0 + r * .55, r

    def info_hit(self, slot, x, y):
        cx, cy, r = self.info_circle(slot)
        return math.hypot(x - cx, y - cy) <= r * 1.25

    def ability_press(self, x, y):
        """Info badges first so they never trigger an ability."""
        for slot in INFO:
            if self.info_hit(slot, x, y):
                self.info_pressed = slot
                return True
        if self.info_open is not None:
            self.info_open = None
        return self.fire_press(x, y) or self.pausa_press(x, y)

    def ability_release(self, x, y):
        if self.info_pressed is not None:
            slot, self.info_pressed = self.info_pressed, None
            if self.info_hit(slot, x, y):
                self.info_open = None if self.info_open == slot else slot
            return True
        return self.fire_release(x, y) or self.pausa_release(x, y)

    def ability_cooldown(self, slot):
        from fire import PLAYER_RECHARGE as FIRE
        from pausa_power import PLAYER_RECHARGE as PAUSA
        return {0: FIRE, 1: PAUSA}.get(slot)

    def draw_ability_icon(self, slot, image, pressed, press_started, unavailable, remaining, active, ring):
        from main import vnow
        x0, y0, x1, y1 = self.ability_rect(slot)
        size = x1 - x0
        down = min(1, max(0, (vnow() - press_started) / .08)) if pressed else 0
        draw = size * (1 - .08 * down)
        oy = down * 3
        self.visual.png(image, (x0 + x1 - draw) / 2, y0 + (size - draw) / 2 + oy, draw, draw, slot=image + '-button')
        if unavailable or down:
            self.cv.create_oval(x0, y0 + oy, x1, y1 + oy, fill='#071b13', width=0,
                                alpha=.45 if unavailable and not active else .25)
        if active:
            self.cv.create_oval(x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline=ring, width=4)
        elif remaining > 0:
            cooldown = self.ability_cooldown(slot)
            frac = max(0, min(1, remaining / cooldown)) if cooldown else 0
            self.cv.create_arc(x0 + 3, y0 + 3, x1 - 3, y1 - 3, start=90, extent=-360 * frac,
                               style='arc', outline='#ffffff', width=max(2, size * .05))
            self.cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=str(math.ceil(remaining)),
                                fill='#ffffff', font=self.F(1.3))

    def draw_abilities(self):
        for slot in range(2, SLOTS):                # reservadas, aún sin habilidad
            x0, y0, x1, y1 = self.ability_rect(slot)
            r = (x1 - x0) * .32
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline='#709582', width=1)
        self.draw_fire_button()
        self.draw_pausa_button()
        for slot in INFO:
            cx, cy, r = self.info_circle(slot)
            down = self.info_pressed == slot
            self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=INFO_DOWN if down else INFO_COLOR,
                                outline='#ffffff', width=2)
            self.cv.create_text(cx, cy, text='i', fill='#ffffff', font=self.F(max(.7, r / self.u * .9)))
        if self.info_open is not None:
            self.draw_info_panel(self.info_open)

    def draw_info_panel(self, slot):
        title, lines = INFO[slot]()
        u, cw = self.u, self.cw
        bx0, by0, bx1, by1 = self.ability_rect(slot)
        width = min(cw * .92, u * 22)
        line_h = u * 1.25
        height = line_h * (len(lines) + 1.3) + u * .6
        x0 = min(max(u * .4, (bx0 + bx1) / 2 - width / 2), cw - width - u * .4)
        y1 = by0 - u * .5
        y0 = max(self.hud, y1 - height)
        self.cv.create_rectangle(x0, y0, x0 + width, y1, fill='#06283a', outline=INFO_COLOR, width=2, alpha=.93)
        self.cv.create_text(x0 + u * .7, y0 + line_h * .75, text=title, fill=INFO_COLOR, font=self.F(1.0), anchor='w')
        for i, line in enumerate(lines):
            self.cv.create_text(x0 + u * .7, y0 + line_h * (1.75 + i), text=line, fill='#ffffff',
                                font=self.F(.78, False), anchor='w')
