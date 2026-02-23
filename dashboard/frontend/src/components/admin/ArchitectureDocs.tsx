"use client";

import { useState } from "react";
import { Database, GitBranch, Layers, BookOpen, Code2, ArrowRight, ChevronDown, ChevronRight } from "lucide-react";

type Section = "overview" | "tables" | "relations" | "flow" | "examples";

export default function ArchitectureDocs() {
  const [active, setActive] = useState<Section>("overview");
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["core", "ai"]));

  const toggle = (key: string) => {
    setExpanded(prev => {
      const s = new Set(prev);
      s.has(key) ? s.delete(key) : s.add(key);
      return s;
    });
  };

  const tabs: { id: Section; label: string; icon: any }[] = [
    { id: "overview", label: "Overview", icon: BookOpen },
    { id: "tables", label: "Tables", icon: Database },
    { id: "relations", label: "Relations", icon: GitBranch },
    { id: "flow", label: "Data Flow", icon: Layers },
    { id: "examples", label: "Examples", icon: Code2 },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Architecture Documentation</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Information architecture, table relations, and usage examples for the DNA platform.
        </p>
      </div>

      {/* Sub-tabs */}
      <div className="flex space-x-1 border-b border-gray-200 dark:border-gray-700">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              active === t.id
                ? "border-blue-500 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            <t.icon className="w-4 h-4" />
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {active === "overview" && <OverviewSection />}
        {active === "tables" && <TablesSection expanded={expanded} toggle={toggle} />}
        {active === "relations" && <RelationsSection />}
        {active === "flow" && <FlowSection />}
        {active === "examples" && <ExamplesSection />}
      </div>
    </div>
  );
}

