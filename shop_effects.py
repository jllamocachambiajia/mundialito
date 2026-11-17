"""Efectos visuales y pasivas del jugador; la CPU conserva siempre los valores base."""
import math
from shop_data import ITEMS


class ShopEffects:
    # ---------- valores de partido: solo equipo humano (team == 0)
    def shop_value(self, key):
        service = getattr(self, 'shop', None)
        return service.passive_value(key) if service else {
            'power': 1.0, 'effect': 1.5, 'keeper': 1.0, 'slide': 1.0,
            'recovery': 0.0, 'impact': 0.0, 'shot': 1.0,
        }[key]

    def player_power_factor(self, body):
        return self.shop_value('power') if getattr(body, 'team', None) == 0 else 1.0

    def player_fire_factor(self, body):
        return self.shop_value('effect') if getattr(body, 'team', None) == 0 else 1.5

    def player_shot_interval(self):
        from main import COOLDOWN
        return COOLDOWN * self.shop_value('shot')

    def shop_recovery_factor(self):
        return 1.0 - self.shop_value('recovery')

    def start_match(self, opp):
        if getattr(self, 'shop', None):
            self.shop.set_country(self.user)
        return super().start_match(opp)

    def reset_positions(self):
        result = super().reset_positions()
        if getattr(self, 'shop', None) and getattr(self, 'state', None) == 'match':
            keeper_scale = self.shop_value('keeper')
            for body in self.bodies:
                if body.team == 0 and body.keeper:
                    from main import PR
                    body.r = PR * keeper_scale
            appearance = self.shop.appearance_for(self.user)
            if appearance:
                star = next((b for b in self.bodies if b.team == 0 and not b.keeper), None)
                if star:
                    old = star.num
                    for body in self.bodies:
                        if body.team == 0 and not body.keeper and body is not star and body.num == appearance['dorsal']:
                            body.num = old
                    star.num = appearance['dorsal']
                    self.nums[0] = [next(b.num for b in self.bodies if b.team == 0 and b.keeper)] + [
                        b.num for b in self.bodies if b.team == 0 and not b.keeper]
        return result

    def shoot(self, body, vx, vy):
        from main import vnow, COOLDOWN
        service = getattr(self, 'shop', None)
        human = bool(service and getattr(self, 'state', None) == 'match' and body.team == 0)
        selected = self.fire.selected(body) if human and not body.keeper else None
        special = bool(selected and selected.get('phase') == 'aim' and not self.fire.executing())
        result = super().shoot(body, vx, vy)
        if not human or self.magnetic_stunned(body):
            return result
        factor = self.shop_value('effect') / 1.5 if special else self.shop_value('power')
        if factor != 1.0:
            body.vx *= factor
            body.vy *= factor
            shot = self.fire.selected(body)
            if shot and shot.get('phase') in ('launch', 'flight'):
                shot['velocity'] = (body.vx, body.vy)
        now = vnow()
        interval = COOLDOWN * self.shop_value('shot')
        if body.keeper:
            self.gk_next[0] = now + interval
        else:
            self.next_shot_at[0] = now + interval
        if special:
            self.fire.ready_at[0] = now + 20.0 * self.shop_recovery_factor()
        return result

    def pausa_activate(self, team):
        activated = super().pausa_activate(team)
        if activated and team == 0:
            from main import vnow
            self.pausa.ready_at[0] = vnow() + 60.0 * self.shop_recovery_factor()
        return activated

    def magnetic_activate(self, team):
        activated = super().magnetic_activate(team)
        if activated and team == 0:
            self.magnetic.ready_at[0] = self.magnetic_now() + 30.0 * self.shop_recovery_factor()
        return activated

    def magnetic_fire_contact(self, a, b, now):
        penalized = super().magnetic_fire_contact(a, b, now)
        if penalized:
            disc = b if a is self.ball else a
            if disc.team == 0:
                shot = self.fire.selected(disc)
                if shot:
                    deadline = shot['started'] + 40.0 * self.shop_recovery_factor()
                    self.fire.ready_at[0] = deadline
                    self.magnetic_fire_penalty[0] = deadline
        return penalized

    def ability_cooldown(self, slot):
        base = super().ability_cooldown(slot)
        return base * self.shop_recovery_factor() if base is not None else None

    def friction_for(self, body, base):
        if body.team == 0 and body is not self.ball and getattr(self, 'shop', None):
            from main import FRICTION
            remaining = self.shop_value('slide')
            return 1 - (1 - FRICTION) / remaining
        return base

    def match_collision(self, a, b):
        humans = [body for body in (a, b)
                  if body is not self.ball and body.team == 0 and getattr(self, 'shop', None)]
        if humans:
            self._impact_before = {id(body): (body.x, body.y, body.vx, body.vy) for body in humans}
        else:
            self._impact_before = {}
        return super().match_collision(a, b)

    def collision_done(self, a, b):
        before = getattr(self, '_impact_before', {})
        if not before:
            return
        factor = 1.0 - self.shop_value('impact')
        for body in (a, b):
            old = before.get(id(body))
            if old:
                body.x = old[0] + (body.x-old[0])*factor
                body.y = old[1] + (body.y-old[1])*factor
                body.vx = old[2] + (body.vx-old[2])*factor
                body.vy = old[3] + (body.vy-old[3])*factor
        self._impact_before = {}

    # ---------- auras, accesorios y apariencias originales
    def _star_points(self, x, y, outer, inner, rotation=-math.pi/2):
        points = []
        for index in range(10):
            radius = outer if index % 2 == 0 else inner
            angle = rotation + index*math.pi/5
            points.extend((x+math.cos(angle)*radius, y+math.sin(angle)*radius))
        return points

    def _heart(self, x, y, size, color):
        r = size*.34
        self.cv.create_oval(x-size*.48, y-size*.38, x+size*.02, y+size*.12, fill=color, width=0)
        self.cv.create_oval(x-size*.02, y-size*.38, x+size*.48, y+size*.12, fill=color, width=0)
        self.cv.create_polygon([x-size*.45, y, x+size*.45, y, x, y+size*.58], fill=color, width=0)

    def _aura_color(self, item_id):
        entry = ITEMS[item_id]
        return self.shop.state['aura_colors'].get(item_id, entry.get('color', '#ffd83d'))

    def draw_equipped_aura(self, sx, sy, radius):
        item_id = self.shop.state['aura']
        if item_id == 'aura_none':
            return
        entry = ITEMS[item_id]
        style = entry['style']
        color = self._aura_color(item_id)
        now = self.vnow() if hasattr(self, 'vnow') else __import__('main').vnow()
        glow = radius*1.43
        self.cv.create_oval(sx-glow, sy-glow, sx+glow, sy+glow,
                            fill=color, width=0, alpha=.075)
        if style == 'solid':
            self.cv.create_oval(sx-glow, sy-glow, sx+glow, sy+glow,
                                outline=color, width=max(1.5, radius*.13), alpha=.85)
        elif style in ('coins', 'hearts', 'stars'):
            for index in range(7):
                angle = now*.8 + index*math.tau/7
                x, y = sx+math.cos(angle)*radius*1.34, sy+math.sin(angle)*radius*1.34
                size = radius*.36
                if style == 'coins':
                    self.cv.create_oval(x-size/2, y-size/2, x+size/2, y+size/2,
                                        fill=color, outline='#fff0a0', width=1)
                    self.cv.create_oval(x-size*.19, y-size*.19, x+size*.19, y+size*.19,
                                        outline='#a96b12', width=1)
                elif style == 'hearts':
                    self._heart(x, y, size, color)
                else:
                    self.cv.create_polygon(self._star_points(x, y, size*.58, size*.25), fill=color, width=0)
        else:
            colors = {
                'gradient': (color, '#56d9ff'), 'duo': ('#ff73b9', '#56d9ff'),
                'rainbow': ('#ff5252', '#ffd83d', '#59dc72', '#56d9ff', '#a879ff'),
            }.get(style, (color, '#ffffff'))
            count = len(colors)
            for index in range(18):
                angle = index*20 + (now*75 if style == 'rainbow' else 0)
                selected = colors[(index*count//18 + (int(now*2) if style == 'rainbow' else 0)) % count]
                self.cv.create_arc(sx-glow, sy-glow, sx+glow, sy+glow,
                                   start=angle, extent=25, style='arc', outline=selected,
                                   width=max(2, radius*.16))

    def draw_equipped_accessories(self, sx, sy, radius, team, num):
        cv = self.cv
        for item_id in self.shop.state['accessories']:
            style = ITEMS[item_id]['style']
            if style == 'moustache':
                cv.create_arc(sx-radius*.55, sy+radius*.02, sx, sy+radius*.48,
                              start=190, extent=160, style='arc', outline='#302219', width=max(2, radius*.14))
                cv.create_arc(sx, sy+radius*.02, sx+radius*.55, sy+radius*.48,
                              start=190, extent=160, style='arc', outline='#302219', width=max(2, radius*.14))
            elif style == 'party_hat':
                cv.create_polygon([sx-radius*.65, sy-radius*.72, sx+radius*.45, sy-radius*.72,
                                   sx-radius*.15, sy-radius*1.75], fill='#ffcf3f', outline='#ff6f61', width=2)
                cv.create_oval(sx-radius*.25, sy-radius*1.85, sx-radius*.05, sy-radius*1.65,
                               fill='#ff73b9', width=0)
            elif style == 'monocle':
                rr = radius*.30
                cv.create_oval(sx+radius*.12, sy-radius*.34, sx+radius*.12+rr*2, sy-radius*.34+rr*2,
                               outline='#f5d87b', width=max(1.5, radius*.08))
                cv.create_line(sx+radius*.65, sy, sx+radius*.76, sy+radius*.72,
                               fill='#f5d87b', width=max(1, radius*.05))
            elif style == 'sunglasses':
                cv.create_rectangle(sx-radius*.68, sy-radius*.36, sx-radius*.05, sy+radius*.03,
                                    fill='#161a22', outline='#f5d87b', width=1)
                cv.create_rectangle(sx+radius*.05, sy-radius*.36, sx+radius*.68, sy+radius*.03,
                                    fill='#161a22', outline='#f5d87b', width=1)
                cv.create_line(sx-radius*.05, sy-radius*.18, sx+radius*.05, sy-radius*.18,
                               fill='#161a22', width=max(2, radius*.08))
            elif style == 'bandaids':
                cv.create_rectangle(sx-radius*.68, sy+radius*.26, sx-radius*.12, sy+radius*.46,
                                    fill='#f2c69b', outline='#a87855', width=1)
                cv.create_rectangle(sx+radius*.20, sy-radius*.63, sx+radius*.52, sy-radius*.45,
                                    fill='#f2c69b', outline='#a87855', width=1)
        appearance = self.shop.appearance_for(team)
        if not appearance or num != appearance['dorsal']:
            return
        style = appearance['style']
        hair = '#241b18' if style != 'messi' else '#3b281f'
        if style == 'mbappe':
            cv.create_arc(sx-radius*.74, sy-radius*.87, sx+radius*.74, sy+radius*.12,
                          start=5, extent=170, style='arc', outline=hair, width=max(3, radius*.22))
        elif style == 'neymar':
            for index in range(5):
                x = sx-radius*.55+index*radius*.27
                cv.create_polygon([x-radius*.16, sy-radius*.67, x+radius*.16, sy-radius*.67,
                                   x, sy-radius*(1.18+.12*(index%2))], fill=hair, width=0)
        else:
            cv.create_arc(sx-radius*.78, sy-radius*.95, sx+radius*.78, sy+radius*.1,
                          start=0, extent=180, style='arc', outline=hair, width=max(4, radius*.26))
        if style == 'messi':
            cv.create_arc(sx-radius*.62, sy+radius*.08, sx+radius*.62, sy+radius*.82,
                          start=180, extent=180, style='arc', outline=hair, width=max(3, radius*.18))

    def _jersey(self, sx, sy, radius, team, keeper=False, side=0, num=None):
        cosmetic = bool(getattr(self, 'shop', None) and self.state in ('match', 'pens')
                        and side == 0 and team == getattr(self, 'user', None))
        if cosmetic:
            self.draw_equipped_aura(sx, sy, radius)
        result = super()._jersey(sx, sy, radius, team, keeper, side, num)
        if cosmetic:
            self.draw_equipped_accessories(sx, sy, radius, team, num)
        return result

    # ---------- balón: devuelve True cuando ya lo dibujó; nunca cambia body.r
    def draw_custom_ball(self, sx, sy, radius, original_radius):
        if not getattr(self, 'shop', None) or self.state not in ('match', 'pens'):
            return False
        item_id = self.shop.state['ball']
        if item_id == 'ball_classic':
            return False
        entry = ITEMS[item_id]
        style = entry['style']
        if style == 'invisible':
            return True
        cv = self.cv
        color = entry.get('color', '#ffffff')
        if style in ('american', 'rugby'):
            cv.create_oval(sx-radius*.72, sy-radius*1.18, sx+radius*.72, sy+radius*1.18,
                           fill='#9a542e' if style == 'american' else '#7b4b32', outline='#f4e2c2', width=2)
            cv.create_line(sx-radius*.30, sy, sx+radius*.30, sy, fill='#ffffff', width=max(1, radius*.10))
            for offset in (-.18, 0, .18):
                cv.create_line(sx+radius*offset, sy-radius*.18, sx+radius*offset, sy+radius*.18,
                               fill='#ffffff', width=1)
            return True
        fills = {'tennis': '#d8ef42', 'basket': '#ed8a32', 'baseball': '#f7f4ea',
                 'volley': '#f7f7f2', 'golf': '#f4f6f7', 'bowling': '#333846',
                 'billiard': '#315bd8', 'cricket': '#a84235'}
        color = fills.get(style, color)
        cv.create_oval(sx-radius, sy-radius, sx+radius, sy+radius,
                       fill=color, outline='#22272b', width=max(1, radius*.09))
        if style == 'tennis':
            cv.create_arc(sx-radius*.8, sy-radius, sx+radius*.8, sy+radius, start=70, extent=220,
                          style='arc', outline='#ffffff', width=max(1, radius*.1))
        elif style == 'basket':
            cv.create_line(sx-radius, sy, sx+radius, sy, fill='#4d2d20', width=1)
            cv.create_line(sx, sy-radius, sx, sy+radius, fill='#4d2d20', width=1)
            cv.create_arc(sx-radius, sy-radius, sx+radius, sy+radius, start=45, extent=90,
                          style='arc', outline='#4d2d20', width=1)
        elif style in ('baseball', 'cricket'):
            cv.create_arc(sx-radius*.65, sy-radius*.8, sx+radius*.65, sy+radius*.8, start=80, extent=200,
                          style='arc', outline='#d34545' if style == 'baseball' else '#f0d4b8', width=2)
        elif style == 'volley':
            for angle in (0, 60, 120):
                cv.create_arc(sx-radius, sy-radius, sx+radius, sy+radius, start=angle, extent=45,
                              style='arc', outline='#3279c7', width=max(2, radius*.16))
        elif style == 'golf':
            for index in range(8):
                angle = index*math.tau/8
                rr = radius*.07
                x, y = sx+math.cos(angle)*radius*.55, sy+math.sin(angle)*radius*.55
                cv.create_oval(x-rr, y-rr, x+rr, y+rr, fill='#c4cbd0', width=0)
        elif style == 'bowling':
            for dx, dy in ((-.2, -.25), (.15, -.3), (0, .02)):
                rr = radius*.10
                cv.create_oval(sx+radius*dx-rr, sy+radius*dy-rr, sx+radius*dx+rr, sy+radius*dy+rr,
                               fill='#111318', width=0)
        elif style == 'billiard':
            cv.create_oval(sx-radius*.52, sy-radius*.52, sx+radius*.52, sy+radius*.52, fill='#ffffff', width=0)
            cv.create_text(sx, sy, text='8', fill='#111318', font=self.F(max(.6, radius/self.u*.75)))
        return True

    # ---------- ambientes visuales
    def _environment(self):
        if not getattr(self, 'shop', None):
            return None
        return self.shop.state['environment']

    def _snowflake(self, x, y, radius, color='#eafaff'):
        for angle in (0, math.pi/3, 2*math.pi/3):
            dx, dy = math.cos(angle)*radius, math.sin(angle)*radius
            self.cv.create_line(x-dx, y-dy, x+dx, y+dy, fill=color, width=1)

    def _flower(self, x, y, radius):
        for index in range(5):
            angle = index*math.tau/5
            px, py = x+math.cos(angle)*radius*.65, y+math.sin(angle)*radius*.65
            rr = radius*.46
            self.cv.create_oval(px-rr, py-rr, px+rr, py+rr, fill='#ff9ecf', width=0, alpha=.85)
        rr = radius*.33
        self.cv.create_oval(x-rr, y-rr, x+rr, y+rr, fill='#ffe77a', width=0)

    def draw_stadium_back(self):
        environment = self._environment()
        if not environment or self.state != 'match':
            return
        from main import FX0, FY0, FX1, FY1, vnow
        if environment == 'env_flowers':
            self.rect_w(FX0, FY0, FX1, FY1, fill='#ff9ecf', width=0, alpha=.065)
        elif environment == 'env_night':
            self.rect_w(FX0, FY0, FX1, FY1, fill='#071122', width=0, alpha=.29)
            for x, y in ((FX0, FY0), (FX0, FY1), (FX1, FY0), (FX1, FY1)):
                sx, sy = self.to_s(x, y)
                for step in range(6, 0, -1):
                    rr = self.u*step*1.8
                    self.cv.create_oval(sx-rr, sy-rr, sx+rr, sy+rr,
                                        fill='#fff4bd', width=0, alpha=.018)
                self.cv.create_line(sx, sy, sx, sy+self.u*2.5, fill='#d5deea', width=2)
                self.cv.create_oval(sx-self.u*.35, sy-self.u*.35, sx+self.u*.35, sy+self.u*.35,
                                    fill='#fff5c7', width=0)
        elif environment == 'env_snow':
            now = vnow()
            for index in range(42):
                x = (index*.61803398875) % 1
                y = (index*.381966 + now*(.025+(index%5)*.005)) % 1
                sx, sy = x*self.cw, self.hud+y*max(1, self.ch-self.hud-self.ctrl_pad)
                self._snowflake(sx, sy, 1.5+(index%3), '#eafaff')

    def draw_stadium_front(self):
        if self._environment() != 'env_visibility' or self.state != 'match':
            return
        from main import FX0, FY0, FX1, FY1
        cv = self.cv
        bottom = self.ch-self.ctrl_pad-getattr(self, 'safe_bottom', 0)
        cv.create_rectangle(0, self.hud, self.cw, bottom, fill='#02050b', width=0, alpha=.12)
        points = []
        for x, y in ((FX0, FY0), (FX1, FY0), (FX1, FY1), (FX0, FY1)):
            points.extend(self.to_s(x, y))
        cv.create_polygon(points, fill='#02050b', width=0, alpha=1.0)
        own = [body for body in self.bodies if body.team == 0]
        for body in own:
            sx, sy = self.to_s(body.x, body.y)
            radius = body.r*self.s
            glow = radius*1.43
            cv.create_oval(sx-glow*1.6, sy-glow*1.6, sx+glow*1.6, sy+glow*1.6,
                           fill='#ffe987', width=0, alpha=.055)
            self.jersey(sx, sy, radius, self.teams[0], body.keeper, 0, body.num)
        for keeper in own:
            if math.hypot(self.ball.x-keeper.x, self.ball.y-keeper.y) <= keeper.r*1.7:
                sx, sy = self.to_s(self.ball.x, self.ball.y)
                radius = self.ball.r*self.s
                if not self.draw_custom_ball(sx, sy, radius, radius):
                    cv.create_oval(sx-radius, sy-radius, sx+radius, sy+radius,
                                   fill='#ffffff', outline='#222222', width=1)
                break

    def draw_hud(self):
        result = super().draw_hud()
        environment = self._environment()
        if environment == 'env_snow':
            for index in range(7):
                x = self.cw*(index+.5)/7
                self._snowflake(x, self.hud*.15, self.u*.28)
                cv = self.cv
                cv.create_polygon([x-self.u*.22, 0, x+self.u*.22, 0, x, self.u*(.35+(index%3)*.2)],
                                  fill='#c9efff', width=0, alpha=.8)
        elif environment == 'env_flowers':
            for x in (self.cw*.12, self.cw*.88):
                self._flower(x, self.hud*.22, self.u*.45)
        return result
