"""Actual included-source identity, compiled callers and timer responsibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_work as separate,snapshot_combined_work as combined
from ios.self_tests.snapshot_combined_work_fixture import packet,timer,advance,ROOT,URL,FILES,EPOCH


class SnapshotCombinedWorkTests(unittest.TestCase):
    def query(self,value):return dict(schemaVersion=1,commandId=value['requestId'],action=combined.ACTION,runId=value['runId'])
    def test_actual_default_main_included_snapshot_and_independent_utf16_pins_admit_without_debug_change(self):
        value=packet();row=combined.admit(value,URL,quiet=True);self.assertEqual(URL+'defaultScripts.js',row['manager']['url'])
        self.assertEqual(URL+'system/snapshot.js',row['sourceUrl']);self.assertNotEqual(row['code']['sha256'],row['codeSources']['evaluations'][1]['sha256'])
        pins=json.loads(combined.PIN_FILE.read_text());self.assertEqual(set(FILES),set(pins['sources']))
        for observed in row['codeSources']['evaluations']:
            path=observed['url'][len(URL):];self.assertEqual(pins['sources'][path],{key:observed[key] for key in ('codeUnits','sha256')})
    def test_separate_profile_and_legacy_timer_shapes_cannot_be_relabelled_as_combined(self):
        value=packet()
        with self.assertRaises(NativeUIError):separate.original(value)
        with self.assertRaises(NativeUIError):separate.command(self.query(value))
        from ios.self_tests.test_ios_snapshot_work import packet as legacy
        with self.assertRaises(NativeUIError):combined.original(legacy())
        value['source']['timerSources']['workers'][0]['timerWork']=dict(snapshotTimerWorkVersion=1,instance='e'*32,complete=True,timers=[])
        with self.assertRaises(NativeUIError):combined.original(value)
    def test_true_default_manager_main_and_actual_included_code_cannot_be_substituted(self):
        for fault in ('manager','main','snapshot','helper','missing','incomplete'):
            value=packet();row=value['source']['workers'][0]
            if fault=='manager':row['manager']['url']=URL+'system/snapshot.js'
            elif fault=='main':row['code']['sha256']='0'*64
            elif fault in ('snapshot','helper'):row['codeSources']['evaluations'][1 if fault=='snapshot' else 3]['sha256']='0'*64
            elif fault=='missing':row['codeSources']['evaluations'].pop()
            else:row['codeSources']['complete']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):combined.admit(value,URL,quiet=True)
    def test_initial_work_requires_real_helper_snapshot_chain_and_all_original_frames(self):
        for fault in ('snapshot','foreign','compiled','gap'):
            value=packet();original=value['source']['callerStacks'][0]
            if fault=='snapshot':original['callerModules'].pop(1)
            elif fault=='foreign':original['callerModules'][1]['url']=URL+'system/pal.js'
            elif fault=='compiled':original['callerStack']['frames'][1]['compiled']['sha256']='0'*64
            else:original['callerModules'][1]['frame']=3
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):combined.original(value)
    def test_real_single_shot_weak_death_does_not_hide_pending_native_dispatch_or_callback(self):
        value=packet();row=timer(value);combined.admit(value,URL,quiet=True)
        for fault in ('pending','callback','alive'):
            changed=deepcopy(value);actual=changed['source']['timerSources']['workers'][0]['timerWork']['timers'][0]
            if fault=='pending':actual.update(pendingDispatch=1,lastDispatchEpochMs=None)
            elif fault=='callback':actual.update(left=0,depth=1,pendingDispatch=1,lastDispatchEpochMs=None)
            else:actual['destroyedEpochMs']=None
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):combined.admit(changed,URL,quiet=True)
        self.assertIsNotNone(row['destroyedEpochMs'])
    def test_unrelated_timer_caller_or_wrong_actual_evaluation_cannot_enter_snapshot_ownership(self):
        for fault in ('module','code','table'):
            value=packet();timer(value);work=value['source']['timerSources']['workers'][0]['timerWork'];caller=work['callerStacks'][0]
            if fault=='module':caller['callerModules'][0]['url']=URL+'system/pal.js'
            elif fault=='code':caller['callerStack']['frames'][0]['compiled']['sha256']='0'*64
            else:work['callerStacks']=[]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):combined.original(value)
    def test_same_manager_timer_cannot_substitute_an_independent_v8_engine(self):
        value=packet();timer(value);combined.admit(value,URL,quiet=True)
        value['source']['timerSources']['workers'][0]['timerWork']['callerStacks'][0]['callerStack']['instance']='6'*32
        with self.assertRaises(NativeUIError):combined.admit(value,URL,quiet=True)
    def test_new_capture_cannot_rewrite_original_callers_evaluations_or_old_heartbeat(self):
        before=packet();new=advance(before);combined.validate(new,self.query(new),42,previous=before)
        for fault in ('caller','code','event','nonce','pid'):
            changed=deepcopy(new)
            if fault=='caller':changed['source']['callerStacks'][1]['id']='5'*32;changed['source']['workers'][0]['latest']['callerStackId']='5'*32
            elif fault=='code':changed['source']['workers'][0]['codeSources']['evaluations']=[]
            elif fault=='event':changed['source']['workers'][0]['latest']['callerSequence']+=1
            elif fault=='nonce':changed['requestId']=before['requestId']
            else:changed['processId']=43
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):combined.validate(changed,self.query(changed),42,previous=before)
    def test_fixed_original_files_use_existing_bounded_compact_private_atomic_writer(self):
        text=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();save=text[text.index('void TestScriptingInterface::saveObject'):]
        compact=save[save.index('// Preserve these passive sources'):save.index('// Append trailing slash')]
        private=save[save.index('QString filepath = QDir::cleanPath'):save.index('QSaveFile output(filepath)')]
        for name in ('feature-ios-snapshot-combined-work.json','feature-ios-snapshot-preflight-http.json'):
            self.assertIn('filename=="'+name+'"',compact);self.assertIn('filename == "'+name+'"',private)
        self.assertIn('QJsonDocument::Compact',compact);self.assertIn('QFileInfo(filepath).isSymLink()',private)
        writer=save[save.index('QSaveFile output(filepath)'):]
        self.assertIn('output.setDirectWriteFallback(false)',writer);self.assertIn('QFile::ReadOwner | QFile::WriteOwner',writer)


if __name__=='__main__':unittest.main()
