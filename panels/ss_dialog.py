# STARSTACK-ADDED: in-content confirmation / info dialog (FORK_CHANGES.md #26)
# Shown inside the content area so the rail (and STOP) stays reachable.
# Open with ks_includes.starstack.confirm() / info(), never directly.
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
        ss_body="",
        ss_yes=None,
        ss_no=None,
        ss_on_yes=None,
        ss_kind="primary",
        **kwargs,
    ):
        super().__init__(screen, title)
        self.on_yes = ss_on_yes
        for child in self.content.get_children():
            self.content.remove(child)

        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=True,
        )
        card.get_style_context().add_class("ss-dialog")
        title_css = {
            "danger": "ss-dialog-title ss-text-error",
            "warning": "ss-dialog-title ss-text-warning",
        }
        card.add(ss.label(ss_title, title_css.get(ss_kind, "ss-dialog-title"), wrap=True))
        card.add(ss.label(ss_body, "ss-dialog-body", wrap=True))

        row = ss.grid(2 if ss_yes else 1, spacing=8)
        no = ss.button(ss_no or _("Go back"), css="ss-btn ss-btn-outline ss-btn-lg")
        no.connect("clicked", self.close)
        widgets = [no]
        if ss_yes:
            yes_css = {
                "danger": "ss-btn ss-btn-danger ss-btn-lg",
                "warning": "ss-btn ss-btn-warning ss-btn-lg",
            }
            yes = ss.button(ss_yes, css=yes_css.get(ss_kind, "ss-btn ss-btn-primary ss-btn-lg"))
            yes.connect("clicked", self.accept)
            widgets.append(yes)
        ss.grid_add(row, widgets)
        card.add(row)

        page = ss.page_box()
        page.add(card)
        self.content.add(page)
        self.content.show_all()

    def close(self, *args):
        ss.close_dialog(self._screen)

    def accept(self, *args):
        cb = self.on_yes
        self.close()
        if cb:
            cb()
