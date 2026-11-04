"""Normal private browser prefix; native/render/GPU aggregation are host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import unittest
import uuid
from unittest.mock import patch

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.world_render_retirements import PicoWorldRenderRetirements,command
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseRetired
from feature_journeys.scenarios import VERSION
from self_tests import test_pico_tablet_web_stereo_flow as seams


class BrowserCaptureNamespaceTests(unittest.TestCase):
    """Actual directory membership only; no product/source or byte qualification."""
    def setUp(self):
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.state=self.root/'state';self.artifacts=self.root/'artifacts'
        self.state.mkdir();self.artifacts.mkdir();self.run='a'*32
        primary=PrivateFeatureState(self.state/'pico-tablet-web-primary.json')
        metadata=PrivateFeatureState(self.artifacts/('tablet-web-'+self.run+'-capture.native.json'))
        for store in (primary,metadata):store.path.write_text('{}')
        self.owner=PicoBrowserCaptureRetirement.__new__(PicoBrowserCaptureRetirement)
        self.owner.primary=SimpleNamespace(store=primary,artifact_root=self.artifacts,run=self.run)
        self.owner.store=PrivateFeatureState(self.state/'pico-tablet-web-capture-retirement.json')
        self.owner.catalog=SimpleNamespace(rows={name:dict(store=store) for name,store in (('primary',primary),('metadata',metadata))})
        self.owner.indexed_rows=self.owner._sealed_indexed_rows=tuple(
            (name,row['store'].path,None,None,None,None) for name,row in self.owner.catalog.rows.items())
        self.owner._inventory=self.owner._sealed_inventory=None
        self.owner.initialize_pngs();self.owner.freeze_inventory()

    def test_same_complete_names_ignore_only_owned_root_children_and_unrelated_entries(self):
        owner=self.owner;owner.inventory()
        owner.store.path.write_text('{}')
        owner.store.path.with_name(owner.store.path.name+'.frame-000.json').write_text('{}')
        (self.state/'unrelated').mkdir();(self.artifacts/'unrelated').write_text('unrelated')
        owner.inventory()

    def test_unexpected_files_directories_and_symlinks_all_remain_members(self):
        for parent,prefix in ((self.state,'pico-tablet-web-'),
                (self.artifacts,'tablet-web-'+self.run+'-'),(self.artifacts,'graphics-'+self.run+'-')):
            for kind in ('file','directory','symlink'):
                with self.subTest(prefix=prefix,kind=kind):
                    path=parent/(prefix+'unexpected')
                    if kind=='file':path.write_text('unexpected')
                    elif kind=='directory':path.mkdir()
                    else:path.symlink_to(self.root/'missing-target')
                    try:
                        with self.assertRaises(NativeUIError):self.owner.inventory()
                    finally:
                        if kind=='directory':path.rmdir()
                        else:path.unlink()
        self.owner.inventory()

    def test_frozen_names_do_not_hide_changed_current_row_path_or_run(self):
        owner=self.owner;row=owner.catalog.rows['primary'];original=row['store']
        row['store']=PrivateFeatureState(original.path.with_name('pico-tablet-web-foreign.json'))
        with self.assertRaises(NativeUIError):owner.inventory()
        row['store']=original;owner.primary.run='b'*32
        with self.assertRaises(NativeUIError):owner.inventory()
        owner.primary.run=self.run;owner.catalog.rows.pop('metadata')
        with self.assertRaises(NativeUIError):owner.inventory()


class PicoBrowserCaptureRetirementTests(unittest.TestCase):
    def setUp(self):
        base=seams.PicoTabletWebStereoFlowTests();base.setUp();self.addCleanup(base.doCleanups)
        self.f,self.model=base.fixture,base.model
        # The actor retains its own lock object for the SAME kernel lock inode.
        self.f.actor.lock=ScriptSourceLock(self.f.primary.lock.path)
        self.batches=[];self.raw='';self.batch_sequence=0;self.mutate=None;self.lose=False
        self.f.target._tablet_web_retired_captures_observer=self.reader
        self.addCleanup(self.close_host)

    def close_host(self):
        owner=self.f.primary.capture_retirement
        if owner is not None:self.assertTrue(owner.catalog.close_host())

    def actor_publish(self):
        target,model=self.f.target,self.model;old_target,old_model=target.lock,model.lock
        target.lock=model.lock=self.f.actor.lock
        try:return self.f.actor.publish()
        finally:target.lock,model.lock=old_target,old_model

    def baseline(self):
        f=self.f;f.activate();f.primary.prepare();f.act('open')
        f.primary.observe(dict(contractVersion=VERSION,runId=f.run,afterSequence=0));self.actor_publish()
        f.act('close');f.activate('cleanup');f.primary.cleanup(dict(contractVersion=VERSION,runId=f.run))
        for _ in range(14):
            f.primary.observe(dict(contractVersion=VERSION,runId=f.run,afterSequence=0))
            self.actor_publish();f.clock.sleep(.25)
        for flow in (f.primary,f.actor):
            error=None
            with flow.lock.held():
                try:state=flow.role_state()
                except Exception as caught:error=caught
            if error is not None:raise error
            self.assertTrue(state['quiet']['complete'])
        f.client.close()
        with self.assertRaises(PhaseRetired):self.actor_publish()
        self.assertTrue(f.actor.actor_retirement.completed)

    def reader(self,target,proofs,lock,run):
        f=self.f;self.assertEqual('target',target);self.assertIs(lock,f.primary.lock);lock.assert_held()
        def guard():
            lock.assert_held();f.target._tablet_web_capture_guard(target,lock);return True
        def send(request):
            command(request);self.batches.append(deepcopy(request));self.batch_sequence+=1
            requested=f.clock.epoch();captures=[]
            for capture in request['captures']:
                self.model.inventory.send(dict(schemaVersion=1,commandId=uuid.uuid4().hex,
                    action='feature-world-render-receipts',operation='inspect',**capture))
                captures.append(deepcopy(self.model.inventory.value))
            packet=dict(worldRenderRetirementsVersion=1,requestId=request['commandId'],runId=run,instance=proofs[0]['memory']['instance'],
                processId=31,sequence=self.batch_sequence,requestedEpochMs=requested,capturedEpochMs=f.clock.epoch(),captures=captures)
            if self.mutate:self.mutate(packet)
            self.raw='' if self.lose else json.dumps(packet)
        return PicoWorldRenderRetirements(send,lambda:self.raw,f.clock.epoch,guard,31,f.target.binding,lock,run,proofs,
            monotonic=f.clock.now,sleep=f.clock.sleep)

    def test_complete_original_histories_share_durable_queries_and_three_second_all_capture_quiet(self):
        self.baseline();f=self.f;before=len(f.target.command_log)
        value=f.primary.retire_original_captures(f.actor);owner=f.primary.capture_retirement
        self.assertTrue(owner.completed);self.assertEqual(value,owner.receipt());self.assertTrue(value['complete'])
        from adapters.json_original_value import container_dimensions
        self.assertIsNone(owner._admission_values);self.assertIsNone(owner._sealed_admission_values)
        self.assertEqual(0,owner._admission_wrapper_bytes)
        plan=container_dimensions(dict(scope=owner.scope,owner=owner.owner,proofs=owner.proofs),
            max_nodes=65536,max_depth=16)
        credit=owner.catalog.value_cache.auxiliary_credit(512*len(owner.catalog.rows)+65536)
        self.assertTrue(plan is None or plan[4]>credit)
        self.assertIsNot(f.primary.lock,f.actor.lock);self.assertGreaterEqual(len(owner.proofs),2)
        self.assertEqual({'primary','actor'},{row['owner']['role'] for row in owner.proofs})
        self.assertGreaterEqual(len(owner.frames),3);self.assertEqual(len(owner.frames),len(self.batches))
        first,last=(json.loads(owner.frames[index]) for index in (0,-1))
        self.assertGreaterEqual(last['host']-first['host'],3)
        self.assertTrue(all(b['capturedEpochMs']-a['capturedEpochMs']>=3000
            for a,b in zip(first['packet']['captures'],last['packet']['captures'])))
        self.assertEqual(before,len(f.target.command_log));self.assertTrue(owner.catalog.rows)
        self.assertTrue(all(row['store'].path.exists() for row in owner.catalog.rows.values()))
        self.assertTrue(all((f.artifacts/row['value']['name']).exists() for row in owner.pngs))
        with self.assertRaises(NativeUIError):f.primary.retire_original_captures(f.actor)
        with self.assertRaises(NativeUIError):f.primary.finalize()

    def test_original_round_work_consumes_poll_period_without_shortening_three_second_quiet(self):
        from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
        self.baseline();f=self.f;append=PicoBrowserCaptureRetirement.append;before=len(f.target.command_log)
        sleep=f.primary.sleep;delays=[]
        def recorded(seconds):delays.append(seconds);return sleep(seconds)
        def work(owner,row,*args,**kwargs):
            result=append(owner,row,*args,**kwargs)
            if row['kind']=='absence-window':f.clock.sleep(.35) # Declared host work only.
            return result
        with patch.object(PicoBrowserCaptureRetirement,'append',work),patch.object(f.primary,'sleep',recorded):
            value=f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement;frames=[json.loads(raw) for raw in owner.frames]
        self.assertTrue(value['complete']);self.assertTrue(owner.completed)
        self.assertEqual([.01]*(len(frames)-1),delays)
        self.assertTrue(all(0<b['host']-a['host']<=.5 for a,b in zip(frames,frames[1:])))
        self.assertGreaterEqual(frames[-1]['host']-frames[0]['host'],3)
        self.assertTrue(all(b['capturedEpochMs']-a['capturedEpochMs']>=3000
            for a,b in zip(frames[0]['packet']['captures'],frames[-1]['packet']['captures'])))
        self.assertEqual(before,len(f.target.command_log))

    def test_genuine_overlong_round_still_refuses_original_half_second_cadence_and_cannot_retry(self):
        from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
        self.baseline();f=self.f;append=PicoBrowserCaptureRetirement.append
        def work(owner,row,*args,**kwargs):
            result=append(owner,row,*args,**kwargs)
            if row['kind']=='absence-window':f.clock.sleep(.55)
            return result
        with patch.object(PicoBrowserCaptureRetirement,'append',work),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement;count=len(self.batches)
        self.assertTrue(owner.failed);self.assertFalse(owner.completed);self.assertEqual(1,len(owner.frames))
        with self.assertRaises(NativeUIError):owner.run()
        self.assertEqual(count,len(self.batches));self.assertTrue(all(row['store'].path.exists() for row in owner.catalog.rows.values()))

    def test_fast_round_keeps_remaining_nominal_period_and_actual_final_query_bounds(self):
        self.baseline();f=self.f;sleep=f.primary.sleep;delays=[]
        def recorded(seconds):delays.append(seconds);return sleep(seconds)
        with patch.object(f.primary,'sleep',recorded):f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement
        self.assertTrue(owner.completed);self.assertEqual(len(owner.frames)-1,len(delays))
        self.assertTrue(all(.01<=delay<=.2 for delay in delays),delays)
        self.assertTrue(any(delay>.01 for delay in delays),delays)
        self.assertEqual(owner.previous,owner.receipt())

    def test_query_intent_clock_jump_prevents_native_query_and_cold_adoption(self):
        self.baseline();f=self.f;write=PrivateFeatureState.write;fired=[]
        def late(store,value,previous):
            write(store,value,previous)
            if store.path.name=='pico-tablet-web-capture-retirement.json' and value['phase']=='reading' and value['pending'] is not None and not fired:
                fired.append(True);f.clock.base+=2000
        with patch.object(PrivateFeatureState,'write',late),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement;self.assertTrue(owner.failed);self.assertEqual([],self.batches)
        self.assertEqual('reading',owner.store.read()['phase']);self.assertIsNotNone(owner.store.read()['pending'])
        from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
        cold=PicoBrowserCaptureRetirement(f.primary,f.actor);self.addCleanup(cold.catalog.close_host)
        with self.assertRaises(NativeUIError):cold.run()
        self.assertEqual([],self.batches)

    def test_lost_batch_result_retains_intent_all_sources_and_does_not_resend(self):
        self.baseline();f=self.f;self.lose=True
        with self.assertRaises(NativeUIError):f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement;self.assertTrue(owner.failed);self.assertFalse(owner.completed)
        self.assertEqual(1,len(self.batches));self.assertEqual(self.batches[0],owner.store.read()['pending'])
        self.assertTrue(all(row['store'].path.exists() for row in owner.catalog.rows.values()))
        with self.assertRaises(NativeUIError):owner.run()
        self.assertEqual(1,len(self.batches))

    def test_current_role_cannot_omit_an_older_original_history_capture(self):
        self.baseline();f=self.f
        with f.primary.lock.held():state=deepcopy(f.primary.role_state())
        self.assertTrue(state['images']);state['images']=[]
        # An empty cold image memo alone is not authority to omit the older
        # admitted sample's capture. The complete original history is intact.
        f.primary._image_cache={};f.primary.image_cache_digests={}
        with patch.object(f.primary,'role_state',return_value=state),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        self.assertEqual([],self.batches);self.assertTrue(f.primary.capture_retirement.failed)

    def test_ready_cas_original_age_and_actual_lock_exit_cannot_authorize_retirement(self):
        self.baseline();f=self.f;held=ScriptSourceLock.held;fired=[]
        @contextmanager
        def late(lock):
            with held(lock):yield
            owner=f.primary.capture_retirement
            if lock is f.primary.lock and owner is not None and owner.previous is not None and owner.previous['complete'] and not fired:
                fired.append(True);f.clock.base+=2000
        with patch.object(ScriptSourceLock,'held',late),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement;self.assertEqual([True],fired)
        self.assertTrue(owner.store.read()['complete']);self.assertFalse(owner.completed);self.assertTrue(owner.failed)
        with self.assertRaises(NativeUIError):owner.receipt()

    def test_same_byte_original_replacement_after_last_target_guard_keeps_ready_owner_unknown(self):
        self.baseline();f=self.f;runtime=f.primary.runtime;fired=[]
        def replaced(original):
            result=runtime(original);owner=f.primary.capture_retirement
            if owner is not None and owner.previous is not None and owner.previous['complete'] and not fired:
                fired.append(True);path=f.primary.store.path
                replacement=path.with_name('replacement-original');replacement.write_bytes(path.read_bytes())
                replacement.chmod(0o600);replacement.replace(path)
            return result
        with patch.object(f.primary,'runtime',side_effect=replaced),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement;self.assertEqual([True],fired)
        self.assertFalse(owner.completed);self.assertTrue(owner.failed);self.assertTrue(owner.store.read()['complete'])

    def test_original_replacement_during_catalogue_copy_refuses_before_any_capture_query(self):
        self.baseline();f=self.f;write=PrivateFeatureState.write;changed=[]
        def replace(store,value,previous):
            write(store,value,previous);owner=f.primary.capture_retirement
            if owner is not None and store.path==owner.store.path and value['phase']=='admitting' and value['chunks'] and not changed:
                path=next(iter(owner.catalog.rows.values()))['store'].path
                temporary=path.with_name('replaced-original-during-copy')
                temporary.write_bytes(path.read_bytes());temporary.chmod(0o600);temporary.replace(path);changed.append(True)
        with patch.object(PrivateFeatureState,'write',replace),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement
        self.assertEqual([True],changed);self.assertTrue(owner.failed);self.assertFalse(owner.completed)
        self.assertEqual([],self.batches);self.assertIsNone(owner.reader)
        self.assertFalse(owner.copying_catalog);self.assertEqual('admitting',owner.store.read()['phase'])
        self.assertTrue(all(row['store'].path.exists() for row in owner.catalog.rows.values()))

    def test_validly_repacked_copied_catalogue_with_changed_original_hash_never_becomes_ready(self):
        from adapters.script_journey.history import pack,unpack
        self.baseline();f=self.f;write=PrivateFeatureState.write;changed=[]
        def replace(store,value,previous):
            owner=f.primary.capture_retirement
            if owner is not None and store.path.name.startswith(owner.store.path.name+'.frame-') and not changed:
                rows=unpack(value['transcript']);self.assertEqual('source-catalog',rows[0]['kind'])
                original=value['transcript']['bytes'];rows[0]['sources'][0]['sha256']='0'*64
                value['transcript']=pack(rows);self.assertEqual(original,value['transcript']['bytes']);changed.append(True)
            write(store,value,previous)
        with patch.object(PrivateFeatureState,'write',replace),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement
        self.assertEqual([True],changed);self.assertTrue(owner.failed);self.assertFalse(owner.completed)
        self.assertEqual([],self.batches);self.assertIsNone(owner.reader);self.assertFalse(owner.copying_catalog)
        self.assertEqual('admitting',owner.store.read()['phase'])
        self.assertTrue(all(row['store'].path.exists() for row in owner.catalog.rows.values()))
        with self.assertRaises(NativeUIError):owner.receipt()

    def test_landed_query_intent_original_replacement_refuses_before_native_send(self):
        self.baseline();f=self.f;write=PrivateFeatureState.write;changed=[]
        def replace(store,value,previous):
            write(store,value,previous);owner=f.primary.capture_retirement
            if owner is not None and store.path==owner.store.path and value.get('pending') is not None and not changed:
                path=next(iter(owner.catalog.rows.values()))['store'].path
                temporary=path.with_name('query-intent-replacement')
                temporary.write_bytes(path.read_bytes());temporary.chmod(0o600);temporary.replace(path);changed.append(True)
        with patch.object(PrivateFeatureState,'write',replace),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement
        self.assertEqual([True],changed);self.assertEqual([],self.batches)
        self.assertTrue(owner.failed);self.assertFalse(owner.completed)
        self.assertIsNotNone(owner.store.read()['pending'])
        self.assertTrue(all(row['store'].path.exists() for row in owner.catalog.rows.values()))

    def test_native_answer_with_changed_original_png_cannot_publish_ready(self):
        self.baseline();f=self.f;changed=[]
        def corrupt(_packet):
            if changed:return
            owner=f.primary.capture_retirement;path=f.artifacts/owner.pngs[0]['value']['name']
            raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]));changed.append(True)
        self.mutate=corrupt
        with self.assertRaises(NativeUIError):f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement
        self.assertEqual([True],changed);self.assertEqual(1,len(self.batches))
        self.assertEqual((),owner.frames);self.assertTrue(owner.failed);self.assertFalse(owner.completed)
        self.assertEqual('reading',owner.store.read()['phase']);self.assertIsNotNone(owner.store.read()['pending'])

    def test_landed_ready_cas_cannot_alias_original_json_list_with_tuple(self):
        self.baseline();f=self.f;write=PrivateFeatureState.write;changed=[]
        def alias(store,value,previous):
            write(store,value,previous);owner=f.primary.capture_retirement
            if owner is None or owner.reader is None or store.path!=owner.store.path or value['phase']!='ready' or changed:return
            for row in owner.catalog.rows.values():
                expected=row['expected']
                for name,item in expected.items():
                    if type(item) is list:
                        expected[name]=tuple(item);changed.append(True);return
            self.fail('The original consumed source graph has no JSON list')
        with patch.object(PrivateFeatureState,'write',alias),self.assertRaises(NativeUIError):
            f.primary.retire_original_captures(f.actor)
        owner=f.primary.capture_retirement
        self.assertEqual([True],changed);self.assertEqual(1,len(self.batches))
        self.assertTrue(owner.failed);self.assertFalse(owner.completed)
        self.assertTrue(all(row['store'].path.exists() for row in owner.catalog.rows.values()))
