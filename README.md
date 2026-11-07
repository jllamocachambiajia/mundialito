# Mundialito — versión 11

Juego Python/Kivy para computadora y Android. Catálogo de 24 países y cuadro eliminatorio de 16 equipos.

## Ejecutar

Python 3.11 o posterior compatible con Kivy. En PC:

```sh
python -m pip install -r requirements.txt
python main.py
```

En Pydroid 3 instala Kivy y Pillow con su gestor de paquetes; extrae el ZIP completo y ejecuta main.py sin moverlo fuera de la carpeta.

## Crear APK en GitHub

1. Extrae el ZIP y sube **todo su contenido** a la raíz de un repositorio, incluido `.github/workflows/build-apk.yml` y `assets/`.
2. En Actions ejecuta **Crear APK** o realiza un commit.
3. Cuando finalice correctamente, descarga el artefacto **CopaMundialChapas-APK**; contiene el APK de prueba.
4. Instálalo en Android permitiendo instalaciones desde esa fuente. La primera compilación descarga SDK/NDK y puede tardar bastante.

Si no ves `.github`, activa la visualización de archivos ocultos. No subas solamente main.py. El ZIP es código y recursos listos para compilar, **no un APK ya compilado**. No requiere servicios externos durante el juego.

## Organización

- `main.py`: juego, controles y físicas conservadas.
- `tournament.py`: cuadro panorámico, copias de avance, fragmentación y secuencias.
- `presentation.py`: recursos SVG reutilizables, GIF acotado y transiciones Kivy Animation.
- `assets/images`: SVG originales y paneles vectoriales.
- `assets/animations`: GIF enviado y tiempos de sus 75 fotogramas.
- `assets/sounds/victory`: 24 victorias distintas más goles, penales y campeonato por país; catalog.json describe cada identidad.
- `assets/sounds/effects`: efectos, avanzar_nivel.wav y perder.wav.
- `assets/sounds/music`: música aportada y acompañamiento de derrota original independiente.
- `tests`: comprobaciones del torneo y reglas conservadas.

## Audio y recursos

`MUSIC_VOL = 0.15` en main.py ajusta el volumen de fondo. El fade-in parte de silencio; los penales reducen el nivel sin reiniciar la pista. La pausa conserva el reloj, las posiciones, los efectos visuales y la transición de volumen. La reanudación de audio usa get_pos/seek; su precisión depende del proveedor de Android.

Las celebraciones son composiciones sintetizadas originales con instrumentos/ritmos inspirados en cada país; no son grabaciones de aficionados ni himnos. Consulta ASSETS_LICENSES.md.

El GIF se muestra durante 3 segundos, sin bucle, en goles del jugador y al ganar el torneo. Los SVG se renderizan como vectores con Kivy, sin reducir resolución. `copa.svg` permanece intacto; `copa_render.svg` conserva sus degradados y convierte cuatro trazos a contornos para evitar un error del renderizador SVG de Kivy 2.3.1.

## Verificación y límites

Ejecuta `python -m unittest discover -s tests -v`. Se comprobaron transiciones, pantallas vertical/horizontal, avance y derrota en Kivy de escritorio. Se conservan las funciones de física, IA, disparo, penales y duración, con pruebas de regresión. Se reutilizan campo, camisetas estáticas, geometrías, intersecciones de fragmentos y sonidos; no se sintetiza audio al jugar.

**Pendiente:** compilar el APK mediante Actions, comprobar Android físico, escucha del audio y medir FPS reales en el teléfono. No se garantiza eliminar todas las caídas de FPS sin esas mediciones. El renderizador SVG de Kivy es experimental; los archivos incluidos se probaron en escritorio.

Referencias visuales (solo consulta, sin incorporar imágenes): Reuters https://www.reuters.com/graphics/SOCCER-WORLDCUP/mopaoglqkpa/knockouts/ y Flourish https://public.flourish.studio/visualisation/14706961/.
