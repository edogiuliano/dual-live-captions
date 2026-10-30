> Mediciones históricas de desarrollo, anteriores al versionado inicial 0.0.1. Los informes crudos referidos viven en `artifacts/` local y no se publican. No son mediciones nuevas de esta entrega.

# Mediciones reales — 2026-10-21

Estos resultados describen esta estación y estas muestras, no garantías de uso.
RTX 3090 24 GB, driver 617.42, Windows x64, Python 3.10, faster-whisper 1.2.1,
CTranslate2 4.8.3, CUDA/cuDNN locales, FP16. Código y versiones fijadas incluidos.

## Corpus y método

Se generaron seis WAV con System.Speech de Windows: Microsoft Zira Desktop
(inglés) y Microsoft Sabina Desktop (español). Las referencias se encuentran en
`tests/audio_samples/reference.json`, y las muestras en esa misma carpeta.
Incluyen preguntas, turnos médicos y frases cortas. Son voces sintéticas limpias;
no se deben presentar como resultados sobre hablantes humanos ni YouTube.

WER: distancia de edición a nivel de palabras, minúsculas y puntuación ignorada,
acentos conservados. Por ello diferencias como "porque"/"por que" y "qué"/"que"
cuentan como errores. La media macro da igual peso a cada archivo. El streaming
concatena ocho intervenciones con pausas 150–500 ms y termina con silencio;
un productor entrega cuadros cada 32 ms a una cola acotada mientras el consumidor
infiere. El reloj sigue corriendo durante inferencia: no es simulación acelerada.

## Comparación de modelos

| Modelo | WER macro en seis archivos completos | Mediana de inferencia por archivo, corrida final |
|---|---:|---:|
| base FP16 | 2,5% | 86,6 ms |
| small FP16 | 2,5% | 130,8 ms |

Todos los archivos completos dieron el idioma esperado, incluyendo frases
cortas. El español largo tuvo WER 15%; los otros cinco archivos 0%. Esto es un
corpus demasiado pequeño para declarar que base y small tienen igual precisión.
La evidencia favorece base como perfil rápido. Small queda como predeterminado
conservador; se necesita un corpus humano más amplio para justificar una mejor
precisión. No se ejecutaron SimulStreaming, Riva, Qwen, Parakeet ni whisper.cpp:
su comparación fue documental. No se inventa un ranking de exactitud entre ellos.

## Streaming incremental real a partir de archivos

Resultados de la corrida final de small, 39,566 segundos de audio:

- WER inglés: 0%; WER español: 9,375%.
- Primer texto por intervención: 0,823–1,648 s; siete de ocho por debajo de 0,9 s.
- Mediana de inferencia: 141,6 ms; percentil 95: 175,9 ms.
- Captura simulada de último cuadro a publicación: mediana 140,5 ms, p95 187,9 ms.
- Cero cuadros descartados. Cero palabras duplicadas adicionales en inglés;
  las frases repetidas en la referencia se conservaron como nuevas intervenciones.
- Inglés y español aparecieron en sus paneles, sin publicar una frase en ambos.
- La prueba de silencio a través del VAD no llamó al motor y no emitió palabras.

Una segunda corrida con base sobre el mismo streaming obtuvo WER EN 0%, ES
9,375%, primera emisión 0,763–1,555 s y cero cuadros descartados. Esa corrida
coincidió con otras pruebas GPU, por lo que no es una comparación aislada de
velocidad. Los archivos crudos son `artifacts/benchmark-small.json` (primera
corrida final con ambos modelos) y `artifacts/benchmark-base.json` (corrida base).

**Interpretación de latencia:** primera emisión incluye ventana mínima y VAD.
"Captura a publicación" parte del último cuadro utilizado: no incluye la espera
desde la primera sílaba. La entrega IPC/visual se mide por separado en la UI.
La latencia física DAC→WASAPI no se midió con instrumentación externa. Los cuadros
de captura duran 32 ms, pero ese tamaño no es una medición de latencia acústica.

## Recursos observados

En la corrida final, muestreo cada ~0,5 s:

- RSS del proceso del benchmark: máximo 849 MB (incluyó carga sucesiva de base
  y small, clasificador y VAD; no equivale al proceso gráfico solamente).
