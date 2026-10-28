# NightWise AI 🌙

**An offline-first route-comparison demonstrator with a custom-trained Transformer interface**

NightWise AI is a student project exploring how a task-specific Transformer, a controlled Python agent, graph-based route planning, and mapped environmental indicators can work together in a local web application.

The application is designed to compare routes using available information such as distance, estimated travel time, road characteristics, and other mapped indicators. Its score is an environmental-support estimate—not a crime prediction or a guarantee of personal safety.

> **Project status:** Prototype / under development. Features depend on the installed optional packages and the data available locally. The included sample graph is a demonstration region, not a live city map.

## Contents

- [Project goals](#project-goals)
- [Features and current scope](#features-and-current-scope)
- [Technology stack](#technology-stack)
- [Repository layout](#repository-layout)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Setup on Windows](#setup-on-windows)
- [Run the application](#run-the-application)
- [Generate data and train the model](#generate-data-and-train-the-model)
- [Run tests](#run-tests)
- [OpenStreetMap and offline operation](#openstreetmap-and-offline-operation)
- [Responsible use and limitations](#responsible-use-and-limitations)
- [Contributing](#contributing)
- [Future work](#future-work)
- [Acknowledgements](#acknowledgements)

## Project goals

1. Provide an interactive way to compare candidate routes.
2. Implement transparent route-feature scoring in Python.
3. Train a small task-specific NLP model from randomly initialized weights rather than using pretrained LLM weights.
4. Connect model predictions to a Python agent with validated, allowlisted tools.
5. Keep the core demonstration usable locally without paid AI inference APIs.
6. Document model and routing limitations honestly.

## Features and current scope

The repository includes:

- A Python backend with server, agent, routing, and scoring modules.
- A dependency-light dashboard served from `backend/app/static/`.
- A React/Vite frontend source scaffold in `frontend/`.
- A PyTorch Transformer implementation in `ml/src/transformer.py`.
- An inference module with a deterministic fallback in `ml/src/inference.py`.
- A synthetic route-request dataset generation script.
- A model training script.
- Automated core tests.
- A small demonstration graph for offline demonstration.

The included sample graph is intentionally small. It is useful for development and demonstrations, but it is not a replacement for a full regional OpenStreetMap street network.

## Technology stack

| Component | Technology | Role |
|---|---|---|
| Backend | Python | Application logic |
| Web server / API | Project server; FastAPI/Uvicorn dependencies are listed | Serve the application and backend endpoints |
| NLP model | PyTorch | Implement and train the custom Transformer when installed |
| Routing | NetworkX | Graph-based route calculations when installed |
| Frontend scaffold | React, TypeScript, Vite | Frontend development |
| Map ecosystem | Leaflet / React Leaflet dependencies | Potential interactive map rendering |
| Data | JSONL and local graph data | Training examples and route demonstration data |
| Tests | Python `unittest` discovery | Core project tests |

The dependency list and available runtime determine which optional implementations are active. The React/Vite source scaffold and the dependency-free static dashboard are separate frontend paths; use the startup method that matches the current implementation.

## Repository layout

```text
Nightwise-AI/
├── backend/
│   ├── app/
│   │   ├── static/
│   │   │   ├── app.css
│   │   │   ├── app.js
│   │   │   └── index.html
│   │   ├── agent.py
│   │   ├── routing.py
│   │   ├── scoring.py
│   │   └── server.py
│   └── __init__.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       └── main.tsx
├── ml/
│   ├── checkpoints/
│   │   └── metrics.json
│   ├── data/
│   │   └── route_requests.jsonl
│   ├── scripts/
│   │   ├── generate_dataset.py
│   │   └── train.py
│   └── src/
│       ├── inference.py
│       └── transformer.py
├── tests/
│   └── test_core.py
├── .env.example
├── requirements.txt
└── README.md
```

## How it works

### 1. Route planning

The routing module builds or loads the project's local demonstration graph and computes candidate routes when the graph supports the requested origin and destination. Route details are then passed to the scoring module.

### 2. Environmental-support scoring

The scoring module computes route indicators from the data actually available in the graph. The exact features and weights should be inspected in `backend/app/scoring.py` and documented alongside any changes.

A score is a comparative heuristic. It must not be presented as a verified safety rating, crime probability, or guarantee.

### 3. Custom Transformer and inference

The Transformer code in `ml/src/transformer.py` is intended to implement a small model with randomly initialized parameters. The inference module in `ml/src/inference.py` provides a deterministic fallback for environments where the learned model is unavailable.

The project is task-specific: it aims to interpret a limited set of route-planning requests, not to act as a general-purpose chatbot.

### 4. Agent and tool validation

The agent in `backend/app/agent.py` connects an interpreted request to allowed application functions. Model output should be validated before any tool is executed. The model must never be permitted to run arbitrary shell commands or unrestricted Python code.

## Requirements

- Windows, macOS, or Linux.
- Python compatible with the versions required by `requirements.txt`.
- Git for cloning and collaboration.
- Internet access for initial dependency installation.
- Optional Node.js/npm for working on the React/Vite frontend.
- Sufficient memory for the selected training configuration.

A dedicated GPU is not required for a small model, although training can take longer on CPU.

## Setup on Windows

### 1. Clone the repository

```powershell
git clone https://github.com/Anjali-7777/Nightwise-AI.git
cd Nightwise-AI
```

### 2. Create and activate a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell prevents virtual-environment activation, call the environment's Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

### 3. Install Python dependencies

```powershell
python -m pip install -r requirements.txt
```

The repository lists FastAPI, Uvicorn, PyTorch, NetworkX, NumPy, and pytest. If a package installation fails, use a compatible Python version and follow the official installation instructions for that package. PyTorch CPU installation instructions are available at https://pytorch.org/get-started/locally/.

### 4. Configure environment variables

Copy the example file if you need local overrides:

```powershell
Copy-Item .env.example .env
```

Never commit `.env` or any file containing passwords, access tokens, or API secrets. The example configuration should contain placeholders or non-secret defaults only.

## Run the application

From the repository root, with the virtual environment active:

```powershell
python -m backend.app.server
```

Open:

**http://127.0.0.1:8000**

The repository README originally documents a standard-library server and deterministic fallback, with optional package-backed functionality when dependencies are installed. If the startup command or port changes, update this section to match the actual server configuration.

### React/Vite frontend

The repository also contains a frontend scaffold. To install its dependencies:

```powershell
cd frontend
npm install
npm run dev
```

Use the local URL printed by Vite. The React/Vite development server may use a different port from the Python server. Check the current implementation and API configuration before assuming the two frontends are interchangeable.

## Generate data and train the model

Return to the repository root before running the ML scripts.

### Generate the task dataset

```powershell
python ml/scripts/generate_dataset.py
```

The generated route-request examples are synthetic. Do not describe them as real user conversations or real-world observations.

### Train the Transformer

```powershell
python ml/scripts/train.py --epochs 5
```

Training behavior depends on the current script and whether PyTorch is installed. Inspect the script's available command-line arguments before changing the configuration. Run training separately from starting the web server; do not retrain on every application startup.

After training, record the actual configuration, dataset split, training/validation losses, and held-out evaluation metrics. Never publish fabricated model performance values. The checked-in `ml/checkpoints/metrics.json` may describe fallback evaluation rather than a learned checkpoint; read its note before interpreting its metrics.

## Run tests

From the repository root:

```powershell
python -m unittest discover -s tests -v
```

The project also lists pytest as a dependency. If the tests are pytest-compatible, you can additionally run:

```powershell
python -m pytest -q
```

Record the actual test output and resolve failures before claiming that all tests pass.

## OpenStreetMap and offline operation

OpenStreetMap (OSM) can provide road and geographic data for a selected region.

Useful resources:

- OpenStreetMap: https://www.openstreetmap.org/
- Export tool: https://www.openstreetmap.org/export
- Geofabrik regional extracts: https://download.geofabrik.de/
- OSMnx documentation: https://osmnx.readthedocs.io/

A full offline route-planning setup requires the required road graph and feature data to be stored locally. A full offline visual map additionally needs local map tiles or another locally available basemap.

These are separate capabilities:

- **Local route calculation:** can work offline when graph data is available.
- **Local model inference:** can work offline when code, vocabulary, checkpoint, and dependencies are present.
- **Visual basemap:** may still require internet unless local tiles are configured.
- **Initial setup:** may require internet to download packages and regional data.

Do not bulk-download public OpenStreetMap standard tiles. Follow the tile provider's usage policy and provide required OpenStreetMap attribution.

## Responsible use and limitations

- Mapped features can be incomplete or outdated.
- The sample graph is a demonstration graph, not a full city map.
- Mapped businesses are not assumed to be open unless verified opening-hours data is available.
- Missing mapped features do not prove that a location is dangerous.
- The environmental-support score is not a crime-risk estimate.
- The custom model handles a constrained task and may misunderstand requests.
- Synthetic training examples may not represent real language use.
- Travel times and route conditions may differ from actual conditions.
- The prototype should not be relied upon as the sole basis for personal-safety decisions.

## Contributing

Contributions are welcome.

1. Create a feature branch.
2. Make a focused change.
3. Run the relevant tests.
4. Commit with a descriptive message.
5. Open a pull request for review.

Example:

```powershell
git checkout -b feature/your-change
git add .
git commit -m "Describe your change"
git push -u origin feature/your-change
```

For a shared student project, use pull requests so changes can be reviewed before merging into `main`.

## Future work

- Import a real regional OpenStreetMap extract.
- Improve interactive map rendering and offline tile support.
- Expand and evaluate the task-specific route-request dataset.
- Improve model evaluation and structured-output validation.
- Add route-feature explanations and data completeness indicators.
- Add regression tests for frontend/backend integration.
- Conduct user testing of route preferences and explanations.

## Acknowledgements

NightWise AI uses or is designed to work with open-source tools including PyTorch, NetworkX, FastAPI, React, Vite, Leaflet, and OpenStreetMap. Refer to each dependency's license and documentation before redistributing or deploying the application.

OpenStreetMap data is available under the Open Database License (ODbL). Review attribution and licensing requirements for any map data or tiles used in the project.

## License

No project license is declared here. Add a `LICENSE` file after deciding on a license suitable for the project, your institution's requirements, and the dependencies and datasets you use.

---

**Maintainer:** Anjali-7777  
**Repository:** https://github.com/Anjali-7777/Nightwise-AI  
**Status:** Student project / under development
