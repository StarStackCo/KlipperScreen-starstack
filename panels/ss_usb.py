# STARSTACK-ADDED: "USB stick: N new files copied" prompt (FORK_CHANGES.md #37, klipper-ui D-065)
# Opened by StarStackRail when klipper-ui's USB import (usb/ + tools/usb_import.py) has copied files
# from a stick into the print jobs folder. The stick is already unmounted, so it can be pulled out.
# Offers to print the newest copied file, unless a print is running.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, ss_report=None, **kwargs):
        super().__init__(screen, title)
        report = ss_report or {}
        copied = report.get("copied", [])
        failed = report.get("failed", [])
        self.newest = report.get("newest")
        busy = ss.is_printing(self._printer)

        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=True,
        )
        card.get_style_context().add_class("ss-dialog")
        head = Gtk.Box(spacing=8)
        head.pack_start(self._gtk.Image("usb", 20, 20), False, False, 0)
        if copied:
            n = len(copied)
            title_text = (
                _("USB stick:")
                + " "
                + (_("1 new file copied") if n == 1 else f"{n} " + _("new files copied"))
            )
        else:
            title_text = _("USB stick: no new files")
        head.pack_start(ss.label(title_text, "ss-dialog-title", wrap=True), True, True, 0)
        card.add(head)

        if copied:
            body = (
                (
                    _("The new file was copied to the print jobs folder.")
                    if len(copied) == 1
                    else _("New files were copied to the print jobs folder.")
                )
                + " "
                + _("You can remove the USB stick.")
            )
        elif report.get("skipped"):
            body = _(
                "Everything on the stick is already on the printer. You can remove the USB stick."
            )
        else:
            body = _("No print files (.gcode) found on the stick. You can remove the USB stick.")
        card.add(ss.label(body, "ss-dialog-body", wrap=True))
        if failed:
            card.add(
                ss.label(
                    f"{len(failed)} "
                    + _("file(s) couldn't be copied")
                    + f": {failed[0].get('reason', '')}",
                    "ss-text-error",
                    wrap=True,
                )
            )

        offer = bool(self.newest) and not busy  # file list may lag a moment; thumbnail waits
        if offer:
            card.add(ss.label(_("Print this one now?"), "ss-row-title"))
            row = Gtk.Box(spacing=10)
            frame = Gtk.Box()
            frame.get_style_context().add_class("ss-thumb")
            frame.set_size_request(56, 56)
            img = self._gtk.Image("file", 34, 34)
            img.set_size_request(56, 56)
            frame.pack_start(img, True, True, 0)
            ss.thumbnail(self, self.newest, 56, img)
            row.pack_start(frame, False, False, 0)
            txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            txt.add(ss.label(ss.pretty_name(self.newest), "ss-row-title", ellipsize=True))
            self.sub = ss.label(self.file_sub(), "ss-btn-sub", ellipsize=True)
            txt.add(self.sub)
            row.pack_start(txt, True, True, 0)
            card.add(row)

        buttons = ss.grid(2 if offer else 1, spacing=8)
        close = ss.button(
            _("Not now") if offer else _("OK"), css="ss-btn ss-btn-outline ss-btn-mid"
        )
        close.connect("clicked", lambda w: ss.close_dialog(self._screen))
        widgets = [close]
        if offer:
            go = ss.button(_("Print now"), css="ss-btn ss-btn-primary ss-btn-mid")
            go.connect("clicked", self.print_now)
            widgets.append(go)
        ss.grid_add(buttons, widgets)
        card.add(buttons)

        page = ss.page_box()
        page.add(card)
        self.content.add(page)
        self.content.show_all()

    def file_sub(self):
        meta = self._files.get_file_info(self.newest) or {}
        mat = (meta.get("filament_type", "") or "").split(";")[0]
        return " · ".join(x for x in (mat, ss.fmt_duration(meta.get("estimated_time"))) if x)

    def print_now(self, *args):
        fn = self.newest
        ss.close_dialog(self._screen)
        ss.bed_clear_then_print(self._screen, fn)

    def process_update(self, action, data):
        # the copied file's metadata (material, time) usually arrives a moment after the prompt
        if action == "notify_metadata_update" and data.get("filename") == self.newest:
            if hasattr(self, "sub"):
                self.sub.set_text(self.file_sub())
