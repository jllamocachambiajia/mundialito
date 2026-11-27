"""Partido autoritario: el servidor simula todo; los clientes solo envían intenciones."""
import math
import random
import uuid

from . import physics as P

HALF = 150.0                       # 45 min de juego = 2:30 reales (igual que v7)
EXTRA = 66.7                       # prórroga completa
GOLDEN = 60.0                      # gol de oro online (en lugar de penales)
SHOT_COOLDOWN = 1.0                # recarga independiente por equipo
KEEPER_COOLDOWN = 1.0              # recarga propia del arquero
FIRE_POWER, FIRE_TIME, FIRE_CD = 1.5, 2.0, 20.0
PAUSA_TIME, PAUSA_CD, PAUSA_OWN, PAUSA_RIVAL = 10.0, 60.0, 0.6, 0.0
MAG_TIME, MAG_CD, MAG_LOCK, MAG_RADIUS = 12.0, 30.0, 22.0, 2.0
MAG_RETURN, STUN_TIME, MAG_FIRE_PENALTY = 0.60, 5.0, 40.0


class Match:
    def __init__(self, mode, players, teams):
        self.id = uuid.uuid4().hex
        self.mode = mode                      # "amistoso" | "ranked"
        self.players = players                # [account_id_lado0, account_id_lado1]
        self.teams = teams                    # [pais0, pais1]
        self.score = [0, 0]
        self.t = 0.0                          # reloj de juego (no avanza durante gol)
        self.real = 0.0                       # segundos reales jugados (duración del fuego)
        self.phase = "first"
        self.events = []
        self.finished = False
        self.winner = None
        self.shot_ready = [0.0, 0.0]
        self.keeper_ready = [0.0, 0.0]
        self.fire = {"ready": [0.0, 0.0], "armed": [False, False], "shot": None}
        self.pausa = {"ready": [0.0, 0.0], "until": 0.0, "owner": None}
        self.mag = {"ready": [0.0, 0.0], "until": [0.0, 0.0], "locked": [0.0, 0.0]}
        self.stun = [0.0, 0.0]
        self.goal_freeze = 0.0
        self.kickoff = random.randint(0, 1)
        self.reset_positions()

    # ------------------------------------------------------------ estado
    def reset_positions(self):
        self.bodies = P.make_team(0) + P.make_team(1)
        self.ball = P.Body((P.FX0 + P.FX1) / 2, P.MY, P.BR, P.BM)
        self.all = self.bodies + [self.ball]
        self.kick_lock = True                 # solo el equipo que saca puede tirar

    def emit(self, name, **data):
        self.events.append({"name": name, **data})

    def clock_limit(self):
        return {"first": HALF, "second": 2 * HALF, "extra": 2 * HALF + EXTRA,
                "golden": 2 * HALF + EXTRA + GOLDEN}[self.phase]

    # ------------------------------------------------------------ entradas
    def shoot(self, side, idx, dx, dy):
        if self.finished or self.goal_freeze > 0 or not (0 <= idx < 6):
            return False
        if self.kick_lock and side != self.kickoff:
            return False
        if self.pausa_active() and self.pausa["owner"] != side:
            return False                      # rival congelado por PAUSA
        body = self.bodies[side * 6 + idx]
        now = self.t
        if body.keeper:
            if now < self.keeper_ready[side] or now < self.stun[side]:
                return False
        elif now < self.shot_ready[side]:
            return False
        if self.fire["shot"] is not None and self.fire["shot"]["team"] != side and self.fire["armed"][side]:
            return False
        d = math.hypot(dx, dy)
        if d < 4 or not math.isfinite(d):
            return False
        if d > P.MAX_DRAG:
            dx, dy = dx * P.MAX_DRAG / d, dy * P.MAX_DRAG / d
        k = P.POWER * (P.GK_POWER if body.keeper else 1.0)
        fire = self.fire["armed"][side] and not body.keeper and self.fire["shot"] is None
        if fire:
            k *= FIRE_POWER
            self.fire["armed"][side] = False
            self.fire["ready"][side] = now + FIRE_CD
            self.fire["shot"] = {"team": side, "body": idx, "start": self.real,
                                 "own_half": (body.x < (P.FX0 + P.FX1) / 2) == (side == 0)}
            self.emit("fire_start", team=side)
        body.vx, body.vy = dx * k, dy * k
        if body.keeper:
            self.keeper_ready[side] = now + KEEPER_COOLDOWN
        else:
            self.shot_ready[side] = now + SHOT_COOLDOWN
        self.kick_lock = False
        self.emit("shot", team=side, body=idx, fire=fire)
        return True

    def ability(self, side, name):
        now = self.t
        if self.finished:
            return False
        if name == "fire":
            if now >= self.fire["ready"][side] and self.fire["shot"] is None:
                self.fire["armed"][side] = True
                self.emit("fire_armed", team=side)
                return True
        elif name == "pausa":
            if now >= self.pausa["ready"][side] and not self.pausa_active():
                self.pausa.update(until=now + PAUSA_TIME, owner=side)
                self.pausa["ready"][side] = now + PAUSA_CD
                self.emit("pausa_start", team=side)
                return True
        elif name == "magnet":
            if now >= self.mag["ready"][side] and now >= self.mag["locked"][side]:
                self.mag["until"][side] = now + MAG_TIME
                self.mag["ready"][side] = now + MAG_CD
                self.mag["locked"][1 - side] = max(self.mag["locked"][1 - side], now + MAG_LOCK)
                self.emit("magnet_start", team=side)
                return True
        return False

    # ------------------------------------------------------------ reglas
    def pausa_active(self):
        return self.pausa["owner"] is not None and self.t < self.pausa["until"]

    def mag_active(self, side):
        return self.t < self.mag["until"][side]

    def _body_scale(self, b):
        if self.t < self.stun[b.team if b.team is not None else 0] and b.keeper:
            return 0.0
        if not self.pausa_active():
            return 1.0
        owner = self.pausa["owner"]
        if b.team is None or b.team == owner:
            return PAUSA_OWN
        return PAUSA_RIVAL

    def _policy(self, a, b):
        shot = self.fire["shot"]
        if shot is None:
            return True
        other = b if a is self.ball else a if b is self.ball else None
        if other is None:
            return True
        if not other.keeper:
            return False                      # el balón de fuego atraviesa a las fichas de campo
        if other.team == shot["team"]:
            return False
        return shot["own_half"]               # arquero rival solo bloquea tiros desde campo propio

    def _contact(self, a, b):
        shot = self.fire["shot"]
        if shot is not None and (a is self.ball or b is self.ball):
            k = b if a is self.ball else a
            if k.keeper and k.team != shot["team"]:
                self._end_fire("bloqueo")
        for side in (0, 1):
            if not self.mag_active(side):
                continue
            mine = a if a.team == side else b if b.team == side else None
            rival = b if mine is a else a
            if mine is None or rival.team is None or rival.team == side:
                continue
            if shot is not None and shot["team"] == rival.team:
                self.mag["until"][side] = self.t
                self.mag["ready"][side] = self.t + MAG_FIRE_PENALTY
                self.emit("magnet_broken", team=side)
                continue
            rival.vx, rival.vy = -rival.vx * MAG_RETURN - (mine.x - rival.x) * 0.02, \
                                 -rival.vy * MAG_RETURN - (mine.y - rival.y) * 0.02
            if rival.keeper and self.t >= self.stun[rival.team]:
                self.stun[rival.team] = self.t + STUN_TIME
                self.emit("keeper_stun", team=rival.team)

    def _end_fire(self, why):
        if self.fire["shot"] is not None:
            self.emit("fire_end", team=self.fire["shot"]["team"], why=why)
            self.fire["shot"] = None

    def _scale(self):
        return 0.5 if self.fire["shot"] is not None else 1.0

    # ------------------------------------------------------------ tick
    def update(self, dt):
        if self.finished:
            return
        if self.goal_freeze > 0:
            self.goal_freeze -= dt
            if self.goal_freeze <= 0:
                self.reset_positions()
            return
        self.real += dt
        self.t += dt * self._scale()
        if self.fire["shot"] is not None and self.real - self.fire["shot"]["start"] >= FIRE_TIME:
            self._end_fire("tiempo")
        if self.pausa["owner"] is not None and not self.pausa_active():
            self.emit("pausa_end", team=self.pausa["owner"])
            self.pausa["owner"] = None
        frames = dt * 60.0
        P.step(self.all, self.ball, scale=frames * self._scale(), collision_policy=self._policy,
               body_scale=self._body_scale, on_contact=self._contact)
        scorer = P.ball_in_goal(self.ball)
        if scorer is not None:
            self.score[scorer] += 1
            self._end_fire("gol")
            self.kickoff = 1 - scorer
            self.goal_freeze = 2.5
            self.emit("goal", team=scorer, score=list(self.score))
            if self.phase == "golden":
                self._finish(scorer)
            return
        if self.t >= self.clock_limit():
            self._next_phase()

    def _next_phase(self):
        tie = self.score[0] == self.score[1]
        if self.phase == "first":
            self.phase = "second"; self.kickoff = 1 - self.kickoff
            self.reset_positions(); self.emit("half_time")
        elif not tie:
            self._finish(0 if self.score[0] > self.score[1] else 1)
        elif self.phase == "second":
            self.phase = "extra"; self.reset_positions(); self.emit("extra_time")
        elif self.phase == "extra":
            self.phase = "golden"; self.reset_positions(); self.emit("golden_goal")
        else:
            self._finish(None)

    def _finish(self, winner):
        self.finished = True
        self.winner = winner
        self.emit("match_end", winner=winner, score=list(self.score))

    def forfeit(self, side):
        if not self.finished:
            self._finish(1 - side)

    def snapshot(self):
        r = lambda v: round(v, 1)
        t = self.t
        return {
            "type": "state", "t": r(t), "phase": self.phase, "score": self.score,
            "bodies": [[r(b.x), r(b.y)] for b in self.bodies],
            "ball": [r(self.ball.x), r(self.ball.y)],
            "kick_lock": self.kick_lock, "kickoff": self.kickoff,
            "cd": {
                "shot": [max(0, r(x - t)) for x in self.shot_ready],
                "keeper": [max(0, r(x - t)) for x in self.keeper_ready],
                "fire": [max(0, r(x - t)) for x in self.fire["ready"]],
                "pausa": [max(0, r(x - t)) for x in self.pausa["ready"]],
                "magnet": [max(0, r(max(a, b) - t)) for a, b in zip(self.mag["ready"], self.mag["locked"])],
            },
            "fx": {
                "fire": self.fire["shot"]["team"] if self.fire["shot"] else None,
                "fire_armed": self.fire["armed"],
                "pausa": self.pausa["owner"] if self.pausa_active() else None,
                "magnet": [self.mag_active(0), self.mag_active(1)],
                "stun": [t < self.stun[0], t < self.stun[1]],
                # v2: solo información para dibujar (no cambia la física)
                "fire_body": self.fire["shot"]["body"] if self.fire["shot"] else None,
                "pausa_left": max(0, r(self.pausa["until"] - t)) if self.pausa_active() else 0,
            },
        }

    def pop_events(self):
        ev, self.events = self.events, []
        return ev
