"""Real host persistence bytes and modeled native service/clocks, no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters.location_bookmarks import IOSLocationBookmarks,command,validate,saved,original_bytes,string_entries
from ios.adapters import feature_observation
from ios.self_tests.test_ios_feature_observation import Native
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Boundary:
    def __init__(self,path):
        self.path=path;self.clock=10.;self.sequence=0;self.requests=[];self.loaded={};self.load_error=False
        self.live=True;self.ignore=False;self.mutate=None;self.last=None
    def epoch(self):return 1700000000000+86400000+round(self.clock*1000)
    def native_clock(self):self.clock+=.001;return self.epoch()
    def clocks(self):return dict(epochMs=self.epoch(),monotonicMs=round(self.clock*1000))
    def sleep(self,seconds):self.clock+=seconds
    def send(self,query):self.requests.append(deepcopy(query))
    def original(self):
        if self.ignore:return ''
        self.clock+=.001;before=self.clocks();self.sequence+=1
        file=dict(source='app-local-data/bookmarks.json',status='absent',reason='',bytes=None,sha256=None,contentBase64=None,identity=None)
        if self.path.exists():
            raw=self.path.read_bytes();info=self.path.stat()
            file.update(status='ready',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                contentBase64=base64.b64encode(raw).decode(),identity=dict(device=str(info.st_dev),inode=str(info.st_ino)))
        self.clock+=.001
        value=dict(iosLocationBookmarksVersion=1,requestId=self.requests[-1]['commandId'],runId=RUN,instance='c'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-bookmarks',clockBefore=before,clockAfter=self.clocks(),
            loaded=dict(source='LocationBookmarks.getBookmarks',entries=deepcopy(self.loaded),loadError=self.load_error),file=file)
        if self.mutate:self.mutate(value)
        self.last=deepcopy(value);return json.dumps(value)
    def reader(self):return IOSLocationBookmarks(self.send,self.original,self.native_clock,lambda:self.live,42,
        monotonic=lambda:self.clock,sleep=self.sleep)


class LocationBookmarksTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'bookmarks.json';self.source=Boundary(self.path)
    def write(self,value):self.path.write_text(json.dumps(value))

    def transport(self):
        native=Native();clock=ClockBoundary();source=self.source
        native.clock=source.clock
        observer=native.observer();observer.monotonic=lambda:source.clock;observer.sleep=source.sleep
        # Deliberately foreign host UTC: only original native timestamps qualify.
        observer.epoch_ms=lambda:9000
        def stamp(value):
            source.native_clock();epoch=source.epoch()
            value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data))
            native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            if query['action']=='feature-native-observe':clock.send(query)
            else:source.send(query)
            return native
        def execute(session,operation,values):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            path=values['remotePath'];native.reads.append(path)
            prefix='@org.example.client:documents/owned-results/'
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+'feature-ios-location-bookmarks.json'))
            raw=clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(raw.encode()).decode()
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),
                         patch.object(native,'execute',side_effect=execute)):
            boundary.start();self.addCleanup(boundary.stop)
        return native,observer

    def test_actual_http_afc_factory_reads_separate_native_clock_and_fixed_bookmark_original(self):
        self.write({'saved':'hifi://saved'});self.source.loaded={'loaded':'hifi://loaded'}
        native,observer=self.transport();reader=observer.location_bookmarks();value=reader.read(RUN)
        self.assertEqual(self.source.last,value)
        self.assertEqual({'saved':'hifi://saved'},saved(value['file'])['entries'])
        self.assertEqual(3,len(native.commands))
        self.assertEqual(['feature-native-observe','feature-ios-location-bookmarks','feature-native-observe'],
                         [row['action'] for row in native.commands])
        self.assertEqual(3,len({row['commandId'] for row in native.commands}))
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],value['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],value['clockAfter']['epochMs'])
        self.assertEqual(3,len(native.reads))

    def test_process_replacement_after_query_prevents_any_bookmark_afc_acceptance(self):
        native,observer=self.transport();original=self.source.send
        def send(query):original(query);native.pid=43
        self.source.send=send
        with self.assertRaises(NativeUIError):observer.location_bookmarks().read(RUN)
        self.assertEqual(2,len(native.commands))
        self.assertFalse(any(path.endswith('/feature-ios-location-bookmarks.json') for path in native.reads))
        self.assertEqual(1,len(self.source.requests))

    def test_loaded_and_persisted_originals_keep_distinct_bytes_and_native_clocks(self):
        self.write({'original':'hifi://original'});self.source.loaded={'original':'hifi://original'}
        reader=self.source.reader();first=reader.read(RUN)
        self.assertEqual(self.path.read_bytes(),original_bytes(first['file']))
        self.assertEqual(self.source.loaded,saved(first['file'])['entries']);self.assertEqual(first,self.source.last)
        self.assertNotEqual(round(self.path.stat().st_mtime*1000),first['clockAfter']['epochMs'])
        self.assertEqual(self.source.requests[0]['commandId'],first['requestId'])
        second=reader.read(RUN);self.assertGreater(second['sequence'],first['sequence'])
        self.assertEqual(first['file'],second['file']);self.assertEqual(2,len(self.source.requests))

    def test_ignored_persistence_cannot_borrow_loaded_or_requested_values(self):
        self.write({'original':'hifi://original'});self.source.loaded={'new':'hifi://new'}
        value=self.source.reader().read(RUN)
        self.assertEqual({'new':'hifi://new'},value['loaded']['entries'])
        self.assertEqual({'original':'hifi://original'},saved(value['file'])['entries'])

    def test_absent_empty_invalid_duplicate_and_unavailable_are_distinct_originals(self):
        reader=self.source.reader();self.assertEqual(dict(status='absent',entries=None),saved(reader.read(RUN)['file']))
        self.path.write_bytes(b'{}');self.assertEqual(dict(status='ready',entries={}),saved(reader.read(RUN)['file']))
        for raw in (b'',b'[]',b'{broken',b'{"x":"first","x":"second"}',b'{"x":NaN}'):
            self.path.write_bytes(raw);value=reader.read(RUN)
            self.assertEqual(raw,original_bytes(value['file']));self.assertEqual('invalid-json',saved(value['file'])['status'])
        value['file']=dict(source='app-local-data/bookmarks.json',status='unavailable',reason='unsafe-file',
            bytes=None,sha256=None,contentBase64=None,identity=None)
        self.assertEqual(dict(status='unavailable',entries=None),saved(value['file']))

    def test_boolean_versions_foreign_nonce_pid_run_domain_and_bad_hash_fail_without_resend(self):
        self.write({})
        mutations=(lambda v:v.update(iosLocationBookmarksVersion=True),lambda v:v.update(processId=43),
            lambda v:v.update(runId='b'*32),lambda v:v.update(requestId='ios-'+'b'*32),
            lambda v:v.update(clockDomain='controller-host'),lambda v:v['file'].update(sha256='f'*64),
            lambda v:v['file'].update(identity=dict(device='01',inode='42')))
        for mutate in mutations:
            source=Boundary(self.path);source.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_native_before_floor_stale_or_slow_clocks_do_not_get_retimed(self):
        for mutate in (lambda v:v['clockBefore'].update(epochMs=v['clockBefore']['epochMs']-100),
                       lambda v:v['clockAfter'].update(epochMs=v['clockAfter']['epochMs']-10000),
                       lambda v:v['clockAfter'].update(monotonicMs=v['clockBefore']['monotonicMs']+2000)):
            source=Boundary(self.path);source.mutate=mutate
            with self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_reused_sequence_or_changed_source_birth_cannot_extend_history(self):
        for mutate in (lambda v:v.update(sequence=1),lambda v:v.update(instance='d'*32)):
            source=Boundary(self.path);reader=source.reader();first=reader.read(RUN);source.mutate=mutate
            with self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last);self.assertEqual(2,len(source.requests))

    def test_missing_hook_cannot_become_an_empty_success_and_passive_read_is_one_send(self):
        self.source.ignore=True
        with self.assertRaises(NativeUIError):self.source.reader().read(RUN)
        self.assertEqual(1,len(self.source.requests));self.assertLess(self.source.clock,12)

    def test_non_string_user_data_and_load_error_are_not_normalized_away(self):
        self.write({'unsupported':7});self.source.loaded={'unsupported':7};self.source.load_error=True
        value=self.source.reader().read(RUN)
        self.assertTrue(value['loaded']['loadError']);self.assertEqual(7,saved(value['file'])['entries']['unsupported'])
        with self.assertRaises(NativeUIError):string_entries(value['loaded']['entries'])

    def test_historical_original_validation_needs_no_clock_or_native_factory(self):
        value=self.source.reader().read(RUN);query=self.source.requests[-1]
        self.source.clock+=100000
        self.assertIs(value,validate(value,query,42));self.assertEqual('absent',saved(value['file'])['status'])
        with self.assertRaises(NativeUIError):validate(value,query,42,self.source.epoch())

    def test_private_fixture_only_accepts_the_closed_observation_command(self):
        query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action='feature-ios-location-bookmarks',runId=RUN)
        state=FixtureState();state.set_client_command(query)
        for update in (dict(expected=True),dict(path='/private/user-data'),dict(schemaVersion=True),dict(commandId='e'*32)):
            with self.assertRaises((RuntimeError,ValueError)):command(query|update)
            with self.assertRaises(ValueError):state.set_client_command(query|update)

    def test_probe_uses_original_native_hook_and_does_not_reissue_same_request(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureIOSLocationBookmarks:c=>{calls++;return {requestId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-location-bookmarks',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||!files[0].v.original||files[0].name!=='feature-ios-location-bookmarks.json')throw Error('original source missing/reissued');
for(const update of [{expected:true},{path:'/private/foreign'},{schemaVersion:true},{commandId:c.commandId+'\n'}])applyClientCommand({...c,...update});
if(calls!==1)throw Error('unsafe command admitted');
delete Test.featureIOSLocationBookmarks;
applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing source became empty success');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
