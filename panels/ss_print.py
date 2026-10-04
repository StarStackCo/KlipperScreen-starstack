# STARSTACK-ADDED: Print page: 6 files per page with thumbnails, sort button (FORK_CHANGES.md #12)
# Sort cycles Newest first → Oldest first → Recently printed (user request D-030).
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel
from ks_includes import starstack as ss

SORTS = ("Newest first", "Oldest first", "Recently printed")
PER_PAGE = 6


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.page = 0
        self.sort = int(ss.get_setting("print_sort", 0) or 0)
        root = ss.page_box(spacing=8)
        head = Gtk.Box(spacing=8)
        head.pack_start(ss.label(_("Print a file"), "ss-page-title"), False, False, 0)
        self.page_lbl = ss.label("", "ss-muted", xalign=1.0)
        head.pack_start(self.page_lbl, True, True, 0)
        self.sort_btn = ss.button(_(SORTS[self.sort]), css="ss-btn ss-btn-card ss-btn-sort", image="shuffle",
                                  gtk=self._gtk, img_size=14, vertical=False)
        self.sort_btn.set_hexpand(False)
        self.sort_btn.connect("clicked", self.cycle_sort)
        head.pack_end(self.sort_btn, False, False, 0)
        root.add(head)
        self.grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=8, row_spacing=8,
                             hexpand=True, vexpand=True)
        root.pack_start(self.grid, True, True, 0)
        foot = Gtk.Box(spacing=8)
        prev = ss.button("‹", css="ss-btn ss-btn-outline ss-btn-pager")
        prev.set_hexpand(False)
        prev.connect("clicked", self.turn, -1)
        nxt = ss.button("›", css="ss-btn ss-btn-outline ss-btn-pager")
        nxt.set_hexpand(False)
        nxt.connect("clicked", self.turn, 1)
        self.note = ss.label("", "ss-muted", xalign=0.5)
        foot.pack_start(prev, False, False, 0)
        foot.pack_start(self.note, True, True, 0)
        foot.pack_end(nxt, False, False, 0)
        root.add(foot)
        self.content.add(root)
        self.content.show_all()

    def files(self):
        items = [f for f in self._files.files.values() if f.get("path", "").lower().endswith(".gcode")
                 and not f["path"].startswith("ss_bench_test")]
        if self.sort == 2:
            order = {}
            try:
                res = self._screen.apiclient.send_request("server/history/list?limit=200&order=desc")
                for i, job in enumerate(res.get("jobs", [])):
                    order.setdefault(job.get("filename"), i)
            except Exception as e:
                logging.debug(f"StarStack: history failed: {e}")
            return sorted(items, key=lambda f: (order.get(f["path"], 10 ** 6), -f.get("modified", 0)))
        return sorted(items, key=lambda f: f.get("modified", 0), reverse=self.sort == 0)

    def refresh(self):
        for c in self.grid.get_children():
            self.grid.remove(c)
        files = self.files()
        pages = max(1, (len(files) + PER_PAGE - 1) // PER_PAGE)
        self.page = max(0, min(self.page, pages - 1))
        self.page_lbl.set_text(_("Page") + f" {self.page + 1} / {pages}")
        busy = ss.is_printing(self._printer)
        self.note.set_text(_("A print is running") if busy else _("Tap a file to print"))
        for i, f in enumerate(files[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]):
            fn = f["path"]
            meta = self._files.get_file_info(fn) or {}
            b = Gtk.Button(can_focus=False, hexpand=True, vexpand=True)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            thumb = Gtk.Box()
            thumb.get_style_context().add_class("ss-thumb")
            pix = None
            try:
                pix = self.get_file_image(fn, 30, 30)
            except Exception:
                pass
            img = Gtk.Image.new_from_pixbuf(pix) if pix else self._gtk.Image("file", 22, 22)
            img.set_size_request(-1, 30)
            thumb.pack_start(img, True, True, 0)
            box.add(thumb)
            box.add(ss.label(ss.pretty_name(fn), "ss-tile-title", ellipsize=True))
            mat = (meta.get("filament_type") or "").split(";")[0]
            box.add(ss.label(" · ".join(x for x in (mat, ss.fmt_duration(meta.get("estimated_time"))) if x),
                             "ss-btn-sub", ellipsize=True))
            b.add(box)
            b.get_style_context().add_class("ss-btn")
            b.get_style_context().add_class("ss-tile")
            b.set_sensitive(not busy)
            b.connect("clicked", lambda w, p=fn: ss.bed_clear_then_print(self._screen, p))
            self.grid.attach(b, i % 3, i // 3, 1, 1)
        if not files:
            self.grid.attach(ss.label(_("No files yet. Send one from OrcaSlicer."), "ss-muted", xalign=0.5), 0, 0, 3, 2)
        self.grid.show_all()

    def cycle_sort(self, *args):
        self.sort = (self.sort + 1) % len(SORTS)
        ss.set_setting("print_sort", self.sort)
        ss.set_button_text(self.sort_btn, _(SORTS[self.sort]))
        self.page = 0
        self.refresh()

    def turn(self, widget, d):
        self.page += d
        self.refresh()

    def activate(self):
        self.refresh()

    def process_update(self, action, data):
        if action == "notify_filelist_changed":
            self.refresh()
        elif action == "notify_metadata_update":
            ss.debounce(self, "_meta_timer", 400, self.refresh)
