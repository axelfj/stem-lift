"""Desktop window: drop a song, pick the stems, press go."""
import os
import queue
import threading

from . import APP_NAME, __version__
from .i18n import t
from .job import collect, run
from .repair import describe, repair_file
from .separate import MODES, Cancelled, make_separator


def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("%s %s" % (APP_NAME, __version__))
    root.geometry("760x620")
    root.minsize(640, 520)
    events = queue.Queue()
    state = {"busy": False, "cancel": threading.Event(), "out_dir": None, "separator": None}

    tk.Label(root, text=APP_NAME, font=("Helvetica", 20, "bold")).pack(pady=(16, 0))
    tk.Label(root, text=t("tagline"), fg="#555").pack(pady=(0, 10))

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    page = tk.Frame(notebook)
    notebook.add(page, text=t("tab_separate"))
    repair_page = tk.Frame(notebook)
    notebook.add(repair_page, text=t("tab_repair"))
    tk.Label(root, text=t("studio"), fg="#777", font=("Helvetica", 9)).pack(pady=(0, 8))

    # Mode and stems
    options = tk.Frame(page)
    options.pack(fill="x", padx=16)
    mode = tk.StringVar(value="4")
    stem_vars = {}

    stems_frame = tk.LabelFrame(options, text=t("stems"), padx=8, pady=6)
    stems_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def rebuild_stems(*_):
        for w in stems_frame.winfo_children():
            w.destroy()
        stem_vars.clear()
        for name in MODES[mode.get()]:
            var = tk.BooleanVar(value=True)
            stem_vars[name] = var
            tk.Checkbutton(stems_frame, text=t("stem_" + name), variable=var).pack(anchor="w")

    mode_frame = tk.LabelFrame(options, text=t("mode"), padx=8, pady=6)
    mode_frame.grid(row=0, column=0, sticky="nsew")
    for key in ("4", "2", "6"):
        tk.Radiobutton(mode_frame, text=t("mode_" + key), variable=mode, value=key,
                       command=rebuild_stems).pack(anchor="w")
    options.columnconfigure(0, weight=1)
    options.columnconfigure(1, weight=1)
    rebuild_stems()

    # Output folder
    out_frame = tk.Frame(page)
    out_frame.pack(fill="x", padx=16, pady=(10, 0))
    tk.Label(out_frame, text=t("output") + ":").pack(side="left")
    out_label = tk.Label(out_frame, text=t("same_folder"), fg="#555", anchor="w")
    out_label.pack(side="left", padx=6, fill="x", expand=True)

    def choose_out():
        folder = filedialog.askdirectory(title=t("output"))
        state["out_dir"] = folder or None
        out_label.configure(text=folder or t("same_folder"))

    tk.Button(out_frame, text=t("choose"), command=choose_out).pack(side="right")

    # Buttons
    bar = tk.Frame(page)
    bar.pack(fill="x", padx=16, pady=12)
    progress = ttk.Progressbar(page, maximum=1000)
    status = tk.Label(page, anchor="w", fg="#555", wraplength=720, justify="left")
    log = tk.Text(page, height=10, state="disabled", font=("Courier", 10))

    def say(text):
        log.configure(state="normal")
        log.insert("end", text + "\n")
        log.see("end")
        log.configure(state="disabled")

    def start(paths):
        if state["busy"]:
            messagebox.showinfo(APP_NAME, t("busy"))
            return
        files = collect(paths)
        if not files:
            messagebox.showinfo(APP_NAME, t("no_audio"))
            return
        chosen = [s for s, v in stem_vars.items() if v.get()] or None
        state["busy"] = True
        state["cancel"].clear()
        cancel_btn.configure(state="normal")
        status.configure(text=t("loading_model"))
        progress.configure(value=0)

        def work():
            try:
                if state["separator"] is None:
                    state["separator"] = make_separator()
                res = run(files, mode.get(), state["out_dir"], state["separator"], chosen,
                          progress=lambda n, total, p, f: events.put(("progress", (n, total, p, f))),
                          cancel=state["cancel"])
                events.put(("done", res))
            except Cancelled:
                events.put(("cancelled", None))
            except Exception as e:  # shown to the user, never swallowed
                events.put(("done", [(files[0], e)]))

        threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "progress":
                    n, total, p, f = value
                    status.configure(text=t("separating") % (os.path.basename(p), n + 1, total))
                    progress.configure(value=int(((n + f) / total) * 1000))
                elif kind == "cancelled":
                    finish(t("cancelled"))
                else:
                    ok = 0
                    folder = ""
                    for path, outcome in value:
                        if isinstance(outcome, Exception):
                            say(t("error") % (os.path.basename(path), outcome))
                        else:
                            ok += 1
                            folder = os.path.dirname(outcome[0]) if outcome else folder
                            for p in outcome:
                                say(p)
                    finish(t("done") % (ok, folder))
        except queue.Empty:
            pass
        root.after(100, poll)

    def finish(text):
        state["busy"] = False
        cancel_btn.configure(state="disabled")
        status.configure(text=text)
        progress.configure(value=1000 if not text.startswith(t("cancelled")) else 0)

    def open_files():
        start(list(filedialog.askopenfilenames(
            title=t("open"),
            filetypes=[("Audio", "*.wav *.wave *.aif *.aiff *.flac *.mp3 *.ogg *.opus"), ("All files", "*.*")])))

    def open_folder():
        folder = filedialog.askdirectory(title=t("open_folder"))
        if folder:
            start([folder])

    tk.Button(bar, text=t("open"), width=18, command=open_files).pack(side="left", padx=4)
    tk.Button(bar, text=t("open_folder"), width=18, command=open_folder).pack(side="left", padx=4)
    cancel_btn = tk.Button(bar, text=t("cancel"), width=12, state="disabled",
                           command=lambda: state["cancel"].set())
    cancel_btn.pack(side="right", padx=4)

    progress.pack(fill="x", padx=16)
    status.pack(fill="x", padx=16, pady=(6, 0))
    log.pack(fill="both", expand=True, padx=16, pady=10)
    say(t("intro"))
    build_repair_tab(repair_page, root, state, tk, ttk, filedialog, messagebox)

    # Drag and drop where the platform offers it without extra packages (macOS Finder open-with).
    try:
        root.createcommand("::tk::mac::OpenDocument", lambda *paths: start(list(paths)))
    except tk.TclError:
        pass

    poll()
    root.mainloop()


