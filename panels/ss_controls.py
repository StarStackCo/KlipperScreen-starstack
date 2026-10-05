# STARSTACK-ADDED: Controls page: temperatures, fan, filament, movement (FORK_CHANGES.md #24)
# Filament and movement are locked while printing (requirements v2.1 §6).
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

JOG = [
    ("X −", "G91\nG1 X-10 F3000\nG90"),
    ("Y −", "G91\nG1 Y-10 F3000\nG90"),
    ("Z −", "G91\nG1 Z-10 F600\nG90"),
    ("Home all", "G28"),
    ("X +", "G91\nG1 X10 F3000\nG90"),
    ("Y +", "G91\nG1 Y10 F3000\nG90"),
    ("Z +", "G91\nG1 Z10 F600\nG90"),
    ("Motors off", "M84"),
]


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page = ss.page_box(spacing=6)
        temps = ss.grid(3, spacing=8)
        self.t_noz = ss.button(_("Nozzle"), "–", css="ss-btn ss-btn-card ss-btn-temp")
        self.t_bed = ss.button(_("Bed"), "–", css="ss-btn ss-btn-card ss-btn-temp")
        self.t_fan = ss.button(_("Part fan"), "–", css="ss-btn ss-btn-card ss-btn-temp")
        self.t_noz.connect("clicked", self.edit_heater, "extruder")
        self.t_bed.connect("clicked", self.edit_heater, "heater_bed")
        self.t_fan.connect("clicked", self.edit_fan)
        ss.grid_add(temps, [self.t_noz, self.t_bed, self.t_fan])
        page.add(temps)

        fil_head = Gtk.Box(spacing=6)
        fil_head.add(ss.section(_("Filament")))
        self.loaded_lbl = ss.label("", "ss-section ss-text-sky")
        fil_head.add(self.loaded_lbl)
        self.lock1 = ss.label("· " + _("locked while printing"), "ss-section ss-text-warning")
        fil_head.add(self.lock1)
        page.add(fil_head)
        fil = ss.grid(2, spacing=8)
        self.load_btn = ss.button(_("Load filament"), css="ss-btn ss-btn-card ss-btn-mid")
        self.unload_btn = ss.button(_("Unload filament"), css="ss-btn ss-btn-card ss-btn-mid")
        self.load_btn.connect(
            "clicked", lambda w: ss._push(self._screen, "ss_filament", ss_mode="load")
        )
        self.unload_btn.connect(
            "clicked",
            lambda w: ss._push(
                self._screen, "ss_filament", ss_mode="unload", ss_material=self.loaded
            ),
        )
        ss.grid_add(fil, [self.load_btn, self.unload_btn])
        page.add(fil)

        mv_head = Gtk.Box(spacing=6)
        mv_head.add(ss.section(_("Move") + " · 10 mm"))
        self.lock2 = ss.label("· " + _("locked while printing"), "ss-section ss-text-warning")
        mv_head.add(self.lock2)
        page.add(mv_head)
        mv = ss.grid(4, spacing=6)
        self.jog_btns = []
        for name, script in JOG:
            b = ss.button(_(name), css="ss-btn ss-btn-card ss-btn-jog")
            b.connect("clicked", lambda w, s=script: ss.gcode(self._screen, s, w))
            self.jog_btns.append(b)
        ss.grid_add(mv, self.jog_btns)
        page.add(mv)
        self.loaded = None
        self.content.add(page)
        self.content.show_all()

    def edit_heater(self, widget, dev):
        p = self._printer
        nozzle = dev == "extruder"
        cfg = p.get_config_section(dev) or {}
        mx = float(cfg.get("max_temp", 300 if nozzle else 110))
        idx = 0 if nozzle else 1
        cmd = "M104 S{}" if nozzle else "M140 S{}"
        ss.adjust(
            self._screen,
            ss_title=_("Nozzle target") if nozzle else _("Bed target"),
            ss_value=p.get_stat(dev, "target") or 0,
            ss_min=0,
            ss_max=mx,
            ss_unit="°C",
            ss_presets=[(_("Off"), 0)] + [(m, t[idx]) for m, t in ss.MATERIALS.items()],
            ss_apply=lambda v: ss.gcode(self._screen, cmd.format(int(v))),
        )

    def edit_fan(self, widget):
        fan = round((self._printer.get_stat("fan", "speed") or 0) * 100)
        ss.adjust(
            self._screen,
            ss_title=_("Part fan"),
            ss_value=fan,
            ss_min=0,
            ss_max=100,
            ss_unit="%",
            ss_presets=[(_("Off"), 0), ("50%", 50), ("80%", 80), ("100%", 100)],
            ss_apply=lambda v: ss.gcode(self._screen, f"M106 S{int(round(v * 2.55))}"),
        )

    def refresh(self):
        p = self._printer
        locked = ss.is_printing(p)
        for b in [self.load_btn, self.unload_btn] + self.jog_btns:
            b.set_sensitive(not locked)
            ss.set_class(b, "ss-btn-locked", locked)
        self.lock1.set_visible(locked)
        self.lock2.set_visible(locked)
        e_t, e_g = p.get_stat("extruder", "temperature") or 0, p.get_stat("extruder", "target") or 0
        b_t, b_g = (
            p.get_stat("heater_bed", "temperature") or 0,
            p.get_stat("heater_bed", "target") or 0,
        )
        ss.set_button_text(
            self.t_noz, None, f"{e_t:.0f}°  " + (f"→ {e_g:.0f}°" if e_g else _("off"))
        )
        ss.set_button_text(
            self.t_bed, None, f"{b_t:.0f}°  " + (f"→ {b_g:.0f}°" if b_g else _("off"))
        )
        ss.set_button_text(self.t_fan, None, f"{(p.get_stat('fan', 'speed') or 0) * 100:.0f}%")
        ss.set_class(self.t_noz, "ss-hot", e_g > 0)
        ss.set_class(self.t_bed, "ss-hot", b_g > 0)

    def activate(self):
        ss.query_loaded_material(self._screen, self._show_loaded)
        self.refresh()

    def _show_loaded(self, material):
        self.loaded = material
        self.loaded_lbl.set_text(
            "· " + (f"{material} " + _("loaded") if material else _("none loaded"))
        )
        ss.set_button_text(
            self.unload_btn, _("Unload") + f" {material}" if material else _("Unload filament")
        )

    def process_update(self, action, data):
        if action == "notify_status_update":
            self.refresh()
