#!/usr/bin/env node
/*
 * InstallationProxy-only pre-session check. It never installs or launches an app
 * and deliberately emits no device, signer, or profile metadata. Discovery
 * mode emits only the two marker-selected bundle IDs to its private caller.
 */

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {randomUUID} = require('node:crypto');

const MAX_INPUT = 4096;
const OVERTE_ID = 'org.overte.interface.e2e';
const WDA_ID = 'org.overte.WebDriverAgentRunner.xctrunner';
const BUNDLE_ID = /^[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9][A-Za-z0-9-]*)+$/;

function validBundleId(value) {
  return typeof value === 'string' && value.length <= 255 && BUNDLE_ID.test(value);
}

async function readRequest() {
  const chunks = [];
  let total = 0;
  for await (const chunk of process.stdin) {
    total += chunk.length;
    if (total > MAX_INPUT) {
      throw new Error('invalid private request');
    }
    chunks.push(chunk);
  }
  const request = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const originalOwnerRequired = request?.originalOwnerRequired === true;
  if (request && Object.hasOwn(request, 'originalOwnerRequired') && !originalOwnerRequired)
    throw new Error('invalid private request');
  if (originalOwnerRequired) delete request.originalOwnerRequired;
  if (!request || typeof request.udid !== 'string' || request.udid.length < 8 ||
      request.udid.length > 128 || /[\0\r\n]/.test(request.udid)) {
    throw new Error('invalid private request');
  }
  const keys = Object.keys(request).sort();
  if (keys.length === 1 && keys[0] === 'udid') {
    return {...request, originalOwnerRequired, overteBundleId: OVERTE_ID, wdaBundleId: WDA_ID,
      discoverRemappedBundleIds: false};
  }
  if (keys.join(',') === 'discoverRemappedBundleIds,udid' &&
      request.discoverRemappedBundleIds === true) {
    return {...request, originalOwnerRequired};
  }
  if (keys.join(',') === 'overteBundleId,udid,wdaBundleId' &&
      validBundleId(request.overteBundleId) && validBundleId(request.wdaBundleId) &&
      request.overteBundleId !== request.wdaBundleId) {
    return {...request, originalOwnerRequired, discoverRemappedBundleIds: false};
  }
  throw new Error('invalid private request');
}

