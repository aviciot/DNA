# DNA Project Development Rules

## Git Discipline
- After EVERY completed feature or fix, immediately run: `git add -A && git commit -m "..."` 
- Never leave working code uncommitted — if the container restarts, uncommitted work is at risk
- Push to remote after each session: `git push`

## File Editing
- ALWAYS edit files on disk (via IDE or file tools), never inside containers via `docker exec`
- The frontend uses a bind mount — disk IS the container for src/ files
- Backend/ai-service containers copy files at build time — disk changes require `docker compose restart <service>`

## Services Under DNA
- `dna-frontend` — Next.js, bind mount: `./dashboard/frontend/src` → `/app/src`, hot-reloads automatically
- `dna-backend` — FastAPI, requires `docker compose restart dna-backend` after code changes
- `dna-auth` — FastAPI, requires `docker compose restart dna-auth` after code changes  
- `dna-ai-service` — Python worker, requires `docker compose restart dna-ai-service` after code changes
- `dna-postgres` — PostgreSQL, schema changes need migration files + `docker compose down -v` for fresh init
- `dna-redis` — Redis, no code

## After Each Session
```
git add -A
git commit -m "describe what was done"
git push
```
