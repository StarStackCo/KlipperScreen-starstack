# STARSTACK-ADDED: Klipper macro prompts (action:prompt_*) shown inside the content area
# instead of a full-screen dialog, so STOP stays reachable (FORK_CHANGES.md #9, #18).
# Opened by the STARSTACK-CHANGE #9 hook in ks_includes/widgets/prompts.py.
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel
from ks_includes import starstack as ss


class Panel(ScreenPanel):
    def __init__(self, screen, title, ss_prompt=None, **kwargs):
        super().__init__(screen, title)
        self.prompt = ss_prompt
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
        card.get_style_context().add_class("ss-dialog")
        head = Gtk.Box(spacing=8)
        head.pack_start(ss.label((ss_prompt.header or "").strip() or _("Printer message"), "ss-dialog-title", wrap=True),
                        True, True, 0)
        close = ss.button("×", css="ss-btn ss-btn-outline ss-btn-close")
        close.set_hexpand(False)
        close.connect("clicked", lambda w: ss_prompt.close())
        head.pack_end(close, False, False, 0)
        card.add(head)
        if ss_prompt.text:
            card.add(ss.label(ss_prompt.text, "ss-dialog-body", wrap=True))
        # Macro-defined buttons (built by the stock Prompt class)
        box = ss_prompt.scroll_box
        if box.get_parent():
            box.get_parent().remove(box)
        scroll = self._gtk.ScrolledWindow(steppers=False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add(box)
        if box.get_children():            # macro-defined buttons
            card.pack_start(scroll, True, True, 0)
        else:
            card.pack_start(Gtk.Box(vexpand=True), True, True, 0)
        if ss_prompt.buttons:
            row = ss.grid(len(ss_prompt.buttons), spacing=8)
            btns = []
            for spec in ss_prompt.buttons:
                css = "ss-btn ss-btn-danger ss-btn-lg" if "error" in spec["style"] else "ss-btn ss-btn-primary ss-btn-lg"
                b = ss.button(spec["name"], css=css)
                b.connect("clicked", lambda w, g=spec["gcode"]: ss.gcode(self._screen, g))
                btns.append(b)
            ss.grid_add(row, btns)
            card.add(row)
        page = ss.page_box()
        page.pack_start(card, True, True, 0)
        self.content.add(page)
        self.content.show_all()

    def back(self):
        self.prompt.close()
        return True
