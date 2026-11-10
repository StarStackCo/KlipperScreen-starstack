# STARSTACK-ADDED: first power-up setup (FORK_CHANGES.md #56, klipper-ui D-114, D-NEW setup)
# Welcome, time zone and clock, Wi-Fi, self-check, tour, filament, first print; every step can be
# skipped. Opens by itself once on a new printer (starstack.offer_setup) and from Settings.
# Design: claude.ai canvas "First power-up and factory reset". The rail keeps its normal buttons
# and STOP; the step number shows above each page instead of the canvas's step rail.
import logging
import os
import subprocess
import time
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

ZONES = [
    ("America/New_York", "Eastern"),
    ("America/Chicago", "Central"),
    ("America/Denver", "Mountain"),
    ("America/Los_Angeles", "Pacific"),
    ("America/Anchorage", "Alaska"),
    ("Pacific/Honolulu", "Hawaii"),
]
OTHER_ZONES = [
    ("America/Phoenix", "Arizona"),
    ("America/Puerto_Rico", "Puerto Rico"),
    ("America/Toronto", "Toronto"),
    ("America/Vancouver", "Vancouver"),
    ("America/Mexico_City", "Mexico City"),
    ("America/Sao_Paulo", "São Paulo"),
    ("Europe/London", "London"),
    ("Europe/Dublin", "Dublin"),
    ("Europe/Paris", "Paris"),
    ("Europe/Berlin", "Berlin"),
    ("Europe/Madrid", "Madrid"),
    ("Europe/Rome", "Rome"),
    ("Europe/Athens", "Athens"),
    ("Asia/Dubai", "Dubai"),
    ("Asia/Kolkata", "India"),
    ("Asia/Singapore", "Singapore"),
    ("Asia/Shanghai", "China"),
    ("Asia/Tokyo", "Tokyo"),
    ("Asia/Seoul", "Seoul"),
    ("Australia/Perth", "Perth"),
    ("Australia/Sydney", "Sydney"),
    ("Pacific/Auckland", "Auckland"),
    ("UTC", "UTC"),
]
STEP_NO = {"time": 1, "wifi": 2, "check": 3, "tour": 4, "filament": 4, "print": 4}
STEP_NAME = {"time": "Time", "wifi": "Wi-Fi", "check": "Self-check", "filament": "Filament"}

# Self-check (klipper-ui D-114): automatic plus questions, about 5 minutes
CHECKS = [
    ("sensors", "Temperature sensors"),
    ("tap", "Nozzle tap (probe)"),
    ("nozzle", "Nozzle heater"),
    ("bed", "Bed heater"),
    ("fans", "Part fan"),
    ("home", "Homing and probing the bed"),
]
PROBE_TEMP = 150  # NOZZLE_CLEAN clean_temp: G28 probes Z at this temperature anyway (B-19)
NOZZLE_TIMEOUT = 180  # s to reach PROBE_TEMP - 3
BED_TEST = 40  # °C target; passes once 5°C warmer than at the start
BED_RISE = 5
BED_TIMEOUT = 90
TAP_SAFE = 45  # °C: above this the page says wait instead of asking for a tap
# what failed, and what to check (translated when shown)
FAILS = {
    "sensors": (
        "A temperature sensor reads wrong",
        "Turn the printer off, then check that the sensor cables at the nozzle and the bed are "
        "plugged in all the way.",
    ),
    "tap": (
        "The probe didn't react",
        "Tap the nozzle tip a little firmer, straight up. If it still doesn't react, turn the "
        "printer off and check the cable to the toolhead.",
    ),
    "nozzle": (
        "Nozzle heater didn't warm up",
        "Turn the printer off, then check the heater cable at the toolhead is plugged in all "
        "the way.",
    ),
    "bed": (
        "Bed heater didn't warm up",
        "Turn the printer off, then check that the bed's heater cable is plugged in all the "
        "way and hasn't been pinched.",
    ),
    "fans": (
        "The part fan isn't spinning",
        "Turn the printer off, then check nothing is stuck in the fan and its cable is plugged in.",
    ),
    "home": (
        "Homing didn't finish",
        "Check nothing blocks the nozzle or the bed, and that no plastic is stuck to the "
        "nozzle tip. The printer's console has Klipper's message.",
    ),
}
# 5 tour pages: title, then (heading, text) cards (translated when shown)
TOUR = [
    (
        "Sending a print",
        [
            (
                "From OrcaSlicer",
                "Slice with the StarStack S1 profile and click Upload and print. If the "
                "printer is busy, the file joins the queue.",
            ),
            (
                "From a USB stick",
                "Plug it in. New files are copied over and the screen asks if you want to "
                "print one.",
            ),
        ],
    ),
    (
        "Home",
        [
            (
                "Your newest file",
                "Home shows it with a big Print button, and your last prints under Print again.",
            ),
            ("While it prints", "Time left, finish time, speed, Pause and Cancel are on Home."),
        ],
    ),
    (
        "The rail on the left",
        [
            (
                "Home, Print, Controls, Settings",
                "Print lists every file. Controls has temperatures, fan, filament and moving "
                "the axes.",
            ),
            (
                "STOP",
                "Stops heaters, motors and the print at once. The print can't be resumed, so "
                "use it only if something is wrong.",
            ),
        ],
    ),
    (
        "Filament",
        [
            (
                "Load, unload, change",
                "Home and Controls have the filament buttons. The printer heats the nozzle, "
                "then tells you what to do.",
            ),
            (
                "Material",
                "The printer remembers what's loaded and warns you if a file was sliced for "
                "another material.",
            ),
        ],
    ),
    (
        "Settings",
        [
            ("Wi-Fi, updates, screen", "Wi-Fi, one-tap updates, screen sleep and the clock."),
            ("Run this again", "Settings › Setup and tour runs this setup again."),
        ],
    ),
]


