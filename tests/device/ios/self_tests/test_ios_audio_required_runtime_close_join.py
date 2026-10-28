"""Actual runtime PCM factory joins strict input origin and normal Close.

PCM/Audio/Qt/OS/SDK boundaries are declared host models. The actual owners,
five cycles, fourteen ordinary actions, byte carriers and independent native
absence codecs execute. No acoustic, physical ADC, peer or whole-end claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import unittest
import wave
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease,INPUT_ORIGIN_PROFILE
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_session_owners import ensure_released
from ios.self_tests import test_ios_audio_normal_journey as normal
from ios.self_tests import test_ios_audio_pcm_input_origin_profile as origin
from ios.self_tests import test_ios_audio_normal_close_evidence as closing


class RequiredClosePCMModel(origin.InputOriginPCMModel,closing.ClosePCMModel):
    """Compose the two original producer methods before first PCM capture.

    InputOrigin.source -> Close.source -> PCM.source creates real native-model
    files, then derives fragments from those exact bytes; original send MRO
    keeps guarded Close2 release and emitted packet2. No saved DTO is upgraded.
    """


class AudioRequiredRuntimeCloseJoinTests(unittest.TestCase):
    def test_same14_actions_actual_runtime_strict_PCM_and_close5_do_not_unlock_whole_session_end(self):
        lease,retired,closed,model,runtime=normal.AudioNormalJourneyTests.run_normal_journey(self,
            pcm_model=RequiredClosePCMModel,pcm_profile=INPUT_ORIGIN_PROFILE,close_evidence=True,runtime_pcm=True)
        self.assertEqual(2,lease.version);self.assertEqual(INPUT_ORIGIN_PROFILE,lease.profile)
        self.assertEqual(3,retired['recording']['cycle']);self.assertEqual(5,closed['recording']['cycle'])
        self.assertTrue(retired['captured']);self.assertFalse(closed['captured'])
        self.assertEqual(1,model.count('feature-recorded-audio-observe'));self.assertFalse(model.memory)
        self.assertEqual([],list(model.native_root.iterdir()))
        parent=lease.recorded;commands=deepcopy(model.commands);inputs=deepcopy(model.model.actions)
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Combined replay attempted product write')):
            archived=IOSAudioRecordedOwner.archive(parent.store,parent.root,parent.binding,parent.run,parent.lock,parent.fixture_url)
            old=IOSAudioPCMLease.archive(lease.store,archived)
            final=IOSAudioPCMLease.archive(PrivateFeatureState(parent.root/'ios-audio-close-lease.json'),archived)
            self.assertEqual(2,old.version);self.assertEqual(3,final.version)
            snapshot=old.snapshot();callback=snapshot['packet']['source']['inputOrigin']
            self.assertTrue(callback['available']);self.assertEqual(INPUT_ORIGIN_PROFILE,callback['profile'])
            for flag in ('physicalADCQualified','acousticQualified','peerQualified','resamplerHistoryQualified'):
                self.assertIs(False,callback[flag])
            with wave.open(BytesIO(old.input_wav()),'rb') as container:
                self.assertEqual(snapshot['packet']['source']['sampleRate'],container.getframerate())
                self.assertEqual(snapshot['pcm']['input'],container.readframes(container.getnframes()))
            # Independent absence for latest cycle5 is never a cycle3 snapshot
            # or input-wave original; cleanup-only mode has no allocation.
            self.assertIsNone(final.state['allocation']);self.assertEqual(closed,final.retired())
            with self.assertRaises(NativeUIError):final.input_wav()
            self.assertEqual(retired,old.retired())
        self.assertEqual(commands,model.commands);self.assertEqual(inputs,model.model.actions)
        # Native empty diagnostic memory does not retire loaded page/code,
        # callback/session/source/SDK or independent acoustic responsibility.
        with self.assertRaises(NativeUIError):ensure_released(runtime.adapter,'test-only')
        self.assertEqual(commands,model.commands);self.assertEqual(inputs,model.model.actions)
        self.assertTrue((parent.root/'ios-audio-recorded-owner.json').exists())
        self.assertTrue((parent.root/'ios-audio-scope.json').exists())


if __name__=='__main__':unittest.main()
