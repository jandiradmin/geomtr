#!/usr/bin/env python3
"""geomtr: mtr with geolocation and ASN for every hop.

Runs the system `mtr --raw`, parses its stream in real time and enriches
every hop IP with data from ip-api.com (free, no API key).

Examples:
    geomtr example.com
    geomtr -c 20 -i 0.5 8.8.8.8
    geomtr -c 10 --report -o out.json example.com
"""
import argparse
import csv
import ipaddress
import json
import math
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

__version__ = "0.1.0"

from rich.console import Console
from rich.live import Live
from rich.table import Table

GEO_URL = "http://ip-api.com/batch?fields=status,message,country,countryCode,regionName,city,isp,org,as,query"


class Hop:
    def __init__(self, nr):
        self.nr = nr
        self.ips = []          # every IP that answered at this hop (ECMP)
        self.ip = None         # most recent responding IP
        self.host = None
        self.sent = 0
        self.recv = 0
        self.last = self.best = self.worst = None
        self._sum = 0.0
        self._sumsq = 0.0

    def add_rtt(self, ms):
        self.recv += 1
        self.last = ms
        self.best = ms if self.best is None else min(self.best, ms)
        self.worst = ms if self.worst is None else max(self.worst, ms)
        self._sum += ms
        self._sumsq += ms * ms

    @property
    def avg(self):
        return self._sum / self.recv if self.recv else None

    @property
    def stdev(self):
        if self.recv < 2:
            return None
        m = self.avg
        return math.sqrt(max(self._sumsq / self.recv - m * m, 0.0))

    @property
    def loss(self):
        # the latest probe may still be in flight, so do not count it as lost
        sent = self.sent - 1 if self.sent > self.recv else self.sent
        return 100.0 * (sent - self.recv) / sent if sent > 0 else 0.0


