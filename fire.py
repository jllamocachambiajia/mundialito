"""Fire shot rules and presentation, without changing ordinary or penalty shots."""
import math

PLAYER_RECHARGE = 20.0
AI_RECHARGE = (20.0, 20.0, 10.0, 5.0)
POWER_FACTOR = 1.5
TIME_FACTOR = .5
MAX_DURATION = 2.0
ANDROID_SAFE_BOTTOM_DP = 72          # margen extra para la barra de navegación (Motorola, etc.)


class FireState:
    def __init__(self):
        self.ready_at = [0.0, 0.0]
        self.armed = [False, False]
        self.shots = {}
        self.recovery = 1.0

    def available(self, team, now):
        return now >= self.ready_at[team] and not self.armed[team] and not self.shots

    def executing(self):
        return any(s['phase'] in ('launch', 'flight') for s in self.shots.values())

    def arm(self, team, now):
        if not self.available(team, now):
            return False
        self.armed[team] = True
        return True

    def select(self, body, now):
        team = body.team
        if body.keeper or not self.armed[team] or self.executing():
            return False
        old = self.shots.get(team)
        if old and old['phase'] != 'aim':
            return False
        self.shots[team] = dict(body=body, phase='aim', origin=body.x,
                                started=now, velocity=(0, 0))
        return True

    def selected_team(self, team):
        return self.shots.get(team) is not None

    def selected(self, body):
        shot = self.shots.get(body.team)
        return shot if shot and shot['body'] is body else None

    def launch(self, body, vx, vy, now, stage, recharge=None):
        shot = self.selected(body)
        if not shot or shot['phase'] != 'aim' or body.keeper or self.executing():
            return False
        team = body.team
        # One ball, one special shot: discard any other team's pre-armed aim.
        self.shots = {team: shot}
        shot.update(phase='launch', origin=body.x, started=now, velocity=(vx, vy))
        self.armed = [False, False]
        if recharge is None:
            recharge = PLAYER_RECHARGE if team == 0 else AI_RECHARGE[stage]
        self.ready_at[team] = now + recharge
        return True

    def finish(self, team=None):
        """The only exit for BOTH teams; never change ball position or velocity."""
        self.shots.clear()
        self.armed = [False, False]
        self.recovery = 1.0

    def expire(self, now):
        if any(s['phase'] != 'aim' and now - s['started'] >= MAX_DURATION
               for s in self.shots.values()):
            self.finish()
            return True
        return False

    def clear(self):
        self.finish()

    def scale(self, dt):
        if self.shots:
            self.recovery = TIME_FACTOR
            return TIME_FACTOR
        self.recovery = 1.0
        return 1.0

    @staticmethod
    def keeper_blocks(shot, keeper, middle):
        if not keeper.keeper or keeper.team == shot['body'].team:
            return False
        own_half = shot['origin'] <= middle if shot['body'].team == 0 else shot['origin'] >= middle
        return own_half


