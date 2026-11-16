
"""Campo magnético para Mundialito / Kivy.

No importa main.py: utiliza el reloj del Game mediante magnetic_now().
No cambia radios físicos permanentes, tiempos de disparo ni penales.
"""
import math
import logging
import wave

DURATION = 12.0
RECHARGE = 30.0
LOCK_OTHER = 22.0  # rival espera: 12 s de campo + 10 s
RADIUS_FACTOR = 2.0
RETURN_FACTOR = 0.60
STUN_DURATION = 5.0
FIRE_CONTACT_FACTOR = 0.50
FIRE_PENALTY = 40.0
START_VOLUME = 0.65
BACKGROUND_VOLUME = 0.12
END_VOLUME = 0.55
BACKGROUND_FADE = 2.0

LOG = logging.getLogger(__name__)


def magnetic_info():
    return ('CAMPO MAGNÉTICO', [
        'Protege al equipo y al arquero',
        'Protege también la pelota; repele rivales',
        'Devuelve el 60 % del impacto rival',
        'Electrocuta al arquero rival durante 5 s',
        'Fuego contra el campo: 50 %, recarga 40 s',
        'Radio: 2 veces el de cada ficha',
        'Duración: 12 s',
        'Recarga: 30 s desde la activación',
    ])


class MagneticState:
    def __init__(self):
        self.ready_at = [0.0, 0.0]      # recarga propia (30 s desde que se activa)
        self.until = [0.0, 0.0]         # fin del campo propio (12 s)
        self.locked_until = [0.0, 0.0]  # bloqueo del otro equipo (22 s)

    def active(self, team, now):
        return team in (0, 1) and now < self.until[team]

    def available(self, team, now):
        return (team in (0, 1)
                and now >= self.ready_at[team]
                and now >= self.locked_until[team]
                and not self.active(team, now))

    def activate(self, team, now):
        if not self.available(team, now):
            return False
        other = 1 - team
        self.until[team] = now + DURATION
        self.ready_at[team] = now + RECHARGE
        # El otro equipo no puede usarlo hasta 12 s de campo + 10 s de espera.
        self.locked_until[other] = now + LOCK_OTHER
        return True

    def finish(self):
        # Conserva las recargas; el reinicio del partido crea otro estado.
        self.until = [0.0, 0.0]
        self.locked_until = [0.0, 0.0]


