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
    # Repair Ready
    "tab_separate": ("Separar stems", "Separate stems"),
    "tab_repair": ("Reparar (Repair Ready)", "Repair (Repair Ready)"),
    "repair_intro": (
        "Arregla grabaciones sin IA: quita clicks y pops, reconstruye picos recortados y elimina el\n"
        "zumbido de la corriente (50/60 Hz). Guarda \"Canción - reparado.wav\" junto al archivo y, si\n"
        "quieres, \"Canción - quitado.wav\" con solo lo que se eliminó, para comprobarlo de oído.",
        "Fixes recordings without AI: removes clicks and pops, rebuilds clipped peaks and takes out\n"
        "mains hum (50/60 Hz). Saves \"Song - repaired.wav\" next to the file and, if you like,\n"
        "\"Song - removed.wav\" with only what was taken out, so you can check by ear.",
    ),
    "declick": ("Quitar clicks y pops", "Remove clicks and pops"),
    "declick_sens": ("Sensibilidad", "Sensitivity"),
    "declip": ("Reconstruir picos recortados (de-clip)", "Rebuild clipped peaks (de-clip)"),
    "dehum": ("Quitar zumbido de la corriente (de-hum)", "Remove mains hum (de-hum)"),
    "hum_auto": ("Automático", "Auto"),
    "write_removed": ("Guardar también lo que se quita", "Also save what was removed"),
    "repair_open": ("Reparar archivo...", "Repair file..."),
    "repairing": ("Reparando %s (%d de %d)...", "Repairing %s (%d of %d)..."),
    "repair_done": ("Listo: %d archivo(s) reparados", "Done: %d file(s) repaired"),
    "report_clicks": ("%d clicks", "%d clicks"),
    "report_clip": ("%d tramos recortados reconstruidos, ganancia %.1f dB", "%d clipped runs rebuilt, gain %.1f dB"),
    "report_hum": ("zumbido a %.2f Hz quitado", "hum at %.2f Hz removed"),
    "repaired_label": ("reparado", "repaired"),
    "removed_label": ("quitado", "removed"),
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
