# Estado de aceptación y trabajo restante

## Implementado y comprobado

- [x] Aplicación de escritorio real PySide6, tema oscuro, dos paneles visibles.
- [x] WASAPI loopback real sobre la salida predeterminada de Windows.
- [x] Captura de navegador comprobada con videos de YouTube en inglés y español.
- [x] ASR local EN/ES, sin usar una API de traducción.
- [x] Detección de cambios en la muestra bilingüe con pausas cortas.
- [x] Publicación durante el habla, provisional corregible y confirmación estable.
- [x] Deduplicación por palabras/tiempo y Local Agreement comprobados.
- [x] Iniciar, pausar, continuar y detener, con proceso ASR separado.
- [x] GPU RTX 3090 probada mediante inferencia FP16 real.
- [x] Overlay flotante, arrastre, tamaño, opacidad, fuente, líneas y dos monitores.
- [x] Control click-through y recuperación desde la ventana/bandeja.
- [x] Historial opt-in en RAM y exportadores TXT/SRT/JSON probados.
- [x] Tests automatizados y referencias sintéticas reproducibles.
- [x] Instrucciones y construcción Windows reproducible.
- [x] EXE Windows x64 sin consola generado y probado con audio real WASAPI/GPU.

## Implementado, requiere más validación real

- Selección de salida, seguimiento de default y reconexión ante hotplug.
- Micrófono solo o simultáneo con fuentes separadas (no mezcla ni AEC).
- Reinicio CPU después de excepción o terminación nativa GPU.
- Modelos descargables con progreso/verificación; probar interrupciones de red.
- Perfiles, idioma habilitado y ajustes aplicados al reiniciar captura.
- Atajos Win32 registrados; verificar colisiones y uso cotidiano en otras apps.

## Pendiente de implementar

1. Application Loopback por árbol de procesos, mediante API Win32 build 20348+.
2. Mejor segmentación acústica de cambios sin pausa, corpus humano y calibración
   de confianza para palabras cortas; comparar AlignAtt y modelos streaming.
3. Validar el watchdog de carga/inferencia bajo bloqueos nativos del driver;
   ampliar pruebas de fallos CUDA inyectados y reales.
4. Instalador firmado/MSI y prueba en Windows limpio. La carpeta portable es la
   distribución inicial; runtime CUDA externo y modelos no se incrustan.
5. Pruebas reales progresivas de 30/60/480 minutos con cambios de dispositivos,
   suspensión/reanudación, varias pantallas y otras cargas GPU.

## Criterios que no se deben declarar garantizados

Exactitud perfecta de idioma, ausencia absoluta de traducción implícita o
alucinaciones, no perder nunca palabras y estabilidad de ocho horas necesitan
evidencia que esta versión inicial todavía no tiene. Que el ASR no contenga un
traductor no convierte Whisper en un detector infalible de palabras originales.

La prueba YouTube y el ensayo ASR de 15 minutos terminaron y están registrados
en `BENCHMARKS.md`. Sigue pendiente una jornada prolongada de captura real.
