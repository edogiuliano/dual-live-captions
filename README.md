# Dual Live Captions

**0.0.1 · Windows 11 x64**

Subtítulos en vivo en inglés y español, procesados localmente. Captura el audio
de Windows y muestra cada idioma por separado, **sin traducir**.

- Audio del sistema mediante WASAPI; micrófono opcional.
- Transcripción incremental con Whisper y aceleración NVIDIA cuando está disponible.
- Overlay unido o ventanas EN/ES independientes, movibles y redimensionables.
- Personalización de fuente, color y fondo; scroll para releer las palabras recientes.
- Historial opcional en memoria y exportación TXT, SRT o JSON.

## Empezar

1. Descargá el paquete Windows desde [Releases](https://github.com/edogiuliano/dual-live-captions/releases).
2. Extraé la carpeta completa y abrí `DualLiveCaptions.exe`.
3. Pulsá **Iniciar → Overlay**. Pasá el mouse para mostrar **Separar/Unir** y **Aa**.

El primer inicio ofrece descargar el modelo. GPU requiere CUDA/cuDNN compatibles;
también funciona en CPU. No se guarda audio ni se envían conversaciones a servidores.

## Proyecto

```text
src/       Aplicación
tests/     Pruebas y muestras sintéticas
scripts/   Lanzadores, compilación y herramientas de desarrollo
assets/    Icono de la aplicación
docs/      Uso, arquitectura e investigación
```

Ver [uso e instalación](docs/USAGE.md), [desarrollo y compilación](docs/DEVELOPMENT.md)
y [documentación](docs/README.md). El reconocimiento puede cometer errores; ver
[límites y validación](docs/testing/MANUAL_TESTS.md).

[Licencia MIT](LICENSE). Las dependencias y los modelos conservan sus licencias.
