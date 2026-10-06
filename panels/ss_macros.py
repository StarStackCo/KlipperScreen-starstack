# STARSTACK-ADDED: Macros page (FORK_CHANGES.md #42, klipper-ui D-067)
# Replaces the stock gcode_macros panel. All visible macros in pages with ‹ › arrows; a macro
# without parameters asks "Run X?", one with parameters (params.X in its G-code) opens a small
# form: Run / Cancel at the top so they stay reachable while the on-screen keyboard is open.
import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

PARAM = re.compile(r"params\.(?P<name>[A-Za-z0-9_]+)(?:\s*\|\s*default\((?P<default>[^)]*)\))?")


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
        self.stack.set_vhomogeneous(False)  # keyboard fits under the form
        page, self.pager = ss.list_page(_("Macros"))
        self.stack.add_named(page, "list")
        self.form = ss.page_box(spacing=6)
        self.stack.add_named(self.form, "form")
        self.content.add(self.stack)
        self.content.show_all()
        self.macro = None
        self.entries = {}
        self.build()

    def macro_info(self, name):
        section = self._printer.get_config_section(f"gcode_macro {name}") or {}
        params = {}
        for m in PARAM.finditer(section.get("gcode", "")):
            key = m.group("name").upper()
            default = (m.group("default") or "").strip().strip("'\"")
            params.setdefault(key, default)
        return section.get("description", ""), params

    def build(self):
        rows = []
        for name in sorted(self._printer.get_gcode_macros(), key=str.upper):
            desc, params = self.macro_info(name)
            note = desc if desc and desc != "G-Code macro" else ""
            if params and not note:
                note = _("settings") + " ›"
            rows.append((ss.row(name.upper(), note, lambda n=name: self.tapped(n)), "row"))
        if not rows:
            rows.append((ss.label(_("No macros found."), "ss-muted"), "text"))
        self.pager.set_rows(rows)

    def tapped(self, name):
        desc, params = self.macro_info(name)
        if not params:
            ss.confirm(
                self._screen,
                _("Run") + f" {name.upper()}?",
                desc if desc and desc != "G-Code macro" else _("Runs this macro on the printer."),
                _("Run"),
                lambda: ss.gcode(self._screen, name),
            )
            return
        self.open_form(name, params)

    # ---- parameter form
    def open_form(self, name, params):
        self.macro = name
        for c in self.form.get_children():
            self.form.remove(c)
        head = Gtk.Box(spacing=8)
        head.pack_start(ss.label(name.upper(), "ss-row-title", ellipsize=True), True, True, 0)
        for text, css, cb in (
            (_("Cancel"), "ss-btn ss-btn-outline ss-btn-mid", self.close_form),
            (_("Run"), "ss-btn ss-btn-primary ss-btn-mid", self.run),
        ):
            b = ss.button(text, css=css)
            b.set_hexpand(False)
            b.set_size_request(84, 44)
            b.connect("clicked", cb)
            head.pack_end(b, False, False, 0)
        self.form.pack_start(head, False, False, 0)
        self.entries = {}
        for key, default in params.items():
            row = Gtk.Box(spacing=8)
            lbl = ss.label(key, "ss-btn-sub", xalign=1.0)
            lbl.set_size_request(110, -1)
            row.pack_start(lbl, False, False, 0)
            entry = Gtk.Entry(hexpand=True)
            entry.set_placeholder_text(default or _("empty = macro default"))
            entry.get_style_context().add_class("ss-console-entry")
            entry.connect("button-press-event", self._screen.show_keyboard)
            entry.connect("touch-event", self._screen.show_keyboard)
            entry.connect("activate", self.run)
            row.pack_start(entry, True, True, 0)
            self.form.pack_start(row, False, False, 0)
            self.entries[key] = entry
        self.form.show_all()
        self.stack.set_visible_child_name("form")

    def run(self, *args):
        values = " ".join(
            f"{k}={e.get_text().strip()}" for k, e in self.entries.items() if e.get_text().strip()
        )
        script = f"{self.macro} {values}".strip()
        self.close_form()
        ss.gcode(self._screen, script)
        self._screen.show_popup_message(script, 1)

    def close_form(self, *args):
        self._screen.remove_keyboard()
        self.stack.set_visible_child_name("list")

    def back(self):
        if self.stack.get_visible_child_name() == "form":
            self.close_form()
            return True
        return False

    def activate(self):
        self.build()
