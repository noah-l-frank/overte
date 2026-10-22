"""Independent v1 archive bytes and bounded temporal scene replay negatives."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_final_archive import IOSEmoteFinalArchive
from ios.adapters.emote_scene_history import before
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase
from ios.self_tests import test_ios_emote_scene_gate as scene_fixture


class SceneArchiveTests(unittest.TestCase):
    def test_independently_authored_v1_envelope_and_copy_are_read_without_relabel(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);lock=ScriptSourceLock(root/'source.lock')
            runtime=PrivateFeatureState(root/'owned.json');store=PrivateFeatureState(root/'archive.json')
            value={'actualOriginal':'preserved'};runtime.write(value,None)
            status=phase(3,95000);status.update(active=False,retiredEpochMs=94900)
            # Literal historical schema, neither current writer nor mutation of
            # a newly written v2 archive is used to construct these originals.
            copy=dict(iosEmoteFinalCopyVersion=1,runId=RUN,role='primary',binding=BINDING,index=1,path=str(runtime.path),payload=pack([value]))
            PrivateFeatureState(root/('emote-final-'+RUN+'-primary-1.json')).write(copy,None)
            payload=dict(phase='validated',phaseOriginal=status,hashes=[digest(value)],records=[dict(index=1,sha256=digest(copy))],pending=None,retired=0)
            original=dict(iosEmoteFinalArchiveVersion=1,runId=RUN,role='primary',binding=BINDING,artifactRoot=str(root),paths=[str(runtime.path)],payload=pack([payload]))
            store.write(original,None);checks=[]
            with lock.held():
                owner=IOSEmoteFinalArchive(store,root,BINDING,RUN,'primary',lock,lock,[runtime],lambda:True,lambda copies:checks.append(copies))
                self.assertEqual(1,owner.version);owner.retire();self.assertEqual(1,store.read()['iosEmoteFinalArchiveVersion'])
                self.assertEqual(copy,PrivateFeatureState(root/('emote-final-'+RUN+'-primary-1.json')).read())
                self.assertEqual(value,checks[0][str(runtime.path)])
            for version in (True,3):
                malformed=deepcopy(store.read());malformed['iosEmoteFinalArchiveVersion']=version;old=store.read();store.write(malformed,old)
                with self.assertRaises(NativeUIError):IOSEmoteFinalArchive(store,root,BINDING,RUN,'primary',lock,lock,[runtime],lambda:True,lambda _:True)
                store.write(old,malformed)

    def test_current_archive_writer_keeps_original_copy_schema_one(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);lock=ScriptSourceLock(root/'source.lock');runtime=PrivateFeatureState(root/'owned.json')
            runtime.write({'owned':True},None);store=PrivateFeatureState(root/'archive.json');status=phase(3,95000);status.update(active=False,retiredEpochMs=94900)
            with lock.held():
                owner=IOSEmoteFinalArchive(store,root,BINDING,RUN,'primary',lock,lock,[runtime],lambda:True,lambda _:True)
                owner.begin(status);owner.retire()
                self.assertEqual(2,store.read()['iosEmoteFinalArchiveVersion']);self.assertEqual(1,owner.record_store(1).read()['iosEmoteFinalCopyVersion'])

    def test_historical_scene_barrier_requires_own_ack_after_both_readiness_and_before_fence(self):
        h=scene_fixture.SceneGateTests();h.setUp();self.addCleanup(h.doCleanups)
        for role in h.roots:h.write(role,'initial')
        h.read('primary','initial');gate=h.gates['primary']
        with h.locks['primary'].held():gate.decode(gate.store.read())
        fence=h.endpoint('primary')['packet'];before(gate,'initial',h.ticket,fence)
        bad=deepcopy(fence);bad['sequence']=1
        with self.assertRaises(NativeUIError):before(gate,'initial',h.ticket,bad)
        with self.assertRaises(NativeUIError):before(gate,'initial','f'*32,fence)
        # A later override/restore call cannot cross this supposedly untouched
        # original barrier, even when the final override bit has returned false.
        from self_tests.test_native_feature_observation import Boundary
        from self_tests.test_native_animation_history import history_source
        source=Boundary();source.send(dict(commandId='1'*32));fresh=deepcopy(source.sample);history_source(fresh)
        history=fresh['animation']['history'];empty=deepcopy(history)
        empty.update(callSequence=0,overrideSequence=0,frameSequence=0,events=[],frames=[])
        modified=deepcopy(gate.replayed)
        own=gate.state['own'][0]['sha256'];peer=gate.state['peer'][0]['sha256']
        modified[own][1]['nativeEndpoint']['animation']['history']=empty
        modified[peer][1]['ownEndpoint']['animation']['history']=history
        fence['animation']['history']=deepcopy(history)
        from adapters.native_feature_observation import validate as native_packet
        for packet in (modified[own][1]['nativeEndpoint'],modified[peer][1]['ownEndpoint'],fence):
            native_packet(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'])
        gate.replayed=modified
        with self.assertRaises(NativeUIError):before(gate,'initial',h.ticket,fence)
