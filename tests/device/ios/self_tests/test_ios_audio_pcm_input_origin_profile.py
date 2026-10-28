"""Durable required callback-origin profile over actual PCM ownership.

Native audio/SDK/OS producers are explicit models; real original bytes, CAS,
ordinary actions, source decoders and loss/recovery execute on the host.
No ADC, acoustic, peer, resampler-history or whole Audio qualification follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_evidence import INPUT
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease,INPUT_ORIGIN_PROFILE
from ios.adapters.audio_pcm_runtime import lease as runtime_lease
from ios.adapters.audio_runtime import IOSAudioRuntime
from ios.self_tests import test_ios_audio_pcm_lease as pcm_fixture
from ios.self_tests import test_ios_audio_normal_journey as normal_fixture


class InputOriginPCMModel(pcm_fixture.PCMModel):
    """Declared synchronous callback model; fragments use actual emitted bytes."""
    unavailable=False
    corrupt_fragment=False
    def source(self):
        source=super().source();raw=self.files[INPUT];frame=source['channels']*2
        split=(len(raw)//2//frame)*frame;rows=[]
        for index,(start,end) in enumerate(((0,split),(split,len(raw))),1):
            fragment=raw[start:end];digest=hashlib.sha256(fragment).hexdigest()
            rows.append(dict(sequence=index,generation=1,readBytes=len(fragment),readSha256=digest,
                inputRate=source['sampleRate'],inputChannels=source['channels'],resamplerUsed=False,routeRevision='1',
                readBeforeEpochMs=source['inputLastEpochMs'],readAfterEpochMs=source['inputLastEpochMs'],
                readBeforeMonotonicMs=100,readAfterMonotonicMs=100,tapEpochMs=source['inputLastEpochMs'],
                tapMonotonicMs=100,offset=start,bytes=len(fragment),convertedBytes=len(fragment),sha256=digest))
        if self.corrupt_fragment:rows[0]['sha256']='f'*64
        source['inputOrigin']=dict(originVersion=1,available=True,profile=INPUT_ORIGIN_PROFILE,
            instance=self.model.native_instance,admissionEpoch=5,coveredBytes=len(raw),rows=rows,
            physicalADCQualified=False,acousticQualified=False,peerQualified=False,resamplerHistoryQualified=False)
        if self.unavailable:source['inputOrigin']=dict(originVersion=1,available=False)
        return source
    def send(self,command):
        try:return super().send(command)
        finally:
            if command['action']=='feature-recorded-audio-observe' and self.packet is not None:self.packet['schemaVersion']=2


class RequiredInputOriginLeaseTests(unittest.TestCase):
    def setUp(self):
        pcm_fixture.AudioPCMLeaseTests.setUp(self);self.model=InputOriginPCMModel(self.fixture.model)
    def archive(self):return pcm_fixture.AudioPCMLeaseTests.archive(self)
    @contextmanager
    def lease(self,*,profile=INPUT_ORIGIN_PROFILE):
        with self.fixture.owner() as recorded:
            native,preview=self.model.reader()
            yield IOSAudioPCMLease(self.store,recorded,native=native,preview=preview,profile=profile)
    def test_required_origin_captures_actual_fragments_and_archive_reopens_without_new_queries(self):
        with self.lease() as owner:
            snapshot=owner.capture();self.assertEqual(2,owner.previous['iosAudioPCMLeaseVersion'])
            self.assertEqual(INPUT_ORIGIN_PROFILE,owner.previous['profile'])
            self.assertEqual(self.model.files[INPUT],snapshot['pcm']['input'])
            origin=snapshot['packet']['source']['inputOrigin'];self.assertTrue(origin['available'])
            self.assertEqual(len(snapshot['pcm']['input']),origin['coveredBytes'])
            retired=owner.retire();self.assertTrue(retired['captured'])
        queries=deepcopy(self.model.commands);self.assertEqual(retired,self.archive());self.assertEqual(queries,self.model.commands)
    def refused_snapshot_stays_owned(self):
        with self.lease() as owner:
            with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'))
        with self.lease() as owner:
            with self.assertRaises(NativeUIError):owner.capture()
            cleanup=owner.retire();self.assertTrue(cleanup['retired']);self.assertFalse(cleanup['captured'])
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'))
        self.assertEqual(1,self.model.count('feature-recorded-audio-release'))
        self.assertEqual(cleanup,self.archive())
    def test_literal_one_packet_cannot_supply_required_origin_or_replay_allocation(self):
        self.model=pcm_fixture.PCMModel(self.fixture.model);self.refused_snapshot_stays_owned()
    def test_unavailable_origin_cannot_supply_required_snapshot_or_replay_allocation(self):
        self.model.unavailable=True;self.refused_snapshot_stays_owned()
    def test_fragment_mismatch_refuses_even_when_complete_input_descriptor_matches(self):
        self.model.corrupt_fragment=True;self.refused_snapshot_stays_owned()
    def test_lost_release_and_default_reopen_preserve_original_strict_profile_without_replay(self):
        with self.lease() as owner:owner.capture()
        self.model.lose_release=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.model.lose_release=False
        with self.lease(profile=None) as owner:
            self.assertEqual(2,owner.version);self.assertEqual(INPUT_ORIGIN_PROFILE,owner.profile)
            self.assertTrue(owner.retire()['captured'])
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'))
        self.assertEqual(1,self.model.count('feature-recorded-audio-release'));self.archive()
    def test_mutated_requested_profile_refuses_before_allocation(self):
        with self.lease() as owner:
            owner.version=1
            with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(0,self.model.count('feature-recorded-audio-observe'))
        with self.lease() as owner:
            owner.profile=None
            with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(0,self.model.count('feature-recorded-audio-observe'))

    def test_legacy_allocation_cannot_be_reclassified_as_required_origin(self):
        with self.lease(profile=None) as owner:
            owner.capture();self.assertEqual(1,owner.version)
        queries=deepcopy(self.model.commands)
        with self.assertRaises(NativeUIError):
            with self.lease():self.fail('Legacy allocation must retain its original profile')
        self.assertEqual(queries,self.model.commands)
        with self.lease(profile=None) as owner:self.assertTrue(owner.retire()['captured'])


class RequiredInputOriginFactoryTests(unittest.TestCase):
    def test_unknown_profile_refuses_before_any_runtime_source_or_parent_access(self):
        runtime=object.__new__(IOSAudioRuntime)
        def forbidden(*_args,**_kwargs):raise AssertionError('Unknown profile must not acquire source')
        runtime._sources=forbidden
        for profile in (True,1,'','required','qt-source-read-to-preview-tap-v2'):
            with self.subTest(profile=profile),self.assertRaises(NativeUIError):runtime_lease(runtime,'primary',None,profile=profile)


class RequiredInputOriginNormalJourneyTests(unittest.TestCase):
    def test_all_fourteen_actions_same_process_resume_and_required_original_input_pcm(self):
        owner,retired=normal_fixture.AudioNormalJourneyTests.run_normal_journey(self,pcm_model=InputOriginPCMModel,pcm_profile=INPUT_ORIGIN_PROFILE)
        self.assertEqual(2,owner.version);self.assertEqual(INPUT_ORIGIN_PROFILE,owner.profile)
        self.assertTrue(retired['captured']);self.assertTrue(owner.snapshot()['packet']['source']['inputOrigin']['available'])


if __name__=='__main__':unittest.main()
