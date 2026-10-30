> Archivo de desarrollo previo a la versión inicial **0.0.1**. Para el uso actual, ver [la documentación](../README.md).

# Dual Live Captions 0.2.0 — overlay compacto e independiente

La ventana principal conserva su diseño. Activar Overlay la oculta y deja
únicamente los subtítulos flotantes. La captura, el proceso ASR, el temporizador
de entrega de 40 ms y la separación EN/ES no cambian. No hay traducción ni atajos
nuevos. Los tres atajos ya existentes conservan sus funciones.

## Uso

1. Iniciar captura en la ventana principal y pulsar Overlay.
2. Pasar el mouse sobre la ventana para mostrar los controles flotantes. No
   reservan espacio ni cambian el tamaño del texto al aparecer.
3. Arrastrar el agarre de puntos para mover. Arrastrar cualquier borde o esquina
   para redimensionar; los bordes tienen una zona de 7 píxeles lógicos.
4. Separar crea ventanas EN y ES independientes. Unir vuelve a la presentación
   conjunta. Se trasladan los mismos dos paneles, sin copiar sus transcripciones.
5. Aa abre Personalización: color/tamaño/tipo de fuente, fondo, opacidad del
   fondo, máximo de líneas y tamaño automático. La casilla de aspecto común
   permite editar ambos idiomas o cada uno por separado. Los cambios se aplican
   inmediatamente, con vista previa, y se guardan automáticamente.
6. ↗ vuelve a la ventana principal sin detener la captura. También se puede
   volver desde Mostrar ventana en la bandeja. × oculta ese overlay; si no queda
   ninguno visible, se recupera la ventana principal. Los idiomas ocultos se
   pueden volver a habilitar desde la configuración existente.

## Tamaño, texto e historial

El overlay unido parte de hasta 960 × 280 píxeles lógicos; cada ventana separada,
de hasta 640 × 280. La altura se limita según la cantidad de líneas y el monitor.
El valor inicial son ocho líneas por idioma, editable hasta 32. La altura útil
también depende de fuente, saltos de párrafo y dimensiones elegidas. Un overlay
angosto puede mostrar menos palabras que uno ancho con igual cantidad de líneas.

El texto se reajusta al ancho y conserva las 500 palabras recientes ya existentes
(límite configurable). Cambiar de tamaño, estilo o modo no elimina palabras.
El texto más antiguo solo se retira al superar la retención configurada, no
por achicar una ventana. El historial opcional de exportación conserva su
comportamiento previo y su consentimiento: no se activa automáticamente.

Subir con rueda/barra activa Releyendo y conserva el ancla visible al actualizar
o reajustar. Lo último vuelve al final. Los provisionales se muestran con menor
contraste y las confirmaciones se mantienen estables. El tamaño automático
ajusta unas pocas líneas legibles, sin intentar encajar todo el historial;
normalmente no baja de 16 px, o del tamaño manual si este es menor.

La opacidad se pinta únicamente en el fondo; las letras no heredan transparencia
de toda la ventana. Las ventanas no toman foco al aparecer y continúan siempre
encima. Se conserva click-through y su recuperación desde Ctrl+Alt+U/bandeja.

Las preferencias usan el mismo settings.json local. Solo se agregan estilos,
modo separado y geometrías; no se escriben conversaciones. Las posiciones se
limitan al área útil, se recuperan si quedan fuera de pantalla y usan píxeles
lógicos de Qt para DPI. Los cambios de posición se guardan con espera breve,
sin escribir en cada evento del mouse.

## Componentes modificados

- overlay.py: panel compacto opcional, estilos, ajuste de fuente y control del
  ancho mínimo. Los paneles principales mantienen sus dimensiones y apariencia.
- floating.py: ventanas livianas, bordes/esquinas, controles al hover y gestión
  de unión/separación con los mismos paneles. Ninguna dependencia de captura/ASR.
- overlay_style.py / personalization.py: preferencias visuales validadas y editor
  inmediato con vista previa por idioma.
