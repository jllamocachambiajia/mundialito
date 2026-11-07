# Verificación v11

- 15 pruebas automáticas aprobadas.
- 21 funciones de física/IA/disparo/penales/pausa mantienen el mismo cuerpo que v10.
- Recorrido Kivy: selección, transición, partido, pausa/reanudar, GIF, penales, resultado, clasificación, campeonato, derrota y regreso al menú.
- Capturas revisadas en 420×900 y 1100×720.
- Pausa: reloj y posiciones no cambian; GIF expira y usa los 75 fotogramas originales.
- Los tres gráficos suministrados son idénticos byte por byte a los originales.
- 24 WAV de victoria diferentes, además de variantes de gol/penal/campeonato, efectos y música.
- Prueba local de 60 redibujados (CPU/software GL): p75 con caché 3.69 ms frente a 5.29 ms sin caché, misma geometría. Esto mide preparación del dibujo, no FPS de Android ni rendimiento GPU.

Pendiente: APK en GitHub Actions, dispositivo Android físico, precisión real de seek del audio y escucha de los sonidos. Los permisos de los recursos aportados no fueron documentados.
