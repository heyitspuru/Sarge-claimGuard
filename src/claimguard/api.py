from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ClaimGuard")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    # ponytail: placeholder page; real dashboard is Phase 3 (React + shadcn per design system)
    return "<h1>ClaimGuard</h1><p>API up. Dashboard arrives in Phase 3.</p>"
