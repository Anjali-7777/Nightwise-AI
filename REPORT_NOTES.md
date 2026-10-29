# NightWise AI — Viva & Project Report Notes

Concise, high-yield bullet points for oral examination (viva voce) and project report documentation.

---

## 1. Core Architectural Decisions

### Why LLM + Deterministic Scoring (Instead of LLM Guessing Safety Scores)?
- **Accountability & Trust**: Personal safety cannot rely on generative model hallucinations or ungrounded predictions. If an LLM hallucinates an arbitrary score of "92/100", there is no mathematical justification.
- **Explainability**: Every point in our 0–100 Night Activity Score is traced to tangible, verifiable indicators: open shops, CCTV cameras, help points, lit streets, and continuous coverage.
- **Separation of Concerns**:
  - **LLM Role**: Acts as an intuitive human-computer interface (orchestrator). It parses ambiguous natural language requests (including Hinglish and slang), calls validated tools, and synthesizes 3–4 sentence trade-off summaries.
  - **Python Heuristic Role**: Executes rigorous metric resampling (every 50 meters), dynamic arrival-time opening hours checks, and non-linear dark-gap penalties.
- **Guardrail against Hallucinations**: Generated summaries pass through a numerical validator (`validate_explanation_numbers`). If the LLM generates a metric that does not exist in the raw graph data, the app smoothly falls back to a deterministic grounded template.

---

## 2. Transformer & Attention Mechanics (Syllabus Mapping)

### Where Transformers Appear in NightWise AI
1. **Agent Task Model (`qwen2.5:0.5b-instruct`)**:
   - Executes zero-temperature JSON-constrained intent extraction.
   - Grounded trade-off summarization.
2. **From-Scratch PyTorch Implementation (`backend/attention/scratch_attention.py`)**:
   - Implements **Sinusoidal Positional Encoding** ($PE_{(pos, 2i)} = \sin(\dots)$, $PE_{(pos, 2i+1)} = \cos(\dots)$).
   - Implements **Scaled Dot-Product Attention** $\text{Softmax}\left(\frac{QK^T}{\sqrt{d_k}} + M\right)V$.
   - Implements **Multi-Head Attention (MHA)** with linear projections $W_Q, W_K, W_V$, head splitting, concatenation, and output projection $W_O$.
   - Enforces a causal lower-triangular mask ($M_{ij} = -\infty$ for $j > i$).
3. **Eager HuggingFace Attention Visualizer (`backend/attention/hf_attention.py`)**:
   - Loads `Qwen/Qwen2.5-0.5B-Instruct` with `attn_implementation="eager"` and `output_attentions=True`.
   - Surfaces all 24 layers and 14 attention heads into an interactive HTML5 Canvas heatmap.

### Why Attention Heatmaps Matter in Navigation
- **Interpreting User Intent**: Shows how query tokens attend to key modifiers (e.g., "walking" receives attention from "safest", adjusting weights to pedestrian mode; "2 AM" prompts arrival time dynamic filtering).
- **Head Specialization**:
  - Lower layers capture syntactic structure and immediate token proximity.
  - Intermediate layers capture semantic bindings (linking "office" with origin and "home" with destination).
  - Upper layers synthesize global sentence intent for next-token generation.

---

## 3. The Night Activity Score Formula (v2 Engine)

$$\text{Score} = \max\left(0, \min\left(100, \sum_{i=1}^{9} \text{Points}_i \times \text{RescaleFactor}\right)\right)$$