class MagneticAudio:
    """Tres canales propios; no interrumpe música ni efectos del partido.

    Sin callbacks diferidos: reiniciar o pausar no deja sonidos pendientes.
    Cada equipo tiene su propia instancia.
    """
    def __init__(self):
        self.sounds = [None, None, None]
        self.lengths = [2.694, 10.008, 2.415]
        self.loaded = False
        self.started = None
        self.phase = None
        self.bg_started = False
        self.suspended = False
        self.muted = False

    @staticmethod
    def _call(sound, method, *args):
        if sound is None:
            return
        try:
            getattr(sound, method)(*args)
        except Exception as exc:
            LOG.debug('Audio campo: %s: %s', method, exc)

    @staticmethod
    def _volume(sound, volume):
        if sound is not None:
            try:
                sound.volume = max(0.0, min(1.0, volume))
            except Exception as exc:
                LOG.debug('Volumen campo: %s', exc)

    def prepare(self):
        if self.loaded:
            return
        self.loaded = True
        try:
            from kivy.core.audio import SoundLoader
            from presentation import asset
        except ImportError as exc:
            LOG.warning('Audio del campo no disponible: %s', exc)
            return

        for i, name in enumerate(('campo.wav', 'campo2.wav',
                                  'campo3.wav')):
            path = asset('sounds', 'effects', name)
            try:
                with wave.open(path, 'rb') as wav:
                    self.lengths[i] = (
                        wav.getnframes() / wav.getframerate())
            except (OSError, EOFError, wave.Error):
                pass
            try:
                sound = SoundLoader.load(path)
                if sound is not None:
                    sound.loop = (i == 1)
                    self.sounds[i] = sound
            except Exception as exc:
                LOG.warning('No se pudo cargar %s: %s', name, exc)

    def _play(self, index, volume, offset=0.0):
        sound = self.sounds[index]
        self._volume(sound, volume)
        self._call(sound, 'play')
        if offset > 0.001:
            self._call(sound, 'seek', offset)

    def _silence(self):
        for sound in self.sounds:
            self._call(sound, 'stop')
        self.phase = None
        self.bg_started = False

    def begin(self, now, enabled=True):
        self.stop()
        self.prepare()
        self.started = now
        self.suspended = False
        self.muted = False
        self.update(now, enabled)

    def update(self, now, enabled=True):
        if self.started is None or self.suspended:
            return
        elapsed = max(0.0, now - self.started)
        if elapsed >= DURATION:
            self.stop()
            return
        if not enabled:
            if not self.muted:
                self._silence()
            self.muted = True
            return
        self.muted = False

        # El fondo acompaña toda la habilidad, sin reiniciar la música.
        fade = min(1.0, (DURATION - elapsed) / BACKGROUND_FADE)
        background_volume = BACKGROUND_VOLUME * fade
        if not self.bg_started:
            length = max(0.01, self.lengths[1])
            self._play(1, background_volume, elapsed % length)
            self.bg_started = True
        self._volume(self.sounds[1], background_volume)

        first_length = max(0.01, self.lengths[0])
        last_length = max(0.01, self.lengths[2])
        if elapsed < first_length:
            phase = 'inicio'
            index, offset, volume = 0, elapsed, START_VOLUME
        elif elapsed < first_length + last_length:
            phase = 'salida'
            offset = elapsed - first_length
            index = 2
            volume = END_VOLUME * (1.0 - offset / last_length)
        else:
            phase = 'fondo'
            index, offset, volume = None, 0.0, 0.0

        if phase != self.phase:
            self._call(self.sounds[0], 'stop')
            self._call(self.sounds[2], 'stop')
            self.phase = phase
            if index is not None:
                self._play(index, volume, offset)
        elif index is not None:
            self._volume(self.sounds[index], volume)

    def pause(self):
        self.suspended = True
        self._silence()

    def resume(self, now, enabled=True):
        self.suspended = False
        self.update(now, enabled)

    def stop(self):
        self._silence()
        self.started = None
        self.suspended = False
        self.muted = False


