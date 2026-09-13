# Modrinth Shortcuts

A small desktop app for creating Desktop / application-menu shortcuts that launch a specific [Modrinth App](https://modrinth.com/app) instance directly, instead of opening Modrinth App and clicking into the instance yourself.

## Requirements

- Linux with Python 3 (includes `tkinter`)
- [Modrinth App](https://modrinth.com/app) installed (Flatpak `com.modrinth.ModrinthApp`, or a native install)
- `gio` (part of GLib, present on most GNOME systems) — optional, only used to mark Desktop shortcuts as trusted so GNOME doesn't prompt "Allow Launching" the first time you double-click one

## Running it

```bash
python3 modrinth_shortcuts.py
```

## What it does

On startup it locates Modrinth App's instance database and lists every instance you have, along with how many shortcuts already exist for each one (it detects shortcuts made by this tool *or* by hand, anywhere in `~/Desktop` or `~/.local/share/applications`).

- **Select all / Select none** — quickly (de)select every instance in the list.
- **Create shortcut(s)** — for each checked instance, writes a `.desktop` launcher to whichever destination(s) you've ticked:
  - **Desktop** — `~/Desktop`
  - **Application menu** — `~/.local/share/applications`
- **Remove shortcut(s)** — deletes any shortcut file pointing at the checked instance(s), wherever it's found.
- **Refresh** — re-scans instances and shortcut status (use after adding/removing instances in Modrinth App).
- **Add this app to menu** — creates a launcher for Modrinth Shortcuts itself, so you can reopen it from your app grid later.

Each generated shortcut runs:

```
flatpak run com.modrinth.ModrinthApp "modrinth://launch/instance/<instance-id>"
```

(or `modrinth-app "modrinth://launch/instance/<instance-id>"` for a native install), which tells Modrinth App to launch that exact instance directly.

## Icons

If an instance has a custom uploaded icon, the shortcut uses it. Instances using one of Modrinth's built-in generated symbol+background icons (not a custom image) fall back to the Modrinth logo, since those icons aren't stored as a static image file.

## Notes

- The app only reads Modrinth App's database (opened read-only) — it never modifies your instances, mods, or settings.
- Shortcut filenames are based on the instance name (e.g. `Main.desktop`); characters that aren't valid in filenames are replaced with `-`.