### 9 Deterministic Components Table
| # | Component | Walking Max Pts | Driving Max Pts | Saturation Factor ($k$) | Mathematical Formulation / Rationale |
|---|---|---|---|---|---|
| **1** | **Open Places Along Route** | **20.0 pts** | **15.0 pts** | $k = 8.0$ places/km | $W_1 \times (1 - \exp(-\text{density}/8.0))$; verified open at arrival time |
| **2** | **Open Help Points** | **15.0 pts** | **10.0 pts** | $k = 2.5$ points/km | $W_2 \times (1 - \exp(-\text{density}/2.5))$; police, hospitals, 24/7 pharmacies |
| **3** | **Distance on Main Roads** | **10.0 pts** | **20.0 pts** | Linear Ratio | $W_3 \times \frac{\text{main\_road\_samples}}{\text{total\_samples}}$; arterial roads prioritize visibility |
| **4** | **Open Transport Locations** | **10.0 pts** | **10.0 pts** | $k = 3.0$ stops/km | $W_4 \times (1 - \exp(-\text{density}/3.0))$; bus stops, metro gates, transit hubs |
| **5** | **Fewer & Shorter Dark Gaps** | **15.0 pts** | **10.0 pts** | Composite Penalty | $W_5 \times (1 - \min(1.0, 0.5 \cdot r_{\text{longest}} + 0.3 \cdot r_{p90} + 0.2 \cdot (1 - \text{evenness})))$ |
| **6** | **Surveillance Cameras** | **10.0 pts** | **5.0 pts** | $k = 4.0$ cams/km | $W_6 \times (0.5 \cdot (1 - \exp(-\text{dens}/4)) + 0.5 \cdot \text{spread}_{200m})$ |
| **7** | **Street Lighting** | **10.0 pts** | **10.0 pts** | $k = 15.0$ lamps/km | $W_7 \times (0.6 \cdot \text{lit\_coverage} + 0.4 \cdot (1 - \exp(-\text{lamps}/15)))$ |
| **8** | **Fewer Turns / Simple Route**| **5.0 pts** | **10.0 pts** | Divisor = 6 / 4 | $W_8 \times \exp(-\text{turns\_per\_km} / \text{divisor})$; Douglas-Peucker $\ge 45^\circ$ angles |
| **9** | **Active Surroundings** | **5.0 pts** | **10.0 pts** | Threshold = 300m / 500m | $W_9 \times (1 - \text{isolation\_share}) - \text{penalty}$; avoids industrial / desolate buffers |
| **Total** | | **100.0 pts** | **100.0 pts** | | Sums to exactly 100 max points |

### Key Mathematical Defenses for Viva:
1. **Saturation Curvature**: Uses $1 - \exp(-\text{density}/k)$. First few places contribute heavily to peace of mind; additional places exhibit diminishing returns.
2. **Cluster De-Duplication**: Venues within a 40m radius are grouped as $1.0 + 0.3 \times \text{extra}$. A 20-shop shopping mall cannot disguise a solitary, isolated route.
3. **Deep-Night Factor**: Non-essential daytime shops receive an automatic 0.6x dampener between 01:00 and 04:00 AM.
4. **Fair Comparison Rescaling (Rule 9)**: When municipal lighting tags are $< 15\%$ and zero lamps are mapped, the lighting component is marked unavailable and remaining components are proportionally rescaled to 100: $\text{RescaleFactor} = \frac{100.0}{\sum_{c \in \text{Available}} W_c}$.

---

## 4. Data Layer Audit (Before vs. After OpenStreetMap Migration)

Evaluated on 3 urban corridors at 2:00 AM walking:

| Metric | Bengaluru (3.97 km) | Hyderabad (3.88 km) | Delhi (3.32 km) |
|---|---|---|---|
| **Geoapify POIs (Before)** | 50 | 50 | 50 |
| **OSM Community POIs (After)** | **216** | **216** | **240** |
| **Total Merged POIs** | **271** (+453%) | **274** (+448%) | **291** (+482%) |
| **Density (POIs / km)** | **68.3 / km** (was 12.3) | **70.6 / km** (was 12.9) | **87.7 / km** (was 15.1) |
| **Share with Opening Hours** | **80.8%** (was 14.3%) | **79.2%** (was 30.0%) | **85.6%** (was 26.0%) |
| **Surveillance Cameras Mapped** | **90** (was 9) | **90** (was 8) | **100** (was 9) |
| **Street Lamps Mapped** | **180** (was 0) | **180** (was 0) | **144** (was 0) |
| **Lit Road Coverage** | **100.0%** (was 0.0%) | **100.0%** (was 0.0%) | **100.0%** (was 0.0%) |

