# STARSTACK-ADDED: bench test helper (FORK_CHANGES.md #21). OFF unless ~/.starstack_dev exists.
#
# Lets the klipper-ui bench scripts drive the UI remotely (the Pi has no xdotool/XTest):
#   echo "click Load filament" > ~/.starstack_dev_cmd   press the first visible, sensitive button with that label
#   echo "show ss_print"       > ~/.starstack_dev_cmd   open a page (like tapping the rail)
#   echo "back"                > ~/.starstack_dev_cmd   close the current pop-up
# The result is written to ~/.starstack_dev_out. Remove ~/.starstack_dev and restart to disable.
import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

FLAG = os.path.expanduser("~/.starstack_dev")
CMD = os.path.expanduser("~/.starstack_dev_cmd")
OUT = os.path.expanduser("~/.starstack_dev_out")


def start(screen):
    if not os.path.exists(FLAG):
        return
    logging.warning("StarStack devtools ENABLED (bench only): remove ~/.starstack_dev to disable")
    GLib.timeout_add(300, _poll, screen)


def _labels(widget):
    out = []
    if isinstance(widget, Gtk.Label):
        out.append(widget.get_text())
    if isinstance(widget, Gtk.Container):
        for c in widget.get_children():
            out += _labels(c)
    return out


def _buttons(widget):
    found = []
    if isinstance(widget, Gtk.Button) and widget.is_visible() and widget.get_sensitive():
        found.append(widget)
    if isinstance(widget, Gtk.Container):
        for c in widget.get_children():
            found += _buttons(c)
    return found


def _poll(screen):
    try:
        if os.path.exists(CMD):
            with open(CMD) as f:
                cmd = f.read().strip()
            os.remove(CMD)
            result = _run(screen, cmd)
            with open(OUT, "w") as f:
                f.write(result + "\n")
    except Exception as e:
        logging.exception(e)
        with open(OUT, "w") as f:
            f.write(f"error: {e}\n")
    return True


def _run(screen, cmd):
    verb, _sp, arg = cmd.partition(" ")
    if verb == "show":
        screen.show_panel(arg, remove_all=True)
        return f"ok show {arg}"
    if verb == "back":
        screen._menu_go_back()
        return "ok back"
    if verb == "click":
        roots = [w for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.Dialog) and w.is_visible()]
        roots.append(screen.base_panel.main_grid)        # dialogs on top are searched first
        for b in [b for r in roots for b in _buttons(r)]:
            texts = _labels(b)
            if arg in texts or (b.get_tooltip_text() == arg):
                b.clicked()
                return f"ok click {arg}"
        return f"not found: {arg} | panels: {' > '.join(screen._cur_panels)}"
    if verb == "where":
        return " > ".join(screen._cur_panels)
    if verb == "sizes":      # who is asking for more height than the screen has?
        lines = [f"window {screen.get_allocated_width()}x{screen.get_allocated_height()} "
                 f"screen {screen.width}x{screen.height}"]

        def walk(w, depth):
            if depth > 7 or not w.get_visible():
                return
            mn, nat = w.get_preferred_height()
            lines.append(f"{'  ' * depth}{type(w).__name__} {' '.join(w.get_style_context().list_classes())} "
                         f"min_h={mn} nat_h={nat} alloc_h={w.get_allocated_height()}")
            if isinstance(w, Gtk.Container):
                for c in w.get_children():
                    walk(c, depth + 1)
        walk(screen.base_panel.main_grid, 0)
        return "\n".join(lines[:80])
    return f"unknown: {cmd}"
