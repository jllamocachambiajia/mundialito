# Mundialito de Chapas — Multijugador EN LÍNEA (rama `multijugador`)

El VPS es la ÚNICA autoridad: simula física, goles, reloj y las tres habilidades.
El APK y el .exe solo envían intenciones (disparo: ficha + vector; habilidad) y dibujan
los estados que llegan 30 veces por segundo. Así no hay desincronización entre teléfono y PC.

## Dónde va cada archivo en tu repositorio

Lo que viene en la carpeta `client/` del ZIP va **junto a tu `main.py`** (no dentro de otra carpeta).

```text
tu-repositorio/                      (rama multijugador)
├── main.py                          ← el tuyo, SIN cambios
├── front_menu.py                    ← REEMPLAZAR (solo añade el botón EN LÍNEA)
├── online_view.py                   ← NUEVO: pantallas acceso / vestuario / búsqueda / partido / resultado / podio
├── network_client.py                ← NUEVO: conexión REST + WebSocket
├── online_config.json               ← NUEVO: pon aquí la IP de tu VPS
├── assets/ ...                      ← los mismos de siempre (fuentes Teko/Oswald y sonidos se reutilizan)
├── server/                          ← NUEVO: servidor autoritario (NO va dentro del APK)
│   ├── app/ (main.py, physics.py, match.py, rooms.py, database.py, config.py)
│   ├── tests/test_server.py
│   ├── Dockerfile  docker-compose.yml  requirements.txt  .dockerignore
└── .github/workflows/
    ├── main.yml                     ← el tuyo (APK + EXE) con 2 líneas extra, ver abajo
    └── servidor.yml                 ← NUEVO: pruebas + imagen Docker ARM64/x86
```

## 1. Servidor en el VPS (Docker)

```bash
git clone -b multijugador https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO/server
docker compose up -d --build
docker compose logs -f           # debe decir: Uvicorn running on http://0.0.0.0:8000
curl http://localhost:8000/health
```
- Abre el puerto **8000 TCP** en el firewall del VPS (y en la lista de seguridad si es Oracle).
- Las cuentas viven en el volumen `mundialito_data`: no se borran al actualizar.
- Documentación interactiva: `http://IP_DEL_VPS:8000/docs`
- Actualizar: `git pull && docker compose up -d --build`

## 2. Cliente (APK y .exe)

1. Edita `online_config.json`: `{"server": "http://IP_DEL_VPS:8000"}`
2. `buildozer.spec`:
   - `requirements = ... ,websocket-client`  (añádelo a tu línea actual)
   - `source.include_exts = py,png,jpg,wav,ogg,ttf,gif,json`  (asegúrate de incluir **json**)
   - `android.permissions = INTERNET`
3. `main.yml`, en el trabajo de Windows, junto a tu `pip install`:
   - `pip install websocket-client`
   - en PyInstaller: `--hidden-import websocket --hidden-import online_view --hidden-import network_client --add-data "online_config.json;."`

## Reglas del modo en línea (las aplica el servidor)
- Tiempo real continuo, 6 fichas por equipo, recarga de 1 s independiente por equipo y para el arquero.
- Saque exclusivo del equipo que saca. Dos tiempos de 2:30, prórroga ~1:07 y después **gol de oro** de 60 s; si nadie marca, empate.
- FUEGO: 150 % de potencia, atraviesa fichas de campo, arquero rival bloquea solo tiros desde campo propio, 2 s reales, recarga 20 s.
- PAUSA: rival congelado 10 s, recarga 60 s.
- CAMPO MAGNÉTICO: 12 s, devuelve el 60 % del impacto, electrocuta 5 s al arquero rival, recarga 30 s y bloquea al rival 22 s; si lo rompe un tiro de fuego, 40 s de penalización.
- Amistoso aleatorio: primer rival disponible, suma V/D sin tocar ELO. Ranked: rival de ELO parecido (la ventana crece con la espera), ELO K=32 desde 1000.
- Abandonar o rendirse (X dos veces) = derrota. Cuentas: usuario 3-16 letras/números/_, contraseña con hash PBKDF2.

## Probar en PC sin compilar
```bash
cd server && pip install -r requirements.txt && uvicorn app.main:app --port 8000
# en otra terminal, en la carpeta del juego:
MUNDIALITO_SERVER=http://127.0.0.1:8000 python online_view.py
```
