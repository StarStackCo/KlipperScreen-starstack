# STARSTACK-ADDED: Extrude / retract page (FORK_CHANGES.md #42, klipper-ui D-067)
# Replaces the stock extrude panel (Advanced). One screen, nothing at the bottom edge:
# nozzle temperature (tap to set), amount and speed chips, Retract / Extrude.
# Blocked below Klipper's min_extrude_temp, like the stock panel and Klipper itself.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

AMOUNTS = (5, 10, 25, 50)  # mm
SPEEDS = (1, 2, 5, 10)  # mm/s


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.amount = int(ss.get_setting("extrude_amount", 10))
        self.speed = int(ss.get_setting("extrude_speed", 2))
        page = ss.page_box(spacing=6)  # must fit 278 px: no section labels, units on the chips
        head = Gtk.Box(spacing=8)
        head.pack_start(ss.label(_("Extrude / retract"), "ss-page-title"), True, True, 0)
        page.pack_start(head, False, False, 0)

        self.temp_btn = ss.button("", css="ss-btn ss-btn-mid", vertical=False)
        self.temp_btn.connect("clicked", self.set_temp)
        page.pack_start(self.temp_btn, False, False, 0)

        self.amount_btns = self.chips(page, AMOUNTS, "mm", self.pick_amount)
        self.speed_btns = self.chips(page, SPEEDS, "mm/s", self.pick_speed)

        page.pack_start(Gtk.Box(vexpand=True), True, True, 0)
        row = ss.grid(2, spacing=8)
        self.retract = ss.button(_("Retract"), css="ss-btn ss-btn-outline ss-btn-action")
        self.retract.connect("clicked", self.move, -1)
        self.extrude = ss.button(_("Extrude"), css="ss-btn ss-btn-primary ss-btn-action")
        self.extrude.connect("clicked", self.move, 1)
        ss.grid_add(row, [self.retract, self.extrude])
        page.pack_start(row, False, False, 0)
        self.content.add(page)
        self.content.show_all()
        self.refresh()

    def chips(self, page, values, unit, cb):
        row = ss.grid(len(values), spacing=8)
        btns = {}
        for v in values:
            b = ss.button(f"{v}", unit, css="ss-btn ss-btn-card")
            b.connect("clicked", lambda w, v=v: cb(v))
            btns[v] = b
        ss.grid_add(row, list(btns.values()))
        page.pack_start(row, False, False, 0)
        return btns

    def min_temp(self):
        cfg = self._printer.get_config_section("extruder") or {}
        return float(cfg.get("min_extrude_temp", 170))

    def refresh(self):
        t = self._printer.get_stat("extruder", "temperature") or 0
        tgt = self._printer.get_stat("extruder", "target") or 0
        hot = t >= self.min_temp()
        text = _("Nozzle") + f" {t:.0f}°" + (f" → {tgt:.0f}°" if tgt else "")
        sub = _("tap to set") if hot else _("too cold to extrude, tap to heat")
        ss.set_button_text(self.temp_btn, text, sub)
        ss.set_class(self.temp_btn, "ss-hot", not hot)
        for b in (self.retract, self.extrude):
            b.set_sensitive(hot)
        for v, b in self.amount_btns.items():
            ss.set_class(b, "ss-chip-active", v == self.amount)
        for v, b in self.speed_btns.items():
            ss.set_class(b, "ss-chip-active", v == self.speed)

    def pick_amount(self, v):
        self.amount = v
        ss.set_setting("extrude_amount", v)
        self.refresh()

    def pick_speed(self, v):
        self.speed = v
        ss.set_setting("extrude_speed", v)
        self.refresh()

    def move(self, widget, direction):
        e = self.amount * direction
        ss.gcode(self._screen, f"M83\nG1 E{e} F{self.speed * 60}", widget)

    def set_temp(self, *args):
        cfg = self._printer.get_config_section("extruder") or {}
        presets = [(_("Off"), 0)] + [(m, t[0]) for m, t in ss.MATERIALS.items()]
        ss.adjust(
            self._screen,
            ss_title=_("Nozzle target"),
            ss_value=self._printer.get_stat("extruder", "target") or 0,
            ss_min=0,
            ss_max=float(cfg.get("max_temp", 300)),
            ss_unit="°C",
            ss_presets=presets,
            ss_apply=lambda v: ss.gcode(self._screen, f"M104 S{int(v)}"),
        )

    def process_update(self, action, data):
        if action == "notify_status_update" and "extruder" in data:
            self.refresh()

    def activate(self):
        self.refresh()
