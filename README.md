# PIDME — Product Image Discovery & Matching Engine

**BUAL 5860 · Spring 2026 · Auburn University**

PIDME is a lightweight web application that automatically discovers and scores product images for an industrial ball bearings catalog (motion.com). It demonstrates how to combine web scraping, fuzzy text matching, and heuristic scoring to solve a real-world product data enrichment problem.

## What Does It Do?

```
Ball Bearing Catalog (20 products)
        │
        ▼
  DuckDuckGo Image Search
  (3 query variants per product)
        │
        ▼
  Heuristic Scoring Engine
  ├── Title fuzzy matching   (50% weight)
  ├── URL relevance analysis (30% weight)
  └── Domain trust scoring   (20% weight)
        │
        ▼
  Ranked Image Candidates
  with confidence tiers (HIGH / MEDIUM / LOW)
        │
        ▼
  Human Review (approve / reject)
  via API or Swagger UI
```

## Quick Start (GitHub Codespaces — Recommended, Zero Install)

**This is the easiest way.** No installs needed — just a GitHub account (free).

1. Go to **https://github.com/sree181/pidme**
2. Click the green **Code** button → **Codespaces** tab → **Create codespace on main**
3. Wait ~90 seconds for the environment to build
4. The backend and frontend start automatically
5. A notification will pop up saying **"Port 5173 is available"** — click **Open in Browser**
6. You'll see the **PIDME Dashboard** with 20 ball bearing products, image thumbnails, scores, and approve/reject buttons

> If you miss the notification, click the **Ports** tab at the bottom of the editor, find port **5173**, and click the globe icon.

## Quick Start (Local)

You need **Python 3.10+** and **Node.js 18+**.

### 1. Clone and navigate

```bash
git clone https://github.com/sree181/pidme.git
cd pidme/src
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows PowerShell
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
npm install
```

### 4. Start the backend (Terminal 1)

```bash
python main.py
```

You should see:

```
INFO: Seeding 20 products...
INFO: Seed complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 5. Start the frontend (Terminal 2)

Open a **second terminal**, navigate to the same folder, activate the venv, and run:

```bash
cd pidme/src
npx vite
```

### 6. Open the dashboard

Open **http://localhost:5173** in your browser — this is the visual dashboard.

The API docs are also available at **http://localhost:8000/docs**.

> **Don't have Node.js?** You can skip steps 3b, 5, and 6. The backend still works on its own — just use the Swagger UI at `http://localhost:8000/docs` instead.

## API Endpoints

Once the app is running, try these in the Swagger UI at `http://localhost:8000/docs`:

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/api/products` | GET | List all products (search, filter, paginate) |
| `/api/products/{id}` | GET | Get one product + its image candidates |
| `/api/stats` | GET | Dashboard stats (coverage %, counts) |
| `/api/product_types` | GET | List unique product types |
| `/api/match/{id}` | POST | Trigger live image search for one product |
| `/api/match/batch` | POST | Trigger image search for all unmatched products |
| `/api/candidates/{id}/approve` | POST | Approve an image candidate |
| `/api/candidates/{id}/reject` | POST | Reject an image candidate |

### Try This Workflow

1. **GET `/api/stats`** — See how many products have images
2. **GET `/api/products`** — Browse the catalog
3. **GET `/api/products/1`** — View a product and its scored image candidates
4. **POST `/api/match/1`** — Run a live DuckDuckGo image search (takes ~5 seconds)
5. **GET `/api/products/1`** — See the new candidates with scores
6. **POST `/api/candidates/{id}/approve`** — Approve the best match

## Project Structure

```
src/
├── main.py              ← FastAPI application (endpoints + background tasks)
├── models.py            ← Database models (Product, ImageCandidate)
├── image_finder.py      ← DuckDuckGo image search + scoring engine
├── seed_data.py         ← 20 real ball bearing products from motion.com
├── seed_candidates.py   ← Pre-discovered image candidates (app works on first run)
├── scraper.py           ← Playwright web scraper for motion.com
├── App.jsx              ← React frontend (product dashboard UI)
├── main.jsx             ← React entry point
├── index.html           ← HTML shell for the frontend
├── vite.config.js       ← Vite dev server config (proxies API to backend)
├── package.json         ← Node.js dependencies (React, Vite)
├── requirements.txt     ← Python dependencies
└── start.sh             ← One-command launcher (backend + frontend)
```

## How the Scoring Engine Works

When you trigger a match (`POST /api/match/{id}`), the engine:

1. **Builds 3 search queries** from the product's manufacturer, part number, and description
2. **Searches DuckDuckGo Images** for each query (up to 8 results per query)
3. **Scores every candidate** on three dimensions:

| Signal | Weight | How It Works |
|--------|--------|--------------|
| **Title relevance** | 50% | Fuzzy string matching (rapidfuzz) between the image's title/alt text and the product's part number, manufacturer, and description |
| **URL relevance** | 30% | Checks if the image URL contains the part number, manufacturer name, or product-related path segments. Penalizes logos, banners, icons. |
| **Domain trust** | 20% | Known industrial domains (skf.com, grainger.com, motion.com) score higher than generic sites |

4. **Computes a composite score** (0–100) and assigns a confidence tier:
   - **HIGH** (≥75): Very likely a correct product image
   - **MEDIUM** (50–74): Plausible, needs human review
   - **LOW** (<50): Unlikely match
5. **Deduplicates** by domain (max 2 per domain) and returns candidates sorted by score

## Seed Data

The app ships with **20 real ball bearing products** from motion.com (SKF, General Bearing, RBC, Kaydon, Thomson, Dodge, Browning) and **pre-discovered image candidates** so the UI has data on first launch. No API calls are needed to see the system in action.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Make sure you activated the virtual environment and ran `pip install -r requirements.txt` |
| Port 8000 already in use | Kill the other process: `lsof -ti:8000 \| xargs kill` (macOS/Linux) |
| DuckDuckGo search returns no results | You may be rate-limited. Wait 30 seconds and try again. The pre-seeded candidates still work. |
| `python` not found | Try `python3` instead of `python`. On Windows, try `py`. |
| `node` or `npm` not found | Install Node.js 18+ from https://nodejs.org. Or skip the frontend and use the Swagger UI. |
| Frontend shows blank page | Make sure the backend is running first (`python main.py` in Terminal 1) |
| Permission errors on pip install | Use the virtual environment (step 2 above) instead of system Python |

## Tech Stack

**Backend (Python):**
- **FastAPI** — Async Python web framework with auto-generated API docs
- **SQLModel** — SQL database ORM (SQLite, zero config)
- **aiosqlite** — Async SQLite driver
- **rapidfuzz** — Fast fuzzy string matching
- **duckduckgo-search** — Web image search (no API key needed)
- **Pillow / imagehash** — Image processing utilities

**Frontend (JavaScript):**
- **React 18** — UI component library
- **Vite** — Fast dev server with hot reload
- **TanStack Query** — Data fetching and caching
- **Axios** — HTTP client
