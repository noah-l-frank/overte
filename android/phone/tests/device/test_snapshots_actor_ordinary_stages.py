"""Actual TLS/IPC boundaries for ordinary Actor preparation and current reads.

Native/SDK/render inputs remain explicit host producers. A separate credentialed
process releases the actual source lock; no device or Android runtime is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_actor_primary_cue as cue
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import unpack
from overte_phone_snapshots_role import PhoneSnapshotsRole

HOOK=r'''
ordinary_batch=module.PhoneSnapshotsActor.ordinary_batch
stage_mutations=[]
inline_stats=dict(entries=0,lockedReads=0,sleeps=0,mutations=0)
def inline_batch(self,role,prepared):
    self.feature.lock.assert_held()
    assert role.system and self.feature.state['handoff'] is not None
    inline_stats['entries']+=1
    read=role.read;bound=self.feature.bound
    def locked_read(*args,**kwargs):
        self.feature.lock.assert_held();inline_stats['lockedReads']+=1
        return read(*args,**kwargs)
    def late_bound():
        result=bound()
        if mode=='inline-os-late-save' and self.state['pending'] is not None and not inline_stats['mutations']:
            inline_stats['mutations']+=1;role.frames[0]['controlledLateOsGraph']=True
        return result
    role.read=locked_read;self.feature.bound=late_bound
    try:return ordinary_batch(self,role,prepared)
    finally:role.read=read;self.feature.bound=bound
def paused_batch(self,role,prepared):
    if mode.startswith('inline-os'):return inline_batch(self,role,prepared)
    if mode!='pause':return ordinary_batch(self,role,prepared)
    assert self.feature.lock._owner is None
    print(json.dumps(dict(stage='prepared',lockReleased=True,counts=counts,
        roleHeader=role.previous,frameCount=len(role.frames))),flush=True)
    release=json.loads(sys.stdin.readline());fault=release.get('fault')
    scope=getattr(adapter,'_existing_input_scope',None)
    if fault=='scope':adapter._existing_input_scope=dict(scope or {})
    if fault=='graph':role.frames.append(dict(controlledForeignGraph=True))
    bound=self.feature.bound;restore=role.restore_originals;restored=[]
    def actual_restore(*args,**kwargs):
        result=restore(*args,**kwargs);restored.append(True);return result
    def late_bound():
        result=bound()
        if ((fault=='late-native-graph' and restored) or (fault=='late-save-graph' and self.state['pending'] is not None)) and not stage_mutations:
            stage_mutations.append(True);role.frames[0]['controlledLateGraph']=True
        return result
    role.restore_originals=actual_restore;self.feature.bound=late_bound
    try:return ordinary_batch(self,role,prepared)
    finally:
        adapter._existing_input_scope=scope;self.feature.bound=bound
        role.restore_originals=restore
module.PhoneSnapshotsActor.ordinary_batch=paused_batch
'''
ANCHOR="module.PhoneSnapshotsRole=construct\nflow=adapter.actor('synthetic',RUN,client)"
assert cue.CHILD.count(ANCHOR)==1
CHILD=cue.CHILD.replace(ANCHOR,"module.PhoneSnapshotsRole=construct\n"+HOOK+"\nflow=adapter.actor('synthetic',RUN,client)")
CHILD=CHILD.replace('state=state)),flush=True)','state=state,stageMutations=len(stage_mutations),inline=inline_stats)),flush=True)')
SLEEP_ANCHOR='    request=client.request;save=flow.save;write=flow.store.write'
assert CHILD.count(SLEEP_ANCHOR)==1
CHILD=CHILD.replace(SLEEP_ANCHOR,SLEEP_ANCHOR+r'''
    sleep=flow.feature.sleep
    def sleeping(value):
        if mode.startswith('inline-os') and value==.1:
            inline_stats['sleeps']+=1;raise AssertionError('OS ordinary acquisition must not release/yield between stages')
        return sleep(value)
    flow.feature.sleep=sleeping
''')
CHILD=CHILD.replace('finally:client.request=request;flow.save=save;flow.store.write=write',
    'finally:client.request=request;flow.save=save;flow.store.write=write;flow.feature.sleep=sleep')


class SnapshotActorOrdinaryStagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cue.SnapshotActorPrimaryCueTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):cue.SnapshotActorPrimaryCueTests.tearDownClass.__func__(cls)
    def setUp(self):
        with patch.object(cue,'CHILD',CHILD):cue.SnapshotActorPrimaryCueTests.setUp(self)
    receive=cue.SnapshotActorPrimaryCueTests.receive
    step=cue.SnapshotActorPrimaryCueTests.step
    primary=cue.SnapshotActorPrimaryCueTests.primary
    entries=cue.SnapshotActorPrimaryCueTests.entries

    def prepared(self,*,cold=False):
        first=self.step(cold=cold);self.assertIsNone(first['error']);self.primary()
        before=deepcopy(first)
        paused=self.step('pause');self.assertEqual('prepared',paused['stage'])
        self.assertTrue(paused['lockReleased']);self.assertGreater(paused['frameCount'],0)
        self.assertEqual(first['counts']['reads'],paused['counts']['reads'])
        self.assertEqual(first['counts']['posts'],paused['counts']['posts'])
        return before,paused

    def release(self,fault=None):
        self.child.stdin.write(json.dumps(dict(fault=fault))+'\n');self.child.stdin.flush()
        return self.receive()

    def unchanged(self,before,result,*,error):
        self.assertEqual(error,result['error'])
        self.assertEqual(before['counts']['reads'],result['counts']['reads'])
        self.assertEqual(before['counts']['posts'],result['counts']['posts'])
        self.assertEqual(before['state']['primaryCue'],result['state']['primaryCue'])
        self.assertEqual(before['state']['pending'],result['state']['pending'])
        self.assertEqual(before['counts']['posts'],len(self.entries()))

    def actual_share_scope(self):
        self.rig.act('open');self.rig.act('capture',dict(mode='still',format='png'));self.primary()
        before=self.step();self.assertIsNone(before['error'])
        self.rig.act('share-open');measured=self.primary()
        self.assertTrue(measured['state']['shareSheet']);self.assertEqual(1,measured['state']['files'])
        return before

    def test_actual_os_share_acquires_own_sample_inline_without_releasing_source_lock(self):
        before=self.actual_share_scope();result=self.step('inline-os')
        self.assertIsNone(result['error']);self.assertFalse(result['result'])
        self.assertEqual(dict(entries=1,lockedReads=1,sleeps=0,mutations=0),result['inline'])
        self.assertEqual(before['counts']['reads']+1,result['counts']['reads'])
        self.assertEqual(before['counts']['posts']+1,result['counts']['posts'])
        self.assertEqual(self.primary_store.read(),result['state']['primaryCue']['header'])
        actual=self.entries()[-1];self.assertTrue(actual['facts']['shareSheet'])
        self.assertGreater(actual['actorSequence'],before['state']['last']['receipt']['actorSequence'])
        self.assertEqual(actual,result['state']['last']['receipt'])

    def test_actual_os_share_retains_last_native_save_graph_guard_before_post(self):
        before=self.actual_share_scope()
        originals={p:p.read_bytes() for p in self.rig.root.glob('emote-frame-snapshots-'+cue.harness.RUN+'-actor-*.json')}
        self.assertTrue(originals);result=self.step('inline-os-late-save')
        self.assertEqual('NativeUIError',result['error'])
        self.assertEqual(dict(entries=1,lockedReads=1,sleeps=0,mutations=1),result['inline'])
        self.assertEqual(before['counts']['reads']+1,result['counts']['reads'])
        self.assertEqual(before['counts']['posts'],result['counts']['posts'])
        self.assertEqual(before['state']['primaryCue'],result['state']['primaryCue'])
        self.assertEqual(before['state']['pending'],result['state']['pending'])
        self.assertEqual(before['counts']['posts'],len(self.entries()))
        for path,raw in originals.items():self.assertEqual(raw,path.read_bytes())

    def test_ready_primary_can_advance_under_released_lock_before_own_current_sample(self):
        before,_=self.prepared()
        self.primary()  # Genuine parent acquisition needs the child's OS lock.
        latest=self.primary_store.read()
        result=self.release();self.assertIsNone(result['error'])
        self.assertEqual(before['counts']['reads']+1,result['counts']['reads'])
        self.assertEqual(before['counts']['posts']+1,result['counts']['posts'])
        self.assertEqual(latest,result['state']['primaryCue']['header'])
        self.assertGreater(result['state']['last']['receipt']['actorSequence'],before['state']['last']['receipt']['actorSequence'])

    def test_one_genuine_activation_and_normal_input_discards_preparation_then_reads_fresh(self):
        before,_=self.prepared();self.rig.act('open')
        deferred=self.release();self.unchanged(before,deferred,error=None)
        self.assertFalse(deferred['result']);self.primary()
        current=self.step();self.assertIsNone(current['error'])
        self.assertEqual(before['counts']['reads']+1,current['counts']['reads'])
        self.assertTrue(self.entries()[-1]['facts']['open'])

    def test_primary_actual_reading_journal_is_deferred_without_adoption_and_recovers(self):
        before,_=self.prepared()
        feature=self.rig.adapter._snapshots_feature('test-only-appium',cue.harness.RUN)
        with ExitStack() as session:
            with feature.lock.held():
                session.enter_context(feature.adapter.existing_input_session(feature.selector))
                feature.load();role=PhoneSnapshotsRole(feature,'primary');batch=role.batch
                def interrupted():batch();raise NativeUIError('Controlled interruption after actual source group')
                role.batch=interrupted
                with self.assertRaises(NativeUIError):role.read(role.state['sequence'])
        pending=self.primary_store.read();self.assertEqual('reading',unpack(pending['payload'])[0]['phase'])
        deferred=self.release();self.unchanged(before,deferred,error=None)
        self.assertEqual(pending,self.primary_store.read())
        self.primary();result=self.step();self.assertIsNone(result['error'])
        self.assertEqual(before['counts']['reads']+1,result['counts']['reads'])

    def test_known_actor_header_missing_and_foreign_are_red_before_current_read_or_post(self):
        before,paused=self.prepared();store=self.primary_store.__class__(self.primary_store.path.with_name('phone-snapshots-actor-originals.json'))
        actual=store.read();self.assertEqual(paused['roleHeader'],actual)
        path=store.path;backup=path.with_name(path.name+'.controlled');path.rename(backup)
        try:self.unchanged(before,self.release(),error='NativeUIError');self.assertFalse(path.exists())
        finally:backup.rename(path)
        before,_=self.prepared(cold=True);actual=store.read()
        foreign=dict(actual,binding=dict(actual['binding'],targetFingerprint='f'*64));store.write(foreign,actual)
        try:self.unchanged(before,self.release(),error='NativeUIError');self.assertEqual(foreign,store.read())
        finally:store.write(actual,store.read())

    def test_scope_and_held_graph_mutations_are_red_without_acquisition(self):
        for fault in ('scope','graph'):
            with self.subTest(fault=fault):
                before,_=self.prepared(cold=True)
                self.unchanged(before,self.release(fault),error='NativeUIError')

    def test_old_original_bytes_changed_after_prepare_are_reopened_and_refused(self):
        before,_=self.prepared()
        paths=sorted(self.rig.root.glob('emote-frame-snapshots-'+cue.harness.RUN+'-actor-*.json'))
        self.assertTrue(paths);path=paths[0];raw=path.read_bytes();foreign=raw+b' '
        path.write_bytes(foreign)
        try:
            self.unchanged(before,self.release(),error='NativeUIError')
            self.assertEqual(foreign,path.read_bytes())
        finally:path.write_bytes(raw)

    def test_pending_save_native_callback_cannot_publish_changed_old_graph(self):
        before,_=self.prepared()
        paths=sorted(self.rig.root.glob('emote-frame-snapshots-'+cue.harness.RUN+'-actor-*.json'))
        originals={path:path.read_bytes() for path in paths};self.assertTrue(originals)
        result=self.release('late-save-graph');self.assertEqual(1,result['stageMutations'])
        self.assertEqual('NativeUIError',result['error'])
        self.assertEqual(before['counts']['reads']+1,result['counts']['reads'])
        self.assertEqual(before['counts']['posts'],result['counts']['posts'])
        self.assertEqual(before['state']['primaryCue'],result['state']['primaryCue'])
        self.assertEqual(before['state']['pending'],result['state']['pending'])
        self.assertEqual(before['counts']['posts'],len(self.entries()))
        for path,raw in originals.items():self.assertEqual(raw,path.read_bytes())

    def test_actual_native_guard_callback_cannot_change_old_graph_before_current_read(self):
        before,_=self.prepared();result=self.release('late-native-graph')
        self.assertEqual(1,result['stageMutations'])
        self.unchanged(before,result,error='NativeUIError')


if __name__=='__main__':unittest.main()
