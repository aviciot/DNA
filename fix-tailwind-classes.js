const fs = require('fs');
const path = require('path');

const componentsDir = 'C:\\Users\\acohen.SHIFT4CORP\\Desktop\\PythonProjects\\MCP Performance\\DNA\\dashboard\\frontend\\src\\components\\admin';

const files = [
  'CustomerManagementV3.tsx',
  'CustomerDashboard.tsx',
  'ManageCustomerPlan.tsx',
  'TaskManagementV3.tsx'
];

files.forEach(file => {
  const filePath = path.join(componentsDir, file);

  if (!fs.existsSync(filePath)) {
    console.log(`Skipping ${file} - not found`);
    return;
  }

  let content = fs.readFileSync(filePath, 'utf8');
  let modified = false;

  // Replace problematic patterns with simple, standard Tailwind classes

  // Pattern: bg-color-500 bg-opacity-20 -> bg-color-100
  const replacements = [
    // Light backgrounds with opacity -> standard light shades
    { from: /bg-purple-500 bg-opacity-20/g, to: 'bg-purple-100' },
    { from: /bg-blue-500 bg-opacity-20/g, to: 'bg-blue-100' },
    { from: /bg-green-500 bg-opacity-20/g, to: 'bg-green-100' },
    { from: /bg-orange-500 bg-opacity-20/g, to: 'bg-orange-100' },
    { from: /bg-red-500 bg-opacity-20/g, to: 'bg-red-100' },
    { from: /bg-yellow-500 bg-opacity-20/g, to: 'bg-yellow-100' },

    // Dark mode: dark:bg-color-900 bg-opacity-30 -> dark:bg-color-800/30
    { from: /dark:bg-(\w+)-900 bg-opacity-30/g, to: 'dark:bg-$1-800' },
    { from: /dark:bg-(\w+)-900 bg-opacity-20/g, to: 'dark:bg-$1-900' },
    { from: /dark:bg-(\w+)-900 bg-opacity-50/g, to: 'dark:bg-$1-700' },

    // Remove orphaned bg-opacity
    { from: /\s+bg-opacity-\d+/g, to: '' },
    { from: /\s+text-opacity-\d+/g, to: '' },
  ];

  replacements.forEach(({ from, to }) => {
    if (content.match(from)) {
      content = content.replace(from, to);
      modified = true;
    }
  });

  if (modified) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`✅ Fixed ${file}`);
  } else {
    console.log(`⏭️  No changes needed in ${file}`);
  }
});

console.log('\n✅ All files processed!');
