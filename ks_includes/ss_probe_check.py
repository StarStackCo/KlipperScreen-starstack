# STARSTACK-ADDED: probe check runner (FORK_CHANGES.md #59, klipper-ui D-NEW probe check)
# Runs klipper-ui's scripts/probe_check.py on the Pi: a full home, then Z homes from 10, 40 and
# near the top, each checked against the motor steps and a probe (B-24). The script talks
# to Moonraker itself; this starts it, waits off the GTK thread and hands its JSON result back.
# One run at a time; the setup self-check stops it when the check is stopped or left. Used by
# setup and by Settings > Advanced > Probe check.
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


def run(on_done):
    """on_done({"ok": bool, "reason": str}) on the GTK main thread, about 3 minutes later."""
    global _proc
    if running():
        GLib.idle_add(on_done, {"ok": False, "reason": _("A probe check is already running.")})
        return
    if not os.path.exists(SCRIPT):
        GLib.idle_add(on_done, {"ok": False, "reason": "probe_check.py missing: update klipper-ui"})
        return
    proc = _proc = subprocess.Popen(
        ["python3", SCRIPT, "--json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    def work():
        try:
            out, err = proc.communicate(timeout=900)
        except Exception as e:  # timeout: end it, never hang the page
            proc.kill()
            out, err = "", str(e)
        logging.info("probe check output:\n%s%s", out[-3000:], err[-1000:])
        GLib.idle_add(on_done, parse(out, err))

    threading.Thread(target=work, daemon=True).start()


def ask(screen):
    """Settings > Advanced > Probe check: confirm, run, then the result."""
    if ss.is_printing(screen.printer):
        screen.show_popup_message(_("Not while printing."), 2)
        return
    if running():
        screen.show_popup_message(_("A probe check is already running."), 2)
        return

    def go():
        # a short message, not a dialog: the result later must not close whatever is open then
        screen.show_popup_message(
            _("Probe check running, about 3 minutes. Watch the first touch reaches the bed."), 3
        )
        run(lambda r: done(screen, r))

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


def done(screen, r):
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
