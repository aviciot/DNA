"use client";

import { FileText, Plus, Search, Download } from "lucide-react";

const MOCK_DOCS = [
  { id: 1, name: "ISO 9001 Certificate", customer: "Acme Corp", date: "2024-01-15", status: "Approved" },
  { id: 2, name: "Quality Manual", customer: "TechStart Inc", date: "2024-01-20", status: "In Review" },
  { id: 3, name: "Audit Report", customer: "Global Industries", date: "2024-01-25", status: "Draft" },
];

const STATUS_COLORS: Record<string, string> = {
  Approved: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  "In Review": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  Draft: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
};

export default function DocumentsPage() {
  return (
    <div className="p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Documents</h2>
            <p className="text-sm text-gray-500 mt-1">Manage ISO certification documents</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
            <Plus className="w-4 h-4" /> Upload Document
          </button>
        </div>

        <div className="mb-4 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" placeholder="Search documents..."
            className="w-full pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm" />
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                {["Document", "Customer", "Date", "Status", "Actions"].map(h => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {MOCK_DOCS.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-blue-500" />
                      <span className="text-sm font-medium text-gray-900 dark:text-white">{doc.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-700 dark:text-gray-300">{doc.customer}</td>
                  <td className="px-5 py-3 text-sm text-gray-500">{doc.date}</td>
                  <td className="px-5 py-3">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${STATUS_COLORS[doc.status]}`}>{doc.status}</span>
                  </td>
                  <td className="px-5 py-3 flex items-center gap-3">
                    <button className="text-sm text-blue-600 hover:underline">View</button>
                    <button className="text-gray-500 hover:text-gray-700"><Download className="w-4 h-4" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
