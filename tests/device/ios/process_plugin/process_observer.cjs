/* Copyright 2026 Overte contributors. SPDX-License-Identifier: Apache-2.0 */
'use strict';
const {performance} = require('node:perf_hooks');
const {randomUUID} = require('node:crypto');
const states = new WeakMap();
const CODE = 'OVT_IOS_PROCESS_SOURCE_UNAVAILABLE';
function need(value) { if (!value) throw new Error(CODE); }
function state(driver) {
  if (!states.has(driver)) states.set(driver, {instance: randomUUID().replaceAll('-', ''), busy: false, poisoned: false,
    uncertain: false, lease: null, sequence: 0, last: null, retiredRequests: new Set()});
  return states.get(driver);
}
const clock = () => ({epochMs: Date.now(), monotonicMs: performance.now()});
const copy = value => JSON.parse(JSON.stringify(value));
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
  // destroyed/closed may become true before the original Node close event.
  // Keep the lease until that callback has drained as well as SDK closure.
  need(socket && typeof socket.once === 'function' && typeof socket.removeListener === 'function');
  let closed;
  const drained = new Promise(resolve => { closed = resolve; socket.once('close', closed); });
  try {
    await service.close();
    need(socket.destroyed === true && service.socket === null && service.connection === null && service.isHandshakeComplete === false);
    await drained;
  } finally { socket.removeListener('close', closed); }
  row.lease = null; row.uncertain = false;
}
async function observe(driver, bundle, timeoutMs = 5000) {
  const owner = scope(driver, bundle), row = state(driver);
  need(!row.busy && !row.poisoned && Number.isInteger(timeoutMs) && timeoutMs > 0 && timeoutMs <= 5000);
  need(row.sequence < 1000000000);
  row.busy = true; const sequence = ++row.sequence, beforeClock = clock(); let expired = false, finished = false, timer, original;
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
      original = {sequence, pid: first, appStates: [before, after], bundlePids: [first, second], clockBefore: beforeClock};
      return first ? {bundleId: bundle, pid: first, foreground: after === 4} : null;
    } finally {
      try { await closeOriginal(row); }
      catch (_) { row.poisoned = true; throw new Error(CODE); }
      finally { finished = true;if (expired) row.busy = false; }
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
  try {
    const value = await Promise.race([task, deadline]); current();
    // Preserve the actual successful nonzero observation, including its
    // original clock and scope. Later absence must not retime or erase it.
    if (value) row.last = {owner: {...owner}, original: {...original, clockAfter: clock()}};
    return value;
  }
  catch (_) { throw new Error(CODE); }
  finally { clearTimeout(timer);if (finished) row.busy = false; }
}
async function observeRetired(driver, bundle, commandId, timeoutMs = 5000) {
  const owner = scope(driver, bundle), row = state(driver), anchor = row.last;
  need(typeof commandId === 'string' && /^ios-[0-9a-f]{32}$/.test(commandId) &&
    !row.retiredRequests.has(commandId) && row.retiredRequests.size < 4096 && row.sequence < 1000000000 &&
    !row.busy && !row.poisoned && !row.uncertain && !row.lease &&
    Number.isInteger(timeoutMs) && timeoutMs > 0 && timeoutMs <= 5000 && anchor &&
    anchor.owner.udid === owner.udid && anchor.owner.bundle === owner.bundle && anchor.owner.session === owner.session);
  row.retiredRequests.add(commandId);row.busy = true;
  const sequence = ++row.sequence, beforeClock = clock(), began = performance.now(); let expired = false, finished = false, timer;
  const current = () => need(!expired && performance.now() - began < timeoutMs && driver.sessionId === owner.session &&
    driver.opts.udid === owner.udid && driver.opts.bundleId === owner.bundle && row.last === anchor);
  const task = (async () => {
    try {
      const before = await driver.mobileQueryAppState(bundle);current();running(before);
      row.uncertain = true;
      const dvt = await driver.remoteXPCFacade.requireService('read configured iOS process',
        Services => Services.startDVTService(owner.udid));
      need(dvt && dvt.dvtService);
      row.lease = {service: dvt.dvtService, socket: dvt.dvtService.socket};
      need(typeof dvt.dvtService.close === 'function' && row.lease.socket && typeof row.lease.socket.destroy === 'function' &&
        row.lease.socket.destroyed === false && dvt.dvtService.connection && dvt.dvtService.isHandshakeComplete === true &&
        dvt.processControl && typeof dvt.processControl.getPidForBundleIdentifier === 'function' &&
        dvt.deviceInfo && typeof dvt.deviceInfo.isRunningPid === 'function');current();
      const first = await dvt.processControl.getPidForBundleIdentifier(bundle);current();
      const firstRunning = await dvt.deviceInfo.isRunningPid(anchor.original.pid);current();
      const after = await driver.mobileQueryAppState(bundle);current();running(after);
      const second = await dvt.processControl.getPidForBundleIdentifier(bundle);current();
      const secondRunning = await dvt.deviceInfo.isRunningPid(anchor.original.pid);current();
      need([first, second].every(pid => Number.isInteger(pid) && pid >= 0 && pid <= 2147483647) &&
        typeof firstRunning === 'boolean' && typeof secondRunning === 'boolean');
      return {appStates: [before, after], bundlePids: [first, second],
        pidChecks: [{pid: anchor.original.pid, running: firstRunning}, {pid: anchor.original.pid, running: secondRunning}]};
    } finally {
      try { await closeOriginal(row); }
      catch (_) { row.poisoned = true; throw new Error(CODE); }
      finally { finished = true;if (expired) row.busy = false; }
    }
  })();
  task.catch(() => {});
  const deadline = new Promise((_, reject) => {timer = setTimeout(() => {
    expired = true;row.poisoned = true;
    try { if (row.lease?.socket && !row.lease.socket.destroyed) row.lease.socket.destroy(); } catch (_) { /* Retain failed ownership. */ }
    reject(new Error(CODE));
  }, timeoutMs);});
  try {
    const value = await Promise.race([task, deadline]);current();
    return {iosRetiredProcessVersion: 1, commandId, instance: row.instance, sequence,
      source: 'dvt-owned-pid-and-bundle-state', clockDomain: 'appium-node-host',
      clockBefore: beforeClock, clockAfter: clock(), anchor: copy(anchor.original), ...value};
  } catch (_) { throw new Error(CODE); }
  finally { clearTimeout(timer);if (finished) row.busy = false; }
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
module.exports = {observe, observeRetired, sourceInfo, cleanup};