function OverviewSection() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { title: "3-Layer Architecture", color: "blue", items: ["customer_profile_data — permanent knowledge base", "customer_placeholders — collection status per plan", "customer_tasks — action items for admins"] },
          { title: "Core Principle", color: "purple", items: ["Placeholder is the atomic unit", "Collect once → fills all documents", "company_name collected for ISO 27001 auto-fills ISO 9001 too"] },
          { title: "Schemas", color: "green", items: ["dna_app — active application schema", "customer — certification data schema", "public — auth users"] },
        ].map(card => (
          <div key={card.title} className={`p-4 rounded-xl border-2 border-${card.color}-200 dark:border-${card.color}-800 bg-${card.color}-50 dark:bg-${card.color}-900/20`}>
            <h4 className={`font-semibold text-${card.color}-900 dark:text-${card.color}-100 mb-3`}>{card.title}</h4>
            <ul className="space-y-1">
              {card.items.map(i => (
                <li key={i} className={`text-sm text-${card.color}-800 dark:text-${card.color}-200 flex items-start gap-2`}>
                  <span className="mt-1 shrink-0">•</span>{i}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <h4 className="font-semibold text-gray-900 dark:text-white mb-3">System Components</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            { label: "Backend", value: "FastAPI · Python 3.12 · Port 8400" },
            { label: "Frontend", value: "Next.js 14 · TypeScript · Tailwind" },
            { label: "Database", value: "PostgreSQL · dna_app schema" },
            { label: "Auth", value: "JWT · localStorage access_token" },
          ].map(c => (
            <div key={c.label} className="p-3 bg-white dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{c.label}</p>
              <p className="font-medium text-gray-900 dark:text-white">{c.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TableGroup({ title, color, tables, expanded, toggle, groupKey }: any) {
  const isOpen = expanded.has(groupKey);
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
      <button
        onClick={() => toggle(groupKey)}
        className="w-full flex items-center justify-between px-5 py-4 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      >
        <span className={`font-semibold text-${color}-700 dark:text-${color}-300`}>{title}</span>
        {isOpen ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
      </button>
      {isOpen && (
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {tables.map((t: any) => (
            <div key={t.name} className="px-5 py-4">
              <div className="flex items-start justify-between mb-2">
                <code className="text-sm font-mono font-bold text-blue-600 dark:text-blue-400">{t.name}</code>
                <span className="text-xs text-gray-500 dark:text-gray-400 ml-4">{t.schema}</span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{t.desc}</p>
              <div className="space-y-1">
                {t.cols.map((c: any) => (
                  <div key={c.name} className="flex items-start gap-3 text-xs">
                    <code className="font-mono text-purple-600 dark:text-purple-400 w-48 shrink-0">{c.name}</code>
                    <span className="text-gray-500 dark:text-gray-400 w-32 shrink-0">{c.type}</span>
                    <span className="text-gray-600 dark:text-gray-300">{c.note}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TablesSection({ expanded, toggle }: { expanded: Set<string>; toggle: (k: string) => void }) {
  const groups = [
    {
      key: "core",
      title: "Core Tables",
      color: "blue",
      tables: [
        {
          name: "dna_app.iso_customers",
          schema: "dna_app",
          desc: "Top-level customer record. Soft-delete via status=inactive. Hard delete cascades everything.",
          cols: [
            { name: "id", type: "SERIAL PK", note: "Auto-increment integer" },
            { name: "name", type: "VARCHAR", note: "Company display name" },
            { name: "email", type: "VARCHAR UNIQUE", note: "Primary contact email" },
            { name: "status", type: "VARCHAR", note: "active | inactive (soft delete)" },
            { name: "created_at", type: "TIMESTAMPTZ", note: "Creation timestamp" },
          ],
        },
        {
          name: "dna_app.customer_iso_plans",
          schema: "dna_app",
          desc: "One plan per customer per ISO standard. Links customer to their certification journey.",
          cols: [
            { name: "id", type: "UUID PK", note: "gen_random_uuid()" },
            { name: "customer_id", type: "INT FK", note: "→ iso_customers.id ON DELETE CASCADE" },
            { name: "iso_standard_id", type: "UUID FK", note: "→ iso_standards.id" },
            { name: "plan_status", type: "VARCHAR", note: "active | completed | on_hold" },
            { name: "target_completion_date", type: "DATE", note: "Optional deadline" },
          ],
        },
        {
          name: "dna_app.customer_documents",
          schema: "dna_app",
          desc: "Generated document instances per customer per template. Tracks fill status.",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "customer_id", type: "INT FK", note: "→ iso_customers.id CASCADE" },
            { name: "plan_id", type: "UUID FK", note: "→ customer_iso_plans.id CASCADE" },
            { name: "template_id", type: "UUID FK", note: "→ catalog_templates.id" },
            { name: "placeholder_fill_status", type: "JSONB", note: "NEW: {key: filled|pending}" },
            { name: "last_auto_filled_at", type: "TIMESTAMPTZ", note: "NEW: last cascade fill time" },
          ],
        },
        {
          name: "dna_app.customer_tasks",
          schema: "dna_app",
          desc: "Action items for admin to collect info. One task per placeholder per plan.",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "customer_id", type: "INT FK", note: "Denormalized for query speed" },
            { name: "plan_id", type: "UUID FK", note: "→ customer_iso_plans.id CASCADE" },
            { name: "placeholder_key", type: "VARCHAR", note: "NEW: links to customer_placeholders" },
            { name: "answer", type: "TEXT", note: "NEW: collected answer text" },
            { name: "answer_file_path", type: "TEXT", note: "NEW: uploaded file path" },
            { name: "answered_via", type: "VARCHAR", note: "NEW: interview | upload | manual" },
          ],
        },
      ],
    },
    {
      key: "ai",
      title: "AI Platform Tables (Migration 005)",
      color: "purple",
      tables: [
        {
          name: "dna_app.customer_profile_data",
          schema: "dna_app",
          desc: "Permanent knowledge base per customer. Collected once, reused across all plans and ISO standards.",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "customer_id", type: "INT FK", note: "→ iso_customers.id CASCADE" },
            { name: "field_key", type: "VARCHAR", note: "e.g. company_name, ceo_name" },
            { name: "field_value", type: "TEXT", note: "The actual collected value" },
            { name: "collected_via", type: "VARCHAR", note: "interview | upload | manual" },
            { name: "UNIQUE", type: "(customer_id, field_key)", note: "One value per field per customer" },
          ],
        },
        {
          name: "dna_app.customer_placeholders",
          schema: "dna_app",
          desc: "Collection status per placeholder per plan. Atomic unit — tracks which templates need each placeholder.",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "customer_id", type: "INT FK", note: "→ iso_customers.id CASCADE" },
            { name: "plan_id", type: "UUID FK", note: "→ customer_iso_plans.id CASCADE" },
            { name: "placeholder_key", type: "VARCHAR", note: "Matches template fillable_sections[].id" },
            { name: "status", type: "VARCHAR", note: "pending | collected | auto_filled" },
            { name: "template_ids", type: "UUID[]", note: "Array of templates needing this placeholder" },
            { name: "UNIQUE", type: "(customer_id, plan_id, placeholder_key)", note: "" },
          ],
        },
        {
          name: "dna_app.collection_requests",
          schema: "dna_app",
          desc: "Tracks outbound collection requests (email, SMS, portal link) sent to customers.",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "customer_id", type: "INT FK", note: "" },
            { name: "plan_id", type: "UUID FK", note: "" },
            { name: "channel", type: "VARCHAR", note: "email | sms | portal" },
            { name: "status", type: "VARCHAR", note: "sent | opened | completed" },
            { name: "placeholder_keys", type: "TEXT[]", note: "Which placeholders this request covers" },
          ],
        },
        {
          name: "dna_app.scheduler_jobs",
          schema: "dna_app",
          desc: "Background job queue for async tasks like document generation and reminder sending.",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "job_type", type: "VARCHAR", note: "fill_document | send_reminder | sync_placeholders" },
            { name: "status", type: "VARCHAR", note: "pending | running | done | failed" },
            { name: "payload", type: "JSONB", note: "Job-specific parameters" },
            { name: "scheduled_at", type: "TIMESTAMPTZ", note: "When to run" },
          ],
        },
      ],
    },
    {
      key: "templates",
      title: "Template Tables",
      color: "green",
      tables: [
        {
          name: "dna_app.catalog_templates",
          schema: "dna_app",
          desc: "AI-parsed document templates. template_structure JSONB contains fillable_sections array.",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "name", type: "VARCHAR", note: "Template display name" },
            { name: "status", type: "VARCHAR", note: "draft | approved" },
            { name: "template_structure", type: "JSONB", note: "Contains fillable_sections[] with id, title, placeholder, type" },
            { name: "version_number", type: "INT", note: "Increments on each edit" },
            { name: "total_fillable_sections", type: "INT", note: "Count of placeholders" },
          ],
        },
        {
          name: "dna_app.iso_standards",
          schema: "dna_app",
          desc: "ISO standard definitions (ISO 27001, ISO 9001, etc.).",
          cols: [
            { name: "id", type: "UUID PK", note: "" },
            { name: "code", type: "VARCHAR UNIQUE", note: "e.g. ISO 27001" },
            { name: "name", type: "VARCHAR", note: "Full standard name" },
            { name: "active", type: "BOOLEAN", note: "Whether available for new plans" },
          ],
        },
      ],
    },
  ];

  return (
    <div className="space-y-4">
      {groups.map(g => (
        <TableGroup key={g.key} groupKey={g.key} title={g.title} color={g.color} tables={g.tables} expanded={expanded} toggle={toggle} />
      ))}
    </div>
  );
}

function RelationsSection() {
  const relations = [
    { from: "iso_customers", to: "customer_iso_plans", type: "1 → N", note: "One customer can have multiple ISO plans" },
    { from: "customer_iso_plans", to: "customer_documents", type: "1 → N", note: "One plan generates multiple documents (one per template)" },
    { from: "customer_iso_plans", to: "customer_tasks", type: "1 → N", note: "One plan generates multiple tasks (one per placeholder)" },
    { from: "customer_iso_plans", to: "customer_placeholders", type: "1 → N", note: "One plan tracks multiple placeholder statuses" },
    { from: "iso_customers", to: "customer_profile_data", type: "1 → N", note: "Customer-level knowledge base (not plan-scoped)" },
    { from: "catalog_templates", to: "customer_documents", type: "1 → N", note: "One template can produce many customer documents" },
    { from: "customer_placeholders", to: "customer_tasks", type: "1 → 1", note: "Each placeholder has one task (via placeholder_key)" },
    { from: "customer_profile_data", to: "customer_placeholders", type: "cascade fill", note: "apply_profile_answer() cascades to placeholders → tasks → documents" },
  ];

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-gray-300">From</th>
              <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-gray-300"></th>
              <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-gray-300">To</th>
              <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-gray-300">Type</th>
              <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-gray-300">Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {relations.map((r, i) => (
              <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <td className="py-3 px-4"><code className="text-blue-600 dark:text-blue-400 font-mono text-xs">{r.from}</code></td>
                <td className="py-3 px-4 text-gray-400"><ArrowRight className="w-4 h-4" /></td>
                <td className="py-3 px-4"><code className="text-purple-600 dark:text-purple-400 font-mono text-xs">{r.to}</code></td>
                <td className="py-3 px-4"><span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs font-medium text-gray-700 dark:text-gray-300">{r.type}</span></td>
                <td className="py-3 px-4 text-gray-600 dark:text-gray-400">{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl">
        <p className="text-sm font-semibold text-yellow-900 dark:text-yellow-100 mb-2">Cascade Delete Chain</p>
        <p className="text-sm text-yellow-800 dark:text-yellow-200 font-mono">
          iso_customers → customer_iso_plans → customer_documents / customer_tasks / customer_placeholders
        </p>
        <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">
          Deleting a customer hard-deletes all plans, documents, tasks, and placeholders. ISO standards and catalog templates are NOT touched.
        </p>
      </div>
    </div>
  );
}

function FlowSection() {
  const steps = [
    { n: "1", title: "Create Customer", desc: "Admin creates customer in iso_customers. No plans yet.", color: "blue" },
    { n: "2", title: "Assign ISO Plan", desc: "Admin picks ISO standard → creates customer_iso_plans record.", color: "blue" },
    { n: "3", title: "Add Templates", desc: "Admin selects templates → plan_management.add_templates_to_plan() runs.", color: "purple" },
    { n: "4", title: "Sync Placeholders", desc: "placeholder_service.sync_placeholders_for_plan() extracts unique placeholder_keys from template fillable_sections. Checks customer_profile_data for known values → auto-fills. Creates customer_placeholders + customer_tasks for unknowns.", color: "purple" },
    { n: "5", title: "Interview", desc: "Admin opens InterviewModal → GET /api/v1/customers/{id}/interview returns all pending placeholders with questions from template titles.", color: "green" },
    { n: "6", title: "Collect Answer", desc: "Admin submits answer → POST /answer → apply_profile_answer() saves to customer_profile_data, cascades to customer_placeholders (status=collected), customer_tasks (status=completed, answer filled), customer_documents (placeholder_fill_status updated).", color: "green" },
    { n: "7", title: "Document Ready", desc: "When all placeholders for a document are filled, document can be auto-generated with all {{placeholder}} values substituted.", color: "orange" },
  ];

  return (
    <div className="space-y-3">
      {steps.map((s, i) => (
        <div key={s.n} className="flex gap-4">
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full bg-${s.color}-100 dark:bg-${s.color}-900/40 border-2 border-${s.color}-400 dark:border-${s.color}-600 flex items-center justify-center text-xs font-bold text-${s.color}-700 dark:text-${s.color}-300 shrink-0`}>
              {s.n}
            </div>
            {i < steps.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 dark:bg-gray-700 mt-1" />}
          </div>
          <div className="pb-4">
            <p className="font-semibold text-gray-900 dark:text-white text-sm">{s.title}</p>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">{s.desc}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function ExamplesSection() {
  const examples = [
    {
      title: "Sync placeholders after adding templates",
      lang: "python",
      code: `# placeholder_service.py
await sync_placeholders_for_plan(
    conn=conn,
    customer_id=3,
    plan_id="uuid-of-plan",
    template_rows=[...],   # rows from catalog_templates
    created_by=1
)
# Result:
# - Reads fillable_sections from each template
# - Checks customer_profile_data for known keys
# - Auto-fills known → status=auto_filled
# - Creates tasks for unknown → status=pending`,
    },
    {
      title: "Apply a collected answer (cascades everywhere)",
      lang: "python",
      code: `# interview.py → apply_profile_answer()
await apply_profile_answer(
    conn=conn,
    customer_id=3,
    field_key="company_name",
    field_value="Acme Corp",
    collected_by=1,
    collected_via="interview"
)
# Cascades to:
# 1. customer_profile_data  → UPSERT (customer_id, field_key)
# 2. customer_placeholders  → status = 'collected'
# 3. customer_tasks         → status = 'completed', answer = value
# 4. customer_documents     → placeholder_fill_status[key] = 'filled'`,
    },
    {
      title: "Get interview session (frontend call)",
      lang: "typescript",
      code: `// InterviewModal.tsx
const res = await axios.get(
  \`\${API_BASE}/api/v1/customers/\${customerId}/interview\`,
  { headers: { Authorization: \`Bearer \${token}\` } }
);
// Returns: InterviewSession {
//   customer_id, customer_name,
//   placeholders: [{
//     placeholder_key, question, status,
//     type, is_mandatory, requires_evidence
//   }]
// }`,
    },
    {
      title: "Template fillable_sections structure",
      lang: "json",
      code: `// catalog_templates.template_structure JSONB
{
  "fillable_sections": [
    {
      "id": "company_name",          // = placeholder_key
      "title": "What is your company's legal name?",  // = question
      "placeholder": "{{company_name}}",
      "type": "text",
      "is_mandatory": true,
      "requires_evidence": false,
      "priority": "high"
    }
  ]
}`,
    },
    {
      title: "Direct DB queries",
      lang: "sql",
      code: `-- Check all placeholders for a customer
SELECT placeholder_key, status, template_ids
FROM dna_app.customer_placeholders
WHERE customer_id = 3;

-- Check profile knowledge base
SELECT field_key, field_value, collected_via
FROM dna_app.customer_profile_data
WHERE customer_id = 3;

-- Tasks with answers
SELECT title, placeholder_key, answer, answered_via
FROM dna_app.customer_tasks
WHERE customer_id = 3 AND answer IS NOT NULL;`,
    },
  ];

  return (
    <div className="space-y-6">
      {examples.map(ex => (
        <div key={ex.title} className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">{ex.title}</span>
            <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">{ex.lang}</span>
          </div>
          <pre className="p-4 text-xs font-mono text-gray-800 dark:text-gray-200 bg-white dark:bg-gray-900 overflow-x-auto leading-relaxed whitespace-pre">
            {ex.code}
          </pre>
        </div>
      ))}
    </div>
  );
}
