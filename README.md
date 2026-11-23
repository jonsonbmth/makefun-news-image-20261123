# The World in One Day — Monday 23 November 2026

[![make.fun](https://make.fun/badge/news-image-20261123.svg)](https://make.fun/bounty/news-image-20261123)
[![rank](https://make.fun/badge/news-image-20261123/jonsonbmth/makefun-news-image-20261123/rank.svg)](https://make.fun/bounty/news-image-20261123)
[![reward](https://make.fun/badge/news-image-20261123/jonsonbmth/makefun-news-image-20261123/reward.svg)](https://make.fun/bounty/news-image-20261123)

An entry for the [make.fun bounty "Sum up 23 November's world news in one image"](https://make.fun/bounty/news-image-20261123): one 1024×1024 page that sums up Monday 23 November 2026 in 38 verified stories across 7 regions.

This is the second version of the entry, drawn late on Monday night (WIB), once the day had actually happened — so it leads with what Monday really produced instead of what was merely expected that morning.

## What is on the page

- **3 lead stories** — Nvidia's board votes unanimously to reinstate Jensen Huang as chief executive, 11 days after he resigned, and the shares jump 33%; Kyiv confirms seven naval drones sank the Russian corvette Merkury off Benghazi; Mitchell and Phillips bat out a draw for New Zealand in the Wellington Test after India's 720 for 9.
- **10 second stories** — the Serang fire death toll confirmed at 24, Modi's $1.6bn flood offer to Nepal, Russian strikes killing 14 in Ukraine, a UNRWA worker killed in Gaza, the 49ers routing the Vikings 35–10 in Mexico City, the eurozone and US flash PMIs, New Zealand's best retail quarter since 2021, Taylor passing Albanese as preferred PM, and a deep M6.5 quake off Vanuatu.
- **25 more stories** — from Bolsonaro's ICU update in Brasilia to Coca-Cola's AFCON 2027 sponsorship, each with its place, outlet, and status.
- **A world map** with numbered pins matching the story numbers, a "THE DAY IN UTC" timeline, a key-numbers strip, and a **DATE CHECK** box that lists, with their real dates, the big stories deliberately left out because they belong to other days — plus the outcomes that were not yet decided when the page was drawn.

Every story names its outlet. One-sided claims are labelled CLAIM, and the rest REPORTED or OFFICIAL. Nothing on the page is invented, and nothing is a forecast dressed up as news: every story was verified against real wires (Reuters, AP, AFP, CNN, WSJ, BBC, ESPNcricinfo, S&P Global, Stats NZ, USGS, UN News, Radio Nepal, IANS, Newspoll, BOM, PCHR, CAF, and official releases) before it was drawn.

## How it is made

`main.py` (Python 3.13, standard library only) draws the whole page in code — its own framebuffer rasterizer, its own hand-typed 5×7 bitmap font and vector serif masthead face, and its own PNG encoder. No network, no fonts, no image files. The pictures and the map are original, drawn in code.

```sh
MAKEFUN_OUTPUT_DIR=/output python3 main.py
```

That writes `/output/entry.png`: 1024×1024, under 1 MiB, and deterministic — two runs produce byte-identical output.

## License

MIT. See [LICENSE](LICENSE).