class MagneticAbility:
    def magnetic_reset(self):
        # También funciona en __init__, antes de crear self.snd.
        for audio in getattr(self, 'magnetic_audio', []):
            audio.stop()
        self.magnetic = MagneticState()
        self.magnetic_audio = [MagneticAudio(), MagneticAudio()]
        self.magnetic_pressed = False
        self.magnetic_press_started = 0.0
        self.magnetic_next_ai = 0.0
        for audio in getattr(self, 'magnetic_stun_audio', []):
            audio.stop()
        self.magnetic_stuns = {}
        self.magnetic_stun_audio = [ElectricAudio(), ElectricAudio()]
        self.magnetic_fire_penalty = [0.0, 0.0]
        self.magnetic_fire_override = None

    def magnetic_now(self):
        # Reloj pausa-aware del juego (main.py).
        from main import vnow
        return vnow()

    def magnetic_prepare(self):
        for audio in self.magnetic_audio:
            audio.prepare()

    def magnetic_finish(self):
        self.magnetic.finish()
        self.magnetic_stuns.clear()
        self.magnetic_fire_override = None
        for audio in self.magnetic_stun_audio:
            audio.stop()
        self.magnetic_pressed = False
        for audio in self.magnetic_audio:
            audio.stop()

    def magnetic_ball_team(self, now=None):
        """Equipo cuyo campo protege al balón (None si no hay campo activo)."""
        if now is None:
            now = self.magnetic_now()
        for team in (0, 1):
            if self.magnetic.active(team, now):
                return team
        return None

    def magnetic_shield_team(self, body, now=None):
        """Equipo que protege a este cuerpo (None si no está protegido)."""
        if now is None:
            now = self.magnetic_now()
        if body is getattr(self, 'ball', None):
            return self.magnetic_ball_team(now)
        return body.team if self.magnetic.active(body.team, now) else None

    def magnetic_active_body(self, body, now=None):
        if getattr(self, 'state', None) != 'match' or body is None:
            return False
        return self.magnetic_shield_team(body, now) is not None

    def magnetic_activate(self, team):
        if (getattr(self, 'state', None) != 'match'
                or getattr(self, 'phase', None) != 'play'
                or getattr(self, 'paused', False)
                or team not in (0, 1)):
            return False
        now = self.magnetic_now()
        if not self.magnetic.activate(team, now):
            return False
        enabled = getattr(getattr(self, 'snd', None), 'on', True)
        self.magnetic_audio[team].begin(now, enabled)
        if team == 1:
            self.flash('¡CAMPO MAGNÉTICO RIVAL!', 1.2)
        return True

    def magnetic_press(self, x, y):
        x0, y0, x1, y1 = self.ability_rect(2)
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        if (self.state == 'match' and self.phase == 'play'
                and not getattr(self, 'paused', False)
                and self.drag is None
                and self.magnetic.available(0, self.magnetic_now())):
            self.magnetic_pressed = True
            self.magnetic_press_started = self.magnetic_now()
        return True

    def magnetic_release(self, x, y):
        if not self.magnetic_pressed:
            return False
        self.magnetic_pressed = False
        x0, y0, x1, y1 = self.ability_rect(2)
        if x0 <= x <= x1 and y0 <= y <= y1:
            self.magnetic_activate(0)
        return True

    def magnetic_update(self):
        now = self.magnetic_now()
        self.fire.expire(now)
        if not self.fire.shots:
            self.magnetic_fire_override = None
        for keeper, effect in list(self.magnetic_stuns.items()):
            if now >= effect["until"] or keeper not in self.bodies:
                self.magnetic_stun_audio[keeper.team].stop()
                del self.magnetic_stuns[keeper]
            else:
                keeper.x, keeper.y = effect["position"]
                keeper.vx = keeper.vy = 0.0
                self.keeper_limit(keeper)
                self.magnetic_stun_audio[keeper.team].update(now, getattr(self.snd, "on", True))
        enabled = getattr(getattr(self, 'snd', None), 'on', True)
        for team, audio in enumerate(self.magnetic_audio):
            if self.magnetic.active(team, now):
                audio.update(now, enabled)
            else:
                audio.stop()

    def magnetic_pause(self):
        self.magnetic_pressed = False
        for audio in self.magnetic_audio + self.magnetic_stun_audio:
            audio.pause()

    def magnetic_resume(self):
        now = self.magnetic_now()
        enabled = getattr(getattr(self, 'snd', None), 'on', True)
        for keeper in self.magnetic_stuns:
            if self.magnetic_stunned(keeper):
                self.magnetic_stun_audio[keeper.team].resume(now, enabled)
        for team, audio in enumerate(self.magnetic_audio):
            if self.magnetic.active(team, now):
                audio.resume(now, enabled)
            else:
                audio.stop()

    def magnetic_ai(self):
        # Una decisión periódica; no reemplaza ai_shoot ni ai_keeper.
        if (self.state != 'match' or self.phase != 'play'
                or getattr(self, 'paused', False)):
            return False
        now = self.magnetic_now()
        if now < self.magnetic_next_ai:
            return False
        self.magnetic_next_ai = now + 0.8
        if (self.kick_team is not None
                or not self.magnetic.available(1, now)):
            return False

        plan = self.magnetic_attack_plan()
        if plan is not None:
            return self.magnetic_activate(1)
        return False

    def magnetic_attack_plan(self):
        """Validate the actual disc-to-ball direction; reuse prediction and goal bounds."""
        from main import FX0, FY0, FY1, GY0, GY1, BR, MAX_DRAG, POWER, PLAYER_FRICTION, FRICTION
        ball = self.ball
        if ball is None or self.held is not None:
            return None
        cap = MAX_DRAG * POWER
        keeper = next((q for q in self.bodies if q.team == 0 and q.keeper), None)
        plans = []
        for disc in self.bodies:
            if disc.team != 1 or disc.keeper:
                continue
            bx, by = self.predict(ball, min(14, math.hypot(ball.x-disc.x, ball.y-disc.y)/cap))
            dx, dy = bx-disc.x, by-disc.y
            distance = math.hypot(dx, dy)
            if distance < 1 or distance > 300 or dx >= -distance*.65:
                continue
            gy = by + dy/dx*(FX0-bx)
            if not GY0+BR < gy < GY1-BR:
                continue
            if not self.lane_free(disc.x, disc.y, bx, by, 1):
                continue
            speed = max(0, cap-distance*(1-PLAYER_FRICTION)) * 1.44
            if speed/(1-FRICTION) < math.hypot(FX0-bx, gy-by)*1.1:
                continue
            separation = abs(gy-keeper.y) if keeper else 70
            score = distance-min(separation,100)*.3
            plans.append((score, disc, dx/distance*cap, dy/distance*cap))
        return min(plans, key=lambda item:item[0]) if plans else None

    def magnetic_attack(self):
        now = self.magnetic_now()
        if not self.magnetic.active(1, now) or not self.can_shoot(1, now) or now < self.ai_at:
            return False
        plan = self.magnetic_attack_plan()
        if plan is None:
            return False
        _, disc, vx, vy = plan
        self.shoot(disc, vx, vy)
        return True

    def magnetic_stunned(self, body):
        effect = getattr(self, 'magnetic_stuns', {}).get(body)
        return (getattr(self, 'state', None) == 'match' and effect is not None
                and self.magnetic_now() < effect['until'])

    def magnetic_body_scale(self, body):
        return 0.0 if self.magnetic_stunned(body) else self.pausa_body_scale(body)

    def magnetic_electrocute(self, keeper):
        if self.magnetic_stunned(keeper):
            return
        now = self.magnetic_now()
        self.keeper_limit(keeper)
        keeper.vx = keeper.vy = 0.0
        self.magnetic_stuns[keeper] = dict(started=now, until=now+STUN_DURATION,
                                          position=(keeper.x, keeper.y))
        if self.drag is keeper:
            self.drag = None
        if self.pending is not None and self.pending[0] is keeper:
            self.pending = None
        if getattr(self, 'held', None) is keeper:
            self.held = None
        if keeper.team == 0:
            self.gk_mode = False
            self.gk_released_at = None
        if getattr(self, 'dash', None) and self.dash['k'] is keeper:
            self.dash = None
        self.magnetic_stun_audio[keeper.team].begin(now, getattr(self.snd, 'on', True))

    def magnetic_fire_contact(self, a, b, now):
        """Only the selected launching disc may breach a protected ball, once."""
        ball = self.ball
        disc = b if a is ball else a if b is ball else None
        if disc is None:
            return False
        shot = self.fire.selected(disc)
        if not shot or shot['phase'] != 'launch':
            return False
        owner = self.magnetic_ball_team(now)
        if owner is None or owner == disc.team:
            return False
        dx, dy = ball.x-disc.x, ball.y-disc.y
        distance = math.hypot(dx, dy)
        if not 0 < distance < ball.r+disc.r:
            return False
        if (disc.vx-ball.vx)*dx+(disc.vy-ball.vy)*dy <= 0:
            return False
        # Reuse the existing transfer, then reduce that shot, not normal POWER.
        launched_at = shot['started']
        self.fire_collision(a, b)
        if shot['phase'] != 'flight':
            return False
        ball.vx *= FIRE_CONTACT_FACTOR
        ball.vy *= FIRE_CONTACT_FACTOR
        cap = math.hypot(*shot['velocity'])*1.44*FIRE_CONTACT_FACTOR
        self.magnetic_fire_override = dict(shot=shot, owner=owner, cap=cap)
        deadline = launched_at+FIRE_PENALTY
        self.fire.ready_at[disc.team] = deadline
        self.magnetic_fire_penalty[disc.team] = deadline
        return True

    def magnetic_repel(self, guard, free):
        """Return 60% of inward impact; moving guards push through ordinary contact.
        Absolute normal speed is bounded by the largest pre-contact normal speed,
        so repeated overlaps cannot pump energy into the simulation.
        """
        dx, dy = free.x - guard.x, free.y - guard.y
        minimum = guard.r * RADIUS_FACTOR + free.r
        distance = math.hypot(dx, dy)
        if distance >= minimum:
            return False
        if distance > 1e-6:
            nx, ny = dx / distance, dy / distance
        else:
            nx, ny = 1.0, 0.0
        free.x = guard.x + nx * (minimum + 0.001)
        free.y = guard.y + ny * (minimum + 0.001)
        incoming = free.vx*nx+free.vy*ny
        pushing = guard.vx*nx+guard.vy*ny
        if incoming-pushing < 0:
            returned = RETURN_FACTOR*max(0.0, -incoming)
            outgoing = max(returned, pushing, 0.0)
            outgoing = min(outgoing, max(abs(incoming), abs(pushing)))
            free.vx += (outgoing-incoming)*nx
            free.vy += (outgoing-incoming)*ny
        if free.keeper:
            self.keeper_limit(free)
            if guard is self.ball:
                self.magnetic_electrocute(free)
        return True

    def magnetic_collision(self, a, b):
        """False: la pareja la resuelve el campo. True: choque normal."""
        if self.state != 'match':
            return True
        now = self.magnetic_now()
        ball = self.ball
        ta = self.magnetic_shield_team(a, now)
        tb = self.magnetic_shield_team(b, now)
        if ta is None and tb is None:
            return True
        if ta is not None and ta == tb:
            return True                 # mismo equipo: pase y tiro normales
        if ta is not None and tb is not None:
            # Campos de equipos distintos: manda el campo del balón.
            guard, free = (a, b) if (a is ball or b is not ball) else (b, a)
        elif ta is not None:
            guard, free = a, b
        else:
            guard, free = b, a
        self.magnetic_repel(guard, free)
        return False

    def match_collision(self, a, b):
        if self.state != 'match':
            return True
        now = self.magnetic_now()
        self.fire.expire(now)
        # Stunned keepers neither block nor transmit impulses, even after expiry.
        if self.magnetic_stunned(a) or self.magnetic_stunned(b):
            return False
        if self.magnetic_fire_contact(a, b, now):
            return False
        # Permit ONLY that selected launch to cross the outer shield and reach
        # the real ball. A miss never acquires an override or a penalty.
        other = b if a is self.ball else a if b is self.ball else None
        if other is not None:
            launch = self.fire.selected(other)
            owner = self.magnetic_ball_team(now)
            if launch and launch['phase'] == 'launch' and owner is not None and owner != other.team:
                return True
        exception = self.magnetic_fire_override
        if exception and any(shot is exception['shot'] for shot in self.fire.shots.values()):
            other = b if a is self.ball else a if b is self.ball else None
            if other is not None and other.team == exception['owner']:
                from main import collide
                collide(a, b)
                speed = self.ball.speed()
                if speed > exception['cap'] and speed > 0:
                    self.ball.vx *= exception['cap']/speed
                    self.ball.vy *= exception['cap']/speed
                return False
        if not self.magnetic_collision(a, b):
            return False
        return self.fire_collision(a, b)

    def draw_magnetic_fields(self):
        if self.state != 'match':
            return
        now = self.magnetic_now()
        for body in self.bodies:
            team = self.magnetic_shield_team(body, now)
            if team is None:
                continue
            x, y = self.to_s(body.x, body.y)
            radius = body.r * self.s * RADIUS_FACTOR
            color = '#35eaff' if team == 0 else '#ff65b5'
            alpha = 0.07 + 0.03 * math.sin(now * 5.0)
            self.cv.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=color, outline=color,
                width=max(1.5, radius * 0.05), alpha=alpha)
            self.cv.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                outline=color, width=max(1.5, radius * 0.04))
            # Puntos orbitando dentro del borde; radio visible exacto.
            for i in range(5):
                angle = now * 1.8 + i * math.tau / 5.0
                px = x + math.cos(angle) * radius * 0.96
                py = y + math.sin(angle) * radius * 0.96
                dot = max(1.2, radius * 0.045)
                self.cv.create_oval(
                    px - dot, py - dot, px + dot, py + dot,
                    fill=color, width=0)

    def draw_magnetic_button(self):
        now = self.magnetic_now()
        self.draw_ability_icon(
            2, 'campo.png', self.magnetic_pressed,
            self.magnetic_press_started,
            not self.magnetic.available(0, now),
            max(0.0, self.magnetic.ready_at[0] - now),
            self.magnetic.active(0, now), '#35eaff')

    def draw_magnetic_electricity(self):
        now = self.magnetic_now()
        for keeper, effect in self.magnetic_stuns.items():
            elapsed, left = now-effect['started'], effect['until']-now
            fade = max(0.0, min(1.0, elapsed/.3, left/.4))
            if fade <= 0:
                continue
            x, y = self.to_s(keeper.x, keeper.y)
            radius = keeper.r*self.s
            self.draw_electric_sparks(x, y, radius, now, fade, '#7df9ff')

    def draw_electric_sparks(self, x, y, radius, now, fade, color):
        for i in range(7):
            angle = i*math.tau/7 + .16*math.sin(now*8+i)
            r = radius*(.45 if i%3 == 0 else 1.1)
            blink = .5+.5*math.sin(now*17+i*2)
            length = radius*.32*fade*blink
            if length < .4:
                continue
            px, py = x+math.cos(angle)*r, y+math.sin(angle)*r
            points = [(px,py), (px+length*.3,py-length*.35),
                      (px-length*.15,py-length*.65), (px+length*.35,py-length)]
            for first, last in zip(points, points[1:]):
                self.cv.create_line(*first, *last, fill=color, width=max(1, radius*.065))

    def draw_magnetic_fire_penalties(self):
        now = self.magnetic_now()
        x0,y0,x1,y1 = self.ability_rect(0)
        for team, until in enumerate(self.magnetic_fire_penalty):
            if now >= until:
                continue
            if team == 0:
                x,y,r = (x0+x1)/2,(y0+y1)/2,(x1-x0)*.4
            else:
                r = self.u*.8
                x,y = self.cw-self.u*2, self.hud*.35
                self.cv.create_text(x-self.u*1.2,y,text=str(math.ceil(until-now)),
                                    fill='#ff3535',font=self.F(.65),anchor='e')
            self.draw_electric_sparks(x,y,r,now,1.0,'#ff3535')


class ElectricAudio(MagneticAudio):
    """One independent looping channel per keeper; no per-frame restart."""
    def prepare(self):
        if self.loaded:
            return
        self.loaded = True
        try:
            from kivy.core.audio import SoundLoader
            from presentation import asset
            sound = SoundLoader.load(asset('sounds','effects','electrocucion.wav'))
            if sound is not None:
                sound.loop = True
                self.sounds[0] = sound
                self.lengths[0] = max(.01, sound.length)
        except Exception as exc:
            LOG.warning('Electrocución sin audio: %s', exc)

    def update(self, now, enabled=True):
        if self.started is None or self.suspended:
            return
        elapsed = max(0, now-self.started)
        if elapsed >= STUN_DURATION:
            self.stop()
            return
        if not enabled:
            self._silence()
            return
        volume = .18*min(1.0, (STUN_DURATION-elapsed)/.35)
        if self.phase != 'electric':
            self._play(0, volume, elapsed % max(.01,self.lengths[0]))
            self.phase = 'electric'
        self._volume(self.sounds[0], volume)