async function main() {
  const request = await readRequest();
  const runtime = path.dirname(fs.realpathSync(__filename));
  const modulePath = path.join(
    runtime, 'appium', 'node_modules', 'appium-xcuitest-driver',
    'node_modules', 'appium-ios-device'
  );
  const metadata = JSON.parse(fs.readFileSync(path.join(modulePath, 'package.json'), 'utf8'));
  if (metadata.name !== 'appium-ios-device' || metadata.version !== '3.1.21') {
    throw new Error('immutable device helper dependency mismatch');
  }
  let applications;
  let originalOwner = null, remoteXpc = null;
  if (request.originalOwnerRequired) {
    remoteXpc = await import(pathToFileURL(path.join(runtime, 'appium', 'node_modules',
      'appium-ios-remotexpc', 'build', 'src', 'index.js')).href);
    if (typeof remoteXpc.originalKeeperOperation !== 'function') throw new Error('original owner unavailable');
    const probe = await remoteXpc.originalKeeperOperation(request.udid, {
      schemaVersion: 2, requestId: randomUUID().replaceAll('-', ''), ownerInstance: null,
      sessionId: null, operation: 'inspect', args: {},
    });
    if (probe?.originalKeeperOperationVersion !== 1) throw new Error('original owner unavailable');
    if (probe.result?.creatorMode === 'userspace-keeper') {
      if (typeof probe.ownerInstance !== 'string' || !/^[0-9a-f]{32}$/.test(probe.ownerInstance))
        throw new Error('original owner unavailable');
      originalOwner = probe.ownerInstance;
    } else throw new Error('required original userspace owner unavailable');
  }
  if (originalOwner !== null) {
    const value = await remoteXpc.originalKeeperOperation(request.udid, {
      schemaVersion: 2, requestId: randomUUID().replaceAll('-', ''), ownerInstance: originalOwner,
      sessionId: null, operation: 'apps-preflight', args: {
        overteBundleId: request.overteBundleId ?? OVERTE_ID,
        wdaBundleId: request.wdaBundleId ?? WDA_ID,
        discoverRemappedBundleIds: request.discoverRemappedBundleIds,
      },
    });
    if (value?.originalKeeperOperationVersion !== 1 || value.ownerInstance !== originalOwner ||
        value.result?.originalKeeperPreflightVersion !== 1 || value.result.ownerInstance !== originalOwner ||
        value.result.source !== 'original-rsd-installation-proxy' || value.result.nativeTouchSupport !== false ||
        value.result.resourceRetirementEstablished !== false) throw new Error('original preflight unavailable');
    applications = value.result.applications;
  } else {
  const {services} = require(modulePath);
  const proxy = await services.startInstallationProxyService(request.udid);
  try {
    const query = {
      applicationType: 'User',
      returnAttributes: [
        'CFBundleIdentifier', 'CFBundleExecutable', 'ApplicationType',
        'ProfileValidated', 'SignerIdentity', 'UIFileSharingEnabled',
        'OverteE2ETestBuildContractVersion', 'Entitlements',
        'OverteE2EWebDriverAgentVersion', 'OverteE2EXCUITestDriverVersion',
      ],
    };
    if (!request.discoverRemappedBundleIds) {
      query.bundleIds = [request.overteBundleId, request.wdaBundleId];
    }
    applications = await proxy.lookupApplications(query);
  } finally {
    proxy.close();
  }
  }
  if (!applications || typeof applications !== 'object') {
    throw new Error('required apps are unavailable');
  }
  let overte;
  let wda;
  if (request.discoverRemappedBundleIds) {
    const values = Object.values(applications);
    const overteCandidates = values.filter((app) =>
      app && app.OverteE2ETestBuildContractVersion === 1 &&
      app.UIFileSharingEnabled === true);
    const wdaCandidates = values.filter((app) =>
      app && app.OverteE2EWebDriverAgentVersion === '16.8.0' &&
      app.OverteE2EXCUITestDriverVersion === '12.8.0' &&
      typeof app.CFBundleExecutable === 'string' &&
      app.CFBundleExecutable.endsWith('-Runner'));
    if (overteCandidates.length !== 1 || wdaCandidates.length !== 1) {
      throw new Error('marker-selected app inventory is ambiguous');
    }
    [overte] = overteCandidates;
    [wda] = wdaCandidates;
  } else {
    if (Object.keys(applications).length !== 2) {
      throw new Error('required apps are unavailable');
    }
    overte = applications[request.overteBundleId];
    wda = applications[request.wdaBundleId];
  }
  const overteId = overte && overte.CFBundleIdentifier;
  const wdaId = wda && wda.CFBundleIdentifier;
  if (!validBundleId(overteId) || !validBundleId(wdaId) || overteId === wdaId) {
    throw new Error('installed bundle identifiers are invalid');
  }
  if (!request.discoverRemappedBundleIds &&
      (overteId !== request.overteBundleId || wdaId !== request.wdaBundleId)) {
    throw new Error('installed bundle identifiers differ from the receipt');
  }
  const validCommon = (app, expected) => app &&
    app.CFBundleIdentifier === expected &&
    app.ApplicationType === 'User' &&
    app.ProfileValidated === true &&
    typeof app.SignerIdentity === 'string' && app.SignerIdentity.length > 0;
  const signingIdentity = (app, expected) => {
    const entitlements = app && app.Entitlements;
    const team = entitlements && entitlements['com.apple.developer.team-identifier'];
    return typeof team === 'string' && /^[A-Z0-9]{10}$/.test(team) &&
      entitlements['application-identifier'] === `${team}.${expected}` ? team : null;
  };
  const overteTeam = signingIdentity(overte, overteId);
  const wdaTeam = signingIdentity(wda, wdaId);
  if (!validCommon(overte, overteId) || !validCommon(wda, wdaId) ||
      overte.SignerIdentity !== wda.SignerIdentity ||
      !overteTeam || overteTeam !== wdaTeam ||
      overte.OverteE2ETestBuildContractVersion !== 1 ||
      overte.UIFileSharingEnabled !== true ||
      wda.OverteE2EWebDriverAgentVersion !== '16.8.0' ||
      wda.OverteE2EXCUITestDriverVersion !== '12.8.0' ||
      typeof wda.CFBundleExecutable !== 'string' ||
      !wda.CFBundleExecutable.endsWith('-Runner')) {
    throw new Error('installed app contract mismatch');
  }
  if (request.discoverRemappedBundleIds) {
    const suffix = wdaId.endsWith('.xctrunner') ? '.xctrunner' : '';
    const updated = suffix ? wdaId.slice(0, -suffix.length) : wdaId;
    process.stdout.write(JSON.stringify({
      overteBundleId: overteId,
      wdaBundleId: wdaId,
      wdaUpdatedBundleId: updated,
      wdaBundleIdSuffix: suffix,
    }));
  }
  return request.discoverRemappedBundleIds;
}

main().then(
  (discovered) => {
    if (!discovered) {
      process.stdout.write('PASS: installed iOS app contracts verified\n');
    }
  },
  () => {
    process.stderr.write('error: installed iOS app preflight failed\n');
    process.exitCode = 2;
  },
);
