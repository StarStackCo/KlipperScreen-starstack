# STARSTACK-ADDED: Screen & language page (FORK_CHANGES.md #39, klipper-ui D-067)
# Replaces the stock settings panel on the touchscreen. Pages with ‹ › arrows, no scrolling.
# Saves to KlipperScreen.conf like the stock panel, except "Confirm emergency stop", which is a
# StarStack setting (.starstack_ui.json, default ON) read by the STOP button (ss.ask_estop).
from ks_includes import starstack as ss
from ks_includes.config import SCREEN_BLANKING_OPTIONS
from ks_includes.screen_panel import ScreenPanel

LANG_NAMES = {
    "system_lang": "System default",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "nl": "Nederlands",
    "pl": "Polski",
    "pt": "Português",
    "pt_BR": "Português (Brasil)",
    "ru": "Русский",
    "uk": "Українська",
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "jp": "日本語",
    "ko": "한국어",
    "cs": "Čeština",
    "sv": "Svenska",
    "tr": "Türkçe",
    "hu": "Magyar",
}


def blank_name(value):
    if value == "off":
        return _("Never")
    secs = int(value)
    if secs >= 3600:
        h = secs // 3600
        return f"{h} " + ngettext("hour", "hours", h)
    m = secs // 60
    return f"{m} " + ngettext("minute", "minutes", m)


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        page, self.pager = ss.list_page(_("Screen & language"))
        self.content.add(page)
        self.content.show_all()
        self.build()

    def main(self, key, default):
        return self._config.get_main_config().get(key, default)

    def save(self, key, value):
        self._config.set("main", key, str(value))
        self._config.save_user_config_options()

    def build(self):
        blank = self.main("screen_blanking", "3600")
        blank_p = self.main("screen_blanking_printing", "3600")
        h24 = self._config.get_main_config().getboolean("24htime", True)
        lang = self.main("language", "system_lang")
        estop = ss.get_setting("confirm_estop", True)
        rows = [
            (ss.row(_("Screen sleep"), blank_name(blank), self.pick_blank), "row"),
            (
                ss.row(_("Screen sleep while printing"), blank_name(blank_p), self.pick_blank_p),
                "row",
            ),
            (ss.switch_row(_("24-hour clock"), "", h24, self.toggle_24h), "row"),
            (ss.row(_("Language"), LANG_NAMES.get(lang, lang), self.pick_lang), "row"),
            (
                ss.switch_row(
                    _("Confirm emergency stop"),
                    _("STOP asks first") if estop else _("STOP acts on one tap"),
                    estop,
                    self.toggle_estop,
                ),
                "tall",
            ),
        ]
        self.pager.set_rows(rows)

    # ---- screen sleep
    def blank_options(self):
        return [("off", _("Never"))] + [
            (str(n), blank_name(str(n))) for n in SCREEN_BLANKING_OPTIONS
        ]

    def pick_blank(self):
        def done(v):
            self.save("screen_blanking", v)
            self._screen.set_screenblanking_timeout(v)
            self.build()

        current = self.main("screen_blanking", "3600")
        ss.choose(self._screen, _("Screen sleep"), self.blank_options(), current, done)

    def pick_blank_p(self):
        def done(v):
            self.save("screen_blanking_printing", v)
            self._screen.set_screenblanking_printing_timeout(v)
            self.build()

        current = self.main("screen_blanking_printing", "3600")
        title = _("Screen sleep while printing")
        ss.choose(self._screen, title, self.blank_options(), current, done)

    # ---- clock, language, STOP
    def toggle_24h(self):
        h24 = self._config.get_main_config().getboolean("24htime", True)
        self.save("24htime", not h24)
        self.build()

    def pick_lang(self):
        langs = ["system_lang", *self._config.lang_list]
        options = [(code, LANG_NAMES.get(code, code)) for code in langs]

        def done(code):
            self._screen.change_language(None, code)  # reloads every page in the new language

        ss.choose(self._screen, _("Language"), options, self.main("language", "system_lang"), done)

    def toggle_estop(self):
        if not ss.get_setting("confirm_estop", True):
            ss.set_setting("confirm_estop", True)
            self.build()
            return

        def off():
            ss.set_setting("confirm_estop", False)
            self.build()

        ss.confirm(
            self._screen,
            _("Stop without asking?"),
            _("STOP will act on a single tap, with no confirmation.")
            + "\n"
            + _("An accidental tap stops the print and it can't be resumed."),
            _("Turn off confirmation"),
            off,
            kind="warning",
        )

    def activate(self):
        self.build()
