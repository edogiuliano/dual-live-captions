> Archivo de desarrollo previo a la versión inicial **0.0.1**. Para el uso actual, ver [la documentación](../README.md).

# Dual Live Captions 0.1.1 — lectura y tamaño

La mejora se concentra en comodidad de lectura. El motor, la captura y la
separación de idiomas conservan la misma arquitectura.

- Overlay inicial de 1120 px de anchura, cinco líneas por idioma y fuente de
  28 px. La ventana principal también tiene más espacio. Los valores se pueden
  ajustar desde Configuración → Overlay.
- Barra vertical en ambos idiomas, tanto en la ventana principal como en overlay.
- Cada panel retiene 500 palabras recientes por defecto, incluyendo los
  provisionales en el presupuesto visible. Las confirmadas más antiguas se
  eliminan cuando llega texto nuevo. Se recorta también una intervención larga,
  sin descartar de golpe toda la conversación ni limitarla a las antiguas 150 palabras.
- Al desplazarse hacia arriba se activa Releyendo y se conserva la palabra
  visible como ancla, aun si se recorta el comienzo. Lo último vuelve al final y
  reactiva el seguimiento. Si el ancla ya supera la retención, se muestra lo más
  antiguo que todavía está disponible.
- Se puede seleccionar texto con el mouse. El overlay sigue sin tomar foco de
  teclado al mostrarse. Si está activado click-through, recuperar la interacción
  con el atajo existente Ctrl+Alt+U antes de usar la barra.
- El comparador pausa su lectura mientras se relee un panel y establece una
  nueva línea de base al volver a En vivo. No interpreta texto anterior como
  una palabra recién publicada.

El historial visual vive solo en RAM. No habilita exportaciones automáticas ni
el historial opt-in. Configuración permite cambiar el límite entre 100 y 2.000
palabras por idioma. Las preferencias anteriores se migran una vez: los valores
antiguos predeterminados 25 px / 3 líneas pasan a 28 px / 5 líneas; una fuente o
cantidad de líneas personalizada se conserva.

## Validación

Tests específicos: límite exacto de 500 palabras, texto de una intervención larga,
presupuesto de provisionales, seguimiento en vivo, pausa al releer, retorno al
final, ancla conservada al recortar 100 palabras y migración de preferencias.
El lector comparativo tiene un test que rechaza tiempos mientras un panel indica
Releyendo. La prueba gráfica `--ui-check` usa exclusivamente texto de muestra,
sin reproducir audio ni iniciar ASR.

Artefactos del código fuente: `artifacts/scroll-ui-source.json` e imágenes del
overlay. El ejecutable de esta versión se valida además con el mismo chequeo
silencioso en `artifacts/scroll-ui-release.json`.

Resultado de esta entrega: 56 pruebas aprobadas y cinco integraciones ASR
omitidas por no afectar el cambio de interfaz. Los 16 chequeos del EXE
silencioso aprobaron. También se abrió el EXE nuevo con el audio actual y se
observó estado Capturando / CUDA; no se reprodujo ninguna muestra encima.
El lector UIA localizó ambos paneles y sus dos marcadores En vivo/Releyendo.

## Uso

Abrir el acceso **Dual Live Captions.lnk**, actualizado al paquete
`dist/0.1.1/DualLiveCaptions/DualLiveCaptions.exe`. El paquete anterior se conserva.
Iniciar captura y abrir Overlay. Usar rueda o arrastrar la barra para releer;
presionar ↓ Lo último para regresar al presente. No se modifican el volumen ni
la salida de audio.
