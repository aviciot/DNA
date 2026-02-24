"use client";

export default function DashboardPage() {
  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h2>
          <p className="mt-1 text-gray-500 dark:text-gray-400">ISO Certification overview</p>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          {[
            { label: "Total Customers", value: "24", color: "blue" },
            { label: "Active Documents", value: "87", color: "green" },
            { label: "Pending Tasks", value: "12", color: "yellow" },
            { label: "Completion Rate", value: "78%", color: "purple" },
          ].map((stat) => (
            <div key={stat.label} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
              <p className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</p>
              <p className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">{stat.value}</p>
            </div>
          ))}
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-4">Recent Activity</h3>
          <div className="space-y-3">
            {[
              { title: "Document Completed", desc: "ISO 9001:2015 for Acme Corp", time: "2 hours ago" },
              { title: "New Customer Added", desc: "TechStart Industries", time: "5 hours ago" },
              { title: "AI Review Requested", desc: "Missing information detected", time: "1 day ago" },
            ].map((a, i) => (
              <div key={i} className="flex items-start space-x-3 pb-3 border-b border-gray-100 dark:border-gray-700 last:border-0">
                <div className="w-2 h-2 mt-1.5 rounded-full bg-blue-500 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{a.title}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{a.desc}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{a.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
