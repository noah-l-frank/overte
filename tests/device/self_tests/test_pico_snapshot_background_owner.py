"""OS return/unknown input with explicit native/HTTP/Parent qualification seams.

The immutable fixture is the complete host-model lineage of the separately
passed normal Upload case. It is test data, never current device authority.
These producers generate virtual observations when queried; the OS event model
changes its independent lifecycle source only on actual model consumption.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import pack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_save_originals import SnapshotSaveOriginals
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals
from adapters.pico4.snapshot_upload_owner import PicoSnapshotUploadOwner,sha
from adapters.pico4.snapshot_background_owner import PicoSnapshotBackgroundOwner
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client


def fixture():
    path=Path(__file__).with_name('pico-snapshot-background-fixture.v1.json.gz')
    if hashlib.sha256(path.read_bytes()).hexdigest()!='342ebb8ad0d383692458f703c0afa51e139882beabae7e46ba1938c30290ef9d':raise ValueError('Unknown host fixture bytes')
    with gzip.open(path,'rb') as source:raw=source.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:raise ValueError('Host fixture exceeds its fixed input bound')
    value=json.loads(raw)
    if value['source']!='0166738f3191da44dac21ceb4865375651c690e3' or value['qualification']!='SYNTHETIC_NATIVE_JS_ANDROID_PARENT_DATA_NOT_DEVICE_AUTHORITY':raise ValueError('Unknown host fixture')
    return value['rows']


class Boundary:
    def __init__(self,root):
        self.root=root;rows=fixture();self.run=rows[-1]['header']['runId'];self.binding=rows[-1]['header']['binding'];self.states={};self.headers={}
        self.lock=ScriptSourceLock(root/'script-sources.lock')
        with self.lock.held():
            for row,kind,verb in zip(rows,(SnapshotCancelOriginals,SnapshotSaveOriginals,SnapshotUploadOriginals,SnapshotUploadOriginals),(None,None,'upload-fail','upload')):
                name=row['name'];state=row['state'];header=row['header']
                if name!='snapshot-cancel':state['parentSha256']=sha(self.headers['snapshot-cancel' if name=='snapshot-save' else 'snapshot-save'])
                if name=='snapshot-upload':state['failureSha256']=sha(self.headers['snapshot-upload-fail'])
                originals=kind(root/(name+'-originals.json'),self.run,self.binding,*(() if verb is None else (verb,)))
                header['payload']=pack([originals.encode(state)]);PrivateFeatureState(root/(name+'-owner.json')).write(header,None)
                self.states[name]=state;self.headers[name]=header
        self.origin=self.states['snapshot-upload']['frames'][-1];self.host=self.origin['hostMonotonic']+1
        self.start_host=self.host;self.start_epoch=json.loads(self.origin['account']['raw'])['capturedEpochMs']+1000
        self.foreground=True;self.calls=[];self.queries=0;self.scope_reads=0;self.signal=True;self.lose='';self.ignore=False;self.advance_before_callback=False
        self.lifecycle=deepcopy(json.loads(self.origin['account']['raw'])['lifecycle'])
        phase=deepcopy(self.states['snapshot-upload']['source']);phase['activations'].append(dict(sequence=len(phase['activations'])+1,ticket=uuid.uuid4().hex,
            activatedEpochMs=self.epoch(),stimulus=dict(verb='background-resume',inputs={})))
        self.phase=phase;self.phase_sequence=phase['sequence'];self.source=PhaseFixtureReader(Client(self.headers['snapshot-upload']['fixtureUrl'].removesuffix('/runs/'+self.run+'/'),'f'*64),
            self.run,'snapshots',monotonic=lambda:self.host,epoch_ms=self.epoch);self.source.status=self.status_phase
        # The typed live Parent is deliberately a qualification/native seam.
        # Its real full normal input/TLS lineage was tested separately.
        self.parent=object.__new__(PicoSnapshotUploadOwner);self.parent.run=self.run;self.parent.binding=self.binding;self.parent.lock=self.lock
        self.parent.store=PrivateFeatureState(root/'snapshot-upload-owner.json');self.parent.read_frame=self.frame
        self.parent.native=SimpleNamespace(guard=self.native_guard,clock_ms=self.epoch)

    def epoch(self):return self.start_epoch+round((self.host-self.start_host)*1000)
    def sleep(self,amount):self.host+=amount
    def status_phase(self,previous=None):
        self.phase_sequence+=1;value=deepcopy(self.phase);value.update(sequence=self.phase_sequence,requestId=uuid.uuid4().hex,capturedEpochMs=self.epoch());return value
    def native_guard(self):
        if not self.foreground:raise AssertionError('Native/Qt query during background')
        return True
    def runtime(self):
        self.scope_reads+=1;self.native_guard();return self.parent
    def os_status(self,binding):return dict(binding=deepcopy(binding),running=True,foreground=self.foreground)
    def os_input(self,operation,binding,*,before_input):
        if self.advance_before_callback:
            self.phase['activations'].append(dict(sequence=len(self.phase['activations'])+1,ticket=uuid.uuid4().hex,activatedEpochMs=self.epoch(),stimulus=dict(verb='close',inputs={})))
        before_input();self.calls.append(operation)
        if not self.ignore:
            self.foreground=operation=='app.launch'
            if self.signal:self.lifecycle['activations' if self.foreground else 'backgrounds']+=1
        if self.lose==operation:self.lose='';raise OSError('Explicit lost model OS return after consumption')

    def frame(self):
        self.native_guard();self.queries+=1;result=deepcopy(self.origin);epoch=self.epoch();result['hostMonotonic']=self.host;base=result['base'];base['hostMonotonic']=self.host
        def original(part,*,request_key):
            value=json.loads(part['raw']);value[request_key]=uuid.uuid4().hex;value['sequence']+=self.queries;value['capturedEpochMs']=epoch
            if 'requestedEpochMs' in value:value['requestedEpochMs']=epoch
            return value
        def encode(part,value):part.update(raw=json.dumps(value));part['sha256']=hashlib.sha256(part['raw'].encode()).hexdigest()
        for kind in ('native','script','files'):
            part=base[kind];value=original(part,request_key='requestId' if kind=='files' else 'commandId')
            if kind=='script':value['captureContext']['capturedEpochMs']=epoch
            if kind=='files':value['source'].update(capturedEpochMs=epoch,sequence=value['source']['sequence']+self.queries);part['request']['commandId']=value['requestId']
            encode(part,value)
        work=base['work'];work.update(requestId=uuid.uuid4().hex,capturedEpochMs=epoch,requestedEpochMs=epoch,sequence=work['sequence']+self.queries)
        work['source']['work'].update(requestId=work['requestId'],capturedEpochMs=epoch,requestedEpochMs=epoch,sequence=work['source']['work']['sequence']+self.queries)
        base['inventory']['capturedEpochMs']=epoch;base['ui']['updatedEpochMs']=epoch
        part=result['upload'];value=original(part,request_key='requestId');value['source']['capturedEpochMs']=epoch;part['request']['commandId']=value['requestId'];encode(part,value)
        part=result['account'];value=original(part,request_key='requestId');value['account']['observation']['capturedEpochMs']=epoch;value['lifecycle']=deepcopy(self.lifecycle);encode(part,value)
        provider=result['provider'];provider.update(capturedEpochMs=epoch,requestId=uuid.uuid4().hex,ticket=self.phase['activations'][-1]['ticket'])
        provider['activations']=[dict(ticket=row['ticket'],verb=row['stimulus']['verb'],capturedEpochMs=row['activatedEpochMs']) for row in self.phase['activations']]
        return result

    def owner(self):
        return PicoSnapshotBackgroundOwner(self.root/'snapshot-background-owner.json',self.run,self.binding,self.lock,self.source,self.os_status,self.os_input,self.runtime,
            monotonic=lambda:self.host,sleep=self.sleep)


class SnapshotBackgroundCase(unittest.TestCase):
    def fixture(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-bg-host-');self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700);return Boundary(root)



class SnapshotBackgroundOwnerTests(SnapshotBackgroundCase):
    def test_normal_home_os_checkpoint_return_original_lifecycle_quiet_and_cold_read_only(self):
        b=self.fixture();owner=b.owner();owner.prepare();owner.home();queries=b.queries;scope=b.scope_reads
        cold=b.owner();self.assertEqual('background-observed',cold.report()['stage']);self.assertEqual((queries,scope),(b.queries,b.scope_reads))
        cold.resume();report=cold.quiet();self.assertEqual('partial-ready',report['stage']);self.assertTrue(report['quietCompleted']);self.assertFalse(report['fullSnapshotRecipe'])
        self.assertFalse(report['independentAfterReturnPng']);self.assertEqual(['lifecycle.background','app.launch'],b.calls)
        queries=b.queries;b.owner();self.assertEqual(queries,b.queries)
        with self.assertRaises(NativeUIError):cold.resume()

    def test_lost_home_and_resume_returns_recover_only_by_observing_original_sources(self):
        b=self.fixture();owner=b.owner();owner.prepare();b.lose='lifecycle.background'
        with self.assertRaises(NativeUIError):owner.home()
        cold=b.owner();cold.background();b.lose='app.launch'
        with self.assertRaises(NativeUIError):cold.resume()
        another=b.owner();self.assertEqual('returned',another.reconcile()['stage']);self.assertEqual(['lifecycle.background','app.launch'],b.calls)



class SnapshotBackgroundFenceTests(SnapshotBackgroundCase):

    def test_os_ack_without_consumption_cannot_create_background_or_allow_resume(self):
        b=self.fixture();owner=b.owner();owner.prepare();b.ignore=True
        with self.assertRaises(NativeUIError):owner.home()
        self.assertEqual('home-issued',b.owner().report()['stage']);self.assertEqual(['lifecycle.background'],b.calls)
        with self.assertRaises(NativeUIError):owner.resume()

    def test_returned_foreground_without_independent_native_lifecycle_transition_is_not_returned(self):
        b=self.fixture();owner=b.owner();owner.prepare();b.signal=False;owner.home()
        with self.assertRaises(NativeUIError):owner.resume()
        self.assertEqual('resume-issued',b.owner().report()['stage']);self.assertTrue(owner.store.path.exists())

    def test_phase_advance_after_durable_home_intent_refuses_the_actual_os_dispatch(self):
        b=self.fixture();owner=b.owner();owner.prepare();b.advance_before_callback=True
        with self.assertRaises(NativeUIError):owner.home()
        self.assertEqual([],b.calls);self.assertEqual('home-issued',b.owner().report()['stage'])

    def test_frozen_source_clock_cannot_hide_slow_home_intent_cas(self):
        b=self.fixture();owner=b.owner();owner.prepare();epoch=b.epoch();b.source.epoch_ms=lambda:epoch
        save=owner.save
        def slow(state):
            save(state)
            if state['stage']=='home-issued':b.host+=2
        with patch.object(owner,'save',side_effect=slow),self.assertRaises(NativeUIError):owner.home()
        self.assertEqual([],b.calls);self.assertEqual('home-issued',b.owner().report()['stage'])

    def test_last_native_guard_phase_advance_is_read_before_actual_home_dispatch(self):
        b=self.fixture();owner=b.owner();owner.prepare();guard=b.parent.native.guard
        def changed():
            if owner.state['stage']=='home-issued':
                b.phase['activations'].append(dict(sequence=len(b.phase['activations'])+1,ticket=uuid.uuid4().hex,activatedEpochMs=b.epoch(),stimulus=dict(verb='close',inputs={})))
            return guard()
        with patch.object(b.parent.native,'guard',side_effect=changed),self.assertRaises(NativeUIError):owner.home()
        self.assertEqual([],b.calls);self.assertEqual('home-issued',b.owner().report()['stage'])

    def test_parent_original_chunk_tamper_refuses_cold_owner_before_any_live_source(self):
        b=self.fixture();owner=b.owner();owner.prepare();owner.home();queries=b.queries
        path=next(b.root.glob('snapshot-upload-originals.json.frame-*'));chunk=json.loads(path.read_bytes());chunk['scopeSha256']='f'*64;path.write_text(json.dumps(chunk))
        with patch.object(b,'runtime',side_effect=AssertionError('Cold BG must not acquire Qt')),self.assertRaises(NativeUIError):b.owner()
        self.assertEqual(queries,b.queries);self.assertEqual(['lifecycle.background'],b.calls)

    def test_changed_parent_header_or_original_python_type_refuses_before_os_source(self):
        b=self.fixture();owner=b.owner()
        with b.lock.held(),patch.object(b,'os_status',side_effect=AssertionError('Admission must fail before SDK')):
            owner.parent_disk['fixtureUrl']='https://foreign.invalid/'
            with self.assertRaises(NativeUIError):owner.bound()
            owner.parent_disk=deepcopy(b.headers['snapshot-upload'])
            class Text(str):pass
            owner.parent['stage']=Text(owner.parent['stage'])
            with self.assertRaises(NativeUIError):owner.bound()
        self.assertEqual([],b.calls);self.assertEqual(0,b.queries)

    def test_cold_validation_rejects_noncontiguous_quiet_and_missing_os_checkpoint(self):
        b=self.fixture();owner=b.owner();owner.prepare();owner.home();owner.resume();owner.quiet()
        with b.lock.held():
            state=deepcopy(owner.state);state['quiet'][0]['indices'].pop(1)
            with self.assertRaises(NativeUIError):owner.validate(state)
            state=deepcopy(owner.state);state['os']=state['os'][:1]
            with self.assertRaises(NativeUIError):owner.validate(state)
        self.assertTrue(owner.store.path.exists());self.assertEqual(['lifecycle.background','app.launch'],b.calls)


class SnapshotBaseFrameExtractionTests(unittest.TestCase):
    def test_unchanged_original_parser_accepts_every_retained_parent_frame(self):
        from adapters.pico4.snapshot_base_frame import validate
        rows=fixture();run=rows[-1]['header']['runId'];binding=rows[-1]['header']['binding'];count=0
        for row in rows:
            for frame in row['state']['frames']:
                validate(frame.get('base',frame),run,123,binding['sessionId']);count+=1
        self.assertGreater(count,50)


if __name__=='__main__':unittest.main()
