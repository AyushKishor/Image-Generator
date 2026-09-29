# Ask the Compete — AI-powered MVP

## What it does
A conversational competitive-intelligence agent grounded in the FSI AI Master Knowledge Table. It retrieves relevant evidence and, when a Gemini API key is configured, asks a Gemini model to synthesize an executive-friendly response with inline [1], [2] citations mapped to the retrieved evidence.

## Run locally
1. Install Python 3.9+.
2. Open a terminal in this folder.
3. Set `GEMINI_API_KEY` (free key from https://aistudio.google.com/apikey) if you want AI synthesis.
4. Run `python server.py`.
5. Open http://localhost:8787.

Without an API key, the app still works in grounded retrieval mode.

## Deploy on Render
The repo root has a `render.yaml` blueprint. In Render choose New > Blueprint, pick this repo, and add `GEMINI_API_KEY` when prompted.

## Files
- `server.py` — web server, retrieval layer, Gemini integration
- `index.html` — conversational UI
- `knowledge.json` — master structured evidence base
- `rating_framework.json` — parameter-specific rating definitions
- `FSI_AI_Master_Knowledge_Table.xlsx` — source workbook
