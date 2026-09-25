# Embedded C/C++ Review Assistant

## Run

```bash
cd backend
python -m venv .venv

For windows .venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Test

```bash
cd backend
pytest -q
```

## API

- `GET /api/health`
- `POST /api/review/code`
- `POST /api/review/repository` with a `.zip` file
