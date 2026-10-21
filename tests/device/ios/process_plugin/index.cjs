/* Copyright 2026 Overte contributors. SPDX-License-Identifier: Apache-2.0 */
'use strict';
const {BasePlugin} = require('appium/plugin');
const source = require('./process_observer.cjs');
const sdk = require('./read_sdk.cjs')(require);
if (sdk.appium !== '3.7.0' || sdk.xcuitest !== '12.8.0' || sdk.remoteXpc !== '5.15.3')
  throw new Error('OVT_IOS_PROCESS_SOURCE_SDK_UNAVAILABLE');
class OverteProcessPlugin extends BasePlugin {
  async execute(next, driver, script, args) {
    const retired = script === 'mobile: overteRetiredProcessInfo';
    if (!retired && script !== 'mobile: overteProcessInfo' && script !== 'mobile: overteProcessSourceInfo') return await next();
    if (!Array.isArray(args) || args.length !== 1 || !args[0] || typeof args[0] !== 'object' ||
        Array.isArray(args[0]) || Object.keys(args[0]).sort().join(',') !== (retired ? 'bundleId,commandId' : 'bundleId'))
      throw new Error('OVT_IOS_PROCESS_SOURCE_UNAVAILABLE');
    if (retired) return await source.observeRetired(driver, args[0].bundleId, args[0].commandId);
    return script === 'mobile: overteProcessInfo' ? await source.observe(driver, args[0].bundleId) :
      source.sourceInfo(driver, args[0].bundleId, sdk);
  }
  async deleteSession(next, driver) { return await source.cleanup(next, driver); }
}
module.exports = {OverteProcessPlugin};
