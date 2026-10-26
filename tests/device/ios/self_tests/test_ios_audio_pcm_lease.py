"""Actual PCM carrier/WAL logic with explicit modeled iOS/audio transport.

No SDK, microphone, acoustic receiver, device, process or compiler is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_evidence import RecordedPreviewEvidence,INPUT,SINK
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.self_tests.test_ios_audio_recorded_owner import AudioRecordedOwnerTests
from self_tests.test_recorded_preview_history import voice,event


class PCMModel:
    def __init__(self,model):
        self.model=model;self.sequence=0;self.packet=None;self.files={};self.memory=True;self.commands=[]
        self.lose_snapshot=False;self.lose_release=False;self.ignore_release=False;self.ack_only=False;self.bad_transfer=False
        self.large_sink=False;self.keep_memory=False;self.keep_file=False;self.foreign=False
    def complete(self):
        m=self.model;rows=deepcopy(m.recorded['events']);seq=rows[-1]['eventSequence']
        for index,(phase,played) in enumerate((('playing',96000),('draining',576000),('completed',576000)),1):
            m.tick();rows.append(event(seq+index,phase,576000,played,epoch=m.native_epoch()))
        m.active=False;m.phase='completed';m.recorded=voice(rows,cycle=m.cycle,started=m.recorded['startedEpochMs'])
    def send_native(self,command):
        m=self.model;m.tick();m.native.send(command);packet=m.native.sample
        packet.update(processId=42,capturedEpochMs=m.native_epoch(),requestedEpochMs=m.native_epoch(),instance=m.native_instance,animation={})
        packet.pop('animationFence');packet['audio']=dict(recording=False,muted=m.muted,recordedVoice=deepcopy(m.recorded))
    def source(self):
        m=self.model;source=m.recorded
        raw=b'\x01\x00\x02\x00'*(source['event']['capturedBytes']//4)
        sink=raw if not self.large_sink else raw+raw+raw
        self.files={INPUT:raw,SINK:sink};self.memory=True
        def descriptor(name,tap):
            value=self.files[name];return dict(name=name,tap=tap,bytes=len(value),sha256=hashlib.sha256(value).hexdigest())
        return dict(cycle=source['cycle'],startedEpochMs=source['startedEpochMs'],sampleRate=source['captureSampleRate'],channels=source['captureChannels'],
            inputLastEpochMs=m.native_epoch(),sinkLastEpochMs=m.native_epoch(),events=deepcopy(source['events']),
            input=descriptor(INPUT,'capture-before-normalization'),sink=descriptor(SINK,'loopback-device-accepted-write'))
    def send(self,command):
        self.commands.append(deepcopy(command));m=self.model;m.tick();action=command['action']
        if action=='feature-recorded-audio-observe':
            source=self.source();self.sequence+=1
            self.packet=dict(schemaVersion=1,requestId=command['commandId'],instance=m.native_instance,sequence=self.sequence,
                requestedEpochMs=m.native_epoch(),capturedEpochMs=m.native_epoch(),processId=42,source=source)
            if self.foreign:self.packet['source']['cycle']+=1
            if self.lose_snapshot:raise NativeUIError('Explicit model lost snapshot response after allocation')
        elif action=='feature-recorded-audio-release':
            if not self.ignore_release:
                if not self.keep_file:self.files={}
                if not self.keep_memory:self.memory=False
            self.packet=dict(schemaVersion=1,requestId=command['commandId'],released=self.ack_only or not self.memory and not self.files)
            if self.lose_release:raise NativeUIError('Explicit model lost release return after delivery')
        else:
            need(action=='feature-recorded-audio-files');self.sequence+=1
            self.packet=dict(schemaVersion=1,requestId=command['commandId'],instance=m.native_instance,sequence=self.sequence,
                requestedEpochMs=m.native_epoch(),capturedEpochMs=m.native_epoch(),processId=42,
                files=[dict(name=name,exists=name in self.files) for name in (INPUT,SINK)],memoryEmpty=not self.memory)
    def reader(self):
        m=self.model
        native=NativeFeatureObservation(self.send_native,lambda:json.dumps(m.native.sample),m.native_epoch,m.guard,42,
            ios=True,monotonic=lambda:m.clock,sleep=m.sleep)
        def read_bytes(name):
            need(not self.bad_transfer);return self.files[name]
        preview=RecordedPreviewEvidence(self.send,lambda:json.dumps(self.packet),read_bytes,
            lambda:native.read(native.sequence)['capturedEpochMs'],m.guard,42,ios=True,monotonic=lambda:m.clock,sleep=m.sleep)
        return native,preview
    def count(self,action):return sum(value['action']==action for value in self.commands)


class AudioPCMLeaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AudioRecordedOwnerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.start();self.model=PCMModel(self.fixture.model);self.model.complete()
        self.store=PrivateFeatureState(self.fixture.root/'ios-audio-pcm-lease.json')
    @contextmanager
    def lease(self):
        with self.fixture.owner() as recorded:
            native,preview=self.model.reader();yield IOSAudioPCMLease(self.store,recorded,native=native,preview=preview)
    def archive(self):
        with self.fixture.lock.held():
            value=self.fixture.store.read()
            recorded=IOSAudioRecordedOwner.archive(self.fixture.store,self.fixture.root,self.fixture.model.owner.binding,
                self.fixture.model.owner.run,self.fixture.lock,value['fixtureUrl'])
            return IOSAudioPCMLease.archive(self.store,recorded).retired()

    def test_original_pcm_larger_than_one_carrier_is_preserved_and_pure_retirement_has_no_getters(self):
        self.model.large_sink=True
        with self.lease() as owner:
            result=owner.capture();self.assertEqual(self.model.files[INPUT],result['pcm']['input'])
            self.assertEqual(self.model.files[SINK],result['pcm']['sink']);self.assertGreater(len(result['pcm']['sink']),1024*1024)
            frame=owner.originals.read(owner.state['snapshot']);self.assertGreater(len(frame['chunks']['sink']),16)
            self.assertFalse(frame['preflight']['memoryEmpty'])
            self.assertTrue(all(reference['bytes']<1024*1024 for reference in owner.state['records']))
            result=owner.retire();self.assertTrue(result['captured']);self.assertFalse(self.model.files);self.assertFalse(self.model.memory)
        requests=deepcopy(self.model.commands);self.assertEqual(result,self.archive());self.assertEqual(requests,self.model.commands)
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'));self.assertEqual(1,self.model.count('feature-recorded-audio-release'))

    def test_lost_allocation_return_is_never_resent_and_cleanup_preserves_missing_snapshot_outcome(self):
        self.model.lose_snapshot=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.capture()
        self.assertTrue(self.model.files);self.model.lose_snapshot=False
        with self.lease() as owner:
            with self.assertRaises(NativeUIError):owner.capture()
            result=owner.retire();self.assertFalse(result['captured']);self.assertTrue(result['retired'])
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'));self.assertFalse(self.model.files)
        self.assertEqual(result,self.archive())

    def test_failed_pcm_pull_remains_owned_without_new_allocation_and_can_only_report_resource_cleanup(self):
        self.model.bad_transfer=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.capture()
        self.model.bad_transfer=False
        with self.lease() as owner:
            with self.assertRaises(NativeUIError):owner.capture()
            self.assertFalse(owner.retire()['captured'])
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'))

    def test_lost_release_return_reconstructs_read_only_absence_without_a_second_release(self):
        with self.lease() as owner:owner.capture()
        self.model.lose_release=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.model.lose_release=False
        with self.lease() as owner:self.assertTrue(owner.retire()['retired'])
        self.assertEqual(1,self.model.count('feature-recorded-audio-release'))
        self.assertEqual(2,self.model.count('feature-recorded-audio-files'))

    def test_release_acknowledgement_cannot_replace_actual_file_and_memory_absence(self):
        with self.lease() as owner:owner.capture()
        self.model.ignore_release=True;self.model.ack_only=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.retire()
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual(1,self.model.count('feature-recorded-audio-release'));self.assertTrue(self.model.files);self.assertTrue(self.model.memory)

    def test_memory_must_be_empty_even_when_both_files_are_actually_absent(self):
        with self.lease() as owner:owner.capture()
        self.model.keep_memory=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertFalse(self.model.files);self.assertTrue(self.model.memory)
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual(1,self.model.count('feature-recorded-audio-release'))

    def test_existing_file_blocks_retirement_even_when_native_memory_is_empty(self):
        with self.lease() as owner:owner.capture()
        self.model.keep_file=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertTrue(self.model.files);self.assertFalse(self.model.memory)

    def test_foreign_cycle_cannot_be_admitted_as_this_recording_snapshot(self):
        self.model.foreign=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'))
        with self.lease() as owner:self.assertFalse(owner.retire()['captured'])

    def test_missing_chunk_and_lost_lease_metadata_cannot_be_recreated_or_reclassified_as_empty(self):
        with self.lease() as owner:
            owner.capture();frame=owner.originals.read(owner.state['snapshot'])
            path=owner.originals.files.path(owner.originals.files.expand(frame['chunks']['input'][0]))
        path.unlink()
        with self.assertRaises((NativeUIError,OSError)):
            with self.lease():pass
        original=self.store.read();self.store.discard(original)
        with self.assertRaises(NativeUIError):
            with self.lease():pass
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'))

    def test_lost_unknown_allocation_metadata_cannot_overwrite_or_release_existing_remote_tap_files(self):
        self.model.lose_snapshot=True
        with self.lease() as owner,self.assertRaises(NativeUIError):owner.capture()
        original=self.store.read();self.store.discard(original);self.model.lose_snapshot=False
        with self.lease() as owner:
            with self.assertRaises(NativeUIError):owner.capture()
            self.assertIsNone(owner.state['allocation'])
            with self.assertRaises(NativeUIError):owner.retire()
        self.assertTrue(self.model.files);self.assertTrue(self.model.memory)
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'));self.assertEqual(0,self.model.count('feature-recorded-audio-release'))

    def test_fully_saved_snapshot_original_recovers_without_another_allocation(self):
        with self.lease() as owner:
            write=owner.originals.write
            def lost(value):
                reference=write(value)
                if value['audioPCMKind']=='snapshot':raise NativeUIError('Explicit lost return after original snapshot save')
                return reference
            with patch.object(owner.originals,'write',side_effect=lost),self.assertRaises(NativeUIError):owner.capture()
            self.assertIsNone(owner.state['snapshot'])
        with self.lease() as owner:self.assertEqual(self.model.files[INPUT],owner.capture()['pcm']['input'])
        self.assertEqual(1,self.model.count('feature-recorded-audio-observe'))

    def test_fully_saved_absence_original_recovers_without_new_native_reads_or_release(self):
        with self.lease() as owner:
            owner.capture();write=owner.originals.write
            def lost(value):
                reference=write(value)
                if value['audioPCMKind']=='absence':raise NativeUIError('Explicit lost return after original absence save')
                return reference
            with patch.object(owner.originals,'write',side_effect=lost),self.assertRaises(NativeUIError):owner.retire()
        requests=deepcopy(self.model.commands)
        with self.lease() as owner:self.assertTrue(owner.retire()['retired'])
        self.assertEqual(requests,self.model.commands)

    def later_start(self):
        self.fixture.model.add_phase('record-start','6'*32)
        with self.fixture.owner() as owner:owner.act(self.fixture.model.ticket,'record-start')

    def test_retired_original_keeps_earlier_owned_start_after_a_later_normal_cycle(self):
        with self.lease() as owner:
            owner.capture();retired=owner.retire()
        saved=self.store.read();body=self.store.path.read_bytes();inode=self.store.path.stat().st_ino
        self.later_start();self.fixture.cancel_phase()
        with self.fixture.owner() as owner:owner.act(self.fixture.model.ticket,'record-cancel')
        commands=deepcopy(self.model.commands);queries=self.fixture.model.counter
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical lease must not write')):
            self.assertEqual(retired,self.archive())
            with self.lease() as owner:self.assertEqual(retired,owner.retire())
        self.assertEqual(commands,self.model.commands);self.assertEqual(queries,self.fixture.model.counter)
        self.assertEqual(saved,self.store.read());self.assertEqual(body,self.store.path.read_bytes())
        self.assertEqual(inode,self.store.path.stat().st_ino)

    def test_unretired_earlier_lease_cannot_release_a_new_current_cycle(self):
        with self.lease() as owner:owner.capture()
        self.later_start();files=deepcopy(self.model.files)
        with self.lease() as owner:
            with self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual(0,self.model.count('feature-recorded-audio-release'))
        self.assertEqual(files,self.model.files);self.assertTrue(self.model.memory)

    def test_saved_recording_must_match_an_entire_actual_owned_start(self):
        with self.lease() as owner:owner.capture();owner.retire()
        self.later_start();saved=self.store.read()
        for key,value in (('ticket','7'*32),('cycle',99),('operationSha256','0'*64),('original',None)):
            with self.subTest(key=key):
                changed=deepcopy(saved);changed['recording'][key]=value;self.store.write(changed,saved)
                with self.assertRaises(NativeUIError):self.archive()
                self.store.write(saved,changed)

    def test_new_lease_selects_latest_actual_owned_start(self):
        self.later_start();self.model.complete()
        with self.lease() as owner:
            snapshot=owner.capture();self.assertEqual('6'*32,snapshot['recording']['ticket'])
            self.assertEqual(self.fixture.model.cycle,snapshot['recording']['cycle']);owner.retire()

    def test_malformed_saved_recording_is_unavailable_without_new_native_delivery(self):
        with self.lease() as owner:owner.capture();owner.retire()
        saved=self.store.read();commands=deepcopy(self.model.commands)
        for value in (None,[],{},dict(saved['recording'],extra=True)):
            with self.subTest(value=value):
                changed=dict(saved,recording=value);self.store.write(changed,saved)
                with self.assertRaises(NativeUIError):self.archive()
                self.store.write(saved,changed)
        self.assertEqual(commands,self.model.commands)


if __name__=='__main__':unittest.main()
