> Archivo de desarrollo previo a la versión inicial **0.0.1**. Para el uso actual, ver [la documentación](../README.md).

# Dual Live Captions 0.1.2 — paneles para párrafos

Esta versión corrige el espacio de lectura de la ventana principal, además del
overlay. En 0.1.1 la cabecera, los controles y la fuente de 28 px dejaban cada
idioma en una franja baja. Se usa como referencia la capacidad de lectura de
Windows Live Captions; no se copian ni guardan sus conversaciones.

## Diseño

- Ventana principal inicial de hasta 1280 × 980 px, ajustada al monitor.
- Dos paneles grandes lado a lado; selector Apilados para volver a disposición
  vertical sin reiniciar el motor. El separador permite repartir el espacio.
- Cabecera en una sola fila y controles en una sola barra inferior. Configuración,
  historial y diagnóstico pasan al menú Más.
- Botón Ampliar para maximizar/restaurar.
- Fuente predeterminada de 20 px, párrafos más próximos y márgenes compactos.
- Overlay de dos columnas, 1280 px de ancho y unas 20 líneas de altura inicial.
- Se conservan 500 palabras por idioma, scroll, Releyendo y Lo último.

Las preferencias antiguas predeterminadas se migran una vez: fuentes de 25/28 px
a 20 px, alturas de 3/5 líneas a 20 y anchura 1120 a 1280. Los demás tamaños
personalizados se conservan. El motor y las preferencias de privacidad no cambian.

## Verificación de espacio

En la prueba gráfica a 1280 × 980, cada área de texto principal midió
**581 × 779 px**, aproximadamente 29 alturas de línea según QFontMetrics.
Ambos textos ocupan más del 70% del área central. El overlay midió
**581 × 548 px por idioma**, unas 20 alturas de línea. La cantidad real de líneas
depende del texto, saltos de párrafo y tamaño de fuente elegido.

Hay pruebas que exigen al menos 650 px de altura y 550 px de anchura por área de
texto a esa geometría; otra comprueba el cambio a Apilados, sin arrancar ASR.
La suite pasó 58 pruebas y omitió las cinco integraciones ASR sin cambios.
Los chequeos gráficos son silenciosos, con datos genéricos de prueba, sin audio.

Fuente: `artifacts/paragraph-ui-source.json` y sus imágenes. La misma comprobación
se ejecutó sobre el paquete en `artifacts/paragraph-ui-release.json`: los 18
chequeos aprobaron, con las mismas dimensiones que el código fuente.

## Abrir

El acceso Dual Live Captions.lnk apunta al ejecutable actualizado en
`dist/0.1.2/DualLiveCaptions/DualLiveCaptions.exe`. Las versiones anteriores se
conservan. Para más espacio se puede maximizar o mover el separador entre idiomas.
