# NightWise AI — "Last Local" Design System Specification

## 1. Design Direction: "Last Local"
The aesthetic concept centers on the feeling of a well-lit bus stop at 2:00 AM in an Indian city: calm, warm, trustworthy, editorial, and civic. It draws from public transit signage, paper tickets, and sodium-vapor streetlights reflecting off dark asphalt.

It strictly avoids generic tech clichés ("AI slop", purple gradients on white, floating generic cards, and cold cyberpunk neon).

---

## 2. Color Palette & Semantics

### Dark Theme ("Night Asphalt", Default)
| Token | Value | Role |
|---|---|---|
| `--ink-950` | `#0A0B14` | Deep night asphalt ground |
| `--ink-900` | `#11131F` | Surface layer (rail, tickets, cards) |
| `--ink-800` | `#191C2C` | Input backgrounds, elevated borders |
| `--ink-700` | `#23273D` | Interactive hover states, dividers |
| `--text-primary` | `#ECE6D8` | Warm off-white primary text |
| `--text-muted` | `#9A9684` | Secondary text, data labels |
| `--sodium` | `#FFB547` | Dominant sodium-lamp amber accent |
| `--sodium-glow` | `rgba(255, 181, 71, 0.18)` | Ambient soft lighting aura |
| `--mint` | `#6FE3B5` | Safest route indicator, covered points |
| `--coral` | `#FF5D5D` | Dark gap penalty indicator, closed places |
| `--cyan` | `#7FC8F8` | Fastest route indicator, transit links |

### Light Theme ("Warm Paper", Classroom & Daylight)
| Token | Value | Role |
|---|---|---|
| `--paper-50` | `#F4EDE0` | Warm newsprint / paper ground |
| `--paper-100` | `#EAE1D1` | Ticket surfaces and card elevation |
| `--paper-200` | `#DCD1BE` | Borders and dashed tear lines |
| `--paper-ink` | `#1B1A17` | High-contrast body text |
| `--paper-muted` | `#6B655B` | Subdued metadata text |
| `--sodium-dark`| `#B8650A` | Accessible contrast amber for paper |

---

## 3. Typography Scale & Fonts

Self-hosted in `frontend/fonts/` with `@font-face` and `font-display: swap`:
1. **Instrument Serif** (Regular & Italic):
   - Role: Display headlines, big numerals, and route duration highlights.
   - Italic styling used for atmospheric emphasis (*"still awake"*).
2. **Bricolage Grotesque** (Variable):
   - Role: UI text, labels, buttons, explainer prose.
3. **Martian Mono**:
   - Role: Point values, times, distances, coordinates, confidence tags.

### Fluid Type Scale
- `--font-display`: `clamp(2.5rem, 5vw, 4.25rem)` (Line-height: 1.05)
- `--font-title-lg`: `clamp(1.75rem, 3vw, 2.5rem)` (Line-height: 1.15)
- `--font-title-md`: `clamp(1.25rem, 2vw, 1.65rem)` (Line-height: 1.25)
- `--font-body-lg`: `1.125rem`
- `--font-body-md`: `0.9375rem`
- `--font-body-sm`: `0.8125rem`
- `--font-mono-md`: `0.875rem`
- `--font-mono-sm`: `0.75rem`

---

## 4. Signature Components

### 1. Transit Ticket Route Card
- Notched semi-circular cutouts at side margins.
- Dashed tear line (`border-top: 2px dashed var(--divider)`) separating trip overview from the 9-component breakdown.
- Martian Mono stamp with route mode, departure timestamp, and Data Confidence badge.

### 2. Lamp-Dial Night Score Gauge
- Semi-circular radial arc with tick marks every 10 points.
- Huge Instrument Serif numeral (`0–100`) at dial center.
- Color dynamically transitions:
  - `< 35`: Coral (`--coral`)
  - `35 – 65`: Sodium Amber (`--sodium`)
  - `> 65`: Mint (`--mint`)

### 3. Light-Meter Pips (Score Rows)
- Replaces generic progress bars with a row of discrete square pips (1 pip per point).
- Earned points glow with amber luminescence; remaining pips stay dark charcoal.
- Tapping any row highlights the associated feature on the MapLibre canvas (e.g. flashing the longest dark gap in red).

### 4. Glowing Lit Streets on MapLibre
- Dual-layer vector polylines:
  - Under-layer: 12px wide blurred glowing line (`rgba(255, 181, 71, 0.4)` or `rgba(111, 227, 181, 0.4)`).
  - Top-layer: 4px crisp vector line.
- Clustered POI source at low zoom to eliminate visual clutter; unclustered priority pins at high zoom.

### 5. Rebuilt AI Lab Storyboard & Heatmap
- 7-step horizontal storyboard illustrating the pipeline from raw query to scored routes.
- Amber-to-ink color ramp on attention canvas with crosshairs and token coordinates.
- Upper triangle causal mask labeled with explicit architectural meaning.
- Honest disclaimer noting LLM "attention sinks" and positional artifacts.

---

## 5. Motion Guidelines
- Single page-load choreography in hero:
  - Text lines reveal with staggered `animation-delay: 100ms, 250ms, 400ms`.
  - SVG route polyline draws itself using `stroke-dashoffset`.
  - Streetlamps switch on sequentially.
- Map and card reveals use `IntersectionObserver`.
- Strictly adheres to `@media (prefers-reduced-motion: reduce)` by disabling transitions and setting `animation: none`.
