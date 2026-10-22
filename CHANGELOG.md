# Changelog

## 1.0.0a1

Primera versión para probar. / First test build.

- Separa canciones (WAV, AIFF, FLAC, MP3, OGG) en 4 stems (voz, batería, bajo, otros), 2 (voz e instrumental) o 6 (+ guitarra y piano) con Demucs (htdemucs / htdemucs_6s).
- Exporta WAV 24-bit a la frecuencia original, con nombres claros (`Canción - Voz.wav`), junto al archivo o en la carpeta que elijas.
- Ventana simple en español o inglés, barra de progreso y cancelar; también funciona por línea de comandos (`stem-lift canción.mp3 --mode 2`).
- El modelo (~80 MB) se descarga la primera vez; después funciona sin internet. CPU por defecto; usa CUDA o Apple MPS si están disponibles.
- Instaladores para Windows (.exe) y macOS (.dmg, Apple silicon).
