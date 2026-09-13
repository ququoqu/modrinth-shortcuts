#!/usr/bin/env python3
"""Modrinth Shortcuts — create desktop / app-menu launchers for Modrinth App instances."""

import os
import re
import sqlite3
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

APP_ID = "com.modrinth.ModrinthApp"
FALLBACK_ICON = "com.modrinth.ModrinthApp"

DESKTOP_DIR = os.path.expanduser("~/Desktop")
APPLICATIONS_DIR = os.path.expanduser("~/.local/share/applications")

# (db_path, launch command list without the uri arg, description)
CANDIDATES = [
    (
        os.path.expanduser("~/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/app.db"),
        ["flatpak", "run", APP_ID],
        "flatpak",
    ),
    (
        os.path.expanduser("~/.local/share/ModrinthApp/app.db"),
        ["modrinth-app"],
        "native",
    ),
    (
        os.path.expanduser("~/.local/share/com.modrinth.theseus/app.db"),
        ["modrinth-app"],
        "native (theseus)",
    ),
]


@dataclass
class Instance:
    id: str
    name: str
    path: str
    icon_path: str | None
    last_played: int | None


def find_install():
    for db_path, launch_cmd, kind in CANDIDATES:
        if os.path.isfile(db_path):
            return db_path, launch_cmd, kind
    return None, None, None


def load_instances(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT id, name, path, icon_path, last_played FROM instances ORDER BY name COLLATE NOCASE"
        )
        return [Instance(*row) for row in cur.fetchall()]
    finally:
        con.close()


def sanitize_filename(name):
    cleaned = re.sub(r"[/\\\n\r\t]", "-", name).strip()
    return cleaned or "Modrinth Instance"


def launch_uri(instance_id):
    return f"modrinth://launch/instance/{instance_id}"


def build_exec(launch_cmd, instance_id):
    parts = [*launch_cmd, launch_uri(instance_id)]
    return " ".join(
        f'"{p}"' if " " in p or ":" in p else p for p in parts
    )


def desktop_entry_contents(instance: Instance, launch_cmd, icon):
    exec_line = build_exec(launch_cmd, instance.id)
    name = instance.name.replace("\n", " ")
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f'Comment=Launch the "{name}" Modrinth instance\n'
        f"Exec={exec_line}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Game;\n"
        f"X-Modrinth-Instance-Id={instance.id}\n"
    )


def shortcut_path(directory, instance: Instance):
    return os.path.join(directory, f"{sanitize_filename(instance.name)}.desktop")


