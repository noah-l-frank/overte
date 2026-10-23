"""Consumed cleanup slots hold without unsolicited Actor acquisitions.

SDK/native/render signals are explicit host producers. HTTP journals, private
originals, separate processes, quiet timing and public finalization are actual;
new typed slots require fresh reads and real gap resets. These counters do not
establish physical-device or APK acceptance.
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

    def waiting(self,fixture,before,after):
        self.assertIsNone(after['error'],after)
        fixture.assert_no_further_acquisition(before,after)
        self.assertEqual(before['actorHeader'],after['actorHeader'])
        self.assertEqual(before['state'],after['state'])
        self.assertIsNone(after['state']['pending'])
        self.assertEqual([],after['points'])
        self.assertEqual(1,len(fixture.reader.request('/runs/'+component.RUN)['entries']))

    def test_consumed_slot_and_normal_successor_wait_until_new_typed_slot(self):
        with self.controlled() as (fixture,step,_shared):
            first=self.published(fixture,step)
            held=step();self.assertIsNone(held['error'],held)
            self.waiting(fixture,first,held)
            fixture.advance_cleanup_primary()
            normal=step();self.waiting(fixture,held,normal)
            header,_frame=fixture.append_cleanup_slot()
            posted=step();self.assertIsNone(posted['error'],posted)
            self.assertGreater(posted['counts']['reads'],normal['counts']['reads'])
            self.assertEqual(normal['counts']['posts']+1,posted['counts']['posts'])
            self.assertEqual(header,posted['state']['primaryCue']['header'])
            self.assertEqual(posted['state']['quiet']['sequences'][-1],posted['state']['last']['original']['sample']['actorSequence'])
            self.assertEqual(2,len(fixture.reader.request('/runs/'+component.RUN)['entries']))

    def test_real_gap_has_no_uncued_quiet_points_then_new_slot_rebuilds_real_quiet(self):
        with self.controlled() as (fixture,step,_shared):
            first=self.published(fixture,step);fixture.advance_cleanup_primary()
            time.sleep(1.6)
            waiting=step();self.waiting(fixture,first,waiting)
            header,_slot=fixture.append_cleanup_slot()
            posted=step();self.assertIsNone(posted['error'],posted)
            self.assertGreaterEqual(len(posted['points']),3)
            point=posted['points'][0]
            self.assertGreater(point['last']-point['previousLast'],1.5)
            self.assertEqual(point['last'],point['started']);self.assertFalse(point['complete'])
            quiet=posted['state']['quiet'];self.assertTrue(quiet['complete'])
            self.assertGreaterEqual(quiet['last']-quiet['started'],3)
            self.assertGreaterEqual(len(quiet['sequences']),3)
            self.assertGreater(quiet['started'],first['state']['quiet']['last'])
            self.assertEqual(waiting['counts']['reads']+len(posted['points']),posted['counts']['reads'])
            self.assertEqual(waiting['counts']['posts']+1,posted['counts']['posts'])
            self.assertEqual(header,posted['state']['primaryCue']['header'])
            self.assertEqual(quiet['sequences'][-1],posted['state']['last']['original']['sample']['actorSequence'])
            self.assertEqual(2,len(fixture.reader.request('/runs/'+component.RUN)['entries']))

    def test_wait_still_rejects_owner_or_file_changes_and_new_slot_rejects_native_failure(self):
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
                    # A normal successor grants no acquisition. Place a real
                    # new slot before exposing the failing current source.
                    fixture.append_cleanup_slot()
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
                else:
                    self.assertEqual(first['counts']['reads'],refused['counts']['reads'])
                    self.assertEqual(first['roleHeader'],refused['roleHeader'])
                    self.assertEqual(first['actorHeader'],refused['actorHeader'])
                    self.assertEqual([],refused['points'])

    def test_reading_diagnostic_and_normal_primary_successors_authorize_no_acquisition(self):
        for kind in ('reading','diagnostic','normal'):
            with self.subTest(kind=kind),self.controlled() as (fixture,step,_shared):
                first=self.published(fixture,step)
                if kind=='diagnostic':fixture.append_cleanup_slot(diagnostic_only=True)
                elif kind=='normal':fixture.advance_cleanup_primary()
                else:
                    f=fixture.boundary.feature
                    with f.lock.held():
                        role=PhoneSnapshotsRole(f,'primary')
                        role.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work={}))
                        role.save()
                held=step();self.assertIsNone(held['error'],held)
                self.waiting(fixture,first,held)

    def test_public_wait_preserves_receipt_then_fresh_close_exit_and_double_finalization(self):
        with self.cleaned() as rig:
            first=self.launch(rig);self.good(rig,first)
            accepted=deepcopy(rig.client.request('/runs/'+slot.harness.RUN)['entries'])
            original_header=deepcopy(rig.slot_actor_store.read())
            original=deepcopy(unpack(original_header['payload'])[0])
            waiting=self.step(rig);self.assertEqual(original,waiting['state'])
            self.assertEqual(first['child']['counts'],waiting['counts'])
            self.assertEqual(original_header,rig.slot_actor_store.read())
            self.assertEqual(accepted,rig.client.request('/runs/'+slot.harness.RUN)['entries'])
            rig.client.close();closed=self.step(rig)
            if closed['state']['phase']=='watching':
                # A retained history turn may observe actual closure and
                # defer to the next cold, fresh closed-phase acquisition.
                self.assertEqual(waiting['counts'],closed['counts'])
                self.assertEqual(waiting['state']['last'],closed['state']['last'])
                self.assertTrue(closed['state']['quiet']['complete'])
                self.assertIsNone(closed['state']['closure'])
                self.assertIsNone(closed['state']['pending'])
                closed=self.step(rig)
            self.assertEqual('retired',closed['state']['phase'])
            self.assertFalse(closed['state']['closure']['active'])
            self.assertEqual(waiting['counts']['posts'],closed['counts']['posts'])
            self.assertEqual(waiting['counts']['reads']+1,closed['counts']['reads'])
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
