/* Copyright 2026 Overte contributors. SPDX-License-Identifier: Apache-2.0 */
'use strict';
const {performance} = require('node:perf_hooks');
const {randomUUID} = require('node:crypto');
const states = new WeakMap();
const CODE = 'OVT_IOS_PROCESS_SOURCE_UNAVAILABLE';
function need(value) { if (!value) throw new Error(CODE); }
function state(driver) {
  if (!states.has(driver)) states.set(driver, {instance: randomUUID().replaceAll('-', ''), busy: false, poisoned: false, uncertain: false, lease: null});
  return states.get(driver);
}
function scope(driver, bundle) {
  try {
  need(driver && typeof driver === 'object' && typeof driver.isRealDevice === 'function' && driver.isRealDevice() === true);
  const opts = driver.opts;
  need(opts && typeof opts.platformName === 'string' && opts.platformName.toLowerCase() === 'ios' &&
    typeof opts.udid === 'string' && opts.udid.length >= 8 && opts.udid.length <= 128 && !/[\x00-\x20\x7f]/.test(opts.udid) &&
    typeof bundle === 'string' && bundle.length <= 255 && !/[\x00-\x20\x7f]/.test(bundle) &&
    /^[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9][A-Za-z0-9-]*)+$/.test(bundle) && opts.bundleId === bundle &&
    typeof driver.sessionId === 'string' && driver.sessionId.length > 0 && driver.sessionId.length <= 160 &&
    typeof driver.mobileQueryAppState === 'function' && driver.remoteXPCFacade && driver.remoteXPCFacade.eligible === true &&
    typeof driver.remoteXPCFacade.requireService === 'function');
  return {udid: opts.udid, bundle, session: driver.sessionId};
  } catch (_) { throw new Error(CODE); }
}
function sourceInfo(driver, bundle, sdk) {
  scope(driver, bundle); const row = state(driver);
  return {processSourceVersion: 1, source: 'dvt-bundle-pid-xcuitest-state', instance: row.instance,
    available: !row.busy && !row.poisoned && !row.uncertain, cleanupPending: row.busy || row.uncertain || Boolean(row.lease), sdk: {...sdk}};
}
function running(value) { need(Number.isInteger(value) && value >= 0 && value <= 4); return value >= 2; }
async function closeOriginal(row) {
  if (!row.lease) { need(!row.uncertain); return; }
  const {service, socket} = row.lease;
  await service.close();
  // The original 5.15.3 source closes its own connection and destroys this
  // original Node socket. A successful close ACK alone is insufficient.
  need(socket.destroyed === true && service.socket === null && service.connection === null && service.isHandshakeComplete === false);
  row.lease = null; row.uncertain = false;
}
async function observe(driver, bundle, timeoutMs = 5000) {
  const owner = scope(driver, bundle), row = state(driver);
  need(!row.busy && !row.poisoned && Number.isInteger(timeoutMs) && timeoutMs > 0 && timeoutMs <= 5000);
  row.busy = true; let expired = false, timer;
  const began = performance.now();
  const current = () => {
    need(!expired && performance.now() - began < timeoutMs && driver.sessionId === owner.session &&
      driver.opts.udid === owner.udid && driver.opts.bundleId === owner.bundle);
  };
  const task = (async () => {
    try {
      const before = await driver.mobileQueryAppState(bundle); current(); running(before);
      row.uncertain = true;
      const dvt = await driver.remoteXPCFacade.requireService('read configured iOS process',
        (Services) => Services.startDVTService(owner.udid));
      need(dvt && dvt.dvtService);
      // Retain ownership before deadline/scope checks, so late acquisition is
      // closed too. Never abandon a just-created native DVT connection.
      row.lease = {service: dvt.dvtService, socket: dvt.dvtService.socket};
      need(typeof dvt.dvtService.close === 'function' && row.lease.socket && typeof row.lease.socket.destroy === 'function' &&
        row.lease.socket.destroyed === false && dvt.dvtService.connection &&
        dvt.dvtService.isHandshakeComplete === true && dvt.processControl &&
        typeof dvt.processControl.getPidForBundleIdentifier === 'function');
      current();
      const first = await dvt.processControl.getPidForBundleIdentifier(bundle); current();
      const after = await driver.mobileQueryAppState(bundle); current();
      const second = await dvt.processControl.getPidForBundleIdentifier(bundle); current();
      need(Number.isInteger(first) && first >= 0 && first <= 2147483647 && first === second &&
        running(before) === running(after) && (before === 4) === (after === 4) && running(after) === (first > 0));
      return first ? {bundleId: bundle, pid: first, foreground: after === 4} : null;
    } finally {
      try { await closeOriginal(row); }
      catch (_) { row.poisoned = true; throw new Error(CODE); }
      finally { row.busy = false; }
    }
  })();
  // A timed-out read is never reused or retried. Late completion still executes
  // the owned finally/close path; no cached PID or late result becomes output.
  task.catch(() => {});
  const deadline = new Promise((_, reject) => { timer = setTimeout(() => {
    expired = true; row.poisoned = true;
    try { if (row.lease?.socket && !row.lease.socket.destroyed) row.lease.socket.destroy(); } catch (_) { /* Remains poisoned and owned. */ }
    reject(new Error(CODE));
  }, timeoutMs); });
  try { return await Promise.race([task, deadline]); }
  catch (_) { throw new Error(CODE); }
  finally { clearTimeout(timer); }
}
async function cleanup(next, driver) {
  const row = states.get(driver); let result, failure;
  try { result = await next(); } catch (error) { failure = error; }
  // Always execute the original session teardown first. Pending/ignored native
  // resource release remains a cleanup error, never a green deletion receipt.
  if (row && (row.busy || row.lease || row.uncertain)) throw new Error('OVT_IOS_PROCESS_SOURCE_CLEANUP_INCOMPLETE');
  if (failure) throw failure;
  return result;
}
module.exports = {observe, sourceInfo, cleanup};