class FireAbility:
    def fire_reset(self):
        self.fire = FireState()
        self.fire_pressed = False
        self.fire_press_started = 0
        self.fire_time = 0.0
        self.fire_block = False

    def fire_rect(self):
        # First of the four shared ability slots (4 x disc diameter, see abilities.py).
        return self.ability_rect(0)

    def fire_press(self, x, y):
        from main import vnow
        x0, y0, x1, y1 = self.fire_rect()
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        # Never turn a dragged player into an accidental button activation.
        if self.drag is None and self.phase == 'play' and self.kick_team != 1 and self.fire.available(0, vnow()):
            self.fire_pressed = True
            self.fire_press_started = vnow()
        return True

    def fire_release(self, x, y):
        from main import vnow
        if not self.fire_pressed:
            return False
        self.fire_pressed = False
        x0, y0, x1, y1 = self.fire_rect()
        if self.phase == 'play' and x0 <= x <= x1 and y0 <= y <= y1 and self.fire.arm(0, vnow()):
            self.snd.play('fuego', dur=.2)
        return True

    def fire_collision(self, a, b):
        """Optional substep policy. Normal pairs always keep the original collide()."""
        from main import collide, FX0, FX1, MAX_DRAG, POWER, vnow
        self.fire.expire(vnow())
        ball = self.ball
        other = b if a is ball else a if b is ball else None
        if other is None:
            return True
        # Intangibility starts ONLY after the armed disc really touched the ball.
        # Aim and launch phases keep every ordinary ball collision.
        flight = next(((team, shot) for team, shot in self.fire.shots.items()
                       if shot['phase'] == 'flight'), None)
        if flight:
            team, shot = flight
            if self.fire.keeper_blocks(shot, other, (FX0+FX1)/2):
                distance = math.hypot(ball.x-other.x, ball.y-other.y)
                approach = (ball.vx-other.vx)*(other.x-ball.x)+(ball.vy-other.vy)*(other.y-ball.y)
                if distance <= ball.r+other.r and approach > 0:
                    self.fire.finish()
                    self.fire_block = True
                return True
            return False
        for team, shot in list(self.fire.shots.items()):
            if shot['phase'] != 'launch' or shot['body'] is not other:
                continue
            if 0 < math.hypot(ball.x-other.x, ball.y-other.y) < ball.r+other.r:
                # Transfer on the actual disc-ball collision, not at button activation.
                collide(a, b)
                vx, vy = shot['velocity']
                speed = math.hypot(vx, vy)
                if speed > 0:
                    ball.vx, ball.vy = vx*1.44, vy*1.44
                    cap = MAX_DRAG*POWER*POWER_FACTOR*1.44
                    magnitude = ball.speed()
                    if magnitude > cap:
                        ball.vx *= cap/magnitude; ball.vy *= cap/magnitude
                shot['phase'] = 'flight'
                # The 2 s special window counts from the special shot itself.
                shot['flight_started'] = shot['started'] = vnow()
                return False
        return True

    def fire_update(self, dt):
        from main import vnow
        self.fire.expire(vnow())
        self.fire_time += dt * (.5 if self.fire.shots else 1)
        if self.fire_block:
            self.fire_block = False
            self.gk_mode = False
            self.flash('¡BLOQUEO DEL ARQUERO!', 1.5)
            self.snd.play('uy', dur=.8)

    def fire_ai(self, body, kind, goal_distance):
        from main import vnow, FX0, FX1, GY0, GY1
        # Only credible scoring attempts, never keeper moves or repositioning.
        if kind != 'tiro' or body.keeper or self.kick_team == 0:
            return False
        b = self.ball
        near_ball = math.hypot(body.x-b.x, body.y-b.y) < 260
        urgent = self.score[1] < self.score[0] or self.clock > 240
        attacking = b.x < (FX0+FX1)/2
        angle_good = GY0-120 < b.y < GY1+120
        if near_ball and angle_good and (attacking or urgent or goal_distance < 600):
            if self.fire.arm(1, vnow()) and self.fire.select(body, vnow()):
                self.snd.play('fuego', dur=.2)
                return True
        return False

    def draw_fire_aura(self):
        from main import FX0, FX1, FY0, FY1
        if self.fire.shots:
            self.rect_w(FX0, FY0, FX1, FY1, fill='#ff261c', width=0, alpha=.15)

    def draw_fire_ring(self, body, sx, sy, radius):
        if not self.fire.selected(body):
            return
        # Continuous animated flame tongues all around the circumference.
        for i in range(28):
            a = i*math.tau/28
            height = .3+.18*math.sin(self.fire_time*12+i*1.7)
            inner, outer = radius*1.08, radius*(1.4+height)
            da = math.tau/65
            points = [sx+math.cos(a-da)*inner, sy+math.sin(a-da)*inner,
                      sx+math.cos(a+.025*math.sin(self.fire_time*9+i))*outer,
                      sy+math.sin(a+.025*math.sin(self.fire_time*9+i))*outer,
                      sx+math.cos(a+da)*inner, sy+math.sin(a+da)*inner]
            self.cv.create_polygon(points, fill='#ff5a12' if i%2 else '#ffd400', width=0)

    def draw_fire_button(self):
        from main import vnow
        now = vnow()
        self.draw_ability_icon(0, 'fuego.png', self.fire_pressed, self.fire_press_started,
                               not self.fire.available(0, now), self.fire.ready_at[0]-now,
                               self.fire.armed[0] or self.fire.selected_team(0), '#ffd400')

    def fire_ball_scale(self, dt):
        """Visual-only lift: 1x -> 2x at mid flight -> 1x. Physics radius/mass untouched."""
        from main import vnow
        shot = next((s for s in self.fire.shots.values() if s['phase'] == 'flight'), None)
        current = getattr(self, 'ball_scale', 1.0)
        if shot:
            progress = min(1.0, max(0.0, (vnow()-shot['flight_started'])/MAX_DURATION))
            current = 1.0 + math.sin(math.pi*progress)
        else:
            # Goal/block/expiry: ease back to the original diameter, never jump.
            current = 1.0 + (current-1.0)*math.exp(-max(0, dt)*10)
            if current < 1.003:
                current = 1.0
        self.ball_scale = current
        return current
