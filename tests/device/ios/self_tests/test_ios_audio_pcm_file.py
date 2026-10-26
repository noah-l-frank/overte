"""Lossless original input framing and common detector, with declared audio."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import array
from copy import deepcopy
import hashlib
import io
import os
import sys
import unittest
from unittest.mock import patch
import wave
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_evidence import INPUT,SINK
from feature_journeys.evidence import file_observation
from feature_journeys.fixtures import challenge
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.self_tests.test_ios_audio_pcm_lease import AudioPCMLeaseTests,PCMModel
from voice_peer import voice_signal


def stereo(challenge_id):
    mono=voice_signal.samples(challenge_id,48000,profile=voice_signal.PREVIEW_PROFILE)
    # Opposite polarity channels are genuine separate samples, not mixed down.
    interleaved=array.array('h',(value for sample in mono for value in (sample,-sample)))
    if sys.byteorder!='little':interleaved.byteswap()
    return interleaved.tobytes()


class OriginalPCM(PCMModel):
    def __init__(self,model,raw,sink):super().__init__(model);self.raw,self.sink=raw,sink
    def source(self):
        value=super().source();self.files={INPUT:self.raw,SINK:self.sink}
        for kind,name in (('input',INPUT),('sink',SINK)):
            value[kind].update(bytes=len(self.files[name]),sha256=hashlib.sha256(self.files[name]).hexdigest())
        return value


class AudioPCMFileTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioPCMLeaseTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.m=self.f.fixture.model;self.challenge=challenge(self.m.owner.run,self.m.ticket).hex()
        self.raw=stereo(self.challenge)
        self.f.model=OriginalPCM(self.m,self.raw,b'\0'*len(self.raw)*2)

    def qualify(self,content,*,ticket=None):
        return file_observation(content,'audio',self.m.owner.run,ticket or self.m.ticket,{})

    def test_common_file_detector_reads_only_original_input_without_losing_inverted_stereo(self):
        with self.f.lease() as owner:
            owner.capture();content=owner.input_wav();result=self.qualify(content)
            self.assertTrue(result['passed']);self.assertEqual(2,result['channelCount'])
            self.assertFalse(any(self.f.model.files[SINK]))
            with wave.open(io.BytesIO(content),'rb') as container:
                self.assertEqual((2,2,48000,144000),tuple((container.getnchannels(),container.getsampwidth(),container.getframerate(),container.getnframes())))
                self.assertEqual(self.raw,container.readframes(container.getnframes()))
            self.assertIn('no physical microphone or loudspeaker claim',result['proof'])
            owner.retire()

    def test_wrong_run_ticket_and_legacy_profile_are_not_accepted_as_original_file_evidence(self):
        with self.f.lease() as owner:
            owner.capture();content=owner.input_wav()
            with self.assertRaises(AssertionError):self.qualify(content,ticket='9'*32)
            with self.assertRaises(AssertionError):file_observation(content,'audio','8'*32,self.m.ticket,{})
            self.assertFalse(voice_signal.analyze(self.write_analysis(content),self.challenge)['passed'])

    def write_analysis(self,content):
        path=self.f.fixture.root/'analysis.wav';path.write_bytes(content);path.chmod(0o600);return path

    def test_challenge_in_digital_sink_cannot_replace_quiet_original_input(self):
        self.f.model.raw=b'\0'*len(self.raw);self.f.model.sink=self.raw
        with self.f.lease() as owner:
            owner.capture()
            with self.assertRaises(AssertionError):self.qualify(owner.input_wav())
            owner.retire()

    def test_missing_or_same_byte_replaced_chunk_is_not_reconstructed(self):
        with self.f.lease() as owner:
            owner.capture();frame=owner.originals.read(owner.state['snapshot'])
            path=owner.originals.files.path(owner.originals.files.expand(frame['chunks']['input'][0]))
            replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
            os.replace(replacement,path)
            with self.assertRaises(NativeUIError):owner.input_wav()
            path.unlink()
            with self.assertRaises((NativeUIError,OSError)):owner.input_wav()

    def test_pure_retired_framing_has_no_queries_writes_or_original_changes(self):
        with self.f.lease() as owner:
            owner.capture();expected=owner.input_wav();owner.retire();url=owner.recorded.fixture_url
        f=self.f.fixture;files={path:(path.stat().st_ino,path.read_bytes()) for path in f.root.iterdir() if path.is_file()}
        commands=deepcopy(self.f.model.commands);queries=self.m.counter
        with f.lock.held(),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No archival writes')):
            parent=IOSAudioRecordedOwner.archive(f.store,f.root,self.m.owner.binding,self.m.owner.run,f.lock,url)
            owner=IOSAudioPCMLease.archive(self.f.store,parent)
            self.assertEqual(expected,owner.input_wav());self.assertTrue(self.qualify(expected)['passed'])
        self.assertEqual(commands,self.f.model.commands);self.assertEqual(queries,self.m.counter)
        self.assertEqual(files,{path:(path.stat().st_ino,path.read_bytes()) for path in f.root.iterdir() if path.is_file()})


if __name__=='__main__':unittest.main()
