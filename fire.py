"""Fire shot rules and presentation, without changing ordinary or penalty shots."""
import math

PLAYER_RECHARGE = 20.0
AI_RECHARGE = (20.0, 20.0, 10.0, 5.0)
POWER_FACTOR = 1.5
TIME_FACTOR = .5
MAX_DURATION = 2.0
ANDROID_SAFE_BOTTOM_DP = 56


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

    def selected(self, body):
        shot = self.shots.get(body.team)
        return shot if shot and shot['body'] is body else None

    def launch(self, body, vx, vy, now, stage):
        shot = self.selected(body)
        if not shot or shot['phase'] != 'aim' or body.keeper or self.executing():
            return False
        team = body.team
        # One ball, one special shot: discard any other team's pre-armed aim.
        self.shots = {team: shot}
        shot.update(phase='launch', origin=body.x, started=now, velocity=(vx, vy))
        self.armed = [False, False]
        self.ready_at[team] = now + (PLAYER_RECHARGE if team == 0 else AI_RECHARGE[stage])
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
        # Four stable slots; visible diameter is twice the player disc diameter.
        diameter = min(self.cw / 5.0, self.ctrl_pad-10, max(44, 72 * self.s))
        cx = self.cw / 8
        cy = self.ch - getattr(self, 'safe_bottom', 0) - self.ctrl_pad / 2
        return cx-diameter/2, cy-diameter/2, cx+diameter/2, cy+diameter/2

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
        flight = next(((team, shot) for team, shot in self.fire.shots.items()
                       if shot['phase'] in ('launch', 'flight')), None)
        if flight:
            team, shot = flight
            # The firing disc alone may transfer its impulse to the ball.
            if shot['phase'] == 'launch' and other is shot['body']:
                flight = None
            else:
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
                shot['flight_started'] = vnow()
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
        for i in range(4):
            cx, cy = self.cw*(i+.5)/4, self.ch-getattr(self, 'safe_bottom', 0)-self.ctrl_pad/2
            if i:
                r = min(self.ctrl_pad*.23, self.cw/24)
                self.cv.create_oval(cx-r, cy-r, cx+r, cy+r, outline='#709582', width=1)
        x0,y0,x1,y1 = self.fire_rect()
        width,height = x1-x0,y1-y0
        down = min(1, max(0, (now-self.fire_press_started)/.08)) if self.fire_pressed else 0
        shrink = 1-.08*down
        size = width*shrink
        # Original upload has generous transparent margins: draw its visible bounds.
        self.visual.texture('fuego.png')
        # PNG is cropped losslessly at delivery, so size is the actual icon diameter.
        self.visual.png('fuego.png',(x0+x1-size)/2,y0+(height-size)/2+down*3,size,size,slot='fire-button')
        unavailable = not self.fire.available(0, now)
        if unavailable or down:
            self.cv.create_oval(x0,y0+down*3,x1,y1+down*3,fill='#071b13',width=0,alpha=.35 if unavailable else .2)
        remaining = max(0,self.fire.ready_at[0]-now)
        if remaining:
            self.cv.create_text((x0+x1)/2,(y0+y1)/2,text=str(math.ceil(remaining)),fill='#ffffff',font=self.F(1.3))
        elif self.fire.armed[0]:
            self.cv.create_oval(x0,y0,x1,y1,outline='#ffd400',width=3)