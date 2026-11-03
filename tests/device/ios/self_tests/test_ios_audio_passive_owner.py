"""Real host WAL/original files with explicit modeled native microphone transport.

No native library, SDK, microphone, hardware/acoustic proof or compiler runs.
The modeled raw waveform never counts as an independent acoustic observation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch
import base64,hashlib,io,json,unittest,wave
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.audio_passive_owner import IOSAudioPassiveOwner
from ios.adapters.audio_passive_capture_source import KINDS,PROFILE
from ios.self_tests.test_ios_audio_pcm_lease import PCMModel
from ios.self_tests.test_ios_audio_recorded_owner import AudioRecordedOwnerTests,BINDING,RUN


def raw(value):return json.dumps(value,separators=(',',':'),allow_nan=False).encode()
def sha(value):return hashlib.sha256(value).hexdigest()


class PassiveBoundary:
    """Producer-only model; no replacement of a consumer/result validator."""
    def __init__(self,clock,lease='4'*32):
        self.lease=lease;self.clock=clock;self.commands=[];self.files={};self.rows=[];self.packet=None;self.sequence=0
        self.owned=False;self.watchdog=False;self.complete=False;self.retired=False;self.start=None;self.capture=None
        self.release_attempted=False;self.lose=set();self.ignore_release=False;self.keep_file=False;self.keep_watchdog=False
        self.block=False;self.change_inode=False
    def descriptor(self,kind):
        if kind not in self.files:return dict(kind=kind,exists=False)
        data=self.files[kind]
        return dict(kind=kind,exists=True,complete=True,bytes=len(data),sha256=sha(data),device='7',inode=str(100+KINDS.index(kind)+(50 if self.change_inode else 0)))
    def state(self,full=False):
        m=self.clock;size=len(self.pcm) if self.owned and self.complete else 0
        value=dict(passiveAcousticVersion=1,profile=PROFILE,owned=self.owned,
            runId=RUN if self.owned else '',role='actor' if self.owned else '',leaseId=self.lease if self.owned else '',
            instance=m.native_instance if self.owned else '',admissionEpoch=1 if self.owned else 0,captureGeneration=1 if self.start else 0,
            inputGeneration=1 if self.owned else 0,inputRouteRevision='1' if self.owned else '0',
            startedEpochMs=self.started if self.owned else 0,startedMonotonicMs=self.started_mono if self.owned else 0,
            active=self.owned and not self.complete,complete=self.owned and self.complete,invalid=False,
            sampleRate=8000 if self.owned else 0,channels=1 if self.owned else 0,bytes=size,coveredBytes=size,
            targetBytes=self.seconds*16000 if self.owned else 0,inputCallbacks=len(self.rows) if self.owned else 0,
            watchdogOwned=self.watchdog,watchdogActive=self.watchdog and not self.complete,
            physicalADCQualified=False,acousticQualified=False,peerQualified=False)
        rows=self.rows if self.owned else []
        if full:value['rows']=deepcopy(rows)
        else:value.update(originRows=len(rows),originRowsSha256=sha(raw(rows)))
        return value
    def finish(self):
        m=self.clock;m.sleep(self.seconds);self.complete=True;self.pcm=b'\x01\x00'*(self.seconds*8000)
        self.rows=[dict(sequence=1,generation=1,routeRevision='1',readBeforeEpochMs=self.started,readAfterEpochMs=m.native_epoch(),
            readBeforeMonotonicMs=self.started_mono,readAfterMonotonicMs=round(m.clock*1000),tapEpochMs=m.native_epoch(),
            tapMonotonicMs=round(m.clock*1000),readBytes=len(self.pcm),readSha256=sha(self.pcm),offset=0,bytes=len(self.pcm),sha256=sha(self.pcm))]
    def send(self,query):
        if self.block:raise AssertionError('Pure original reconstruction performed a native send')
        self.commands.append(deepcopy(query));m=self.clock;m.tick();epoch=m.native_epoch();verb=query['operation']
        if self.start is not None:need(query['startCommandId']==self.start['commandId'])
        if verb=='start':
            need(self.start is None and not self.retired);self.start=deepcopy(query);self.seconds=query['seconds'];self.owned=self.watchdog=True
            self.started=epoch;self.started_mono=round(m.clock*1000)
            self.files['intent']=raw(dict(passiveAcousticIntentVersion=1,instance=m.native_instance,runId=RUN,leaseId=self.lease,
                role='actor',processId=42,issuedEpochMs=epoch,command=query))
        if verb=='capture':
            need(self.complete and self.capture is None);self.capture=deepcopy(query);buffer=io.BytesIO()
            with wave.open(buffer,'wb') as output:output.setnchannels(1);output.setsampwidth(2);output.setframerate(8000);output.writeframes(self.pcm)
            self.files['wav']=buffer.getvalue()
            self.files['capture']=raw(dict(passiveAcousticOriginalVersion=1,instance=m.native_instance,runId=RUN,role='actor',leaseId=self.lease,
                processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch,captureCommand=query,source=self.state(full=True),wav=self.descriptor('wav')))
        if verb=='release':
            need(not self.release_attempted);self.release_attempted=True
            if not self.ignore_release:
                self.owned=False
                if not self.keep_watchdog:self.watchdog=False
                if not self.keep_file:self.files={}
                self.retired=not self.files and not self.watchdog
        if verb=='recover':need(self.release_attempted)
        if verb=='read':
            data=self.files[query['kind']][query['offset']:query['offset']+query['bytes']]
            source=dict(kind=query['kind'],offset=query['offset'],bytes=len(data),base64=base64.b64encode(data).decode(),sha256=sha(data),
                original=self.descriptor(query['kind']),originalOnly=True)
        else:source=dict(state=self.state(),files=[self.descriptor(kind) for kind in KINDS],retired=self.retired,
            startAttempted=self.start is not None,captureAttempted=self.capture is not None,releaseAttempted=self.release_attempted,
            openOriginalFds=len(self.files),originalBytes=sum(len(data) for data in self.files.values()))
        self.sequence+=1;self.packet=dict(passiveAcousticReplyVersion=1,commandId=query['commandId'],instance=m.native_instance,
            sequence=self.sequence,processId=42,runId=RUN,role='actor',leaseId=self.lease,operation=verb,
            requestedEpochMs=epoch,capturedEpochMs=epoch,source=source)
        if verb in self.lose:raise NativeUIError('Declared lost return after native model delivery')
    def read(self):
        if self.block:raise AssertionError('Pure original reconstruction read native transport')
        return raw(self.packet).decode() if self.packet else None
    def count(self,verb):return sum(query['operation']==verb for query in self.commands)


class AudioPassiveOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioRecordedOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.m=self.f.model;self.root=self.f.root/'passive';self.root.mkdir(mode=0o700)
        self.store=PrivateFeatureState(self.root/'ios-audio-passive-owner.json');self.boundary=PassiveBoundary(self.m)
    @contextmanager
    def owner(self):
        m=self.m;native,_unused=PCMModel(m).reader()
        with self.f.lock.held():
            yield IOSAudioPassiveOwner(self.store,self.root,BINDING,RUN,'4'*32,self.f.lock,m.guard,native=native,
                transport=dict(send=self.boundary.send,read=self.boundary.read),
                phase=PhaseFixtureReader(m.client(),RUN,'audio',epoch_ms=m.epoch,monotonic=lambda:m.clock),
                epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
    def begin(self):
        with self.owner() as owner:owner.start(6)
        self.boundary.finish()
    def test_actual_host_originals_and_original_creator_survive_pure_archive_without_native_getters(self):
        self.begin()
        with self.owner() as owner:
            value=owner.capture();self.assertEqual(96044,len(value['wav']));self.assertIsNotNone(owner.state['birth'])
            self.assertFalse(owner.retire()['nativeQualified'])
        before={p:(p.stat().st_ino,p.read_bytes()) for p in self.root.iterdir()};commands=deepcopy(self.boundary.commands)
        self.boundary.block=True
        with self.f.lock.held():
            archive=IOSAudioPassiveOwner.archive(self.store,self.root,BINDING,RUN,'4'*32,self.f.lock,m_fixture_url(self.m))
            self.assertTrue(archive.retired()['retired']);self.assertEqual(value['wav'],archive.snapshot()['wav'])
        self.assertEqual(commands,self.boundary.commands);self.assertEqual(before,{p:(p.stat().st_ino,p.read_bytes()) for p in self.root.iterdir()})
    def test_lost_start_observes_original_creator_without_second_allocation(self):
        self.boundary.lose.add('start')
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.start(6)
        self.boundary.lose.clear()
        with self.owner() as owner:self.assertIsNotNone(owner.start(6)['birth']);owner.retire()
        self.assertEqual(1,self.boundary.count('start'));self.assertEqual(1,self.boundary.count('release'))
    def test_lost_capture_return_reads_original_files_without_second_capture(self):
        self.begin();self.boundary.lose.add('capture')
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.capture()
        self.boundary.lose.clear()
        with self.owner() as owner:self.assertEqual(96044,len(owner.capture()['wav']));owner.retire()
        self.assertEqual(1,self.boundary.count('capture'))
    def test_lost_release_return_recovers_without_second_release_and_requires_distinct_absence(self):
        self.begin();self.boundary.lose.add('release')
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.boundary.lose.clear()
        with self.owner() as owner:self.assertTrue(owner.retire()['retired'])
        self.assertEqual(1,self.boundary.count('release'));self.assertEqual(1,self.boundary.count('recover'))
        self.assertGreaterEqual(self.boundary.count('files'),1)
    def test_ignored_release_ack_cannot_hide_live_capture_memory_or_watchdog(self):
        self.begin();self.boundary.ignore_release=True
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual(1,self.boundary.count('release'));self.assertTrue(self.boundary.owned)
    def test_native_file_left_after_memory_release_blocks_absence_without_second_release(self):
        self.begin();self.boundary.keep_file=True
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertFalse(self.boundary.owned);self.assertTrue(self.boundary.files)
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual(1,self.boundary.count('release'))
    def test_separate_watchdog_left_after_memory_and_file_release_blocks_retirement(self):
        self.begin();self.boundary.keep_watchdog=True
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertFalse(self.boundary.owned);self.assertFalse(self.boundary.files);self.assertTrue(self.boundary.watchdog)
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual(1,self.boundary.count('release'))
    def lost_saved_proof(self,kind):
        original=OriginalFrameStore.write;saved={}
        def lost(store,index,envelope):
            reference=original(store,index,envelope)
            if store.namespace=='ios-audio-passive-proofs' and envelope['value']['kind']==kind:
                path=store.path(store.expand(reference));saved.update(path=path,inode=path.stat().st_ino,body=path.read_bytes())
                raise OSError('Declared lost return after saved original proof')
            return reference
        return patch.object(OriginalFrameStore,'write',lost),saved
    def test_saved_birth_original_recovers_exact_inode_and_creator_without_second_start(self):
        fault,saved=self.lost_saved_proof('birth')
        with fault,self.owner() as owner,self.assertRaises(OSError):owner.start(6)
        intent_reads=sum(query['operation']=='read' and query['kind']=='intent' for query in self.boundary.commands)
        with self.owner() as owner:
            value=owner.start(6);self.assertIsNotNone(value['birth']);self.assertIsNone(owner.state['pending']);owner.retire()
        self.assertEqual(1,self.boundary.count('start'))
        self.assertEqual(intent_reads,sum(query['operation']=='read' and query['kind']=='intent' for query in self.boundary.commands))
        self.assertEqual(saved['inode'],saved['path'].stat().st_ino);self.assertEqual(saved['body'],saved['path'].read_bytes())
    def test_saved_snapshot_original_recovers_pointer_without_new_capture_or_chunk_reads(self):
        self.begin();fault,saved=self.lost_saved_proof('snapshot')
        with fault,self.owner() as owner,self.assertRaises(OSError):owner.capture()
        reads=self.boundary.count('read');captures=self.boundary.count('capture')
        with self.owner() as owner:
            self.assertEqual(96044,len(owner.capture()['wav']));self.assertIsNone(owner.state['pending']);owner.retire()
        self.assertEqual(reads,self.boundary.count('read'));self.assertEqual(captures,self.boundary.count('capture'))
        self.assertEqual(saved['inode'],saved['path'].stat().st_ino);self.assertEqual(saved['body'],saved['path'].read_bytes())
    def test_same_body_replacement_descriptor_cannot_become_original_selected_file(self):
        self.begin()
        with self.owner() as owner:
            original=self.boundary.send
            def changed(query):
                if query['operation']=='read':self.boundary.change_inode=True
                return original(query)
            self.boundary.send=changed;owner.transport['send']=changed
            with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(1,self.boundary.count('capture'));self.assertTrue(self.boundary.files)


def m_fixture_url(model):return model.client().url+'/runs/'+RUN+'/'
if __name__=='__main__':unittest.main()