- VRAM total del sistema observada: 1.858–2.777 MiB.
- Utilización GPU total observada: 10–74% en muestras puntuales.

Otras aplicaciones usan GPU: estos valores no aíslan memoria ni utilización
exclusiva del producto, y no demuestran convivencia fluida con OBS o juegos.
No se midió el consumo eléctrico. No se impone un límite de potencia/utilización.

## Prueba Windows completa

Se abrió la GUI real, se cargó small en CUDA y se reprodujo la conversación WAV
por la salida **predeterminada real de Windows**, sin cambiarla ni configurar
cables. WASAPI loopback capturó ese sonido. Se repitió tras corregir el cierre
de una lectura bloqueante: 12 eventos confirmados EN y 14 ES; coincidencias de
referencia positivas para ambos idiomas. Los eventos son fragmentos confirmados,
no un conteo de oraciones. Se vieron parciales durante reproducción; el último
estado al finalizar silencio no tenía provisionales.

Última inferencia de la segunda prueba: 153 ms; publicación 156 ms desde el último
cuadro; entrega UI registrada entre cero y un intervalo de repintado en la muestra
final. No hay un p95 visual completo de esta prueba. En la primera corrida la
entrega final registrada fue 46 ms. No equiparar estos valores a primera palabra.

Pausa/continuación/detención funcionaron y el proceso hijo terminó. Historial
persistente permaneció deshabilitado; el test utilizó RAM para validar referencias
y no guardó transcripciones en su informe. Overlay movido a ambos monitores que
el entorno realmente expuso: GM3CP238 y LF24T35. Sus centros quedaron dentro de
cada pantalla. Click-through se activó y desactivó desde control; la prueba no
certifica interacción sobre toda aplicación de terceros ni pantalla exclusiva.
Evidencia: `artifacts/windows-smoke.json`, `main-window.png`, `overlay.png`.

## Pruebas automatizadas

Primera ejecución: 29 unitarias/GUI aprobadas y cinco integraciones omitidas
por requerir opt-in. Con `DLC_INTEGRATION=1`: las cinco pruebas reales de ASR/VAD
aprobaron en GPU. Incluyen muestras EN/ES, frases cortas y ausencia de emisión en
silencio. Revisión final: **40 pruebas aprobadas**, incluidas esas cinco
integraciones, GUI, recuperación de inicialización GPU inyectada, descarga
corrupta, identidad de endpoint y dispositivo ausente. Ruff también aprobado.

Los tests de buffer y cola verifican límites, discontinuidad y orden; no son una
prueba de ocho horas. La recuperación de CUDA fatal está implementada por
aislamiento y reinicio, pero no se provocó un fallo real del driver.

## YouTube y navegador real

Se reprodujo audio real desde el navegador integrado, con WASAPI real en CUDA,
sin guardar audio ni transcripciones:

