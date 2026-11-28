import { test, expect } from '@playwright/test';

test('real FastAPI/PostgreSQL refresh rotation is serialized and lost responses fail closed', async ({ browser }, testInfo) => {
  const browserKey = testInfo.project.name.toUpperCase();
  const initialRefreshToken = process.env[`PGCC_E2E_REFRESH_TOKEN_${browserKey}`];
  expect(initialRefreshToken, 'CI must seed an isolated PostgreSQL refresh session').toBeTruthy();

  const context = await browser.newContext();
  await context.addCookies([{
    name: 'pgcc_refresh',
    value: initialRefreshToken,
    domain: 'localhost',
    path: '/api/v1/auth',
    httpOnly: true,
    sameSite: 'Strict',
  }]);

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
      const payload = await response.json();
      return { status: response.status, payload };
    });
  });

  const results = await Promise.all([
    refreshFromTab(firstTab),
    refreshFromTab(secondTab),
  ]);

  expect(results.map((result) => result.status)).toEqual([200, 200]);
  expect(results[0].payload.access_token).toBeTruthy();
  expect(results[1].payload.access_token).toBeTruthy();
  expect(results[0].payload.access_token).not.toBe(results[1].payload.access_token);

  // Simulate the transport losing a successful response after FastAPI has
  // committed the rotation. route.fetch reaches the real backend, but aborting
  // the browser response prevents its Set-Cookie from reaching the cookie jar.
  const cookieBeforeLoss = await context.cookies('http://localhost:4173/api/v1/auth');
  const oldCookie = cookieBeforeLoss.find((cookie) => cookie.name === 'pgcc_refresh');
  expect(oldCookie?.value).toBeTruthy();

  await firstTab.route('**/api/v1/auth/refresh', async (route) => {
    const requestHeaders = await route.request().allHeaders();
    // Use Node's independent HTTP client so the backend commit happens but
    // its Set-Cookie header is never applied to the browser cookie jar.
    const committedResponse = await fetch('http://127.0.0.1:8000/api/v1/auth/refresh', {
      method: 'POST',
      headers: {
        cookie: requestHeaders.cookie || '',
        origin: 'http://localhost:4173',
      },
    });
    expect(committedResponse.status).toBe(200);
    await route.abort('failed');
  });
  const responseWasLost = await firstTab.evaluate(async () => {
    try {
      await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      });
      return false;
    } catch {
      return true;
    }
  });
  expect(responseWasLost).toBe(true);
  await firstTab.unroute('**/api/v1/auth/refresh');

  const cookieAfterLoss = await context.cookies('http://localhost:4173/api/v1/auth');
  expect(cookieAfterLoss.find((cookie) => cookie.name === 'pgcc_refresh')?.value)
    .toBe(oldCookie.value);

  // The browser still has the consumed token. The retry must be rejected as
  // replay rather than silently accepting the stale cookie or weakening policy.
  const retry = await firstTab.evaluate(async () => {
    const response = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      credentials: 'include',
    });
    return { status: response.status, payload: await response.json() };
  });
  expect(retry.status).toBe(401);
  expect(retry.payload.detail).toContain('Réutilisation');

  await context.close();
});
