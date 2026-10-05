# STARSTACK-ADDED: Wi-Fi page (FORK_CHANGES.md #36, klipper-ui B-6 / D-063)
# One big row per network (strongest access point per name): tap to connect, type the password with
# the StarStack keyboard, Disconnect/Forget in our dialog. Uses upstream's NetworkManager backend
# (ks_includes/sdbus_nm.py) unchanged. Enterprise (802.1x) Wi-Fi and interface choice stay on the
# stock page: "All network settings" at the end of the list.
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


def signal_icon(level):
    # NetworkManager reports strength in percent (same thresholds as the stock page)
    if level > 75:
        return "wifi_excellent"
    if level > 60:
        return "wifi_good"
    if level > 30:
        return "wifi_fair"
    return "wifi_weak"


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.nm = None
        self.timer = None
        self.shown = None  # what the list currently shows, to rebuild only on changes
        self.pw_ssid = None
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
        self.content.add(self.stack)
        try:
            from ks_includes.sdbus_nm import SdbusNm

            self.nm = SdbusNm(self.popup)
        except Exception as e:
            logging.exception("StarStack: NetworkManager not available")
            self.stack.add_named(self.build_error(e), "error")
            self.content.show_all()
            return
        self.stack.add_named(self.build_list(), "list")
        self.stack.add_named(self.build_password(), "password")
        self.content.show_all()
        self.stack.set_visible_child_name("list")

    def popup(self, msg, level=3):
        self._screen.show_popup_message(msg, level)

    # ------------------------------------------------------------------ pages
    def build_error(self, error):
        page = ss.page_box(spacing=10)
        page.add(ss.label(_("Wi-Fi"), "ss-page-title"))
        page.add(
            ss.label(
                _("Network settings are not available on this printer.")
                + "\n"
                + _("NetworkManager is missing or not allowed."),
                "ss-dialog-body",
                wrap=True,
            )
        )
        page.add(ss.label(str(error), "ss-muted", wrap=True))
        return page

    def build_list(self):
        page = ss.page_box(spacing=6)
        head = Gtk.Box(spacing=8)
        head.pack_start(ss.label(_("Wi-Fi"), "ss-page-title"), True, True, 0)
        self.refresh_btn = ss.button(image="refresh", gtk=self._gtk, img_size=22)
        self.refresh_btn.get_style_context().add_class("ss-btn-mid")
        self.refresh_btn.set_hexpand(False)
        self.refresh_btn.set_size_request(56, 44)
        self.refresh_btn.connect("clicked", self.rescan)
        head.pack_end(self.refresh_btn, False, False, 0)
        # On/off pill, same look as Settings › Advanced mode
        self.switch = Gtk.Button(can_focus=False)
        self.switch.get_style_context().add_class("ss-btn")
        self.switch.set_size_request(72, 44)
        self.track = Gtk.Box(valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        self.track.set_size_request(56, 28)
        self.switch_text = ss.label("", "ss-switch-text", xalign=0.5)
        self.switch_text.set_halign(Gtk.Align.CENTER)
        self.track.set_center_widget(self.switch_text)
        self.switch.add(self.track)
        self.switch.connect("clicked", self.toggle_wifi)
        head.pack_end(self.switch, False, False, 0)
        page.pack_start(head, False, False, 0)
        self.status = ss.label("", "ss-muted", wrap=True)
        page.pack_start(self.status, False, False, 0)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.list)
        page.pack_start(scroll, True, True, 0)
        return page

    def build_password(self):
        # Fits above the on-screen keyboard: title row, then entry + Show + Connect in one row
        page = ss.page_box(spacing=6)
        head = Gtk.Box(spacing=8)
        self.pw_title = ss.label("", "ss-row-title", ellipsize=True)
        head.pack_start(self.pw_title, True, True, 0)
        cancel = ss.button(_("Cancel"), css="ss-btn ss-btn-outline ss-btn-mid")
        cancel.set_hexpand(False)
        cancel.set_size_request(84, 40)
        cancel.connect("clicked", self.close_password)
        head.pack_end(cancel, False, False, 0)
        page.pack_start(head, False, False, 0)
        row = Gtk.Box(spacing=8)
        self.pw_entry = Gtk.Entry(hexpand=True, visibility=False)
        self.pw_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.pw_entry.set_placeholder_text(_("Password"))
        self.pw_entry.get_style_context().add_class("ss-console-entry")
        self.pw_entry.connect("button-press-event", self._screen.show_keyboard)
        self.pw_entry.connect("touch-event", self._screen.show_keyboard)
        self.pw_entry.connect("activate", self.join)
        self.pw_show = ss.button(_("Show"), css="ss-btn ss-btn-outline ss-btn-mid")
        self.pw_show.set_hexpand(False)
        self.pw_show.set_size_request(70, -1)
        self.pw_show.connect("clicked", self.toggle_visible)
        join = ss.button(_("Connect"), css="ss-btn ss-btn-primary ss-btn-mid")
        join.set_hexpand(False)
        join.set_size_request(96, -1)
        join.connect("clicked", self.join)
        row.pack_start(self.pw_entry, True, True, 0)
        row.pack_start(self.pw_show, False, False, 0)
        row.pack_start(join, False, False, 0)
        page.pack_start(row, False, False, 0)
        self.pw_error = ss.label("", "ss-text-error", wrap=True)
        page.pack_start(self.pw_error, False, False, 0)
        return page

    # ------------------------------------------------------------------ state
    def networks(self):
        """One entry per network name, strongest access point first."""
        best = {}
        for net in self.nm.get_networks():
            if net.get("BSSID") and net["SSID"] not in best:
                best[net["SSID"]] = net  # get_networks() is sorted by signal, strongest first
        return list(best.values())

    def connected_ssid(self):
        bssid = self.nm.get_connected_bssid()
        if bssid is None:
            return None
        return next((n["SSID"] for n in self.nm.get_networks() if n.get("BSSID") == bssid), None)

    def wired_text(self):
        for dev in self.nm.get_all_network_devices():
            iface = dev["interface"]
            if iface == getattr(self.nm.wlan_device, "interface", None) or iface == "lo":
                continue
            ip = self.nm.get_ip_for_interface(iface)
            if ip:
                return _("Cable connected") + f" · {ip}"
        return ""

    def refresh(self):
        if self.nm is None or self.stack.get_visible_child_name() != "list":
            return True
        wired = self.wired_text()
        if not self.nm.wifi:
            self.switch.hide()
            self.refresh_btn.hide()
            self.status.set_text(
                _("This printer has no Wi-Fi adapter.") + ("\n" + wired if wired else "")
            )
            self.fill([], None, False)
            return True
        on = self.nm.is_wifi_enabled()
        ss.set_class(self.track, "ss-switch-on", on)
        ss.set_class(self.track, "ss-switch-off", not on)
        self.switch_text.set_text(_("ON") if on else _("OFF"))
        self.refresh_btn.set_visible(on)
        if not on:
            self.status.set_text(_("Wi-Fi is off.") + (" " + wired if wired else ""))
            self.fill([], None, False)
            return True
        current = self.connected_ssid()
        iface = self.nm.wlan_device.interface
        if current:
            text = _("Connected to") + f" {current} · {self.nm.get_ip_for_interface(iface)}"
        else:
            text = _("Not connected to Wi-Fi.")
        self.status.set_text(text + (" " + wired if wired else ""))
        self.fill(self.networks(), current, True)
        return True

    def fill(self, nets, current, on):
        key = (
            on,
            current,
            tuple((n["SSID"], n["known"], signal_icon(n["signal_level"])) for n in nets),
        )
        if key == self.shown:
            return
        self.shown = key
        for c in self.list.get_children():
            self.list.remove(c)
        if on and not nets:
            self.list.add(ss.label(_("Looking for networks…"), "ss-muted"))
        for net in sorted(nets, key=lambda n: n["SSID"] != current):  # connected one on top
            self.list.add(self.row(net, net["SSID"] == current))
        self.list.add(ss.label(_("OTHER"), "ss-section"))
        more = self.plain_row(_("All network settings"), _("enterprise Wi-Fi, interfaces"))
        more.connect("clicked", lambda w: self._screen.show_panel("network", _("Network")))
        self.list.add(more)
        self.list.show_all()

    def plain_row(self, name, note):
        b = Gtk.Button(can_focus=False, hexpand=True)
        box = Gtk.Box(spacing=8)
        box.pack_start(ss.label(name, "ss-row-title"), True, True, 0)
        box.pack_end(ss.label(note, "ss-muted", xalign=1.0), False, False, 0)
        b.add(box)
        b.get_style_context().add_class("ss-btn")
        b.get_style_context().add_class("ss-row")
        return b

    def row(self, net, connected):
        b = Gtk.Button(can_focus=False, hexpand=True)
        box = Gtk.Box(spacing=10)
        box.pack_start(self._gtk.Image(signal_icon(net["signal_level"]), 24, 24), False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, valign=Gtk.Align.CENTER)
        txt.add(ss.label(net["SSID"], "ss-row-title", ellipsize=True))
        secured = self.secured(net)
        if connected:
            sub, css = _("Connected"), "ss-btn-sub ss-text-sky"
        elif net["known"]:
            sub, css = _("Saved"), "ss-btn-sub"
        else:
            sub, css = (_("Secured") if secured else _("Open")), "ss-btn-sub"
        txt.add(ss.label(sub, css))
        box.pack_start(txt, True, True, 0)
        if secured:
            box.pack_end(self._gtk.Image("lock", 18, 18), False, False, 0)
        b.add(box)
        b.get_style_context().add_class("ss-btn")
        b.get_style_context().add_class("ss-row")
        b.get_style_context().add_class("ss-row-tall")
        b.connect("clicked", self.tapped, net["SSID"], connected)
        return b

    @staticmethod
    def secured(net):
        sec = net.get("security") or ""
        return bool(sec) and sec != "Open" and "OWE" not in sec

    # ------------------------------------------------------------------ actions
    def tapped(self, widget, ssid, connected):
        net = next((n for n in self.networks() if n["SSID"] == ssid), None)
        if connected:
            ss.confirm(
                self._screen,
                ssid,
                _("Connected.")
                + " "
                + _("Disconnecting may cut off Mainsail on other devices.")
                + " "
                + _("Only if this is the printer's only network."),
                _("Disconnect"),
                self.disconnect,
                no_label=_("Go back"),
                alt_label=_("Forget"),
                on_alt=lambda: self.ask_forget(ssid),
            )
        elif self.nm.is_known(ssid):
            ss.confirm(
                self._screen,
                ssid,
                _("Saved network. Connect to it now?"),
                _("Connect"),
                lambda: self.connect(ssid),
                alt_label=_("Forget"),
                on_alt=lambda: self.ask_forget(ssid),
            )
        elif net and "802.1x" in (net.get("security") or ""):
            ss.confirm(
                self._screen,
                ssid,
                _("This network needs a username and password (enterprise Wi-Fi).")
                + " "
                + _("Set it up in All network settings."),
                _("Open"),
                lambda: self._screen.show_panel("network", _("Network")),
            )
        elif net and not self.secured(net):
            self.add_and_connect(ssid, "")
        else:
            self.open_password(ssid)

    def add_and_connect(self, ssid, psk):
        result = self.nm.add_network(ssid, psk)
        if "error" in result:
            return result
        self.connect(ssid)
        return result

    def connect(self, ssid):
        self.nm.connect(ssid)
        self.shown = None
        GLib.timeout_add_seconds(2, self._refresh_once)

    def disconnect(self):
        self.nm.disconnect_network()
        self.shown = None
        GLib.timeout_add_seconds(2, self._refresh_once)

    def ask_forget(self, ssid):
        ss.confirm(
            self._screen,
            _("Forget") + f" {ssid}?",
            _("The printer won't join this network by itself any more.")
            + " "
            + _("You'll need the password again."),
            _("Forget"),
            lambda: self.forget(ssid),
            kind="danger",
        )

    def forget(self, ssid):
        self.nm.delete_network(ssid)
        self.shown = None
        GLib.timeout_add_seconds(1, self._refresh_once)

    def _refresh_once(self):
        self.refresh()
        return False

    def toggle_wifi(self, *args):
        on = self.nm.is_wifi_enabled()
        if not on:
            self.nm.toggle_wifi(True)
            self.shown = None
            GLib.timeout_add_seconds(3, self._rescan_once)
            self.refresh()
            return
        ss.confirm(
            self._screen,
            _("Turn off Wi-Fi?"),
            _("Mainsail on other devices stops working unless the printer also has a cable."),
            _("Turn off"),
            self._wifi_off,
            kind="warning",
        )

    def _wifi_off(self):
        self.nm.toggle_wifi(False)
        self.shown = None
        self.refresh()

    def rescan(self, *args):
        self.nm.rescan()
        GLib.timeout_add_seconds(3, self._refresh_once)

    def _rescan_once(self):
        self.rescan()
        return False

    # ------------------------------------------------------------------ password page
    def open_password(self, ssid):
        self.pw_ssid = ssid
        self.pw_title.set_text(_("Password for") + f" {ssid}")
        self.pw_entry.set_text("")
        self.pw_entry.set_visibility(False)
        ss.set_button_text(self.pw_show, _("Show"))
        self.pw_error.set_text("")
        self.stack.set_visible_child_name("password")
        self._screen.show_keyboard(entry=self.pw_entry)

    def toggle_visible(self, *args):
        visible = not self.pw_entry.get_visibility()
        self.pw_entry.set_visibility(visible)
        ss.set_button_text(self.pw_show, _("Hide") if visible else _("Show"))

    def join(self, *args):
        psk = self.pw_entry.get_text()
        if len(psk) < 8:
            self.pw_error.set_text(_("Wi-Fi passwords have at least 8 characters."))
            return
        result = self.add_and_connect(self.pw_ssid, psk)
        if "error" in result:
            self.pw_error.set_text(result.get("message", _("Couldn't add network")))
            return
        self.close_password()

    def close_password(self, *args):
        self._screen.remove_keyboard()
        self.pw_entry.set_text("")
        self.pw_ssid = None
        self.stack.set_visible_child_name("list")
        self.shown = None
        self.refresh()

    # ------------------------------------------------------------------ lifecycle
    def activate(self):
        if self.nm is None:
            return
        if self.nm.wifi:
            self.nm.set_connection_monitoring(True)
            GLib.timeout_add_seconds(1, self.nm.monitor_connection_status)
            if self.nm.is_wifi_enabled():
                self.nm.rescan()
        self.shown = None
        self.refresh()
        if self.timer is None:
            self.timer = GLib.timeout_add_seconds(5, self.refresh)

    def deactivate(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        if self.nm is not None:
            self.nm.set_connection_monitoring(False)

    def back(self):
        if self.stack.get_visible_child_name() == "password":
            self.close_password()
            return True
        return False
