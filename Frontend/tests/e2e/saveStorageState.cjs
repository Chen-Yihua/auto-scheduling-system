// node tests/e2e/saveStorageState.cjs

const { chromium } = require('playwright');

(async () => {
  // 用 PersistentContext 開啟 Chrome User Data
  const userDataDir = './chrome-user-data-playwright';
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false, // 要開 GUI 手動登入
    channel: 'chrome', // 用你系統的 Chrome
    args: ['--disable-blink-features=AutomationControlled'],
  });

  const page = await context.newPage();

  // 開你的頁面
  await page.goto('http://localhost:3000');

  console.log('請手動登入 Google(帳密手打，不要用貼上的)，登入完成後回到這邊按 Enter 繼續...');
  // 暫停，讓你手動登入
  await new Promise((resolve) => {
    process.stdin.once('data', resolve);
  });

  // 存 storageState.json
  await context.storageState({ path: 'storageState.json' });
  console.log('已存好 storageState.json');

  await context.close();
})();
