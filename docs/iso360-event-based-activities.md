# ISO360 — Event-Based Activities

## The Problem They Solve

Most compliance failures don't happen at the annual audit.
They happen in the middle of the year when something changes and nobody updates the compliance records.

A new developer joins. Nobody did the background check the ISO standard requires.
A new SaaS tool gets approved. Nobody documented the vendor security review.
A server gets breached. Nobody followed the incident response procedure.

Six months later the auditor asks: "Show me your background check records for all staff hired this year."
The customer has nothing. That's a nonconformity. That risks certification.

**Event-based activities are the safety net that catches these moments.**

---

## How It Works

Calendar activities (monthly/quarterly/yearly) fire automatically on a schedule.

Event-based activities fire when something real happens in the business:

| When this happens... | ISO360 creates a task for... |
|---|---|
| New employee is hired | Background verification + NDA signing (Clause 6.1, 6.6) |
| New SaaS/cloud vendor added | Vendor security assessment + contract review (Clause 5.22, 5.23) |
| A security incident occurs | Incident response procedure + lessons learned (Clause 5.25–5.27) |
| A system change is deployed | Change risk assessment + approval record (Clause 8.1) |
| An audit finding is raised | Corrective action plan + root cause analysis (Clause 10.2) |

---

## Why It Matters to the Customer

Without this, the customer has to remember to do these things themselves.
They never do. Real companies are busy.

With ISO360 event-based activities:
- Admin sees the incident happened → opens ISO360 tab → clicks "Trigger" → customer gets a task with exact steps and evidence fields
- Customer follows the procedure, uploads proof
- Evidence exists when the auditor asks 12 months later

**The customer isn't just certified once. They're demonstrably operating the ISMS continuously.**
That's the difference between a certificate on the wall and an actual security program.

---

## Current Implementation Status

Event-based activities are fully defined and personalized in `customer_documents` (33 per customer for ISO 27001:2022). They sit with `next_due_date = NULL`.

**Phase 4** will add a "Trigger" button in the ISO360 admin tab that creates a `customer_task` on demand.

**Future:** Webhook integrations (HR system, ticketing, cloud provider events) can auto-trigger the right activity without admin involvement.

---

## Example: Real Audit Scenario

**Without ISO360:**
Auditor: "Show me background checks for the 4 people hired in Q2."
Customer: "We... did them verbally. We don't have records."
Result: Major nonconformity. Corrective action required. Possible suspension of certificate.

**With ISO360:**
When each hire happened, admin triggered "Conduct candidate background verification".
Customer followed 5 steps, uploaded HR approval + check result.
Auditor asks. Customer pulls up 4 completed tasks with timestamps and uploaded evidence.
Result: Full conformance. Zero findings.
