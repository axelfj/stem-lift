# Changelog

## Unreleased: V2 preparation

- Exigir Demucs por defecto; rechazar colisiones de salida y publicar stems mediante staging sin sobrescritura; cancelar con limpieza de resultados propios.
- Todavía no constituye una versión V2 publicada ni valida binarios nativos.

## 1.1.0a1

Repair Ready: reparación básica de grabaciones sin IA, en una pestaña nueva y por línea de comandos (`stem-lift-repair`). / Repair Ready: basic restoration without AI, in a new tab and from the command line.

- **De-click**: detecta clicks y pops por la segunda diferencia de la señal frente a su rango robusto local (MAD) y los reconstruye con una spline cúbica desde las muestras limpias de ambos lados. Prueba: 50 clicks sintéticos sobre un seno dejan un residuo por debajo de −40 dB y el resto de la señal no se toca.
- **De-clip**: encuentra tramos planos en el pico del archivo (o por encima de un umbral) y los reconstruye con un arco de coseno que encaja con el valor y la pendiente de ambos bordes (exacto para una onda; Hermite cúbico cuando el tramo no parece la cima de una onda), bajando la ganancia para que quepa y diciendo cuánto. Prueba: un seno recortado a 0,5 recupera su pico con error < 1 % a 100 y 440 Hz y < 4 % a 1 kHz (el issue pedía < 5 %).
- **De-hum**: elige 50 o 60 Hz (o el que le digas), afina la frecuencia exacta con la deriva de fase entre bloques y resta cada armónico medido en bloques de 1 s solapados (sigue cambios lentos de nivel, fase cero, sin resonancias de filtro). Prueba: zumbido de 60 Hz con 3 armónicos cae más de 30 dB y la música queda intacta; también sigue un zumbido a 50,4 Hz.
- Guarda `Canción - reparado.wav` y, opcional, `Canción - quitado.wav` con solo lo que se eliminó para escucharlo.
- La ventana ahora tiene dos pestañas: Separar stems y Reparar.

## 1.0.0a1

Primera versión para probar. / First test build.

- Separa canciones (WAV, AIFF, FLAC, MP3, OGG) en 4 stems (voz, batería, bajo, otros), 2 (voz e instrumental) o 6 (+ guitarra y piano) con Demucs (htdemucs / htdemucs_6s).
- Exporta WAV 24-bit a la frecuencia original, con nombres claros (`Canción - Voz.wav`), junto al archivo o en la carpeta que elijas.
- Ventana simple en español o inglés, barra de progreso y cancelar; también funciona por línea de comandos (`stem-lift canción.mp3 --mode 2`).
- El modelo (~80 MB) se descarga la primera vez; después funciona sin internet. CPU por defecto; usa CUDA o Apple MPS si están disponibles.
- Instaladores para Windows (.exe) y macOS (.dmg, Apple silicon).

