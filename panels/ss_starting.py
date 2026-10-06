# STARSTACK-ADDED: "Starting printer…" screen (FORK_CHANGES.md #31, hook #11)
# Replaces the stock splash while Klipper starts, restarts or reconnects (STARSTACK-CHANGE #11 in
# screen.py printer_initializing). Shutdown/error states use ss_stopped instead.
# Same API as the stock splash: update_text(msg).
# Progress bar (klipper-ui D-070): after power-up it continues the boot splash's bar (same
# estimate, from uptime); after a restart it fills over ~12 s. It only reaches 100 % when the
# printer is ready: finish() fills it to the end, then screen.py opens Home (D-071).
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

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
        self.title_lbl = ss.label(_("Starting printer…"), "ss-starting-title", xalign=0.5)
        center.add(self.title_lbl)
        self.bar = Gtk.ProgressBar(halign=Gtk.Align.CENTER)
        self.bar.get_style_context().add_class("ss-boot-bar")
        self.bar.set_size_request(200, -1)
        center.add(self.bar)
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
        self.timer = None
        self.finishing = None
        self.started = time.monotonic()
        # First screen of this app: stop the boot splash, then repaint everything once in case
        # its last frame landed on top of us
        ss.boot_ui_up()
        GLib.timeout_add(600, lambda: self._screen.queue_draw() and False)

    def activate(self):
        self.started = time.monotonic()
        self.finishing = None
        self.tick()
        if self.timer is None:
            self.timer = GLib.timeout_add(250, self.tick)

    def finish(self, done):
        """Printer ready: run the bar to the end (~0.4 s), then call done()."""
        if self.finishing is not None:
            return  # already on the way
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        start = self.bar.get_fraction()
        self.finishing = 0

        def step():
            self.finishing += 1
            self.bar.set_fraction(min(1.0, start + (1 - start) * self.finishing / 8))
            if self.finishing < 8:
                return True
            GLib.timeout_add(200, self.finished, done)
            return False

        GLib.timeout_add(50, step)

    def finished(self, done):
        self.finishing = None
        done()
        if self._screen._cur_panels[-1:] == ["ss_starting"]:  # not ready after all: carry on
            self.activate()
        return False

    def tick(self):
        if self.finishing is not None:
            self.timer = None
            return False
        if not self._screen._cur_panels or self._screen._cur_panels[-1] != "ss_starting":
            self.timer = None
            return False
        up = ss.uptime()
        if up < ss.BOOT_WINDOW:
            p = ss.progress(up, ss.boot_expected())
        else:
            p = ss.progress(time.monotonic() - self.started, 12)
        self.bar.set_fraction(p)
        return True

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
