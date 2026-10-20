/* Copyright 2026 Overte contributors. SPDX-License-Identifier: Apache-2.0 */
'use strict';
const fs = require('node:fs'), path = require('node:path');
const {createRequire} = require('node:module');
function metadata(name, resolver) {
  // Use Node's actual package search order. The locked ESM packages can export
  // neither a CommonJS entry nor package.json; require.resolve(name) is then
  // unavailable even though the actual driver can import the package.
  const folders = resolver.resolve.paths(name);
  if (!Array.isArray(folders)) throw new Error('OVT_IOS_PROCESS_SOURCE_SDK_UNAVAILABLE');
  for (const folder of folders) {
    const root = path.join(folder, name), file = path.join(root, 'package.json');
    if (fs.existsSync(root)) {
      if (!fs.existsSync(file)) throw new Error('OVT_IOS_PROCESS_SOURCE_SDK_UNAVAILABLE');
      const stat = fs.statSync(file);
      if (!stat.isFile() || stat.size < 1 || stat.size > 262144) throw new Error('OVT_IOS_PROCESS_SOURCE_SDK_UNAVAILABLE');
      const actual = JSON.parse(fs.readFileSync(file, 'utf8'));
      if (actual.name === name && typeof actual.version === 'string') return {manifest: file, version: actual.version};
      throw new Error('OVT_IOS_PROCESS_SOURCE_SDK_UNAVAILABLE');
    }
  }
  throw new Error('OVT_IOS_PROCESS_SOURCE_SDK_UNAVAILABLE');
}
function readSdk(resolver) {
  try {
    const driver = metadata('appium-xcuitest-driver', resolver);
    // Resolve RemoteXPC from the actual driver's import context, including any
    // nested dependency, rather than guessing a global/neighboring package.
    return {appium: metadata('appium', resolver).version, xcuitest: driver.version,
      remoteXpc: metadata('appium-ios-remotexpc', createRequire(driver.manifest)).version};
  } catch (_) { throw new Error('OVT_IOS_PROCESS_SOURCE_SDK_UNAVAILABLE'); }
}
module.exports = readSdk;
