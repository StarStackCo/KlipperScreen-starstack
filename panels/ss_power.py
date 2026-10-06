# STARSTACK-ADDED: Shut down / reboot page (FORK_CHANGES.md #41, klipper-ui D-067)
# Replaces the stock shutdown panel. Every action asks first; all are locked while printing.
from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page, self.pager = ss.list_page(_("Shut down / reboot"))
        self.content.add(page)
        self.content.show_all()
        self.build()

    def build(self):
        busy = ss.is_printing(self._printer)
        note = _("locked while printing") if busy else ""
        ws = self._screen._ws
        actions = [
            (
                _("Shut down the printer"),
                _("Shut down?"),
                _("The Pi shuts down safely.")
                + " "
                + _("Wait until the screen goes dark, then switch off the power."),
                _("Shut down"),
                lambda: ws.send_method("machine.shutdown"),
            ),
            (
                _("Reboot the printer"),
                _("Reboot?"),
                _("The Pi restarts. The printer is ready again in about a minute."),
                _("Reboot"),
                lambda: ws.send_method("machine.reboot"),
            ),
            (
                _("Restart Klipper"),
                _("Restart Klipper?"),
                _("Reloads the printer configuration. Takes about 10 seconds."),
                _("Restart"),
                ws.api.restart,
            ),
            (
                _("Restart the touchscreen"),
                _("Restart the touchscreen?"),
                _("Only the screen restarts. The printer keeps running."),
                _("Restart"),
                self._screen.restart_ks,
            ),
        ]
        rows = []
        for name, title, body, yes, action in actions:
            rows.append(
                (
                    ss.row(
                        name,
                        note,
                        lambda t=title, b=body, y=yes, a=action: ss.confirm(
                            self._screen, t, b, y, a, kind="warning"
                        ),
                        sensitive=not busy,
                    ),
                    "row",
                )
            )
        self.pager.set_rows(rows)

    def activate(self):
        self.build()
