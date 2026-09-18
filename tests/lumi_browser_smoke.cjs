// Usage: node tests/lumi_browser_smoke.cjs <runtime> <upstream checkout> <core> <h5p directory>
// Requires @playwright/test from the upstream checkout and locally installed Chrome.
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const { createRequire } = require('node:module');
const [runtime, upstream, core, packages] = process.argv.slice(2).map(p => path.resolve(p));
const load = createRequire(path.join(runtime, 'package.json'));
const { H5PPlayer, H5PConfig, fsImplementations: stores } = load('@lumieducation/h5p-server');
const PackageImporter = load('@lumieducation/h5p-server/build/src/PackageImporter').default;
const { chromium } = createRequire(path.join(upstream, 'package.json'))('@playwright/test');
const mime = load('mime-types');
const user = { id: 'smoke', name: 'Smoke', email: '', type: 'local' };

(async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'lumi-browser-'));
  const pages = new Map();
  let browser;
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      // This smoke host has no persistent learner state or gradebook.
      if (url.pathname.startsWith('/contentUserData/') || url.pathname === '/finishedData') {
        res.setHeader('Content-Type', 'application/json');
        return res.end(JSON.stringify({ success: true }));
      }
      if (pages.has(url.pathname)) {
        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        return res.end(pages.get(url.pathname));
      }
      if (url.pathname === '/favicon.ico') { res.writeHead(204); return res.end(); }
      const isCore = url.pathname.startsWith('/core/');
      const base = isCore ? core : root;
      const relative = decodeURIComponent(isCore ? url.pathname.slice(6) : url.pathname.slice(1));
      const filename = path.resolve(base, relative);
      if (!filename.startsWith(base + path.sep)) throw new Error('Outside test root');
      const bytes = await fs.readFile(filename);
      res.setHeader('Content-Type', mime.lookup(filename) || 'application/octet-stream');
      res.end(bytes);
    } catch { res.writeHead(404); res.end(); }
  });
  try {
    const names = (await fs.readdir(packages)).filter(n => n.endsWith('.h5p'));
    if (!names.length) throw new Error('No H5P packages to test');
    for (const [index, name] of names.entries()) {
      const folder = path.join(root, `activity-${index}`);
      await fs.mkdir(folder);
      await PackageImporter.extractPackage(path.join(packages, name), folder,
        { includeLibraries: true, includeContent: true, includeMetadata: true });
      const metadata = JSON.parse(await fs.readFile(path.join(folder, 'h5p.json')));
      const params = JSON.parse(await fs.readFile(path.join(folder, 'content/content.json')));
      const config = new H5PConfig(undefined, { baseUrl: '', coreUrl: '/core',
        librariesUrl: `/activity-${index}`, contentFilesUrl: `/activity-${index}/content`, contentUserStateSaveInterval: false });
      const player = new H5PPlayer(new stores.FileLibraryStorage(folder),
        new stores.FileContentStorage(path.join(root, `store-${index}`)), config);
      const html = await player.render('1', user, 'en', { metadataOverride: metadata, parametersOverride: params });
      pages.set(`/play-${index}`, html);
    }
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    for (const [index, name] of names.entries()) {
      const page = await browser.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('response', response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
      await page.goto(`http://127.0.0.1:${server.address().port}/play-${index}`);
      await page.waitForFunction(() => window.H5P?.instances?.length > 0);
      const frame = page.frames().find(f => f !== page.mainFrame()) || page.mainFrame();
      await frame.locator('.h5p-content').waitFor({ state: 'visible' });
      const start = frame.getByRole('button', { name: /^Start/ });
      if (await start.count()) await start.first().click();
      const panel = frame.locator('.h5p-panel-button').first();
      if (await panel.count()) {
        await panel.click();
        if (await panel.getAttribute('aria-expanded') !== 'true') throw new Error(`${name}: panel did not expand`);
        await frame.locator('.h5p-panel-content p').first().waitFor({ state: 'visible' });
      }
      const controls = await frame.locator('button, input, [role="button"], [role="radio"], [role="checkbox"]').count();
      if (!controls) throw new Error(`${name}: no interactive controls`);
      const answer = frame.locator('input[type="text"]:visible').first();
      if (await answer.count()) await answer.fill('test');
      const option = frame.locator('[role="radio"]:visible, [role="checkbox"]:visible').first();
      if (await option.count()) await option.click();
      const check = frame.locator('.h5p-question-check-answer:visible').first();
      if (await check.count()) await check.click();
      const score = await page.evaluate(() => {
        const activity = H5P.instances[0];
        if (typeof activity.getScore !== 'function') return { graded: false };
        return { graded: true, score: activity.getScore(), maximum: activity.getMaxScore() };
      });
      if (score.graded && (!Number.isFinite(score.score) || !(score.maximum > 0))) throw new Error(`${name}: invalid score`);
      if (errors.length) throw new Error(`${name}: ${errors.join('; ')}`);
      console.log(JSON.stringify({ name, controls, ...score, errors }));
      await page.close();
    }
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    // Only our own unique temporary directory is removed.
    await fs.rm(root, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
