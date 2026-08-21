# TrustAI — Multimodal Digital Content Trust & Fake Content Detection System

![TrustAI Banner](documentation/banner.png)

TrustAI is an explainable, multimodal AI system that analyzes **images**, **videos**, and **website URLs** and returns a **Trust Score (0–100)**, Risk Level, Evidence list, and human-readable Explanation. It is designed as a decision-support tool — results are probabilistic risk assessments, not absolute guarantees.

---

## Quick Start

### 1 — Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # then edit .env with your keys / DB URL
uvicorn main:app --reload
```

Backend runs at **http://localhost:8000** — visit `/docs` for the interactive Swagger UI.

### 2 — Train the URL model (demo pipeline, no real dataset needed)

```bash
cd backend
python models/url_model/train_url_model.py
# Saves trained_models/url_model.pkl
```

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**.

---

## Environment Variables (`backend/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./trustai.db` |
| `GOOGLE_SAFE_BROWSING_API_KEY` | Google Safe Browsing v4 | *(optional)* |
| `VIRUSTOTAL_API_KEY` | VirusTotal API v3 | *(optional)* |
| `MAX_IMAGE_MB` | Max upload size for images | `10` |
| `MAX_VIDEO_MB` | Max upload size for videos | `100` |
| `UPLOAD_DIR` | Temp upload directory | `uploads/` |
| `SECRET_KEY` | App secret (future auth) | `changeme` |

---

## Folder Structure

```
trust-ai/
├── frontend/                   # Vite + React + Tailwind CSS
│   └── src/
│       ├── components/         # Reusable UI components
│       ├── pages/              # Route-level pages
│       └── services/api.js     # All API calls
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── api/                    # Route handlers
│   ├── services/               # Business logic & ML inference
│   ├── models/                 # Training scripts & feature extractors
│   ├── explanation/            # Evidence & Explanation Engine
│   ├── database/               # SQLAlchemy ORM
│   └── utils/                  # Validation & preprocessing helpers
├── datasets/
│   └── url/generate_demo_data.py  # Synthetic URL dataset for pipeline testing
├── trained_models/             # Saved model artifacts (gitignored for large files)
├── notebooks/                  # Jupyter notebooks for EDA
└── documentation/              # Report, diagrams, screenshots
```

---

## Training Your Own Models

### URL Model
```bash
# 1. Generate synthetic demo data (or supply your own CSV)
python datasets/url/generate_demo_data.py

# 2. Train
python backend/models/url_model/train_url_model.py
```
Supply a real labeled URL dataset (e.g., PhishTank + DMOZ/Alexa) for production-quality results.

### Image Model (EfficientNet-B0 fine-tuning)
```bash
# Prepare dataset in this structure:
# datasets/image/train/{real,ai_generated}/
# datasets/image/validation/{real,ai_generated}/
# datasets/image/test/{real,ai_generated}/

python backend/models/image_model/train_image_model.py
```

### Video / Deepfake Model
```bash
# Prepare frame-level dataset:
# datasets/video/train/{real,fake}/  (pre-cropped face frames)
# datasets/video/test/{real,fake}/

python backend/models/deepfake_model/train_deepfake_model.py
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analyze/image` | Analyze uploaded image |
| `POST` | `/api/analyze/video` | Analyze uploaded video |
| `POST` | `/api/analyze/url` | Analyze a URL |
| `GET` | `/api/analysis/{id}` | Retrieve analysis by ID |
| `GET` | `/api/history` | Retrieve analysis history |
| `GET` | `/api/health` | Health check |

Full request/response schemas available at `http://localhost:8000/docs`.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python 3.10+ + FastAPI + Uvicorn |
| ML | PyTorch, scikit-learn, XGBoost |
| Vision | Transformers, torchvision, OpenCV |
| Explainability | SHAP, rule-based engine |
| Database | SQLAlchemy (SQLite default / PostgreSQL) |
| External Intel | Google Safe Browsing v4, VirusTotal v3 |

---

## Limitations

- AI detectors can produce false positives and false negatives.
- Trust Score is a probabilistic risk estimate, not factual proof.
- External API quotas and availability affect URL intelligence results.
- Video analysis requires sufficient detectable faces and frames.
- Model performance depends on the quality of training data supplied by the user.

---

## License

MIT — see `LICENSE`.

> **Academic integrity note:** Report only your own measured model metrics. Do not fabricate evaluation results.
