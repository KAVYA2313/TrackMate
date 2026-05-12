# TrackMate Backend

FastAPI + PostgreSQL backend for TrackMate MVP.

## Run steps

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create PostgreSQL database:

```sql
CREATE DATABASE trackmate_db;
```

Update `.env` database password.

Run backend:

```bash
uvicorn app.main:app --reload
```

Open:

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

Seed demo maths data:

```bash
python -m app.seed.seed_math_questions
```
