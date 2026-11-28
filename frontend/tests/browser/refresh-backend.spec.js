import { test, expect } from '@playwright/test';

test('real FastAPI/PostgreSQL refresh rotation is serialized across tabs and replay remains rejected', async ({ browser }, testInfo) => {
  const browserKey = testInfo.project.name.toUpperCase();
  const initialRefreshToken = process.env[`PGCC_E2E_REFRESH_TOKEN_${browserKey}`];
  expect(initialRefreshToken, 'CI must seed an isolated PostgreSQL refresh session').toBeTruthy();

  const context = await browser.newContext();
  await context.addCookies([{
    name: 'pgcc_refresh',
    value: initialRefreshToken,
    url: 'http://127.0.0.1:4173',
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

  // A separate browser context replays the original, now-revoked cookie.
  // The real API must reject it and preserve the anti-replay policy.
  const replayContext = await browser.newContext();
  await replayContext.addCookies([{
    name: 'pgcc_refresh',
    value: initialRefreshToken,
    url: 'http://127.0.0.1:4173',
    path: '/api/v1/auth',
    httpOnly: true,
    sameSite: 'Strict',
  }]);
  const replayTab = await replayContext.newPage();
  await replayTab.goto('/');
  const replay = await replayTab.evaluate(async () => {
    const response = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      credentials: 'include',
    });
    return { status: response.status, payload: await response.json() };
  });
  expect(replay.status).toBe(401);
  expect(replay.payload.detail).toContain('Réutilisation');

  await replayContext.close();
  await context.close();
});
