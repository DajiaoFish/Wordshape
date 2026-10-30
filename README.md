# WordShape

**English** | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)

**Turn text into graphics — then pour text into shapes.**

A pure-Python typography tool with two features and 16 effects. No AI image model involved: everything is computed locally, so output is **watermark-free, credit-free and fully deterministic** (same input → same pixels).

![Nine text transform effects](examples/overview-9-effects.png)

*Feature 1 — nine text transform effects*

---

## Contents

- [Features](#features)
- [Install](#install)
- [Quick start](#quick-start)
- [Feature 1 — Text transform](#feature-1--text-transform)
- [Feature 2 — Subject silhouette fill](#feature-2--subject-silhouette-fill)
- [Fonts](#fonts)
- [Integration](#integration)
- [Project layout](#project-layout)
- [FAQ](#faq)
- [License](#license)

---

## Features

| Feature | Input | Output |
|---|---|---|
| **text** — text transform | A string | Text replicated, warped, perspective-bent or arranged in rings (9 effects) |
| **fill** — silhouette fill | A subject image + a string | Transparent PNG where the text fills the subject outline (7 effects) |

All output is PNG, red text `#E03A2F` on a transparent background by default — ready to composite onto posters, covers or video.

---

## Install

```bash
git clone https://github.com/DajiaoFish/Wordshape.git
cd Wordshape
pip install -r requirements.txt
```

Requirements: Python 3.9+, `Pillow`, `numpy`. Nothing else.

---

## Quick start

```bash
# List all effects
python -m wordshape list

# Feature 1: text transform (default: transparent bg, red text)
python -m wordshape text "HELLO" -o out/spiral.png --effect spiral

# Feature 1: black background, red text
python -m wordshape text "KEEP GOING" -o out/fisheye.png --effect fisheye --mode br

# Feature 2: fill a silhouette (horizontal)
python -m wordshape fill subject.png "stay curious" -o out/subject.png

# Feature 2: vertical layout + wave distortion
python -m wordshape fill subject.png "stay curious" -o out/subject_wave.png --layout v --effect wave
```

---

## Feature 1 — Text transform

| Key | Name | Description |
|---|---|---|
| `spiral` | Spiral repeat | 25 copies, 97% scale + 10° rotation each — dense vortex, original text readable on top |
| `circular` | Circular text | Text bent along a circle, then 8 rotated copies |
| `tunnel` | Perspective tunnel | Multi-line text as four perspective walls, hollow centre |
| `wave_v` | Vertical wave | Multi-line text bent along a vertical sine wave |
| `wave_h` | Horizontal wave | Multi-line text with staggered horizontal offsets |
| `flowline` | Flowline | All lines flow along one smooth sine curve |
| `waveweave` | Wave weave | 23 thin wave bands interwoven — texture use, low legibility |
| `fisheye` | Fisheye | Convex lens mapping: magnified centre, compressed edges |
| `ring` | Ring rotation | Text frames nested with 95% scale + 3° rotation, 20 layers |

### Output modes

| `--mode` | Background | Text |
|---|---|---|
| `tr` | transparent | red `#E03A2F` (**default**) |
| `br` | black `#111111` | red |
| `bw` | white | black |
| `wb` | black | white |
| `white` | transparent | white |
| `black` | transparent | black |
| `red` | red | white |
| `navy` | navy `#0A1F33` | cyan `#4FE0E6` |

Custom colours: `--bg "#101010" --fg "#F0C040"`.

### Options

| Flag | Description | Default |
|---|---|---|
| `--size` | Base font size | 240 |
| `--rows` | Override row count for effects that take it | effect-specific |
| `--font` | Font file path | auto-detected |
| `-o / --out` | Output PNG | required |

---

## Feature 2 — Subject silhouette fill

![Seven silhouette fill effects](examples/overview-7-effects.png)

*Feature 2 — seven silhouette fill effects*

| Effect | Flag | Description |
|---|---|---|
| Horizontal (default) | — | Fill line by line |
| Vertical | `--layout v` | Fill column by column |
| Wave | `--effect wave` | Vertical sine distortion |
| Fisheye bulge | `--effect fisheye` | Magnified centre, shrunken edges |
| Swirl | `--effect swirl` | Stronger twist towards the outside |
| Tunnel (outline) | `--effect tunnel` | Rings follow the subject outline, hollow centre |
| Tunnel (round) | `--effect tunnel_round` | Perfect circular rings, centre cut to the subject shape |

### Input images

1. **Transparent PNG** — best, uses the alpha channel directly
2. **Solid background** — subject is segmented automatically (`--threshold`)
3. **Complex background** — cut it out first, or pass `--mask`

### Options

| Flag | Description | Default |
|---|---|---|
| `--size` | Base font size (density) | 16 |
| `--rows` | Row count (columns in vertical mode) | auto |
| `--gap` | Line gap ratio | 0.02 |
| `--fg` | Text colour | `#E03A2F` |
| `--threshold` | Background segmentation threshold | 36 |

---

## Fonts

Fonts are resolved automatically, in this order:

1. `WORDSHAPE_FONT` environment variable
2. `fonts/` directory inside the repo (bundle a font there to ship it)
3. System font directories — Windows `C:/Windows/Fonts`, macOS `/System/Library/Fonts`, Linux `/usr/share/fonts`

Built-in candidates include Microsoft YaHei, SimHei, PingFang, Hiragino, Noto Sans CJK, Source Han Sans and WenQuanYi.

Pass `--font /path/to/font.otf` to override.

---

## Integration

### CLI

Any environment that can run a shell command can call WordShape directly:

```bash
python -m wordshape text "<text>" -o <out.png> --effect <key>
python -m wordshape fill <image.png> "<text>" -o <out.png> [--layout v] [--effect wave]
```

Exit code `0` means success; the output path is printed to stdout.

### HTTP server

`server.py` is a zero-dependency server (standard library only):

```bash
python server.py --port 8000
```

```bash
curl -X POST http://127.0.0.1:8000/text \
  -H "Content-Type: application/json" \
  -d '{"text":"HELLO","effect":"spiral","mode":"tr"}'

curl -X POST http://127.0.0.1:8000/fill \
  -H "Content-Type: application/json" \
  -d '{"image":"<base64 or data URI>","text":"stay curious","layout":"v"}'
```

Both return `{"ok": true, "image": "<base64 PNG>"}`.

> Note: sandboxed workflow engines that only allow `numpy` / `requests` (for example Coze code nodes) cannot run this locally — deploy `server.py` and call it over HTTP instead.

### Agent skills

`SKILL.md` follows the Agent Skills format (YAML front matter + instructions). Drop the repository into an agent's skills directory — the agent picks it up from the description and calls the CLI.

---

## Project layout

```
wordshape/
├── wordshape/
│   ├── textfx.py        # Feature 1: 9 transform effects
│   ├── subjectfill.py   # Feature 2: silhouette fill
│   ├── cli.py           # command-line entry
│   └── __main__.py      # python -m wordshape
├── server.py            # zero-dependency HTTP server
├── SKILL.md             # Agent Skills descriptor
├── requirements.txt
└── examples/
```

---

## FAQ

**Why is the output on a transparent background?**
It is a design asset meant to be composited onto your own artwork. Use `--mode bw` (or similar) for a solid background.

**Why does the silhouette look like a "block of text"?**
That is the nature of silhouette filling: shape at a distance, text up close. Subjects with rich detail (fur, ears, fingers) read better than flat blocks.

**Does it support Chinese / Japanese / Korean?**
Yes, any language. Latin text keeps word spacing; CJK is written seamlessly without gaps.

**Will two runs produce the same image?**
Yes. Deterministic computation — identical inputs produce identical output, so you can re-run freely while tuning.

**Does it consume image-generation credits?**
No. Everything is local image processing.

---

## License

[MIT](LICENSE) © 2026 [DajiaoFish](https://github.com/DajiaoFish)
