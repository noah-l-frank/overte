"""Canonical installed factory and AFC codecs; native/OS are boundary models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pending_commit_owner import FILE
from ios.adapters import feature_observation
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
from self_tests.test_pending_commit_owner import Boundary,RUN


class PendingRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups)
        self.f=self.k.f;self.boundary=Boundary();self.afc=[]
        def producer(value):
            value['processId']=42
            if value['commit']:value['commit']['observation']['processId']=42
        self.boundary.edit=producer
        previous=self.k.client.execute
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.boundary.original().encode()).decode()
            return previous(session,operation,values)
        self.k.client.execute=execute
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!='feature-pending-commit-owner':return self.k.post(request,timeout)
            self.boundary.send(query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post))

    def test_existing_factory_reads_and_retires_original_event_without_new_session_or_launch(self):
        root=self.f.adapter.state_path('test-only').parent;store=PrivateFeatureState(root/'pending-runtime-intent.json')
        def intent(command):store.write(command,store.read())
        count=(self.f.sessions,self.f.launches);owner=self.f.adapter._pending_owner('test-only',intent)
        owner.focus(RUN);owner.type_owned(RUN);held=owner.hold(RUN)
        original=held['commit']['observation'];event=original['eventId'];self.boundary.replace_context()
        rejected=owner.attempt_retired(RUN,event);cleaned=owner.release_owned(RUN,event)
        self.assertEqual(original['events'][0],rejected['commit']['observation']['events'][0])
        self.assertEqual([],cleaned['resources']['pendingRuns']);self.assertEqual(count,(self.f.sessions,self.f.launches))
        self.assertEqual(len(self.boundary.commands),len(self.afc));self.assertEqual('release',store.read()['operation'])
        self.assertTrue(all(row['commandId'].startswith('ios-') for row in self.boundary.commands))

    def test_changed_installed_bytes_refuse_transport_without_launch_or_new_session(self):
        owner=self.f.adapter._pending_owner('test-only');count=(self.f.sessions,self.f.launches)
        self.f.artifact.write_bytes(b'Changed candidate after owner construction')
        with self.assertRaises(NativeUIError):owner.read(RUN)
        self.assertEqual([],self.boundary.commands);self.assertEqual([],self.afc)
        self.assertEqual(count,(self.f.sessions,self.f.launches))

    def test_replaced_process_or_background_cannot_borrow_existing_owner(self):
        for change in (dict(pid=43),dict(foreground=False)):
            old=dict(self.f.process);owner=self.f.adapter._pending_owner('test-only');self.f.process.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):owner.read(RUN)
            self.f.process=old;self.assertEqual([],self.boundary.commands)
