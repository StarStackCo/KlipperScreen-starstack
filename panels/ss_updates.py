# STARSTACK-ADDED: Updates page (FORK_CHANGES.md #43, klipper-ui D-067)
# Replaces the stock updater panel: Moonraker's update manager in pages with ‹ › arrows.
# In Settings for everyone (user, 2026-10-08): one-tap items; Advanced mode adds the per-app list.
# Each update asks first and is locked while printing (an update restarts services).
# The board firmware row comes from klipper-ui's update helper (D-087), which keeps the board at
# the host's Klipper version after "Update everything". The same helper checks every update and
# undoes it if the printer doesn't come back healthy; "Undo last update" asks it to go back one
# update (klipper-ui D-092).
import json

from gi.repository import GLib

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
HEALTH = "/run/starstack/update-health"  # same helper: last update checked / undone
UNDO_REQUEST = "/run/starstack/undo-request"  # read by the helper


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def board_row():
    """(note, css) for the board firmware row, or None when the helper doesn't manage the board."""
    b = read_json(BOARD)
    if not b:
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
            else:
                rows.append((ss.label(_("Everything is up to date."), "ss-muted"), "text"))
            board = board_row()
            if board:
                rows.append((ss.row(_("Board firmware"), board[0], None, css_note=board[1]), "row"))
            rows += self.health_rows(busy)
            if not ss.advanced():  # the per-app list is for Advanced mode
                infos = {}
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

    def health_rows(self, busy):
        h = read_json(HEALTH) or {}
        rows = []
        css = {
            "checking": "ss-text-sky",
            "undoing": "ss-text-sky",
            "undone": "ss-text-warning",
        }.get(h.get("state"), "ss-muted")
        if h.get("message"):
            rows.append((ss.label(h["message"], css, wrap=True), "text"))
        if h.get("can_undo") and h.get("state") not in ("checking", "undoing"):
            rows.append(
                (
                    ss.row(
                        _("Undo last update"),
                        _("back to") + f" {h.get('undo_to', '')}",
                        self.ask_undo,
                        sensitive=not busy,
                    ),
                    "row",
                )
            )
        return rows

    def ask_undo(self):
        ss.confirm(
            self._screen,
            _("Undo the last update?"),
            _("Klipper, the touchscreen and the other StarStack parts go back to the versions")
            + " "
            + _("before the last update. Services restart; it takes a few minutes.")
            + "\n"
            + _("Don't switch the printer off until it's finished."),
            _("Undo update"),
            self.undo,
            kind="warning",
        )

    def undo(self):
        if ss.is_printing(self._printer):
            return
        try:
            with open(UNDO_REQUEST, "w") as f:
                f.write("undo\n")
        except OSError:
            self._screen.show_popup_message(_("The update helper isn't installed"), 2)
            return
        self._screen.show_popup_message(_("Undoing the last update…"), 1)

    def tick(self):
        self.build()  # the helper's board/health status changes on its own
        return True

    def deactivate(self):
        if getattr(self, "ticker", None):
            GLib.source_remove(self.ticker)
            self.ticker = None

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
        if not getattr(self, "ticker", None):
            self.ticker = GLib.timeout_add_seconds(5, self.tick)
