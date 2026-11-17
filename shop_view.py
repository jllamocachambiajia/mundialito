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
            'start': time.monotonic(), 'duration': 2.15,
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
            if elapsed >= self.reward_animation['duration']+.65:
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
        top = self._shop_header_height()+24
        available = h-top-35
        height = min(150, available*.32)
        for index, (label, subtitle, page, color) in enumerate((
            ('COSMÉTICOS', 'Auras · balones · accesorios · estadio', 'cosmetics', '#e6c98e'),
            ('PASIVAS', 'Siete mejoras permanentes para tu equipo', 'passives', '#a9d979'),
        )):
            cy = top+available*(.28+index*.43)
            self._shop_card(w*.07, cy-height/2, w*.86, height, color)
            # Emblema futbolístico: chapita con trayectoria.
            px, py = w*.20, cy
            rr = min(36, height*.25)
            self.cv.create_oval(px-rr, py-rr, px+rr, py+rr, fill='#184c34', outline='#fff2c9', width=2)
            if index == 0:
                self.cv.create_arc(px-rr*1.35, py-rr*1.35, px+rr*1.35, py+rr*1.35,
                                   start=20, extent=285, style='arc', outline='#d47824', width=4)
            else:
                for bar in range(4):
                    bh = rr*(.35+bar*.36)
                    self.cv.create_rectangle(px-rr+bar*rr*.48, py+rr-bh,
                                             px-rr+bar*rr*.48+rr*.25, py+rr, fill='#f2cf4f', width=0)
            self.cv.create_text(w*.60, cy-height*.12, text=label, fill='#123d2c',
                                font=self.front_font(min(32, w*.072), True))
            self.cv.create_text(w*.60, cy+height*.19, text=subtitle, fill='#355344',
                                font=self.front_font(min(14, w*.032)), width=w*.56)
            self.shop_buttons.append((w*.07, cy-height/2, w*.93, cy+height/2,
                                      lambda page=page: self.shop_go(page)))

    def _shop_cosmetics(self):
        w, h = self.cw, self.ch
        top = self._shop_header_height()+62
        gap = 12
        height = min(92, (h-top-28-gap*3)/4)
        for index, (category, name, description) in enumerate(CATEGORIES):
            y = top+index*(height+gap)
            self._shop_card(14, y, w-28, height, '#e8d7b5')
            self.cv.create_text(32, y+height*.34, text=name, fill='#153c2c',
                                font=self.front_font(min(23, w*.053), True), anchor='w', width=w-100)
            self.cv.create_text(32, y+height*.70, text=description, fill='#526052',
                                font=self.front_font(min(13, w*.031)), anchor='w', width=w-100)
            self.cv.create_text(w-35, y+height/2, text='›', fill='#a26820',
                                font=self.front_font(38, True))
            self.shop_buttons.append((14, y, w-14, y+height,
                                      lambda category=category: self.shop_go('category', category)))

    def _passive_bars(self, x, y, level, maximum):
        for index in range(maximum):
            height = 9+index*5
            color = '#e5ad2f' if index < level else '#a9a58f'
            self.cv.create_rectangle(x+index*13, y-height, x+index*13+8, y,
                                     fill=color, outline='#625c48', width=.5)

    def _shop_passives(self):
        w = self.cw
        card_h = 158
        content_top = self._shop_header_height()+62
        viewport_h = self.ch-content_top-12
        self.shop_max_scroll = max(0, len(PASSIVE_ORDER)*(card_h+12)-viewport_h)
        self.shop_scroll = max(0, min(self.shop_scroll, self.shop_max_scroll))
        for index, key in enumerate(PASSIVE_ORDER):
            definition = PASSIVES[key]
            saved = self.shop.state['passives'][key]
            level = saved['level']
            y = content_top+index*(card_h+12)-self.shop_scroll
            if y > self.ch or y+card_h < content_top:
                continue
            self._shop_card(12, y, w-24, card_h, '#e3d5b6')
            self.cv.create_text(28, y+23, text=definition['name'], fill='#153c2c',
                                font=self.front_font(min(22, w*.051), True), anchor='w', width=w*.60)
            value = definition['values'][level]
            display = passive_display(key, value)
            self.cv.create_text(28, y+56, text=display, fill='#9b5518',
                                font=self.front_font(min(23, w*.054), True), anchor='w', width=w-56)
            self.cv.create_text(28, y+83, text=definition['description'], fill='#4d5d50',
                                font=self.front_font(min(12, w*.029)), anchor='w', width=max(105, w-190))
            self._passive_bars(30, y+125, level, definition['max_level'])
            self.cv.create_text(28+definition['max_level']*13+8, y+119,
                                text=f'NIVEL {level}/{definition["max_level"]}', fill='#344a3b',
                                font=self.front_font(13, True), anchor='w')
            price = passive_price(level) if level < definition['max_level'] else None
            bx, by = w-79, y+102
            if price is not None:
                self._shop_button(bx, by, 112, 38, f'MEJORAR · {price}',
                                  lambda key=key: self._buy_passive(key), '#e5ad2f')
            else:
                self.cv.create_text(bx, by, text='MÁXIMO', fill='#2a6c45',
                                    font=self.front_font(18, True))
            if level:
                self._shop_button(bx, y+139, 112, 30,
                                  'DESACTIVAR' if saved['enabled'] else 'ACTIVAR',
                                  lambda key=key: self._toggle_passive(key),
                                  '#47775a' if saved['enabled'] else '#b6ad96',
                                  '#ffffff' if saved['enabled'] else '#24372b')

    def _shop_preview(self, entry, x, y, radius):
        cv = self.cv
        category = entry['category']
        style = entry['style']
        if category == 'aura':
            color = entry.get('color', self.shop.state['aura_colors'].get(entry['id'], '#e6ad31'))
            cv.create_oval(x-radius*1.3, y-radius*1.3, x+radius*1.3, y+radius*1.3,
                           outline=color, width=4, alpha=.9)
            if style in ('coins', 'hearts', 'stars'):
                for index in range(4):
                    angle = index*math.tau/4
                    px, py = x+math.cos(angle)*radius*1.35, y+math.sin(angle)*radius*1.35
                    if style == 'hearts':
                        self._heart(px, py, radius*.35, color)
                    elif style == 'stars':
                        cv.create_polygon(self._star_points(px, py, radius*.23, radius*.1), fill=color, width=0)
                    else:
                        self._coin(px, py, radius*.18)
            elif style in ('gradient', 'duo', 'rainbow'):
                colors = ('#f25c54', '#ffd83d', '#59dc72', '#56d9ff', '#a879ff')
                for index in range(8):
                    cv.create_arc(x-radius*1.3, y-radius*1.3, x+radius*1.3, y+radius*1.3,
                                  start=index*45, extent=32, style='arc',
                                  outline=colors[index%len(colors)], width=4)
            cv.create_oval(x-radius, y-radius, x+radius, y+radius, fill='#2d8c52', outline='#ffffff', width=2)
            return
        if category == 'ball':
            if style == 'invisible':
                cv.create_oval(x-radius, y-radius, x+radius, y+radius, outline='#858a83', width=2)
                cv.create_line(x-radius*.7, y+radius*.7, x+radius*.7, y-radius*.7, fill='#858a83', width=2)
                return
            if style in ('american', 'rugby'):
                cv.create_oval(x-radius*.7, y-radius*1.15, x+radius*.7, y+radius*1.15,
                               fill='#995632', outline='#ffffff', width=2)
            else:
                colors = {'tennis': '#d8ef42', 'basket': '#ed8a32', 'bowling': '#333846',
                          'billiard': '#315bd8', 'cricket': '#a84235'}
                cv.create_oval(x-radius, y-radius, x+radius, y+radius,
                               fill=entry.get('color', colors.get(style, '#f7f7f2')), outline='#343b36', width=2)
                if style == 'classic':
                    cv.create_oval(x-radius*.25, y-radius*.25, x+radius*.25, y+radius*.25, fill='#222222', width=0)
                elif style in ('basket', 'baseball', 'tennis', 'volley', 'cricket'):
                    cv.create_arc(x-radius*.85, y-radius*.85, x+radius*.85, y+radius*.85,
                                  start=30, extent=240, style='arc', outline='#7f4938', width=2)
            return
        if category in ('accessory', 'appearance'):
            cv.create_oval(x-radius, y-radius, x+radius, y+radius,
                           fill='#3b9b5d', outline='#ffffff', width=2)
            if category == 'appearance':
                cv.create_arc(x-radius*.8, y-radius*.9, x+radius*.8, y+radius*.1,
                              start=0, extent=180, style='arc', outline='#2b211d', width=5)
                cv.create_text(x, y+radius*.25, text=str(entry['dorsal']), fill='#ffffff',
                               font=self.front_font(radius*.8, True))
            elif style == 'party_hat':
                cv.create_polygon([x-radius*.7, y-radius*.6, x+radius*.5, y-radius*.6,
                                   x-radius*.1, y-radius*1.7], fill='#ffbf3f', width=0)
            elif style == 'moustache':
                cv.create_arc(x-radius*.6, y, x+radius*.6, y+radius*.6,
                              start=180, extent=180, style='arc', outline='#2b211d', width=4)
            elif style == 'monocle':
                cv.create_oval(x, y-radius*.45, x+radius*.65, y+radius*.2, outline='#d9a82e', width=3)
            elif style == 'sunglasses':
                cv.create_rectangle(x-radius*.7, y-radius*.35, x+radius*.7, y+radius*.05, fill='#20242b', width=0)
            else:
                cv.create_rectangle(x-radius*.65, y, x+radius*.65, y+radius*.25, fill='#efc39a', width=0)
            return
        # Ambiente: miniatura de cancha.
        cv.create_rectangle(x-radius*1.2, y-radius*.85, x+radius*1.2, y+radius*.85,
                            fill='#163d2c' if style in ('night', 'visibility') else '#4cae62', width=0)
        cv.create_rectangle(x-radius*1.2, y-radius*.85, x+radius*1.2, y+radius*.85,
                            fill='', outline='#ffffff', width=1)
        if style == 'snow':
            self._snowflake(x, y, radius*.5)
        elif style == 'flowers':
            self._flower(x, y, radius*.5)
        elif style == 'night':
            for dx in (-.8, .8):
                self._coin(x+radius*dx, y-radius*.45, radius*.12)
        else:
            cv.create_oval(x-radius*.45, y-radius*.45, x+radius*.45, y+radius*.45,
                           fill='#f2d55c', width=0, alpha=.65)

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
        card_h = 126
        content_top = self._shop_header_height()+105
        viewport_h = self.ch-content_top-12
        self.shop_max_scroll = max(0, len(entries)*(card_h+10)-viewport_h)
        self.shop_scroll = max(0, min(self.shop_scroll, self.shop_max_scroll))
        for index, entry in enumerate(entries):
            item_id = entry['id']
            y = content_top+index*(card_h+10)-self.shop_scroll
            if y > self.ch or y+card_h < content_top:
                continue
            self._shop_card(10, y, self.cw-20, card_h,
                            '#eee0c2' if self.shop.owned(item_id) else '#d9c9aa')
            self._shop_preview(entry, 49, y+48, 25)
            name_size = min(18, self.cw*.042)
            self.cv.create_text(87, y+20, text=entry['name'], fill='#173c2c',
                                font=self.front_font(name_size, True), anchor='w', width=self.cw-195)
            self.cv.create_text(87, y+47, text=entry['description'], fill='#566052',
                                font=self.front_font(min(11, self.cw*.027)), anchor='w', width=self.cw-195)
            owned = self.shop.owned(item_id)
            active = self.shop.active(item_id)
            if owned:
                price_text = 'EQUIPADO' if active else 'DISPONIBLE'
            elif entry['price'] is None:
                price_text = 'PRECIO PENDIENTE'
            else:
                price_text = f'{entry["price"]} MONEDITAS'
            self.cv.create_text(87, y+78, text=price_text, fill='#a05a19' if not owned else '#34704a',
                                font=self.front_font(13, True), anchor='w', width=self.cw-195)
            if entry.get('customizable'):
                self._shop_button(49, y+103, 65, 25, 'COLOR',
                                  lambda item_id=item_id: self._open_palette(item_id), '#313b35', '#ffffff')
            if entry.get('info'):
                self._shop_button(49, y+103, 65, 25, 'INFO',
                                  lambda item_id=item_id: self._open_info(item_id), '#47775a', '#ffffff')
            if not owned:
                label = 'PENDIENTE' if entry['price'] is None else 'COMPRAR'
                self._shop_button(self.cw-66, y+96, 100, 38, label,
                                  lambda item_id=item_id: self._buy(item_id),
                                  '#b7aa8d' if entry['price'] is None else '#e5ad2f')
            else:
                self._shop_button(self.cw-66, y+96, 100, 38,
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
        progress = max(0, min(1, elapsed/animation['duration']))
        ease = 1-(1-progress)**3
        value = round(animation['from']+(animation['to']-animation['from'])*ease)
        if value != animation['shown'] and progress < 1:
            animation['shown'] = value
            self.shop_audio.coin_tick()
        width = min(340, self.cw*.88)
        height = min(104, self.ch*.16)
        x0, y0 = (self.cw-width)/2, 14
        pulse = 1+.025*math.sin(now*8)
        self._shop_card(x0, y0, width, height, '#eac35f', '#fff0ad')
        self._coin(x0+42, y0+height/2, 24*pulse)
        self.cv.create_text(x0+82, y0+height*.31,
                            text=f'+{animation["amount"]} MONEDITAS', fill='#7b4211',
                            font=self.front_font(min(18, self.cw*.043), True), anchor='w')
        self.cv.create_text(x0+82, y0+height*.69, text=f'{value:,}'.replace(',', '.'),
                            fill='#173c2c', font=self.front_font(min(34, self.cw*.08), True), anchor='w')
        for index in range(8):
            angle = now*1.3+index*math.tau/8
            x = self.cw/2+math.cos(angle)*width*.53
            y = y0+height/2+math.sin(angle)*height*.66
            self.cv.create_polygon(self._star_points(x, y, 4.5, 2), fill='#ffe990', width=0)
