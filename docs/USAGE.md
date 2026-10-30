# Uso e instalación

## Windows portable

Extraer el ZIP de la versión 0.0.1 y conservar `_internal` junto a
`DualLiveCaptions.exe`. No requiere Python ni abrir una terminal cada vez.
El script opcional `install-portable.ps1`, incluido en el paquete, copia la
aplicación a Programas del usuario y crea un acceso en Inicio.

1. Elegir la salida de Windows o dejar la predeterminada.
2. Pulsar Iniciar. Si falta el modelo se informa su tamaño y se ofrece descargarlo
   desde Hugging Face, con progreso y verificación de integridad.
3. Reproducir audio normalmente. El programa no cambia el volumen ni la salida.
4. Overlay oculta la ventana principal, conservando la captura y el reconocimiento.
5. Arrastrar el encabezado/fondo vacío para mover y cualquier borde/esquina para
   cambiar tamaño. Separar/Unir permite tener una o dos ventanas.
6. Aa abre Personalización. La flecha vuelve a la ventana principal y × oculta.
   La bandeja de Windows también permite recuperar la interfaz o salir.

## Texto y apariencia

El texto provisional puede corregirse. Cada panel conserva 500 palabras recientes
por defecto; el límite puede configurarse. Agrandar muestra más contexto sin
aumentar la letra, salvo al activar tamaño automático. Subir con rueda o barra
permite releer sin saltar al final. Lo último restaura el seguimiento en vivo.

Color, fuente, tamaño, fondo y opacidad pueden compartirse o ajustarse por idioma.
Las líneas iniciales no limitan el resize manual. Las preferencias y posiciones
se guardan localmente. Desactivar Bloquear posición y click-through para mover.

Atajos existentes: Ctrl+Alt+O (overlay), Ctrl+Alt+P (pausa), Ctrl+Alt+U (recuperar
interacción). Los primeros dos se pueden configurar. Si recuperación está ocupada
por otra aplicación, click-through permanece deshabilitado.

## Motor y GPU

Los perfiles Rápido, Equilibrado y Preciso utilizan parámetros reales para
priorizar velocidad o calidad. Modelo, fuente de audio y procesamiento cambian
al detener e iniciar. CUDA/cuDNN son externos al paquete: ver [CUDA](CUDA.md).
El modo automático utiliza CPU cuando no encuentra un runtime GPU compatible.

El micrófono es opcional y se procesa separado del audio del sistema. Con altavoces
puede volver a captar la salida: se recomiendan auriculares para ambas fuentes.

## Privacidad y límites

No se graba audio, no hay telemetría obligatoria ni se envían conversaciones a
servicios externos. El historial completo está desactivado por defecto y vive en
RAM cuando se habilita. Solo Exportar escribe TXT/SRT/JSON. Los registros técnicos
omiten las conversaciones. Preferencias/modelos: `%LOCALAPPDATA%/DualLiveCaptions`.

Whisper puede omitir, confundir o inventar palabras, especialmente con ruido,
voces superpuestas y cambios de idioma muy cortos. No se garantiza latencia ni
exactitud. Captura por aplicación individual, prueba de ocho horas y validación
en Windows limpio siguen pendientes. Pantalla exclusiva, DRM y escritorio seguro
pueden limitar el overlay o la captura.
