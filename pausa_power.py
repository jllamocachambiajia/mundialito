"""PAUSA special ability: 15 % simulation speed for 10 s, for player and CPU.

Only the physics multiplier is exposed; UI, buttons, sounds and recharge clocks
keep running on the pause-aware real clock (vnow), never on simulated time.
"""
import math
import random
OWNER_SPEED = 0.6            # Velocidad suave para el que USÓ la pausa
RIVAL_SPEED = 0.0            # Velocidad del rival (completamente quieto)
SPEED = 0.15                 # multiplicador de simulación durante PAUSA
DURATION = 10.0              # segundos reales (respetan el botón de pausa del juego)
PLAYER_RECHARGE = 60.0       # jugador humano, cualquier ronda
AI_RECHARGE = 60.0           # CPU en dificultad normal
AI_FURY_RECHARGE = {2: 50.0, 3: 40.0}   # MODO FURIA: semifinal / final
PARTICLES = 90


class PausaState:
    def __init__(self):
        self.ready_at = [0.0, 0.0]
        self.until = None
        self.owner = None

    def active(self, now):
        return self.until is not None and now < self.until

    def available(self, team, now):
        return now >= self.ready_at[team] and not self.active(now)

    def activate(self, team, now, recharge):
        if not self.available(team, now):
            return False
        self.owner = team
        self.until = now + DURATION
        self.ready_at[team] = now + recharge
        return True

    def expire(self, now):
        if self.until is not None and now >= self.until:
            self.finish()
            return True
        return False

    def finish(self):
        """Single safe exit: speed always comes back to 100 %."""
        self.until = None
        self.owner = None

    def scale(self, now):
        self.expire(now)
        return SPEED if self.active(now) else 1.0
        def team_scale(self, team, now):
        """Retorna la velocidad según si el equipo es el dueño de la pausa o el rival."""
        self.expire(now)
        if self.active(now):
            return OWNER_SPEED if self.owner == team else RIVAL_SPEED
        return 1.0
    


def combined_scale(*multipliers):
    """Slow-motion effects never multiply: the lowest active multiplier wins."""
    return min([1.0] + [m for m in multipliers if m is not None])


class PausaAbility:
    def pausa_reset(self):
        self.pausa = PausaState()
        self.pausa_pressed = False
        self.pausa_press_started = 0.0
        self.pausa_particles = []
        self.pausa_next_ai_check = 0.0

    def pausa_recharge(self, team):
        if team == 0:
            return PLAYER_RECHARGE
        if self.ai_hard():
            return AI_FURY_RECHARGE.get(self.round, AI_RECHARGE)
        return AI_RECHARGE

    def pausa_activate(self, team):
        from main import vnow
        now = vnow()
        if self.state != 'match' or not self.pausa.activate(team, now, self.pausa_recharge(team)):
            return False
        self.snd.play('pausa_inicio', dur=.05)        # mismo instante de la activación
        self.pausa_spawn()
        if team == 1:
            self.flash('¡PAUSA RIVAL!', 1.2)
        return True

    def pausa_scale(self):
        from main import vnow
        if self.state != 'match':
            return 1.0
        return self.pausa.scale(vnow())

    def pausa_press(self, x, y):
        from main import vnow
        x0, y0, x1, y1 = self.ability_rect(1)
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        if self.drag is None and self.phase == 'play' and self.pausa.available(0, vnow()):
            self.pausa_pressed = True
            self.pausa_press_started = vnow()
        return True

    def pausa_release(self, x, y):
        if not self.pausa_pressed:
            return False
        self.pausa_pressed = False
        x0, y0, x1, y1 = self.ability_rect(1)
        if self.phase == 'play' and x0 <= x <= x1 and y0 <= y <= y1:
            self.pausa_activate(0)
        return True

    def draw_pausa_button(self):
        from main import vnow
        now = vnow()
        self.draw_ability_icon(1, 'pausa.png', self.pausa_pressed, self.pausa_press_started,
                               not self.pausa.available(0, now), self.pausa.ready_at[0]-now,
                               self.pausa.active(now) and self.pausa.owner == 0, '#ff5cc8')

    def pausa_ai(self):
        """CPU uses PAUSA only on real attacking/defending situations."""
        from main import vnow, FX0, FX1, MY, GY0, GY1
        now = vnow()
        if self.state != 'match' or self.phase != 'play' or now < self.pausa_next_ai_check:
            return False
        self.pausa_next_ai_check = now + .8
        if not self.pausa.available(1, now) or self.kick_team is not None:
            return False
        hard = self.ai_hard()
        trailing = self.score[1] < self.score[0]
        if not (hard or trailing):
            return False
        b = self.ball
        field = [p for p in self.bodies if p.team == 1 and not p.keeper]
        near = min((math.hypot(p.x-b.x, p.y-b.y) for p in field), default=999)
        attack = b.x < FX0 + (FX1-FX0)*.38 and GY0-160 < b.y < GY1+160 and near < 170
        danger = b.x > FX1 - (FX1-FX0)*.3 and b.vx > 3 and abs(b.y-MY) < 200
        chance = .65 if hard else .3
        if (attack or danger) and random.random() < chance:
            return self.pausa_activate(1)
        return False

    def pausa_spawn(self):
        rng = random.Random()
        self.pausa_particles = [dict(x=rng.uniform(0, 1), y=rng.uniform(0, 1),
                                     vx=rng.uniform(-.012, .012), vy=rng.uniform(-.03, -.006),
                                     r=rng.uniform(.7, 2.1), ph=rng.uniform(0, math.tau),
                                     c=rng.choice(('#7df9ff', '#c58bff', '#ffffff', '#ff7ad9')))
                                for _ in range(PARTICLES)]

    def draw_pausa_effect(self, dt):
        from main import vnow
        now = vnow()
        if not self.pausa.active(now):
            self.pausa_particles = []
            return
        if not self.pausa_particles:
            self.pausa_spawn()
        cv, cw, ch, u = self.cv, self.cw, self.ch, self.u
        left = self.pausa.until - now
        fade = min(1, (10 - left) / .4, left / .6)
        cv.create_rectangle(0, 0, cw, ch, fill='#3a1aff', width=0, alpha=.10 * fade)
        for p in self.pausa_particles:
            p['x'] = (p['x'] + p['vx'] * dt) % 1.0
            p['y'] = (p['y'] + p['vy'] * dt) % 1.0
            tw = .55 + .45 * math.sin(now * 3 + p['ph'])
            r = p['r'] * u * .32 * (.7 + .5 * tw)
            x, y = p['x'] * cw, p['y'] * ch
            cv.create_oval(x-r*2.2, y-r*2.2, x+r*2.2, y+r*2.2, fill=p['c'], width=0, alpha=.12 * fade * tw)
            cv.create_oval(x-r, y-r, x+r, y+r, fill=p['c'], width=0, alpha=.55 * fade * tw)
        cx, cy, rr = cw - u * 2.2, self.hud + u * 2.2, u * 1.4
        cv.create_arc(cx-rr, cy-rr, cx+rr, cy+rr, start=90, extent=360*left/10, style='arc',
                      outline='#7df9ff', width=max(2, u*.3))
        cv.create_text(cx, cy, text=str(math.ceil(left)), fill='#ffffff', font=self.F(.9))
