> Archivo de desarrollo previo a la versión inicial **0.0.1**. Para el uso actual, ver [la documentación](../README.md).

# 0.2.1 — movimiento y resize del overlay

Corrección limitada al overlay. No cambia ui.py, captura, ASR, idiomas ni atajos.

## Causas y corrección

- Antes solo se iniciaba movimiento desde el agarre. Ahora un clic izquierdo en
  el encabezado o en una zona vacía inicia un gesto de ventana. Botones, barras
  de scroll, separador interno y selección de palabras conservan su interacción.
- El gesto se sigue con coordenadas globales y captura del mouse hasta soltarlo;
  no depende de startSystemMove/Resize en ventanas Tool sin activación.
- Las cuatro esquinas y los cuatro bordes usan la geometría del momento del
  clic. Al mover arriba/izquierda se preservan respectivamente abajo/derecha,
  también al alcanzar el mínimo o máximo. No se acumula deriva de un píxel.
- Se eliminó el máximo calculado con ocho líneas. El máximo ahora usa el ancho
  y alto útiles de los monitores disponibles, con el mínimo anterior razonable.
  Líneas iniciales queda como referencia de apertura, no como un tope manual.
- El temporizador guarda la geometría; ya no corrige ni recentra una ventana
  movida por el usuario. La recuperación al abrir o cambiar monitores se mantiene,
  pospuesta si existe un gesto activo.
- Se comprueba el área recortada por el viewport antes de tratar un clic como
  selección de texto. Las palabras fuera de la vista por scroll no bloquean el
  arrastre del encabezado.

Al agrandar se amplía el viewport y se ven más palabras retenidas, con la misma
fuente si tamaño automático está desactivado. Al achicar se vuelve a priorizar el
final, salvo que se esté releyendo. No se cambia el límite de historial configurado.

## Archivos

- floating.py: gestos de mouse, anclajes, límites y guardado de geometría.
- personalization.py: etiqueta Líneas iniciales y aclaración del resize libre.
- tests/unit/test_overlay_mouse.py: 53 pruebas nuevas de interacción y geometría.
- scripts/dev/check_overlay_mouse.py: fixture de prueba sin audio, con referencia
  opcional para herramientas que omiten ventanas Tool sin foco. Ese contenedor
  existe únicamente en la prueba y no forma parte del overlay de producción.
- Versión, README y nombre del artefacto de construcción actualizados a 0.2.1.

## Validación

Suite completa con DLC_INTEGRATION=1: **129 pruebas aprobadas**. Incluye las cinco
integraciones existentes con inferencia local sobre archivos EN/ES y silencio.
No se reprodujo audio sobre las conversaciones actuales.

Las pruebas nuevas envían MouseButtonPress/MouseMove/MouseButtonRelease a los
widgets de ventanas Qt reales y comprueban la geometría final. No se limitan a
comprobar las etiquetas de los bordes. Hay 32 combinaciones de resize: ocho zonas
en unido horizontal, unido vertical, EN y ES. También se comprueban arrastre por
encabezado/fondo, historial desplazado, pausa de 500 ms sosteniendo el gesto,
botones, fuente fija, historial conservado y límites con el borde opuesto anclado.

Se observó recepción y movimiento con eventos nativos de Windows en el fixture
de prueba. La automatización de una secuencia nativa controlada de todos los
bordes no se pudo completar con fiabilidad mientras había otra entrada de mouse;
no se declara como aprobada. La matriz reproducible anterior usa eventos Qt.
El fixture tiene un propietario visible únicamente para permitir seleccionar
estas ventanas en las herramientas de escritorio; conserva la clase y flags del
overlay. No guarda audio ni texto de conversaciones.

La comprobación visual silenciosa, fuente y EXE, usa solo texto genérico. Los
informes son artifacts/free-overlay-source.json y free-overlay-release.json.
La imagen y medidas de un overlay de 1250 × 900 están en free-overlay-large.png
y free-overlay-large.json. No hay una medición nueva de latencia de ASR.

## Uso

Abrir el acceso Dual Live Captions.lnk, que apunta a
dist/0.2.1/DualLiveCaptions/DualLiveCaptions.exe. Si está ejecutándose una versión
anterior, salir desde la bandeja y abrir la nueva cuando sea conveniente.
No ejecutar dos capturas simultáneas para aplicar la actualización.

En Overlay, arrastrar el espacio del encabezado o el fondo vacío para mover;
arrastrar cualquier borde/esquina para cambiar de tamaño. Bloquear posición y
click-through mantienen sus funciones anteriores: desactivarlos para interactuar.
El texto real sigue permitiendo selección con el mouse.

Referencia de Qt: [captura y liberación del mouse](https://doc.qt.io/qt-6.8/qwidget.html#grabMouse).
