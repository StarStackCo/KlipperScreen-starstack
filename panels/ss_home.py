# STARSTACK-ADDED: Home page: idle / printing / complete (FORK_CHANGES.md #22)
# Design: klipper-ui design/phase2-directions/Prototype.dc.html (approved D-029/D-030)
import logging
import os
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from ks_includes.screen_panel import ScreenPanel
from ks_includes import starstack as ss

THUMB = 56


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.recent_cache = (0, [])
        self.dismissed = None
        self.resume_at = None                 # target °C while reheating before resume
        self.speed_pending = None             # tapped speed preset not yet applied by Klipper
        self.cc = {"changes": [], "m73": []}  # color changes in the current file
        self.phase = False                    # alternates "color change in" / "time left"
        self.ticker = None
        self.stack = Gtk.Stack(hexpand=True, vexpand=True)
        self.stack.add_named(self.build_idle(), "idle")
        self.stack.add_named(self.build_printing(), "printing")
        self.stack.add_named(self.build_done(), "done")
        self.content.add(self.stack)
        self.content.show_all()

    # ------------------------------------------------------------ idle
    def build_idle(self):
        page = ss.page_box()
        page.add(ss.section(_("Print again")))
        self.recent_grid = ss.grid(3, spacing=8)
        page.add(self.recent_grid)
        page.add(ss.section(_("Preheat")))
        row = ss.grid(4, spacing=8)
        btns = []
        for name, (noz, bed) in ss.MATERIALS.items():
            b = ss.button(name, f"{noz}° / {bed}°", css="ss-btn ss-btn-card ss-btn-tall")
            b.connect("clicked", lambda w, n=name: ss.gcode(self._screen, f"PREHEAT_{n}", w))
            btns.append(b)
        cool = ss.button(_("Cool down"), css="ss-btn ss-btn-outline ss-btn-tall ss-text-sky",
                         image="cool-down", gtk=self._gtk, img_size=18)
        cool.connect("clicked", lambda w: ss.gcode(self._screen, "COOL_DOWN", w))
        btns.append(cool)
        ss.grid_add(row, btns)
        page.add(row)
        return page

    def recent_jobs(self):
        stamp, jobs = self.recent_cache
        if time.time() - stamp < 30 and jobs:
            return jobs
        jobs, seen = [], set()
        try:
            res = self._screen.apiclient.send_request("server/history/list?limit=30&order=desc")
            for job in res.get("jobs", []):
                fn = job.get("filename")
                if not fn or fn in seen or not job.get("exists", True) or fn.startswith("ss_bench"):
                    continue
                seen.add(fn)
                jobs.append(job)
                if len(jobs) == 3:
                    break
        except Exception as e:
            logging.debug(f"StarStack: history failed: {e}")
        if len(jobs) < 3:   # fall back to newest files
            files = sorted(self._files.files.values(), key=lambda f: f.get("modified", 0), reverse=True)
            for f in files:
                if f["path"] not in seen and len(jobs) < 3:
                    seen.add(f["path"])
                    jobs.append({"filename": f["path"], "metadata": f})
        self.recent_cache = (time.time(), jobs)
        return jobs

    def refresh_idle(self):
        for child in self.recent_grid.get_children():
            self.recent_grid.remove(child)
        tiles = []
        for i, job in enumerate(self.recent_jobs()):
            fn = job["filename"]
            meta = self._files.get_file_info(fn) or job.get("metadata", {}) or {}
            b = Gtk.Button(can_focus=False, hexpand=True)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.add(self.thumb(fn, THUMB))
            box.add(ss.label(ss.pretty_name(fn), "ss-tile-title", lines=2))
            mat = meta.get("filament_type", "") or ""
            sub = (mat.split(";")[0], ss.fmt_duration(meta.get("estimated_time")))
            box.add(ss.label(" · ".join(x for x in sub if x),
                             "ss-btn-sub", ellipsize=True))
            b.add(box)
            b.get_style_context().add_class("ss-btn")
            b.get_style_context().add_class("ss-tile")
            if i == 0:
                b.get_style_context().add_class("ss-tile-highlight")
            b.connect("clicked", lambda w, f=fn: ss.bed_clear_then_print(self._screen, f))
            tiles.append(b)
        if not tiles:
            tiles.append(ss.label(_("No prints yet. Send one from OrcaSlicer."), "ss-muted", wrap=True))
        ss.grid_add(self.recent_grid, tiles)
        self.recent_grid.show_all()

    def thumb(self, filename, size):
        frame = Gtk.Box(halign=Gtk.Align.FILL)
        frame.get_style_context().add_class("ss-thumb")
        pix = None
        try:
            pix = self.get_file_image(filename, size, size)
        except Exception:
            pass
        img = Gtk.Image.new_from_pixbuf(pix) if pix else self._gtk.Image("file", size * 0.6, size * 0.6)
        img.set_size_request(-1, size)
        frame.pack_start(img, True, True, 0)
        return frame

    # ------------------------------------------------------------ printing
    def build_printing(self):
        page = ss.page_box(spacing=7)
        card = Gtk.Box(spacing=10)
        card.get_style_context().add_class("ss-card")
        self.job_thumb_box = Gtk.Box()
        card.pack_start(self.job_thumb_box, False, False, 0)
        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        self.job_name = ss.label("", "ss-job-name", ellipsize=True)
        self.job_line = ss.label("", "ss-muted", ellipsize=True)
        self.progress = Gtk.ProgressBar(hexpand=True)
        self.progress.get_style_context().add_class("ss-progress")
        mid.add(self.job_name)
        mid.add(self.job_line)
        mid.add(self.progress)
        card.pack_start(mid, True, True, 0)
        self.job_pct = ss.label("0%", "ss-pct", xalign=1.0)
        card.pack_end(self.job_pct, False, False, 0)
        page.add(card)

        speeds = ss.grid(4)
        self.speed_btns = {}
        for name, pct, macro in ss.SPEEDS:
            b = ss.button(_(name), f"{pct}%", css="ss-btn ss-btn-chip")
            b.connect("clicked", self.pick_speed, pct, macro)
            self.speed_btns[pct] = b
        ss.grid_add(speeds, [self.speed_btns[p] for _n, p, _m in ss.SPEEDS])
        page.add(speeds)

        self.tiles_box = Gtk.Box()
        page.add(self.tiles_box)
        self.tiles = {}
        self.tiles_adv = None

        page.pack_start(Gtk.Box(vexpand=True), True, True, 0)
        actions = ss.grid(3)
        self.pause_btn = ss.button(_("Pause"), css="ss-btn ss-btn-primary ss-btn-action")
        self.pause_btn.connect("clicked", self.toggle_pause)
        self.mid_btn = ss.button(_("Cancel object"), css="ss-btn ss-btn-card ss-btn-action")
        self.mid_btn.connect("clicked", self.middle_action)
        cancel = ss.button(_("Cancel print"), css="ss-btn ss-btn-outline-danger ss-btn-action")
        cancel.connect("clicked", self.ask_cancel)
        ss.grid_add(actions, [self.pause_btn, self.mid_btn, cancel])
        page.add(actions)
        self.job_file = None
        return page

    def pick_speed(self, widget, pct, macro):
        """Highlight the tapped preset immediately; it applies as soon as Klipper is free
        (e.g. after the start-of-print heat-up)."""
        self.speed_pending = pct
        for p, b in self.speed_btns.items():
            ss.set_class(b, "ss-chip-active", p == pct)
        ss.gcode(self._screen, macro)

    def build_tiles(self):
        adv = ss.advanced()
        if self.tiles_adv == adv:
            return
        self.tiles_adv = adv
        for child in self.tiles_box.get_children():
            self.tiles_box.remove(child)
        keys = ["nozzle", "bed", "fan", "flow"] + (["pa"] if adv else [])
        g = ss.grid(len(keys))
        self.tiles = {}
        for k in keys:
            name = {"nozzle": _("Nozzle"), "bed": _("Bed"), "fan": _("Fan"), "flow": _("Flow"), "pa": "PA"}[k]
            b = Gtk.Button(can_focus=False, hexpand=True)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, valign=Gtk.Align.CENTER)
            box.add(ss.label(name, "ss-btn-sub", xalign=0.5))
            val = ss.label("–", "ss-tile-value", xalign=0.5)
            sub = ss.label("", "ss-btn-sub", xalign=0.5)
            box.add(val)
            box.add(sub)
            b.add(box)
            b.get_style_context().add_class("ss-btn")
            b.get_style_context().add_class("ss-btn-card")
            b.get_style_context().add_class("ss-btn-tile")
            b.connect("clicked", self.open_tile, k)
            self.tiles[k] = (b, val, sub)
        ss.grid_add(g, [self.tiles[k][0] for k in keys])
        self.tiles_box.pack_start(g, True, True, 0)
        self.tiles_box.show_all()

    def open_tile(self, widget, key):
        p = self._printer
        if key in ("nozzle", "bed"):
            dev = "extruder" if key == "nozzle" else "heater_bed"
            cfg = p.get_config_section(dev) or {}
            mx = float(cfg.get("max_temp", 300 if key == "nozzle" else 110))
            idx = 0 if key == "nozzle" else 1
            presets = [(_("Off"), 0)] + [(m, t[idx]) for m, t in ss.MATERIALS.items()]
            cmd = "M104 S{}" if key == "nozzle" else "M140 S{}"
            ss.adjust(self._screen, ss_title=_("Nozzle target") if key == "nozzle" else _("Bed target"),
                      ss_value=p.get_stat(dev, "target") or 0, ss_min=0, ss_max=mx, ss_unit="°C",
                      ss_presets=presets, ss_apply=lambda v: ss.gcode(self._screen, cmd.format(int(v))))
        elif key == "fan":
            ss.adjust(self._screen, ss_title=_("Part fan"), ss_value=round((p.get_stat("fan", "speed") or 0) * 100),
                      ss_min=0, ss_max=100, ss_unit="%",
                      ss_presets=[(_("Off"), 0), ("50%", 50), ("80%", 80), ("100%", 100)],
                      ss_apply=lambda v: ss.gcode(self._screen, f"M106 S{int(round(v * 2.55))}"))
        elif key == "flow":
            flow = round((p.get_stat("gcode_move", "extrude_factor") or 1) * 100)
            ss.adjust(self._screen, ss_title=_("Flow"), ss_value=flow,
                      ss_min=40, ss_max=120, ss_unit="%", ss_steps=(-5, -1, 1, 5),
                      ss_apply=lambda v: ss.gcode(self._screen, f"SET_FLOW PERCENT={int(v)}"))
        elif key == "pa":
            pa = p.get_stat("extruder", "pressure_advance") or 0
            ss.adjust(self._screen, ss_title=_("Pressure advance"), ss_value=pa,
                      ss_min=0, ss_max=1, ss_steps=(-0.01, -0.001, 0.001, 0.01), ss_decimals=3,
                      ss_apply=lambda v: ss.gcode(self._screen, f"SET_PRESSURE_ADVANCE ADVANCE={v:.4f}"))

    def toggle_pause(self, widget):
        p = self._printer
        if p.state != "paused":
            self.resume_at = None
            self._screen._ws.klippy.print_pause()
            return
        if self.resume_at:                      # tapped again while reheating: stop waiting
            self.resume_at = None
            self.update_view()
            return
        # Nozzle cooled while paused (idle timeout / filament change)? Reheat first, then resume,
        # instead of Mainsail's RESUME aborting with "not hot enough".
        temp = 0
        try:
            res = self._screen.apiclient.send_request("printer/objects/query?gcode_macro%20RESUME")
            temp = float(res["status"]["gcode_macro RESUME"]["last_extruder_temp"].get("temp", 0) or 0)
        except Exception as e:
            logging.debug(f"StarStack: RESUME temp query failed: {e}")
        if temp > 0 and (p.get_stat("extruder", "temperature") or 0) < temp - 5:
            self.resume_at = temp
            ss.gcode(self._screen, f"M104 S{temp:.0f}")
            self.update_view()
        else:
            self._screen._ws.klippy.print_resume()

    def check_resume(self):
        p = self._printer
        if not self.resume_at:
            return
        if p.state != "paused":
            self.resume_at = None
        elif (p.get_stat("extruder", "temperature") or 0) >= self.resume_at - 3:
            self.resume_at = None
            self._screen._ws.klippy.print_resume()

    # ---- color changes (M600) in the current file
    def start_color_scan(self, fn):
        self.cc = {"changes": [], "m73": []}
        meta = self._files.get_file_info(fn) or {}
        gpath = self._files.gcodes_path
        if not gpath or not fn:
            return
        path = os.path.join(gpath, fn)
        start, end = meta.get("gcode_start_byte"), meta.get("gcode_end_byte")

        def work():
            result = ss.scan_color_changes(path, start, end)
            GLib.idle_add(self._color_scan_done, fn, result)
        threading.Thread(target=work, daemon=True).start()

    def _color_scan_done(self, fn, result):
        if fn == self.job_file:
            self.cc = result
            logging.info(f"StarStack: {len(result['changes'])} color change(s) in {fn}")
        return False

    def color_change_eta(self, fn, pos, dur):
        """Seconds until the next color change, or None if there isn't one."""
        nxt = next((o for o in self.cc["changes"] if o > pos), None)
        if nxt is None:
            return None
        m73 = self.cc["m73"]
        if m73:
            now = [r for o, r in m73 if o <= pos]
            at = [r for o, r in m73 if o <= nxt]
            if now and at:
                return max(0, now[-1] - at[-1]) * 60
        meta = self._files.get_file_info(fn) or {}
        start = meta.get("gcode_start_byte") or 0
        if pos > start and dur > 0:
            return dur / (pos - start) * (nxt - pos)
        return None

    def color_change_pause(self, pos):
        return any(0 <= pos - o < 400 for o in self.cc["changes"])

    def tick(self):
        self.phase = not self.phase
        if self.stack.get_visible_child_name() == "printing":
            self.refresh_printing()
        return True

    def runout(self):
        for s in self._printer.get_filament_sensors():
            if self._printer.get_stat(s, "enabled") and self._printer.get_stat(s, "filament_detected") is False:
                return True
        return False

    def middle_action(self, widget):
        if self._printer.state == "paused":
            pos = self._printer.get_stat("virtual_sdcard", "file_position") or 0
            mode = "change" if self.color_change_pause(pos) else "load"
            ss._push(self._screen, "ss_filament", ss_mode=mode)
        else:
            objects = self._printer.get_stat("exclude_object", "objects") or []
            if not objects:
                ss.info(self._screen, _("No objects to cancel"),
                        _("This file has no object labels. Turn on \"Label objects\" in OrcaSlicer."))
                return
            ss._push(self._screen, "ss_cancel_object")

    def ask_cancel(self, widget):
        name = ss.pretty_name(self._printer.get_stat("print_stats", "filename"))
        ss.confirm(self._screen, _("Cancel this print?"), f"{name} " + _("will stop and can't be resumed."),
                   _("Cancel print"), self._screen._ws.klippy.print_cancel, kind="danger", no_label=_("Keep printing"))

    def file_progress(self, fn):
        """Progress through the G-code body (like Mainsail): ignores the thumbnail/header bytes."""
        p = self._printer
        pos = p.get_stat("virtual_sdcard", "file_position") or 0
        meta = self._files.get_file_info(fn) or {}
        start, end = meta.get("gcode_start_byte"), meta.get("gcode_end_byte")
        if start is not None and end and end > start and pos:
            return max(0.0, min(1.0, (pos - start) / (end - start)))
        return p.get_stat("virtual_sdcard", "progress") or 0

    def refresh_printing(self):
        p = self._printer
        fn = p.get_stat("print_stats", "filename")
        if fn != self.job_file:
            self.job_file = fn
            for c in self.job_thumb_box.get_children():
                self.job_thumb_box.remove(c)
            t = self.thumb(fn, THUMB)
            t.set_size_request(THUMB, THUMB)
            self.job_thumb_box.add(t)
            self.job_thumb_box.show_all()
            self.job_name.set_text(ss.pretty_name(fn))
            self.start_color_scan(fn)
        self.build_tiles()
        self.check_resume()
        paused = p.state == "paused"
        pos = p.get_stat("virtual_sdcard", "file_position") or 0
        progress = self.file_progress(fn)
        dur = p.get_stat("print_stats", "print_duration") or p.get_stat("print_stats", "total_duration") or 0
        info = p.get_stat("print_stats", "info") or {}
        color_pause = paused and self.color_change_pause(pos)
        parts = []
        if self.resume_at:
            parts.append(_("Reheating to") + f" {self.resume_at:.0f}°, " + _("then resuming"))
        elif paused:
            parts.append(_("Color change") if color_pause else
                         _("Filament ran out") if self.runout() else _("Paused"))
        if info.get("total_layer"):
            parts.append(_("Layer") + f" {info.get('current_layer') or 0} / {info['total_layer']}")
        # Alternate every 4 s between "Color change in X" and "X left" when the file has color changes
        eta = None if paused else self.color_change_eta(fn, pos, dur)
        if eta is not None and self.phase:
            parts.append(_("Color change in") + " " + ss.fmt_duration(eta))
        elif progress > 0.02 and dur > 0:
            parts.append(ss.fmt_duration(dur / progress - dur) + " " + _("left"))
        self.job_line.set_text(" · ".join(parts))
        ss.set_class(self.job_line, "ss-text-sky", eta is not None and self.phase and not paused)
        self.progress.set_fraction(min(1.0, progress))
        self.job_pct.set_text(f"{int(progress * 100)}%")
        ss.set_class(self.job_pct, "ss-text-warning", paused)
        ss.set_class(self.progress, "ss-progress-paused", paused)
        sf = round((p.get_stat("gcode_move", "speed_factor") or 1) * 100)
        if self.speed_pending == sf:
            self.speed_pending = None             # Klipper has applied the tapped preset
        shown = self.speed_pending or sf
        for pct, b in self.speed_btns.items():
            ss.set_class(b, "ss-chip-active", pct == shown)
        resume_txt = _("Reheating…") if self.resume_at else _("Resume")
        ss.set_button_text(self.pause_btn, resume_txt if paused else _("Pause"))
        ss.set_button_text(self.mid_btn, (_("Change filament") if color_pause else _("Load filament"))
                           if paused else _("Cancel object"))
        if self.tiles:
            e_t, e_g = p.get_stat("extruder", "temperature") or 0, p.get_stat("extruder", "target") or 0
            b_t, b_g = p.get_stat("heater_bed", "temperature") or 0, p.get_stat("heater_bed", "target") or 0
            vals = {"nozzle": (f"{e_t:.0f}°", f"/ {e_g:.0f}°"), "bed": (f"{b_t:.0f}°", f"/ {b_g:.0f}°"),
                    "fan": (f"{(p.get_stat('fan', 'speed') or 0) * 100:.0f}%", _("part")),
                    "flow": (f"{(p.get_stat('gcode_move', 'extrude_factor') or 1) * 100:.0f}%", "40–120"),
                    "pa": (f"{p.get_stat('extruder', 'pressure_advance') or 0:.3f}", _("advanced"))}
            for k, (b, val, sub) in self.tiles.items():
                val.set_text(vals[k][0])
                sub.set_text(vals[k][1])
            ss.set_class(self.tiles["nozzle"][1], "ss-text-hot", e_g > 0)
            ss.set_class(self.tiles["bed"][1], "ss-text-hot", b_g > 0)

    # ------------------------------------------------------------ done
    def build_done(self):
        page = ss.page_box()
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, vexpand=True, valign=Gtk.Align.FILL)
        card.get_style_context().add_class("ss-card")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER, vexpand=True)
        self.done_icon = self._gtk.Image("complete", 44, 44)
        self.done_title = ss.label(_("Print complete"), "ss-done-title", xalign=0.5)
        self.done_name = ss.label("", "ss-muted", xalign=0.5, ellipsize=True)
        inner.add(self.done_icon)
        inner.add(self.done_title)
        inner.add(self.done_name)
        inner.add(ss.label(_("Wait for the bed to cool before removing the print."), "ss-btn-sub", xalign=0.5))
        card.add(inner)
        page.pack_start(card, True, True, 0)
        row = ss.grid(2, spacing=8)
        done = ss.button(_("Done"), css="ss-btn ss-btn-outline ss-btn-action")
        done.connect("clicked", self.dismiss)
        again = ss.button(_("Print again"), css="ss-btn ss-btn-primary ss-btn-action")
        again.connect("clicked", lambda w: ss.bed_clear_then_print(
            self._screen, self._printer.get_stat("print_stats", "filename")))
        ss.grid_add(row, [done, again])
        page.add(row)
        return page

    def done_key(self):
        ps = self._printer.get_stat("print_stats") or {}
        return f"{ps.get('filename')}|{ps.get('total_duration')}"

    def dismiss(self, *args):
        self.dismissed = self.done_key()
        self.recent_cache = (0, [])
        self.update_view()

    # ------------------------------------------------------------ common
    def update_view(self):
        p = self._printer
        if p is None:
            return
        state = p.get_stat("print_stats", "state")
        if ss.is_printing(p):
            self.stack.set_visible_child_name("printing")
            self.refresh_printing()
        elif (state in ("complete", "error") and p.get_stat("print_stats", "filename")
              and self.done_key() != self.dismissed):
            self.done_title.set_text(_("Print complete") if state == "complete" else _("Print failed"))
            self.done_name.set_text(f"{ss.pretty_name(p.get_stat('print_stats', 'filename'))} · "
                                    f"{ss.fmt_duration(p.get_stat('print_stats', 'print_duration'))}")
            self.stack.set_visible_child_name("done")
        else:
            if self.stack.get_visible_child_name() != "idle" or not self.recent_grid.get_children():
                self.refresh_idle()
            self.stack.set_visible_child_name("idle")

    def deactivate(self):
        if self.ticker:
            GLib.source_remove(self.ticker)
            self.ticker = None

    def activate(self):
        if self.ticker is None:
            self.ticker = GLib.timeout_add_seconds(4, self.tick)
        self.recent_cache = (0, []) if not ss.is_printing(self._printer) else self.recent_cache
        self.tiles_adv = None
        if self._printer and not ss.is_printing(self._printer):
            self.refresh_idle()
        self.update_view()

    def process_update(self, action, data):
        if action == "notify_status_update":
            self.update_view()
        elif action == "notify_metadata_update" and data.get("filename") == self.job_file:
            self.job_file = None          # rebuild the job card thumbnail now that metadata exists
            self.update_view()
        elif action == "notify_metadata_update" and self.stack.get_visible_child_name() == "idle":
            ss.debounce(self, "_meta_timer", 400, self.refresh_idle)
