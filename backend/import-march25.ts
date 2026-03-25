import { importMarkdownReview, syncAllMarkdownReviews } from './src/services/markdownImport';

async function run() {
  console.log('=== Importing March 25 ===');
  try {
    const count = await importMarkdownReview('2026-03-25', 1);
    console.log('Imported', count, 'findings');
  } catch (e) {
    console.error('Error:', e);
  }
  
  console.log('\n=== Syncing all ===');
  const result = await syncAllMarkdownReviews(1);
  console.log(result);
}

run();
