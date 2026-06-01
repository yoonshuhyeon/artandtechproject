# atc-backend

Python/FastAPI backend for the atc MVP.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Notes
- WebSocket endpoint: `ws://localhost:8000/ws/{room_code}`
- Create room: `POST /rooms`
# ate
