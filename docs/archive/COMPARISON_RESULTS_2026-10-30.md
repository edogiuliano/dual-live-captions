> Archivo de desarrollo previo a la versión inicial **0.0.1**. Para el uso actual, ver [la documentación](../README.md).

# Primera comparación en vivo con Windows — 30/10/2026

Se inició un monitor de 30 minutos sobre el audio que el usuario ya estaba
usando. No se reprodujo audio adicional. Windows Live Captions y el EXE de Dual
Live Captions 0.1.0 capturaron simultáneamente la salida de Windows. Dual utilizó
CUDA y small; historial de conversaciones desactivado.

El monitor lee los controles reales de texto de ambas aplicaciones. Se probó
lectura directa de `CaptionsTextBlock` y de los dos paneles Qt. No utiliza
capturas de pantalla ni guarda texto o audio en su informe.

Se descartó un primer ensayo del algoritmo porque las palabras corregidas
debían conservar su posición en la frase. La revisión 2 incorpora esa corrección
y trece tests deterministas de alineamiento, tiempos, desplazamiento de líneas,
revisiones, idiomas, privacidad y límites de memoria. La suite unitaria completa
pasó: **48 pruebas**, sin volver a cargar ni modificar el motor ASR existente.
Ruff pasó para los módulos del proyecto.

## Muestra preliminar, no resultado definitivo

Instantánea alrededor de 124 segundos de la revisión 2:

| Métrica | Observación |
|---|---:|
| Palabras comparadas entre anclas comunes | 87 |
| Palabras emparejadas para tiempos | 65 |
| Mediana Dual menos Windows | +242 ms |
| P10 / P90 de diferencia de aparición | −81 / +660 ms |
| Coincidencia textual normalizada | 88,5% |
| Correcciones provisionales Windows / Dual | 3 / 14 palabras |
| Intervalo mediano real de muestreo | 108 ms |
| P95 del intervalo de muestreo | 112 ms |
| Lectura UIA mediana | 1,06 ms |
| Reinicios de línea de base durante esta muestra | 0 |

El comparador ocupó aproximadamente 70 MB de RAM en una observación puntual.
Los valores son de una ventana móvil y cambian mientras sigue entrando audio.
Las palabras de un mismo bloque de publicación no son muestras estadísticas
independientes. P10/P90 no constituye un intervalo de confianza.

La muestra sugiere que el texto coincidente de Dual apareció aproximadamente un
cuarto de segundo después de Windows. No mide desde el inicio de la voz ni la
pintura exacta del monitor. Las palabras discrepantes no entran al cálculo de
tiempo. Por ello no se debe presentar esta cifra como latencia absoluta de ASR.

El 88,5% es **coincidencia con Windows, no precisión real**. Se comparó el panel
inglés; el idioma de Windows no fue verificado automáticamente ni cambiado.
El otro panel de Dual tuvo actividad en español y se mantuvo fuera de la
comparación. En audio bilingüe, errores de Windows también pueden reducir el
acuerdo. No se obtuvo una referencia humana para calcular WER.

## Dónde seguir la prueba

- Informe que continúa actualizándose cada dos segundos:
  `artifacts/comparison/2026-10-30-live/report.json`.
- Instantánea numérica separada: `preliminary.json` en esa misma carpeta.
- Ventana: **Comparación en vivo · Windows y Dual**, iniciada minimizada.
- Lanzador para repetir otra sesión: **Comparar subtítulos.lnk**.

Al cumplir los 30 minutos se detiene solo el monitor. Los subtítulos siguen
funcionando. El usuario puede ampliar la duración, pausar o terminar desde la
ventana del comparador. No se creó una automatización de Codex ni se programó
una notificación posterior.
