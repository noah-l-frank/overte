"""Original lifetime protocol/history and source-age counterexamples; no VM/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_script_object_lifetimes import ACTION,NativeScriptObjectLifetimes,command,validate,destroyed
from adapters.normal_ui import NativeUIError

MANAGER='b'*32


class Boundary:
    def __init__(self):
        self.host=0.;self.epoch=20000;self.sequence=0;self.packet=None;self.calls=[];self.fault=None
        self.row=dict(instance=MANAGER,registeredEpochMs=19000,managerAlive=True,engineAlive=True,
            workerCreated=True,workerAlive=True,managerDestroyedEpochMs=0,engineDestroyedEpochMs=0,
            workerCreatedEpochMs=19001,workerDestroyedEpochMs=0)
    def send(self,request):
        command(request);self.calls.append(deepcopy(request));self.sequence+=1
        revision=2+sum(not self.row[key+'Alive'] for key in ('manager','engine','worker'))
        self.packet=dict(scriptObjectLifetimesVersion=1,commandId=request['commandId'],instance='a'*32,sequence=self.sequence,
            processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
            source=dict(complete=True,revision=revision,capturedEpochMs=self.epoch,objects=[deepcopy(self.row)]))
        if self.fault:self.fault(self.packet)
    def reader(self):
        return NativeScriptObjectLifetimes(self.send,lambda:json.dumps(self.packet),lambda:self.epoch,lambda:True,31,
            monotonic=lambda:self.host,sleep=lambda value:setattr(self,'host',self.host+value))


class NativeScriptObjectLifetimeTests(unittest.TestCase):
    def test_actual_all_three_object_deaths_are_required_and_original_tombstones_survive_cold_restore(self):
        b=Boundary();reader=b.reader();before=reader.read()
        with self.assertRaises((ValueError,RuntimeError)):destroyed(before,MANAGER)
        for kind in ('manager','engine','worker'):
            b.epoch+=1;b.row[kind+'Alive']=False;b.row[kind+'DestroyedEpochMs']=b.epoch
            value=reader.read(reader.last['sequence'])
            if kind!='worker':
                with self.assertRaises((ValueError,RuntimeError)):destroyed(value,MANAGER)
        self.assertFalse(destroyed(value,MANAGER)['workerAlive'])
        cold=b.reader();cold.restore(value);fresh=cold.read(value['sequence'])
        self.assertGreater(fresh['sequence'],value['sequence']);self.assertEqual(value['source']['objects'],fresh['source']['objects'])

    def test_disappearing_or_resurrected_original_object_and_retimed_death_cannot_advance_cursor(self):
        for fault in ('missing','birth','death','resurrection'):
            with self.subTest(fault=fault):
                b=Boundary();b.row.update(managerAlive=False,managerDestroyedEpochMs=19500);reader=b.reader();old=reader.read()
                def edit(value):
                    source=value['source'];row=source['objects'][0]
                    if fault=='missing':source.update(objects=[],revision=0)
                    elif fault=='birth':row['registeredEpochMs']+=1
                    elif fault=='death':row['managerDestroyedEpochMs']+=1
                    else:row.update(managerAlive=True,managerDestroyedEpochMs=0);source['revision']-=1
                b.fault=edit
                with self.assertRaises(NativeUIError):reader.read(old['sequence'])
                self.assertEqual(old,reader.last)

    def test_unknown_incomplete_boolean_or_forged_revision_and_unborn_worker_refuse(self):
        b=Boundary();value=b.reader().read();request=b.calls[0]
        for fault in ('unknown','incomplete','bool','revision','unborn'):
            broken=deepcopy(value);source=broken['source'];row=source['objects'][0]
            if fault=='unknown':source['expectedDestroyed']=True
            elif fault=='incomplete':source['complete']=False
            elif fault=='bool':row['managerDestroyedEpochMs']=False
            elif fault=='revision':source['revision']+=1
            else:row['workerCreated']=False
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(broken,request,31,20000)
        with self.assertRaises((ValueError,RuntimeError)):destroyed(value,'c'*32)

    def test_final_copy_or_guard_cannot_hide_elapsed_host_or_native_age_and_failed_cursor_stays_uncommitted(self):
        for fault in ('copy','guard','native','regression'):
            with self.subTest(fault=fault):
                b=Boundary();reader=b.reader();original=deepcopy
                def copy(value):
                    result=original(value)
                    if type(value) is dict and 'scriptObjectLifetimesVersion' in value:b.host+=2
                    return result
                calls=[0]
                def guard():
                    calls[0]+=1
                    if calls[0]==4:
                        if fault=='guard':b.host+=2
                        elif fault=='native':b.epoch+=2000
                        elif fault=='regression':b.epoch-=1
                    return True
                reader.guard=guard
                with patch('adapters.native_script_object_lifetimes.deepcopy',copy if fault=='copy' else original),self.assertRaises(NativeUIError):reader.read()
                self.assertIsNone(reader.last);self.assertEqual(1,len(b.calls))

    def test_closed_original_probe_branch_forwards_native_only_and_never_invents_absence(self):
        root=Path(__file__).resolve().parents[3];source=(root/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=source.index('        if (command && command.action === "feature-script-object-lifetimes-observe") {')
        end=source.index('        if (command && command.action === "feature-script-work-observe") {',start)
        branch=source[start:end]
        js='''const assert=require('node:assert/strict');let lastScriptObjectLifetimesRequest='',calls=0,files=[];
function objectKeysMatch(value,keys){return JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.slice().sort());}
const Test={featureScriptObjectLifetimes(c){calls++;return {scriptObjectLifetimesVersion:1,commandId:c.commandId,original:true};},saveObject(v,p){files.push([v,p]);}};
function apply(command){BRANCH return false;}
const command={schemaVersion:1,commandId:'a'.repeat(32),action:'feature-script-object-lifetimes-observe'};
assert.equal(apply(command),true);apply(command);assert.equal(calls,1);assert.equal(files.length,1);
assert.equal(files[0][0].original,true);assert.equal(files[0][1],'feature-script-object-lifetimes.json');
apply({...command,commandId:'b'.repeat(32),expectedDestroyed:true});assert.equal(calls,1);
delete Test.featureScriptObjectLifetimes;apply({...command,commandId:'c'.repeat(32)});
assert.equal(files[1][0].available,false);assert.equal(files[1][0].source,undefined);
'''.replace('BRANCH',branch)
        subprocess.run(['node','-e',js],check=True,timeout=10,capture_output=True)

    def test_actual_pico_factory_keeps_original_source_lock_and_passive_private_file_route(self):
        from adapters.script_journey.lock import ScriptSourceLock
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as fixture_module
        fixture=fixture_module.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter=fixture.instance();boundary=Boundary();lock=ScriptSourceLock(fixture.fixture.root/'script-sources.lock')
        def canonical(target,provided):
            self.assertEqual(fixture.fake.target,target);self.assertIs(lock,provided);return lock
        adapter._script_journey=lambda:SimpleNamespace(_lock=canonical)
        adapter._native_feature_observer=lambda target:SimpleNamespace(send=boundary.send,guard=lambda:True,
            clock_ms=lambda:boundary.epoch,pid=31,monotonic=lambda:boundary.host,sleep=lambda seconds:None)
        reads=[]
        def original(target,package,path,**options):
            reads.append((target,package,path,options));return json.dumps(boundary.packet)
        adapter.adb.read_debug_app_file=original;events=deepcopy(fixture.fake.events)
        with lock.held():reader=adapter._script_object_lifetimes(fixture.fake.target,source_lock=lock);value=reader.read()
        self.assertEqual(31,value['processId']);self.assertEqual(events,fixture.fake.events)
        self.assertEqual([(fixture.fake.target,'org.overte.pico','files/overte-e2e/feature-script-object-lifetimes.json',{'attempts':1})],reads)
        before=len(boundary.calls)
        with self.assertRaises(NativeUIError):reader.read(value['sequence'])
        self.assertEqual(before,len(boundary.calls))


if __name__=='__main__':unittest.main()