def build_repair_tab(page, root, state, tk, ttk, filedialog, messagebox):
    """Repair Ready: de-click, de-clip, de-hum on files, with 'listen to what was removed'."""
    events = queue.Queue()
    options = {"declick": tk.BooleanVar(value=True), "declip": tk.BooleanVar(value=True),
               "dehum": tk.BooleanVar(value=False), "hum": tk.StringVar(value="auto"),
               "removed": tk.BooleanVar(value=False), "sens": tk.DoubleVar(value=1.0)}

    tk.Label(page, text=t("repair_intro"), justify="left", fg="#333").pack(anchor="w", padx=16, pady=(10, 6))
    box = tk.Frame(page)
    box.pack(fill="x", padx=16)
    row = tk.Frame(box)
    row.pack(fill="x")
    tk.Checkbutton(row, text=t("declick"), variable=options["declick"]).pack(side="left")
    tk.Label(row, text="   " + t("declick_sens")).pack(side="left")
    tk.Scale(row, variable=options["sens"], from_=0.5, to=2.0, resolution=0.1, orient="horizontal",
             length=140, showvalue=True).pack(side="left")
    tk.Checkbutton(box, text=t("declip"), variable=options["declip"]).pack(anchor="w")
    row = tk.Frame(box)
    row.pack(fill="x")
    tk.Checkbutton(row, text=t("dehum"), variable=options["dehum"]).pack(side="left")
    for key, label in (("auto", t("hum_auto")), ("50", "50 Hz"), ("60", "60 Hz")):
        tk.Radiobutton(row, text=label, variable=options["hum"], value=key).pack(side="left", padx=(6, 0))
    tk.Checkbutton(box, text=t("write_removed"), variable=options["removed"]).pack(anchor="w")

    out_frame = tk.Frame(page)
    out_frame.pack(fill="x", padx=16, pady=(10, 0))
    tk.Label(out_frame, text=t("output") + ":").pack(side="left")
    out_label = tk.Label(out_frame, text=t("same_folder"), fg="#555", anchor="w")
    out_label.pack(side="left", padx=6, fill="x", expand=True)
    local = {"out_dir": None, "busy": False}

    def choose_out():
        folder = filedialog.askdirectory(title=t("output"))
        local["out_dir"] = folder or None
        out_label.configure(text=folder or t("same_folder"))

    tk.Button(out_frame, text=t("choose"), command=choose_out).pack(side="right")

    bar = tk.Frame(page)
    bar.pack(fill="x", padx=16, pady=12)
    progress = ttk.Progressbar(page, maximum=1000)
    status = tk.Label(page, anchor="w", fg="#555", wraplength=720, justify="left")
    log = tk.Text(page, height=8, state="disabled", font=("Courier", 10))

    def say(text):
        log.configure(state="normal")
        log.insert("end", text + "\n")
        log.see("end")
        log.configure(state="disabled")

    def start(paths):
        if local["busy"] or state["busy"]:
            messagebox.showinfo(APP_NAME, t("busy"))
            return
        files = collect(paths)
        if not files:
            messagebox.showinfo(APP_NAME, t("no_audio"))
            return
        local["busy"] = True
        progress.configure(value=0)
        opts = {k: v.get() for k, v in options.items()}
        hum_hz = None if opts["hum"] == "auto" else float(opts["hum"])

        def work():
            results = []
            for n, path in enumerate(files):
                events.put(("progress", (n, len(files), path, 0.0)))
                try:
                    written, report = repair_file(
                        path, local["out_dir"], opts["declick"], opts["declip"], opts["dehum"], hum_hz,
                        opts["sens"], opts["removed"],
                        progress=lambda f, n=n, path=path: events.put(("progress", (n, len(files), path, f))))
                    results.append((path, written, report))
                except Exception as e:  # shown to the user, never swallowed
                    results.append((path, e, None))
            events.put(("done", results))

        threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "progress":
                    n, total, p, f = value
                    status.configure(text=t("repairing") % (os.path.basename(p), n + 1, total))
                    progress.configure(value=int(((n + f) / total) * 1000))
                else:
                    ok = 0
                    for path, outcome, report in value:
                        if isinstance(outcome, Exception):
                            say(t("error") % (os.path.basename(path), outcome))
                        else:
                            ok += 1
                            say("%s: %s" % (os.path.basename(path), describe(report)))
                            for p in outcome:
                                say("    " + p)
                    local["busy"] = False
                    status.configure(text=t("repair_done") % ok)
                    progress.configure(value=1000)
        except queue.Empty:
            pass
        root.after(100, poll)

    def open_files():
        start(list(filedialog.askopenfilenames(
            title=t("repair_open"),
            filetypes=[("Audio", "*.wav *.wave *.aif *.aiff *.flac *.mp3 *.ogg *.opus"), ("All files", "*.*")])))

    def open_folder():
        folder = filedialog.askdirectory(title=t("open_folder"))
        if folder:
            start([folder])

    tk.Button(bar, text=t("repair_open"), width=18, command=open_files).pack(side="left", padx=4)
    tk.Button(bar, text=t("open_folder"), width=18, command=open_folder).pack(side="left", padx=4)
    progress.pack(fill="x", padx=16)
    status.pack(fill="x", padx=16, pady=(6, 0))
    log.pack(fill="both", expand=True, padx=16, pady=10)
    poll()
