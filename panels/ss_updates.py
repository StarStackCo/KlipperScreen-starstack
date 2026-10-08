# STARSTACK-ADDED: Updates page (FORK_CHANGES.md #43, klipper-ui D-067)
# Replaces the stock updater panel: Moonraker's update manager in pages with ‹ › arrows.
# Each update asks first and is locked while printing (an update restarts services).
# The board firmware row comes from klipper-ui's update helper (D-087), which keeps the board at
# the host's Klipper version after "Update everything".
import json

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel

NAMES = {
    "klipper": "Klipper",
    "moonraker": "Moonraker",
    "mainsail": "Mainsail",
    "KlipperScreen": "Touchscreen",
    "klipper-ui": "StarStack macros + theme",
    "system": "System packages",
    "crowsnest": "Camera (crowsnest)",
    "mainsail-config": "Mainsail macros",
    "sonar": "Wi-Fi keepalive (sonar)",
}
BOARD = "/run/starstack/board-firmware"  # written by klipper-ui's update helper


def board_row():
    """(note, css) for the board firmware row, or None when the helper doesn't manage the board."""
    try:
        with open(BOARD) as f:
            b = json.load(f)
    except (OSError, ValueError):
        return None
    state = b.get("state")
    if state == "ok":
        return _("matches Klipper") + f" · {b.get('mcu', '')}", "ss-muted"
    if state == "updating":
        return _("updating…"), "ss-text-sky"
    if state == "failed":
        return _("update failed: see Mainsail"), "ss-text-error"
    return None


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.status = None
        self.error = None
        page, self.pager = ss.list_page(_("Updates"))
        self.content.add(page)
        self.content.show_all()
        self.build()

    @staticmethod
    def pending(info):
        if "package_count" in info:
            return info["package_count"] > 0
        return info.get("version") != info.get("remote_version") and info.get("remote_version")

    def note(self, name, info):
        if name == "system":
            n = info.get("package_count", 0)
            return (f"{n} " + _("to update"), True) if n else (_("up to date"), False)
        if not info.get("is_valid", True) or info.get("is_dirty"):
            return (_("needs repair (use Mainsail)"), False)
        if self.pending(info):
            return (f"{info.get('version')} → {info.get('remote_version')}", True)
        return (_("up to date") + f" · {info.get('version', '')}", False)

    def build(self):
        busy = ss.is_printing(self._printer)
        rows = [(ss.row(_("Check for updates"), "", self.refresh, sensitive=not busy), "row")]
        if self.error:
            rows.append((ss.label(self.error, "ss-text-error", wrap=True), "text"))
        if self.status is None and not self.error:
            rows.append((ss.label(_("Checking…"), "ss-muted"), "text"))
        if self.status:
            infos = self.status.get("version_info", {})
            todo = [n for n, i in infos.items() if self.pending(i)]
            if todo:
                rows.append(
                    (
                        ss.row(
                            _("Update everything"),
                            f"{len(todo)} " + _("updates"),
                            lambda: self.ask("full"),
                            sensitive=not busy,
                            css_note="ss-text-sky",
                        ),
                        "row",
                    )
                )
            board = board_row()
            if board:
                rows.append((ss.row(_("Board firmware"), board[0], None, css_note=board[1]), "row"))
            for name in sorted(infos, key=lambda n: NAMES.get(n, n).lower()):
                text, avail = self.note(name, infos[name])
                rows.append(
                    (
                        ss.row(
                            NAMES.get(name, name),
                            text,
                            (lambda n=name: self.ask(n)) if avail else None,
                            sensitive=not busy or not avail,
                            css_note="ss-text-sky" if avail else "ss-muted",
                        ),
                        "row",
                    )
                )
        if busy:
            rows.append((ss.label(_("Updates are locked while printing."), "ss-muted"), "text"))
        self.pager.set_rows(rows)

    def _got_status(self, response, *args):
        if isinstance(response, dict) and "result" in response:
            self.status, self.error = response["result"], None
        else:
            msg = (
                (response or {}).get("error", {}).get("message")
                if isinstance(response, dict)
                else None
            )
            self.error = "Moonraker: " + (msg or _("update manager not available"))
        self.build()
        return False

    def refresh(self):
        self.status, self.error = None, None
        self.build()
        self._screen._ws.send_method("machine.update.refresh", {}, self._got_status)

    def ask(self, name):
        what = _("everything") if name == "full" else NAMES.get(name, name)
        ss.confirm(
            self._screen,
            _("Update") + f" {what}?",
            _("Services restart during the update and the touchscreen may restart too.")
            + "\n"
            + _("Don't switch the printer off until it's finished."),
            _("Update"),
            lambda: self.update(name),
            kind="warning",
        )

    def update(self, name):
        if ss.is_printing(self._printer):
            return
        if name in ("klipper", "moonraker", "system", "full"):
            self._screen._ws.send_method(f"machine.update.{name}")
        else:
            self._screen._ws.send_method("machine.update.client", {"name": name})
        self._screen.show_popup_message(_("Updating") + f" {NAMES.get(name, name)}…", 1)

    def activate(self):
        self._screen._ws.send_method("machine.update.status", {}, self._got_status)
