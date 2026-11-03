# STARSTACK-ADDED: touch and display guard (FORK_CHANGES.md #51, klipper-ui D-094)
#
# Ghost touches: the S1's resistive panel (TSC2007) sometimes reports a touch nobody made, from
# electrical noise on the screen cable. Logged on the S1 (2026-10-08): ghosts are a single reading,
# press to release in ~24 ms; real taps last 75-150 ms (4-6 readings). Every press is held back for
# up to HOLD_MS; if it is released sooner (by the event timestamps) the press and the release are
# both dropped, otherwise everything is passed on in order, unchanged.
#
# Color bands: the same noise can corrupt pixels on the way to the display (fbtft over SPI). fbtft
# only resends the parts of the screen that change, so a band stays until that area is redrawn.
# A full repaint every REPAINT_S seconds clears it (about 0.3 s of the 12 MHz SPI link each time;
# measured +1% CPU at one repaint a second).
import logging

from gi.repository import Gdk, GLib, Gtk

# Shorter press-to-release is noise. 40 ms (ghosts ~24 ms) still let ghosts open the pressure
# advance page overnight (2026-11-03), so 70 ms at the user's choice. Logged real taps were
# 54-150 ms, so a very quick tap may need a slightly longer press.
MIN_TOUCH_MS = 70
HOLD_MS = 80  # wall-clock wait before a held press is passed on anyway
REPAINT_S = 5

PRESS = (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.TOUCH_BEGIN)
RELEASE = (Gdk.EventType.BUTTON_RELEASE, Gdk.EventType.TOUCH_END, Gdk.EventType.TOUCH_CANCEL)
FOLLOW = (
    Gdk.EventType.MOTION_NOTIFY,
    Gdk.EventType.TOUCH_UPDATE,
    Gdk.EventType._2BUTTON_PRESS,
    Gdk.EventType._3BUTTON_PRESS,
)


class ScreenGuard:
    def __init__(self, window):
        self.window = window
        self.held = []  # the press being checked plus anything after it, as copies
        self.timer = None
        self.ghosts = 0
        self.pressed_at = None  # event time of the last press passed on, for log_touch
        Gdk.event_handler_set(self.on_event, None)
        GLib.timeout_add_seconds(REPAINT_S, self.repaint)

    def on_event(self, event, *_args):
        kind = event.get_event_type()
        if self.held:
            if kind in RELEASE:
                ms = event.get_time() - self.held[0].get_time()
                if ms < MIN_TOUCH_MS:
                    self.ghosts += 1
                    logging.info(f"StarStack: ignored a ghost touch, {ms} ms (#{self.ghosts})")
                    self.drop()
                    return
                self.flush()
            elif kind in FOLLOW:
                self.held.append(event.copy())
                return
            else:
                self.flush()
        elif kind in PRESS:
            self.held = [event.copy()]
            self.timer = GLib.timeout_add(HOLD_MS, self.held_long_enough)
            return
        if kind in RELEASE:
            self.log_touch(event)
        Gtk.main_do_event(event)

    def log_touch(self, event):
        """A touch that was passed on: how long and where, so a ghost that still gets through can
        be told from a real tap in the log (klipper-ui D-094)."""
        if self.pressed_at is None:
            return
        ms = event.get_time() - self.pressed_at
        ok, x, y = event.get_coords()
        logging.info(f"StarStack: touch {ms} ms" + (f" at {x:.0f},{y:.0f}" if ok else ""))
        self.pressed_at = None

    def held_long_enough(self):
        self.timer = None  # this timeout ends here (returns False)
        return self.flush()

    def drop(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        self.held = []

    def flush(self):
        held, self.held = self.held, []
        if held:
            self.pressed_at = held[0].get_time()
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        for e in held:
            Gtk.main_do_event(e)
        return False

    def repaint(self):
        if self.window.get_visible():
            self.window.queue_draw()
        return True
