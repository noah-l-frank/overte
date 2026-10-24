"""Independent wire/source/read-lease models; no native compilation or server.

Native/Qt boundaries remain explicit models. Real Python weak references test
retention logic; none of these cases qualify an installed/native/device run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_replies as source
from ios.adapters import assets_reply_protocol as wire
from ios.self_tests.assets_reply_fixture import Fixture,RUN,binary,string


class AssetsRepliesTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name);self.path.chmod(0o700);self.fixture=Fixture(self.path);self.addCleanup(self.fixture.close)
        self.owner,self.boundary=self.fixture.owner,self.fixture.boundary

    def component_query(self,kind='inventory',**values):return self.owner._query(kind,**values)

    def test_original_bundle_bytes_companion_paths_and_read_only_retirement(self):
        before=deepcopy(self.boundary.data);value=self.owner.observe_bundle()
        self.assertEqual({'main.gltf','mesh/triangle.bin','textures/checker.png'},{row['relativePath'] for row in value['files']})
        for row in value['files']:
            actual=base64.b64decode(row['body']['base64']);self.assertEqual(before['/e2e-'+RUN+'/'+row['relativePath']],actual)
            self.assertEqual(hashlib.sha256(actual).hexdigest(),row['hash']);self.assertEqual(value['binding'],row['binding'])
        self.assertNotIn('bakeState',value);self.assertNotIn('sceneModel',value)
        self.owner.close();self.assertEqual('closed',self.fixture.restore().state['phase']);self.assertEqual(before,self.boundary.data)
        requests=len(self.boundary.requests);self.owner.close();self.assertEqual(requests,len(self.boundary.requests));self.assertIsNotNone(self.fixture.store.read())

    def test_exact_original_result_bytes_are_hashed_without_json_reencoding(self):
        self.boundary.status['/e2e-'+RUN+'/main.gltf']=(5,'Native error: ä 東京\nsecond line')
        actual=self.owner.read('inventory');packet=self.owner.state['originals'][-1]['packet'];job=packet['source']['job']
        original=base64.b64decode(job['resultBase64']);canonical=json.dumps(job['result'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        self.assertNotEqual(original,canonical);self.assertEqual(5,actual['mappings'][0]['status'])
        self.assertIn('東京',actual['mappings'][0]['bakingErrors']);self.owner.close()

    def test_actual_message_weak_hold_blocks_success_after_object_and_callback_return(self):
        self.boundary.hold_messages=True;native=self.boundary.native();query=self.component_query();packet=native.request(query)
        self.assertFalse(packet['source']['job']['alive']);self.assertFalse(packet['source']['job']['tokenAlive']);self.assertEqual(0,packet['source']['job']['pendingBodies'])
        self.assertTrue(packet['source']['job']['messages'][0]['alive']);self.assertFalse(source.drained(packet))
        with self.assertRaises(NativeUIError):source.qualified(packet)
        self.boundary.held_messages.clear();last=native.request(self.component_query('observe',jobId=query['commandId']))
        self.assertTrue(source.drained(last));source.qualified(last)

    def test_actual_callback_control_weak_hold_blocks_drain_after_message_expiry(self):
        self.boundary.hold_controls=True;native=self.boundary.native();query=self.component_query();packet=native.request(query)
        self.assertFalse(packet['source']['job']['alive']);self.assertFalse(packet['source']['job']['messages'][0]['alive'])
        self.assertTrue(packet['source']['job']['tokenAlive']);self.assertFalse(source.drained(packet))
        self.boundary.held_controls.clear();last=native.request(self.component_query('observe',jobId=query['commandId']));self.assertTrue(source.drained(last))

    def test_malformed_original_wire_is_retained_for_diagnostics_and_can_drain(self):
        self.boundary.bad_wire=True
        with self.assertRaises(NativeUIError):self.owner.read('bad-inventory')
        self.assertEqual('failed',self.owner.state['jobs'][0]['phase']);self.assertTrue(self.owner.state['originals'])
        packet=self.owner.state['originals'][-1]['packet'];self.assertTrue(source.drained(packet))
        reply=source.events(packet['source'])['replies']['mapping-reply'];self.assertTrue(wire.body(reply['details']['payload']).endswith(b'not-a-mapping'))
        self.owner.close();self.assertEqual('closed',self.owner.state['phase'])

    def test_measured_oversize_info_is_original_failure_and_no_raw_read_starts(self):
        self.owner.read('inventory');self.boundary.size_override=40000
        with self.assertRaises(NativeUIError):self.owner.read('too-large','info',source_slot='inventory',relative_path='main.gltf')
        packet=self.owner.state['originals'][-1]['packet'];self.assertEqual('40000',packet['source']['job']['result']['size'])
        self.assertFalse(any(query['operation']=='raw-server' for query in self.boundary.requests));self.owner.close()

    def test_actual_sender_object_or_message_mismatch_never_qualifies(self):
        query=self.component_query();packet=self.boundary.native().request(query)
        for field,value in (('sender','33333333-3333-4333-8333-333333333333'),('serverInstance','f'*32),('messageId',900)):
            bad=deepcopy(packet);bad['source']['complete']=False
            reply=next(event for event in bad['source']['job']['events'] if event['kind']=='mapping-reply');reply['details'][field]=value;reply['details']['sameTarget']=False
            source.validate(bad,query,42)
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.qualified(bad)

    def test_raw_data_hash_is_checked_against_original_inventory_not_input_ack(self):
        self.owner.read('inventory');self.owner.read('info','info',source_slot='inventory',relative_path='main.gltf')
        query=self.component_query('raw-server',sourceJob=self.owner._job('info')['query']['commandId'],relativePath='main.gltf')
        packet=self.boundary.native().request(query);job=packet['source']['job'];wrong=b'x'*int(job['inputs']['size'])
        raw=next(event for event in job['events'] if event['kind']=='raw-body');raw['details']['payload']=binary(wrong)
        job['result']['body']=binary(wrong);encoded=json.dumps(job['result'],ensure_ascii=True,indent=1).encode();job['resultBase64']=base64.b64encode(encoded).decode()
        event=next(event for event in job['events'] if event['kind']=='result');event['details']=dict(bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest())
        source.validate(packet,query,42)
        with self.assertRaises(NativeUIError):source.qualified(packet)

    def test_lost_read_start_recovers_by_observe_without_resending(self):
        self.boundary.lost='inventory'
        with self.assertRaises(NativeUIError):self.owner.read('uncertain')
        self.assertEqual('issued',self.owner.state['jobs'][0]['phase']);restored=self.fixture.restore();restored.recover('uncertain')
        self.assertEqual(1,sum(query['operation']=='inventory' for query in self.boundary.requests));restored.close()

    def test_lost_retirement_recovers_actual_weak_drain_without_repeating_cancel(self):
        self.boundary.defer=True;self.boundary.lost='inventory'
        with self.assertRaises(NativeUIError):self.owner.read('pending')
        self.boundary.lost='retire'
        with self.assertRaises(NativeUIError):self.owner.close()
        restored=self.fixture.restore();restored.close();self.assertEqual('closed',restored.state['phase'])
        self.assertEqual(1,sum(query['operation']=='retire' for query in self.boundary.requests))

    def test_latest_observer_clock_does_not_retime_an_old_server_reply(self):
        native=self.boundary.native();query=self.component_query();first=native.request(query);captured=source.qualified(first)['captured']
        self.boundary.sleep(2);last=native.request(self.component_query('observe',jobId=query['commandId']))
        self.assertEqual(captured,source.events(last['source'])['replies']['mapping-reply']['clock'])
        with self.assertRaises(NativeUIError):source.qualified(last)
        self.assertEqual(captured,source.qualified(first)['captured'])

    def test_raw_protocol_rejects_duplicate_truncated_and_trailing_mapping_rows(self):
        row=self.boundary.rows()[0];entry=string(row['path'])+bytes.fromhex(row['hash'])+struct.pack('<i',row['status'])
        for raw in (struct.pack('<I',2)+entry+entry,struct.pack('<I',1)+entry[:-1],struct.pack('<I',1)+entry+b'x'):
            with self.subTest(bytes=len(raw)),self.assertRaises(NativeUIError):wire.inventory(raw)

    def test_redirect_is_preserved_without_an_oven_or_ready_verdict(self):
        self.owner.read('inventory');self.boundary.redirect=dict(hash='f'*64,path='/.baked/'+'1'*64+'/model.fbx')
        value=self.owner.read('redirect','mapping',source_slot='inventory',relative_path='main.gltf')
        self.assertTrue(value['redirected']);self.assertEqual(self.boundary.redirect['path'],value['redirectedPath'])
        self.assertNotIn('bakeState',value);self.assertNotIn('oven',value);self.owner.close()

    def test_unavailable_server_is_not_an_empty_mapping_inventory(self):
        self.boundary.available=False
        with self.assertRaises(NativeUIError):self.owner.read('no-server')
        packet=self.owner.state['originals'][-1]['packet'];self.assertEqual(2,packet['source']['job']['result']['error'])
        self.assertFalse(source.events(packet['source'])['replies']);self.owner.close()

    def test_public_cache_audit_operation_is_closed(self):
        query=self.component_query();query['operation']='asset-request'
        with self.assertRaises(NativeUIError):source.command(query)


if __name__=='__main__':unittest.main()