def current_zone():
    try:
        with open("/etc/timezone") as f:
            return f.read().strip()
    except OSError:
        path = os.path.realpath("/etc/localtime")
        return path.split("zoneinfo/", 1)[1] if "zoneinfo/" in path else ""


def zone_now(zone, h24):
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(zone))
    except Exception:
        return ""
    return now.strftime("%H:%M") if h24 else now.strftime("%I:%M %p").lstrip("0")


class Panel(ScreenPanel):
    def __init__(self, screen, title, ss_step="welcome", **kwargs):
        super().__init__(screen, title)
        self.skipped = []  # step names the user skipped, listed on the last page
        self.results = {}  # self-check: name -> (state, note); state ok | fail | skip
        self.timer = None
        self.away = None  # "filament" / "wifi": a page opened from here, act on return
        self.tour_page = 0
        self.checking = False  # self-check heaters or moves are running
        self.live = {}  # self-check: name -> live note (temperature while heating)
        self.page = ss.page_box(spacing=6)
        self.content.add(self.page)
        self.show(ss_step)

    # ------------------------------------------------------------ page plumbing
    def clear(self):
        self.stop_timer()
        for child in self.page.get_children():
            self.page.remove(child)

    def show(self, step):
        self.step = step
        self.clear()
        getattr(self, "page_" + step)()
        self.page.show_all()

    def head(self, title, step=None):
        if step in STEP_NO:
            self.page.add(
                ss.label(
                    _("Setup") + f" · {STEP_NO[step]} / 4 · " + _(STEP_NAME.get(step, "Tour")),
                    "ss-muted",
                )
            )
        self.page.add(ss.label(title, "ss-page-title", wrap=True))

    def text(self, body, css="ss-dialog-body"):
        lbl = ss.label(body, css, wrap=True)
        self.page.add(lbl)
        return lbl

    def actions(self, buttons):
        """buttons: [(text, callback, kind)] with kind outline | primary. Pinned to the bottom."""
        self.page.pack_start(Gtk.Box(vexpand=True), True, True, 0)
        row = Gtk.Box(spacing=8, homogeneous=True)
        for text, cb, kind in buttons:
            b = ss.button(text, css=f"ss-btn ss-btn-{kind} ss-btn-action")
            b.connect("clicked", lambda w, c=cb: c())
            row.add(b)
        self.page.add(row)

    def skip(self, step, nxt):
        if step not in self.skipped:
            self.skipped.append(step)
        self.show(nxt)

    def go(self, step, nxt):
        if step in self.skipped:
            self.skipped.remove(step)
        self.show(nxt)

    def stop_timer(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None

    def every(self, ms, fn):
        self.stop_timer()

        def run():
            if fn() is False:
                self.timer = None
                return False
            return True

        self.timer = GLib.timeout_add(ms, run)

    # ------------------------------------------------------------ 1 welcome
    def page_welcome(self):
        self.page.add(ss.label("STARSTACK S1", "ss-section ss-text-sky"))
        self.page.add(
            ss.label(_("Welcome. Let's get your printer ready."), "ss-done-title", wrap=True)
        )
        self.text(
            _(
                "About 15 minutes, then your first print. You can skip any step and come back to "
                "it in Settings."
            )
        )
        self.actions(
            [
                (_("Start"), lambda: self.show("time"), "primary"),
            ]
        )

    # ------------------------------------------------------------ 2 time zone and clock
    def page_time(self):
        self.head(_("Where is this printer?"), "time")
        h24 = self._config.get_main_config().getboolean("24htime", True)
        zone = current_zone()
        grid = ss.grid(2, spacing=6)
        btns = []
        for tz, name in ZONES:
            b = ss.button(name, zone_now(tz, h24), css="ss-btn ss-btn-card")
            ss.set_class(b, "ss-card-hl", tz == zone)
            b.connect("clicked", lambda w, z=tz: self.set_zone(z))
            btns.append(b)
        ss.grid_add(grid, btns)
        self.page.add(grid)
        other = dict(OTHER_ZONES).get(zone)
        row = Gtk.Box(spacing=6, homogeneous=True)
        for text, on, cb in (
            (other or _("Other zone"), bool(other), self.pick_other),
            (_("12-hour"), not h24, lambda: self.set_24h(False)),
            (_("24-hour"), h24, lambda: self.set_24h(True)),
        ):
            b = ss.button(text, css="ss-btn " + ("ss-btn-primary" if on else "ss-btn-outline"))
            b.connect("clicked", lambda w, c=cb: c())
            row.add(b)
        self.page.add(row)
        self.actions(
            [
                (_("Back"), lambda: self.show("welcome"), "outline"),
                (_("Skip"), lambda: self.skip("time", "wifi"), "outline"),
                (_("Next"), lambda: self.go("time", "wifi"), "primary"),
            ]
        )

    def pick_other(self):
        ss.choose(self._screen, _("Time zone"), OTHER_ZONES, current_zone(), self.set_zone)

    def set_zone(self, zone):
        # needs install.sh's polkit rule (klipper-ui D-NEW first power-up); without it timedatectl
        # asks for a password, which a touchscreen can't give
        try:
            r = subprocess.run(
                ["timedatectl", "--no-ask-password", "set-timezone", zone],
                capture_output=True,
                text=True,
                timeout=10,
            )
            ok = r.returncode == 0
            if not ok:
                logging.error(f"StarStack setup: set-timezone {zone}: {r.stderr.strip()}")
        except (OSError, subprocess.SubprocessError) as e:
            logging.error(f"StarStack setup: set-timezone {zone}: {e}")
            ok = False
        if ok:
            time.tzset()  # this app's clock follows at once
        else:
            self._screen.show_popup_message(_("Couldn't change the time zone"), 2)
        if self.step == "time":
            self.show("time")

    def set_24h(self, on):
        self._config.set("main", "24htime", str(on))
        self._config.save_user_config_options()
        self.show("time")

    # ------------------------------------------------------------ 3 Wi-Fi
    def page_wifi(self):
        self.head(_("Connect to Wi-Fi"), "wifi")
        self.text(
            _(
                "Needed to send prints from your computer and get updates. You can plug in an "
                "Ethernet cable instead, or skip this and print from a USB stick."
            )
        )
        self.net_lbl = self.text("", "ss-row-title ss-text-sky")
        ss.request(self._screen, "machine.system_info", {}, self._got_net)
        b = ss.button(_("Choose a Wi-Fi network"), css="ss-btn ss-btn-card ss-btn-action")
        b.connect("clicked", self.open_wifi)
        self.page.add(b)
        self.actions(
            [
                (_("Back"), lambda: self.show("time"), "outline"),
                (_("Skip, no Wi-Fi"), lambda: self.skip("wifi", "check"), "outline"),
                (_("Next"), lambda: self.go("wifi", "check"), "primary"),
            ]
        )

    def _got_net(self, result):
        if self.step != "wifi":
            return
        nets = ((result or {}).get("system_info") or {}).get("network") or {}
        ips = [
            a.get("address")
            for iface, info in nets.items()
            if iface != "lo"
            for a in info.get("ip_addresses", [])
            if a.get("family") == "ipv4" and not a.get("is_link_local")
        ]
        self.net_lbl.set_text(_("Connected") + f" · {ips[0]}" if ips else _("Not connected yet"))

    def open_wifi(self, *args):
        self.away = "wifi"
        ss._push(self._screen, "ss_network", title=_("Wi-Fi"), ss_done=True)

    # ------------------------------------------------------------ 4 self-check
    def page_check(self):
        self.head(_("Self-check"), "check")
        self.text(
            _(
                "The printer tests itself in about 5 minutes. It will ask you a couple of "
                "questions, so stay close."
            )
        )
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.get_style_context().add_class("ss-card")
        card.add(ss.section(_("Before you start")))
        for item in (
            _("Remove packing material and tape"),
            _("Nothing on the bed"),
            _("Keep hands clear once it moves: the nozzle gets hot"),
        ):
            card.add(ss.label("✓  " + item, "ss-row-title", wrap=True))
        self.page.add(card)
        self.actions(
            [
                (_("Back"), lambda: self.show("wifi"), "outline"),
                (_("Skip"), lambda: self.skip("check", "tour"), "outline"),
                (_("Start check"), self.start_check, "primary"),
            ]
        )

    def temp(self, heater):
        return self._printer.get_stat(heater, "temperature") or 0

    def start_check(self):
        self.results = {}
        t = [round(self.temp("extruder")), round(self.temp("heater_bed"))]
        ok = all(5 <= x <= 300 for x in t)  # unplugged reads far below room temperature
        self.results["sensors"] = ("ok" if ok else "fail", f"{t[0]}°C, {t[1]}°C")
        self.next_check()

    def next_check(self):
        """Run the first check without a result, or show a failure, or the results page."""
        failed = [n for n, _l in CHECKS if self.results.get(n, ("",))[0] == "fail"]
        if failed:
            self.show_fail(failed[0])
            return
        todo = next((n for n, _l in CHECKS if n not in self.results), None)
        if todo is None:
            self.end_check()
            self.show("check_done")
        elif todo == "tap":
            self.show("check_tap")
        elif todo in ("nozzle", "bed"):
            self.start_heat()
        elif todo == "fans":
            ss.gcode(self._screen, "M106 S255")
            self.show("check_fan")
        elif todo == "home":
            self.start_home()

    def end_check(self):
        self.checking = False
        ss.gcode(self._screen, "TURN_OFF_HEATERS\nM107")

    # ---- tap the nozzle (the probe) before anything moves or heats (user, D-114)
    def page_check_tap(self):
        self.page.add(ss.label(_("Self-check · Bed probe"), "ss-muted"))
        self.page.add(ss.label(_("Tap the nozzle"), "ss-done-title"))
        self.text(
            _(
                "The nozzle is also the bed probe. Give its tip a light tap with your finger, to "
                "prove the probe works before anything moves."
            )
        )
        self.tap_temp = self.text("", "ss-row-title ss-text-sky")
        self.tap_state = self.text(_("Waiting for your tap…"), "ss-row-title ss-text-warning")
        self.actions(
            [
                (_("Skip this check"), lambda: self.check_result("tap", "skip", ""), "outline"),
                (
                    _("Nothing happened"),
                    lambda: self.check_result("tap", "fail", _("No tap seen")),
                    "outline",
                ),
            ]
        )
        self.tap_busy = False
        self.every(250, self.poll_tap)

    def poll_tap(self):
        t = round(self.temp("extruder"))
        if t > TAP_SAFE:
            self.tap_temp.set_text(
                _("Still warm: {}°C. Wait until it's below {}°C.").format(t, TAP_SAFE)
            )
            return True
        self.tap_temp.set_text(_("It's not hot: {}°C, safe to touch.").format(t))
        if not self.tap_busy:
            # Z homes on the probe (probe:z_virtual_endstop), so its endstop state is the probe's.
            # Moonraker's endstop query prints nothing to the console, unlike QUERY_PROBE.
            self.tap_busy = True
            ss.request(self._screen, "printer.query_endstops.status", {}, self._got_endstops)
        return True

    def _got_endstops(self, result):
        self.tap_busy = False
        if self.step == "check_tap" and (result or {}).get("z") == "TRIGGERED":
            self.check_result("tap", "ok", _("You tapped it"))

    def check_result(self, name, state, note):
        self.results[name] = (state, note)
        self.next_check()

    # ---- heaters, part fan, homing: the running list
    def page_check_run(self):
        head = Gtk.Box(spacing=8)
        head.pack_start(ss.label(_("Self-check"), "ss-page-title"), True, True, 0)
        done = sum(1 for n, _l in CHECKS if n in self.results)
        head.pack_end(ss.label(f"{done} / {len(CHECKS)}", "ss-muted", xalign=1.0), False, False, 0)
        self.page.add(head)
        bar = Gtk.ProgressBar()
        bar.get_style_context().add_class("ss-progress")
        bar.set_fraction(done / len(CHECKS))
        self.page.add(bar)
        self.run_rows = {}
        for name, title in CHECKS:
            row = Gtk.Box(spacing=8)
            row.pack_start(ss.label(title, "ss-row-title", ellipsize=True), True, True, 0)
            note = ss.label("", "ss-muted", xalign=1.0)
            row.pack_end(note, False, False, 0)
            self.page.add(row)
            self.run_rows[name] = note
        self.refresh_rows()
        self.actions([(_("Stop the check"), self.stop_check, "outline")])

    def refresh_rows(self):
        marks = {"ok": "✓ ", "skip": _("skipped") + " ", "fail": "✗ "}
        for name, note in self.run_rows.items():
            state, text = self.results.get(name, ("", ""))
            if state:
                note.set_text(marks[state] + text)
                ss.set_class(note, "ss-text-sky", state == "ok")
            elif name in self.live:
                note.set_text(self.live[name])
                ss.set_class(note, "ss-text-warning", True)

    def start_heat(self):
        self.checking = True
        self.live = {}
        self.heat_from = time.monotonic()
        self.bed_start = self.temp("heater_bed")
        cmds = []
        if "nozzle" not in self.results:
            cmds.append(f"M104 S{PROBE_TEMP}")
        if "bed" not in self.results:
            cmds.append(f"M140 S{BED_TEST}")
        ss.gcode(self._screen, "\n".join(cmds))
        self.show("check_run")
        self.every(1000, self.tick_heat)

    def tick_heat(self):
        took = time.monotonic() - self.heat_from
        if "nozzle" not in self.results:
            t = self.temp("extruder")
            self.live["nozzle"] = f"{t:.0f}°C " + _("of") + f" {PROBE_TEMP}°C"
            if t >= PROBE_TEMP - 3:
                self.results["nozzle"] = ("ok", _("Reached {}°C").format(PROBE_TEMP))
            elif took > NOZZLE_TIMEOUT:
                ss.gcode(self._screen, "M104 S0")
                self.results["nozzle"] = (
                    "fail",
                    _("{:.0f}°C after {} minutes").format(t, NOZZLE_TIMEOUT // 60),
                )
        if "bed" not in self.results:
            t = self.temp("heater_bed")
            self.live["bed"] = f"{t:.0f}°C " + _("of") + f" {BED_TEST}°C"
            if t >= self.bed_start + BED_RISE:
                ss.gcode(self._screen, "M140 S0")  # it heats: no need to wait for 40°C
                self.results["bed"] = ("ok", _("Warmed to {:.0f}°C").format(t))
            elif took > BED_TIMEOUT:
                ss.gcode(self._screen, "M140 S0")
                self.results["bed"] = (
                    "fail",
                    _("Stayed at {:.0f}°C for {} seconds").format(t, BED_TIMEOUT),
                )
        self.refresh_rows()
        if "nozzle" in self.results and "bed" in self.results:
            self.timer = None
            self.next_check()
            return False
        return True

    def page_check_fan(self):
        self.page.add(ss.label(_("Self-check · Fans"), "ss-muted"))
        self.page.add(ss.label(_("Is the part fan spinning?"), "ss-done-title", wrap=True))
        self.text(
            _(
                "Look at the fan beside the nozzle. It should be running now and blowing air at "
                "the nozzle tip."
            )
        )
        self.actions(
            [
                (_("No"), lambda: self.fan_answer(False), "outline"),
                (_("Yes, it's spinning"), lambda: self.fan_answer(True), "primary"),
            ]
        )

    def fan_answer(self, yes):
        ss.gcode(self._screen, "M107")
        self.check_result(
            "fans", "ok" if yes else "fail", _("You confirmed") if yes else _("You said no")
        )

    def start_home(self):
        self.checking = True
        self.live = {"home": _("running")}
        self.show("check_run")

        def done(result):
            if not self.checking:  # stopped meanwhile
                return
            self.results["home"] = ("ok", "") if result is not None else ("fail", "")
            self.next_check()

        # G28 heats the nozzle to clean_temp before probing Z (_PROBE_HOT, B-19); it is already
        # there from the heater check, so this is quick. The reply comes when homing has finished.
        ss.request(self._screen, "printer.gcode.script", {"script": "G28"}, done)

    def stop_check(self):
        self.end_check()
        self.show("check")

    def show_fail(self, name):
        self.end_check()
        self.failed = name
        self.show("check_fail")

    def page_check_fail(self):
        title, what = (_(x) for x in FAILS[self.failed])
        self.page.add(ss.label("⚠  " + title, "ss-dialog-title ss-text-error", wrap=True))
        self.text(self.results[self.failed][1])
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.get_style_context().add_class("ss-card")
        card.add(ss.section(_("What to check")))
        card.add(ss.label(what, "ss-row-title", wrap=True))
        self.page.add(card)
        self.actions(
            [
                (_("Skip this check"), self.skip_failed, "outline"),
                (_("Try again"), self.retry_failed, "primary"),
            ]
        )

    def skip_failed(self):
        self.results[self.failed] = ("skip", "")
        self.next_check()

    def retry_failed(self):
        if self.failed == "sensors":
            self.start_check()
            return
        del self.results[self.failed]
        self.next_check()

    def page_check_done(self):
        bad = [n for n, _l in CHECKS if self.results.get(n, ("",))[0] != "ok"]
        self.page.add(
            ss.label(
                ("✓  " + _("Everything checks out"))
                if not bad
                else _("Done, {} skipped").format(len(bad)),
                "ss-page-title",
            )
        )
        for name, title in CHECKS:
            state, note = self.results.get(name, ("skip", ""))
            row = Gtk.Box(spacing=8)
            row.pack_start(ss.label(title, "ss-row-title", ellipsize=True), True, True, 0)
            text = {"ok": note or _("OK"), "skip": _("skipped")}.get(state, note)
            row.pack_end(ss.label(text, "ss-muted", xalign=1.0), False, False, 0)
            self.page.add(row)
        self.actions(
            [
                (_("Run it again"), self.start_check, "outline"),
                (_("Next"), lambda: self.go("check", "tour"), "primary"),
            ]
        )
        if bad and "check" not in self.skipped:
            self.skipped.append("check")
        elif not bad and "check" in self.skipped:
            self.skipped.remove("check")

    # ------------------------------------------------------------ 5 tour
    def page_tour(self):
        title, tips = _(TOUR[self.tour_page][0]), TOUR[self.tour_page][1]
        head = Gtk.Box(spacing=8)
        head.pack_start(
            ss.label(_("Quick tour") + f" · {self.tour_page + 1} / {len(TOUR)}", "ss-muted"),
            True,
            True,
            0,
        )
        dots = Gtk.Box(spacing=5, valign=Gtk.Align.CENTER)
        for i in range(len(TOUR)):
            d = Gtk.Box()
            d.set_size_request(8, 8)
            d.get_style_context().add_class("ss-dot-on" if i == self.tour_page else "ss-dot")
            dots.add(d)
        head.pack_end(dots, False, False, 0)
        self.page.add(head)
        self.page.add(ss.label(title, "ss-page-title"))
        for tip, body in tips:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.get_style_context().add_class("ss-card")
            card.add(ss.label(_(tip), "ss-row-title", wrap=True))
            card.add(ss.label(_(body), "ss-dialog-body", wrap=True))
            self.page.add(card)
        last = self.tour_page == len(TOUR) - 1
        self.actions(
            [
                (_("Back"), lambda: self.tour_turn(-1), "outline"),
                (_("End tour"), lambda: self.tour_end(), "outline"),
                (_("Next"), lambda: self.tour_turn(1), "primary"),
            ]
            if not last
            else [
                (_("Back"), lambda: self.tour_turn(-1), "outline"),
                (_("Next"), lambda: self.tour_end(), "primary"),
            ]
        )

    def tour_turn(self, d):
        if self.tour_page + d < 0:
            self.show("check")
            return
        self.tour_page += d
        self.show("tour")

    def tour_end(self):
        self.tour_page = 0
        self.show("filament")

    # ------------------------------------------------------------ 6 filament
    def page_filament(self):
        self.head(_("Load filament"), "filament")
        self.text(
            _(
                "Load the material you'll print with. PLA is the easiest for a first print. The "
                "printer heats the nozzle and tells you what to do."
            )
        )
        self.fil_lbl = self.text("", "ss-row-title ss-text-sky")
        ss.query_loaded_material(self._screen, self._got_loaded)
        load = ss.button(_("Load filament"), css="ss-btn ss-btn-primary ss-btn-action")
        load.connect("clicked", self.open_filament)
        self.page.add(load)
        self.actions(
            [
                (_("Back"), lambda: self.show("tour"), "outline"),
                (_("Skip"), lambda: self.skip("filament", "print"), "outline"),
                (_("Already loaded"), lambda: self.go("filament", "print"), "outline"),
            ]
        )

    def _got_loaded(self, material):
        if self.step == "filament":
            self.fil_lbl.set_text(_("Loaded now: {}").format(material) if material else "")

    def open_filament(self, *args):
        self.away = "filament"
        ss._push(self._screen, "ss_filament", ss_mode="load")

    # ------------------------------------------------------------ 7 first print
    def page_print(self):
        self.head(_("Your first print"), "print")
        starters = ss.starter_files(self._files)
        self.first = starters[0] if starters else None
        if self.first:
            meta = self._files.get_file_info(self.first) or {}
            mat = (meta.get("filament_type", "") or "").split(";")[0]
            sub = " · ".join(x for x in (mat, ss.fmt_duration(meta.get("estimated_time"))) if x)
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.get_style_context().add_class("ss-card")
            card.get_style_context().add_class("ss-card-hl")
            card.add(ss.label(ss.pretty_name(self.first), "ss-card-title", ellipsize=True))
            card.add(ss.label(sub, "ss-muted"))
            card.add(ss.label(_("A quick check that everything prints well."), "ss-muted"))
            self.page.add(card)
            for item in (
                _("Bed is clear"),
                _("Thin layer of glue on the plate, so the print sticks"),
            ):
                self.page.add(ss.label("✓  " + item, "ss-row-title", wrap=True))
            self.actions(
                [
                    (_("Skip for now"), lambda: self.skip("print", "finished"), "outline"),
                    (_("Ready, print it"), self.print_first, "primary"),
                ]
            )
        else:
            self.text(
                _(
                    "There's no test print on this printer yet. Send one from OrcaSlicer or "
                    "plug in a USB stick."
                )
            )
            self.actions([(_("Next"), lambda: self.skip("print", "finished"), "primary")])

    def print_first(self):
        fn = self.first
        self.finish()
        ss.bed_clear_then_print(self._screen, fn)  # filament check and "Print <name>?" (D-126)

    # ------------------------------------------------------------ 8 finished
    def page_finished(self):
        self.page.add(ss.label(_("You're all set"), "ss-done-title"))
        names = [_(STEP_NAME.get(s, "First print")) for s in self.skipped]
        self.text(
            _("Your printer is ready.")
            + (" " + _("You skipped: {}.").format(", ".join(names)) if names else "")
        )
        self.text(_("Settings › Setup and tour runs any of these again."))
        buttons = [(_("Go to Home"), self.finish, "primary")]
        if "wifi" in self.skipped:
            buttons.insert(0, (_("Set up Wi-Fi"), lambda: self.show("wifi"), "outline"))
        self.actions(buttons)

    def finish(self):
        if self.checking:
            self.end_check()
        ss.set_setting("setup_done", True)
        self._screen.show_panel("ss_home", remove_all=True)

    # ------------------------------------------------------------ KlipperScreen hooks
    def activate(self):
        away, self.away = self.away, None
        if away == "wifi" and self.step == "wifi":
            self.show("wifi")  # show the new connection
        elif away == "filament" and self.step == "filament":
            # loaded: on to the first print; canceled: stay here
            ss.query_loaded_material(
                self._screen, lambda m: self.go("filament", "print") if m else self.show("filament")
            )

    def deactivate(self):
        if self.checking and not self.away:  # left the self-check by the rail: heaters off
            self.end_check()
            self.stop_timer()
            self.step = "check"
            self.show("check")
