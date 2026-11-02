# DocSpace

FastAPI project scaffold for the DocSpace API.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive docs are at `/docs`.
The initial `/health` endpoint returns the service status. Authentication, database,
and migration modules are scaffolds ready for implementation.