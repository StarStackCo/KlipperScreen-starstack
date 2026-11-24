# STARSTACK-ADDED: probe check runner (FORK_CHANGES.md #59, klipper-ui D-NEW probe check)
# Runs klipper-ui's scripts/probe_check.py on the Pi: Z homes at the homing point from 5 to 40 mm,
# each checked against the motor steps and a probe (B-24). The script talks to Moonraker itself;
# this starts it off the GTK thread and hands its JSON result back. Used by the setup self-check
# and by Settings > Advanced > Probe check.
import json
import logging
import os
import subprocess
import threading

from gi.repository import GLib

from ks_includes import starstack as ss

SCRIPT = os.path.expanduser("~/klipper-ui/scripts/probe_check.py")
# What to fix after a failed check (user, klipper-ui D-NEW probe check); translated when shown
FAIL_TITLE = "Homing check failed"
FIX = (
    "1. Turn the printer off and unplug it.\n"
    "2. Check the heatsink and nozzle screws are tight and no plastic is on the nozzle.\n"
    "3. Check the toolhead cable has slack with the head at the front left and Z down.\n"
    "4. Check nothing is stuck to the bed at the back right.\n"
    "5. Plug it in, turn it on and run the self-check again."
)


def parse(stdout, stderr=""):
    """The script's last JSON line → {"ok", "reason"}; anything else is a failure."""
    for line in reversed(stdout.splitlines()):
        if line.startswith("{"):
            try:
                r = json.loads(line)
                return {"ok": bool(r.get("ok")), "reason": str(r.get("reason", ""))}
            except ValueError:
                break
    last = (stderr.strip().splitlines() or ["no result from probe_check.py"])[-1]
    return {"ok": False, "reason": last}


def run(on_done):
    """on_done({"ok": bool, "reason": str}) on the GTK main thread, about 3 minutes later."""

    def work():
        if not os.path.exists(SCRIPT):
            result = {"ok": False, "reason": "probe_check.py missing: update klipper-ui"}
        else:
            try:
                p = subprocess.run(
                    ["python3", SCRIPT, "--json"], capture_output=True, text=True, timeout=900
                )
                logging.info("probe check output:\n%s%s", p.stdout[-3000:], p.stderr[-1000:])
                result = parse(p.stdout, p.stderr)
            except Exception as e:  # timeout or no python3: report it, never hang the page
                logging.exception("probe check")
                result = {"ok": False, "reason": str(e)}
        GLib.idle_add(on_done, result)

    threading.Thread(target=work, daemon=True).start()


def ask(screen):
    """Settings > Advanced > Probe check: confirm, run, then the result."""
    if ss.is_printing(screen.printer):
        screen.show_popup_message(_("Not while printing."), 2)
        return

    def go():
        ss.info(
            screen,
            _("Probe check running"),
            _("About 3 minutes. Watch the first time the nozzle comes down: it must touch the bed.")
            + "\n"
            + _("To stop, use STOP on the left."),
        )
        run(lambda r: done(screen, r))

    ss.confirm(
        screen,
        _("Run the probe check?"),
        _(
            "The nozzle heats to 150°C, then Z homes 5 times at the back right, from higher each "
            "time. Keep your hands clear."
        ),
        _("Run"),
        go,
    )


def done(screen, r):
    ss.close_dialog(screen)
    if not r["ok"]:
        fail(screen, r["reason"])
        return
    # the script can't see the first home: only the user knows it touched the bed
    ss.confirm(
        screen,
        "✓ " + _("Probe check passed"),
        r["reason"] + "\n\n" + _("Did the nozzle touch the bed the first time it came down?"),
        _("No"),
        lambda: fail(screen, _("The first touch didn't reach the bed.")),
        kind="warning",
        no_label=_("Yes, it touched"),
    )


def fail(screen, reason):
    ss.info(screen, "⚠ " + _(FAIL_TITLE), reason + "\n\n" + _(FIX))
