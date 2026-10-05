# STARSTACK-ADDED: shared code for the StarStack touchscreen UI (FORK_CHANGES.md #20)
#
# The StarStack UI is active only when the theme is "starstack", so choosing any
# other theme in KlipperScreen's settings gives back the stock UI.
#
# Contents:
#   enabled()            is the StarStack UI active?
#   MATERIALS            nozzle/bed temps (must match macros/starstack_macros.cfg in klipper-ui)
#   Advanced mode store  small JSON file next to the printer config
#   UI helpers           label(), button(), section(), dialogs (in-content, never cover the rail)
#   StarStackRail        the left rail: Home / Print / Controls / Settings + STOP
import json
import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

THEME = "starstack"
MATERIALS = {"PLA": (210, 60), "PETG": (240, 80), "TPU": (225, 40)}
SPEEDS = [("Silent", 50, "SPEED_SILENT"), ("Normal", 100, "SPEED_NORMAL"),
          ("Fast", 125, "SPEED_FAST"), ("Draft", 150, "SPEED_DRAFT")]
STATE_FILE = os.path.expanduser("~/printer_data/config/.starstack_ui.json")
PAGES = ("ss_home", "ss_print", "ss_controls", "ss_settings")
KEYBOARD_HEIGHT = 4 * (44 + 1) + 2 + 16       # 4 rows of 44 px keys, 1 px row gap, 16 px bottom margin (hook #13)


def enabled(screen):
    try:
        return screen._config.get_main_config().get("theme") == THEME
    except Exception:
        return False


# ---------------------------------------------------------------- settings store
def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def get_setting(key, default=None):
    return _load_state().get(key, default)


def set_setting(key, value):
    data = _load_state()
    data[key] = value
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except OSError as e:
        logging.error(f"StarStack: cannot save {key}: {e}")


def advanced(screen=None):
    return bool(get_setting("advanced", False))


# ---------------------------------------------------------------- printer helpers
def is_printing(printer):
    return printer is not None and printer.state in ("printing", "paused")


def gcode(screen, script, widget=None):
    """Send G-code without graying out the button: if Klipper is busy (e.g. waiting for a heater)
    the command queues, and a grayed button would look stuck until it runs (user report)."""
    screen._send_action(None, "printer.gcode.script", {"script": script})


def loaded_material(screen):
    """Remembered filament from Klipper save_variables (not subscribed by KlipperScreen, so query it)."""
    try:
        res = screen.apiclient.send_request("printer/objects/query?save_variables")
        var = res["status"]["save_variables"]["variables"].get("loaded_material", "NONE")
        return None if str(var).upper() == "NONE" else str(var).upper()
    except Exception as e:
        logging.debug(f"StarStack: loaded_material query failed: {e}")
        return None


def pretty_name(filename):
    base = os.path.splitext(os.path.basename(filename or ""))[0]
    for sep in ("_PLA", "_PETG", "_TPU", "_ABS", "_ASA"):
        if sep in base:
            base = base.split(sep)[0]
    base = base.replace("(1)", "").replace("_", " ").replace("-", " ").strip()
    return base[:1].upper() + base[1:] if base else filename


def pretty_object(name, index=None):
    """Klipper upper-cases object names (Orca: PART.STL_ID_0_COPY_1) → 'Part (2)'."""
    base = (name or "").split(".STL")[0].split(".3MF")[0].split(".OBJ")[0]
    base = base.replace("_", " ").replace("-", " ").strip().lower()
    base = base[:1].upper() + base[1:]
    return f"{base} ({index + 1})" if index is not None else base


def scan_color_changes(path, start=None, end=None):
    """Find color changes (M600/M601/PAUSE lines) in a G-code file. Runs in a worker thread.
    Returns {"changes": [byte offsets], "m73": [(offset, remaining_min)]}."""
    changes, m73 = [], []
    try:
        with open(path, "rb") as f:
            if start:
                f.seek(start)
            off = f.tell()
            for line in f:
                s = line.lstrip()
                if s[:1] in (b"M", b"P"):
                    if s.startswith((b"M600", b"M601", b"PAUSE")):
                        changes.append(off)
                    elif s.startswith(b"M73 ") and b" R" in s:
                        try:
                            m73.append((off, int(s.split(b" R")[1].split()[0])))
                        except (ValueError, IndexError):
                            pass
                off += len(line)
                if end and off > end:
                    break
    except OSError as e:
        logging.debug(f"StarStack: color scan failed: {e}")
    return {"changes": changes, "m73": m73}


