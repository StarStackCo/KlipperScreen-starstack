# STARSTACK-ADDED: Console with the command box at the TOP (FORK_CHANGES.md #35)
# The stock console puts its entry at the bottom edge, which is hard to tap. Here the entry and Send
# sit at the top; tapping the entry opens the on-screen keyboard below and the output shrinks.
import re
import time
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

COLORS = {
    "command": "#88D8F2",
    "error": "#FF6467",
    "response": "#FAFAFA",
    "warning": "#FF8904",
    "time": "#A1A1A1",
}


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page = ss.page_box(spacing=6)

        row = Gtk.Box(spacing=8)
        self.entry = Gtk.Entry(hexpand=True, vexpand=False)
        self.entry.set_placeholder_text(_("Type a G-code command, e.g. G28"))
        self.entry.get_style_context().add_class("ss-console-entry")
        self.entry.connect("button-press-event", self._screen.show_keyboard)
        self.entry.connect("touch-event", self._screen.show_keyboard)
        self.entry.connect("activate", self.send)
        send = ss.button(_("Send"), css="ss-btn ss-btn-primary ss-btn-mid")
        send.set_hexpand(False)
        send.set_size_request(84, -1)
        send.connect("clicked", self.send)
        clear = ss.button(_("Clear"), css="ss-btn ss-btn-outline ss-btn-mid")
        clear.set_hexpand(False)
        clear.set_size_request(70, -1)
        clear.connect("clicked", lambda w: self.buffer.set_text(""))
        row.pack_start(self.entry, True, True, 0)
        row.pack_start(send, False, False, 0)
        row.pack_start(clear, False, False, 0)
        page.pack_start(row, False, False, 0)

        self.buffer = Gtk.TextBuffer()
        view = Gtk.TextView(
            buffer=self.buffer,
            editable=False,
            cursor_visible=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
        )
        view.get_style_context().add_class("ss-console-output")
        self.scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(view)
        view.connect("size-allocate", self._to_bottom)
        page.pack_start(self.scroll, True, True, 0)
        self.content.add(page)
        self.content.show_all()

    def _to_bottom(self, *args):
        adj = self.scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def add(self, kind, when, message):
        if kind != "command" and re.match(r"^(?:ok\s+)?(B|C|T\d*):", message):
            return  # temperature reports
        color = COLORS["command"] if kind == "command" else COLORS["response"]
        if message.startswith("!!"):
            color, message = COLORS["error"], message[3:]
        elif message.startswith("//"):
            color, message = COLORS["warning"], message[3:]
        message = GLib.markup_escape_text(message)
        stamp = datetime.fromtimestamp(when).strftime("%H:%M:%S")
        self.buffer.insert_markup(
            self.buffer.get_end_iter(),
            f'\n<span color="{COLORS["time"]}">{stamp}</span> '
            f'<span color="{color}">{message}</span>',
            -1,
        )
        if self.buffer.get_line_count() > 500:
            self.buffer.delete(self.buffer.get_iter_at_line(0), self.buffer.get_iter_at_line(1))

    def send(self, *args):
        cmd = self.entry.get_text().strip()
        if not cmd:
            return
        self.entry.set_text("")
        self._screen.remove_keyboard()
        self.add("command", time.time(), cmd)
        self._screen._ws.api.gcode_script(cmd)

    def _history(self, result, method, params):
        for r in result.get("result", {}).get("gcode_store", []):
            self.add(r["type"], r["time"], r["message"])

    def activate(self):
        self.buffer.set_text("")
        self._screen._ws.send_method("server.gcode_store", {"count": 60}, self._history)

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            self.add("response", time.time(), data)
