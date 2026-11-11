# geomtr

**`mtr` with geolocation.** A live traceroute table that shows the city, country and AS of every hop. No API token, no signup.

![geomtr demo](assets/demo.gif)

## Features

- Live-updating table: Loss%, Sent, Recv, Last, Avg, Best, Worst, StDev
- City / region / country and ASN + ISP for every hop ([ip-api.com](https://ip-api.com), free, no key)
- IPv4 and IPv6 (`-4` / `-6`)
- Shows ECMP / load-balanced hops (`+N` alternate IPs)
- Private ranges are labeled locally and never sent to the API
- Report mode and export to JSON / CSV
- Batched and cached geo lookups that stay inside the free API rate limits

## Install

**Homebrew (macOS / Linux):**

```bash
brew install jandiradmin/tap/geomtr
```

**pipx:**

```bash
pipx install git+https://github.com/jandiradmin/geomtr.git
```

`mtr` must be installed and in your PATH (`brew install mtr` or `sudo apt install mtr-tiny`). Homebrew installs it for you.

**From source:**

```bash
git clone https://github.com/jandiradmin/geomtr.git
cd geomtr
pip install rich
ln -s "$PWD/geomtr.py" ~/.local/bin/geomtr   # any directory in your PATH
```

## Usage

```bash
geomtr example.com                          # live view, Ctrl+C to stop
geomtr -4 example.com                       # force IPv4
geomtr -6 example.com                       # force IPv6
geomtr -c 20 -i 0.5 8.8.8.8                 # 20 cycles, 0.5 s interval
geomtr -c 10 --report -o out.csv host       # one-shot report + export (.csv / .json)
geomtr -n --no-geo host                     # no DNS, no geolocation
```

Optional aliases:

```bash
alias trace='geomtr'
alias traceroute='geomtr -c 3 --report'     # original stays available as \traceroute
```

## Notes

- Geolocation is queried over plain HTTP. On the free tier ip-api.com only serves HTTP, and the service sees the hop IPs it is asked about.
- GeoIP for backbone routers and anycast/CDN addresses (Cloudflare, Fastly, Google…) is often the registration location, not the physical one. Router hostnames such as `lax-`, `ffm-` or `kiev-` are often a better hint.
- On Linux, `mtr` may need root or `cap_net_raw` depending on how it was packaged.

## License

MIT
