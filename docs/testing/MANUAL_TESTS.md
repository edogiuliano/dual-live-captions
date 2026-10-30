# Validación manual pendiente

No se necesitan comandos para estas pruebas. Abrir el EXE, elegir perfil
Equilibrado y salida predeterminada. Dejar historial desactivado salvo que se
necesite una exportación explícita de una conversación de prueba consentida.

## Salidas y desconexión

1. Reproducir voz en YouTube y comprobar el indicador de nivel y ambos paneles.
2. Cambiar desde Windows la salida a otro dispositivo ya conectado. Se espera
   reapertura dentro de unos segundos, sin modificar el volumen ni el default.
3. Desenchufar auriculares y volver a conectarlos. Registrar tiempo de recuperación.
4. Seleccionar una salida específica en la app; al desconectarla debe informar
   reconexión y esperar su regreso, sin capturar otra salida silenciosamente.
5. Comprobar también cambio a un dispositivo nuevo no enumerado al iniciar.

Estas acciones físicas no fueron realizadas automáticamente en esta entrega.
Hay pruebas de resolución de identidad con fallos inyectados, pero no equivalen
al ensayo físico. La consulta Core Audio usa identidades nuevas cada dos segundos.

## Micrófono y fuentes simultáneas

En Configuración elegir un micrófono concreto que tenga señal. Para micrófono
solo desactivar Audio de Windows. Para ambas fuentes, activar las dos y usar
auriculares. Pronunciar inglés y español mientras otra fuente reproduce voz.
Verificar la etiqueta Sistema/Micrófono en historial exportado. La app separa
orígenes y no realiza cancelación de eco ni separación de voces superpuestas.
La apertura simultánea y recepción de cuadros sí se probaron en esta estación.

## Latencia y exactitud humana

Usar conversación pública o material de prueba con referencia consentida. Marcar
inicio de voz, primera publicación y confirmación con un reloj de video externo.
Comparar palabras EN/ES, nombres, números y alternancia sin pausa. Anotar falsos
provisionales además de errores confirmados. Guardar transcripciones solo con
Exportar y consentimiento; no agregar conversaciones personales al repositorio.

Ya se probaron dos videos de YouTube, sin referencia alineada humana. Hubo un
provisional EN durante el español: no se garantiza separación perfecta.

## Overlay y otras aplicaciones

Mover a cada monitor con distintas escalas DPI. Arrastrar y redimensionar, ajustar
fuente/líneas/opacidad, ocultar un idioma, bloquear posición y volver a desbloquear.
Activar click-through y hacer clic en un navegador detrás; recuperar interacción
con Ctrl+Alt+U o con la bandeja. Probar conflicto de atajo con otra aplicación.
Sobre pantalla exclusiva/DRM/escritorio seguro puede no funcionar.

## Jornadas prolongadas

Realizar sesiones reales de 15, 30, 60 y 480 minutos con GUI + WASAPI. Cada 15
minutos anotar memoria de GUI y proceso ASR por separado en Administrador de
tareas, VRAM total, tiempo de inferencia, publicación y descartes. Comprobar que
no se acumula retraso al pausar, cambiar salida, volver del silencio o reanudar
tras suspensión. Probar junto a Discord/OBS/navegador.

El ensayo ya concluido de 15 minutos se hizo con ASR a velocidad real desde
archivos, sin WASAPI continuo. No sustituye esta matriz. El programa incluye
watchdog de carga de 90 s y de inferencia de 30 s; no se inyectó un bloqueo real
del driver durante estas pruebas.

## Windows limpio y modelos

Copiar la carpeta portable completa a otro Windows 11 x64. Abrir sin Python.
Sin runtime GPU debe funcionar CPU. Seleccionar bibliotecas GPU desde Diagnóstico
y reiniciar reconocimiento. Cancelar una descarga desde el cierre de la ventana,
volver a abrir y reintentar. Comprobar barra de progreso, tamaño informado y
rechazo de archivos corruptos. El descargador ya verificó un tiny real por SHA256;
el rechazo de contenido corrupto se comprobó en test automatizado.