---

## 5. Empirical 9-Component Ablation Results

Evaluated across 3 candidate metropolitan corridors (Bengaluru, Delhi, Nagpur) at 2:00 AM walking:

| # | Component Name | Base Weight | Direct Contribution (BLR / DEL / NAG) | Rescaled Score Delta (Mean) | Primary Impact Rationale |
|---|---|---|---|---|---|
| 1 | Open places along route | 20.0 pts | 14.3 / 14.9 / 9.8 pts | **+1.5 pts** (13.0 base pts) | Active eyes on street; critical social presence |
| 2 | Open help points | 15.0 pts | 8.6 / 9.5 / 4.9 pts | **+3.6 pts** (7.7 base pts) | Emergency stations; essential psychological reassurance |
| 3 | Distance on main roads | 10.0 pts | 8.1 / 8.6 / 6.9 pts | **-0.7 pts** (7.9 base pts) | Wide thoroughfares; vehicular visibility |
| 4 | Open transport locations | 10.0 pts | 5.1 / 5.7 / 4.9 pts | **+2.3 pts** (5.2 base pts) | Lit transit nodal connectivity |
| 5 | Fewer & shorter dark gaps | 15.0 pts | 14.9 / 14.9 / 13.7 pts | **-4.4 pts** (14.5 base pts) | Penalizes long dark gaps & blindspots |
| 6 | Surveillance cameras | 10.0 pts | 8.1 / 9.2 / 4.8 pts | **-0.1 pts** (7.4 base pts) | Surveillance deterrence across corridor |
| 7 | Street lighting | 10.0 pts | 6.6 / 6.6 / 4.9 pts | **+1.4 pts** (6.0 base pts) | Street lamp illumination & lit carriageways |
| 8 | Fewer turns / simple route | 5.0 pts | 5.0 / 5.0 / 5.0 pts | **-1.4 pts** (5.0 base pts) | Route simplicity & low disorientation risk |
| 9 | Active surroundings | 5.0 pts | 5.0 / 5.0 / 5.0 pts | **-1.4 pts** (5.0 base pts) | Avoidance of industrial / desolated buffers |

---

## 6. Weight Sensitivity Analysis (±20% Weight Perturbation)

Evaluated across 5 real-world corridor pairs (Fastest back-lane vs Safest arterial) in Bengaluru, Delhi, Nagpur, Hyderabad, and Mumbai:

| Component Tested | Nominal Weight | +20% Perturbed | -20% Perturbed | Ranking Flips (+20%) | Ranking Flips (-20%) | Stability Index |
|---|---|---|---|---|---|---|
| **open_places** | 20.0 pts | 24.0 pts | 16.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **help_points** | 15.0 pts | 18.0 pts | 12.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **main_roads** | 10.0 pts | 12.0 pts | 8.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **transport** | 10.0 pts | 12.0 pts | 8.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **gaps** | 15.0 pts | 18.0 pts | 12.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **cameras** | 10.0 pts | 12.0 pts | 8.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **lighting** | 10.0 pts | 12.0 pts | 8.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **turns** | 5.0 pts | 6.0 pts | 4.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |
| **surroundings** | 5.0 pts | 6.0 pts | 4.0 pts | 0 / 5 (0.0%) | 0 / 5 (0.0%) | **100.0%** |

- **Total Evaluations**: 90 pairwise comparisons.
- **Total Ranking Flips**: **0 / 90 (0.0%)**.
- **Overall System Ranking Stability**: **100.0%**.
- **Conclusion**: The "Safest" arterial corridor decisively maintains superior environmental support over dark back-alleys even under severe calibration perturbations, proving the robustness of the v2 scoring weights.

---

## 7. Limitations & Ethical Disclaimers
1. **Absence of Mapping $\ne$ Danger**: Missing OSM tags (e.g. unmapped streetlights) mean a stretch is treated as *unknown*, not inherently hazardous.
2. **Guidance, Not a Safety Guarantee**: The system provides comparative indicators so users can weigh travel time against environmental support. The application never makes the decision for the user.
