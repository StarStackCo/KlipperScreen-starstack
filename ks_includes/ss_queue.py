# STARSTACK-ADDED: job queue list (FORK_CHANGES.md #54, klipper-ui D-111)
# The queued jobs with move earlier / later / remove, and a check of the next job's filament
# against the loaded one. Used by Home after a print (design "A4") and by the Queue page.
#   mode "start": the printer is free: Not now / Print anyway / Change to X or Plate is clear, start
#   mode "busy":  a print is running: Back / Add a file
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss

THUMB = 30


class QueueView:
    def __init__(self, panel, mode="start", on_close=None):
        self.panel = panel
        self.screen = panel._screen
        self.mode = mode
        self.on_close = on_close
        self.loaded = None
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, vexpand=True)
        self.head = ss.section("")
        self.box.pack_start(self.head, False, False, 0)
        self.pager = ss.Pager(spacing=4, compact=True)
        self.box.pack_start(self.pager.box, True, True, 0)
        self.warn = ss.label("", "ss-text-warning ss-row-title", ellipsize=True)
        self.warn.set_no_show_all(True)
        self.box.pack_start(self.warn, False, False, 0)
        self.actions = Gtk.Box(spacing=8, homogeneous=True)
        self.box.pack_start(self.actions, False, False, 0)

    # ---- data
    def jobs(self):
        return ss.queue_jobs()

    def want(self):
        jobs = self.jobs()
        return ss.file_material(self.screen, jobs[0]["filename"]) if jobs else None

    def refresh(self):
        """Redraw from the cached queue; the loaded filament is asked for again each time."""
        self.render()
        ss.query_loaded_material(self.screen, self._got_loaded)

    def _got_loaded(self, material):
        self.loaded = material
        self.render()

    # ---- view
    def render(self):
        jobs = self.jobs()
        total = sum(
            (self.screen.files.get_file_info(j["filename"]) or {}).get("estimated_time") or 0
            for j in jobs
        )
        n = len(jobs)
        head = _("Up next") + " · " + (_("1 job") if n == 1 else f"{n} " + _("jobs"))
        self.head.set_text((head + (f" · {ss.fmt_duration(total)}" if total else "")).upper())
        self.pager.set_rows([(self.row(i, j), "row") for i, j in enumerate(jobs)])
        want = self.want()
        swap = self.mode == "start" and want and self.loaded and want != self.loaded
        empty = self.mode == "start" and want and not self.loaded
        if swap:
            self.warn.set_text(_("Next job needs") + f" {want}. {self.loaded} " + _("is loaded."))
        elif empty:
            self.warn.set_text(_("Next job needs") + f" {want}. " + _("No filament is loaded."))
        self.warn.set_visible(bool(swap or empty))
        for c in self.actions.get_children():
            self.actions.remove(c)
        if self.mode == "busy":
            self.add_button(_("Back"), "ss-btn-outline", self.close)
            self.add_button(_("Add a file"), "ss-btn-card", self.add_file)
        else:
            self.add_button(_("Not now"), "ss-btn-outline", self.close)
            if swap or empty:
                self.add_button(_("Print anyway"), "ss-btn-card", self.print_anyway)
                text = (_("Change to") if swap else _("Load")) + f" {want}"
                self.add_button(text, "ss-btn-primary", self.change_filament)
            elif jobs:
                self.add_button(_("Plate is clear, start"), "ss-btn-primary", self.start)
        self.actions.show_all()

    def add_button(self, text, css, cb):
        b = ss.button(text, css=f"ss-btn {css} ss-btn-action")
        b.connect("clicked", lambda w: cb())
        self.actions.pack_start(b, True, True, 0)

    def row(self, i, job):
        fn = job["filename"]
        meta = self.screen.files.get_file_info(fn) or {}
        box = Gtk.Box(spacing=6)
        box.get_style_context().add_class("ss-card")
        box.get_style_context().add_class("ss-qrow")
        if i == 0 and self.mode == "start":
            box.get_style_context().add_class("ss-card-hl")
        box.pack_start(ss.label(f"{i + 1}", "ss-qnum", xalign=0.5), False, False, 0)
        frame = Gtk.Box()
        frame.get_style_context().add_class("ss-thumb")
        img = self.panel._gtk.Image("file", THUMB * 0.6, THUMB * 0.6)
        img.set_size_request(THUMB, THUMB)
        frame.pack_start(img, True, True, 0)
        ss.thumbnail(self.panel, fn, THUMB, img)
        box.pack_start(frame, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        txt.add(ss.label(ss.pretty_name(fn), "ss-row-title", ellipsize=True))
        mat = (meta.get("filament_type") or "").split(";")[0]
        sub = " · ".join(x for x in (mat, ss.fmt_duration(meta.get("estimated_time"))) if x)
        if fn not in self.screen.files.files:
            sub = _("File no longer on the printer")
        txt.add(ss.label(sub, "ss-btn-sub", ellipsize=True))
        box.pack_start(txt, True, True, 0)
        tools = Gtk.Box()
        for icon, cb, ok in (
            ("arrow-up", lambda w: ss.queue_move(self.screen, i, -1, self.refresh), i > 0),
            (
                "arrow-down",
                lambda w: ss.queue_move(self.screen, i, 1, self.refresh),
                i < len(self.jobs()) - 1,
            ),
            ("cancel", lambda w: ss.queue_remove(self.screen, job["job_id"], self.refresh), True),
        ):
            b = Gtk.Button(can_focus=False)
            b.add(self.panel._gtk.Image(icon, 16, 16))
            for c in ("ss-btn", "ss-btn-qtool") + (("ss-btn-qremove",) if icon == "cancel" else ()):
                b.get_style_context().add_class(c)
            b.set_sensitive(ok)
            b.connect("clicked", cb)
            tools.pack_start(b, False, False, 0)
        box.pack_end(tools, False, False, 0)
        return box

    # ---- actions
    def close(self):
        if self.on_close:
            self.on_close()

    def add_file(self):
        self.screen.show_panel("ss_print", remove_all=True)

    def start(self):
        ss.queue_start(self.screen)

    def print_anyway(self):
        # tell PRINT_START too, so it doesn't ask again (klipper-ui D-106)
        ss.gcode(self.screen, f"ACCEPT_MATERIAL MATERIAL={self.want()}")
        ss.queue_start(self.screen)

    def change_filament(self):
        """Unload what is in (the load page does that first, D-097 follow-up), load the next
        job's material, then come back here with the check passed."""
        back = lambda: ss.queue_refresh(self.screen, self.refresh)  # noqa: E731
        ss._push(self.screen, "ss_filament", ss_mode="load", ss_then=back)
