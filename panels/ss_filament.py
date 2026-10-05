# STARSTACK-ADDED: guided filament load / unload (FORK_CHANGES.md #16, D-030)
# Uses the StarStack macros (klipper-ui macros/starstack_macros.cfg), which never block:
#   LOAD_FILAMENT / UNLOAD_FILAMENT MATERIAL=X  → heats if cold, moves filament when hot
#   PURGE_MORE, FILAMENT_DONE (heater off unless a print is paused)
# The remembered material (save_variables) lets Unload start straight away.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel
from ks_includes import starstack as ss


class Panel(ScreenPanel):
    def __init__(self, screen, title, ss_mode="load", ss_material=None, **kwargs):
        super().__init__(screen, title)
        self.change = ss_mode == "change"          # color change: unload, then load the same material
        if self.change:
            ss_material = ss_material or ss.loaded_material(screen)
            ss_mode = "unload"
        self.mode = ss_mode
        self.mat = ss_material if ss_mode == "unload" else None
        self.loaded = ss.loaded_material(screen) if ss_mode == "load" else None
        self.step = "pick" if not self.mat else "heat"
        self.sent_move = False
        page = ss.page_box(spacing=10)
        head = Gtk.Box(spacing=8)
        self.title_lbl = ss.label("", "ss-page-title")
        head.pack_start(self.title_lbl, True, True, 0)
        self.dots = Gtk.Box(spacing=5, valign=Gtk.Align.CENTER)
        head.pack_end(self.dots, False, False, 0)
        page.add(head)
        self.body = ss.label("", "ss-dialog-body", wrap=True)
        page.add(self.body)
        self.mats = ss.grid(3, spacing=8)
        btns = []
        for name, (noz, _bed) in ss.MATERIALS.items():
            b = ss.button(name, f"{noz}°C " + _("nozzle"), css="ss-btn ss-btn-card ss-btn-mat")
            b.connect("clicked", self.pick, name)
            btns.append(b)
        ss.grid_add(self.mats, btns)
        page.add(self.mats)
        self.bar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row = Gtk.Box()
        row.pack_start(ss.label(_("Nozzle"), "ss-muted"), True, True, 0)
        self.temp_lbl = ss.label("", "ss-text-hot ss-row-title", xalign=1.0)
        row.pack_end(self.temp_lbl, False, False, 0)
        self.bar = Gtk.ProgressBar()
        self.bar.get_style_context().add_class("ss-progress")
        self.bar.get_style_context().add_class("ss-progress-paused")
        self.bar_box.add(row)
        self.bar_box.add(self.bar)
        page.add(self.bar_box)
        page.pack_start(Gtk.Box(vexpand=True), True, True, 0)
        actions = Gtk.Box(spacing=8, homogeneous=True)
        self.back_btn = ss.button(_("Cancel"), css="ss-btn ss-btn-outline ss-btn-action")
        self.back_btn.connect("clicked", self.cancel)
        self.alt_btn = ss.button("", css="ss-btn ss-btn-outline-accent ss-btn-action")
        self.alt_btn.connect("clicked", self.alt)
        self.next_btn = ss.button("", css="ss-btn ss-btn-primary ss-btn-action")
        self.next_btn.connect("clicked", self.next)
        for b in (self.back_btn, self.alt_btn, self.next_btn):
            actions.add(b)
        page.add(actions)
        self.content.add(page)
        self.content.show_all()
        for w in (self.mats, self.bar_box, self.alt_btn, self.next_btn):
            w.set_no_show_all(True)   # visibility is controlled by render(), not by show_all()
        if self.step == "heat":
            self.start_heat()
        self.render()

    # ---- actions
    def macro(self):
        return "LOAD_FILAMENT" if self.mode == "load" else "UNLOAD_FILAMENT"

    def pick(self, widget, name):
        self.mat = name
        self.start_heat()

    def start_heat(self):
        self.step = "heat"
        self.sent_move = False
        ss.gcode(self._screen, f"{self.macro()} MATERIAL={self.mat}")   # cold → starts heating only
        self.render()

    def target(self):
        return ss.MATERIALS[self.mat][0] if self.mat else 0

    def hot(self):
        return (self._printer.get_stat("extruder", "temperature") or 0) >= self.target() - 5

    def next(self, widget):
        if self.step == "ready":                 # load: filament inserted
            ss.gcode(self._screen, f"LOAD_FILAMENT MATERIAL={self.mat}")
            self.step = "purge"
        elif self.step == "unloaded" and self.change:   # old filament out → load the new color
            self.mode, self.step = "load", "ready"
        elif self.step in ("purge", "unloaded"):
            ss.gcode(self._screen, "FILAMENT_DONE")
            ss.close_dialog(self._screen)
            return
        self.render()

    def alt(self, widget):
        if self.step == "pick" and self.mode == "load" and self.loaded:
            self.mode, self.mat = "unload", self.loaded
            self.start_heat()
        elif self.step == "purge":
            ss.gcode(self._screen, "PURGE_MORE", widget)

    def cancel(self, widget):
        if self.step != "pick":
            ss.gcode(self._screen, "FILAMENT_DONE")
        ss.close_dialog(self._screen)

    # ---- view
    def render(self):
        load = self.mode == "load"
        self.title_lbl.set_text(_("Change filament") if self.change else
                                (_("Load filament") if load else _("Unload filament")))
        steps = ["pick", "heat", "ready", "purge"] if load else ["pick", "heat", "unloaded"]
        cur = steps.index(self.step) if self.step in steps else 0
        for c in self.dots.get_children():
            self.dots.remove(c)
        for i in range(len(steps)):
            d = Gtk.Box()
            d.set_size_request(8, 8)
            d.get_style_context().add_class("ss-dot-on" if i <= cur else "ss-dot")
            self.dots.add(d)
        self.dots.show_all()
        alt, nxt = None, None
        if self.step == "pick":
            txt = _("Which material are you loading?") if load else \
                _("No filament is recorded as loaded.") + "\n" + _("Which material is in the printer?")
            if load and self.loaded:
                txt += "\n" + f"{self.loaded} " + _("is loaded now. Unload it first.")
                alt = _("Unload") + f" {self.loaded} " + _("first")
        elif self.step == "heat":
            txt = (_("Loading") if load else _("Unloading")) + f" {self.mat}.\n" + \
                _("Heating the nozzle first. This takes about a minute.")
        elif self.step == "ready":
            txt = _("Nozzle is hot.") + "\n" + _("Push the filament into the extruder until you feel it grip, then tap Load.")
            nxt = _("Load")
        elif self.step == "purge":
            txt = _("Filament is purging.") + "\n" + _("Is the plastic coming out clean and the right color?")
            alt, nxt = _("Purge more"), _("Done")
        else:  # unloaded
            if self.change:
                txt = _("Unloading…") + "\n" + _("Pull the old filament out gently, then tap Next.")
                nxt = _("Next")
            else:
                txt = _("Unloading…") + "\n" + _("When the filament is free, pull it out gently and tap Done.")
                nxt = _("Done")
        self.body.set_text(txt)
        self.mats.set_visible(self.step == "pick")
        self.bar_box.set_visible(self.step == "heat")
        self.alt_btn.set_visible(alt is not None)
        self.next_btn.set_visible(nxt is not None)
        if alt:
            ss.set_button_text(self.alt_btn, alt)
        if nxt:
            ss.set_button_text(self.next_btn, nxt)
        self.update_temp()

    def update_temp(self):
        if self.step != "heat" or not self.mat:
            return
        t = self._printer.get_stat("extruder", "temperature") or 0
        tgt = self.target()
        self.temp_lbl.set_text(f"{t:.0f}° / {tgt}°")
        self.bar.set_fraction(max(0.0, min(1.0, t / tgt)) if tgt else 0)
        if self.hot() and not self.sent_move:
            self.sent_move = True
            if self.mode == "load":
                self.step = "ready"
            else:
                ss.gcode(self._screen, f"UNLOAD_FILAMENT MATERIAL={self.mat}")
                self.step = "unloaded"
            self.render()

    def process_update(self, action, data):
        if action == "notify_status_update" and "extruder" in data:
            self.update_temp()

    def activate(self):
        self.render()      # KlipperScreen re-shows the whole page after attaching; re-apply visibility

    def back(self):
        self.cancel(None)
        return True
