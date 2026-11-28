import test from 'node:test';
import assert from 'node:assert/strict';
import { withCrossTabRefreshLock } from '../src/services/refreshLock.js';

function createLockManager() {
  let tail = Promise.resolve();
  const requests = [];
  return {
    requests,
    locks: {
      request(name, options, callback) {
        requests.push({ name, options });
        const result = tail.then(callback);
        tail = result.catch(() => undefined);
        return result;
      },
    },
  };
}

test('serializes refresh operations that originate in separate tabs', async () => {
  const manager = createLockManager();
  const order = [];
  let releaseFirst;
  const firstGate = new Promise((resolve) => { releaseFirst = resolve; });

  const first = withCrossTabRefreshLock(async () => {
    order.push('first-start');
    await firstGate;
    order.push('first-end');
    return 'rotated-1';
  }, manager.locks);

  const second = withCrossTabRefreshLock(async () => {
    order.push('second-start');
    order.push('second-end');
    return 'rotated-2';
  }, manager.locks);

  await Promise.resolve();
  assert.deepEqual(order, ['first-start']);
  releaseFirst();

  assert.equal(await first, 'rotated-1');
  assert.equal(await second, 'rotated-2');
  assert.deepEqual(order, ['first-start', 'first-end', 'second-start', 'second-end']);
  assert.equal(manager.requests.length, 2);
  assert.ok(manager.requests.every(({ name, options }) =>
    name === 'pgcc-auth-refresh' && options.mode === 'exclusive'
  ));
});

test('fails closed when cross-tab locking is unavailable', async () => {
  let called = false;
  await assert.rejects(
    withCrossTabRefreshLock(() => { called = true; }, undefined),
    /Web Locks API unavailable/
  );
  assert.equal(called, false);
});

test('releases the lock after a failed refresh operation', async () => {
  const manager = createLockManager();
  await assert.rejects(
    withCrossTabRefreshLock(async () => { throw new Error('network failure'); }, manager.locks),
    /network failure/
  );
  assert.equal(
    await withCrossTabRefreshLock(async () => 'next attempt', manager.locks),
    'next attempt'
  );
});
