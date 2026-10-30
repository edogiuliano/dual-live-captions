# Desarrollo

## Entorno

Windows 11 x64 y Python 3.10. Desde la raíz del proyecto:

```powershell
py -3.10 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
.venv/Scripts/python.exe -m pip install -e . --no-deps
.venv/Scripts/pythonw.exe scripts/launch.py
```

El código está en `src/dual_live_captions`. Los lanzadores permanecen en `scripts/`;
`scripts/packaging/` contiene recursos de distribución y `scripts/dev/` diagnósticos,
benchmark, muestras y pruebas manuales. Los cambios visuales no reinician el ASR.

## Pruebas

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src tests scripts --select F
```

Las cinco integraciones ASR requieren el modelo small ya descargado. Para incluirlas:

```powershell
$env:DLC_INTEGRATION = '1'
.venv/Scripts/python.exe -m pytest -q
Remove-Item Env:/DLC_INTEGRATION
```

CI usa `QT_QPA_PLATFORM=offscreen:configfile=tests/qt-offscreen.json` con dos pantallas
virtuales. Los tests Win32 de flags reales se reservan al backend nativo de Windows;
una ventana offscreen no tiene un HWND válido. No se cambian los monitores del usuario.
Configuración basada en la [implementación oficial de Qt 6.8.3](https://github.com/qt/qtbase/blob/v6.8.3/src/plugins/platforms/offscreen/qoffscreenintegration.cpp).

Las muestras en `tests/audio_samples/` son voces sintéticas con referencias del
proyecto, no conversaciones de usuarios. Pueden regenerarse con
`scripts/dev/generate_fixtures.ps1` si están disponibles las voces SAPI indicadas.
Las pruebas de reconocimiento desde archivos no reproducen audio por los parlantes.

## Compilar

```powershell
./scripts/build.ps1
```

El script verifica tests, lee la versión de la aplicación y genera:
`dist/0.0.1/DualLiveCaptions/DualLiveCaptions.exe`, metadatos de versión de Windows,
licencias y acceso directo local. `-SkipTests` permite reutilizar una corrida ya aprobada.
Los modelos y las bibliotecas NVIDIA se descargan/configuran aparte; no se incrustan.
El ejecutable todavía no está firmado digitalmente.

Verificación gráfica silenciosa con texto genérico, sin iniciar ASR:

```powershell
dist/0.0.1/DualLiveCaptions/DualLiveCaptions.exe --ui-check artifacts/ui-check.json
```

`scripts/dev/check_overlay_mouse.py` abre un fixture de texto sin audio. Benchmark y
soak escriben sus resultados en `artifacts/`. `scripts/dev/smoke_windows.py` **sí reproduce
audio sintético**: ejecutarlo únicamente cuando no interrumpa conversaciones reales.

## Publicación

La versión 0.0.1 inaugura el versionado público. Los prototipos están documentados en
`docs/archive/`; el código público empieza con un commit limpio. El historial local
previo permanece en la rama local anterior, sin publicarse con sus archivos generados.

No agregar `.venv`, `dist`, `build`, modelos, CUDA, capturas, conversaciones ni reportes
de máquina. `.gitignore` los excluye. Mantener las referencias sintéticas y las pruebas
junto al código; documentar los límites de cada medición.