def find_existing_shortcuts(instance: Instance):
    found = []
    for d in (DESKTOP_DIR, APPLICATIONS_DIR):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".desktop"):
                continue
            fp = os.path.join(d, fn)
            try:
                with open(fp, "r", errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue
            if instance.id in content:
                found.append(fp)
    return found


def write_shortcut(directory, instance: Instance, launch_cmd, icon, trust_on_desktop):
    os.makedirs(directory, exist_ok=True)
    path = shortcut_path(directory, instance)
    with open(path, "w") as f:
        f.write(desktop_entry_contents(instance, launch_cmd, icon))
    os.chmod(path, 0o755)
    if trust_on_desktop and directory == DESKTOP_DIR:
        subprocess.run(
            ["gio", "set", path, "metadata::trusted", "yes"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return path


class App(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)
        self.master = master
        self.master.title("Modrinth Shortcuts")
        self.master.geometry("560x460")
        self.pack(fill="both", expand=True)

        self.db_path = None
        self.launch_cmd = None
        self.install_kind = None
        self.instances: list[Instance] = []
        self.check_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        self.status_label = ttk.Label(top, text="Locating Modrinth App…")
        self.status_label.pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        self.inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        sel_row = ttk.Frame(self)
        sel_row.pack(fill="x", pady=(6, 0))
        ttk.Button(sel_row, text="Select all", command=lambda: self._set_all(True)).pack(
            side="left"
        )
        ttk.Button(sel_row, text="Select none", command=lambda: self._set_all(False)).pack(
            side="left", padx=(6, 0)
        )

        dest_row = ttk.LabelFrame(self, text="Create shortcut in")
        dest_row.pack(fill="x", pady=8)
        self.dest_desktop = tk.BooleanVar(value=True)
        self.dest_menu = tk.BooleanVar(value=False)
        ttk.Checkbutton(dest_row, text="Desktop", variable=self.dest_desktop).pack(
            side="left", padx=6, pady=4
        )
        ttk.Checkbutton(
            dest_row, text="Application menu", variable=self.dest_menu
        ).pack(side="left", padx=6, pady=4)

        action_row = ttk.Frame(self)
        action_row.pack(fill="x")
        ttk.Button(
            action_row, text="Create shortcut(s)", command=self.create_selected
        ).pack(side="left")
        ttk.Button(
            action_row, text="Remove shortcut(s)", command=self.remove_selected
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            action_row,
            text="Add this app to menu",
            command=self.install_self_launcher,
        ).pack(side="right")

        self.log = tk.Text(self, height=5, state="disabled", wrap="word")
        self.log.pack(fill="x", pady=(8, 0))

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_all(self, value):
        for v in self.check_vars.values():
            v.set(value)

    def refresh(self):
        self.db_path, self.launch_cmd, self.install_kind = find_install()
        for child in self.inner.winfo_children():
            child.destroy()
        self.check_vars.clear()

        if not self.db_path:
            self.status_label.config(text="Modrinth App not found (looked for its instance database).")
            self.instances = []
            return

        try:
            self.instances = load_instances(self.db_path)
        except sqlite3.Error as e:
            self.status_label.config(text=f"Failed to read instance database: {e}")
            self.instances = []
            return

        self.status_label.config(
            text=f"Found {len(self.instances)} instance(s) — {self.install_kind} install"
        )

        for inst in self.instances:
            row = ttk.Frame(self.inner)
            row.pack(fill="x", anchor="w", pady=2)
            var = tk.BooleanVar(value=False)
            self.check_vars[inst.id] = var
            ttk.Checkbutton(row, variable=var).pack(side="left")
            ttk.Label(row, text=inst.name, width=30, anchor="w").pack(side="left")
            existing = find_existing_shortcuts(inst)
            status = f"{len(existing)} shortcut(s)" if existing else "no shortcut"
            ttk.Label(row, text=status, foreground="#666").pack(side="left", padx=(8, 0))

    def _selected_instances(self):
        return [i for i in self.instances if self.check_vars.get(i.id) and self.check_vars[i.id].get()]

    def create_selected(self):
        selected = self._selected_instances()
        if not selected:
            messagebox.showinfo("Modrinth Shortcuts", "Select at least one instance first.")
            return
        if not self.dest_desktop.get() and not self.dest_menu.get():
            messagebox.showinfo("Modrinth Shortcuts", "Choose at least one destination.")
            return

        for inst in selected:
            icon = inst.icon_path if inst.icon_path and os.path.isfile(inst.icon_path) else FALLBACK_ICON
            if self.dest_desktop.get():
                path = write_shortcut(DESKTOP_DIR, inst, self.launch_cmd, icon, trust_on_desktop=True)
                self._log(f"Created {path}")
            if self.dest_menu.get():
                path = write_shortcut(APPLICATIONS_DIR, inst, self.launch_cmd, icon, trust_on_desktop=False)
                self._log(f"Created {path}")
        self.refresh()

    def remove_selected(self):
        selected = self._selected_instances()
        if not selected:
            messagebox.showinfo("Modrinth Shortcuts", "Select at least one instance first.")
            return
        removed = 0
        for inst in selected:
            for path in find_existing_shortcuts(inst):
                try:
                    os.remove(path)
                    removed += 1
                    self._log(f"Removed {path}")
                except OSError as e:
                    self._log(f"Could not remove {path}: {e}")
        if removed == 0:
            self._log("No shortcuts found for the selected instance(s).")
        self.refresh()

    def install_self_launcher(self):
        os.makedirs(APPLICATIONS_DIR, exist_ok=True)
        script_path = os.path.abspath(__file__)
        path = os.path.join(APPLICATIONS_DIR, "modrinth-shortcuts.desktop")
        with open(path, "w") as f:
            f.write(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Modrinth Shortcuts\n"
                "Comment=Create desktop shortcuts for Modrinth App instances\n"
                f'Exec=python3 "{script_path}"\n'
                f"Icon={FALLBACK_ICON}\n"
                "Terminal=false\n"
                "Categories=Game;Utility;\n"
            )
        os.chmod(path, 0o755)
        self._log(f"Added launcher: {path}")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    sys.exit(main())
