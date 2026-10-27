"""Actual probe dispatch and existing bound HTTP/AFC; native Qt is a model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import subprocess
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation, chat_qml_sources as source
from ios.self_tests.chat_qml_source_fixture import Boundary, RUN, URL
import ios.self_tests.test_ios_keyboard_runtime as keyboard_fixture
from self_tests.test_native_feature_observation import probe_source


class ChatQmlSourceProbeTests(unittest.TestCase):
    def test_actual_probe_publishes_original_once_even_when_native_or_save_return_is_lost(self):
        boundary = Boundary()
        query = dict(schemaVersion=1, commandId='ios-' + 'a' * 32, action=source.ACTION, runId=RUN)
        boundary.send(query)
        self.assertEqual(query, FixtureState().set_client_command(query))
        for extra in (dict(sourceUrl=URL), dict(sha256='0' * 64), dict(objectId='a' * 32), dict(profile='cache')):
            with self.subTest(extra=extra), self.assertRaises(ValueError): FixtureState().set_client_command(dict(query, **extra))
        program = '''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSChatQmlSources:q=>{calls++;return {...original,requestId:q.commandId}},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-chat-qml-sources.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("original replaced/replayed");
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),sourceUrl:"wanted"});if(calls!==1)throw Error("requested source accepted");
delete Test.featureIOSChatQmlSources;applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
if(files.at(-1).v.status!=="unavailable"||files.at(-1).v.source)throw Error("missing SDK became source");
Test.featureIOSChatQmlSources=()=>{calls++;throw Error("declared native failure")};
const unknown={...q,commandId:"ios-"+"d".repeat(32)};applyClientCommand(unknown);applyClientCommand(unknown);
if(calls!==2||files.length!==3)throw Error("unknown source read replayed");
Test.featureIOSChatQmlSources=q=>{calls++;return {...original,requestId:q.commandId}};
Test.saveObject=(v,f)=>{files.push({v,f});throw Error("declared lost save return")};
const lost={...q,commandId:"ios-"+"e".repeat(32)};try{applyClientCommand(lost)}catch(e){}applyClientCommand(lost);
if(calls!==3||files.length!==4)throw Error("uncertain save replayed native read");
'''.replace('PACKET', boundary.raw).replace('QUERY', json.dumps(query)).replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-'], input=program, capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)


class ChatQmlSourceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k = keyboard_fixture.KeyboardRuntimeTests(); self.k.setUp(); self.addCleanup(self.k.doCleanups)
        self.f, self.boundary, self.afc, self.lose_return = self.k.f, Boundary(), [], False
        def clock(value):
            self.k.b.time = self.boundary.time; self.k.native_clock(value)
        self.f.clock.mutate = clock
        def post(request, timeout):
            query = json.loads(request.data)
            if query['action'] != source.ACTION: return self.k.post(request, timeout)
            FixtureState().set_client_command(query); self.boundary.send(query)
            if self.lose_return: raise OSError('Declared lost original source command return')
            raw = json.dumps(query).encode()
            class Response:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self, limit): return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation, 'post_request', side_effect=post))
        execute = self.k.client.execute
        def read(session, operation, values):
            if operation == 'mobile: pullFile' and values['remotePath'].endswith('/' + source.FILE):
                self.afc.append(values['remotePath']); return base64.b64encode(self.boundary.raw.encode()).decode()
            return execute(session, operation, values)
        self.k.client.execute = read
        self.sources = self.k.fixture.runtime._sources('test-only')

    def reader(self): return self.sources['observer'].chat_qml_sources(clock_source=self.sources['clock_source'])

    def test_existing_bound_session_reads_unchanged_source_and_original_native_clock(self):
        before = self.f.sessions, self.f.launches
        reader = self.reader(); value = reader.read(RUN)
        source.admit_direct_unit(value, URL)
        self.assertEqual(before, (self.f.sessions, self.f.launches))
        self.assertEqual((1, 1), (len(self.boundary.queries), len(self.afc)))
        self.assertEqual(1, reader.acquisition['iosChatQmlSourcesAcquisitionVersion'])
        self.assertLess(value['source']['loadCompleted']['epochMs'], reader.acquisition['nativeRequestedEpochMs'])
        self.assertEqual(self.boundary.value['source'], value['source'])

    def test_changed_candidate_or_process_refuses_before_query_and_afc(self):
        for update in (dict(pid=43), dict(foreground=False)):
            before = deepcopy(self.f.process); reader = self.reader(); self.f.process.update(update)
            with self.subTest(update=update), self.assertRaises(NativeUIError): reader.read(RUN)
            self.f.process = before
        reader = self.reader(); self.f.artifact.write_bytes(b'Foreign installed candidate archive')
        with self.assertRaises(NativeUIError): reader.read(RUN)
        self.assertEqual([], self.afc); self.assertEqual([], self.boundary.queries)

    def test_unavailable_or_foreign_original_cannot_admit_a_load_or_reissue_read(self):
        def unavailable(value):
            request = value['requestId']; value.clear()
            value.update(iosChatQmlSourcesVersion=1, requestId=request, status='unavailable')
        for mutate in (unavailable, lambda value: value.update(processId=43),
                lambda value: value['source']['compilerInput'].update(unitSha256='0' * 64)):
            self.boundary.mutate = mutate; reader = self.reader(); before = len(self.boundary.queries)
            with self.assertRaises(NativeUIError): reader.read(RUN)
            self.assertEqual(before + 1, len(self.boundary.queries))
            self.assertIsNone(reader.last); self.assertIsNone(reader.acquisition)

    def test_lost_http_return_preserves_unknown_read_without_afc_or_resubmission(self):
        self.lose_return = True; reader = self.reader()
        with self.assertRaises(NativeUIError): reader.read(RUN)
        self.assertEqual((1, 0), (len(self.boundary.queries), len(self.afc)))
        self.assertIsNone(reader.last); self.assertIsNone(reader.acquisition)

    def test_later_unavailable_registration_cannot_return_the_previous_roots_good_receipt(self):
        reader = self.reader(); first = reader.read(RUN)
        def missed_second_root(value):
            request = value['requestId']; value.clear()
            value.update(iosChatQmlSourcesVersion=1, requestId=request, status='unavailable')
        # Explicit native failure boundary: C++ catch/latch behavior is reviewed
        # source, not executed here. The live transport must reject unavailable
        # even when this same reader retains an earlier valid original.
        self.boundary.mutate = missed_second_root
        with self.assertRaises(NativeUIError): reader.read(RUN)
        self.assertEqual(first, reader.last)
        self.assertEqual((2, 2), (len(self.boundary.queries), len(self.afc)))
        self.assertNotEqual(self.boundary.queries[0]['commandId'], self.boundary.queries[1]['commandId'])


if __name__ == '__main__': unittest.main()
