# STARSTACK-ADDED: "Printer stopped" screen for Klipper shutdown / error
# (FORK_CHANGES.md #30, hook #8)
# Replaces the stock splash for these two states only (STARSTACK-CHANGE #8 in screen.py).
# Plain-language message + one confirmed "Restart printer" (FIRMWARE_RESTART); details on request.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, ss_kind="shutdown", ss_msg="", **kwargs):
        super().__init__(screen, title)
        msg = ss_msg or ""
        if "webhooks request" in msg or "emergency" in msg.lower() or "M112" in msg:
            headline, plain = _("Printer stopped"), _("Emergency stop was pressed.")
        elif ss_kind == "error":
            headline = _("Printer error")
            plain = _("Klipper could not start. This is usually a config or connection problem.")
        else:
            headline, plain = _("Printer stopped"), _("Klipper shut down to protect the printer.")
        page = ss.page_box(spacing=8)
        page.get_style_context().add_class("ss-stopped")
        head = Gtk.Box(spacing=10)
        head.add(self._gtk.Image("emergency", 30, 30))
        head.add(ss.label(headline, "ss-stopped-title"))
        page.add(head)
        page.add(ss.label(plain, "ss-dialog-body ss-stopped-body", wrap=True))
        page.add(
            ss.label(
                _("Heaters and motors are off. Check the printer is safe before restarting."),
                "ss-muted",
                wrap=True,
            )
        )
        self.details = ss.label(msg.strip(), "ss-btn-sub", wrap=True)
        scroll = self._gtk.ScrolledWindow(steppers=False)
        scroll.set_vexpand(True)
        scroll.add(self.details)
        page.pack_start(scroll, True, True, 0)
        spacer = Gtk.Box(vexpand=True)  # keeps the buttons at the bottom while details are hidden
        page.pack_start(spacer, True, True, 0)
        scroll.set_no_show_all(True)  # no empty dark box until Details is tapped
        row = Gtk.Box(spacing=8, homogeneous=False)
        more = ss.button(_("Details"), css="ss-btn ss-btn-outline ss-btn-action")
        more.set_hexpand(False)
        more.set_size_request(110, -1)
        more.connect("clicked", self.toggle_details, scroll, spacer)
        restart = ss.button(_("Restart printer"), css="ss-btn ss-btn-white ss-btn-action")
        restart.connect("clicked", self.ask_restart)
        row.pack_start(more, False, False, 0)
        row.pack_start(restart, True, True, 0)
        page.add(row)
        self.content.add(page)
        self.content.show_all()

    @staticmethod
    def toggle_details(widget, scroll, spacer):
        show = not scroll.get_visible()
        if show:
            scroll.set_no_show_all(False)  # show_all() skips widgets marked no_show_all
            scroll.show_all()
        else:
            scroll.hide()
        spacer.set_visible(not show)

    def ask_restart(self, *args):
        ss.confirm(
            self._screen,
            _("Restart the printer?"),
            _("Klipper restarts and the printer is ready again in about 10 seconds."),
            _("Restart"),
            self._screen._ws.api.restart_firmware,
        )
