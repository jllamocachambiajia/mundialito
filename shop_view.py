"""Tienda Kivy y celebraciones de moneditas, compuesta sobre el menú existente."""
import math
import time
import uuid
from kivy.graphics import PushMatrix, PopMatrix, Translate, Color, RoundedRectangle
from shop_audio import ShopAudio
from shop_data import (CATEGORIES, ITEMS, PALETTE, PASSIVES, PASSIVE_ORDER,
                       catalog_for, passive_display, passive_price)
from shop_effects import ShopEffects
from shop_service import ShopController, ShopService


class ShopView(ShopEffects):
    def front_init(self):
        super().front_init()
        self.shop = ShopService(self.store)
        self.shop_audio = ShopAudio(lambda: self.snd.on)
        self.shop_actions = ShopController(self.shop, self.shop_audio)
        self.shop_page = 'root'
        self.shop_category = None
        self.shop_scroll = 0.0
        self.shop_max_scroll = 0.0
        self.shop_buttons = []
        self.shop_touch = None
        self.shop_transition = None
        self.shop_palette = None
        self.shop_info = None
        self.shop_toast = ('', 0.0)
        self.reward_animation = None
        self.tournament_id = None

    # ---------- entrada, salida y navegación de tres flechas
    def open_shop(self):
        self.shop.refresh()
        self.shop_page = 'root'
        self.shop_category = None
        self.shop_scroll = 0
        self.shop_palette = self.shop_info = None
        self.menu_audio.transition_effect()
        self.state = 'shop'
        self.render()

    def close_shop(self):
        # El estado ya está guardado; se recarga aquí antes de la siguiente partida.
        self.shop.refresh()
        self.shop_page = 'root'
        self.shop_category = None
        self.state = 'home'
        self.menu_audio.start()
        self.recalc()
        self.render()

    def shop_go(self, page, category=None, direction=1):
        self.shop_page = page
        self.shop_category = category
        self.shop_scroll = 0
        self.shop_palette = self.shop_info = None
        self.shop_transition = {'start': time.monotonic(), 'duration': .26, 'direction': direction}
        self.menu_audio.transition_effect()
        self.render()

    def shop_back(self, level):
        if level == 1:
            self.close_shop()
        elif level == 2:
            self.shop_go('root', direction=-1)
        elif level == 3:
            self.shop_go('cosmetics', direction=-1)

    def front_keyboard(self, window, key, *args):
        if key == 27 and getattr(self, 'state', None) == 'shop':
            if self.shop_palette:
                self.shop_palette = None
                self.render()
            elif self.shop_info:
                self.shop_info = None
                self.render()
            elif self.shop_page == 'root':
                self.close_shop()
            elif self.shop_page in ('cosmetics', 'passives'):
                self.shop_back(2)
            else:
                self.shop_back(3)
            return True
        return super().front_keyboard(window, key, *args)

    def start_tournament(self, team):
        self.tournament_id = uuid.uuid4().hex
        self.shop.set_country(team)
        return super().start_tournament(team)

    def finish_user_match(self, winner, text):
        if winner == self.user and self.round == 3:
            reward = self.shop.reward(f'tournament:{self.tournament_id}', 'tournament', 1000)
            if reward:
                self.start_reward(reward['amount'], reward['balance'])
        return super().finish_user_match(winner, text)

    def start_reward(self, amount, balance):
        self.shop.refresh()
        self.reward_animation = {
            # 2 s para ver el resultado y 4 s de conteo pausado.
            'start': time.monotonic()+2.0, 'duration': 4.0,
            'from': max(0, balance-amount), 'to': balance, 'amount': amount,
            'shown': None,
        }

    def front_tick(self):
        super().front_tick()
        now = time.monotonic()
        if self.state == 'shop':
            if self.shop_transition and now-self.shop_transition['start'] >= self.shop_transition['duration']:
                self.shop_transition = None
            self.render()
        elif self.reward_animation:
            elapsed = now-self.reward_animation['start']
            if elapsed >= self.reward_animation['duration']+1.4:
                self.reward_animation = None
            self.render()

    def front_stop(self):
        if getattr(self, 'shop_audio', None):
            self.shop_audio.stop()
        return super().front_stop()

    # ---------- renderizado general
    def render(self):
        if not getattr(self, 'shop', None) or self.state != 'shop':
            result = super().render()
            self.draw_reward_overlay()
            return result
        self.draw_shop()

    def draw(self):
        if getattr(self, 'shop', None) and self.state == 'shop':
            self.draw_shop()
            return
        result = super().draw()
        self.draw_reward_overlay()
        return result

    def _shop_header_height(self):
        return max(76, min(102, self.ch*.135))

    def _shop_depth(self):
        if self.shop_page == 'root':
            return 1
        if self.shop_page in ('cosmetics', 'passives'):
            return 2
        return 3

    def _shop_arrow(self, x, y, size, level):
        cv = self.cv
        cv.create_oval(x-size/2, y-size/2, x+size/2, y+size/2,
                       fill='#123d2c', outline='#e6c98e', width=1.5)
        cv.create_line(x+size*.17, y, x-size*.16, y, fill='#ffcf4a', width=3)
        cv.create_line(x-size*.16, y, x-size*.01, y-size*.16, fill='#ffcf4a', width=3)
        cv.create_line(x-size*.16, y, x-size*.01, y+size*.16, fill='#ffcf4a', width=3)
        self.shop_buttons.append((x-size/2, y-size/2, x+size/2, y+size/2,
                                  lambda level=level: self.shop_back(level)))

    def _coin(self, x, y, radius):
        self.cv.create_oval(x-radius, y-radius, x+radius, y+radius,
                            fill='#f6a91b', outline='#ffe678', width=max(1.5, radius*.13))
        self.cv.create_oval(x-radius*.68, y-radius*.68, x+radius*.68, y+radius*.68,
                            outline='#d67812', width=max(1, radius*.09))
        self.cv.create_text(x, y+radius*.03, text='M', fill='#a95810',
                            font=self.front_font(radius*1.15, True))

    def _shop_header(self):
        w = self.cw
        header = self._shop_header_height()
        self.cv.create_rectangle(0, 0, w, header, fill='#082b22', width=0)
        self.cv.create_rectangle(0, header-3, w, header, fill='#d6b877', width=0)
        size = min(48, header*.55)
        self._shop_arrow(18+size/2, header/2, size, 1)
        cx = w*.44
        # Carrito geométrico relleno, reconocible incluso en pantallas angostas.
        self.cv.create_line(cx-84, header*.35, cx-75, header*.35, cx-70, header*.43,
                            fill='#e8d4a6', width=2.5)
        self.cv.create_polygon([cx-72, header*.42, cx-34, header*.42,
                                cx-40, header*.62, cx-65, header*.62],
                               fill='#e8d4a6', width=0)
        for offset in (0, 9, 18):
            self.cv.create_line(cx-66+offset, header*.45, cx-62+offset, header*.58,
                                fill='#082b22', width=1.1)
        self.cv.create_oval(cx-63, header*.66, cx-55, header*.74, fill='#f6a91b', width=0)
        self.cv.create_oval(cx-44, header*.66, cx-36, header*.74, fill='#f6a91b', width=0)
        self.cv.create_text(cx+24, header*.5, text='TIENDA', fill='#f8eed6',
                            font=self.front_font(min(36, w*.085), True))
        balance_x = w-18
        self.cv.create_text(balance_x-17, header*.5, text=f'{self.shop.balance:,}'.replace(',', '.'),
                            fill='#ffd45c', font=self.front_font(min(25, w*.059), True), anchor='e')
        self._coin(w-17, header*.5, min(14, w*.035))

    def _shop_button(self, cx, cy, width, height, text, action, color='#f0d39b', fg='#132d22', font=None):
        before = len(self.buttons)
        self.front_button(cx, cy, width, height, text, action, color, fg)
        entry = self.buttons.pop()
        if font is not None:
            # front_button ya ajusta el texto; font queda disponible para tarjetas personalizadas.
            pass
        self.shop_buttons.append(entry)

    def _shop_card(self, x, y, width, height, fill='#e8d7b5', outline='#796b4d'):
        def rgb(value):
            return tuple(int(value[i:i+2], 16)/255 for i in (1, 3, 5))
        with self.cv.canvas:
            Color(.012, .105, .082, .55)
            RoundedRectangle(pos=(x+2, self.ch-y-height-4), size=(width, height), radius=[10])
            Color(*rgb(outline), 1)
            RoundedRectangle(pos=(x, self.ch-y-height), size=(width, height), radius=[10])
            Color(*rgb(fill), 1)
            RoundedRectangle(pos=(x+1.2, self.ch-y-height+1.2), size=(width-2.4, height-2.4), radius=[9])
        self.cv.create_rectangle(x+1, y+9, x+5, y+height-9, fill='#d99d32', width=0)

    def _shop_root(self):
        w, h = self.cw, self.ch
        top = self._shop_header_height()+max(14, h*.022)
        bottom = h-max(14, h*.022)
        gap = max(12, h*.02)
        height = min((bottom-top-gap)/2, max(170, w*.78))
        y0 = top+((bottom-top)-(height*2+gap))/2
        margin = max(10, w*.035)
        for index, (label, subtitle, page, color) in enumerate((
            ('COSMÉTICOS', 'Auras · balones · accesorios · estadio', 'cosmetics', '#e6c98e'),
            ('PASIVAS', 'Siete mejoras permanentes para tu equipo', 'passives', '#a9d979'),
        )):
            y = y0+index*(height+gap)
            cy = y+height/2
            self._shop_card(margin, y, w-margin*2, height, color)
            rr = min(height*.30, w*.14)
            px, py = margin+w*.05+rr, cy
            self.cv.create_oval(px-rr, py-rr, px+rr, py+rr, fill='#184c34', outline='#fff2c9', width=max(2, rr*.08))
            if index == 0:
                # Chapita con trayectoria, contenida dentro del aro.
                self.cv.create_arc(px-rr*.74, py-rr*.74, px+rr*.74, py+rr*.74,
                                   start=20, extent=285, style='arc', outline='#d47824', width=max(3, rr*.11))
                cr = rr*.36
                self.cv.create_oval(px-cr, py-cr, px+cr, py+cr, fill='#f2cf4f', outline='#fff2c9', width=2)
            else:
                # Barras ascendentes inscritas en el aro (no sobresalen).
                span = rr*1.08
                bw = span/4*.68
                base = py+rr*.48
                for bar in range(4):
                    bh = rr*(.32+bar*.24)
                    x0 = px-span/2+bar*span/4+(span/4-bw)/2
                    self.cv.create_rectangle(x0, base-bh, x0+bw, base, fill='#f2cf4f', width=0)
            tx = (px+rr+w-margin)/2
            tw = w-margin-(px+rr)-16
            self.cv.create_text(tx, cy-height*.13, text=label, fill='#123d2c',
                                font=self.front_font(min(w*.095, height*.22, tw/(len(label)*.52)), True))
            self.cv.create_text(tx, cy+height*.17, text=subtitle, fill='#355344',
                                font=self.front_font(min(w*.045, height*.11)), width=tw)
            self.shop_buttons.append((margin, y, w-margin, y+height,
                                      lambda page=page: self.shop_go(page)))

    def _shop_cosmetics(self):
        w, h = self.cw, self.ch
        top = self._shop_header_height()+62
        gap = max(10, h*.016)
        height = min(170, (h-top-16-gap*3)/4)
        for index, (category, name, description) in enumerate(CATEGORIES):
            y = top+index*(height+gap)
            self._shop_card(12, y, w-24, height, '#e8d7b5')
            pr = min(height*.30, w*.10)
            px = 26+pr*1.25
            entry = next((e for e in catalog_for(category) if e.get('price')), catalog_for(category)[0])
            self._shop_preview(entry, px, y+height/2, pr)
            tx = px+pr*1.6+10
            avail = w-tx-44
            big = min(w*.07, height*.27)
            one_line = big*len(name)*.50 <= avail
            size = big if one_line else min(w*.056, height*.20)
            self.cv.create_text(tx, y+height*(.36 if one_line else .32), text=name, fill='#153c2c',
                                font=self.front_font(size, True), anchor='w', width=avail)
            self.cv.create_text(tx, y+height*(.70 if one_line else .80), text=description, fill='#526052',
                                font=self.front_font(min(w*.041, height*(.15 if one_line else .12))),
                                anchor='w', width=avail)
            self.cv.create_text(w-34, y+height/2, text='›', fill='#a26820',
                                font=self.front_font(min(52, height*.5), True))
            self.shop_buttons.append((12, y, w-12, y+height,
                                      lambda category=category: self.shop_go('category', category)))

    def _passive_bars(self, x, y, level, maximum, k=1.0):
        for index in range(maximum):
            height = (9+index*5)*k
            color = '#e5ad2f' if index < level else '#a9a58f'
            self.cv.create_rectangle(x+index*13*k, y-height, x+index*13*k+8*k, y,
                                     fill=color, outline='#625c48', width=.5)

    def _shop_passives(self):
        w = self.cw
        card_h = max(185, min(260, w*.56))
        k = card_h/158
        gap = 12
        content_top = self._shop_header_height()+62
        viewport_h = self.ch-content_top-12
        self.shop_max_scroll = max(0, len(PASSIVE_ORDER)*(card_h+gap)-viewport_h)
        self.shop_scroll = max(0, min(self.shop_scroll, self.shop_max_scroll))
        bw, bh = max(124, w*.34), max(42, card_h*.23)
        for index, key in enumerate(PASSIVE_ORDER):
            definition = PASSIVES[key]
            saved = self.shop.state['passives'][key]
            level = saved['level']
            y = content_top+index*(card_h+gap)-self.shop_scroll
            if y > self.ch or y+card_h < content_top:
                continue
            self._shop_card(10, y, w-20, card_h, '#e3d5b6')
            self.cv.create_text(26, y+card_h*.14, text=definition['name'], fill='#153c2c',
                                font=self.front_font(min(w*.066, 30), True), anchor='w', width=w-52)
            value = definition['values'][level]
            self.cv.create_text(26, y+card_h*.33, text=passive_display(key, value), fill='#9b5518',
                                font=self.front_font(min(w*.062, 29), True), anchor='w', width=w-52)
            self.cv.create_text(26, y+card_h*.53, text=definition['description'], fill='#4d5d50',
                                font=self.front_font(min(w*.039, 18)), anchor='w', width=w-bw-60)
            self._passive_bars(28, y+card_h*.84, level, definition['max_level'], k)
            self.cv.create_text(28+definition['max_level']*13*k+8, y+card_h*.80,
                                text=f'NIVEL {level}/{definition["max_level"]}', fill='#344a3b',
                                font=self.front_font(min(w*.042, 19), True), anchor='w')
            price = passive_price(level) if level < definition['max_level'] else None
            bx = w-22-bw/2
            by = y+card_h*.56 if level else y+card_h*.74
            if price is not None:
                self._shop_button(bx, by, bw, bh, f'MEJORAR · {price}',
                                  lambda key=key: self._buy_passive(key), '#e5ad2f')
            else:
                self.cv.create_text(bx, by, text='MÁXIMO', fill='#2a6c45',
                                    font=self.front_font(min(w*.06, 26), True))
            if level:
                self._shop_button(bx, y+card_h*.83, bw, bh*.86,
                                  'DESACTIVAR' if saved['enabled'] else 'ACTIVAR',
                                  lambda key=key: self._toggle_passive(key),
                                  '#47775a' if saved['enabled'] else '#b6ad96',
                                  '#ffffff' if saved['enabled'] else '#24372b')

    def _preview_team(self):
        from main import TEAMS
        team = getattr(self, 'user', None)
        return team if team in TEAMS else 'Brasil'

    def _shop_preview(self, entry, x, y, radius):
        """Miniatura que reutiliza exactamente el mismo dibujo del partido."""
        cv = self.cv
        category = entry['category']
        style = entry['style']
        now = time.monotonic()
        if category == 'aura':
            pulse = 1.25 + 0.1*math.sin(now*8)
            self.draw_aura_ring(entry['id'], x, y, radius*pulse, max(1.5, radius*.14), now)
            self._jersey(x, y, radius, self._preview_team(), num=10)
            return
        if category == 'ball':
            if style == 'invisible':
                cv.create_oval(x-radius, y-radius, x+radius, y+radius, outline='#858a83', width=2)
                cv.create_line(x-radius*.7, y+radius*.7, x+radius*.7, y-radius*.7, fill='#858a83', width=2)
                return
            if not self.draw_ball_style(entry['id'], x, y, radius*.85):
                r = radius*.85
                cv.create_oval(x-r, y-r, x+r, y+r, fill='#ffffff', outline='#222222', width=max(1, r*.09))
                cv.create_oval(x-r*.32, y-r*.32, x+r*.32, y+r*.32, fill='#172a20', width=0)
                for i in range(5):
                    a = i*math.tau/5-math.pi/2
                    px, py = x+math.cos(a)*r*.68, y+math.sin(a)*r*.68
                    cv.create_oval(px-r*.14, py-r*.14, px+r*.14, py+r*.14, fill='#172a20', width=0)
            return
        if category == 'accessory':
            self._jersey(x, y, radius, self._preview_team())
            self.draw_accessory(style, x, y, radius)
            return
        if category == 'appearance':
            self._jersey(x, y, radius, entry['team'], num=entry['dorsal'])
            self.draw_star_look(style, x, y, radius)
            return
        # Ambiente: miniatura de cancha con el mismo efecto del partido.
        x0, y0, x1, y1 = x-radius*1.2, y-radius*.9, x+radius*1.2, y+radius*.9
        cv.create_rectangle(x0, y0, x1, y1, fill='#3f9a55', width=0)
        for band in range(4):
            cv.create_rectangle(x0+band*radius*.6, y0, x0+band*radius*.6+radius*.3, y1, fill='#47a75e', width=0)
        cv.create_rectangle(x0, y0, x1, y1, fill='', outline='#ffffff', width=1)
        cv.create_line(x0, y, x1, y, fill='#ffffff', width=1)
        cv.create_oval(x-radius*.28, y-radius*.28, x+radius*.28, y+radius*.28, outline='#ffffff', width=1)
        if style == 'snow':
            cv.create_rectangle(x0, y0, x1, y1, fill='#dff6ff', width=0, alpha=.25)
            for i in range(9):
                fx = x0+((i*.618+now*.05) % 1)*(x1-x0)
                fy = y0+((i*.382+now*.12) % 1)*(y1-y0)
                self._snowflake(fx, fy, radius*.12)
        elif style == 'flowers':
            cv.create_rectangle(x0, y0, x1, y1, fill='#ff9ecf', width=0, alpha=.12)
            for fx, fy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1), (x, y)):
                self._flower(fx, fy, radius*.22)
        elif style == 'night':
            cv.create_rectangle(x0, y0, x1, y1, fill='#071122', width=0, alpha=.55)
            for fx, fy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                for step in range(4, 0, -1):
                    rr = radius*.09*step
                    cv.create_oval(fx-rr, fy-rr, fx+rr, fy+rr, fill='#fff4bd', width=0, alpha=.10)
                cv.create_oval(fx-radius*.06, fy-radius*.06, fx+radius*.06, fy+radius*.06, fill='#fff5c7', width=0)
        else:
            cv.create_rectangle(x0, y0, x1, y1, fill='#02050b', width=0)
            r = radius*.28
            cv.create_oval(x-r*2, y-r*2, x+r*2, y+r*2, fill='#ffe987', width=0, alpha=.10)
            self._jersey(x, y, r, self._preview_team())

    def _buy(self, item_id):
        result = self.shop_actions.buy(item_id)
        self._shop_result(result)

    def _buy_passive(self, key):
        result = self.shop_actions.buy_passive(key)
        self._shop_result(result)

    def _toggle_passive(self, key):
        result = self.shop_actions.toggle_passive(key)
        self._shop_result(result, success=False)

    def _equip(self, item_id):
        result = self.shop_actions.equip(item_id)
        self._shop_result(result, success=False)

    def _shop_result(self, result, success=True):
        if not result.get('ok'):
            self.shop_toast = (result.get('reason', 'No se pudo completar'), time.monotonic()+2.0)
        self.shop.refresh()
        self.render()

    def _shop_category_items(self):
        category = self.shop_category
        entries = catalog_for(category)
        w = self.cw
        card_h = max(150, min(215, w*.48))
        gap = 12
        content_top = self._shop_header_height()+100
        viewport_h = self.ch-content_top-12
        self.shop_max_scroll = max(0, len(entries)*(card_h+gap)-viewport_h)
        self.shop_scroll = max(0, min(self.shop_scroll, self.shop_max_scroll))
        pr = card_h*.22
        px = 16+card_h*.33
        tx = px+card_h*.33+8
        bw, bh = max(118, w*.31), max(42, card_h*.24)
        for index, entry in enumerate(entries):
            item_id = entry['id']
            y = content_top+index*(card_h+gap)-self.shop_scroll
            if y > self.ch or y+card_h < content_top:
                continue
            owned = self.shop.owned(item_id)
            active = self.shop.active(item_id)
            self._shop_card(8, y, w-16, card_h, '#eee0c2' if owned else '#d9c9aa')
            self._shop_preview(entry, px, y+card_h*.40, pr)
            self.cv.create_text(tx, y+card_h*.16, text=entry['name'], fill='#173c2c',
                                font=self.front_font(min(w*.056, 26), True), anchor='w', width=w-tx-22)
            self.cv.create_text(tx, y+card_h*.40, text=entry['description'], fill='#566052',
                                font=self.front_font(min(w*.037, 17)), anchor='w', width=w-tx-22)
            if owned:
                price_text = 'EQUIPADO' if active else 'DISPONIBLE'
            elif entry['price'] is None:
                price_text = 'PRECIO PENDIENTE'
            else:
                price_text = f'{entry["price"]} MONEDITAS'
            self.cv.create_text(tx, y+card_h*.62, text=price_text, fill='#a05a19' if not owned else '#34704a',
                                font=self.front_font(min(w*.045, 21), True), anchor='w', width=w-tx-22)
            small_w = min(card_h*.58, tx-22)
            if entry.get('customizable'):
                self._shop_button(px, y+card_h*.83, small_w, bh*.8, 'COLOR',
                                  lambda item_id=item_id: self._open_palette(item_id), '#313b35', '#ffffff')
            if entry.get('info'):
                self._shop_button(px, y+card_h*.83, small_w, bh*.8, 'INFO',
                                  lambda item_id=item_id: self._open_info(item_id), '#47775a', '#ffffff')
            bx, by = w-20-bw/2, y+card_h*.82
            if not owned:
                label = 'PENDIENTE' if entry['price'] is None else 'COMPRAR'
                self._shop_button(bx, by, bw, bh, label,
                                  lambda item_id=item_id: self._buy(item_id),
                                  '#b7aa8d' if entry['price'] is None else '#e5ad2f')
            else:
                self._shop_button(bx, by, bw, bh,
                                  'DESACTIVAR' if active else 'ACTIVAR',
                                  lambda item_id=item_id: self._equip(item_id),
                                  '#47775a' if active else '#d9b965',
                                  '#ffffff' if active else '#173c2c')

    def _open_palette(self, item_id):
        self.shop_palette = item_id
        self.render()

    def _open_info(self, item_id):
        self.shop_info = item_id
        self.render()

    def _shop_overlays(self):
        if self.shop_palette:
            width = min(320, self.cw*.88)
            cell = width/4
            height = cell*4+58
            x0, y0 = (self.cw-width)/2, (self.ch-height)/2
            self.cv.create_rectangle(0, 0, self.cw, self.ch, fill='#000000', width=0, alpha=.65)
            self.cv.create_rectangle(x0, y0, x0+width, y0+height, fill='#101312', outline='#e7c36c', width=2)
            self.cv.create_text(self.cw/2, y0+25, text='ELIGE UN COLOR', fill='#f5e7c7',
                                font=self.front_font(20, True))
            for index, (name, color) in enumerate(PALETTE):
                col, row = index%4, index//4
                cx, cy = x0+(col+.5)*cell, y0+58+(row+.5)*cell
                radius = cell*.30
                self.cv.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                    fill=color, outline='#ffffff', width=1.5)
                self.shop_buttons.append((cx-cell/2, cy-cell/2, cx+cell/2, cy+cell/2,
                                          lambda color=color: self._select_palette(color)))
        elif self.shop_info:
            entry = ITEMS[self.shop_info]
            width, height = min(340, self.cw*.9), 190
            x0, y0 = (self.cw-width)/2, (self.ch-height)/2
            self.cv.create_rectangle(0, 0, self.cw, self.ch, fill='#000000', width=0, alpha=.65)
            self._shop_card(x0, y0, width, height, '#e8d7b5')
            self.cv.create_text(self.cw/2, y0+35, text='REQUISITOS', fill='#173c2c',
                                font=self.front_font(25, True))
            self.cv.create_text(self.cw/2, y0+88,
                                text=f"Selección: {entry['team']}\nDorsal obligatorio: {entry['dorsal']}\nEl dorsal se fija al entrar al partido.",
                                fill='#435447', font=self.front_font(17), width=width-36)
            self._shop_button(self.cw/2, y0+155, 120, 36, 'ENTENDIDO',
                              lambda: self._close_shop_overlay(), '#d9b965')

        message, until = self.shop_toast
        if message and time.monotonic() < until:
            self.cv.create_rectangle(15, self.ch-55, self.cw-15, self.ch-15, fill='#14271f', width=0, alpha=.95)
            self.cv.create_text(self.cw/2, self.ch-35, text=message, fill='#ffe1a0',
                                font=self.front_font(15), width=self.cw-40)

    def _select_palette(self, color):
        result = self.shop.set_aura_color(self.shop_palette, color)
        self.shop_palette = None
        self._shop_result(result, success=False)

    def _close_shop_overlay(self):
        self.shop_info = None
        self.render()

    def draw_shop(self):
        self.cv.delete('all')
        self.buttons = []
        self.shop_buttons = []
        self.cv.create_rectangle(0, 0, self.cw, self.ch, fill='#0b3024', width=0)
        # Franjas deportivas discretas solo en la zona de contenido.
        for index in range(7):
            self.cv.create_rectangle(index*self.cw/7, self._shop_header_height(),
                                     index*self.cw/7+self.cw/14, self.ch,
                                     fill='#103a2a', width=0)
        offset = 0
        if self.shop_transition:
            progress = min(1, (time.monotonic()-self.shop_transition['start'])/self.shop_transition['duration'])
            ease = 1-(1-progress)**3
            offset = self.shop_transition['direction']*self.cw*(1-ease)
        with self.cv.canvas:
            PushMatrix()
            Translate(offset, 0)
        try:
            if self.shop_page == 'root':
                self._shop_root()
            elif self.shop_page == 'cosmetics':
                self._shop_cosmetics()
            elif self.shop_page == 'passives':
                self._shop_passives()
            else:
                self._shop_category_items()
        finally:
            with self.cv.canvas:
                PopMatrix()
        # Se dibujan al final: ninguna tarjeta desplazada puede tapar la cabecera
        # ni interceptar los toques de las flechas jerárquicas.
        self._shop_header()
        depth = self._shop_depth()
        size = 38
        for level in range(2, depth+1):
            self._shop_arrow(19+size/2, self._shop_header_height()+22+(level-2)*43, size, level)
        self._shop_overlays()

    # ---------- toques y scroll táctil
    def on_press(self, ev):
        if getattr(self, 'shop', None) and self.state == 'shop':
            self.shop_touch = {'x': ev.x, 'y': ev.y, 'last_y': ev.y, 'action': None, 'moved': False}
            if not self.shop_transition:
                for x0, y0, x1, y1, action in reversed(self.shop_buttons):
                    if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                        self.shop_touch['action'] = action
                        self.front_press = (x0, y0, x1, y1, time.monotonic())
                        break
            return
        return super().on_press(ev)

    def on_motion(self, ev):
        if getattr(self, 'shop', None) and self.state == 'shop':
            if self.shop_touch:
                touch = self.shop_touch
                if abs(ev.y-touch['y']) > 8:
                    touch['moved'] = True
                    touch['action'] = None
                if touch['moved'] and not self.shop_palette and not self.shop_info:
                    self.shop_scroll = max(0, min(self.shop_max_scroll, self.shop_scroll-(ev.y-touch['last_y'])))
                touch['last_y'] = ev.y
                self.render()
            return
        return super().on_motion(ev)

    def on_release(self, ev):
        if getattr(self, 'shop', None) and self.state == 'shop':
            touch, self.shop_touch = self.shop_touch, None
            if touch and touch['action'] and not touch['moved']:
                touch['action']()
            return
        return super().on_release(ev)

    # ---------- animación sobre victoria amistosa o campeonato
    def draw_reward_overlay(self):
        animation = getattr(self, 'reward_animation', None)
        if not animation or self.state in ('home', 'shop', 'loading'):
            return
        now = time.monotonic()
        elapsed = now-animation['start']
        if elapsed < 0:
            return
        progress = max(0, min(1, elapsed/animation['duration']))
        ease = progress*progress*(3-2*progress)
        value = round(animation['from']+(animation['to']-animation['from'])*ease)
        if value != animation['shown'] and progress < 1 and int(elapsed*9) != animation.get('tick'):
            animation['tick'] = int(elapsed*9)
            animation['shown'] = value
            self.shop_audio.coin_tick()
        appear = min(1, elapsed/.45)
        width = min(420, self.cw*.9)
        height = min(130, self.ch*.15)*(.85+.15*appear)
        x0 = (self.cw-width)/2
        y0 = self.ch*.715-height/2
        pulse = 1+.04*math.sin(now*5)
        self._shop_card(x0, y0, width, height, '#eac35f', '#fff0ad')
        cr = height*.30
        self._coin(x0+cr+18, y0+height/2, cr*pulse)
        tx = x0+cr*2+32
        self.cv.create_text(tx, y0+height*.30,
                            text=f'+{animation["amount"]} MONEDITAS', fill='#7b4211',
                            font=self.front_font(min(24, self.cw*.055), True), anchor='w')
        self.cv.create_text(tx, y0+height*.68, text=f'{value:,}'.replace(',', '.'),
                            fill='#173c2c', font=self.front_font(min(44, self.cw*.10), True), anchor='w')
        for index in range(8):
            angle = now*1.3+index*math.tau/8
            x = self.cw/2+math.cos(angle)*width*.53
            y = y0+height/2+math.sin(angle)*height*.66
            self.cv.create_polygon(self._star_points(x, y, 6, 2.6), fill='#ffe990', width=0)

    # Botón de fin de torneo (campeón o derrota): mismo destino, mayor tamaño táctil.
    def button(self, cx, cy, w, h, text, cmd, *args, **kwargs):
        if text == 'VOLVER AL MENÚ' and self.state not in ('match', 'pens', 'shop'):
            new_h = min(84, max(60, self.ch*.08))
            w = min(self.cw*.88, 460)
            if cy > self.ch-h:            # botón inferior: se mantiene pegado abajo
                cy = self.ch-new_h/2-max(16, self.ch*.025)
            h = new_h
            kwargs['font'] = self.F(min(3.2, new_h*.36/max(1, self.u)))
        return super().button(cx, cy, w, h, text, cmd, *args, **kwargs)
