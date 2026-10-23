"""A real unconsumed cleanup slot rebuilds quiet with new locked histories.

The existing component fixture supplies explicit native/SDK host producers.
Source locks, immutable files, separate Actor, HTTP receipts and quiet time are
actual. These counters qualify neither an Android APK nor physical devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import multiprocessing
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_actor as component
import test_snapshots_actor_maintenance as maintenance
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_actor import PhoneSnapshotsActor
from overte_phone_snapshots_actor_history import SnapshotActorHistoryPass
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_role import PhoneSnapshotsRole


class SnapshotLockedSlotRebuildTests(unittest.TestCase):
    controlled=maintenance.SnapshotActorMaintenanceTests.controlled
    published=maintenance.SnapshotActorMaintenanceTests.published
    waiting=maintenance.SnapshotActorMaintenanceTests.waiting

    @contextmanager
    def rebuilding(self,kind='positive'):
        active=multiprocessing.get_context('fork').Value('i',0)
        reports=multiprocessing.get_context('fork').Queue()
        trace=dict(on=False,reading=None,passes=[],ready=None,owner=None,
            currentReads=0,lockedReads=0,mutations=0,nativeDuringReplay=0)
        read=SnapshotActorHistoryPass.read;finish=SnapshotActorHistoryPass.finish
        current=PhoneSnapshotsRole.read;actual_file=SnapshotsOriginals.file
        step=PhoneSnapshotsActor.step;batch=PhoneSnapshotsActor.quiet_batch

        def replay(token):
            if not trace['on']:return read(token)
            info=dict(token=token,locked=token.locked_replay,files=set(),
                oldFrames=len(token.role.frames),complete=False,finished=False,used=False)
            self.assertNotIn(id(token),[id(row['token']) for row in trace['passes']])
            trace['passes'].append(info)
            if token.locked_replay:
                trace['lockedReads']+=1
                token.feature.lock.assert_held()
                self.assertIs(token.feature.lock._owner,token.replay_lock_owner)
            else:self.assertIsNone(token.feature.lock._owner)
            trace['reading']=info
            def forbidden(*_args,**_kwargs):
                trace['nativeDuringReplay']+=1
                raise AssertionError('Historical file replay requested current target authority')
            try:
                with patch.object(token.feature,'bound',forbidden),patch.object(token.feature.phase,'status',forbidden):
                    result=read(token)
                info['complete']=True
                self.assertEqual(info['oldFrames'],len(info['files']))
                self.assertTrue(token.file_seal)
                return result
            finally:trace['reading']=None

        def qualified(token):
            result=finish(token)
            if trace['on']:
                info=next(row for row in trace['passes'] if row['token'] is token)
                self.assertTrue(info['complete']);info['finished']=True;trace['ready']=info
            return result

        def acquire(role,*args,**kwargs):
            if trace['on'] and role.role=='actor':
                self.assertIsNone(trace['reading'])
                info=trace['ready'];self.assertIsNotNone(info)
                self.assertTrue(info['complete'] and info['finished']);self.assertFalse(info['used'])
                role.feature.lock.assert_held()
                if trace['owner'] is None:trace['owner']=role.feature.lock._owner
                self.assertIs(trace['owner'],role.feature.lock._owner)
                if info['locked']:self.assertIs(trace['owner'],info['token'].replay_lock_owner)
                info['used']=True;trace['currentReads']+=1
            return current(role,*args,**kwargs)

        def file_read(engine,path,descriptor,value):
            result=actual_file(engine,path,descriptor,value)
            info=trace['reading']
            if info is not None:
                self.assertEqual(path.stat().st_ino,os.fstat(descriptor).st_ino)
                if path.name.startswith('emote-frame-snapshots-'):info['files'].add(str(path))
                if (info['locked'] and trace['lockedReads']==2 and kind not in ('positive','late-feature-aba')
                        and not trace['mutations'] and path.name.startswith('emote-frame-snapshots-')):
                    token=info['token'];f=token.feature;f.lock.assert_held()
                    self.assertIs(trace['owner'],f.lock._owner)
                    trace['readsAtMutation']=trace['currentReads']
                    if kind=='owner':
                        previous=f.store.read();state=unpack(previous['payload'])[0]
                        state['cleanupStages']['foreignLockedReplay']=True
                        f.store.write(dict(previous,payload=pack([state])),previous)
                    elif kind=='file':path.write_bytes(path.read_bytes()+b' ')
                    elif kind=='graph':token.role.frames[0]['foreignLockedReplay']=True
                    elif kind=='native-guard':f.guard=lambda:False
                    else:raise AssertionError('Unknown locked-replay mutation')
                    trace['mutations']+=1
            return result

        def bounded(actor,role,prepared,started,**kwargs):
            if trace['on']:trace['batchStarted']=started
            return batch(actor,role,prepared,started,**kwargs)

        def owned_step(actor):
            if not active.value:return step(actor)
            trace.update(on=True,reading=None,passes=[],ready=None,owner=None,
                currentReads=0,lockedReads=0,mutations=0,nativeDuringReplay=0)
            restored=actor.feature.restored
            def after_restored(*args,**kwargs):
                result=restored(*args,**kwargs)
                if kind=='late-feature-aba' and trace['currentReads']==2 and not trace['mutations']:
                    f=actor.feature;f.lock.assert_held();store=f.store
                    raw=store.path.read_bytes();before=store.path.stat();previous=store.read()
                    trace['actorHeaderAtMutationSha256']=hashlib.sha256(actor.store.path.read_bytes()).hexdigest()
                    trace['readsAtMutation']=trace['currentReads']
                    store.write(previous,previous);after=store.path.stat()
                    self.assertEqual(raw,store.path.read_bytes())
                    self.assertNotEqual((before.st_dev,before.st_ino),(after.st_dev,after.st_ino))
                    trace['mutations']+=1
                return result
            try:
                with patch.object(actor.feature,'restored',after_restored):return step(actor)
            finally:
                used=trace['passes']
                packet=dict(currentReads=trace['currentReads'],lockedReads=trace['lockedReads'],
                    mutations=trace['mutations'],readsAtMutation=trace.get('readsAtMutation'),
                    nativeDuringReplay=trace['nativeDuringReplay'],batchStarted=trace.get('batchStarted'),
                    actorHeaderAtMutationSha256=trace.get('actorHeaderAtMutationSha256'),
                    passes=[dict(identity=id(row['token']),locked=row['locked'],oldFrames=row['oldFrames'],
                        actualOldFrameFiles=len(row['files']),complete=row['complete'],finished=row['finished'],
                        used=row['used'],closed=row['token'].closed) for row in used])
                trace['on']=False;reports.put(packet)

        try:
            with patch.object(SnapshotActorHistoryPass,'read',replay),\
                    patch.object(SnapshotActorHistoryPass,'finish',qualified),\
                    patch.object(PhoneSnapshotsRole,'read',acquire),\
                    patch.object(SnapshotsOriginals,'file',file_read),\
                    patch.object(PhoneSnapshotsActor,'quiet_batch',bounded),\
                    patch.object(PhoneSnapshotsActor,'step',owned_step):
                with self.controlled() as (fixture,advance,_shared):
                    first=self.published(fixture,advance)
                    fixture.advance_cleanup_primary()
                    header,_slot=fixture.append_cleanup_slot()
                    before=deepcopy(fixture.reader.request('/runs/'+component.RUN)['entries'])
                    time.sleep(1.6)  # Real elapsed gap; no clock or quiet-rule replacement.
                    active.value=1
                    value=advance();report=reports.get(timeout=3)
                    self.assertTrue(report['passes'])
                    self.assertTrue(all(row['closed'] for row in report['passes']),report)
                    self.assertEqual(0,report['nativeDuringReplay'])
                    self.assertEqual(len(report['passes']),len({row['identity'] for row in report['passes']}))
                    yield fixture,first,header,before,value,report
        finally:reports.close();reports.join_thread()

    def test_real_gap_rebuilds_new_slot_with_full_new_histories_and_one_fresh_post(self):
        with self.rebuilding() as (fixture,first,header,before,value,report):
            self.assertIsNone(value['error'],value)
            points=value['points'];self.assertGreaterEqual(len(points),3)
            self.assertGreater(points[0]['last']-points[0]['previousLast'],1.5)
            self.assertEqual(points[0]['started'],points[0]['last']);self.assertFalse(points[0]['complete'])
            quiet=value['state']['quiet'];self.assertTrue(quiet['complete'])
            self.assertGreaterEqual(quiet['last']-quiet['started'],3)
            self.assertGreaterEqual(len(quiet['sequences']),3)
            self.assertLess(quiet['last']-report['batchStarted'],4.0)
            self.assertEqual(len(points),report['currentReads'])
            self.assertEqual(report['currentReads'],len(report['passes']))
            self.assertEqual(report['currentReads']-1,report['lockedReads'])
            self.assertTrue(all(row['complete'] and row['finished'] and row['used'] for row in report['passes']))
            self.assertEqual(first['counts']['reads']+report['currentReads'],value['counts']['reads'])
            self.assertEqual(first['counts']['posts']+1,value['counts']['posts'])
            self.assertEqual(header,value['state']['primaryCue']['header'])
            sample=value['state']['last']['original']['sample']
            self.assertEqual(quiet['sequences'][-1],sample['actorSequence'])
            entries=fixture.reader.request('/runs/'+component.RUN)['entries']
            self.assertEqual(before,entries[:-1]);self.assertEqual(len(before)+1,len(entries))
            self.assertEqual(sample['actorSequence'],entries[-1]['actorSequence'])
            self.assertIsNone(value['state']['pending'])

    def test_no_slot_reading_diagnostic_and_normal_successors_wait_without_acquisition(self):
        # Delegate the original real-fixture cases rather than clone them.
        maintenance.SnapshotActorMaintenanceTests.test_consumed_slot_and_normal_successor_wait_until_new_typed_slot(self)
        maintenance.SnapshotActorMaintenanceTests.test_reading_diagnostic_and_normal_primary_successors_authorize_no_acquisition(self)

    def test_second_locked_replay_rejects_actual_owner_file_graph_and_guard_mutations(self):
        for kind in ('owner','file','graph','native-guard','late-feature-aba'):
            with self.subTest(kind=kind),self.rebuilding(kind) as (fixture,first,_header,before,value,report):
                self.assertEqual('NativeUIError',value['error']['error'],value)
                self.assertEqual(1,report['mutations'])
                self.assertEqual(1 if kind=='late-feature-aba' else 2,report['lockedReads'])
                self.assertEqual(report['readsAtMutation'],report['currentReads'])
                self.assertGreaterEqual(report['currentReads'],2)
                if kind=='late-feature-aba':
                    self.assertTrue(report['passes'][-1]['complete'])
                    journal=fixture.boundary.feature.store.path.with_name('phone-snapshots-actor-lifecycle.json')
                    self.assertEqual(report['actorHeaderAtMutationSha256'],hashlib.sha256(journal.read_bytes()).hexdigest())
                else:self.assertFalse(report['passes'][-1]['complete'])
                self.assertFalse(value['state']['quiet']['complete'])
                self.assertEqual(first['counts']['posts'],value['counts']['posts'])
                self.assertEqual(first['state']['last'],value['state']['last'])
                self.assertIsNone(value['state']['pending'])
                self.assertEqual(before,fixture.reader.request('/runs/'+component.RUN)['entries'])


if __name__=='__main__':unittest.main()
