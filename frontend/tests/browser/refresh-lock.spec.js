import { test, expect } from '@playwright/test';

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