- [Try something new for 30 days — Matt Cutts / TED-Ed](https://www.youtube.com/watch?v=UNP03fDSj1U):
  tramo etiquetado después de omitir publicidad: 17 fragmentos confirmados EN,
  17 provisionales EN y cero eventos ES. La fase anterior incluyó publicidad
  en inglés y se separó del conteo principal.
- [Cómo engañar a tu cerebro para aprender más rápido — Ezequiel Martinez / TEDxRosario](https://www.youtube.com/watch?v=A5mMFztAyuM):
  65 fragmentos confirmados ES, 78 provisionales ES, cero confirmaciones EN,
  **un provisional EN incorrecto o ambiguo**. La separación provisional no fue
  perfecta. Se reforzó el tratamiento de nombres y fragmentos cortos con contexto
  acústico; no se afirma haber eliminado todos esos errores.

La prueba duró 180,3 s y terminó sin errores del servicio. Contadores en
`artifacts/browser-probe.json`. No hay referencia humana alineada de estos videos:
**no se calculó WER ni exactitud de idioma por palabra sobre YouTube**.

## Ensayo continuo de 15 minutos

Completado: 900,015 s de streaming a velocidad real de la conversación sintética
repetida; small/FP16, VAD y estabilización reales. 627 fragmentos confirmados,
cero errores, cero cuadros descartados. RSS después del primer minuto:
809,75–811,17 MB; última muestra 811,16 MB. Muestreo cada 30 s.

Informe: `artifacts/soak-result.json`. No se observó una cola creciente. Es una
prueba ASR desde archivo, **no acredita ocho horas ni 15 minutos continuos de
WASAPI/GUI**. Coincidió con otras pruebas GPU y no fue un entorno aislado.

## Fuentes simultáneas

Prueba de cinco segundos: salida ROG PELTA seleccionada explícitamente, WAV
reproduciéndose y micrófono ROG PELTA en paralelo. En la última repetición se
recibieron 140 cuadros del sistema y 139 del micrófono; ambos hilos terminaron.
Solo se guardaron contadores
(`artifacts/sources-probe.json`). No se evaluó precisión del micrófono ni AEC.

Un primer intento de micrófono falló. Se sincronizó inicialización/terminación
de PortAudio y se incorporó pycaw/COM para consultar identidad fresca de Core
Audio; después ambas fuentes abrieron. Desenchufar y cambiar salida físicamente
sigue pendiente de ensayo manual.

## Pruebas aún pendientes

- Conversaciones humanas con ruido, acentos argentinos y voces superpuestas;
  medir WER/CER y exactitud de idioma por palabra con referencias humanas.
- Cambios EN/ES de una palabra dentro de una misma frase sin pausas.
- Desenchufar físicamente auriculares, reconectar y cambiar salida mientras habla.
- Micrófono + salida simultánea con conversación real y posible eco.
- Sesiones completas de 30/60 minutos y ocho horas, con WASAPI y GUI.
- Convivencia con OBS, Discord y varios videos; pantalla completa exclusiva/DRM.
- Instalación en otra PC Windows limpia y runtimes CUDA alternativos.

El primer EXE falló al cargar QtWidgets. Se fijó PySide6 Essentials 6.8.3 para
corregir el empaquetado. La validación del EXE final se documenta separadamente.

## Ejecutable final y fallback CPU

La compilación Windows x64 sin consola, PySide6 Essentials 6.8.3 y PyInstaller
6.22.3 pasó la prueba real incorporada `--self-test`: se abrió GUI/overlay desde
el EXE, reprodujo el WAV sintético, capturó WASAPI y recibió confirmaciones en
ambos paneles. Registró nueve provisionales distintos EN y trece ES, CUDA activo,
pausa/continuación y proceso detenido correctamente. Duración total de la prueba:
52,468 s (incluye carga, reproducción y cierre). Historial desactivado.

Última muestra: inferencia 132,7 ms, último cuadro a publicación 125 ms, entrega
UI 16 ms. Son relojes/muestras diferentes, no una suma ni un percentil de sesión.
Reporte `artifacts/exe-selftest.json` y captura `artifacts/exe-selftest.png`.
El paquete ocupa aproximadamente 415,5 MiB antes del ZIP, sin pesos ni runtime
NVIDIA; el EXE necesita su carpeta `_internal`.

También se ejecutó base en CPU INT8 sobre `short_es.wav`: cinco palabras,
idioma ES y 1.137 ms de inferencia. Comprueba ejecución CPU real; no se midió
streaming CPU prolongado ni se garantiza igual latencia que CUDA.

El descargador propio completó una descarga real de tiny (~75 MB de pesos)
con verificación SHA256, revisión fijada y manifiesto `verified.json`. Base y
small se identifican por SHA256 en `docs/research/model-revisions.json`. Esto no sustituye
ensayos de cortes de red en GUI.

Se repitió la prueba del **EXE definitivo** después de fijar inicialización COM
por hilo de captura: 52,390 s, CUDA, confirmaciones en ambos paneles, once
provisionales EN y trece ES, pausa/continuación/detención aprobadas. Última
inferencia 164,6 ms, publicación 172 ms, entrega UI 16 ms. Evidencia exacta de
esta entrega: `artifacts/exe-final.json` y `artifacts/exe-final.png`.

La repetición final de streaming conservó WER EN 0% y ES 9,375%, sin descartes.
Primera publicación 0,823–1,648 s. Usar `artifacts/benchmark.json` o
`benchmark-small.json` para reproducir las estadísticas de esta repetición.
