# STARSTACK-ADDED: Bed mesh page (FORK_CHANGES.md #46, klipper-ui D-067)
# Replaces the stock bed_mesh panel (Advanced › tools): colour map of the active mesh (blue low,
# orange high) + Calibrate / Profile / Clear / Save. Calibrate and Save ask first and are locked
# while printing (Save runs SAVE_CONFIG, which restarts Klipper).
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

LOW, MID, HIGH = (0.0, 0.67, 0.78), (0.15, 0.15, 0.15), (1.0, 0.54, 0.02)  # sky / grey / orange


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page = ss.page_box(spacing=6)
        page.pack_start(ss.label(_("Bed mesh"), "ss-page-title"), False, False, 0)
        body = Gtk.Box(spacing=10)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.map = Gtk.DrawingArea()
        self.map.set_size_request(176, 176)
        self.map.connect("draw", self.draw)
        left.pack_start(self.map, False, False, 0)
        self.range = ss.label("", "ss-btn-sub", xalign=0.5)
        left.pack_start(self.range, False, False, 0)
        body.pack_start(left, False, False, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        self.calibrate = ss.button(_("Calibrate"), css="ss-btn ss-btn-primary ss-btn-mid")
        self.calibrate.connect("clicked", self.ask_calibrate)
        self.profile = ss.button(_("Profile"), " ", css="ss-btn ss-btn-card ss-btn-mid")
        self.profile.connect("clicked", self.pick_profile)
        self.clear = ss.button(_("Clear active mesh"), css="ss-btn ss-btn-outline ss-btn-mid")
        self.clear.connect("clicked", lambda w: ss.gcode(self._screen, "BED_MESH_CLEAR", w))
        self.save = ss.button(_("Save to config"), css="ss-btn ss-btn-outline ss-btn-mid")
        self.save.connect("clicked", self.ask_save)
        for b in (self.calibrate, self.profile, self.clear, self.save):
            right.pack_start(b, False, False, 0)
        body.pack_start(right, True, True, 0)
        page.pack_start(body, False, False, 0)
        self.content.add(page)
        self.content.show_all()
        self.refresh()

    # ---- data
    def profiles(self):
        return self._printer.get_stat("bed_mesh", "profiles") or {}

    def active(self):
        return self._printer.get_stat("bed_mesh", "profile_name") or ""

    def points(self):
        prof = self.profiles().get(self.active()) or {}
        return prof.get("points") or []

    def refresh(self):
        busy = ss.is_printing(self._printer)
        name = self.active()
        ss.set_button_text(self.profile, _("Profile"), name or _("none loaded"))
        self.profile.set_sensitive(bool(self.profiles()))
        self.calibrate.set_sensitive(not busy)
        self.save.set_sensitive(not busy and bool(self.points()))  # nothing to save without a mesh
        pts = [v for row in self.points() for v in row]
        if pts:
            self.range.set_text(
                _("range") + f" {min(pts):+.3f} … {max(pts):+.3f} mm  ({max(pts) - min(pts):.3f})"
            )
        else:
            self.range.set_text(_("No mesh loaded. Tap Calibrate."))
        self.map.queue_draw()

    # ---- drawing
    def draw(self, area, ctx):
        w, h = area.get_allocated_width(), area.get_allocated_height()
        ctx.set_source_rgb(0.09, 0.09, 0.09)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()
        grid = self.points()
        if not grid or not grid[0]:
            return
        rows, cols = len(grid), len(grid[0])
        vals = [v for r in grid for v in r]
        lo, hi = min(vals), max(vals)
        span = max(abs(lo), abs(hi), 0.01)
        cw, ch = w / cols, h / rows
        for r, row in enumerate(grid):
            for c, v in enumerate(row):
                t = min(1.0, abs(v) / span)
                ctx.set_source_rgb(*mix(MID, HIGH if v > 0 else LOW, t))
                # row 0 is the front of the bed (y min): draw it at the bottom
                ctx.rectangle(c * cw + 1, (rows - 1 - r) * ch + 1, cw - 2, ch - 2)
                ctx.fill()

    # ---- actions
    def ask_calibrate(self, *args):
        homed = (self._printer.get_stat("toolhead", "homed_axes") or "").lower()
        script = ("" if all(a in homed for a in "xyz") else "G28\n") + "BED_MESH_CALIBRATE"
        ss.confirm(
            self._screen,
            _("Calibrate the bed mesh?"),
            _("The printer homes if needed, then probes the bed. The nozzle touches the bed: ")
            + _("make sure it's clean and empty. Takes a few minutes."),
            _("Calibrate"),
            lambda: ss.gcode(self._screen, script),
        )

    def pick_profile(self, *args):
        names = sorted(self.profiles())
        ss.choose(
            self._screen,
            _("Bed mesh profile"),
            [(n, n) for n in names],
            self.active(),
            lambda n: ss.gcode(self._screen, f"BED_MESH_PROFILE LOAD={n}"),
        )

    def ask_save(self, *args):
        ss.confirm(
            self._screen,
            _("Save the mesh to the config?"),
            _("Klipper writes printer.cfg and restarts. Takes about 10 seconds."),
            _("Save"),
            lambda: ss.gcode(self._screen, "SAVE_CONFIG"),
            kind="warning",
        )

    def process_update(self, action, data):
        if action == "notify_status_update" and "bed_mesh" in data:
            self.refresh()

    def activate(self):
        self.refresh()
