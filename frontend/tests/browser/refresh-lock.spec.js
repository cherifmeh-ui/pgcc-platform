import { test, expect } from '@playwright/test';

test('two real browser tabs serialize refresh and share the rotated HttpOnly cookie', async ({ browser }) => {
  const context = await browser.newContext();
  await context.addCookies([{
    name: 'refresh_token',
    value: 'seed-token',
    domain: 'localhost',
    path: '/',
    httpOnly: true,
    sameSite: 'Strict',
  }]);

  // Keep the Vue application from auto-running restoreSession(): this test
  // isolates the shared lock helper, while a separate app-startup scenario can
  // exercise the store integration without adding implicit refresh requests.
  await context.route('http://localhost:4173/', (route) => route.fulfill({
    status: 200,
    contentType: 'text/html',
    body: '<!doctype html><html><head></head><body></body></html>',
  }));

  const observedCookies = [];
  let requestCount = 0;
  await context.route('**/api/v1/auth/refresh', async (route) => {
    const cookie = route.request().headers().cookie || '';
    observedCookies.push(cookie);
    requestCount += 1;
    const rotation = requestCount;
    // Keep the first request in flight long enough for the second tab to contend.
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'set-cookie': `refresh_token=rotated-${rotation}; HttpOnly; Path=/; SameSite=Strict`,
      },
      body: JSON.stringify({ access_token: `access-${rotation}` }),
    });
  });

  const firstTab = await context.newPage();
  const secondTab = await context.newPage();
  await Promise.all([firstTab.goto('/'), secondTab.goto('/')]);

  const refreshFromTab = (page) => page.evaluate(async () => {
    const { withCrossTabRefreshLock } = await import('/src/services/refreshLock.js');
    return withCrossTabRefreshLock(async () => {
      const response = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      });
      if (!response.ok) throw new Error(`refresh failed: ${response.status}`);
      return response.json();
    });
  });

  const results = await Promise.all([
    refreshFromTab(firstTab),
    refreshFromTab(secondTab),
  ]);

  expect(results.map((result) => result.access_token).sort()).toEqual(['access-1', 'access-2']);
  expect(requestCount).toBe(2);
  expect(observedCookies).toHaveLength(2);
  expect(observedCookies[0]).toContain('refresh_token=seed-token');
  expect(observedCookies[1]).toContain('refresh_token=rotated-1');
  expect(observedCookies[1]).not.toContain('refresh_token=seed-token');

  await context.close();
});


test('a waiting tab acquires the refresh lock when the lock owner tab closes', async ({ browser }) => {
  const context = await browser.newContext();
  const owner = await context.newPage();
  const waiter = await context.newPage();
  await Promise.all([owner.goto('/'), waiter.goto('/')]);

  await owner.evaluate(() => {
    window.__refreshLockAcquired = false;
    window.__holdRefreshLock = new Promise((resolve) => {
      window.__releaseRefreshLock = resolve;
    });
    window.__refreshLockPromise = navigator.locks.request(
      'pgcc-auth-refresh',
      { mode: 'exclusive' },
      async () => {
        window.__refreshLockAcquired = true;
        await window.__holdRefreshLock;
      },
    );
  });
  await owner.waitForFunction(() => window.__refreshLockAcquired === true);

  await waiter.evaluate(() => {
    window.__waitingLockAcquired = false;
    window.__waitingLockPromise = navigator.locks.request(
      'pgcc-auth-refresh',
      { mode: 'exclusive' },
      () => {
        window.__waitingLockAcquired = true;
      },
    );
  });
  await waiter.waitForFunction(async () => {
    const state = await navigator.locks.query();
    return state.pending.some((lock) => lock.name === 'pgcc-auth-refresh');
  });

  // Closing the browsing context destroys the lock owner; Web Locks must
  // release its exclusive lock so another live tab is not blocked forever.
  await owner.close();
  await waiter.waitForFunction(() => window.__waitingLockAcquired === true);

  await context.close();
});
