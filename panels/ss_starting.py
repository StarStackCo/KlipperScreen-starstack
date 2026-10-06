# STARSTACK-ADDED: "Starting printer…" screen (FORK_CHANGES.md #31, hook #11)
# Replaces the stock splash while Klipper starts, restarts or reconnects (STARSTACK-CHANGE #11 in
# screen.py printer_initializing). Shutdown/error states use ss_stopped instead.
# Same API as the stock splash: update_text(msg).
# Progress bar (klipper-ui D-070): after power-up it continues the boot splash's bar (same
# estimate, from uptime); after a restart it fills over ~12 s. It only reaches 100 % when the
# printer is ready: finish() fills it to the end, then screen.py opens Home (D-071).
# Cover (D-073): when klipper-ui's boot splash is installed, a full-screen window shows the exact
# boot image (logo + bar, no rail or buttons) so boot, restart and this screen look identical.
# If the printer still isn't up after COVER_MAX seconds, the cover lifts to show this panel's
# status text and Details / Retry buttons.
import os
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

BOOT_PNG = "/usr/local/share/starstack/starstack-splash-boot.png"
BAR = (140, 236, 200, 6)  # x, y, w, h: same as klipper-ui tools/make_splash.py + bootbar
FILL = (0x00 / 255, 0xAC / 255, 0xC7 / 255)  # theme @accent
COVER_MAX = 60


class Cover:
    """Full-screen copy of the boot splash with a live progress bar."""

    def __init__(self, pix):
        self.pix, self.fraction = pix, 0.0
        self.win = Gtk.Window(type=Gtk.WindowType.POPUP)  # no window manager: always on top
        self.win.set_default_size(pix.get_width(), pix.get_height())
        self.win.move(0, 0)
        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.draw)
        self.win.add(self.area)

    @staticmethod
    def load(screen):
        if not os.path.exists(BOOT_PNG):
            return None
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file(BOOT_PNG)
        except GLib.Error:
            return None
        if (pix.get_width(), pix.get_height()) != (screen.width, screen.height):
            return None
        return Cover(pix)

    def set_fraction(self, f):
        if f != self.fraction:
            self.fraction = f
            x, y, w, h = BAR
            self.area.queue_draw_area(x, y, w, h)

    def draw(self, area, ctx):
        Gdk.cairo_set_source_pixbuf(ctx, self.pix, 0, 0)
        ctx.paint()
        x, y, w, h = BAR
        fill = int(w * self.fraction)
        if fill > 1:  # same shape as the boot bar: corner pixels cut
            ctx.set_source_rgb(*FILL)
            ctx.rectangle(x, y + 1, fill, h - 2)
            ctx.rectangle(x + 1, y, fill - 1, h)
            ctx.fill()

    def show(self):
        self.win.show_all()

    def hide(self):
        self.win.hide()

    def destroy(self):
        self.win.destroy()


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
        self.cover = None
        self.show_cover()
        # First screen of this app: stop the boot splash, then repaint everything once in case
        # its last frame landed on top of us
        ss.boot_ui_up()
        GLib.timeout_add(600, lambda: self._screen.queue_draw() and False)

    def activate(self):
        self.started = time.monotonic()
        self.finishing = None
        self.show_cover()
        self.tick()
        if self.timer is None:
            self.timer = GLib.timeout_add(250, self.tick)

    def set_progress(self, f):
        self.bar.set_fraction(f)
        if self.cover:
            self.cover.set_fraction(f)

    def show_cover(self):
        if self.cover is None:
            self.cover = Cover.load(self._screen)
        if self.cover:
            self.cover.show()

    def leave(self):
        self.timer = None
        if self.cover:
            self.cover.destroy()  # a new one is made next time (this panel may be rebuilt)
            self.cover = None
        return False

    def finish(self, done):
        """Printer ready: run the bar to the end (~0.2 s, keeps Home quick), then call done()."""
        if self.finishing is not None:
            return  # already on the way
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        start = self.bar.get_fraction()
        self.finishing = 0

        def step():
            self.finishing += 1
            self.set_progress(min(1.0, start + (1 - start) * self.finishing / 4))
            if self.finishing < 4:
                return True
            GLib.timeout_add(60, self.finished, done)
            return False

        GLib.timeout_add(40, step)

    def finished(self, done):
        self.finishing = None
        done()  # Home is drawn under the cover first, then the cover goes: no flash
        if self._screen._cur_panels[-1:] == ["ss_starting"]:  # not ready after all: carry on
            self.activate()
        else:
            self.leave()
        return False

    def tick(self):
        if self.finishing is not None:
            self.timer = None
            return False
        if not self._screen._cur_panels or self._screen._cur_panels[-1] != "ss_starting":
            return self.leave()  # another screen took over (error, print, dialog)
        up = ss.uptime()
        if up < ss.BOOT_WINDOW:
            p = ss.progress(up, ss.boot_expected())
        else:
            p = ss.progress(time.monotonic() - self.started, 12)
        self.set_progress(p)
        if self.cover and time.monotonic() - self.started > COVER_MAX:
            self.cover.hide()  # taking too long: show the status text and buttons
        return True

    def deactivate(self):
        self.leave()

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
