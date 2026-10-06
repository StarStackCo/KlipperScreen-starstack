# STARSTACK-ADDED: About this printer (FORK_CHANGES.md #40, klipper-ui D-067)
# Read-only facts in pages with ‹ › arrows (replaces the stock "system" panel on the touchscreen):
# network, software versions, storage, Pi temperature/memory, uptime.
import os
import shutil

from ks_includes import functions
from ks_includes import starstack as ss
from ks_includes.screen_panel import ScreenPanel


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        self.klipper = "…"
        page, self.pager = ss.list_page(_("About this printer"))
        self.content.add(page)
        self.content.show_all()
        self.build()

    def info_row(self, name, value):
        return (ss.row(name, value or "–", css_note="ss-row-title"), "row")

    def network(self):
        info = getattr(self._printer, "system_info", None) or {}
        out = []
        for iface, data in (info.get("network") or {}).items():
            ips = [a["address"] for a in data.get("ip_addresses", []) if a.get("family") == "ipv4"]
            if ips and iface != "lo":
                kind = _("Wi-Fi") if iface.startswith("wl") else _("Ethernet")
                out.append(f"{kind} · {ips[0]}")
        return out

    def pi_temperature(self):
        for name in self._printer.get_temp_devices():
            low = name.lower()
            if name.startswith("temperature_sensor") and any(
                k in low for k in ("pi", "host", "cb1", "mcu_temp", "soc")
            ):
                t = self._printer.get_stat(name, "temperature")
                if t:
                    return f"{t:.0f} °C"
        return None

    def build(self):
        info = getattr(self._printer, "system_info", None) or {}
        server = getattr(self._screen, "server_info", None) or {}
        rows = [self.info_row(_("Name"), os.uname().nodename)]
        rows += [self.info_row(_("Network"), n) for n in self.network()] or [
            self.info_row(_("Network"), _("not connected"))
        ]
        rows.append((ss.label(_("SOFTWARE"), "ss-section"), "section"))
        rows.append(self.info_row("Klipper", self.klipper))
        rows.append(self.info_row("Moonraker", server.get("moonraker_version")))
        rows.append(self.info_row(_("Touchscreen"), functions.get_software_version()))
        dist = (info.get("distribution") or {}).get("name")
        rows.append(self.info_row(_("System"), dist))
        rows.append((ss.label(_("HARDWARE"), "ss-section"), "section"))
        gcodes = self._files.gcodes_path
        if gcodes and os.path.isdir(gcodes):
            du = shutil.disk_usage(gcodes)
            rows.append(
                self.info_row(_("Storage free"), f"{fmt_bytes(du.free)} / {fmt_bytes(du.total)}")
            )
        cpu = info.get("cpu_info") or {}
        if cpu.get("total_memory"):
            mem = int(cpu["total_memory"]) * (1024 if cpu.get("memory_units") == "kB" else 1)
            rows.append(self.info_row(_("Memory"), fmt_bytes(mem)))
        rows.append(self.info_row(_("Pi temperature"), self.pi_temperature()))
        try:
            with open("/proc/uptime") as f:
                secs = float(f.read().split()[0])
            rows.append(self.info_row(_("Running for"), ss.fmt_duration(secs)))
        except OSError:
            pass
        self.pager.set_rows(rows)

    def _got_info(self, result):
        if result:
            self.klipper = result.get("software_version", "–")
            self.build()

    def activate(self):
        ss.request(self._screen, "printer.info", {}, self._got_info)
        self.build()
