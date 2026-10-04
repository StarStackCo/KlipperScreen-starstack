# STARSTACK-ADDED: Cancel object: bed map with positions + part list (FORK_CHANGES.md #15, D-022)
# Tap a part on the map or in the list, then confirm. Needs [exclude_object] + Orca "Label objects".
# Like stock exclude.py: excluding the LAST remaining part cancels the print instead (Klipper quirk).
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk
from ks_includes.screen_panel import ScreenPanel
from ks_includes import starstack as ss

COL = {"normal": (0.0, 0.67, 0.78), "selected": (1.0, 0.39, 0.40), "gone": (0.25, 0.25, 0.25)}


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.selected = None
        p = self._printer
        sx = p.get_config_section("stepper_x") or {}
        sy = p.get_config_section("stepper_y") or {}
        self.bed = (float(sx.get("position_min", 0)), float(sy.get("position_min", 0)),
                    float(sx.get("position_max", 180)), float(sy.get("position_max", 180)))
        root = Gtk.Box(spacing=12)
        root.get_style_context().add_class("ss-page")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left.add(ss.section(_("Bed") + f" · {self.bed[2] - self.bed[0]:.0f} × {self.bed[3] - self.bed[1]:.0f} mm"))
        self.map = Gtk.DrawingArea()
        self.map.set_size_request(196, 196)
        self.map.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.TOUCH_MASK)
        self.map.connect("draw", self.draw)
        self.map.connect("button-press-event", self.tap)
        left.add(self.map)
        root.pack_start(left, False, False, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, hexpand=True)
        right.add(ss.label(_("Cancel an object"), "ss-page-title"))
        right.add(ss.label(_("Tap a part. The rest keep printing."), "ss-btn-sub", wrap=True))
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.list)
        scroll.set_vexpand(True)
        right.pack_start(scroll, True, True, 0)
        row = ss.grid(2)
        back = ss.button(_("Back"), css="ss-btn ss-btn-outline ss-btn-mid")
        back.connect("clicked", lambda w: ss.close_dialog(self._screen))
        self.cancel_btn = ss.button(_("Cancel part"), css="ss-btn ss-btn-danger ss-btn-mid")
        self.cancel_btn.connect("clicked", self.ask)
        ss.grid_add(row, [back, self.cancel_btn])
        right.add(row)
        root.pack_start(right, True, True, 0)
        self.content.add(root)
        self.refresh()
        self.content.show_all()

    def objects(self):
        return self._printer.get_stat("exclude_object", "objects") or []

    def excluded(self):
        return self._printer.get_stat("exclude_object", "excluded_objects") or []

    def refresh(self):
        for c in self.list.get_children():
            self.list.remove(c)
        gone = self.excluded()
        for i, obj in enumerate(self.objects()):
            name = obj["name"]
            b = Gtk.Button(can_focus=False, hexpand=True)
            box = Gtk.Box(spacing=6)
            badge = ss.label(str(i + 1), "ss-badge", xalign=0.5)
            box.pack_start(badge, False, False, 0)
            box.pack_start(ss.label(ss.pretty_object(name, i), "ss-row-title", ellipsize=True), True, True, 0)
            state = _("canceled") if name in gone else (_("selected") if name == self.selected else "")
            box.pack_end(ss.label(state, "ss-btn-sub"), False, False, 0)
            b.add(box)
            for c in ("ss-btn", "ss-row", "ss-row-obj"):
                b.get_style_context().add_class(c)
            ss.set_class(b, "ss-row-selected", name == self.selected)
            ss.set_class(badge, "ss-badge-selected", name == self.selected)
            ss.set_class(badge, "ss-badge-gone", name in gone)
            b.set_sensitive(name not in gone)
            b.connect("clicked", self.select, name)
            self.list.add(b)
        self.cancel_btn.set_sensitive(self.selected is not None and self.selected not in gone)
        self.list.show_all()
        self.map.queue_draw()

    def select(self, widget, name):
        self.selected = name
        self.refresh()

    # ---- map
    def to_px(self, w, h, x, y):
        x0, y0, x1, y1 = self.bed
        return (x - x0) / (x1 - x0) * w, h - (y - y0) / (y1 - y0) * h

    def draw(self, da, ctx):
        w, h = da.get_allocated_width(), da.get_allocated_height()
        ctx.set_source_rgb(0.094, 0.094, 0.094)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()
        ctx.set_source_rgb(0.157, 0.157, 0.157)
        ctx.set_line_width(1)
        ctx.rectangle(0.5, 0.5, w - 1, h - 1)
        ctx.stroke()
        gone = self.excluded()
        for i, obj in enumerate(self.objects()):
            poly = obj.get("polygon")
            if not poly:
                continue
            key = "gone" if obj["name"] in gone else ("selected" if obj["name"] == self.selected else "normal")
            r, g, b = COL[key]
            pts = [self.to_px(w, h, x, y) for x, y in poly]
            ctx.move_to(*pts[0])
            for pt in pts[1:]:
                ctx.line_to(*pt)
            ctx.close_path()
            ctx.set_source_rgba(r, g, b, 0.25)
            ctx.fill_preserve()
            ctx.set_source_rgb(r, g, b)
            ctx.set_line_width(2)
            ctx.stroke()
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            ctx.set_source_rgb(0.98, 0.98, 0.98)
            ctx.set_font_size(13)
            ctx.move_to(cx - 4, cy + 5)
            ctx.show_text(str(i + 1))

    def tap(self, da, ev):
        w, h = da.get_allocated_width(), da.get_allocated_height()
        gone = self.excluded()
        for obj in self.objects():
            poly = obj.get("polygon")
            if not poly or obj["name"] in gone:
                continue
            pts = [self.to_px(w, h, x, y) for x, y in poly]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            if min(xs) - 6 <= ev.x <= max(xs) + 6 and min(ys) - 6 <= ev.y <= max(ys) + 6:
                self.select(None, obj["name"])
                return

    def ask(self, *args):
        name = self.selected
        remaining = [o["name"] for o in self.objects() if o["name"] not in self.excluded()]
        if remaining == [name]:
            ss.confirm(self._screen, _("Cancel the whole print?"),
                       _("This is the last part still printing, so the print will be canceled."),
                       _("Cancel print"), self._screen._ws.klippy.print_cancel, kind="danger")
            return
        idx = [o["name"] for o in self.objects()].index(name)
        ss.confirm(self._screen, _("Cancel") + f" {ss.pretty_object(name, idx)}?",
                   _("This part stops printing. The other parts carry on. This can't be undone."),
                   _("Cancel part"), lambda: ss.gcode(self._screen, f"EXCLUDE_OBJECT NAME={name}"), kind="danger")

    def activate(self):
        self.refresh()

    def process_update(self, action, data):
        if action == "notify_status_update" and "exclude_object" in data:
            if self.selected in self.excluded():
                self.selected = None
            self.refresh()
        if action == "notify_status_update" and not ss.is_printing(self._printer):
            ss.close_dialog(self._screen)
