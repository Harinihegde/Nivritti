# Nivritti — Ancient Words for Modern Moments

**Live demo:** https://nivritti-uipk.onrender.com — note: free tier may take ~30-60s to load on first visit if idle*

Nivritti is a full-stack web app that connects everyday feelings to Sanskrit concepts using AI.

A user shares a thought or feeling in plain English. The app searches a database of Sanskrit concepts, uses **Google's Gemini AI** to select the single most relevant word for that feeling, then generates a short, warm reflection connecting the two. Users can save meaningful moments and revisit them later.

## How it works

1. **User input** — the user types a thought or feeling on the "explore" page.
2. **Concept matching** — all Sanskrit concepts are fetched from the database, and Gemini is prompted to pick the single best match for the user's input.
3. **AI reflection** — Gemini is prompted a second time to write a short, non-preachy reflection connecting the chosen concept to what the user shared.
4. **Persistence** — every exploration is logged to the database; users can mark meaningful ones as "saved" and view them later on a "my moments" page.

## Tech stack

- **Database:** Supabase (PostgreSQL)
- **AI:** Google Gemini (`gemini-2.5-flash`)
- **Backend (Python version):** FastAPI, Jinja2 templates
- **Backend (original version):** Next.js (TypeScript, App Router)
- **Frontend:** HTML/CSS/JavaScript (Python version) or React (TypeScript version)

This project exists in two parallel implementations — a Next.js/TypeScript version and a Python/FastAPI version — built to demonstrate the same product architecture across two different stacks.

## Running the Python version locally

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`) with:

```
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-anon-key
GEMINI_API_KEY=your-gemini-api-key
```

Then start the server:

```bash
uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000` in your browser.

## Database schema

- **`concepts`** — Sanskrit word, script, meaning, related human experience, a traditional "encounter" passage, and a reflection prompt.
- **`explorations`** — a log of every user interaction: their input, which concept was matched, the AI-generated reflection, and whether it was saved.

## Error handling

The backend gracefully handles failures in the database and AI service (e.g. a paused database, a rate-limited AI call) and returns a clear, specific message to the user instead of crashing — for example, "Could not load concepts. Please try again shortly." Saving a moment is treated as non-critical: if it fails, the user still sees their result, they just can't save that particular one.
