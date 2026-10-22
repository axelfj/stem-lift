"""Two-language strings. Spanish when the system language is Spanish, English otherwise."""
import locale
import os

_STRINGS = {
    "tagline": ("Separa cualquier canción en stems. Gratis.", "Split any song into stems. Free."),
    "intro": (
        "Arrastra una canción o pulsa \"Abrir canción\". Stem Lift la separa en voz, batería,\n"
        "bajo y otros, y guarda un WAV por stem junto al archivo original.\n\n"
        "La primera vez descarga el modelo (unos 80 MB). Después funciona sin internet.\n"
        "En una laptop normal tarda más o menos lo que dura la canción.",
        "Drop a song here or press \"Open song\". Stem Lift splits it into vocals, drums,\n"
        "bass and other, and saves one WAV per stem next to the original file.\n\n"
        "The first run downloads the model (about 80 MB). After that it works offline.\n"
        "On a normal laptop it takes roughly the length of the song.",
    ),
    "open": ("Abrir canción...", "Open song..."),
    "open_folder": ("Abrir carpeta...", "Open folder..."),
    "cancel": ("Cancelar", "Cancel"),
    "mode": ("Modo", "Mode"),
    "stems": ("Stems a exportar", "Stems to export"),
    "mode_4": ("4 stems: voz, batería, bajo, otros", "4 stems: vocals, drums, bass, other"),
    "mode_2": ("2 stems: voz e instrumental", "2 stems: vocals and instrumental"),
    "mode_6": ("6 stems: + guitarra y piano", "6 stems: + guitar and piano"),
    "output": ("Carpeta de salida", "Output folder"),
    "same_folder": ("Junto al archivo original", "Next to the original file"),
    "choose": ("Elegir...", "Choose..."),
    "loading_model": ("Descargando y cargando el modelo (solo la primera vez)...",
                      "Downloading and loading the model (first time only)..."),
    "separating": ("Separando %s (%d de %d)...", "Separating %s (%d of %d)..."),
    "done": ("Listo: %d canción(es) separadas en %s", "Done: %d song(s) separated into %s"),
    "cancelled": ("Cancelado.", "Cancelled."),
    "error": ("Error con %s: %s", "Error with %s: %s"),
    "no_audio": ("Ahí no hay archivos de audio.", "No audio files found there."),
    "busy": ("Espera a que termine la separación actual.", "Wait for the current separation to finish."),
    "device": ("Procesador", "Processor"),
    "studio": ("¿Quieres una mezcla o un master profesional? rommuser.com/estudio",
               "Want a professional mix or master? rommuser.com/estudio"),
    "stem_vocals": ("Voz", "Vocals"),
    "stem_drums": ("Batería", "Drums"),
    "stem_bass": ("Bajo", "Bass"),
    "stem_other": ("Otros", "Other"),
    "stem_guitar": ("Guitarra", "Guitar"),
    "stem_piano": ("Piano", "Piano"),
    "stem_instrumental": ("Instrumental", "Instrumental"),
}


def _system_is_spanish():
    for var in ("STEM_LIFT_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return v.lower().startswith("es")
    try:
        lang = locale.getlocale()[0] or ""
    except ValueError:
        lang = ""
    return lang.lower().startswith("es")


SPANISH = _system_is_spanish()


def t(key):
    es, en = _STRINGS[key]
    return es if SPANISH else en
