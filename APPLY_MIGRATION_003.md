# Quick Guide: Apply Migration 003

## What Was Fixed?

✅ Tasks now link to specific templates
✅ Documents tab shows correct tasks per template
✅ No more duplicate tasks across templates

---

## Files Changed (6 files)

### Backend (4 files)
1. ✅ `migrations/003_add_template_id_to_tasks.sql` - Database migration
2. ✅ `run_migration_003.py` - Migration runner script
3. ✅ `app/routes/plan_management.py` - Task generation & API endpoints
4. ✅ `app/services/task_generator_service.py` - Document task generation

### Frontend (1 file)
5. ✅ `src/app/customers/[id]/page.tsx` - Task interface & filtering

### Documentation (1 file)
6. ✅ `MIGRATION_003_SUMMARY.md` - Detailed changelog

---

## Apply Migration - 3 Steps

### Step 1: Start Docker (if not running)
```bash
cd "C:\Users\acohen.SHIFT4CORP\Desktop\PythonProjects\MCP Performance\DNA\dashboard"
docker-compose up -d
```

### Step 2: Run Migration
```bash
cd backend
python run_migration_003.py
```

**Expected output:**
```
✅ Migration 003 completed successfully!
📊 Results:
   - Total tasks: X
   - Tasks with template_id: X
   - Tasks backfilled: X/X
```

### Step 3: Restart Containers
```bash
cd ..
docker-compose restart backend frontend
```

**Wait 30 seconds for containers to fully restart.**

---

## Test It Works

1. Open: http://localhost:3003/customers/5
2. Click **Documents** tab
3. Expand a template (click to expand)
4. **Expected**: Tasks ONLY under their specific template
5. **Before**: All tasks showed under all templates ❌

### Test Checklist
- [ ] Customer workspace loads
- [ ] Documents tab shows ISO plans
- [ ] Can expand templates
- [ ] Tasks appear under CORRECT templates only
- [ ] Task counts accurate (match number of tasks shown)
- [ ] No console errors (F12 → Console)

---

## If Something Goes Wrong

### Check Container Status
```bash
docker-compose ps
```
All should be "Up"

### Check Backend Logs
```bash
docker-compose logs backend --tail=50
```

### Check Frontend Logs
```bash
docker-compose logs frontend --tail=50
```

### Rollback (if needed)
```bash
# Stop containers
docker-compose down

# Rollback git changes
git checkout HEAD -- backend/ frontend/

# Delete migration files
rm backend/migrations/003_add_template_id_to_tasks.sql
rm backend/run_migration_003.py

# Restart
docker-compose up -d --build
```

---

## Commit Changes (After Testing)

Once you verify everything works:

```bash
git add .
git commit -m "Fix template-task linking: add template_id to customer_tasks

- Add template_id column to customer_tasks table
- Update task generation to save template_id
- Update API response to include template_id
- Update frontend filtering to use template_id
- Add migration script with automatic backfill

Result: Tasks now correctly grouped by template in Documents tab"

git push origin main
```

---

## Summary of Changes

**Problem**: Tasks had `plan_id` but not `template_id`
→ All tasks showed under all templates (incorrect)

**Solution**: Added `template_id` column
→ Tasks now link to specific templates (correct)

**Impact**:
- ✅ Accurate task grouping
- ✅ Correct task counts
- ✅ Better user experience
- ✅ No breaking changes
- ✅ Existing data migrated automatically

**Performance**: Same speed (for 8x faster, see `IMPROVED_SCHEMA_DESIGN.md`)

---

## Need Help?

See detailed docs:
- `MIGRATION_003_SUMMARY.md` - Full technical details
- `DATABASE_RELATIONSHIPS.md` - Database structure
- `IMPROVED_SCHEMA_DESIGN.md` - Optional optimizations
