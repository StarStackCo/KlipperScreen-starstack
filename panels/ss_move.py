# STARSTACK-ADDED: Move axes page (FORK_CHANGES.md #45, klipper-ui D-067)
# Finer jogging than Controls (which moves 10 mm): live position, step chips 0.1/1/10/50 mm,
# X/Y/Z ± (an axis can't move until it's homed, like Klipper itself), Home all, Motors off.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

STEPS = (0.1, 1, 10, 50)


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.step = float(ss.get_setting("move_step", 10))
        page = ss.page_box(spacing=6)
        head = Gtk.Box(spacing=8)
        head.pack_start(ss.label(_("Move axes"), "ss-page-title"), False, False, 0)
        self.pos = ss.label("", "ss-muted", xalign=1.0)
        head.pack_start(self.pos, True, True, 0)
        page.pack_start(head, False, False, 0)

        row = ss.grid(len(STEPS), spacing=8)
        self.step_btns = {}
        for s in STEPS:
            b = ss.button(f"{s:g}", "mm", css="ss-btn ss-btn-card")
            b.connect("clicked", lambda w, s=s: self.pick_step(s))
            self.step_btns[s] = b
        ss.grid_add(row, list(self.step_btns.values()))
        page.pack_start(row, False, False, 0)

        jog = ss.grid(4, spacing=8)
        self.axis_btns = []
        for axis in "XYZ":
            for d in (-1, 1):
                b = ss.button(
                    f"{axis} {'−' if d < 0 else '+'}", css="ss-btn ss-btn-card ss-btn-tall"
                )
                b.connect("clicked", self.jog, axis, d)
                self.axis_btns.append((axis, b))
        home = ss.button(_("Home all"), css="ss-btn ss-btn-card ss-btn-tall")
        home.connect("clicked", lambda w: ss.gcode(self._screen, "G28", w))
        off = ss.button(_("Motors off"), css="ss-btn ss-btn-outline ss-btn-tall")
        off.connect("clicked", self.motors_off)
        ss.grid_add(jog, [b for _a, b in self.axis_btns] + [home, off])
        page.pack_start(jog, False, False, 0)
        self.content.add(page)
        self.content.show_all()
        self.refresh()

    def speed(self, axis):
        cfg = self._config.get_main_config()
        if axis == "Z":
            return float(cfg.get("move_speed_z", 10)) * 60
        return float(cfg.get("move_speed_xy", 50)) * 60

    def refresh(self):
        homed = (self._printer.get_stat("toolhead", "homed_axes") or "").upper()
        pos = self._printer.get_stat("gcode_move", "gcode_position") or [0, 0, 0]
        parts = [f"{a} {pos[i]:.1f}" if a in homed else f"{a} –" for i, a in enumerate("XYZ")]
        self.pos.set_text("  ".join(parts) + ("" if homed else "  · " + _("not homed")))
        for axis, b in self.axis_btns:
            b.set_sensitive(axis in homed)
        for s, b in self.step_btns.items():
            ss.set_class(b, "ss-chip-active", s == self.step)

    def pick_step(self, s):
        self.step = s
        ss.set_setting("move_step", s)
        self.refresh()

    def jog(self, widget, axis, d):
        dist = self.step * d
        ss.gcode(self._screen, f"G91\nG1 {axis}{dist:g} F{self.speed(axis):.0f}\nG90", widget)

    def motors_off(self, widget):
        if ss.is_printing(self._printer):
            return
        ss.confirm(
            self._screen,
            _("Turn the motors off?"),
            _("The axes can then be moved by hand. Home again before printing."),
            _("Motors off"),
            lambda: ss.gcode(self._screen, "M84"),
        )

    def process_update(self, action, data):
        if action == "notify_status_update" and ("toolhead" in data or "gcode_move" in data):
            ss.debounce(self, "_pos_timer", 200, self.refresh)

    def activate(self):
        self.refresh()