def fmt_duration(seconds):
    if not seconds:
        return "–"
    seconds = int(seconds)
    h, m = seconds // 3600, (seconds % 3600) // 60
    return f"{h} h {m} min" if h else f"{max(m, 1)} min"


# ---------------------------------------------------------------- widget helpers
def label(text, css=None, xalign=0.0, wrap=False, ellipsize=False, lines=0):
    lbl = Gtk.Label(label=text, xalign=xalign)
    if lines:
        lbl.set_lines(lines)
        wrap = ellipsize = True
    if wrap:
        lbl.set_line_wrap(True)
        lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if ellipsize:
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
    for c in (css or "").split():
        lbl.get_style_context().add_class(c)
    return lbl


def button(text=None, sub=None, css="ss-btn", image=None, gtk=None, img_size=28, vertical=True):
    """Flat StarStack button: optional icon, main text and a small sub line."""
    b = Gtk.Button(can_focus=False, hexpand=True)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,
                  spacing=2 if vertical else 8, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    if image and gtk:
        box.add(gtk.Image(image, img_size, img_size))
    if text is not None:
        box.add(label(text, "ss-btn-text", xalign=0.5))
    if sub is not None:
        box.add(label(sub, "ss-btn-sub", xalign=0.5))
    b.add(box)
    for c in css.split():
        b.get_style_context().add_class(c)
    return b


def set_button_text(b, text=None, sub=None):
    labels = [w for w in b.get_child().get_children() if isinstance(w, Gtk.Label)]
    if text is not None and labels:
        labels[0].set_text(text)
    if sub is not None and len(labels) > 1:
        labels[1].set_text(sub)


def set_class(widget, css, on):
    ctx = widget.get_style_context()
    if on and not ctx.has_class(css):
        ctx.add_class(css)
    elif not on and ctx.has_class(css):
        ctx.remove_class(css)


def debounce(owner, attr, ms, fn):
    """Run fn once, ms after the last call (used to redraw when file metadata trickles in)."""
    from gi.repository import GLib
    if getattr(owner, attr, None):
        GLib.source_remove(getattr(owner, attr))

    def run():
        setattr(owner, attr, None)
        fn()
        return False
    setattr(owner, attr, GLib.timeout_add(ms, run))


def section(text):
    return label(text.upper(), "ss-section")


def page_box(spacing=8):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing, hexpand=True, vexpand=True)
    box.get_style_context().add_class("ss-page")
    return box


def grid(columns, spacing=6):
    g = Gtk.Grid(column_homogeneous=True, column_spacing=spacing, row_spacing=spacing, hexpand=True)
    g.ss_columns = columns
    return g


