# geomtr

**`mtr` with geolocation.** A live traceroute table that shows the city, country and AS of every hop. No API token, no signup.

```
$ geomtr -4 status.ks.ua
┏━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━┳━━━━━━━┓
┃ Nr ┃ IP             ┃ Host                         ┃ Location                    ┃ AS                          ┃ Loss% ┃ Snt ┃   Avg ┃
┡━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━╇━━━━━━━┩
│  1 │ 192.168.85.1   │                              │ Private network             │                             │   0.0 │  10 │   4.1 │
│  … │                │                              │                             │                             │       │     │       │
│  9 │ 212.162.25.90  │ pantel.edge9.frankfurt1.l…   │ Frankfurt am Main, Hesse, DE│ AS3356 Level 3 Parent, LLC  │   0.0 │  10 │ 182.0 │
│ 10 │ 91.239.136.198 │                              │ Kyiv, Kyiv City, UA         │ AS35213 TOV "Kompjuternie…  │   0.0 │  10 │ 190.8 │
│ 11 │ 193.151.240.4  │ web.status.ks.ua             │ Kyiv, Kyiv City, UA         │ AS25482 ISP STATUS          │   0.0 │  10 │ 193.5 │
└────┴────────────────┴──────────────────────────────┴─────────────────────────────┴─────────────────────────────┴───────┴─────┴───────┘
```

## Features

- Live-updating table: Loss%, Sent, Recv, Last, Avg, Best, Worst, StDev
- City / region / country and ASN + ISP for every hop ([ip-api.com](https://ip-api.com), free, no key)
- IPv4 and IPv6 (`-4` / `-6`)
- Shows ECMP / load-balanced hops (`+N` alternate IPs)
- Private ranges are labeled locally and never sent to the API
- Report mode and export to JSON / CSV
- Batched and cached geo lookups that stay inside the free API rate limits

## Install

Requires [`mtr`](https://github.com/traviscross/mtr) and Python 3.8+.

```bash
# macOS
brew install mtr
# Debian / Ubuntu
sudo apt install mtr-tiny

git clone https://github.com/jandiradmin/geomtr.git
cd geomtr
pip install -r requirements.txt
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
