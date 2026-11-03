# STARSTACK-ADDED: Queue page (FORK_CHANGES.md #55, klipper-ui D-111)
# Opened from Home's "Next up" strip or the "Up next" card: reorder or remove queued jobs, and
# (printer free) start the next one once the plate is clear.
from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel
from ks_includes.ss_queue import QueueView


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page = ss.page_box(spacing=6)
        page.pack_start(ss.label(_("Queue"), "ss-page-title"), False, False, 0)
        mode = "busy" if ss.is_printing(self._printer) else "start"
        self.view = QueueView(self, mode=mode, on_close=self._screen._menu_go_back)
        page.pack_start(self.view.box, True, True, 0)
        self.content.add(page)
        self.content.show_all()

    def update(self):
        self.view.mode = "busy" if ss.is_printing(self._printer) else "start"
        self.view.refresh()

    def activate(self):
        self.view.mode = "busy" if ss.is_printing(self._printer) else "start"
        ss.queue_refresh(self._screen, self.update)

    def process_update(self, action, data):
        if action == "notify_job_queue_changed":
            ss.queue_refresh(self._screen, self.update)
        elif action == "notify_status_update" and "print_stats" in data:
            if ss.is_printing(self._printer) and self.view.mode == "start":
                # the next job just started (here or from Mainsail): watch it on Home
                self._screen.show_panel("ss_home", remove_all=True)
            elif not ss.is_printing(self._printer) and self.view.mode == "busy":
                self.update()
