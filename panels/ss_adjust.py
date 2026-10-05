# STARSTACK-ADDED: value adjuster (FORK_CHANGES.md #26)
# nozzle / bed / fan / flow / pressure advance
# Opened with ks_includes.starstack.adjust(). Values are clamped to [ss_min, ss_max]
# here AND by Klipper / the StarStack macros on the printer.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(
        self,
        screen,
        title,
        ss_title="",
        ss_value=0,
        ss_min=0,
        ss_max=100,
        ss_unit="",
        ss_steps=(-10, -1, 1, 10),
        ss_presets=(),
        ss_decimals=0,
        ss_apply=None,
        **kwargs,
    ):
        super().__init__(screen, title)
        self.v, self.lo, self.hi = ss_value, ss_min, ss_max
        self.unit, self.dec, self.apply_cb = ss_unit, ss_decimals, ss_apply
        for child in self.content.get_children():
            self.content.remove(child)
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER, vexpand=True
        )
        card.get_style_context().add_class("ss-dialog")
        head = Gtk.Box(spacing=8)
        head.add(ss.label(ss_title, "ss-dialog-title"))
        head.add(ss.label(_("Limit") + f" {self.fmt(ss_min)}–{self.fmt(ss_max)}", "ss-muted"))
        card.add(head)
        self.value_lbl = ss.label(self.fmt(self.v), "ss-big-value", xalign=0.5)
        card.add(self.value_lbl)

        steps = ss.grid(len(ss_steps))
        ss.grid_add(steps, [self._step_btn(d) for d in ss_steps])
        card.add(steps)
        if ss_presets:
            presets = ss.grid(len(ss_presets))
            btns = []
            for name, val in ss_presets:
                b = ss.button(name, css="ss-btn ss-btn-outline ss-btn-sm")
                b.connect("clicked", self.set_value, val)
                btns.append(b)
            ss.grid_add(presets, btns)
            card.add(presets)
        actions = ss.grid(2, spacing=8)
        cancel = ss.button(_("Cancel"), css="ss-btn ss-btn-outline")
        cancel.connect("clicked", lambda *a: ss.close_dialog(self._screen))
        ok = ss.button(_("Set"), css="ss-btn ss-btn-primary")
        ok.connect("clicked", self.apply)
        ss.grid_add(actions, [cancel, ok])
        card.add(actions)
        page = ss.page_box()
        page.add(card)
        self.content.add(page)
        self.content.show_all()

    def fmt(self, v):
        return (f"{v:.{self.dec}f}" if self.dec else f"{int(round(v))}") + self.unit

    def _step_btn(self, d):
        txt = ("+" if d > 0 else "−") + (f"{abs(d):g}")
        b = ss.button(txt, css="ss-btn ss-btn-step")
        b.connect("clicked", self.step, d)
        return b

    def set_value(self, widget, v):
        self.v = min(self.hi, max(self.lo, round(v, 4)))
        self.value_lbl.set_text(self.fmt(self.v))

    def step(self, widget, d):
        self.set_value(widget, self.v + d)

    def apply(self, *args):
        cb, v = self.apply_cb, self.v
        ss.close_dialog(self._screen)
        if cb:
            cb(v)
