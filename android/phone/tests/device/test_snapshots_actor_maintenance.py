"""Unpublished cleanup observations keep genuine quiet progress between slots.

SDK/native/render signals are explicit host producers. HTTP journals, private
originals, separate processes, quiet timing and public finalization are actual;
these counters do not establish physical-device or APK acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import inspect
import json
import multiprocessing
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_actor as component
import test_snapshots_read_ready_slot as slot
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_retirement import NAMES,terminated
from overte_phone_snapshots_role import PhoneSnapshotsRole


class SnapshotActorMaintenanceTests(unittest.TestCase):
    # Import support as modules and delegate helpers, avoiding discovery of
    # either the original42 component tests or the six public slot tests.
    setUpClass=classmethod(slot.SnapshotReadReadySlotTests.setUpClass.__func__)
    tearDownClass=classmethod(slot.SnapshotReadReadySlotTests.tearDownClass.__func__)
    receive=slot.SnapshotReadReadySlotTests.receive
    step=slot.SnapshotReadReadySlotTests.step
    launch=slot.SnapshotReadReadySlotTests.launch
    good=slot.SnapshotReadReadySlotTests.good
    cleaned=slot.SnapshotReadReadySlotTests.cleaned

    @contextmanager
    def controlled(self,*,source_failure=False):
        fixture=component.SnapshotsActorTests('test_cleanup_frontier_publishes_once_then_requires_new_own_read')
        fixture.setUp();process=None
        shared=multiprocessing.get_context('fork').Array('i',[0,0])
        if source_failure:
            original=fixture.boundary.native_source.mutate
            def native(value):
                original(value)
                with shared.get_lock():
                    if shared[0]:value['processId']=999;shared[1]+=1
            fixture.boundary.native_source.mutate=native
        try:
            step=fixture.cleanup_frontier(slot_mode=True)
            # This is the existing fixture's real provisioning handle, used
            # only to verify owned cleanup, never as a target observation.
            process=inspect.getclosurevars(step).nonlocals['process']
            self.assertEqual(fixture.slot_process['pid'],process.pid)
            yield fixture,step,shared
        finally:
            self.assertTrue(fixture.doCleanups(),'Owned component fixture cleanup failed')
            if process is not None:self.assertEqual(0,process.exitcode,'Independent component Actor did not exit normally')

    def published(self,fixture,step):
        fixture.enroll_complete_without_post(step)
        header,_frame=fixture.append_cleanup_slot()
        value=fixture.completed_frontier(step)
        self.assertEqual(header,value['state']['primaryCue']['header'])
        return value

    def unpublished(self,fixture,before,after):
        self.assertIsNone(after['error'],after)
        self.assertEqual(before['counts']['reads']+1,after['counts']['reads'])
        self.assertEqual(before['counts']['posts'],after['counts']['posts'])
        self.assertEqual(before['state']['last'],after['state']['last'])
        self.assertEqual(before['state']['primaryCue'],after['state']['primaryCue'])
        self.assertIsNone(after['state']['pending'])
        self.assertEqual(1,len(after['points']))
        previous=unpack(before['roleHeader']['payload'])[0]
        current=unpack(after['roleHeader']['payload'])[0]
        self.assertEqual(previous['sequence']+1,current['sequence'])
        self.assertEqual(current['sequence'],after['state']['quiet']['sequences'][-1])
        self.assertEqual(1,len(fixture.reader.request('/runs/'+component.RUN)['entries']))

    def test_consumed_slot_waits_then_actual_primary_advance_maintains_without_post_and_new_slot_reads_again(self):
        with self.controlled() as (fixture,step,_shared):
            first=self.published(fixture,step)
            held=step();self.assertIsNone(held['error'],held)
            fixture.assert_no_further_acquisition(first,held)
            fixture.advance_cleanup_primary()
            maintained=step();self.unpublished(fixture,held,maintained)
            header,_frame=fixture.append_cleanup_slot()
            posted=step();self.assertIsNone(posted['error'],posted)
            self.assertGreater(posted['counts']['reads'],maintained['counts']['reads'])
            self.assertEqual(maintained['counts']['posts']+1,posted['counts']['posts'])
            self.assertEqual(header,posted['state']['primaryCue']['header'])
            self.assertEqual(posted['state']['quiet']['sequences'][-1],posted['state']['last']['original']['sample']['actorSequence'])
            self.assertEqual(2,len(fixture.reader.request('/runs/'+component.RUN)['entries']))

    def test_real_gap_resets_maintenance_and_each_unpublished_sample_yields_until_real_quiet_rebuilds(self):
        with self.controlled() as (fixture,step,_shared):
            first=self.published(fixture,step);fixture.advance_cleanup_primary()
            time.sleep(1.6)
            previous=step();self.unpublished(fixture,first,previous)
            point=previous['points'][0]
            self.assertGreater(point['last']-point['previousLast'],1.5)
            self.assertEqual(point['last'],point['started']);self.assertFalse(point['complete'])
            self.assertFalse(previous['state']['quiet']['complete'])
            started=time.monotonic()
            while not previous['state']['quiet']['complete']:
                self.assertLess(time.monotonic()-started,15,'Real unpublished quiet interval failed to complete')
                time.sleep(.15)
                current=step();self.unpublished(fixture,previous,current);previous=current
            quiet=previous['state']['quiet']
            self.assertGreaterEqual(quiet['last']-quiet['started'],3)
            self.assertGreaterEqual(len(quiet['sequences']),3)
            self.assertGreater(quiet['started'],first['state']['quiet']['last'])

    def test_changed_owner_late_original_and_actual_native_failure_never_publish_maintenance(self):
        for kind in ('owner','old-original','native-source'):
            with self.subTest(kind=kind),self.controlled(source_failure=kind=='native-source') as (fixture,step,shared):
                first=self.published(fixture,step);fixture.advance_cleanup_primary()
                entries=deepcopy(fixture.reader.request('/runs/'+component.RUN)['entries'])
                modified=None;changed=None
                if kind=='owner':
                    store=fixture.boundary.feature.store;before=store.read();state=unpack(before['payload'])[0]
                    state['cleanupStages']['foreignMaintenanceOwner']=True
                    changed=dict(before,payload=pack([state]));store.write(changed,before)
                elif kind=='old-original':
                    f=fixture.boundary.feature
                    with f.lock.held():
                        def guard():f.lock.assert_held();return True
                        host=SnapshotsOriginals(f.root,f.binding,f.run,'actor',guard,lambda *_:self.fail('Read-only original audit wrote an intent'),kind='snapshots')
                        state=unpack(first['roleHeader']['payload'])[0]
                        reference=host.expand(host.manifest(state['manifests'][0])[0]);host.read(reference)
                        path=host.path(reference);raw=path.read_bytes()+b' '
                        path.write_bytes(raw);modified=(path,raw)
                else:
                    with shared.get_lock():shared[0]=1
                refused=step();self.assertEqual('NativeUIError',refused['error']['error'],refused)
                self.assertEqual(first['counts']['posts'],refused['counts']['posts'])
                self.assertEqual(first['state']['last'],refused['state']['last'])
                self.assertEqual(entries,fixture.reader.request('/runs/'+component.RUN)['entries'])
                if changed is not None:self.assertEqual(changed,fixture.boundary.feature.store.read())
                if modified is not None:self.assertEqual(modified[1],modified[0].read_bytes())
                if kind=='native-source':
                    with shared.get_lock():self.assertGreater(shared[1],0)
                    self.assertGreater(refused['counts']['reads'],first['counts']['reads'])

    def test_reading_or_diagnostic_primary_successor_does_not_authorize_maintenance(self):
        for kind in ('reading','diagnostic'):
            with self.subTest(kind=kind),self.controlled() as (fixture,step,_shared):
                first=self.published(fixture,step)
                if kind=='diagnostic':fixture.append_cleanup_slot(diagnostic_only=True)
                else:
                    f=fixture.boundary.feature
                    with f.lock.held():
                        role=PhoneSnapshotsRole(f,'primary')
                        role.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work={}))
                        role.save()
                held=step();self.assertIsNone(held['error'],held)
                fixture.assert_no_further_acquisition(first,held)
                self.assertEqual(first['state']['last'],held['state']['last'])
                self.assertEqual(1,len(fixture.reader.request('/runs/'+component.RUN)['entries']))

    def test_public_maintenance_keeps_original_receipt_and_real_close_exit_and_double_finalization(self):
        with self.cleaned() as rig:
            first=self.launch(rig);self.good(rig,first)
            accepted=deepcopy(rig.client.request('/runs/'+slot.harness.RUN)['entries'])
            original=deepcopy(unpack(rig.slot_actor_store.read()['payload'])[0]['last'])
            maintained=self.step(rig);self.assertEqual(original,maintained['state']['last'])
            self.assertGreater(maintained['counts']['reads'],first['child']['counts']['reads'])
            self.assertEqual(first['child']['counts']['posts'],maintained['counts']['posts'])
            started=time.monotonic()
            while not maintained['state']['quiet']['complete']:
                self.assertLess(time.monotonic()-started,20,'Public maintenance did not rebuild actual quiet')
                time.sleep(.05);maintained=self.step(rig)
            self.assertEqual(accepted,rig.client.request('/runs/'+slot.harness.RUN)['entries'])
            rig.client.close();closed=self.step(rig)
            if closed['state']['phase']=='watching':
                # A retained history turn may observe actual closure and
                # defer to the next cold, fresh closed-phase acquisition.
                self.assertEqual(maintained['counts'],closed['counts'])
                self.assertEqual(maintained['state']['last'],closed['state']['last'])
                self.assertTrue(closed['state']['quiet']['complete'])
                self.assertIsNone(closed['state']['closure'])
                self.assertIsNone(closed['state']['pending'])
                closed=self.step(rig)
            self.assertEqual('retired',closed['state']['phase'])
            self.assertFalse(closed['state']['closure']['active'])
            self.assertEqual(maintained['counts']['posts'],closed['counts']['posts'])
            self.assertFalse(terminated(closed['state']['process']))
            rig.slot_child.stdin.write(json.dumps(dict(mode='exit'))+'\n');rig.slot_child.stdin.flush()
            rig.slot_child.wait(timeout=5);self.assertEqual(0,rig.slot_child.returncode)
            self.assertTrue(terminated(closed['state']['process']))
            value=dict(contractVersion=slot.harness.VERSION,runId=slot.harness.RUN)
            self.assertTrue(rig.invoke('feature.snapshots.cleanup',value)['performed'])
            self.assertTrue(all(PrivateFeatureState(rig.root/name).read() is None for name in NAMES))
            archives=list(rig.root.glob('emote-frame-snapshots-retirement-*.json'));self.assertEqual(1,len(archives))
            before=(archives[0].stat().st_ino,archives[0].read_bytes())
            self.assertTrue(rig.invoke('feature.snapshots.cleanup',value)['performed'])
            self.assertEqual(before,(archives[0].stat().st_ino,archives[0].read_bytes()))


if __name__=='__main__':unittest.main()
