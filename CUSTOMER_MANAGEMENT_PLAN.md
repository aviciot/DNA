# Customer Management - Complete Workflow Plan

## ✅ **Code Cleanup Done:**

- ✅ Removed old `customers.py` → only `customer_management.py` now
- ✅ Removed old `iso_customers.py` → integrated into customer_management
- ✅ Removed old `iso_plans.py` → only `plan_management.py` now
- ✅ Removed old `tasks.py` → only `task_management.py` now
- ✅ Clean API structure in `main.py`

---

## 📋 **Current Customer Management Features:**

### **✅ Already Working:**
1. **List Customers** - Shows all customers with stats
2. **Create Customer** - Modal with name, email, contact, phone, address
3. **Dashboard Stats** - Total customers, plans, tasks, completion rate
4. **Search** - Filter customers by name/email
5. **Status Filter** - Active/Inactive

### **🚧 Need to Implement:**
1. **Edit Customer** - Update customer details
2. **Delete Customer** - Soft delete (set status=inactive)
3. **Manage Customer Plans** - Assign ISOs and templates
4. **View Customer Progress** - See detailed progress

---

## 🎯 **Complete Workflow:**

### **Workflow 1: Create & Setup New Customer**

```
Admin → Customers Tab
  ↓
Click "Create Customer"
  ↓
Fill Form:
  - Name: "Acme Corporation"
  - Email: "admin@acme.com"
  - Contact Person: "John Doe"
  - Phone: "+1234567890"
  - Address: "123 Main St"
  - Send Welcome Email: ✓
  ↓
Click "Create" → Success!
  ↓
Customer appears in list
```

### **Workflow 2: Assign ISO & Templates**

```
Customer Card → Click "Manage Plans" button (Settings icon)
  ↓
Opens: Manage Customer Plan Modal/Page
  ↓
Step 1: Select ISO Standard
  - ISO 27001:2022
  - ISO 9001:2015
  - ISO 14001:2015
  ↓
Step 2: Select Templates for chosen ISO
  - ISMS Policy (ISMS-01)
  - Risk Assessment (ISMS-02)
  - Access Control (ISMS-20)
  - [Checkbox for each template]
  ↓
Step 3: Set Target Date & Plan Name
  - Target Completion: 2026-12-31
  - Plan Name: "Acme ISO 27001 Certification"
  ↓
Click "Generate Tasks"
  ↓
System creates:
  - 1 ISO Plan record
  - N Template assignments
  - M Tasks (from template questions)
  ↓
Success → Show summary:
  "Created plan with 15 templates, 45 tasks generated"
```

### **Workflow 3: Monitor Progress**

```
Customer Card → Click "View Details" button (Eye icon)
  ↓
Opens: Customer Progress Dashboard
  ↓
Shows:
  - Overall Progress: 35%
  - ISO 27001: 40% (12/30 tasks)
  - ISO 9001: 25% (5/20 tasks)
  - Overdue Tasks: 3
  - Pending Reviews: 2
  ↓
Click on ISO card → Expands
  ↓
Shows:
  - Template breakdown
  - Task status (Pending/In Progress/Completed)
  - Timeline
  - Documents uploaded
```

### **Workflow 4: Edit Customer**

```
Customer Card → Click "Edit" button (Edit2 icon)
  ↓
Opens: Edit Customer Modal
  ↓
Pre-filled form with current data
  ↓
Update fields (name, email, contact, etc.)
  ↓
Click "Save Changes"
  ↓
Success → Customer card updates immediately
```

### **Workflow 5: Deactivate Customer**

```
Customer Card → Click "..." menu → "Deactivate"
  ↓
Confirmation dialog:
  "Are you sure? This will hide the customer but keep all data."
  ↓
Click "Confirm"
  ↓
Customer status → "inactive"
  ↓
Customer disappears from list (unless "Show Inactive" filter is on)
```

---

## 🛠️ **Implementation Plan:**

### **Phase 1: Edit & Delete (Quick - 15 min)**

**Add to CustomerManagementV3.tsx:**

