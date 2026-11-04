"""Actual Probe branch under Node; Native calls are counter leaves only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[3]
PROBE=ROOT/'tests/device/probe/overte_e2e_probe.js'
PROGRAM=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const p=process.argv[1],text=fs.readFileSync(p,'utf8');
let a=text.indexOf('function objectKeysMatch('),b=text.indexOf('function httpUrl(',a),keys=text.slice(a,b);
a=text.indexOf('function savePicoEmoteSourceTransaction(');b=text.indexOf('function saveNativeFeatureObservation(',a);const helper=text.slice(a,b);
const action=text.indexOf('&& command.action === "feature-pico-emote-source-transaction"');
a=text.lastIndexOf('if (command &&',action);b=text.indexOf('if (command && command.schemaVersion === 1\n                && /^(?:ios-)?[0-9a-f]{32}$/.test(command.commandId)\n                && command.action === "feature-native-observe"',action);
assert(a>=0 && b>a);const branch=text.slice(a,b);
const counters={native:0,conversion:0,timer:0};
const context={lastNativeFeatureRequest:'prior',nativeFeatureTimer:null,
 Script:{setTimeout(){counters.timer++;throw new Error('No pending scheduler expected');},clearTimeout(){throw new Error('No active timer');}},
 Test:{featurePicoEmoteSourceTransaction(command){counters.native++;return {requestId:command.commandId,complete:true};}}};
vm.createContext(context);vm.runInContext(keys+'\n'+helper+'\nfunction invoke(command){'+branch+'}',context);
const valid={schemaVersion:1,action:'feature-pico-emote-source-transaction',commandId:'1'.repeat(32),runId:'2'.repeat(32),originalPolicySha256:'3'.repeat(64),parentBaselineSha256:'4'.repeat(64)};
let faults=0;
for(const key of ['commandId','runId','originalPolicySha256','parentBaselineSha256']) {
 for(const bad of [[valid[key]],new String(valid[key]),{toString(){counters.conversion++;return valid[key];}},null,true,1]) {
  context.invoke({...valid,[key]:bad});faults++;assert.strictEqual(counters.native,0);assert.strictEqual(context.lastNativeFeatureRequest,'prior');
 }
}
for(const patch of [{schemaVersion:'1'},{schemaVersion:true},{schemaVersion:[1]},{action:new String(valid.action)}]) {
 context.invoke({...valid,...patch});faults++;assert.strictEqual(counters.native,0);assert.strictEqual(context.lastNativeFeatureRequest,'prior');
}
assert.strictEqual(counters.conversion,0);context.invoke(valid);context.invoke(valid);
assert.strictEqual(counters.native,1);assert.strictEqual(context.lastNativeFeatureRequest,valid.commandId);
assert.strictEqual(counters.timer,0);
console.log(JSON.stringify({faultCases:faults,validNativeLeafCalls:counters.native,conversionCalls:counters.conversion,duplicateCalls:0,nativeCompiled:false,nativeExecuted:false,source:p}));
"""


class SourceTransactionProbeTests(unittest.TestCase):
    def test_actual_probe_rejects_twenty_eight_nonstring_and_conversion_cases_before_native_or_nonce(self):
        result=subprocess.run(['node','-e',PROGRAM,str(PROBE)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5,check=False)
        self.assertEqual(0,result.returncode,result.stderr.decode('utf-8','replace'))
        value=json.loads(result.stdout);self.assertEqual(28,value['faultCases'])
        self.assertEqual(1,value['validNativeLeafCalls']);self.assertEqual(0,value['conversionCalls'])
        self.assertFalse(value['nativeExecuted'] or value['nativeCompiled'])

    def test_native_source_order_has_typed_ids_before_conversion_and_before_clock_or_nonce(self):
        # Source-order counter ONLY. No native compiler or C++ runtime executes.
        header=(ROOT/'tests/device/native/PicoEmoteSourceTransaction.h').read_text()
        body=header[header.index('    static bool command'):header.index('    // Called again ONLY')]
        self.assertNotIn('QJsonObject::fromVariantMap',body)
        self.assertLess(body.index('field.userType()!=QMetaType::QString'),body.index('field.toString()'))
        cpp=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        body=cpp[cpp.index('QVariantMap TestScriptingInterface::featurePicoEmoteSourceTransaction('):cpp.index('QVariantMap TestScriptingInterface::featurePicoEmoteSourceOriginal(')]
        self.assertLess(body.index('PicoEmoteSourceTransaction::command(command)'),
            body.index('make_shared<const overte::e2e::PicoEmoteSourceTransactionRequest>'))


if __name__=='__main__':unittest.main()
