# STARSTACK-ADDED: Input shaper page (FORK_CHANGES.md #47, klipper-ui D-067)
# Replaces the stock input_shaper panel (Advanced › tools). Shows the shaper in use per axis.
# With an accelerometer ([resonance_tester]): Measure X & Y (SHAPER_CALIBRATE) and Save
# (SAVE_CONFIG); Klipper's recommendations are picked out of its console replies.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.results = []
        page = ss.page_box(spacing=8)
        page.pack_start(ss.label(_("Input shaper"), "ss-page-title"), False, False, 0)
        self.current = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        page.pack_start(self.current, False, False, 0)
        self.info = ss.label("", "ss-muted", wrap=True)
        page.pack_start(self.info, False, False, 0)
        page.pack_start(Gtk.Box(vexpand=True), True, True, 0)
        row = ss.grid(2, spacing=8)
        self.measure = ss.button(_("Measure X & Y"), css="ss-btn ss-btn-primary ss-btn-mid")
        self.measure.connect("clicked", self.ask_measure)
        self.save = ss.button(_("Save to config"), css="ss-btn ss-btn-outline ss-btn-mid")
        self.save.connect("clicked", self.ask_save)
        ss.grid_add(row, [self.measure, self.save])
        page.pack_start(row, False, False, 0)
        self.content.add(page)
        self.content.show_all()
        self.refresh()

    def has_accel(self):
        return bool(self._printer.get_config_section("resonance_tester"))

    def refresh(self):
        for c in self.current.get_children():
            self.current.remove(c)
        cfg = self._printer.get_config_section("input_shaper") or {}
        for axis in "xy":
            kind = cfg.get(f"shaper_type_{axis}", cfg.get("shaper_type", "")) if cfg else ""
            freq = cfg.get(f"shaper_freq_{axis}", "") if cfg else ""
            value = f"{kind} · {float(freq):.1f} Hz" if kind and freq else _("off")
            self.current.add(ss.row(axis.upper() + " " + _("axis"), value, css_note="ss-row-title"))
        busy = ss.is_printing(self._printer)
        accel = self.has_accel()
        self.measure.set_sensitive(accel and not busy)
        self.save.set_sensitive(accel and not busy and bool(self.results))
        if self.results:
            self.info.set_text("\n".join(self.results))
        elif accel:
            self.info.set_text(
                _("Measuring shakes the printer for a few minutes.")
                + " "
                + _("Keep hands off and the bed empty.")
            )
        else:
            self.info.set_text(
                _("Measuring needs an accelerometer (e.g. ADXL345)")
                + " "
                + _("and [resonance_tester] in the printer config.")
            )
        self.current.show_all()

    def ask_measure(self, *args):
        homed = (self._printer.get_stat("toolhead", "homed_axes") or "").lower()
        script = ("" if all(a in homed for a in "xyz") else "G28\n") + "SHAPER_CALIBRATE"
        self.results = []
        ss.confirm(
            self._screen,
            _("Measure input shaper?"),
            _("The printer homes if needed, then vibrates each axis. Takes a few minutes."),
            _("Measure"),
            lambda: ss.gcode(self._screen, script),
        )

    def ask_save(self, *args):
        ss.confirm(
            self._screen,
            _("Save the shaper settings?"),
            _("Klipper writes printer.cfg and restarts. Takes about 10 seconds."),
            _("Save"),
            lambda: ss.gcode(self._screen, "SAVE_CONFIG"),
            kind="warning",
        )

    def process_update(self, action, data):
        if action == "notify_gcode_response" and "Recommended shaper" in data:
            self.results.append(data.replace("//", "").strip())
            self.refresh()

    def activate(self):
        self.refresh()
