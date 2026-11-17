"""Catálogo y reglas puras de la tienda. No depende de Kivy ni del motor físico."""
from copy import deepcopy

PALETTE = [
    ('Blanco', '#ffffff'), ('Amarillo', '#ffd83d'), ('Naranja', '#ff8a32'),
    ('Rojo', '#f04444'), ('Rosa', '#ff73b9'), ('Violeta', '#a879ff'),
    ('Azul', '#4388ff'), ('Celeste', '#56d9ff'), ('Turquesa', '#35e4c2'),
    ('Verde', '#59dc72'), ('Lima', '#b9ed55'), ('Dorado', '#d9a82e'),
    ('Marrón', '#8c5a3c'), ('Gris claro', '#b8c0ca'), ('Gris', '#59616c'),
    ('Negro', '#111318'),
]
PALETTE_HEX = tuple(color for _, color in PALETTE)


def item(item_id, category, name, description, price, **extra):
    return dict(id=item_id, category=category, name=name, description=description,
                price=price, **extra)


ITEMS = {}
def add(*args, **kwargs):
    entry = item(*args, **kwargs)
    ITEMS[entry['id']] = entry


add('aura_none', 'aura', 'SIN AURA', 'Chapitas limpias, sin resplandor.', 0, style='none')
for index, (name, color) in enumerate(PALETTE):
    add(f'aura_color_{index:02d}', 'aura', f'AURA {name.upper()}',
        'Resplandor circular gratuito.', 0, style='solid', color=color)
for item_id, name, style in (
    ('aura_coins', 'MONEDITAS', 'coins'),
    ('aura_hearts', 'CORAZONCITOS', 'hearts'),
    ('aura_stars', 'ESTRELLITAS', 'stars'),
    ('aura_gradient', 'DEGRADADOS', 'gradient'),
    ('aura_duo', 'COMBINACIONES', 'duo'),
):
    add(item_id, 'aura', name, 'Diseño especial para el contorno de tus chapitas.',
        500, style=style, customizable=style in ('coins', 'hearts', 'stars'))
add('aura_rainbow', 'aura', 'ARCOÍRIS ANIMADO',
    'Remolino continuo con transiciones progresivas de color.', 1000, style='rainbow')

add('ball_classic', 'ball', 'BALÓN CLÁSICO', 'El diseño original del partido.', 0, style='classic')
for index, (name, color) in enumerate(PALETTE):
    add(f'ball_color_{index:02d}', 'ball', f'BALÓN {name.upper()}',
        'Color liso. Física y colisión originales.', 0, style='solid', color=color)
for item_id, name, style in (
    ('ball_american', 'FÚTBOL AMERICANO', 'american'),
    ('ball_tennis', 'TENIS', 'tennis'), ('ball_basket', 'BÁSQUETBOL', 'basket'),
    ('ball_baseball', 'BÉISBOL', 'baseball'), ('ball_volley', 'VOLEIBOL', 'volley'),
    ('ball_golf', 'GOLF', 'golf'), ('ball_rugby', 'RUGBY', 'rugby'),
    ('ball_bowling', 'BOLICHE', 'bowling'), ('ball_billiard', 'BILLAR', 'billiard'),
    ('ball_cricket', 'CRÍQUET', 'cricket'),
):
    add(item_id, 'ball', name, 'Diseño deportivo con las dimensiones físicas intactas.',
        200, style=style)
add('ball_invisible', 'ball', 'BALÓN INVISIBLE',
    'Oculta solo el dibujo; el balón sigue existiendo y colisionando.', None,
    style='invisible', pending=True)

for item_id, name, price, style in (
    ('acc_moustache', 'MOSTACHO', 400, 'moustache'),
    ('acc_party_hat', 'SOMBRERO DE FIESTA', 600, 'party_hat'),
    ('acc_monocle', 'MONÓCULO', 400, 'monocle'),
    ('acc_sunglasses', 'LENTES DE SOL', 200, 'sunglasses'),
    ('acc_bandaids', 'DOS CURITAS', 100, 'bandaids'),
):
    add(item_id, 'accessory', name, 'Accesorio decorativo para cualquier selección.',
        price, style=style)
for item_id, name, price, team, dorsal, style in (
    ('star_messi', 'APARIENCIA 10 CELESTE', 2000, 'Argentina', 10, 'messi'),
    ('star_neymar', 'APARIENCIA 10 VERDE', 1200, 'Brasil', 10, 'neymar'),
    ('star_ronaldo', 'APARIENCIA 7 ROJA', 2000, 'Portugal', 7, 'ronaldo'),
    ('star_mbappe', 'APARIENCIA 10 AZUL', 1200, 'Francia', 10, 'mbappe'),
):
    add(item_id, 'appearance', name,
        f'Diseño original estilizado. Solo {team}; dorsal fijo {dorsal}.',
        price, style=style, team=team, dorsal=dorsal, info=True)

for item_id, name, price, style, description in (
    ('env_snow', 'NIEVE', 600, 'snow', 'Copos, hielo y marcador helado.'),
    ('env_flowers', 'FLORES', 600, 'flowers', 'Detalles rosados y una cancha ligeramente teñida.'),
    ('env_night', 'NOCHE', 600, 'night', 'Cuatro faroles y zonas de luz localizada.'),
    ('env_visibility', 'VISIBILIDAD LIMITADA', 800, 'visibility',
     'Oscuridad opcional: solo tus auras revelan tus chapitas.'),
):
    add(item_id, 'environment', name, description, price, style=style)

