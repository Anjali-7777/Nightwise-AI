# NightWise AI

NightWise AI is an offline-first route comparison demonstrator. It ranks routes using mapped environmental-support indicators (not crime probability and not a safety guarantee), explains trade-offs, and interprets natural-language preferences with a task-specific model interface.

## Quick start (Windows PowerShell)

```powershell
$py = 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe ml\scripts\generate_dataset.py
& .\.venv\Scripts\python.exe -m backend.app.server
```

Open http://127.0.0.1:8000. If optional packages are not installed, the standard-library server and deterministic model fallback still work. With PyTorch/FastAPI/NetworkX installed, the optional implementations are available.

## Tests and training

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe ml\scripts\train.py --epochs 5
```

The generated dataset is synthetic and must not be presented as real user data. The sample graph is a clearly labelled demonstration region. External map extracts and tiles are optional downloads; the included demo is fully offline.

## Architecture

`backend/app/routing.py` creates candidate routes over a small local graph, `scoring.py` computes transparent normalized indicators, and `agent.py` validates model output before calling an allowlisted tool. `ml/src/transformer.py` contains a from-scratch PyTorch Transformer encoder when PyTorch is available; `ml/src/inference.py` provides a deterministic offline fallback otherwise. `frontend/` contains the React/Vite source scaffold, while `backend/app/static/` is a dependency-free runnable dashboard for environments without npm packages.

Limitations: the demo graph is not a live map, opening hours and live conditions are unknown unless supplied by a future data importer, and mapped absence is not evidence of danger.
