import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDataDir = path.join(__dirname, '../dist/data');
const indexPath = path.join(distDataDir, 'index.json');

console.log('Checking dist data directory:', distDataDir);

if (!fs.existsSync(indexPath)) {
  console.error('Error: web/dist/data/index.json not found! Build might have failed to copy public files.');
  process.exit(1);
}

try {
  const indexData = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
  console.log(`Successfully parsed dist index.json. Total entries: ${indexData.length}`);

  if (indexData.length > 0) {
    const latest = indexData[0];
    console.log('Latest dist entry info:');
    console.log(`- ID: ${latest.id}`);
    console.log(`- Target Date: ${latest.target_date}`);
    console.log(`- Generated At: ${latest.generated_at}`);
  }
} catch (e) {
  console.error('Error parsing dist index.json:', e.message);
  process.exit(1);
}

console.log('Dist data verification passed.');
