# The World in One Day — Monday 23 November 2026

[![make.fun](https://make.fun/badge/news-image-20261123.svg)](https://make.fun/bounty/news-image-20261123)
[![rank](https://make.fun/badge/news-image-20261123/jonsonbmth/makefun-news-image-20261123/rank.svg)](https://make.fun/bounty/news-image-20261123)
[![reward](https://make.fun/badge/news-image-20261123/jonsonbmth/makefun-news-image-20261123/reward.svg)](https://make.fun/bounty/news-image-20261123)

An entry for the [make.fun bounty "Sum up 23 November's world news in one image"](https://make.fun/bounty/news-image-20261123): one 1024×1024 page that sums up Monday 23 November 2026 in 32 verified stories across 6 regions.

## What is on the page

- **3 lead stories** — Nepal's prime minister Balendra Shah meets Narendra Modi in Delhi; the search resumes at dawn in the burnt-out candy factory in Serang, Indonesia (24 body bags recovered, 29 still missing); New Zealand fight to save the Wellington Test after India's 720 for 9.
- **10 second stories** — Wong's first flight into Western Sydney, the Newspoll preferred-PM flip, Japan's markets shut for Labor Thanksgiving Day, a Fiji quake, Sydney storms, flash PMIs, Victoria polling, parliament's final sitting week, Guru Nanak Jayanti, and Vikings at 49ers.
- **19 more stories** — from NZ retail sales to Burundi's election vetting, each with its place, outlet, and status.
- **A world map** with numbered pins matching the story numbers, a "THE DAY IN UTC" timeline, a key-numbers strip, and a **DATE CHECK** box that lists, with their real dates, the big stories deliberately left out because they belong to other days — plus the outcomes that were not yet decided when the page was drawn early on Monday morning (WIB).

Every story names its outlet. One-sided claims are labelled CLAIM, scheduled items FORECAST, and the rest REPORTED or OFFICIAL. Nothing on the page is invented: every story was verified against real wires (Reuters, AP, AFP, Al Jazeera, BBC, The Guardian, ABC, AAP, ESPNcricinfo, Cricbuzz, Xinhua, IANS, and official releases) before it was drawn.

## How it is made

`main.py` (Python 3.13, standard library only) draws the whole page in code — its own framebuffer rasterizer, its own hand-typed 5×7 bitmap font and vector serif masthead face, and its own PNG encoder. No network, no fonts, no image files. The pictures and the map are original, drawn in code.

```sh
MAKEFUN_OUTPUT_DIR=/output python3 main.py
```

That writes `/output/entry.png`: 1024×1024, under 1 MiB, and deterministic — two runs produce byte-identical output.

## License

MIT. See [LICENSE](LICENSE).
