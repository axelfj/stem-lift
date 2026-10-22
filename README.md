# Stem Lift

Separa cualquier canción en stems (voz, batería, bajo, otros) con inteligencia artificial. **Gratis, open source y sin cuentas.** Funciona sin internet después de la primera vez.

*Split any song into stems (vocals, drums, bass, other) with AI. Free, open source, no accounts. Works offline after the first run.*

Hecho por [ROMMUSER](https://rommuser.com) para productores que están empezando. Usa [Demucs](https://github.com/facebookresearch/demucs) de Meta (licencia MIT). Si quieres una mezcla o master profesional: [rommuser.com/estudio](https://rommuser.com/estudio).

## Descargar

En [Releases](https://github.com/axelfj/stem-lift/releases):

- **Windows:** `StemLift-Setup-<versión>.exe`. Si Windows dice "Windows protegió tu PC", pulsa *Más información* y *Ejecutar de todas formas* (el instalador no está firmado todavía; el código es público aquí).
- **macOS (Apple silicon):** `StemLift.dmg`. Arrastra la app a Aplicaciones. La primera vez: clic derecho → *Abrir*, o *Ajustes del Sistema → Privacidad y seguridad → Abrir de todas formas*.

El instalador pesa varios cientos de MB porque incluye PyTorch. El modelo de separación (~80 MB) se descarga la primera vez que separas una canción.

## Usar

1. Abre Stem Lift y pulsa **Abrir canción** (o una carpeta entera).
2. Elige 4 stems (voz, batería, bajo, otros), 2 (voz e instrumental) o 6 (+ guitarra y piano), y marca cuáles quieres exportar.
3. Espera. En una laptop normal tarda más o menos lo que dura la canción. Con GPU NVIDIA o Mac con Apple silicon es mucho más rápido.
4. Los stems quedan en una carpeta `Canción - stems` junto al archivo, como WAV de 24 bits a la frecuencia original.

Línea de comandos:

```
stem-lift "mi cancion.mp3"                     # 4 stems junto al archivo
stem-lift cancion.wav --mode 2 --out ./stems   # voz e instrumental
stem-lift carpeta/ --stems vocals,drums        # solo esos stems, para toda la carpeta
```

## Desde el código

```bash
pip install -r requirements.txt
pip install -r requirements-demucs.txt --extra-index-url https://download.pytorch.org/whl/cpu
python app.py
python -m unittest discover -s tests -v
```

Las pruebas no necesitan PyTorch: usan un backend de bandas de frecuencia (`--backend bands`) que separa de forma exacta pero no musical, pensado solo para probar la app y el CI.

## Estructura

```
stem_lift/separate.py   Backends: DemucsSeparator (real) y BandSeparator (pruebas)
stem_lift/job.py        Leer canción, separar, escribir stems
stem_lift/audio.py      Lectura/escritura con libsndfile
stem_lift/gui.py        Ventana tkinter      stem_lift/cli.py   Línea de comandos
stem_lift/i18n.py       Textos en español e inglés
tests/                  Pruebas sin modelo
installer/              Inno Setup (Windows); el .dmg se arma en CI
```

## Roadmap

En el [issue #1](https://github.com/axelfj/stem-lift/issues/1): GPU, lote, de-noise de voces (Clean Vox) y exportar listo para Stem Organizer.

## Licencia

MIT. Demucs es MIT; PyTorch es BSD.
