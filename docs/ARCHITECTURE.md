# Arquitectura

El overlay: `floating.OverlayManager` administra tres ventanas
livianas (unida/EN/ES) y los mismos dos CaptionPanel. Al separar se trasladan los
widgets, sin repetir eventos ni duplicar el proceso ASR. La ventana principal se
oculta; su temporizador continúa drenando IPC y entregando Caption a los paneles.
Los estilos por idioma y la geometría usan Settings.save existente. El editor de
personalización solo actualiza presentación. La captura y el motor no cambian.
`src/dual_live_captions` mantiene componentes independientes:

| Módulo | Responsabilidad |
|---|---|
| app / ui | QApplication, controles, estado, configuración, bandeja, descargas |
| overlay / hotkeys | Ventana superior sin foco, renderizado, geometría, atajos Win32 |
| audio | WASAPI loopback/micrófono, conversión estéreo/mono, soxr con estado, colas acotadas |
| asr | Interfaz ASREngine, adapter faster-whisper y Silero ONNX con estado por fuente |
| pipeline | VAD, preroll, buffer circular, planificación incremental y publicación |
| language | Clasificador local EN/ES y contraste con idioma acústico |
| subtitles | Palabras, eventos, Local Agreement, historial opt-in, exportadores |
| service | Proceso aislado, threads de captura, recuperación CPU y apagado |
| settings / models / runtime / diagnostics | Persistencia de preferencias, modelos, DLL y diagnóstico |

El motor es sustituible mediante `ASREngine.transcribe(audio) -> Recognition`.
Los tiempos de palabras se convierten del buffer a una línea temporal monotónica
común de la sesión, incluso tras detener e iniciar. Los eventos `Caption`
incluyen origen, idioma, inicio/fin, identificador y estado parcial/confirmado.

`windows_devices` usa pycaw/COM para consultar la identidad actual de endpoints
y dispositivos activos; no cambia default ni volumen. La captura compara esa
foto cada dos segundos y reabre los streams cuando cambia la topología, en lugar
de confiar únicamente en listas cacheadas de PortAudio. Inicialización, apertura
y cierre de PortAudio están sincronizados entre hilos.

## Flujo de audio real

Endpoint WASAPI compartido → callback PortAudio → cola local acotada → mono
float32 → soxr con estado a 16 kHz → cuadros 512 muestras (32 ms) → cola ASR
acotada → Silero recurrente por fuente → preroll 256 ms → buffer circular
10/14/18 segundos según perfil → decodificación periódica → estabilización →
clasificación EN/ES → eventos IPC → UI a intervalos de 40 ms.

Captura y modelo viven en un proceso hijo `spawn`, sin servidor de red. Cada
fuente tiene su propio hilo de captura y VAD/buffer/estabilizador. Una sola
inferencia se ejecuta a la vez. No se mezclan muestras ni contextos de fuentes.
La UI controla eventos de stop/pause. Detener descarta la cola y los parciales;
el historial confirmado, si está habilitado, permanece en RAM hasta limpiar/cerrar.

Un callback evita que una lectura bloqueante en un endpoint silencioso impida
cerrar. Se liberan explícitamente streams y remuestreadores. Los cambios de
default/hotplug provocan reapertura y la discontinuidad reinicia VAD y contexto.
Elegir un dispositivo específico conserva su nombre y espera su regreso.

## Estabilización e idioma

Whisper recibe siempre `task=transcribe`, idioma automático, temperatura cero,
timestamps por palabra y sin condicionamiento automático sobre texto generado.
Contexto acústico se conserva dentro del buffer solapado. Silencios no invocan
ASR. Se filtran segmentos de baja confianza, silencio y repetición excesiva.

Local Agreement confirma el prefijo coincidente en dos hipótesis sucesivas,
con margen al extremo del audio. Las marcas de tiempo evitan republicar palabras
confirmadas al volver a decodificar contexto. La cola provisional se reemplaza.
Una pausa de voz confirma la última hipótesis válida. El texto confirmado es
inmutable; esto también conserva errores confirmados prematuramente.

El idioma acústico se contrasta con Lingua restringido a inglés/español. Se
clasifican frases y, para grupos largos con evidencia suficiente, spans. Palabras
aisladas ambiguas requieren confianza acústica o se retienen. No hay dos motores
que publiquen traducciones de la misma intervención. Aun así, no se puede detectar
con certeza una traducción implícita generada por Whisper sin una referencia.
Code-switch de una o dos palabras dentro de una frase sigue siendo una limitación.

## Límites de memoria y privacidad

Cola ASR 96 bloques; cola de paquetes por endpoint 32 bloques; IPC 256 eventos;
buffer de audio máximo 24 s validado; cada panel conserva 500 palabras
confirmadas, configurable entre 100 y 2.000, y la vista incluye provisionales
dentro del mismo presupuesto. La vista desplazable es únicamente memoria local,
independiente del historial opt-in, de hasta 10.000 confirmaciones y retención temporal.
Sobrecarga descarta audio antiguo y se informa; no crece latencia indefinidamente.

Se escribe únicamente configuración y modelos durante el flujo normal. Logs
rotativos de 512 KB × 4 guardan tipos de error, sin texto/audio. Exportación
requiere acción del usuario. La aplicación no configura audio, volumen ni cables.

## Recuperación y límites

Errores de captura reintentan con espera cancelable. Fallos recuperables de
inferencia GPU reinician una vez en CPU. Si falla nativamente el proceso ASR, la
UI detecta su salida y puede iniciar CPU automáticamente. Un watchdog limita
la carga del modelo a 90 s y una inferencia a 30 s; termina el hijo que excede
ese plazo y permite una recuperación CPU. Detener espera cinco
segundos y luego termina el hijo si sigue bloqueado. No hay modelo cargado en
la UI. Los bloqueos del driver pueden necesitar intervención externa a la app.

No se implementaron per-process loopback, AEC, diarización de hablantes, soporte
de otros idiomas ni un backend AlignAtt. Frecuencias de monitor diferentes no
modifican el procesamiento ASR. Multi-monitor se basa en geometrías disponibles
de Qt; el overlay nunca toma foco al aparecer.

## Lectura desplazable

Cada panel contiene un QScrollArea con QLabel. En modo En vivo sigue el extremo
inferior; al subir entra en Releyendo. El ancla de palabra visible y su posición
vertical se preservan al llegar frases, redimensionar o recortar palabras antiguas.
Si el propio ancla fue eliminada por retención, se muestra el inicio disponible.
Lo último restaura el seguimiento. Fuente, anchura inicial, líneas y palabras
retenidas se ajustan en Configuración. Rueda y barra no registran atajos globales.

El comparador externo reconoce captionFollowState. Cuando se relee contenido
viejo pausa la lectura comparativa y restablece su línea de base al volver a
En vivo, evitando asignar una falsa primera aparición a texto anterior.
