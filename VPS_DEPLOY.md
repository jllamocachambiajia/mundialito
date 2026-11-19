# Guía de Despliegue en VPS: Llamoca.enlace.ink
## Servidor Multijugador en Tiempo Real para Mundialito

Esta guía explica paso a paso cómo desplegar el servidor multijugador (`server.py`) en tu servidor VPS para que dos personas puedan jugar simultáneamente desde sus computadoras o celulares Android conectándose al subdominio **`Llamoca.enlace.ink`**.

---

### 1. Requisitos Previos

- Servidor VPS con Linux (Ubuntu 20.04/22.04/24.04 o Debian 11/12).
- Python 3.8 o superior (`python3 --version`).
- Acceso SSH como usuario `root` o con privilegios `sudo`.
- Registro DNS tipo **A** configurado:
  - Nombre: `Llamoca.enlace.ink`
  - Destino: La dirección IP pública de tu VPS.

> [!NOTE]
> El archivo `server.py` fue diseñado para funcionar utilizando la biblioteca estándar de Python (`asyncio`, `socket`, `struct`, `json`), por lo que **no requiere instalar dependencias pesadas ni configurar entornos virtuales obligatorios**.

---

### 2. Clonar el Repositorio en el VPS

Conéctate a tu VPS mediante SSH y descarga la rama con multijugador:

```bash
# Navegar a una carpeta de servicios (por ejemplo /opt o tu home)
cd /opt
sudo git clone -b feature/multiplayer https://github.com/jllamocachambiajia/mundialito.git mundialito
cd mundialito
```

Prueba rápida para verificar que el servidor inicia:
```bash
python3 server.py 8765
```
Deberías ver en la terminal:
```
[INFO] === Servidor Mundialito iniciado en 0.0.0.0:8765 ===
[INFO] Listo para recibir conexiones en ws://0.0.0.0:8765
```
Presiona `Ctrl + C` para detenerlo tras la comprobación.

---

### 3. Configurar como Servicio Permanente (Systemd)

Para que el servidor se ejecute las 24 horas del día de fondo y se reinicie automáticamente si el servidor se reinicia, creamos un servicio en `systemd`:

1. Crear el archivo del servicio:
```bash
sudo nano /etc/systemd/system/mundialito.service
```

2. Pegar la siguiente configuración:
```ini
[Unit]
Description=Servidor Multijugador Mundialito
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mundialito
ExecStart=/usr/bin/python3 /opt/mundialito/server.py 8765
Restart=always
RestartSec=5
Environment=HOST=0.0.0.0
Environment=PORT=8765

[Install]
WantedBy=multi-user.target
```

3. Activar e iniciar el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable mundialito
sudo systemctl start mundialito
```

4. Verificar el estado del servicio:
```bash
sudo systemctl status mundialito
```

---

### 4. Configurar Nginx y Certificado SSL (HTTPS / WSS)

Para que la conexión funcione mediante un túnel seguro con `wss://Llamoca.enlace.ink`:

1. Instalar Nginx y Certbot (si no los tienes):
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

2. Crear la configuración del sitio para `Llamoca.enlace.ink`:
```bash
sudo nano /etc/nginx/sites-available/mundialito
```

3. Agregar la siguiente configuración:
```nginx
server {
    server_name Llamoca.enlace.ink;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

4. Habilitar el sitio y verificar la configuración:
```bash
sudo ln -s /etc/nginx/sites-available/mundialito /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

5. Generar el certificado SSL gratuito con Let's Encrypt:
```bash
sudo certbot --nginx -d Llamoca.enlace.ink
```

Certbot actualizará automáticamente la configuración de Nginx para habilitar SSL en el puerto 443.

---

### 5. Cómo Jugar en 2 Equipos al Mismo Tiempo

Una vez levantado el servidor en el VPS:

#### Modalidad 1: Multijugador en Línea (2 Celulares o Computadoras)
1. Ambos jugadores abren el juego y seleccionan **MULTIJUGADOR EN LÍNEA**.
2. **Jugador 1:** Pulsa **CREAR SALA PRIVADA**. La pantalla mostrará un código PIN de 4 dígitos (ejemplo: `4821`).
3. **Jugador 2:** Pulsa **UNIRSE CON CÓDIGO**, digita el PIN `4821` en el teclado numérico en pantalla y pulsa conectar.
4. ¡El partido comenzará de inmediato!
   - El Jugador 1 controla su equipo local y el Jugador 2 controla su equipo visitante.
   - Cada disparo realizado por un jugador se retransmite en tiempo real al otro dispositivo.

#### Modalidad 2: 2 Jugadores Local (En el mismo Celular, Tablet o PC)
1. En el menú principal, selecciona **2 JUGADORES (LOCAL)**.
2. Cada jugador selecciona su país con las flechas correspondientes.
3. Pulsa **¡INICIAR PARTIDO!**.
4. Ambos jugadores pueden tocar la pantalla y arrastrar sus chapitas de forma simultánea gracias al soporte multitouch integrado.
