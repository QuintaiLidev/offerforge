# Deployment

OfferForge can be deployed as a private MVP for personal study. The intended
cloud use case is simple: open `/app` from a phone browser, review cards, submit
practice attempts, and keep the SQLite database on persistent storage.

HTTP Basic Auth is the minimum protection layer for this private MVP. It is not
a full account system, and it does not provide user registration, sessions, or
per-user permissions.

## Required Environment Variables

Set these variables in the deployment platform before exposing the app:

```text
OFFERFORGE_AUTH_ENABLED=true
OFFERFORGE_AUTH_USERNAME=change-me
OFFERFORGE_AUTH_PASSWORD=change-me
OFFERFORGE_DATABASE_PATH=/persistent/offerforge/offerforge.db
```

Use a strong private username and password. The values above are placeholders.

`OFFERFORGE_DATABASE_PATH` points SQLite at the database file. Locally, the
default remains `data/offerforge.db`; in the cloud, point it at a mounted
persistent disk or volume.

## Start Commands

For production-style deployment, use the platform-provided `PORT`:

```sh
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

For local development:

```sh
python -m uvicorn app.main:app --reload
```

## SQLite Persistence

SQLite is still the storage backend. For cloud deployment, the database file
must live on a persistent disk or volume.

Do not commit the production database to Git. If the platform rebuilds or
replaces the container without a persistent disk, the data will be lost.

## Smoke Test Checklist

After deployment, verify:

- `GET /api/v1/health` returns `200`.
- `/docs` requires authentication when Basic Auth is enabled.
- `/app` requires authentication when Basic Auth is enabled.
- After login, `/app` opens in a phone browser.
- `GET /api/v1/reviews/today` returns data.
- `POST /api/v1/practice-attempts` can submit a practice attempt.
- After an app restart, SQLite data still exists.

## Security Notes

- Cloud deployment must enable Basic Auth.
- Do not use default or placeholder credentials.
- Do not commit `.env`.
- Do not commit database files.
- Do not expose private study records to the public internet without protection.

## Platform Notes

OfferForge is not tied to a single platform. Render, Railway, Fly.io, and
similar services can work if they support:

- Python 3.11+
- Environment variables
- Persistent disks or volumes
- Custom start commands