CATEGORIES = (
    ('aura', 'AURAS', 'Colores y diseños animados'),
    ('ball', 'BALONES PERSONALIZADOS', 'Deportes y colores, sin cambios físicos'),
    ('accessory', 'ACCESORIOS Y APARIENCIAS', 'Detalles decorativos originales'),
    ('environment', 'AMBIENTES DE ESTADIO', 'Nieve, flores, noche y visibilidad'),
)

PASSIVES = {
    'power': dict(name='POTENCIA', max_level=5,
                  values=(1.0, 1.05, 1.10, 1.15, 1.20, 1.25),
                  description='Potencia de tus disparos normales.'),
    'effect': dict(name='TIRO CON EFECTO', max_level=5,
                   values=(1.5, 1.6, 1.7, 1.8, 1.9, 2.0),
                   description='Potencia máxima de tu habilidad de fuego.'),
    'keeper': dict(name='GRANDEZA DEL ARQUERO', max_level=4,
                   values=(1.0, 1.125, 1.25, 1.375, 1.5),
                   description='Diámetro de tu arquero durante el partido.'),
    'slide': dict(name='CONTROL DE DESLIZAMIENTO', max_level=4,
                  values=(1.0, .9, .8, .7, .6),
                  description='Deslizamiento restante de tus chapitas.'),
    'recovery': dict(name='RECUPERACIÓN RÁPIDA', max_level=4,
                     values=(0.0, .05, .10, .15, .20),
                     description='Reducción de recarga de tus habilidades especiales.'),
    'impact': dict(name='RESISTENCIA AL IMPACTO', max_level=4,
                   values=(0.0, .05, .10, .15, .20),
                   description='Menos desplazamiento por choques entre chapitas.'),
    'shot': dict(name='RECARGA DE DISPARO', max_level=5,
                 values=(1.0, .95, .90, .85, .80, .75),
                 description='Intervalo mínimo entre tus disparos.'),
}
PASSIVE_ORDER = tuple(PASSIVES)


def passive_price(level):
    """Precio del nivel siguiente: redondeo comercial tras cada incremento del 20 %."""
    if level < 0 or level >= 5:
        return None
    price = 400
    for _ in range(level):
        price = int(price * 1.2 + .5)
    return price


def default_state():
    return {
        'version': 1, 'balance': 0,
        'owned': sorted(key for key, entry in ITEMS.items() if entry['price'] == 0),
        'aura': 'aura_color_01', 'ball': 'ball_classic',
        'accessories': [], 'appearance': None, 'environment': None,
        'aura_colors': {'aura_coins': '#ffd83d', 'aura_hearts': '#ff73b9',
                        'aura_stars': '#ffffff'},
        'passives': {key: {'level': 0, 'enabled': False} for key in PASSIVES},
        'country': None,
    }


def normalize_state(raw):
    state = default_state()
    if not isinstance(raw, dict):
        return state
    balance = raw.get('balance', 0)
    state['balance'] = max(0, int(balance)) if isinstance(balance, (int, float)) else 0
    owned = raw.get('owned', [])
    if isinstance(owned, list):
        state['owned'] = sorted(set(state['owned']) | {key for key in owned if key in ITEMS})
    for key in ('aura', 'ball', 'appearance', 'environment'):
        value = raw.get(key)
        expected = 'accessory' if key == 'appearance' else key
        if key in ('appearance', 'environment') and value is None:
            state[key] = None
        elif value in ITEMS and (key != 'appearance' or ITEMS[value]['category'] == 'appearance'):
            if key == 'appearance' or ITEMS[value]['category'] == expected:
                state[key] = value
    if state['aura'] is None:
        state['aura'] = 'aura_none'
    if state['ball'] is None:
        state['ball'] = 'ball_classic'
    accessories = raw.get('accessories', [])
    if isinstance(accessories, list):
        state['accessories'] = sorted({key for key in accessories if key in ITEMS and ITEMS[key]['category'] == 'accessory'})
    colors = raw.get('aura_colors', {})
    if isinstance(colors, dict):
        for key in state['aura_colors']:
            if colors.get(key) in PALETTE_HEX:
                state['aura_colors'][key] = colors[key]
    saved_passives = raw.get('passives', {})
    if isinstance(saved_passives, dict):
        for key, definition in PASSIVES.items():
            saved = saved_passives.get(key, {})
            try:
                level = max(0, min(definition['max_level'], int(saved.get('level', 0))))
            except (TypeError, ValueError, AttributeError):
                level = 0
            state['passives'][key] = {'level': level, 'enabled': bool(level and saved.get('enabled', False))}
    country = raw.get('country')
    state['country'] = country if isinstance(country, str) else None
    appearance = state['appearance']
    if appearance and appearance in state['owned'] and state['country'] != ITEMS[appearance]['team']:
        state['appearance'] = None
    return state


def passive_value(state, key, enabled_only=True):
    definition = PASSIVES[key]
    saved = normalize_state(state)['passives'][key]
    if enabled_only and not saved['enabled']:
        return definition['values'][0]
    return definition['values'][saved['level']]


def passive_display(key, value):
    if key in ('power', 'effect', 'keeper'):
        suffix = 'del diámetro original' if key == 'keeper' else 'de potencia'
        return f'{value*100:g}% {suffix}'
    if key == 'slide':
        return f'{value*100:g}% de deslizamiento restante'
    if key in ('recovery', 'impact'):
        label = 'de recuperación' if key == 'recovery' else 'de desplazamiento'
        return f'{value*100:g}% menos {label}'
    return f'{value:.2f} s · {(1-value)*100:g}% menos'


def catalog_for(category):
    if category == 'accessory':
        return [entry for entry in ITEMS.values() if entry['category'] in ('accessory', 'appearance')]
    return [entry for entry in ITEMS.values() if entry['category'] == category]
