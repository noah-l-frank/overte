"""Actual Probe branch in Node; Native provider is explicitly a declared model.

Native files are source-only/uncompiled; no Android input, SDK or app runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[3]
PROBE=ROOT/'tests/device/probe/overte_e2e_probe.js'
NATIVE=(ROOT/'interface/src/scripting/TestScriptingInterface.h',ROOT/'interface/src/scripting/TestScriptingInterface.cpp')


class LifecyclePendingDeliveryTests(unittest.TestCase):
    def setUp(self):
        def pin(path):
            value=path.stat();return hashlib.sha256(path.read_bytes()).hexdigest(),(value.st_dev,value.st_ino,value.st_mode,
                value.st_uid,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)
        self.pins={path:pin(path) for path in (PROBE,*NATIVE)}
        self.addCleanup(lambda:self.assertEqual(self.pins,{path:pin(path) for path in self.pins}))
        source=PROBE.read_text();a=source.index('        if (command && command.action === "feature-pico-pending-read") {')
        b=source.index('\n        if (command && command.schemaVersion === 1',a)
        wrapper=source[a:b]
        a=source.index('        if (command && command.action === "feature-pending-commit-owner") {')
        b=source.index('\n        if (command && command.action === "feature-web-runtime-observe")',a)
        self.program=r'''const assert=require('node:assert/strict');
let calls=0,saves=0,marker=1,throwSave=false,commands=[],saved=[];
let Test={featurePicoPendingReadVersion:()=>marker,featurePendingCommitOwner:c=>{calls++;commands.push(c);return {commandId:c.commandId};},saveObject:(value,path)=>{assert.equal(path,'feature-pending-commit-owner.json');saves++;saved.push(value);if(throwSave)throw Error('uncertain actual save');}};
let lastPicoPendingReadCommandId='';
function objectKeysMatch(value,expected){return value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===expected.slice().sort().join(',');}
function applyClientCommand(command){
'''+wrapper+source[a:b]+r'''
}
function command(){return {schemaVersion:1,commandId:'a'.repeat(32),action:'feature-pico-pending-read',operation:'observe',runId:'b'.repeat(32),eventId:'',picoPendingReadVersion:1};}
'''

    def run_model(self,assertions):
        result=subprocess.run(['node','-e',self.program+assertions],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=5,check=False,text=True)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_new_probe_route_publishes_each_exact_original_operation_once_and_preserves_native_dto(self):
        self.run_model(r'''
let i=0;
for(let operation of ['observe','focus','type','hold','attempt','release']){
 let c=command();c.commandId=(++i).toString().repeat(32);c.operation=operation;
 if(operation!=='observe'){c.ownerInstance='d'.repeat(32);c.intentSequence=i;}
 if(['focus','type','hold','attempt'].includes(operation)){c.fieldToken='e'.repeat(32);c.observationSequence=i;}
 if(['attempt','release'].includes(operation))c.eventId='f'.repeat(32);
 applyClientCommand(c);applyClientCommand(c);
 assert.equal(calls,i);assert.equal(saves,i);
 assert.equal(commands[i-1].action,'feature-pending-commit-owner');assert.equal(commands[i-1].operation,operation);
 assert.equal(commands[i-1].picoPendingReadVersion,undefined);assert.equal(c.action,'feature-pico-pending-read');
}
''')

    def test_actual_probe_refuses_wrong_types_ios_extra_fields_and_unknown_operation_before_consume(self):
        self.run_model(r'''
const bads=[c=>c.operation=['observe'],c=>c.schemaVersion=true,c=>c.commandId='ios-'+c.commandId,c=>c.operation='unknown',c=>c.runId=4,c=>c.eventId='bad',c=>c.picoPendingReadVersion=true,c=>c.extra=1,c=>{c.operation='focus';c.ownerInstance='d'.repeat(32);c.intentSequence=true;c.fieldToken='e'.repeat(32);c.observationSequence=1;}];
for(let mutate of bads){lastPicoPendingReadCommandId='';let c=command();mutate(c);applyClientCommand(c);assert.equal(calls,0);assert.equal(saves,0);assert.equal(lastPicoPendingReadCommandId,'');}
''')

    def test_actual_probe_marker_unavailable_and_unknown_save_never_resend_while_legacy_repeats_unchanged(self):
        self.run_model(r'''
marker=0;applyClientCommand(command());assert.equal(lastPicoPendingReadCommandId,'');assert.equal(calls,0);marker=1;
throwSave=true;assert.throws(()=>applyClientCommand(command()));assert.equal(calls,1);assert.equal(saves,1);applyClientCommand(command());assert.equal(calls,1);assert.equal(saves,1);
throwSave=false;let old=command();old.action='feature-pending-commit-owner';delete old.picoPendingReadVersion;applyClientCommand(old);applyClientCommand(old);assert.equal(calls,3);assert.equal(saves,3);
''')

    def test_native_marker_is_only_compile_presence_with_no_gui_provider_or_new_blocking_queue(self):
        source=NATIVE[1].read_text();a=source.index('int TestScriptingInterface::featurePicoPendingReadVersion() {');b=source.index('\n}\n',a)
        body=source[a:b]
        self.assertIn('defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)',body)
        self.assertIn('return 1;',body);self.assertIn('return 0;',body)
        for forbidden in ('invokeMethod','qApp->','BlockingQueuedConnection','_featureLifecycle','pendingCommitProvider'):
            self.assertNotIn(forbidden,body)
        self.assertIn('Q_INVOKABLE int featurePicoPendingReadVersion();',NATIVE[0].read_text())

    def test_actual_e2e_pending_writer_sets_owner_only_mode_before_write_commit_and_generic_fallback(self):
        source=NATIVE[1].read_text();a=source.index('void TestScriptingInterface::saveObject(');b=source.index('void TestScriptingInterface::showMaximized()',a)
        body=source[a:b];a=body.index('#if defined(OVERTE_E2E_FEATURE_TESTS)\n');b=body.index('#endif\n    QSaveFile file(filepath);',a)
        feature=body[a:b]
        self.assertIn('const bool featureResult=filename.startsWith("feature-");',feature)
        self.assertIn('filename == "feature-pending-commit-owner.json"',feature)
        create=feature.index('QSaveFile output(filepath);')
        no_fallback=feature.index('output.setDirectWriteFallback(false);',create)
        owner_mode=feature.index('output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)',no_fallback)
        write=feature.index('output.write(jsonData)',owner_mode)
        commit=feature.index('output.commit();',write)
        self.assertLess(create,no_fallback);self.assertLess(no_fallback,owner_mode)
        self.assertLess(owner_mode,write);self.assertLess(write,commit)
        self.assertIn('return;',feature[commit:])
