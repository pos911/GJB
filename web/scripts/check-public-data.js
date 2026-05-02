import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDataDir = path.join(__dirname, '../public/data');
const indexPath = path.join(publicDataDir, 'index.json');

console.log('Checking public data directory:', publicDataDir);

if (!fs.existsSync(indexPath)) {
  console.error('Error: web/public/data/index.json not found!');
  process.exit(1);
}

try {
  const indexData = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
  console.log(`Successfully parsed index.json. Total entries: ${indexData.length}`);

  if (indexData.length > 0) {
    const latest = indexData[0];
    console.log('Latest entry info:');
    console.log(`- ID: ${latest.id}`);
    console.log(`- Target Date: ${latest.target_date}`);
    console.log(`- Generated At: ${latest.generated_at}`);
  } else {
    console.warn('Warning: index.json is empty.');
  }
} catch (e) {
  console.error('Error parsing index.json:', e.message);
  process.exit(1);
}

console.log('Public data verification passed.');
