# Spec Workspace Frontend

A routed React/TypeScript frontend for the uploaded FastAPI backend.

## Run

```bash
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000`.

Override it with:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Backend endpoints used

- `POST /api/run-agents`
- `POST /api/run-coverage`
- `POST /api/prioritise-vplan`
- `GET /api/download/{filename}`
- `GET /api/usage-chart/{filename}`

The inconsistency and source-specification extraction pages are intentionally marked as not yet connected because those endpoints are not present in the supplied backend.


## vPlan categorisation and prioritisation

The vPlan viewer expects every test to contain `category` and `priority`. The Prioritise dialog sends `vplan_file`, `priority_1_categories`, and `priority_2_categories` to `/api/prioritise-vplan`.