- ui.py: conexión de eventos, ocultar/volver, menú de personalización y bandeja.
- settings.py: persistencia en el almacenamiento existente.
- comparison_windows.py: el lector existente puede seguir ambas ventanas
  separadas; mantiene la pausa al releer texto.
- app.py / ui_check.py: comprobación gráfica silenciosa aislada de las
  preferencias del usuario. Tests y versión del paquete actualizados.

audio.py, asr.py, pipeline.py, language.py, service.py y hotkeys.py no se modifican.

## Verificación realizada

- Suite completa con DLC_INTEGRATION=1: **76 pruebas aprobadas**, incluidas cuatro
  muestras ASR reales (EN, ES, EN corto y ES corto) y silencio. Son archivos
  sintéticos locales; no se reprodujeron sobre el audio actual del usuario.
- Pruebas de identidad del proceso al ocultar/volver, mismos paneles al separar
  y unir repetidamente, geometría y visibilidad independientes, historial/scroll
  después del resize, enlaces muy largos sin desbordamiento, estilos por idioma,
  persistencia y recuperación de posiciones con monitor ausente.
- Se verifican las ocho zonas de resize y el alfa del fondo por separado de la
  opacidad del texto. Se verifica que los controles no cambien el área de lectura.
  Se comprueba el bit Win32 WS_EX_TRANSPARENT de las tres ventanas al activar
  click-through y su eliminación al recuperar la interacción.
- Comprobación gráfica fuente: **27 chequeos aprobados** al 100% y 150% de escala,
  con texto de prueba, sin ASR, sin audio y sin modificar preferencias. Colocación
  programática dentro de los dos monitores disponibles GM3CP238 y LF24T35.
  Artefactos: artifacts/compact-overlay-source.json y compact-overlay-dpi150.json,
  con imágenes del modo unido, EN/ES y Personalización.

Se conservan también los controles anteriores de anchura inicial, posición,
monitor y altura de Configuración. Una prueba verifica que siguen aplicándose
al overlay compacto.

El ejecutable portable pasó los mismos **27 chequeos gráficos**, incluyendo
ocultar/volver, separar/unir, actualización de estilos, scroll y recuperación
de click-through. Informe: artifacts/compact-overlay-release.json.
No se atribuyen estas pruebas a una mejora de precisión o latencia del motor.

## Límites y pruebas manuales pendientes

La automatización de escritorio disponible no expone estas ventanas Tool que no
toman foco. Por eso el arrastre físico con mouse desde las ocho zonas, los gestos
de selección sobre otras aplicaciones y la recuperación mediante el atajo global
deben comprobarse manualmente en el EXE. La ruta de recuperación sí se invoca en
la prueba gráfica; no equivale a pulsar el atajo en Windows.

La escala al 150% se probó con QT_SCALE_FACTOR, no cambiando ajustes de Windows.
La desconexión física de un monitor y monitores con distintas escalas simultáneas
siguen pendientes. Hay pruebas de límites geométricos equivalentes y cambios
de pantalla programáticos; no se presentan como una desconexión real.

No se realizó un ensayo nuevo de ocho horas ni una medición nueva de latencia
voz-a-pantalla. Las restricciones previas de pantalla exclusiva, DRM y escritorio
seguro se mantienen.

Para repetir la comprobación silenciosa del paquete:

```powershell
dist/0.2.0/DualLiveCaptions/DualLiveCaptions.exe --ui-check artifacts/compact-overlay-release.json
```

Para una prueba manual con texto genérico, sin iniciar ningún motor:

```powershell
.venv/Scripts/python.exe scripts/dev/check_overlay_mouse.py --output artifacts/overlay-mouse-check.json
```

El ejecutable portable está en dist/0.2.0/DualLiveCaptions/DualLiveCaptions.exe.
Conservar _internal junto al EXE. El acceso Dual Live Captions.lnk se actualiza a
este paquete; las versiones anteriores se conservan.

Referencia de implementación nativa: [QWindow — movimiento y resize del sistema](https://doc.qt.io/qt-6/qwindow.html#startSystemResize).
