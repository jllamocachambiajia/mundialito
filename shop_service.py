"""Compras, equipamiento y reglas de progreso sobre el LocalStore existente."""
from shop_data import (ITEMS, PASSIVES, PALETTE_HEX, default_state, normalize_state,
                       passive_price)


class ShopService:
    def __init__(self, store):
        self.store = store
        self.state = normalize_state(store.get('shop_v1', default_state()))

    def refresh(self):
        self.state = normalize_state(self.store.get('shop_v1', default_state()))
        return self.state

    @property
    def balance(self):
        return self.state['balance']

    def owned(self, item_id):
        return item_id in self.state['owned']

    def active(self, item_id):
        entry = ITEMS[item_id]
        category = entry['category']
        if category == 'aura':
            return self.state['aura'] == item_id
        if category == 'ball':
            return self.state['ball'] == item_id
        if category == 'accessory':
            return item_id in self.state['accessories']
        if category == 'appearance':
            return self.state['appearance'] == item_id
        if category == 'environment':
            return self.state['environment'] == item_id
        return False

    def _change(self, callback):
        def normalized_transaction(raw):
            data = normalize_state(raw)
            result = callback(data)
            raw.clear()
            raw.update(data)
            return result
        result = self.store.mutate_shop(normalized_transaction)
        self.refresh()
        return result

    def buy(self, item_id):
        entry = ITEMS.get(item_id)
        if entry is None:
            return {'ok': False, 'reason': 'Artículo desconocido'}
        if entry['price'] is None:
            return {'ok': False, 'reason': 'Precio pendiente de confirmación'}
        def transaction(data):
            if item_id in data['owned']:
                return {'ok': False, 'reason': 'Ya lo tienes'}
            if data['balance'] < entry['price']:
                return {'ok': False, 'reason': 'No tienes moneditas suficientes'}
            data['balance'] -= entry['price']
            data['owned'].append(item_id)
            data['owned'] = sorted(set(data['owned']))
            return {'ok': True, 'kind': 'cosmetic', 'amount': -entry['price'],
                    'balance': data['balance']}
        return self._change(transaction)

    def buy_passive(self, key):
        definition = PASSIVES.get(key)
        if definition is None:
            return {'ok': False, 'reason': 'Pasiva desconocida'}
        def transaction(data):
            saved = data['passives'][key]
            if saved['level'] >= definition['max_level']:
                return {'ok': False, 'reason': 'Nivel máximo alcanzado'}
            price = passive_price(saved['level'])
            if data['balance'] < price:
                return {'ok': False, 'reason': 'No tienes moneditas suficientes'}
            data['balance'] -= price
            saved['level'] += 1
            saved['enabled'] = True
            data['passives'][key] = saved
            return {'ok': True, 'kind': 'passive', 'amount': -price,
                    'level': saved['level'], 'balance': data['balance']}
        return self._change(transaction)

    def toggle_passive(self, key):
        def transaction(data):
            saved = data['passives'][key]
            if not saved['level']:
                return {'ok': False, 'reason': 'Compra primero el nivel 1'}
            saved['enabled'] = not saved['enabled']
            data['passives'][key] = saved
            return {'ok': True, 'kind': 'toggle', 'enabled': saved['enabled']}
        return self._change(transaction)

    def equip(self, item_id):
        entry = ITEMS.get(item_id)
        if entry is None:
            return {'ok': False, 'reason': 'Artículo desconocido'}
        def transaction(data):
            if item_id not in data['owned']:
                return {'ok': False, 'reason': 'Primero debes comprarlo'}
            category = entry['category']
            if category == 'appearance' and data['country'] != entry['team']:
                return {'ok': False, 'reason': f"Requiere jugar con {entry['team']}"}
            if category == 'aura':
                data['aura'] = 'aura_none' if data['aura'] == item_id else item_id
            elif category == 'ball':
                data['ball'] = 'ball_classic' if data['ball'] == item_id else item_id
            elif category == 'accessory':
                selected = set(data['accessories'])
                selected.symmetric_difference_update((item_id,))
                data['accessories'] = sorted(selected)
            elif category == 'appearance':
                data['appearance'] = None if data['appearance'] == item_id else item_id
            elif category == 'environment':
                data['environment'] = None if data['environment'] == item_id else item_id
            return {'ok': True, 'kind': 'equip'}
        # active se calcula después de guardar para reflejar el estado real.
        result = self._change(transaction)
        if result.get('ok'):
            result['active'] = self.active(item_id)
        return result

    def set_aura_color(self, item_id, color):
        if color not in PALETTE_HEX or not ITEMS.get(item_id, {}).get('customizable'):
            return {'ok': False, 'reason': 'Color no disponible'}
        def transaction(data):
            if item_id not in data['owned']:
                return {'ok': False, 'reason': 'Primero debes comprarlo'}
            data['aura_colors'][item_id] = color
            return {'ok': True, 'kind': 'color'}
        return self._change(transaction)

    def set_country(self, country):
        def transaction(data):
            data['country'] = country
            appearance = data['appearance']
            if appearance and ITEMS[appearance]['team'] != country:
                data['appearance'] = None
            return {'ok': True, 'kind': 'country'}
        return self._change(transaction)

    def reward(self, transaction_id, kind, amount):
        result = self.store.claim_reward(transaction_id, kind, amount)
        self.refresh()
        return result

    def passive_value(self, key):
        definition = PASSIVES[key]
        saved = self.state['passives'][key]
        return definition['values'][saved['level'] if saved['enabled'] else 0]

    def appearance_for(self, country):
        item_id = self.state['appearance']
        if item_id and ITEMS[item_id]['team'] == country and self.owned(item_id):
            return ITEMS[item_id]
        return None


class ShopController:
    """El sonido depende del resultado confirmado, nunca del simple toque."""
    def __init__(self, service, audio=None):
        self.service = service
        self.audio = audio

    def buy(self, item_id):
        result = self.service.buy(item_id)
        if result.get('ok') and self.audio:
            self.audio.purchase('cosmetic')
        return result

    def buy_passive(self, key):
        result = self.service.buy_passive(key)
        if result.get('ok') and self.audio:
            self.audio.purchase('passive')
        return result

    def equip(self, item_id):
        return self.service.equip(item_id)  # Sin sonido de compra.

    def toggle_passive(self, key):
        return self.service.toggle_passive(key)  # Sin sonido de compra.
