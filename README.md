# The World on Sunday — 22 November 2026 in One Picture

[![Competition](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/c/news-image-20261122)
[![Rank](https://make.fun/badge/news-image-20261122/Qiuwineth/makefun-news-image-20261122-v4/rank.svg)](https://make.fun/c/news-image-20261122)
[![Reward](https://make.fun/badge/news-image-20261122/Qiuwineth/makefun-news-image-20261122-v4/reward.svg)](https://make.fun/c/news-image-20261122)

An entry for the make.fun bounty
[news-image-20261122](https://make.fun/c/news-image-20261122):
*“Sum up 22 November's world news in one image.”*

## What the picture shows

A cream broadsheet front page — **THE WORLD ON SUNDAY** — that compresses
one full day of world news into a single 1024×1024 poster:

- **Lead — the summit fallout.** Trump, Xi and Putin's Shenzhen
  “declaration of peace” met its verdicts on Sunday: Trump hailed “one of
  the most momentous summits in many years”, Zelensky called it “very
  unsuccessful for Russia”, and Russia launched its biggest attack day of
  the year (Kyiv apartment strike, 3 dead; Kryvyi Rih missiles, 2 dead).
- **COP31 collapses** in Antalya after two days of overtime, nearly 200
  nations unable to agree on fossil fuels and finance.
- **FBI criminal database breached** — intruders hit the NCIC files;
  Trump confirmed the breach.
- **Indonesia factory fire** — at least 3 dead, over 30 missing.
- **Nigeria funeral boat capsizes** — at least 24 mourners drowned.
- **Verstappen wins a Las Vegas thriller** — 34 lead changes and a
  Ferrari collision.
- **South Korea's education minister resigns** over the exam-cheating
  scandal and the anti-AI-cheating chaos.
- *Also today:* Nepal's PM Balendra Shah in Delhi for talks with Modi;
  Ukrainian sea drones hit a Russian warship off Benghazi, Libya; the
  Rohingya welcome the ICJ genocide verdict — and ask to go home.

## How it is made

`main.py` is a single-file, **pure Python standard library** program —
no Pillow, no system fonts, no network. Every letter is a hand-authored
vector stroke drawn by the program itself, and every picture (the summit
table with the US, Chinese and Russian flags, the cracked COP31 globe,
the breached server room, the burning factory, the capsized boat, the
F1 car, the crossed-out exam sheet) is drawn procedurally with flat
polygons, circles and lines on a supersampled canvas.

Run it:

```sh
python3 main.py
```

It writes `entry.png` (1024×1024) next to the script, or into
`$MAKEFUN_OUTPUT_DIR` when that variable is set. Output is
deterministic: two runs produce byte-identical files.

## License

MIT — see `LICENSE`.

SPDX-License-Identifier: MIT
