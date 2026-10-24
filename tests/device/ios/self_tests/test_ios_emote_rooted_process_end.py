"""Real process WAL/fence carrier/OS owner with explicit paired-proof models.

The full frozen paired seal and local fence authorization are deliberately NOT
qualified here. Their public constructors/readers have separate strict tests.
These cases exercise post-issued uncertainty, original OS clocks and no resend.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.test_ios_process_retirement import BINDING,RUN
from ios.self_tests.test_ios_retired_process import Boundary,SOURCE,BUNDLE


class RootedProcessEndStorageTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700);actor=root/'actor';actor.mkdir(mode=0o700)
        primary_lock=ScriptSourceLock(root/'script-feature-sources.lock');lock=ScriptSourceLock(actor/'script-feature-sources.lock')
        for current in (lock,primary_lock):
            held=current.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.os=Boundary();self.stops=[]
        def forbidden(*args,**kwargs):self.fail('Post-issued path queried native/SDK mutation instead of OS')
        adapter=SimpleNamespace(_candidate_guard=forbidden,_binding=forbidden,target=lambda selector:dict(appId=BUNDLE))
        runtime=IOSEmoteRuntime(adapter);runtime._sources=forbidden;runtime._emote_rooted_stop=lambda *args:self.stops.append(args)
        owner=object.__new__(IOSEmoteRootedProcessEnd);self.owner=owner
        owner.runtime,owner.run,owner.role,owner.root,owner.lock,owner.primary_lock=runtime,RUN,'actor',actor,lock,primary_lock
        owner.binding=deepcopy(BINDING);owner.monotonic=lambda:self.os.clock;owner.deadline=owner.last_clock=None;owner.peer=None
        owner.flow=SimpleNamespace(selector='fixture-actor',state=dict(binding=deepcopy(BINDING)),epoch_ms=self.os.epoch)
        owner.ownership=SimpleNamespace(roles=SimpleNamespace(locks=dict(primary=primary_lock,actor=lock)))
        archive_store=PrivateFeatureState(root/'explicit-frozen-model.json');archive_store.write(dict(pairedProofModel=True),None)
        owner.archive=SimpleNamespace(store=archive_store,previous=archive_store.read());owner.seal=dict(explicitSealModel=True)
        owner.store=PrivateFeatureState(actor/('ios-emote-actor-'+RUN+'-rooted-process-end.json'))
        owner.previous=owner.state=None
        owner.frames=OriginalFrameStore(actor,BINDING,RUN,'actor',owner.bound,owner.intent,
            namespace='emote-rooted-process',schema_prefix='emoteRootedProcess',monotonic=owner.monotonic)
        owner.state=dict(phase='prepared',source=deepcopy(SOURCE),bundleId=BUNDLE,peer=None,fence=None,pending=None,processSha256=None);owner.save()
        ref=owner.frames.write(1,dict(phaseAfter=dict(capturedEpochMs=self.os.epoch()-100),explicitLocalFenceModel=True))
        owner.state.update(phase='stop-issued',fence=ref,pending=None);owner.save()
        # Only paired/native authorization is modeled. The original host
        # carrier is always physically read before the real OS owner advances.
        owner.fence_validate=lambda:dict(explicitFenceModel=owner.fence_original())
        self.enterContext(patch('ios.adapters.emote_rooted_process_end.retired_process_observer',side_effect=lambda *args:self.os.reader()))
        self.enterContext(patch('ios.adapters.emote_rooted_process_end.mark_stopped',side_effect=lambda *args:None))
    def test_issued_uncertainty_advances_only_os_and_complete_replay_has_no_new_query(self):
        owner=self.owner
        self.assertFalse(owner.advance());self.os.clock+=1.6;self.assertFalse(owner.advance());self.os.clock+=1.6
        self.assertTrue(owner.advance());self.assertEqual('complete',owner.state['phase'])
        queries=deepcopy(self.os.queries);self.assertEqual(3,len(queries));self.assertTrue(owner.os_state()['windows'][-1]['complete'])
        self.assertEqual(owner.previous,owner.completed());self.assertTrue(owner.advance());self.assertEqual(queries,self.os.queries)
        self.assertEqual([],self.stops)
    def test_issued_stop_cannot_be_repeated_even_when_no_os_absence_exists(self):
        owner=self.owner;self.os.running=[True,True]
        with self.assertRaises(NativeUIError):owner.stop(None,None,None)
        self.assertFalse(owner.advance());self.assertEqual('stop-issued',owner.state['phase']);self.assertEqual([],self.stops)
    def test_lost_os_reply_keeps_issued_responsibility_and_new_read_cannot_bridge_failure(self):
        owner=self.owner
        with patch.object(self.os,'send',side_effect=OSError('Explicit lost OS reply')),self.assertRaises(NativeUIError):owner.advance()
        self.assertEqual('stop-issued',owner.state['phase']);self.os.clock+=1
        self.assertFalse(owner.advance());self.assertEqual([],self.stops)
        state=owner.os_state();self.assertEqual(1,state['windows'][-1]['start']);self.assertEqual(0,state['windows'][-1]['elapsedMs'])
        from ios.adapters.process_retirement import IOSProcessRetirement
        reader=object.__new__(IOSProcessRetirement);reader.profile='emote';reader.store=owner.os_store()
        reader.binding,reader.source,reader.bundle,reader.run,reader.role,reader.stage=owner.binding,SOURCE,BUNDLE,RUN,'actor',0
        reader.pid=42;reader.historical=True;reader._archives=None
        self.assertEqual(['abandoned','observed'],[reader.load(ref)['mode'] for ref in state['records']])
    def test_replaced_original_fence_or_changed_private_wal_blocks_before_any_os_query(self):
        owner=self.owner;path=owner.frames.path(owner.frames.expand(owner.state['fence']));replacement=path.with_suffix('.replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):owner.advance()
        self.assertEqual([],self.os.queries);self.assertEqual([],self.stops)


if __name__=='__main__':unittest.main()
