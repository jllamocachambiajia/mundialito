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

    # ---------- indicador de selección original con apariencia cosmética
    # El motor calcula el pulso y el grosor como siempre; aquí solo cambia el
    # color o diseño del MISMO anillo. Nunca se dibuja un segundo círculo.
    def _mix(self, first, second, amount):
        a = [int(first[i:i+2], 16) for i in (1, 3, 5)]
        b = [int(second[i:i+2], 16) for i in (1, 3, 5)]
        return '#%02x%02x%02x' % tuple(int(a[i]+(b[i]-a[i])*amount) for i in range(3))

    def _coin_symbol(self, x, y, size, color):
        self.cv.create_oval(x-size/2, y-size/2, x+size/2, y+size/2,
                            fill=color, outline='#fff0a0', width=1)
        self.cv.create_oval(x-size*.22, y-size*.22, x+size*.22, y+size*.22,
                            outline='#a96b12', width=1)

    def draw_aura_ring(self, item_id, sx, sy, ring, width, now):
        """Dibuja el anillo de radio `ring` (ya pulsado) con el diseño del aura."""
        cv = self.cv
        entry = ITEMS.get(item_id) or ITEMS['aura_none']
        style = entry['style']
        if style == 'none':
            cv.create_oval(sx-ring, sy-ring, sx+ring, sy+ring, outline='#fff36b', width=width)
            return
        color = self._aura_color(item_id)
        if style == 'solid':
            cv.create_oval(sx-ring, sy-ring, sx+ring, sy+ring, outline=color, width=width)
        elif style in ('coins', 'hearts', 'stars'):
            # Aro fino del mismo indicador decorado con sus símbolos sobre la circunferencia.
            cv.create_oval(sx-ring, sy-ring, sx+ring, sy+ring, outline=color, width=max(1, width*.55))
            count = 8
            size = max(5, ring*.36)
            for index in range(count):
                angle = now*.6 + index*math.tau/count
                x, y = sx+math.cos(angle)*ring, sy+math.sin(angle)*ring
                if style == 'coins':
                    self._coin_symbol(x, y, size, color)
                elif style == 'hearts':
                    self._heart(x, y-size*.08, size, color)
                else:
                    cv.create_polygon(self._star_points(x, y, size*.58, size*.25,
                                                        -math.pi/2+angle), fill=color, width=0)
        else:
            if style == 'rainbow':
                stops = ('#ff5252', '#ff9f3d', '#ffd83d', '#59dc72', '#56d9ff', '#4388ff', '#a879ff', '#ff5252')
            elif style == 'duo':
                stops = ('#ff73b9', '#56d9ff', '#ff73b9')
            else:
                stops = (color, '#56d9ff', color)
            segments = 24
            spin = (now*90) % 360 if style == 'rainbow' else 0
            for index in range(segments):
                t = index/segments
                pos = t*(len(stops)-1)
                k = min(len(stops)-2, int(pos))
                shade = self._mix(stops[k], stops[k+1], pos-k)
                cv.create_arc(sx-ring, sy-ring, sx+ring, sy+ring, start=spin+index*360/segments,
                              extent=360/segments+1.5, style='arc', outline=shade, width=width)

    def draw_selection_ring(self, body, sx, sy, R, pulse):
        if not getattr(self, 'shop', None):
            return super().draw_selection_ring(body, sx, sy, R, pulse)
        from main import vnow
        self.draw_aura_ring(self.shop.state['aura'], sx, sy, R*pulse, max(1.5, R*0.14), vnow())

    # ---------- accesorios y apariencias: un solo dibujo para tienda y partido
    def draw_accessory(self, style, sx, sy, radius):
        cv = self.cv
        if style == 'moustache':
            for side in (-1, 1):
                cv.create_oval(sx+side*radius*.30-radius*.26, sy-radius*.05, sx+side*radius*.30+radius*.26,
                               sy+radius*.16, fill='#302219', width=0)
                cv.create_oval(sx+side*radius*.56-radius*.08, sy-radius*.16, sx+side*radius*.56+radius*.08,
                               sy+radius*.02, fill='#302219', width=0)
        elif style == 'party_hat':
            cv.create_polygon([sx-radius*.65, sy-radius*.72, sx+radius*.45, sy-radius*.72,
                               sx-radius*.15, sy-radius*1.75], fill='#ffcf3f', outline='#ff6f61', width=2)
            cv.create_line(sx-radius*.48, sy-radius*1.0, sx+radius*.22, sy-radius*1.0, fill='#ff6f61', width=max(1, radius*.08))
            cv.create_line(sx-radius*.33, sy-radius*1.3, sx+0, sy-radius*1.3, fill='#43b7ff', width=max(1, radius*.08))
            cv.create_oval(sx-radius*.27, sy-radius*1.87, sx-radius*.03, sy-radius*1.63,
                           fill='#ff73b9', width=0)
        elif style == 'monocle':
            rr = radius*.30
            cv.create_oval(sx+radius*.12, sy-radius*.34, sx+radius*.12+rr*2, sy-radius*.34+rr*2,
                           fill='#cfe9ff', outline='#f5d87b', width=max(1.5, radius*.10), alpha=.35)
            cv.create_line(sx+radius*.65, sy, sx+radius*.76, sy+radius*.72,
                           fill='#f5d87b', width=max(1, radius*.06))
        elif style == 'sunglasses':
            cv.create_rectangle(sx-radius*.68, sy-radius*.36, sx-radius*.05, sy+radius*.03,
                                fill='#161a22', outline='#f5d87b', width=1)
            cv.create_rectangle(sx+radius*.05, sy-radius*.36, sx+radius*.68, sy+radius*.03,
                                fill='#161a22', outline='#f5d87b', width=1)
            cv.create_line(sx-radius*.05, sy-radius*.18, sx+radius*.05, sy-radius*.18,
                           fill='#161a22', width=max(2, radius*.08))
            cv.create_line(sx-radius*.55, sy-radius*.28, sx-radius*.35, sy-radius*.12, fill='#5c6577', width=1)
            cv.create_line(sx+radius*.18, sy-radius*.28, sx+radius*.38, sy-radius*.12, fill='#5c6577', width=1)
        elif style == 'bandaids':
            cv.create_rectangle(sx-radius*.68, sy+radius*.26, sx-radius*.12, sy+radius*.46,
                                fill='#f2c69b', outline='#a87855', width=1)
            cv.create_rectangle(sx-radius*.50, sy+radius*.30, sx-radius*.30, sy+radius*.42,
                                fill='#e0ab7d', width=0)
            cv.create_rectangle(sx+radius*.20, sy-radius*.63, sx+radius*.52, sy-radius*.45,
                                fill='#f2c69b', outline='#a87855', width=1)

    def draw_star_look(self, style, sx, sy, R):
        """Peinados y barbas estilizados, distintos entre sí; pueden salir del círculo."""
        cv = self.cv
        if style == 'messi':
            hair, light, beard = '#4b2e1c', '#7a5236', '#2e1c11'
            # Laterales ordenados, no rapados.
            cv.create_arc(sx-R*1.0, sy-R*1.0, sx+R*1.0, sy+R*1.0, start=140, extent=30,
                          style='arc', outline=hair, width=max(2, R*.13))
            cv.create_arc(sx-R*1.0, sy-R*1.0, sx+R*1.0, sy+R*1.0, start=10, extent=30,
                          style='arc', outline=hair, width=max(2, R*.13))
            # Volumen superior con dirección lateral hacia la derecha.
            cv.create_oval(sx-R*.86, sy-R*1.14, sx+R*.70, sy-R*.44, fill=hair, width=0)
            cv.create_oval(sx-R*.25, sy-R*1.26, sx+R*.96, sy-R*.58, fill=hair, width=0)
            for k in range(5):
                x0 = sx-R*(.66-k*.30)
                cv.create_line(x0, sy-R*.62, x0+R*.42, sy-R*(1.02+.04*(k % 2)), fill=light, width=max(1, R*.07))
            # Puntas del flequillo cayendo al costado.
            for k in range(4):
                x0 = sx-R*(.55-k*.32)
                cv.create_polygon([x0, sy-R*.66, x0+R*.26, sy-R*.66, x0+R*.24, sy-R*.40], fill=hair, width=0)
            # Barba corta definida, más oscura que el cabello.
            cv.create_arc(sx-R*1.02, sy-R*1.0, sx+R*1.02, sy+R*1.04, start=212, extent=116,
                          style='arc', outline=beard, width=max(3, R*.22))
            cv.create_oval(sx-R*.30, sy+R*.80, sx+R*.30, sy+R*1.10, fill=beard, width=0)
        elif style == 'neymar':
            hair, light, fade = '#17110e', '#4a3628', '#5a524c'
            # Degradado lateral visible: dos bandas de tono progresivo.
            for start in (128, 2):
                cv.create_arc(sx-R*1.0, sy-R*1.0, sx+R*1.0, sy+R*1.0, start=start, extent=50,
                              style='arc', outline=fade, width=max(2, R*.18))
                cv.create_arc(sx-R*.94, sy-R*.94, sx+R*.94, sy+R*.94, start=start+8, extent=34,
                              style='arc', outline='#2e2723', width=max(1, R*.10))
            # Parte superior larga y rizada con mechones.
            cv.create_oval(sx-R*.62, sy-R*1.12, sx+R*.62, sy-R*.52, fill=hair, width=0)
            curls = [(-.50, -.78), (-.28, -.98), (-.02, -1.08), (.25, -.99), (.48, -.80),
                     (-.38, -1.18), (-.10, -1.30), (.18, -1.25), (.40, -1.10), (-.15, -.80), (.15, -.82)]
            for dx, dy in curls:
                rr = R*.19
                x, y = sx+R*dx, sy+R*dy
                cv.create_oval(x-rr, y-rr, x+rr, y+rr, fill=hair, width=0)
                cv.create_arc(x-rr*.75, y-rr*.75, x+rr*.75, y+rr*.75, start=40, extent=150,
                              style='arc', outline=light, width=max(1, R*.05))
            # Bigote fino y perilla tipo candado.
            cv.create_arc(sx-R*.86, sy-R*.70, sx+R*.86, sy+R*1.02, start=235, extent=70,
                          style='arc', outline=hair, width=max(2, R*.10))
            cv.create_oval(sx-R*.16, sy+R*.84, sx+R*.16, sy+R*1.12, fill=hair, width=0)
        elif style == 'ronaldo':
            hair, shine = '#1e140e', '#5a4130'
            # Laterales cortos y limpios.
            for start in (138, 8):
                cv.create_arc(sx-R*.99, sy-R*.99, sx+R*.99, sy+R*.99, start=start, extent=34,
                              style='arc', outline=hair, width=max(1.5, R*.11))
            # Parte superior moderada, peinada hacia atrás con contorno nítido.
            cv.create_oval(sx-R*.74, sy-R*1.10, sx+R*.74, sy-R*.50, fill=hair, width=0)
            cv.create_oval(sx-R*.05, sy-R*1.20, sx+R*.66, sy-R*.80, fill=hair, width=0)
            for k, inset in enumerate((.18, .34, .50)):
                cv.create_arc(sx-R*(.74-inset), sy-R*(1.06-inset*.25), sx+R*(.74-inset*.4), sy-R*(.52+inset*.1),
                              start=25, extent=135, style='arc', outline=shine, width=max(1, R*.06))
            # Rostro limpio, sin barba.
        elif style == 'mbappe':
            hair, fade = '#0b0a0a', '#3b3633'
            # Buzz cut: banda corta pegada al contorno, sin volumen.
            cv.create_arc(sx-R*.92, sy-R*.92, sx+R*.92, sy+R*.92, start=32, extent=116,
                          style='arc', outline=hair, width=max(3, R*.30))
            # Línea frontal recta y definida.
            cv.create_line(sx-R*.48, sy-R*.70, sx+R*.48, sy-R*.70, fill=hair, width=max(2, R*.10))
            # Degradado progresivo en laterales y nuca.
            for start in (148, 12):
                cv.create_arc(sx-R*.95, sy-R*.95, sx+R*.95, sy+R*.95, start=start, extent=22,
                              style='arc', outline=fade, width=max(2, R*.18))
            # Textura corta discreta.
            for k in range(9):
                a = math.radians(40+k*12.5)
                x, y = sx+math.cos(a)*R*.86, sy-math.sin(a)*R*.86
                rr = max(.6, R*.035)
                cv.create_oval(x-rr, y-rr, x+rr, y+rr, fill='#2b2725', width=0)

    def draw_equipped_accessories(self, sx, sy, radius, team, num):
        for item_id in self.shop.state['accessories']:
            self.draw_accessory(ITEMS[item_id]['style'], sx, sy, radius)
        appearance = self.shop.appearance_for(team)
        if not appearance or num != appearance['dorsal']:
            return
        self.draw_star_look(appearance['style'], sx, sy, radius)

    def _jersey(self, sx, sy, radius, team, keeper=False, side=0, num=None):
        cosmetic = bool(getattr(self, 'shop', None) and self.state in ('match', 'pens')
                        and side == 0 and team == getattr(self, 'user', None))
        result = super()._jersey(sx, sy, radius, team, keeper, side, num)
        if cosmetic:
            self.draw_equipped_accessories(sx, sy, radius, team, num)
        return result

    # ---------- balón: devuelve True cuando ya lo dibujó; nunca cambia body.r
    def draw_custom_ball(self, sx, sy, radius, original_radius):
        if not getattr(self, 'shop', None) or self.state not in ('match', 'pens'):
            return False
        return self.draw_ball_style(self.shop.state['ball'], sx, sy, radius)

    def draw_ball_style(self, item_id, sx, sy, radius):
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
            if self.selection_ring_visible(body):
                from main import vnow
                self.draw_selection_ring(body, sx, sy, radius, 1.25 + 0.1 * math.sin(vnow() * 8))
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
