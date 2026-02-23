# Files Guide - What's What

## Read These First (Morning):

### 1. START_HERE.md
**5 min read**
Quick summary, test steps, what's next

### 2. MORNING_CHECKLIST.md
**Follow step-by-step**
Testing guide with commands

### 3. GOOD_MORNING.md
**10 min read**
Overview of all changes, test instructions

---

## Reference Documents:

### CORRECT_APPROACH.md
**Full design document**
- System architecture
- Database schema
- How semantic mapping works
- 5-phase implementation plan

### MORNING_PROGRESS_REPORT.md
**Detailed progress**
- What was done (3 phases)
- Files changed
- Test instructions
- Next steps

### CLEANUP_PLAN.md
**Keep vs Delete**
- What code was kept
- What was deleted
- What was created new

---

## Code Files Changed:

### Database:
- `db/init/005_correct_approach_rebuild.sql` - NEW migration

### AI Service:
- `ai-service/agents/template.py` - REWRITTEN
- `ai-service/db_client.py` - Updated
- `ai-service/stream_consumer.py` - Updated

### Backend:
- `backend/app/routes/catalog_templates.py` - REWRITTEN

### Backed Up:
- `backend/app/routes/catalog_templates.py.OLD` - Old version

---

## Utility Scripts:

### verify_database.py
**Quick database check**
Run to verify tables exist

### tests/test_new_structure.py
**Pytest tests**
Automated verification

---

## Where to Start:

**Morning:**
1. Read START_HERE.md
2. Follow MORNING_CHECKLIST.md
3. Test upload

**Later:**
1. Read CORRECT_APPROACH.md
2. Plan frontend updates

---

**All files are in:** `DNA/` directory
**Documentation ends with:** `.md`
**Code files are in:** subdirectories
