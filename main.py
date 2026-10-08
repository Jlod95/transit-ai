from fastapi import FastAPI

app = FastAPI(title="Transit AI")

@app.get("/health")
def health():
    return {"status": "ok"}