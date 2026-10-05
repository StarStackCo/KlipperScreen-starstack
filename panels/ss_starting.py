# STARSTACK-ADDED: "Starting printer…" screen (FORK_CHANGES.md #31, hook #11)
# Replaces the stock splash while Klipper starts, restarts or reconnects (STARSTACK-CHANGE #11 in
# screen.py printer_initializing). Shutdown/error states use ss_stopped instead.
# Same API as the stock splash: update_text(msg).
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


def plain(msg):
    m = (msg or "").lower()
    if "lost connection" in m or "disconnected" in m:
        return _("Reconnecting to the printer…")
    if "connecting" in m:
        return _("Connecting to the printer…")
    if "moonraker" in m:
        return _("Waiting for the printer service…")
    return _("Starting printer…")


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page = ss.page_box(spacing=8)
        page.set_valign(Gtk.Align.FILL)
        center = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            vexpand=True,
        )
        plate = Gtk.Box(halign=Gtk.Align.CENTER)
        plate.get_style_context().add_class("ss-logo-plate")
        plate.add(self._gtk.Image("starstack-logo", 220, 50))
        center.add(plate)
        status = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(18, 18)
        self.spinner.start()
        status.add(self.spinner)
        self.title_lbl = ss.label(_("Starting printer…"), "ss-starting-title", xalign=0.5)
        status.add(self.title_lbl)
        center.add(status)
        self.sub_lbl = ss.label(_("This usually takes about 10 seconds."), "ss-muted", xalign=0.5)
        center.add(self.sub_lbl)
        page.pack_start(center, True, True, 0)

        self.details = ss.label("", "ss-btn-sub", wrap=True, xalign=0.5)
        self.details.set_no_show_all(True)
        page.add(self.details)

        row = Gtk.Box(spacing=8)
        more = ss.button(_("Details"), css="ss-btn ss-btn-outline ss-btn-mid")
        more.set_hexpand(False)
        more.set_size_request(110, -1)
        more.connect("clicked", lambda w: self.details.set_visible(not self.details.get_visible()))
        self.action = ss.button("", css="ss-btn ss-btn-card ss-btn-mid")
        self.action.connect("clicked", self.do_action)
        row.pack_start(more, False, False, 0)
        row.pack_start(self.action, True, True, 0)
        page.add(row)
        self.content.add(page)
        self.content.show_all()
        self.update_text(_("Initializing printer..."))

    def update_text(self, text):
        self.title_lbl.set_text(plain(text))
        self.details.set_text((text or "").strip())
        connected = bool(
            self._screen._ws and self._screen._ws.connected and self._screen.state.initialized
        )
        ss.set_button_text(
            self.action, _("Restart Klipper") if connected else _("Retry connection")
        )

    def do_action(self, *args):
        if self._screen._ws and self._screen._ws.connected and self._screen.state.initialized:
            ss.confirm(
                self._screen,
                _("Restart Klipper?"),
                _("Use this if the printer stays on this screen for more than a minute."),
                _("Restart"),
                self._screen._ws.api.restart,
            )
        else:
            self._screen.connect_printer(self._screen.connecting_to_printer)
