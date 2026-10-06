# STARSTACK-ADDED: Fans page (FORK_CHANGES.md #44, klipper-ui D-067)
# Replaces the stock fan panel (Advanced › tools). Every fan with its speed, in pages with ‹ ›;
# the part fan and generic fans can be set, hotend/controller fans are automatic (read-only).
from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


def fan_name(fan):
    """'fan' -> Part fan, 'heater_fan hotend_fan' -> Hotend fan (Klipper's own name, tidied)."""
    if fan == "fan":
        return _("Part fan")
    name = fan.partition(" ")[2].replace("_", " ").strip()
    return name.capitalize() or fan


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page, self.pager = ss.list_page(_("Fans"))
        self.content.add(page)
        self.content.show_all()
        self.shown = None
        self.build()

    def speeds(self):
        return {
            f: round((self._printer.get_stat(f, "speed") or 0) * 100)
            for f in self._printer.get_fans()
        }

    def build(self):
        speeds = self.speeds()
        if speeds == self.shown:
            return
        self.shown = speeds
        rows = []
        for fan, pct in speeds.items():
            settable = fan == "fan" or fan.startswith("fan_generic ")
            note = f"{pct}%" + ("" if settable else " · " + _("automatic"))
            cb = (lambda f=fan: self.adjust(f)) if settable else None
            css = "ss-text-sky" if pct else "ss-muted"
            rows.append((ss.row(fan_name(fan), note, cb, css_note=css), "row"))
        if not rows:
            rows.append((ss.label(_("No fans configured."), "ss-muted"), "text"))
        self.pager.set_rows(rows)

    def adjust(self, fan):
        if fan == "fan":
            apply = lambda v: ss.gcode(self._screen, f"M106 S{int(round(v * 2.55))}")  # noqa: E731
        else:
            name = fan.split(" ", 1)[1]
            apply = lambda v: ss.gcode(  # noqa: E731
                self._screen, f"SET_FAN_SPEED FAN={name} SPEED={v / 100:.2f}"
            )
        ss.adjust(
            self._screen,
            ss_title=fan_name(fan),
            ss_value=round((self._printer.get_stat(fan, "speed") or 0) * 100),
            ss_min=0,
            ss_max=100,
            ss_unit="%",
            ss_presets=[(_("Off"), 0), ("50%", 50), ("80%", 80), ("100%", 100)],
            ss_apply=apply,
        )

    def process_update(self, action, data):
        if action == "notify_status_update" and any(f in data for f in self._printer.get_fans()):
            ss.debounce(self, "_fan_timer", 500, self.build)

    def activate(self):
        self.shown = None
        self.build()
