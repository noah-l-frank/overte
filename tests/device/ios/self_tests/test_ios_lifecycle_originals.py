"""Existing installed factory, original private transports, declared native/OS.

No native code, real Qt/IME/UIKit, compiler or device executes in these cases.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,lifecycle_originals
from ios.self_tests.test_ios_lifecycle_fields import FieldBoundary,Census
from ios.self_tests.test_ios_pending_runtime import PendingRuntimeTests


class LifecycleOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.p=PendingRuntimeTests();self.p.setUp();self.addCleanup(self.p.doCleanups)
        self.f=self.p.f;self.tick=10;self.b=FieldBoundary('scripts');self.c=Census(epoch=20000)
        self.field=self.c.load('scripts',focused=False)
        self.field['identity']['componentSource']='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml'
        self.b.census=self.c;self.c.clock=self.stamp
        self.p.boundary.epoch=lambda:20000+self.tick
        self.p.k.b.stamp=self.stamp
        def native_clock(packet):self.stamp();self.p.k.native_clock(packet)
        self.f.clock.mutate=native_clock
        prior_producer=self.p.boundary.edit
        def pending_producer(value):
            prior_producer(value)
            if not self.c.pending:self.c.pending.append(dict(token=value['current']['token'],identity=deepcopy(self.field['identity'])))
        self.p.boundary.edit=pending_producer
        before_observed=self.b.observed
        def observed():
            value=before_observed();value['sampleEpochMs']=self.stamp()['epochMs']
            value['controls'][0]['focused']=self.field['focused'];return value
        self.b.observed=observed;self.enterContext(patch.object(normal_input,'urlopen',self.b.post))
        previous_execute=self.p.k.client.execute
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/ios-normal-ui-request-result.json'):
                return base64.b64encode(json.dumps(self.b.receipt).encode()).decode()
            return previous_execute(session,operation,values)
        self.p.k.client.execute=execute
    def stamp(self):
        self.tick+=1;self.p.k.b.time=self.tick
        return dict(epochMs=20000+self.tick,monotonicMs=self.tick)
    def source(self):return self.f.adapter._lifecycle_sources('test-only','a'*32)

    def test_actual_existing_factory_joins_independent_original_sources_without_launch(self):
        count=(self.f.sessions,self.f.launches);source=self.source();original=source.sample(time.time()*1000)
        measured=lifecycle_originals.validate(original,source.binding,source.run)
        self.assertEqual('scripts',measured['field']['identity']['editor'])
        self.assertFalse(measured['field']['focused']);self.assertFalse(measured['keyboard']['keyboard'])
        self.assertEqual(measured['field']['identity'],measured['holder']['current'])
        self.assertEqual(count,(self.f.sessions,self.f.launches));self.assertEqual(2,len(self.b.requests))
        self.assertTrue(all(row['operation']=='observe' for row in self.b.requests))
        self.assertEqual(['observe'],[row['operation'] for row in self.p.boundary.commands])

    def test_changed_candidate_prevents_all_source_transport(self):
        source=self.source();self.f.artifact.write_bytes(b'Foreign candidate after source admission')
        with self.assertRaises((ValueError,NativeUIError)):source.sample(time.time()*1000)
        self.assertEqual([],self.b.requests);self.assertEqual([],self.p.boundary.commands)

    def test_unknown_keyboard_and_disagreeing_native_identity_cannot_be_editor_facts(self):
        source=self.source();self.p.k.b.events=[]
        with self.assertRaises(NativeUIError):source.sample(time.time()*1000)
        self.assertTrue(all(row['operation']=='observe' for row in self.b.requests))
        self.assertEqual(['observe'],[row['operation'] for row in self.p.boundary.commands])

    def test_rewritten_sources_fail_original_clock_digest_and_do_not_retime(self):
        source=self.source();original=source.sample(time.time()*1000);saved=deepcopy(original)
        changed=deepcopy(original);changed['originals']['ui']['lifecycleFieldInventory']['fields'][0]['current']['text']='retry-'+'a'*32
        with self.assertRaises(NativeUIError):lifecycle_originals.validate(changed,source.binding,source.run)
        self.assertEqual(saved,original)
