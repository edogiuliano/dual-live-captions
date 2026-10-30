# Comparación real con Windows Live Captions

Preparado el 30 de octubre de 2026. Usa el audio que el usuario ya está usando;
no reproduce muestras ni modifica volumen, salida de audio o preferencias de
privacidad. Windows Live Captions y Dual continúan transcribiendo por separado.

## Uso sin terminal

Abrir **Comparar subtítulos.lnk** en `D:/SUbtitle`. Mantener abiertas la ventana
de Windows Live Captions y Dual o su overlay. La comparación comienza con una
sesión de 30 minutos, configurable hasta 480. Se puede minimizar el comparador.
Al terminar el tiempo, se detiene únicamente la medición, no los subtítulos.

El informe numérico se actualiza cada dos segundos en
`artifacts/comparison/<fecha-hora>/report.json`. El botón **Terminar y guardar
métricas** finaliza antes. **Pausar medición** pausa solo la lectura y al
continuar establece una nueva línea de base para no inventar tiempos del período
no observado. Cambiar el panel de idioma también reinicia la muestra.

Este lanzador usa el Python local de este proyecto y no requiere escribir
comandos. No modifica el ejecutable ni sus preferencias. Para reproducir
desde desarrollo: `python scripts/compare_windows.py --minutes 30 --language en`.

## Qué lee y qué guarda

El lector usa UI Automation de Windows, con comtypes ya instalado. Enumera solo
identidades y títulos de procesos `LiveCaptions.exe` y `DualLiveCaptions.exe`.
En Windows lee exclusivamente `CaptionsTextBlock`; en Dual, las etiquetas de los
paneles EN/ES. Prefiere el overlay si es visible. No lee Chrome Live Caption,
otras ventanas, correos, páginas, archivos personales ni el portapapeles.

Texto nuevo y marcas temporales se conservan únicamente en RAM, con límites.
El JSON contiene métricas, contadores y tiempos; **no contiene palabras de las
conversaciones, audio ni capturas de pantalla**. No hay conexiones de red.
La sesión se puede cerrar o detener; las palabras temporales se liberan.

Todo texto que ya estaba en las ventanas al arrancar queda excluido. Si una
ventana se cierra, cambia de identidad o deja de poder leerse, se indica el
problema y se restablece la línea de base al recuperarse. No se interpreta la
ausencia de lectura como una demora del motor. El informe cuenta los reinicios.

## Interpretación de los números

- **Diferencia de aparición:** tiempo de primera aparición exacta de una palabra
  en Dual menos el de esa misma palabra en Windows. `+0,50 s` significa que Dual
  apareció medio segundo después. Valores negativos favorecen a Dual.
- Se emparejan bloques de al menos tres palabras coincidentes y con tiempos
  plausibles; las repeticiones muy separadas no se usan. Se exige un segundo
  desde la primera aparición para incluir una palabra en la muestra estable.
- La mediana y P10/P90 describen esas palabras emparejadas. Las palabras que
  difieren o faltan no proporcionan una muestra temporal: hay sesgo de selección.
- **Coincidencia de palabras:** uno menos la distancia de edición normalizada,
  calculada entre anclas comunes. Los extremos todavía retrasados se excluyen.
  No es WER contra una referencia humana y no equivale a exactitud del ASR.
- **Correcciones:** palabras ya expuestas que después se reemplazan o eliminan.
  Incluye texto provisional. El desplazamiento de líneas antiguas fuera del
  panel no se cuenta como corrección.

Una corrección conserva su posición en la frase y recibe un nuevo tiempo de
aparición. Así se evita mover artificialmente las palabras corregidas al final
de la conversación. El algoritmo se prueba con casos sintéticos deterministas,
independientemente de la observación real de Windows.

El muestreo objetivo es de 100 ms; se muestran intervalo y costo reales. La
medición refleja texto expuesto por los controles de accesibilidad, no el instante
exacto de pintura de un cuadro del monitor. No mide el retraso absoluto desde el
inicio de voz: para eso hace falta una referencia de audio sincronizada.

Se mantienen hasta 180 segundos de palabras en RAM, con máximo 5.000 por motor,
y se alinean como máximo las últimas 300 palabras estables. El historial numérico
está limitado a 3.600 muestras. Los valores mostrados son de una ventana móvil,
no una media infalible de toda la jornada.

## Idiomas y límites de esta prueba

El panel seleccionado debe coincidir con el idioma que Windows esté reconociendo.
Si subís por el historial de un panel, el comparador espera y
no asigna tiempos a esas palabras antiguas. Pulsá **↓ Lo último** para retomar;
la muestra establece una nueva línea de base.
El comparador no cambia ese idioma y marca que no lo verificó automáticamente.
El otro panel de Dual se cuenta como actividad, sin evaluarlo contra un Windows
configurado en otro idioma.

Si el audio alterna idiomas mientras Windows reconoce uno solo, sus errores
pueden reducir la coincidencia aun cuando Dual transcriba mejor. Windows tampoco
es la verdad de referencia. Sin una transcripción humana no se puede decidir
automáticamente cuál de dos versiones distintas es correcta.

Texto inactivo no produce una latencia ficticia de cero. Una muestra pequeña se
marca como tal. Si el usuario cambia el idioma de Windows, debe cambiar también
el panel seleccionado en el comparador. Evitar abrir dos sesiones del comparador
sin necesidad. Este monitor no incorpora grabación de conversaciones.
