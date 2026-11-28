// Serialize refresh-token rotations across every same-origin browser tab.
// The refresh cookie is shared by tabs; rotating it without a cross-tab lock
// can make a legitimate concurrent request look like token replay to the API.
export async function withCrossTabRefreshLock(operation, lockManager = globalThis.navigator?.locks) {
  if (!lockManager || typeof lockManager.request !== 'function') {
    throw new Error(
      'Web Locks API unavailable: secure cross-tab session refresh is not supported in this browser.'
    );
  }

  return lockManager.request('pgcc-auth-refresh', { mode: 'exclusive' }, operation);
}
