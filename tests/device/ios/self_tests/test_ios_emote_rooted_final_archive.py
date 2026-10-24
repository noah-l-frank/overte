"""Host copy durability; native replies are explicit GPU fixture models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack
from ios.adapters.emote_final_archive import IOSEmoteFinalArchive
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.self_tests import test_ios_emote_rooted_gpu as gpu_fixture
from ios.self_tests.test_ios_emote_sources import phase


class RootedFinalArchiveTests(unittest.TestCase):
    def setUp(self):
        self.f=gpu_fixture.CurrentGPUTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.lease=self.f.owner.lock.held();self.lease.__enter__();self.addCleanup(self.lease.__exit__,None,None,None)
        self.store=PrivateFeatureState(self.f.root/'ios-emote-rooted-final.json')
        self.paths=[self.f.store];self.checks=0
        self.status=phase(3,95000);self.status.update(runId=self.f.flow.run,active=False,retiredEpochMs=94900)

    def validate(self,copies):
        self.checks+=1;f=self.f
        VulkanWorldFrameOwner.archive_original(copies[str(f.store.path)],f.root,f.flow.state['binding'],
            f.flow.run,'primary',0,f.owner.request_id,f.owner.lock)

    def owner(self,validate=None):
        f=self.f
        return IOSEmoteRootedFinalArchive(self.store,f.root,f.flow.state['binding'],f.flow.run,'primary',
            f.owner.lock,f.owner.lock,self.paths,lambda:True,validate or self.validate)

    def test_freeze_reopens_actual_png_and_retains_all_current_ownership(self):
        before=self.f.store.read();commands=deepcopy(self.f.native.commands)
        archive=self.owner();archive.begin(self.status);archive.freeze()
        self.assertEqual('validated',archive.state['phase']);self.assertEqual(1,self.checks)
        self.assertEqual(before,self.f.store.read());self.assertEqual(commands,self.f.native.commands)
        self.assertEqual(before,archive.copies()[str(self.f.store.path)])
        self.owner().qualify();self.assertEqual(2,self.checks)
        with self.assertRaises(EmoteObservationPending):archive.retire()
        self.assertEqual(before,self.f.store.read())

    def test_copy_return_loss_adopts_the_same_existing_host_copy(self):
        archive=self.owner();archive.begin(self.status);write=PrivateFeatureState.write;lost=[]
        def once(store,value,previous):
            write(store,value,previous)
            if store.path==archive.record_store(1).path and not lost:
                lost.append(store.path.stat().st_ino);raise OSError('Lost host copy return')
        with patch.object(PrivateFeatureState,'write',once),self.assertRaises(OSError):archive.freeze()
        resumed=self.owner();resumed.freeze()
        self.assertEqual(lost[0],resumed.record_store(1).path.stat().st_ino)
        self.assertEqual('validated',resumed.state['phase']);self.assertIsNotNone(self.f.store.read())

    def test_original_failure_keeps_freezing_and_cannot_authorize_retirement(self):
        archive=self.owner();archive.begin(self.status)
        def failed(_copies):raise NativeUIError('Actual original proof unavailable')
        archive.validate=failed
        with self.assertRaises(NativeUIError):archive.freeze()
        self.assertEqual('freezing',archive.state['phase']);self.assertIsNotNone(self.f.store.read())
        with self.assertRaises(EmoteObservationPending):archive.retire()

    def test_explicit_false_validation_cannot_promote_the_host_archive(self):
        archive=self.owner(lambda _copies:False);archive.begin(self.status)
        with self.assertRaises(NativeUIError):archive.freeze()
        self.assertEqual('freezing',archive.state['phase']);self.assertIsNotNone(self.f.store.read())

    def test_changed_current_metadata_after_begin_is_never_copied(self):
        archive=self.owner();archive.begin(self.status)
        value=self.f.store.read();self.f.store.write(dict(value,phase='captured'),value)
        with self.assertRaises(NativeUIError):archive.freeze()
        self.assertIsNone(archive.record_store(1).read())
        self.assertEqual('captured',self.f.store.read()['phase'])

    def test_literal_legacy_and_rooted_headers_cannot_be_relabelled_or_mixed(self):
        archive=self.owner();archive.begin(self.status);archive.freeze();original=self.store.read()
        f=self.f
        with self.assertRaises(NativeUIError):
            IOSEmoteFinalArchive(self.store,f.root,f.flow.state['binding'],f.flow.run,'primary',
                f.owner.lock,f.owner.lock,self.paths,lambda:True,self.validate)
        for version in (True,2):
            malformed=dict(original,iosEmoteRootedFinalArchiveVersion=version);self.store.write(malformed,self.store.read())
            with self.assertRaises(NativeUIError):self.owner()
        self.store.write(original,self.store.read())
        store=archive.record_store(1);value=store.read();bad=deepcopy(value)
        bad['iosEmoteFinalCopyVersion']=bad.pop('iosEmoteRootedFinalCopyVersion');store.write(bad,value)
        with self.assertRaises(NativeUIError):self.owner()

    def test_early_retiring_and_complete_phase_packets_are_rejected(self):
        archive=self.owner();archive.begin(self.status);archive.freeze();original=self.store.read()
        for stage in ('retiring','complete'):
            state=unpack(original['payload'])[0];state.update(phase=stage,retired=len(self.paths))
            malformed=dict(original,payload=pack([state]));self.store.write(malformed,self.store.read())
            with self.assertRaises(NativeUIError):self.owner()
        self.assertIsNotNone(self.f.store.read())


if __name__=='__main__':unittest.main()
