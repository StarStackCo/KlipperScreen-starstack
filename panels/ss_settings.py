# STARSTACK-ADDED: Settings page (FORK_CHANGES.md #25)
# Pages with ‹ › arrows (no scrolling, D-064): Advanced mode + tools + printer settings
# Advanced tools live here so Controls never scrolls (D-029). Stock KlipperScreen panels are reused.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page = ss.page_box(spacing=6)
        page.pack_start(ss.label(_("Settings"), "ss-page-title"), False, False, 0)
        self.pager = ss.Pager()
        page.pack_start(self.pager.box, True, True, 0)
        self.content.add(page)
        self.content.show_all()
        self.build()

    def row(self, name, note="", cb=None, sensitive=True):
        b = Gtk.Button(can_focus=False, hexpand=True)
        box = Gtk.Box(spacing=8)
        box.pack_start(ss.label(name, "ss-row-title"), True, True, 0)
        box.pack_end(ss.label(note, "ss-muted", xalign=1.0), False, False, 0)
        b.add(box)
        b.get_style_context().add_class("ss-btn")
        b.get_style_context().add_class("ss-row")
        b.set_sensitive(sensitive)
        if cb:
            b.connect("clicked", lambda w: cb())
        return b

    def open(self, panel, title, **kw):
        self._screen.show_panel(panel, title, **kw)

    def build(self, reset=False):
        rows = []
        adv = ss.advanced()
        printing = ss.is_printing(self._printer)

        sw = Gtk.Button(can_focus=False, hexpand=True)
        box = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        txt.add(ss.label(_("Advanced mode"), "ss-row-title"))
        txt.add(
            ss.label(
                _("Extrude, console, bed mesh, tools"),
                "ss-btn-sub",
                ellipsize=True,
            )
        )
        box.pack_start(txt, True, True, 0)
        # Switch pill: fixed size, text centered in it
        track = Gtk.Box(valign=Gtk.Align.CENTER, halign=Gtk.Align.END)
        track.set_size_request(56, 28)
        track.get_style_context().add_class("ss-switch-on" if adv else "ss-switch-off")
        state = ss.label(_("ON") if adv else _("OFF"), "ss-switch-text", xalign=0.5)
        state.set_halign(Gtk.Align.CENTER)
        state.set_valign(Gtk.Align.CENTER)
        track.set_center_widget(state)
        box.pack_end(track, False, False, 0)
        sw.add(box)
        sw.get_style_context().add_class("ss-btn")
        sw.get_style_context().add_class("ss-row")
        sw.get_style_context().add_class("ss-row-tall")
        sw.connect("clicked", self.toggle_advanced)
        rows.append((sw, "tall"))

        if adv:
            rows.append((ss.label(_("ADVANCED"), "ss-section ss-text-warning"), "section"))
            for name, note, cb in [
                (
                    _("Extrude / retract"),
                    _("blocked when cold"),
                    lambda: self.open("ss_extrude", _("Extrude")),
                ),
                (_("Console"), _("type G-code"), lambda: self.open("ss_console", _("Console"))),
                (_("Updates"), "", lambda: self.open("ss_updates", _("Updates"))),
                (
                    _("All KlipperScreen tools"),
                    _("bed mesh, etc."),
                    lambda: self.open(
                        "main_menu", _("KlipperScreen"), items=self._config.get_menu_items("__main")
                    ),
                ),
                (_("Restart firmware"), "", self.ask_restart),
            ]:
                rows.append((self.row(name, note, cb), "row"))

        rows.append((ss.label(_("PRINTER"), "ss-section"), "section"))
        lock = " · " + _("locked while printing") if printing else ""
        for name, note, cb, ok in [
            (_("Wi-Fi"), "", lambda: self.open("ss_network", _("Wi-Fi")), True),
            (
                _("Screen & language"),
                _("sleep, 24 h, language"),
                lambda: self.open("ss_screen", _("Screen")),
                True,
            ),
            (_("About this printer"), "", lambda: self.open("ss_about", _("About")), True),
            (
                _("Shut down / reboot") + lock,
                "",
                lambda: self.open("ss_power", _("Shut down")),
                not printing,
            ),
        ]:
            rows.append((self.row(name, note, cb, ok), "row"))
        self.pager.set_rows(rows, reset=reset)

    def toggle_advanced(self, *args):
        if ss.advanced():
            ss.set_setting("advanced", False)
            self.build()
            return

        def on():
            ss.set_setting("advanced", True)
            self.build()

        ss.confirm(
            self._screen,
            _("Turn on Advanced mode?"),
            _("Advanced settings can ruin prints or damage the printer if set wrong.")
            + "\n"
            + _("Proceed at your own risk."),
            _("I understand, turn on"),
            on,
            kind="warning",
        )

    def ask_restart(self):
        ss.confirm(
            self._screen,
            _("Restart firmware?"),
            _("Klipper restarts and the printer is ready again in about 10 seconds."),
            _("Restart"),
            self._screen._ws.api.restart_firmware,
        )

    def activate(self):
        self.build(reset=True)
