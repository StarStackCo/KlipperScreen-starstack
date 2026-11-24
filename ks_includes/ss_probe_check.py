# STARSTACK-ADDED: probe check runner (FORK_CHANGES.md #59, klipper-ui D-141)
# Runs klipper-ui's scripts/probe_check.py on the Pi in two parts: a full home and homes from
# Z 10 and 40, then (only after the user saw the first touch reach the bed) the home from near
# the top, each checked against the motor steps and a probe (B-24). The script talks to Moonraker
# itself; this starts it, waits off the GTK thread and hands its JSON result back. One run at a
# time; the setup self-check stops it when the check is stopped or left. Used by setup and by
# Settings > Advanced > Probe check.
import json
import logging
import os
import subprocess
import threading

from gi.repository import GLib

from ks_includes import starstack as ss

SCRIPT = os.path.expanduser("~/klipper-ui/scripts/probe_check.py")
# What to fix after a failed check (user, klipper-ui D-141); translated when shown
FAIL_TITLE = "Homing check failed"
FIX = (
    "1. Turn the printer off and unplug it.\n"
    "2. Check the heatsink and nozzle screws are tight and no plastic is on the nozzle.\n"
    "3. Check the toolhead cable has slack with the head at the front left and Z down.\n"
    "4. Check nothing is stuck to the bed at the back left.\n"
    "5. Plug it in, turn it on and run the self-check again."
)
_proc = None  # the running script, so a second run is refused and Stop can end it


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


def running():
    return _proc is not None and _proc.poll() is None


def stop():
    """End the script: it sends no more G-code (a move already sent still finishes)."""
    if running():
        _proc.terminate()


def run(on_done, part):
    """part 1: full home, homes from Z 10 and 40. part 2, only after the user saw the first touch
    reach the bed: the home from near the top (a false first zero would put the head that much
    higher, klipper-ui D-141). on_done({"ok", "reason"}) on the GTK thread 1 to 2 minutes later."""
    global _proc
    if running():
        GLib.idle_add(on_done, {"ok": False, "reason": _("A probe check is already running.")})
        return
    if not os.path.exists(SCRIPT):
        GLib.idle_add(on_done, {"ok": False, "reason": "probe_check.py missing: update klipper-ui"})
        return
    proc = _proc = subprocess.Popen(
        ["python3", SCRIPT, "--json", f"--part{part}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def work():
        try:
            out, err = proc.communicate(timeout=900)
        except Exception as e:  # timeout: end it, never hang the page
            proc.kill()
            out, err = "", str(e)
        logging.info("probe check part %s output:\n%s%s", part, out[-3000:], err[-1000:])
        GLib.idle_add(on_done, parse(out, err))

    threading.Thread(target=work, daemon=True).start()


def ask(screen):
    """Settings > Advanced > Probe check: confirm, part 1, the first-touch question, part 2."""
    if ss.is_printing(screen.printer):
        screen.show_popup_message(_("Not while printing."), 2)
        return
    if running():
        screen.show_popup_message(_("A probe check is already running."), 2)
        return

    def go():
        # a short message, not a dialog: the result later must not close whatever is open then
        screen.show_popup_message(
            _("Probe check running. Watch the first time the nozzle comes down."), 3
        )
        run(lambda r: after_part1(screen, r), 1)

    ss.confirm(
        screen,
        _("Run the probe check?"),
        _(
            "The nozzle heats to 150°C and the printer homes, then Z homes again from higher and "
            "higher, up near the top, at the back left. Keep your hands clear. To stop it, use "
            "STOP on the left."
        ),
        _("Run"),
        go,
    )


def after_part1(screen, r):
    if not r["ok"]:
        fail(screen, r["reason"])
        return
    ss.confirm(
        screen,
        _("Did the nozzle touch the bed the first time it came down?"),
        r["reason"] + "\n\n" + _("If yes, Z rises near the top and homes once more."),
        _("Yes, it touched"),
        lambda: part2(screen),
        no_label=_("Stop"),
        alt_label=_("No"),
        on_alt=lambda: fail(screen, _("The first touch didn't reach the bed.")),
    )


def part2(screen):
    screen.show_popup_message(_("Last step: Z rises near the top and homes once more."), 3)
    run(lambda r: done(screen, r), 2)


def done(screen, r):
    if not r["ok"]:
        fail(screen, r["reason"])
        return
    ss.info(screen, "✓ " + _("Probe check passed"), r["reason"])


def fail(screen, reason):
    ss.info(screen, "⚠ " + _(FAIL_TITLE), reason + "\n\n" + _(FIX))
