# STARSTACK-ADDED: generic "pick one" page (FORK_CHANGES.md #38)
# Opened with ks_includes.starstack.choose(): screen sleep, language, font size, step sizes, ...
# One row per option in pages with ‹ › arrows (no scrolling, D-064); the current one is marked.
from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(
        self,
        screen,
        title,
        ss_title="",
        ss_options=None,
        ss_current=None,
        ss_on_pick=None,
        **kwargs,
    ):
        super().__init__(screen, title)
        self.on_pick = ss_on_pick
        page, pager = ss.list_page(ss_title)
        rows = []
        for value, text in ss_options or []:
            mark = "✓ " + _("current") if str(value) == str(ss_current) else ""
            rows.append(
                (ss.row(text, mark, lambda v=value: self.pick(v), css_note="ss-text-sky"), "row")
            )
        pager.set_rows(rows)
        if ss_current is not None:
            values = [str(v) for v, _t in ss_options or []]
            if str(ss_current) in values:
                pager.show_row(values.index(str(ss_current)))
        self.content.add(page)
        self.content.show_all()

    def pick(self, value):
        cb = self.on_pick
        ss.close_dialog(self._screen)
        if cb:
            cb(value)