1. **Edit Customer:**
   - Create `handleEditCustomer(customer)` function
   - Set `isEditModalOpen = true`
   - Pre-fill form with customer data
   - PATCH `/api/v1/customers/{id}` on save
   - Reload customer list

2. **Delete/Deactivate Customer:**
   - Create `handleDeactivateCustomer(customerId)` function
   - Show confirmation dialog
   - PATCH `/api/v1/customers/{id}` with `{status: "inactive"}`
   - Remove from filtered list

3. **Wire up existing buttons:**
   ```tsx
   <button onClick={() => handleEditCustomer(customer)} ...>
     <Edit2 className="w-5 h-5" />
   </button>
   ```

### **Phase 2: Manage Plans Integration (Medium - 30 min)**

**Option A: Modal Approach**
- Click "Manage Plans" → Opens modal
- Use existing ManageCustomerPlan component
- Pass `customerId` and `customerName` as props
- Modal overlay with close button

**Option B: Navigation Approach**
- Click "Manage Plans" → Navigate to `/admin?tab=manage-plans&customer={id}`
- Pre-select customer in ManageCustomerPlan component
- Cleaner separation

**Recommended: Option A (Modal)** - Faster workflow, no page navigation

### **Phase 3: View Details Integration (Quick - 10 min)**

- Click "View Details" → Opens modal
- Use existing CustomerDashboardSimple component
- Pass `customerId` as prop
- Shows progress dashboard

---

## 📍 **API Endpoints Ready:**

All backend endpoints are already implemented:

### **Customers:**
```
GET    /api/v1/customers           - List all
GET    /api/v1/customers/{id}      - Get one
POST   /api/v1/customers           - Create
PATCH  /api/v1/customers/{id}      - Update
DELETE /api/v1/customers/{id}      - Delete (soft)
```

### **Plans:**
```
POST   /api/v1/plans                           - Create ISO plan
GET    /api/v1/customers/{id}/plans            - List customer plans
POST   /api/v1/plans/{id}/templates            - Add templates
POST   /api/v1/plans/{id}/generate-tasks       - Generate tasks
DELETE /api/v1/plans/{id}/templates/{tid}      - Remove template
```

### **Progress:**
```
GET    /api/v1/customers/{id}/progress         - Get progress
GET    /api/v1/customers/{id}/progress/{iso}   - ISO-specific
```

---

## 🎨 **UI Improvements:**

### **Customer Card Actions:**

Current buttons:
- 👁️ View Details (Eye) → Opens progress modal
- ⚙️ Manage Plans (Settings) → Opens plan assignment modal
- ✏️ Edit (Edit2) → Opens edit customer modal
- 🗑️ Delete → Add dropdown menu with "Deactivate" option

Suggested layout:
```
┌─────────────────────────────────────┐
│ Acme Corporation        [View] [⋮] │
│ admin@acme.com                      │
│ ━━━━━━━━━━━━━━ 35%                 │
│ 3 Plans | 45 Tasks | 15 Completed  │
└─────────────────────────────────────┘

[View] = Eye icon → Progress Dashboard
[⋮] = Dropdown menu:
      - Edit Customer
      - Manage Plans
      - View Progress
      - Deactivate
```

---

## ⚡ **Quick Implementation Order:**

1. **Now (5 min):** Wire up Edit button with modal
2. **Now (5 min):** Add Delete/Deactivate confirmation
3. **Now (10 min):** Connect Manage Plans button to modal
4. **Now (5 min):** Connect View Details to dashboard

**Total: 25 minutes to have full CRUD + Plan management**

---

## 🔄 **Full User Journey:**

```
1. Create Customer
   ↓
2. Manage Plans → Assign ISO + Templates
   ↓
3. System generates tasks
   ↓
4. Customer works on tasks (separate workflow)
   ↓
5. Admin monitors progress (View Details)
   ↓
6. Edit customer if details change
   ↓
7. Deactivate when done
```

---

## 📝 **Next Steps:**

1. Implement Edit Customer functionality
2. Implement Delete/Deactivate functionality
3. Connect Manage Plans button
4. Connect View Details button
5. Test complete workflow
6. Add success/error messages for all actions

**Should we start with the implementation?**
