# Cloud MVP Smoke Test

## Goal

Verify that OfferForge has moved from a local FastAPI study tool to a private
cloud MVP that works from a phone browser.

The smoke test covers the minimum review loop:

```text
Create card -> load /app today review -> show answer -> submit rating -> card state updates
```

## Cloud Environment

- Platform: Render
- Repo: GitHub private repo
- Auth: Basic Auth enabled
- Database: SQLite file on free Render filesystem for MVP smoke test
- Note: The current free environment does not guarantee long-term persistence.
  Production use needs a persistent disk or volume.

## Smoke Test Checklist

- `GET /api/v1/health` returns `200`.
- `/docs` requires Basic Auth.
- `/app` requires Basic Auth.
- Phone browser can open `/app`.
- Swagger can create a test knowledge card.
- `/app` can load a today review card.
- "显示答案" works.
- All five rating buttons can submit:
  - `dont_know`
  - `with_hint`
  - `correct_slow`
  - `correct_explain`
  - `transfer`
- Submitting writes a `PracticeAttempt`.
- Submitting updates `KnowledgeCard` state.
- Submitting refreshes the today queue to empty or the next card.

## Current Limits

- Render free filesystem is not suitable for long-term production study data.
- Persistent disk is not connected yet.
- Formal backups are not configured yet.
- User registration is not implemented.

## Conclusion

Cloud MVP smoke test passed.

OfferForge has completed the minimum loop across local development, GitHub push,
Render deployment, phone access, and five-rating practice submission.
