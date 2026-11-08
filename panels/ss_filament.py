# STARSTACK-ADDED: guided filament load / unload (FORK_CHANGES.md #28, D-030)
# Uses the StarStack macros (klipper-ui macros/starstack_macros.cfg), which never block:
#   LOAD_FILAMENT / UNLOAD_FILAMENT MATERIAL=X  → heats if cold, moves filament when hot
#   PURGE_MORE, FILAMENT_DONE (heater off unless a print is paused)
# The remembered material (save_variables) lets Unload start straight away.
# klipper-ui D-116: Prime (heat, then push a little), and walk-away loading: Grab pulls the
# filament into the gears while the nozzle heats (LOAD_FILAMENT GRAB=1), then it loads and purges
# by itself when hot and turns the heater off (GRABBED=1 OFF=1).
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, ss_mode="load", ss_material=None, ss_then=None, **kwargs):
        super().__init__(screen, title)
        self.then = ss_then  # after Done (not Cancel): e.g. back to Print (D-090)
        self.change = ss_mode == "change"  # color change: unload, then load the same material
        if self.change:
            ss_mode = "unload"
        self.mode = ss_mode
        self.mat = ss_material if ss_mode in ("unload", "prime") else None
        self.grabbed = False  # walk-away load: filament already pulled into the gears
        self.loaded = None  # filled in asynchronously (save_variables query)
        self.checked = ss_mode != "load"  # load: material buttons only once we know nothing is in
        self.swap = False  # loading over a loaded filament: unload it first, then pick the new one
        if ss_mode == "load" or (self.change and not ss_material):
            ss.query_loaded_material(screen, self._got_loaded)
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
            w.set_no_show_all(True)  # visibility is controlled by render(), not by show_all()
        if self.step == "heat":
            self.start_heat()
        self.render()

    def _got_loaded(self, material):
        """Async answer: which filament Klipper remembers as loaded."""
        if self.step != "pick":
            return
        if self.change and material:  # color change: unload the remembered material
            self.mat = material
            self.start_heat()
        elif self.mode == "load":
            self.loaded, self.checked = material, True
            self.render()

    # ---- actions
    def macro(self):
        return "UNLOAD_FILAMENT" if self.mode == "unload" else "LOAD_FILAMENT"

    def pick(self, widget, name):
        self.mat = name
        self.start_heat()

    def start_heat(self):
        self.step = "heat"
        self.sent_move = False
        self.grabbed = False
        # HEAT=1: heat only. The move is sent once, when hot (unload) or when the user taps Load.
        # Without it a nozzle that was already hot (paused print) moved twice (klipper-ui D-097).
        ss.gcode(self._screen, f"{self.macro()} MATERIAL={self.mat} HEAT=1")
        self.render()

    def target(self):
        return ss.MATERIALS[self.mat][0] if self.mat else 0

    def hot(self):
        return (self._printer.get_stat("extruder", "temperature") or 0) >= self.target() - 5

    def next(self, widget):
        if self.step == "ready":  # load: filament inserted
            ss.gcode(self._screen, f"LOAD_FILAMENT MATERIAL={self.mat}")
            self.step = "purge"
        elif self.step == "pick" and self.mode == "load" and self.loaded:
            # a filament is in: it must come out before a new one goes in (user, 2026-11-02)
            self.swap, self.mode, self.mat = True, "unload", self.loaded
            self.start_heat()
            return
        elif self.step == "unloaded" and self.change:  # old filament out → load the new color
            self.mode, self.step = "load", "ready"
        elif self.step == "unloaded" and self.swap:  # old filament out → pick the new one
            self.swap, self.loaded, self.mat = False, None, None
            self.mode, self.step = "load", "pick"
        elif self.step in ("purge", "unloaded", "away"):
            ss.gcode(self._screen, "FILAMENT_DONE")
            ss.close_dialog(self._screen)
            if self.then:
                self.then()
            return
        self.render()

    def alt(self, widget):
        if self.step == "purge":
            ss.gcode(self._screen, "PURGE_MORE", widget)
        elif self.step == "heat" and self.mode == "load" and not self.grabbed:
            ss.gcode(self._screen, f"LOAD_FILAMENT MATERIAL={self.mat} GRAB=1", widget)
            self.grabbed = True
            self.render()
        elif self.step == "away":  # loaded while away, heater off: heat again and push a little
            self.mode = "prime"
            self.start_heat()

    def cancel(self, widget):
        if self.step != "pick":
            ss.gcode(self._screen, "FILAMENT_DONE")
        ss.close_dialog(self._screen)

    # ---- view
    def render(self):
        load = self.mode == "load"
        self.title_lbl.set_text(
            _("Change filament")
            if self.change or self.swap or (load and self.loaded)
            else (
                _("Prime") + f" {self.mat}"
                if self.mode == "prime"
                else (_("Load filament") if load else _("Unload filament"))
            )
        )
        if self.mode == "prime":
            steps = ["heat", "purge"]
        elif load:
            steps = ["pick", "heat", "away" if self.grabbed else "ready", "purge"]
        else:
            steps = ["pick", "heat", "unloaded"]
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
            txt = (
                _("Which material are you loading?")
                if load
                else _("No filament is recorded as loaded.")
                + "\n"
                + _("Which material is in the printer?")
            )
            if load and not self.checked:
                txt = _("Checking which filament is in…")
            elif load and self.loaded:
                txt = (
                    f"{self.loaded} "
                    + _("is in the printer.")
                    + "\n"
                    + _("It has to come out before you load a new filament.")
                )
                nxt = _("Unload") + f" {self.loaded}"
        elif self.step == "heat" and self.mode == "prime":
            txt = _("Heating the nozzle, then it pushes out a little") + f" {self.mat}."
        elif self.step == "heat" and load and self.grabbed:
            txt = (
                _("Filament grabbed. You can walk away.")
                + "\n"
                + _("It loads and purges when the nozzle is hot, then turns the heater off.")
            )
        elif self.step == "heat" and load:
            txt = (
                _("Loading")
                + f" {self.mat}. "
                + _("Heating the nozzle first.")
                + "\n"
                + _("To walk away: push the filament in until it stops, then tap Grab.")
            )
            alt = _("Grab")
        elif self.step == "heat":
            txt = (
                _("Unloading")
                + f" {self.mat}.\n"
                + _("Heating the nozzle first. This takes about a minute.")
            )
        elif self.step == "away":
            txt = (
                f"{self.mat} "
                + _("is loading and purging.")
                + "\n"
                + _("The heater turns off when it's done. Prime pushes out more if needed.")
            )
            alt, nxt = _("Prime"), _("Done")
        elif self.step == "ready":
            txt = (
                _("Nozzle is hot.")
                + "\n"
                + _("Push the filament in until it grips, or turn the extruder gear by hand.")
                + " "
                + _("Then tap Load.")
            )
            nxt = _("Load")
        elif self.step == "purge":
            txt = (
                _("Filament is purging.")
                + "\n"
                + _("Is the plastic coming out clean and the right color?")
            )
            alt, nxt = _("Purge more"), _("Done")
        else:  # unloaded
            if self.change or self.swap:
                txt = _("Unloading…") + "\n" + _("Pull the old filament out gently, then tap Next.")
                nxt = _("Next")
            else:
                txt = (
                    _("Unloading…")
                    + "\n"
                    + _("When the filament is free, pull it out gently and tap Done.")
                    + " "
                    + _("The motor is off, so the extruder gear turns by hand.")
                )
                nxt = _("Done")
        self.body.set_text(txt)
        # materials only once we know nothing is in (a loaded filament must come out first)
        self.mats.set_visible(self.step == "pick" and self.checked and not (load and self.loaded))
        self.bar_box.set_visible(self.step == "heat" and not self.grabbed)
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
        self.temp_lbl.set_text(f"{t:.0f}°C / {tgt}°C")
        self.bar.set_fraction(max(0.0, min(1.0, t / tgt)) if tgt else 0)
        if self.hot() and not self.sent_move:
            self.sent_move = True
            if self.mode == "prime":
                ss.gcode(self._screen, "PURGE_MORE")
                self.step = "purge"
            elif self.mode == "load" and self.grabbed:
                ss.gcode(self._screen, f"LOAD_FILAMENT MATERIAL={self.mat} GRABBED=1 OFF=1")
                self.step = "away"
            elif self.mode == "load":
                self.step = "ready"
            else:
                ss.gcode(self._screen, f"UNLOAD_FILAMENT MATERIAL={self.mat}")
                self.step = "unloaded"
            self.render()

    def process_update(self, action, data):
        if action == "notify_status_update" and "extruder" in data:
            self.update_temp()

    def activate(self):
        self.render()  # KlipperScreen re-shows the whole page after attaching; re-apply visibility

    def back(self):
        self.cancel(None)
        return True
