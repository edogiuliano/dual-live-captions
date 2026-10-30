# CUDA, distribución y diagnóstico

Motor comprobado: faster-whisper 1.2.1, CTranslate2 4.8.3, RTX 3090,
driver 617.42, Windows x64, FP16. CTranslate2 usa CUDA directamente; el valor
"CUDA Version" de nvidia-smi describe capacidad del driver, no la presencia de
cuBLAS/cuDNN. Se realiza una inferencia de calentamiento antes de anunciar listo.

La [documentación oficial](https://github.com/SYSTRAN/faster-whisper#gpu)
requiere cuBLAS CUDA 12 y cuDNN 9. No mezclar cuDNN 8 ni copiar DLL al azar a
System32. Para instalar desde paquetes NVIDIA, usar sus términos e instrucciones
oficiales y una versión compatible con el driver.

El programa busca las bibliotecas en:

1. `gpu/` junto al EXE o en `%LOCALAPPDATA%/DualLiveCaptions/gpu`.
2. `DLC_CUDA_PATH` y `CUDA_PATH/bin`.
3. Directorios explícitos de `%LOCALAPPDATA%/DualLiveCaptions/gpu-paths.json`.
4. `torch/lib` en las rutas Python existentes.

Un directorio válido debe contener `cublas64_12.dll` y `cudnn64_9.dll`, además de
sus dependencias (cuBLASLt y los componentes de cuDNN).

También se puede seleccionar esa carpeta desde **Diagnóstico → Seleccionar
carpeta de bibliotecas CUDA / cuDNN**, sin editar archivos ni usar terminal.

Ejemplo del archivo de rutas:

```json
["C:/ruta/al/runtime/bin"]
```

En esta estación se reutilizó un runtime ya instalado y se guardó su ruta en la
configuración local. El paquete portable **no redistribuye** esas DLL NVIDIA.
Por ello, copiar el EXE a otro equipo no garantiza GPU sin instalar el runtime.
El fallback CPU sí viene con la aplicación. El modelo tampoco está incrustado.

En Configuración se puede elegir CPU, automático o CUDA, FP16 o INT8+FP16. La
cuantización puede cambiar rendimiento y precisión; se midió FP16. No se aplica
un límite físico de utilización GPU: un trabajador, sin batch, y perfiles pequeños
reducen la demanda. El usuario debe evaluar la convivencia con OBS/juegos.

Diagnóstico muestra versiones, GPU, memoria total de GPU observada, memoria del
proceso gráfico y métricas recientes. Los valores de memoria de nvidia-smi pueden
incluir otras aplicaciones; no atribuir toda esa cifra al motor.

Errores comunes:

- Modelo ausente: Iniciar ofrece descargarlo. Con conexión caída se conserva el
  archivo parcial y se puede reintentar. No se inicia ASR con un modelo incompleto.
- DLL o CUDA incompatible: automático usa CPU si no encuentra runtime. Una
  excepción recuperable reinicia el motor en CPU. Un fallo nativo termina solo
  el proceso ASR y la ventana puede reiniciarlo en CPU.
- Audio sin nivel: comprobar la salida seleccionada y reproducir voz. Una salida
  física diferente no se captura hasta seleccionarla o usar predeterminada.
- Dispositivo desconectado: reintento cada segundo. El seguimiento de salida
  predeterminada comprueba cambios cada dos segundos con snapshot nuevo.
- Sobrecarga: cola compartida de 96 cuadros, unos tres segundos con una fuente
  o 1,5 segundos con dos fuentes simultáneas. Se avisa
  de bloques descartados, se marca discontinuidad y se reinicia la estabilización.
  Reducir perfil o desactivar segunda fuente. No se promete conservar audio que
  la computadora no puede procesar en tiempo real.

Las bibliotecas Qt se distribuyen como DLL enlazadas dinámicamente en `_internal`.
Sus licencias y las de dependencias se recopilan en `THIRD_PARTY`; se conservan
los avisos. Para distribuir a terceros se debe revisar también la licencia de
los pesos y de cualquier runtime GPU agregado por el distribuidor.
