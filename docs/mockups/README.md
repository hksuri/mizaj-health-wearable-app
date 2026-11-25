# UI mockups

Visual reference for the Mizaj web app (chat, annotate, review, sidebar; light and dark).

| Path | Contents |
| --- | --- |
| [mizaj-ui/](mizaj-ui/) | Design Canvas export — open `.dc.html` artboards via a local static server |

Implementation should match these screens for layout and theme (HLD D19). Contracts (SSE, tools, evals) still come from [lld.md](../lld.md).

### Preview

```bash
cd docs/mockups/mizaj-ui && python3 -m http.server 8765
# open http://localhost:8765/Main.dc.html (or ChatEmpty, Annotate, Review, *Dark variants)
```
