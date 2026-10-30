# Investigación inicial — 21 de octubre de 2026

## Decisión inicial

Implementar escritorio PySide6, WASAPI loopback mediante PyAudioWPatch y ASR local
faster-whisper/CTranslate2. Un solo modelo multilingüe, `task=transcribe`, idioma
automático, VAD Silero en CPU y estabilización Local Agreement. No se incorpora
ningún motor de traducción. La selección es provisional hasta las mediciones
reproducibles de `BENCHMARKS.md`; no supone superioridad universal.

El entorno real tiene Windows, RTX 3090 24 GB, driver 617.42, Python 3.10 y .NET
8/10. Python 3.14 predeterminado se evita para ampliar compatibilidad de ruedas
nativas. Hay modelos tiny/base en la caché del usuario y DLL CUDA 12/cuDNN 9 en
otra instalación local. Se deben verificar con inferencia, no solo nvidia-smi.

## Comparación de proyectos

Las fechas y licencias observadas por la API oficial están en
`repositories.json`; no indican que todos los cambios hayan sido releases.

| Tecnología | Evidencia y licencia actual | Ventajas para este proyecto | Limitaciones y decisión |
|---|---|---|---|
| [SimulStreaming](https://github.com/ufal/SimulStreaming) | MIT en la revisión actual; no confundir con anuncios antiguos de licencia no comercial. AlignAtt sobre Whisper, PyTorch y dependencias de atención | Política que usa alineamiento para decidir emisión, contexto y ASR multilingüe offline | Más integración y empaquetado Windows; no ofrece por sí solo captura WASAPI ni separación EN/ES por palabra. Candidato futuro; no se afirma haberlo medido |
| [WhisperLiveKit upstream](https://github.com/QuentinFuxa/WhisperLiveKit) | Apache-2.0; múltiples backends, servidor y UI web | Integra streaming, VAD y políticas de estabilización | Mucha funcionalidad fuera del MVP, capas de servidor/diarización/traducción. Se elige app local directa |
| [Fork solicitado](https://github.com/coloeso/whisperlivekit) | Fork de upstream, último push observado 2025-09-30, licencia API NOASSERTION | Referencia de integración SimulStreaming | No asumir licencia idéntica al upstream actual ni mantenimiento equivalente; no redistribuir su código |
| [WhisperLive](https://github.com/collabora/WhisperLive) | MIT; cliente/servidor y faster-whisper/TensorRT | Implementación casi en vivo, audio continuo | Servidor y cliente no resuelven overlay nativo ni clasificación de idiomas del producto |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT; CTranslate2, PyAV, ONNX Runtime; instalado 1.2.1 | Ruedas Windows, FP16/INT8, timestamps por palabra, CPU/GPU, sin FFmpeg externo | Whisper no es streaming nativo: se necesita política propia; idioma de una ventana no equivale al de todas sus palabras. Elegido para MVP |
| [Whisper-Streaming](https://github.com/ufal/whisper_streaming) | MIT; Local Agreement adaptativo | Evidencia publicada sobre procesamiento incremental y recorte | Latencia publicada pertenece a su corpus/equipo, no a esta máquina. Tomar política conceptual, implementar y medir |
| [Silero VAD](https://github.com/snakers4/silero-vad) | MIT, ONNX CPU y PyTorch, 8/16 kHz | VAD pequeño y con estado, evita inferir sobre silencio | No identifica idioma ni distingue toda música/voz; umbral configurable. Usar recurso incluido por faster-whisper |
| [OpenAI Whisper](https://github.com/openai/whisper) | MIT, modelos multilingües y PyTorch | Referencia de ASR, task transcribe conserva idioma | Ventanas cortas pueden alucinar o cambiar idioma; original requiere más dependencias. No se usa traducción |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | MIT, C/C++, GGML, cuantización y CUDA | Buena distribución nativa y fallback CPU | El ejemplo streaming no resuelve estabilización ni bilingüismo; alternativa de backend para otra versión |
| [FunASR](https://github.com/modelscope/FunASR) | MIT para toolkit; licencias de pesos independientes | Modelos streaming, VAD y puntuación | Verificar idiomas por modelo: no asumir que SenseVoice o Paraformer cubren español. Ecosistema de modelos y distribución más complejo |
| [NVIDIA Riva](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/asr/asr-overview.html) | Producto bajo términos NVIDIA; modelos incluyen code-switch es-en | Streaming entrenado, optimización GPU | [Matriz vigente](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/support-matrix/support-matrix.html): Riva SDK 2.26 orientado a L4T; x86 remite a NIM. No es una rueda Windows de escritorio. No usar cloud por defecto |
| [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) | Pesos CC-BY-4.0, 25 idiomas, NeMo/Transformers | ASR multilingüe reciente, incluido español | No equiparar modelo offline a streaming nativo; merece comparación Windows separada. No descargado |
| [Qwen3-ASR 0.6B](https://huggingface.co/Qwen/Qwen3-ASR-0.6B) | Apache-2.0 en la tarjeta/revisión consultada | Inglés/español, herramientas de streaming | Integración y aceleración Windows distintas de vLLM Linux; no medido ni descargado |

## Estrategias bilingües

A: modelo multilingüe único evita dos versiones de la misma voz y duplica menos
el cómputo. Se vuelve a detectar idioma sin fijar inglés y se contrastan los
textos con un clasificador EN/ES local. La confianza acústica y el contexto
sirven para fragmentos ambiguos; no se fuerza la clasificación de un nombre.

B: dos decodificadores forzados EN y ES pueden producir sendas transcripciones
plausibles de una voz, inclusive traducirla implícitamente. Exige calibración
con referencias y selección; consume más GPU. No elegido por defecto.

C: clasificador acústico previo y ASR condicionado ahorra decodificaciones,
pero un error temprano y ventanas muy cortas pierden cambios de idioma. Se
reserva como experimento. Ninguna estrategia garantiza code-switch perfecto.
La evaluación automatizada debe separar WER, idioma, duplicación y latencia.

## Audio y overlay Windows

[WASAPI loopback](https://learn.microsoft.com/windows/win32/coreaudio/loopback-recording)
copia el audio del endpoint en modo compartido sin redirigir ni modificar el
volumen. Se captura con el formato nativo, mezcla a mono y remuestrea con estado
a 16 kHz. Sistema y micrófono mantienen colas/estados separados: no se mezclan.
El micrófono puede volver a oír altavoces; usar auriculares, no prometer AEC.

[Application Loopback](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/)
requiere ActivateAudioInterfaceAsync, parámetros de proceso y Windows build
20348+. Es técnicamente viable, pero PyAudioWPatch opera por endpoint. Captura
por proceso se deja expresamente pendiente; no ofrecer una opción simulada.

Overlay Qt Tool, always-on-top, sin activación al mostrar. Click-through exige
un atajo global registrado correctamente y control desde ventana principal.
Pantalla completa exclusiva, DRM y escritorio seguro pueden impedir captura o
superposición. Frecuencias distintas de monitores no requieren igualar FPS:
actualizar por eventos y limitar repintados.

## Recursos y riesgos

CUDA 12 + cuDNN 9 según documentación de faster-whisper; detectar DLL y ejecutar
una prueba antes de anunciar GPU. FP16 por defecto en CUDA, INT8 en CPU, un
trabajador y beam pequeño para latencia. Sin batches grandes. tiny/base sirven
como diagnóstico, small como candidato equilibrado; large-v3/turbo opcionales
y con tamaño informado antes de descargar. No descargar pesos de varios GB
silenciosamente. PyTorch no es requisito del motor elegido.

Buffers y colas limitados, descarte explícito y visible en sobrecarga, historial
opt-in en RAM, exportación manual, logs rotativos sin audio/textos. Recuperación
de audio y fallback CPU ante errores recuperables. Los fallos nativos fatales
CUDA no siempre son capturables por Python: se deben documentar y probar.
Estabilidad de ocho horas y cambio físico de dispositivos requieren ensayos
reales; un test acelerado de buffers no los sustituye.

## Versionado y reproducibilidad

Dependencias resueltas quedan fijadas después de instalación. `repositories.json`
es una foto del 2026-10-21. `BENCHMARKS.md` contendrá resultados propios y comandos
de reproducción, diferenciando audio sintético, archivos reales, loopback y
pruebas manuales pendientes. No se trasladan cifras publicadas a este producto.

Tags observados mediante API oficial (`release-tags.json`): WhisperLiveKit
v0.2.26, WhisperLive v0.10.0, faster-whisper v1.2.1, Silero v6.2.3, Whisper
v20250625, FunASR v1.4.16 y whisper.cpp v1.9.5. Whisper-Streaming y el fork coloeso
no devolvieron tags; SimulStreaming devolvió `nc`, que no se debe confundir con
la licencia MIT de su rama actual.

Se agregó [pycaw](https://github.com/AndreMiras/pycaw), MIT, versión 20260927,
para consultar identidades reales de Core Audio y evitar confiar solo en listas
cacheadas de PortAudio. No se usan funciones de volumen. Se fijó PySide6
Essentials 6.8.3 tras un fallo real de QtWidgets del paquete inicial con 6.12.
