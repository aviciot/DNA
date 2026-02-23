const fs = require('fs');
const path = require('path');

const componentsDir = 'C:\\Users\\acohen.SHIFT4CORP\\Desktop\\PythonProjects\\MCP Performance\\DNA\\dashboard\\frontend\\src\\components\\admin';

// Files to process
const files = [
  'CustomerDashboard.tsx',
  'CustomerManagement.tsx',
  'CustomerManagementV3.tsx',
  'ISOStandards.tsx',
  'ManageCustomerPlan.tsx',
  'SystemHealth.tsx',
  'TaskManagementV3.tsx',
  'TemplateBuilder.tsx',
  'TemplateCatalog.tsx',
  'TemplateLibrary.tsx',
  'TemplatePreviewModal.tsx',
  'TemplateStudio.tsx'
];

files.forEach(file => {
  const filePath = path.join(componentsDir, file);

  if (!fs.existsSync(filePath)) {
    console.log(`Skipping ${file} - not found`);
    return;
  }

  let content = fs.readFileSync(filePath, 'utf8');

  // Replace bg-color-number/opacity with bg-color-number bg-opacity-opacity
  // Example: bg-purple-500/20 -> bg-purple-500 bg-opacity-20
  content = content.replace(/bg-(\w+)-(\d+)\/(\d+)/g, 'bg-$1-$2 bg-opacity-$3');

  // Replace from-color-number/opacity (for gradients, just remove the opacity part)
  content = content.replace(/from-(\w+)-(\d+)\/(\d+)/g, 'from-$1-$2');

  // Replace to-color-number/opacity (for gradients, just remove the opacity part)
  content = content.replace(/to-(\w+)-(\d+)\/(\d+)/g, 'to-$1-$2');

  // Replace text-color-number/opacity
  content = content.replace(/text-(\w+)-(\d+)\/(\d+)/g, 'text-$1-$2 text-opacity-$3');

  // Replace border-color-number/opacity
  content = content.replace(/border-(\w+)-(\d+)\/(\d+)/g, 'border-$1-$2 border-opacity-$3');

  fs.writeFileSync(filePath, content, 'utf8');
  console.log(`✅ Fixed ${file}`);
});

console.log('✅ All files processed!');
