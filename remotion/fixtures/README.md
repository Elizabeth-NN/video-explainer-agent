# Remotion Fixtures

Each JSON file in this directory is a complete `ExplainerProps` object (the same
format the Python pipeline writes to `input-props.json`), with a single scene that
exercises one visual type.

## Fixture files

| File | Visual type | What it tests |
|------|-------------|---------------|
| `flow.json` | `flow` | 3-node electricity-transfer flow |
| `hub.json` | `hub` | Sun as central hub with 4 satellite processes |
| `bars.json` | `bars` | Renewable energy GW bar chart |
| `sequence.json` | `sequence` | 4-step mRNA vaccine sequence |
| `cycle.json` | `cycle` | 4-stage water cycle |
| `layers.json` | `layers` | Solar-cell layer stack with 2 electron carriers |
| `anatomy.json` | `anatomy` | Animal cell with 4 labelled parts (circle subject) |
| `comparison.json` | `comparison` | Solar vs nuclear side-by-side |
| `scene-graph.json` | `scene-graph` | 5-node internet routing graph |
| `broken-normalize.json` | `layers` | Unknown color `"blue"` → `teal`, unknown icon `"battery"` → `cell`, carrier index 99 → filtered |

## Rendering a still

From the `remotion/` directory:

```bash
# Generic pattern
npx remotion still src/index.ts Explainer --frame=60 out/fixture-<name>.png \
  --props=fixtures/<name>.json

# Examples
npx remotion still src/index.ts Explainer --frame=60 out/fixture-layers.png \
  --props=fixtures/layers.json

npx remotion still src/index.ts Explainer --frame=60 out/fixture-cycle.png \
  --props=fixtures/cycle.json

npx remotion still src/index.ts Explainer --frame=60 out/fixture-broken.png \
  --props=fixtures/broken-normalize.json
```

> **Note:** The `--concurrency=1` flag is optional but avoids port conflicts when
> running multiple stills back-to-back.

## What `broken-normalize.json` verifies

- Color `"blue"` → resolved to `"teal"` via `COLOR_ALIASES`
- Color `"yellow"` → resolved to `"gold"` via `COLOR_ALIASES`
- Color `"green"` → resolved to `"teal"` via `COLOR_ALIASES`
- Carrier with `fromLayer: 99, toLayer: 99` → silently filtered out (only 4 layers)
- The scene renders without errors or TypeScript exceptions
