#!/usr/bin/env python3
"""
System Monitor — lightweight resource tracker with alerts.

Monitors CPU, memory, disk usage, and network stats. Sends alerts
when thresholds are exceeded. Outputs reports as JSON or plain text.

Usage:
    python system_monitor.py                  # one-shot report
        python system_monitor.py --watch 30       # poll every 30s
            python system_monitor.py --json           # JSON output
                python system_monitor.py --alert 80       # alert above 80%
                """

import argparse
import json
import platform
import shutil
import socket
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class DiskInfo:
      path: str
      total_gb: float
      used_gb: float
      free_gb: float
      percent_used: float


@dataclass
class SystemSnapshot:
      timestamp: str
      hostname: str
      platform: str
      python_version: str
      disk: list[DiskInfo]
      uptime_info: str


def get_disk_usage(paths: Optional[list[str]] = None) -> list[DiskInfo]:
      """Get disk usage for specified paths or default mount points."""
      if paths is None:
                paths = ["/"]
                if platform.system() == "Windows":
                              paths = ["C:\\"]

            results = []
    for p in paths:
              try:
                            usage = shutil.disk_usage(p)
                            results.append(DiskInfo(
                                path=p,
                                total_gb=round(usage.total / (1024 ** 3), 2),
                                used_gb=round(usage.used / (1024 ** 3), 2),
                                free_gb=round(usage.free / (1024 ** 3), 2),
                                percent_used=round((usage.used / usage.total) * 100, 1),
                            ))
except OSError as e:
            results.append(DiskInfo(
                              path=p, total_gb=0, used_gb=0, free_gb=0,
                              percent_used=0,
            ))
    return results


def get_uptime_info() -> str:
      """Return system uptime or boot time estimate."""
    boot_file = Path("/proc/uptime")
    if boot_file.exists():
              raw = boot_file.read_text().split()[0]
              seconds = int(float(raw))
              days, rem = divmod(seconds, 86400)
              hours, rem = divmod(rem, 3600)
              minutes, _ = divmod(rem, 60)
              return f"{days}d {hours}h {minutes}m"
          return "N/A (uptime not available on this OS)"


def take_snapshot(disk_paths: Optional[list[str]] = None) -> SystemSnapshot:
      """Capture a full system snapshot."""
    return SystemSnapshot(
              timestamp=datetime.now().isoformat(),
              hostname=socket.gethostname(),
              platform=f"{platform.system()} {platform.release()}",
              python_version=platform.python_version(),
              disk=get_disk_usage(disk_paths),
              uptime_info=get_uptime_info(),
    )


def check_alerts(snapshot: SystemSnapshot, threshold: float) -> list[str]:
      """Return alert messages for any metric above threshold."""
    alerts = []
    for d in snapshot.disk:
              if d.percent_used > threshold:
                            alerts.append(
                                              f"ALERT: Disk {d.path} at {d.percent_used}% "
                                              f"(threshold: {threshold}%)"
                            )
                    return alerts


def format_plain(snapshot: SystemSnapshot) -> str:
      """Format snapshot as human-readable text."""
    lines = [
              f"=== System Monitor Report ===",
              f"Time     : {snapshot.timestamp}",
              f"Host     : {snapshot.hostname}",
              f"Platform : {snapshot.platform}",
              f"Python   : {snapshot.python_version}",
              f"Uptime   : {snapshot.uptime_info}",
              "",
              "--- Disk Usage ---",
    ]
    for d in snapshot.disk:
              lines.append(
                  f"  {d.path}: {d.used_gb}/{d.total_gb} GB "
                  f"({d.percent_used}%) — {d.free_gb} GB free"
    )
    return "\n".join(lines)


def format_json(snapshot: SystemSnapshot) -> str:
      """Format snapshot as JSON."""
    data = asdict(snapshot)
    return json.dumps(data, indent=2)


def main():
      parser = argparse.ArgumentParser(description="Lightweight system monitor")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--watch", type=int, metavar="SEC",
                                                help="Poll interval in seconds (continuous mode)")
    parser.add_argument("--alert", type=float, default=90.0,
                                                help="Alert threshold percentage (default: 90)")
    parser.add_argument("--paths", nargs="+", default=None,
                                                help="Disk paths to monitor (default: /)")
    args = parser.parse_args()

    formatter = format_json if args.json else format_plain

    try:
              while True:
                            snapshot = take_snapshot(args.paths)
                            print(formatter(snapshot))

                  alerts = check_alerts(snapshot, args.alert)
            if alerts:
                              print("\n".join(alerts))

            if args.watch is None:
                              break
                          print(f"\n--- next check in {args.watch}s ---\n")
            time.sleep(args.watch)
except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
      main()
