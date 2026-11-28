import { test, expect } from '@playwright/test';

test('two real browser tabs serialize refresh and share the rotated HttpOnly cookie', async ({ browser }) => {
  const context = await browser.newContext();
  await context.addCookies([{
    name: 'refresh_token',
    value: 'seed-token',
    domain: '127.0.0.1',
    path: '/',
    httpOnly: true,
    sameSite: 'Strict',
  }]);

  // Keep the Vue application from auto-running restoreSession(): this test
  // isolates the shared lock helper, while a separate app-startup scenario can
  // exercise the store integration without adding implicit refresh requests.
  await context.route('http://127.0.0.1:4173/', (route) => route.fulfill({
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