class Geo:
    """Geo data cache with batched background lookups."""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.data = {}
        self.pending = set()
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        if enabled:
            threading.Thread(target=self._worker, daemon=True).start()

    def request(self, ip):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return
        with self.lock:
            if ip in self.data or ip in self.pending:
                return
            if not addr.is_global:
                self.data[ip] = {"location": "Private network", "as": ""}
                return
            if not self.enabled:
                return
            self.pending.add(ip)
            self.cv.notify()

    def get(self, ip):
        with self.lock:
            return self.data.get(ip)

    def _worker(self):
        while True:
            with self.lock:
                while not self.pending:
                    self.cv.wait()
            time.sleep(0.5)  # let a batch accumulate
            with self.lock:
                batch = list(self.pending)[:100]
            try:
                req = urllib.request.Request(
                    GEO_URL, data=json.dumps(batch).encode(),
                    headers={"Content-Type": "application/json", "User-Agent": "geomtr"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    results = json.load(r)
            except Exception:
                time.sleep(5)
                continue
            with self.lock:
                for res in results:
                    ip = res.get("query")
                    if res.get("status") == "success":
                        loc = ", ".join(x for x in (res.get("city"), res.get("regionName"), res.get("countryCode")) if x)
                        self.data[ip] = {
                            "location": loc,
                            "country": res.get("country"),
                            "city": res.get("city"),
                            "as": res.get("as") or res.get("isp") or "",
                        }
                    else:
                        self.data[ip] = {"location": res.get("message", "unknown"), "as": ""}
                    self.pending.discard(ip)
            time.sleep(4.5)  # ip-api free tier: 15 batch requests per minute


class Tracer:
    def __init__(self, target, count, interval, resolve, family=None):
        self.target = target
        try:
            self.target_ips = {ai[4][0] for ai in socket.getaddrinfo(target, None, {4: socket.AF_INET, 6: socket.AF_INET6}.get(family, 0))}
        except OSError:
            self.target_ips = {target}
        self.hops = {}
        self.lock = threading.Lock()
        self.geo = None
        cmd = ["mtr", "--raw", "-c", str(count), "-i", str(interval)]
        if not resolve:
            cmd.append("-n")
        if family:
            cmd.append(f"-{family}")
        cmd.append(target)
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    def hop(self, n):
        if n not in self.hops:
            self.hops[n] = Hop(n + 1)
        return self.hops[n]

    def run(self):
        for line in self.proc.stdout:
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            kind, pos, val = parts[0], int(parts[1]), parts[2].strip()
            with self.lock:
                h = self.hop(pos)
                if kind == "x":
                    h.sent += 1
                elif kind == "h":
                    h.ip = val
                    if val not in h.ips:
                        h.ips.append(val)
                    self.geo.request(val)
                elif kind == "p":
                    h.add_rtt(int(val.split()[0]) / 1000.0)
                elif kind == "d":
                    h.host = val

    def visible_hops(self):
        """Hops up to and including the target (mtr keeps probing past it)."""
        with self.lock:
            hops = [self.hops[k] for k in sorted(self.hops)]
        last = len(hops)
        for i, h in enumerate(hops):
            if h.ip and (h.ip in self.target_ips or h.host == self.target):
                last = i + 1
                break
        else:
            # trim trailing "*" hops when nothing further answers
            while last > 0 and not hops[last - 1].ip:
                last -= 1
            if last < len(hops):
                last += 1
        return hops[:last]


def fmt(v):
    return "" if v is None else f"{v:.1f}"


def build_rows(tracer):
    rows = []
    for h in tracer.visible_hops():
        g = tracer.geo.get(h.ip) if h.ip else None
        rows.append({
            "nr": h.nr,
            "ip": h.ip or "*",
            "other_ips": [ip for ip in h.ips if ip != h.ip],
            "host": h.host if h.host and h.host != h.ip else "",
            "location": (g or {}).get("location", "…" if h.ip else ""),
            "as": (g or {}).get("as", ""),
            "loss": round(h.loss, 1),
            "sent": h.sent, "recv": h.recv,
            "last": h.last, "avg": h.avg, "best": h.best, "worst": h.worst, "stdev": h.stdev,
        })
    return rows


def render(tracer, title):
    t = Table(title=title, expand=True, header_style="bold cyan", row_styles=["", "dim"])
    t.add_column("Nr", justify="right", no_wrap=True)
    t.add_column("IP", no_wrap=True)
    t.add_column("Host", overflow="ellipsis", no_wrap=True, ratio=2)
    t.add_column("Location", overflow="ellipsis", no_wrap=True, ratio=2)
    t.add_column("AS", overflow="ellipsis", no_wrap=True, ratio=2)
    for c in ("Loss%", "Snt", "Rcv", "Last", "Avg", "Best", "Wrst", "StDev"):
        t.add_column(c, justify="right", no_wrap=True)
    for r in build_rows(tracer):
        loss = r["loss"]
        ls = "red" if loss >= 50 else "yellow" if loss > 0 else "green"
        ip = r["ip"] + (f" [dim](+{len(r['other_ips'])})[/]" if r["other_ips"] else "")
        t.add_row(str(r["nr"]), ip, r["host"], r["location"], r["as"],
                  f"[{ls}]{loss:.1f}[/]", str(r["sent"]), str(r["recv"]),
                  fmt(r["last"]), fmt(r["avg"]), fmt(r["best"]), fmt(r["worst"]), fmt(r["stdev"]))
    return t


def export(rows, path):
    if path.endswith(".csv"):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["nr"])
            w.writeheader()
            for r in rows:
                w.writerow({**r, "other_ips": " ".join(r["other_ips"])})
    else:
        with open(path, "w") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="mtr with per-hop geolocation and ASN (ip-api.com)")
    ap.add_argument("target")
    ap.add_argument("-c", "--count", type=int, default=0, help="number of cycles (0 = run until Ctrl+C)")
    ap.add_argument("-i", "--interval", type=float, default=1.0, help="seconds between cycles")
    ap.add_argument("-n", "--no-dns", action="store_true", help="do not resolve hostnames")
    fam = ap.add_mutually_exclusive_group()
    fam.add_argument("-4", dest="family", action="store_const", const=4, help="use IPv4 only")
    fam.add_argument("-6", dest="family", action="store_const", const=6, help="use IPv6 only")
    ap.add_argument("--no-geo", action="store_true", help="skip geolocation lookups")
    ap.add_argument("--report", action="store_true", help="no live view, print the final table only")
    ap.add_argument("-o", "--output", help="save results to a .json or .csv file")
    ap.add_argument("-V", "--version", action="version", version=f"geomtr {__version__}")
    args = ap.parse_args()

    if not shutil.which("mtr"):
        sys.exit("mtr not found. Install it first: brew install mtr (macOS) or apt install mtr-tiny (Debian/Ubuntu)")

    count = args.count or 10**7
    tracer = Tracer(args.target, count, args.interval, not args.no_dns, args.family)
    tracer.geo = Geo(enabled=not args.no_geo)
    reader = threading.Thread(target=tracer.run, daemon=True)
    reader.start()

    console = Console()
    ver = f" IPv{args.family}" if args.family else ""
    title = f"geomtr{ver} → {args.target}   (Ctrl+C to stop)"
    try:
        if args.report:
            with console.status(f"Tracing {args.target}…"):
                reader.join()
                time.sleep(1.5)  # let pending geo lookups finish
        else:
            with Live(render(tracer, title), console=console, refresh_per_second=2, screen=False) as live:
                while reader.is_alive():
                    live.update(render(tracer, title))
                    time.sleep(0.5)
                time.sleep(1.5)
                live.update(render(tracer, f"geomtr{ver} → {args.target}"))
    except KeyboardInterrupt:
        tracer.proc.terminate()

    err = tracer.proc.stderr.read() if tracer.proc.poll() not in (None, 0) and not tracer.hops else ""
    if err:
        sys.exit(err.strip())
    if args.report:
        console.print(render(tracer, f"geomtr{ver} → {args.target}"))
    if args.output:
        export(build_rows(tracer), args.output)
        console.print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
