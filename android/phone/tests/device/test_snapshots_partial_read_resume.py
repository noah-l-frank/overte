"""Partial actual Snapshot reads retain original floors across cold recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import multiprocessing
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_actor as base
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from overte_phone_script_history import unpack,same
import overte_phone_snapshots_actor as source
import test_snapshots_role as roles


def partial_child(boundary,url,queue,command):
    try:
        f=boundary.feature;f.role='actor';f.load=lambda:setattr(f,'previous',f.store.read())
        phase=PhaseFixtureReader(Client(url,'a'*64),base.RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
        f.phase.client=phase.client;f.phase.status=phase.status
        f.phase.provider=lambda:dict(boundary.provider,active=phase.status()['active'])
        f.monotonic,f.sleep=time.monotonic,time.sleep
        constructed=[];original=source.PhoneSnapshotsRole;injected=[False];floors=[]
        def construct(*args,**kwargs):
            role=original(*args,**kwargs);constructed.append(role)
            if role.frames and role.frames[-1].get('diagnostic'):
                partial=role.frames[-1]
                floors.append(dict(native=role.native.sequence,expectedNative=partial['nativeBefore']['sequence'],
                    avatar=role.avatar.last['sequence'],expectedAvatar=partial['avatarBefore']['sequence']))
            batch=role.batch
            def actual_then_pending():
                value=batch()
                if not injected[0]:
                    injected[0]=True;raise source.SnapshotPending()
                return value
            role.batch=actual_then_pending;return role
        with patch.object(source,'PhoneSnapshotsRole',construct):
            actor=source.PhoneSnapshotsActor(f);result=actor.step();role=constructed[-1]
            assert not result and role.state['phase']=='ready' and role.state['pending'] is None
            partial=deepcopy(role.frames[-1]);assert partial['diagnostic'] and partial['groups']
            assert 'nativeBefore' in partial and 'avatarBefore' in partial and 'nativeAfter' not in partial and 'avatarAfter' not in partial
            assert actor._cleanup_reader is None and actor._cleanup_anchor is not None
            assert same(actor._cleanup_anchor[1]['role'],role.previous)
            queue.put(dict(partial=True,sequence=role.state['sequence'],native=partial['nativeBefore']['sequence'],
                avatar=partial['avatarBefore']['sequence'],groups=len(partial['groups']),header=role.previous))
            assert command.recv()=='resume'
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                actor.step()
                if actor.state['quiet'] is not None and actor.state['quiet']['complete']:break
                time.sleep(.25)
            assert actor.state['quiet']['complete']
            assert same(constructed[-1].frames[0],partial)
            queue.put(dict(resumed=True,constructors=len(constructed),floors=floors,
                diagnosticPreserved=True,quiet=deepcopy(actor.state['quiet'])))
            assert command.recv()=='closed';finished=actor.step()
            queue.put(dict(finished=finished,phase=actor.state['phase']))
    except Exception as error:queue.put(dict(error=type(error).__name__,message=str(error)))


class SnapshotPartialReadResumeTests(unittest.TestCase):
    def partial(self,native_edit=lambda _:None,*,empty_after=None):
        import tempfile
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-actual-partial-');self.addCleanup(temporary.cleanup)
        b=roles.SnapshotRolesBoundary(temporary.name);b.clean();original=b.native_source.mutate
        def changed(value):original(value);native_edit(value)
        b.native_source.mutate=changed
        with b.role() as role:
            batch=role.batch
            def actual_then_pending():
                batch()
                if empty_after is not None:role.checkpoint(**{empty_after:{}})
                raise source.SnapshotPending()
            role.batch=actual_then_pending
            with self.assertRaises(source.SnapshotPending):role.read(0)
            frame=deepcopy(role.frames[-1]);header=deepcopy(role.previous)
            self.assertEqual('ready',role.state['phase']);self.assertIsNone(role.state['pending'])
            self.assertTrue(frame['diagnostic']);self.assertTrue(frame['groups'])
            for key in ('nativeAfter','avatarAfter'):
                if key==empty_after:self.assertEqual({},frame[key])
                else:self.assertNotIn(key,frame)
        b.native_source.mutate=original
        return b,frame,header

    def test_partial_raw_groups_and_before_floors_survive_actual_cold_constructor(self):
        b,partial,header=self.partial()
        with b.role() as role:
            self.assertTrue(same(header,role.previous));self.assertTrue(same(partial,role.frames[-1]))
            self.assertEqual(partial['nativeBefore']['sequence'],role.native.sequence)
            self.assertTrue(same(partial['nativeBefore']['lifecycle'],role.native.lifecycle))
            self.assertTrue(same(partial['avatarBefore'],role.avatar.last))
            self.assertTrue(same(partial['groups'][-1]['rootsAfter'],role.measurements.roots.last))
            self.assertTrue(same(partial['groups'][-1]['snapshot'],role.measurements.snapshot.last))

    def test_fresh_replayed_native_sequence_cannot_pass_partial_before_floor(self):
        b,partial,_=self.partial();original=b.native_source.mutate
        def replayed(value):original(value);value['sequence']=partial['nativeBefore']['sequence']
        b.native_source.mutate=replayed
        with b.role() as role,self.assertRaises(NativeUIError):role.native.read(role.native.sequence,require_account=True)

    def test_fresh_lifecycle_regression_cannot_pass_partial_before_floor(self):
        b,partial,_=self.partial(lambda value:value['lifecycle'].update(backgrounds=2,activations=3))
        self.assertEqual(2,partial['nativeBefore']['lifecycle']['backgrounds'])
        with b.role() as role,self.assertRaises(NativeUIError):role.native.read(role.native.sequence,require_account=True)

    def test_fresh_account_generation_regression_cannot_pass_partial_before_floor(self):
        b,partial,_=self.partial(lambda value:value['account']['observation'].update(credentialGeneration=2))
        self.assertEqual(2,partial['nativeBefore']['account']['observation']['credentialGeneration'])
        with b.role() as role,self.assertRaises(NativeUIError):role.native.read(role.native.sequence,require_account=True)

    def test_fresh_replayed_avatar_sequence_cannot_pass_partial_before_floor(self):
        b,partial,_=self.partial()
        b.avatar_source.edit=lambda value:value.update(sequence=partial['avatarBefore']['sequence'])
        with b.role() as role,self.assertRaises(NativeUIError):role.avatar.read()

    def test_present_invalid_native_after_in_actual_immutable_diagnostic_cannot_fall_back(self):
        b,partial,_=self.partial(empty_after='nativeAfter')
        self.assertTrue(partial['nativeBefore']);self.assertEqual({},partial['nativeAfter'])
        with self.assertRaises(NativeUIError),b.role():pass

    def test_present_invalid_avatar_after_in_actual_immutable_diagnostic_cannot_fall_back(self):
        b,partial,_=self.partial(empty_after='avatarAfter')
        self.assertTrue(partial['avatarBefore']);self.assertEqual({},partial['avatarAfter'])
        with self.assertRaises(NativeUIError),b.role():pass

    def test_actual_batch_pending_archives_raw_prefix_then_cold_actor_resume_and_close(self):
        rig=base.SnapshotsActorTests('test_own_original_quiet_and_actual_closed_phase_precede_actor_retirement')
        rig.setUp();self.addCleanup(rig.doCleanups);b=rig.boundary;b.clean()
        rig.reader.activate('d'*32,'cleanup',{});b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=base.TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        rig.server.shutdown();rig.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=partial_child,args=(b,rig.url,queue,receive));process.start()
        rig.thread=threading.Thread(target=rig.server.serve_forever,daemon=True);rig.thread.start()
        try:
            partial=queue.get(timeout=15);self.assertTrue(partial.get('partial'),partial)
            self.assertFalse(rig.reader.request('/runs/'+base.RUN)['entries'])
            send.send('resume');resumed=queue.get(timeout=20);self.assertTrue(resumed.get('resumed'),resumed)
            self.assertEqual(2,resumed['constructors']);self.assertTrue(resumed['diagnosticPreserved'])
            self.assertTrue(resumed['floors'])
            for floor in resumed['floors']:
                self.assertEqual(floor['expectedNative'],floor['native'])
                self.assertEqual(floor['expectedAvatar'],floor['avatar'])
            rig.reader.close();send.send('closed');final=queue.get(timeout=15)
            self.assertEqual(dict(finished=True,phase='retired'),final)
            process.join(3);self.assertEqual(0,process.exitcode)
        finally:
            if process.is_alive():process.terminate();process.join(3)


if __name__=='__main__':unittest.main()