def grid_add(g, widgets):
    for i, w in enumerate(widgets):
        g.attach(w, i % g.ss_columns, i // g.ss_columns, 1, 1)


# ---------------------------------------------------------------- in-content dialogs
def _push(screen, panel, **kwargs):
    """Show one of our pop-up panels inside the content area (the rail stays visible)."""
    if screen._cur_panels and screen._cur_panels[-1] == panel:
        screen._menu_go_back()
    if panel in screen.panels:
        screen.panels_reinit = list(set(getattr(screen, "panels_reinit", []) + [panel]))
    screen.show_panel(panel, **kwargs)


def confirm(screen, title, body, yes_label, on_yes, kind="primary", no_label=None):
    """kind: primary | danger | warning"""
    _push(screen, "ss_dialog", ss_title=title, ss_body=body, ss_yes=yes_label,
          ss_no=no_label or _("Go back"), ss_on_yes=on_yes, ss_kind=kind)


def info(screen, title, body):
    _push(screen, "ss_dialog", ss_title=title, ss_body=body, ss_yes=None,
          ss_no=_("Close"), ss_on_yes=None, ss_kind="primary")


def close_dialog(screen):
    popups = ("ss_dialog", "ss_adjust", "ss_cancel_object", "ss_filament", "ss_prompt")
    if screen._cur_panels and screen._cur_panels[-1] in popups:
        screen._menu_go_back()


def adjust(screen, **kwargs):
    _push(screen, "ss_adjust", **kwargs)


def bed_clear_then_print(screen, filename):
    confirm(screen, _("Is the bed clear?"),
            _("Remove any old print from the bed before starting") + f"\n{pretty_name(filename)}.\n"
            + _("Printing on top of a part can damage the nozzle."),
            _("Bed is clear, print"), lambda: screen._ws.klippy.print_start(filename),
            no_label=_("Not yet"))


def ask_estop(screen):
    confirm(screen, _("Emergency stop?"),
            _("Stops everything immediately: heaters, motors and any print.") + "\n"
            + _("The print can't be resumed. Use this only if something is wrong."),
            _("STOP NOW"), screen._ws.klippy.emergency_stop, kind="danger")


# ---------------------------------------------------------------- the rail
class StarStackRail:
    """Replaces the stock action bar: 4 page buttons + STOP (always present, D-036)."""

    NAV = (("ss_home", "main", "Home"), ("ss_print", "files", "Print"),
           ("ss_controls", "fine-tune", "Controls"), ("ss_settings", "settings", "Settings"))

    def __init__(self, base):
        self.base = base
        self.screen = base._screen
        gtk = base._gtk
        bar = base.action_bar
        for child in bar.get_children():
            bar.remove(child)
        bar.set_size_request(64, -1)
        bar.set_spacing(0)
        bar.set_homogeneous(True)            # 5 equal slots down the rail: icons evenly spaced
        bar.get_style_context().add_class("ss-rail")
        size = 24
        self.nav = {}

        def slot(button, w, h):
            button.set_size_request(w, h)
            button.set_halign(Gtk.Align.CENTER)
            button.set_valign(Gtk.Align.CENTER)
            box = Gtk.Box(vexpand=True)
            box.set_center_widget(button)
            bar.pack_start(box, True, True, 0)

        for page, icon, name in self.NAV:
            b = Gtk.Button(can_focus=False)
            b.set_name(icon)
            img = gtk.Image(icon, size, size)
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.CENTER)
            b.add(img)
            b.set_tooltip_text(name)
            b.get_style_context().add_class("ss-rail-btn")
            b.connect("clicked", self.go, page)
            b.connect("clicked", self.screen.remove_keyboard)
            slot(b, 48, 44)
            self.nav[page] = b
        self.stop = Gtk.Button(can_focus=False)
        stop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1,
                           halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        stop_img = gtk.Image("emergency", 20, 20)
        stop_img.set_halign(Gtk.Align.CENTER)
        stop_box.pack_start(stop_img, False, False, 0)
        stop_box.pack_start(label(_("STOP"), "ss-stop-text", xalign=0.5), False, False, 0)
        self.stop.add(stop_box)
        self.stop.get_style_context().add_class("ss-stop")
        self.stop.connect("clicked", lambda *a: ask_estop(self.screen))
        slot(self.stop, 52, 52)
        self.update_stop()
        self._contain_content(base)
        from ks_includes import starstack_devtools   # bench-only, inactive without ~/.starstack_dev
        starstack_devtools.start(self.screen)

    @staticmethod
    def _contain_content(base):
        """SAFETY: wrap the page area in a scroller so no page can make the window taller than
        the screen (which would push STOP off the bottom). A too-tall page scrolls instead."""
        grid = base.main_grid
        if base.content.get_parent() is not grid:
            return
        grid.remove(base.content)
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_height(False)
        scroller.get_style_context().add_class("ss-content-guard")
        scroller.add(base.content)
        grid.attach(scroller, 1, 1, 1, 1)

    def go(self, widget, page):
        if self.screen._cur_panels and self.screen._cur_panels[0] == page and len(self.screen._cur_panels) == 1:
            return
        self.screen.show_panel(page, remove_all=True)

    def on_panel(self, panel_name):
        root = self.screen._cur_panels[0] if self.screen._cur_panels else panel_name
        ready = self.screen.printer is not None and self.screen.printer.state not in (
            "disconnected", "startup", "shutdown", "error", None)
        for page, b in self.nav.items():
            set_class(b, "ss-rail-active", page == root)
            b.set_sensitive(ready)
        self.update_stop()

    def update_stop(self):
        p = self.screen.printer
        active = False
        if p is not None and p.state not in ("disconnected", "startup", "shutdown", "error", None):
            heaters = [h for h in p.get_temp_devices() if p.device_has_target(h)]
            hot = any((p.get_stat(h, "target") or 0) > 0 for h in heaters)
            busy = p.get_stat("idle_timeout", "state") == "Printing"
            active = is_printing(p) or hot or busy
        set_class(self.stop, "ss-stop-active", active)
        set_class(self.stop, "ss-stop-idle", not active)

    def process_update(self, action, data):
        if action == "notify_status_update":
            self.update_stop()
