"""Failed preparation stays failed across genuine HTTP and modeled OS sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_abort import IOSAvatarAbort
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.self_tests.test_ios_process_retirement import BINDING,RUN,SOURCE,BUNDLE
from ios.self_tests.test_ios_retired_process import Boundary


class AvatarAbortTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.os=Boundary();self.calls=[];self.exists=True;self.delete_lost=False;self.delete_ignored=False;self.get_lost=False
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_GET(self):
                if outer.get_lost:
                    outer.get_lost=False;outer.calls.append('GET');self.connection.close();return
                self.reply('GET')
            def do_DELETE(self):
                if not outer.delete_ignored:outer.exists=False
                if outer.delete_lost:
                    outer.calls.append('DELETE');self.connection.close();return
                self.reply('DELETE')
            def reply(self,method):
                outer.calls.append(method);status=200 if method=='DELETE' or outer.exists else 404
                raw=json.dumps(dict(value={} if status==200 else dict(error='invalid session id'))).encode()
                self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown);self.addCleanup(self.thread.join,.01)
        target=dict(serverUrl='http://127.0.0.1:'+str(self.server.server_port),appId=BUNDLE)
        self.good=True;self.stop_lost=False;self.stop_count=0
        class Base:
            _operation=None
            _session_recreation_forbidden=False
            def _candidate_guard(base,**_kwargs):
                if not outer.good:raise NativeUIError('Actual modeled candidate changed')
            def _binding(base,*_args):raise AssertionError('No unowned binding acquisition')
            def _target(base,_selector):return deepcopy(target)
            def read_session(base,_selector):return dict(sessionId=BINDING['sessionId'])
            def _scope(base,*_args):return {key:value for key,value in BINDING.items() if key!='processIdentity'}
            def invoke(base,selector,operation,values):
                self.assertEqual(('app.stop',{}),(operation,values));self.assertTrue(base._session_recreation_forbidden);outer.stop_count+=1
                if outer.stop_lost:raise OSError('Actual stop return lost')
                return dict(performed=True)
        self.runtime=IOSAvatarRuntime(Base());self.feature=object.__new__(IOSAvatarFeature)
        feature=self.feature;feature.runtime=self.runtime;feature.selector='ios:primary';feature.lock=self.lock;feature.run=RUN;feature.role='primary'
        feature.store=PrivateFeatureState(self.root/'ios-avatar-primary-feature.json')
        failed=dict(iosAvatarFeatureVersion=1,runId=RUN,payload=pack([dict(phase='preparing',bindings=dict(primary=BINDING))]))
        feature.store.write(failed,None)
        def load():feature.previous=feature.store.read();feature.state=unpack(feature.previous['payload'])[0]
        feature.load=load
        self.addCleanup(patch.stopall)
        patch.object(IOSGraphicsRuntime,'_graphics_final_source',return_value=deepcopy(SOURCE)).start()
        patch.object(IOSGraphicsRuntime,'_retired_process_observer',side_effect=lambda *_args:self.os.reader()).start()
        patch.object(IOSGraphicsRuntime,'_graphics_final_stopped',return_value=None).start()

    def owner(self):return IOSAvatarAbort(self.feature,epoch_ms=lambda:self.os.clock*1000,monotonic=lambda:self.os.clock)
    def quiet(self,owner):
        self.assertFalse(owner.process_round());self.os.clock+=1.6;self.assertFalse(owner.process_round())
        self.os.clock+=1.6;self.assertTrue(owner.process_round())

    def test_failed_original_is_preserved_through_one_stop_os_quiet_and_actual_sdk_absence(self):
        with self.lock.held():
            owner=self.owner();failed=deepcopy(self.feature.previous);owner.stop();self.quiet(owner)
            self.assertTrue(owner.delete());result=owner.result()
            self.assertEqual('failed',result['status']);self.assertTrue(result['ownershipRetained'])
            self.assertEqual(failed,self.feature.store.read());self.assertEqual(1,self.stop_count);self.assertEqual(['GET','DELETE','GET'],self.calls)
            rebuilt=self.owner();self.assertEqual(result,rebuilt.result());self.assertEqual(['GET','DELETE','GET'],self.calls)

    def test_lost_stop_and_delete_returns_never_send_those_operations_again(self):
        with self.lock.held():
            owner=self.owner();self.stop_lost=True
            with self.assertRaises(OSError):owner.stop()
            owner=self.owner();self.quiet(owner);self.delete_lost=True
            with self.assertRaises(Exception):owner.delete()
            self.assertEqual('delete-issued',owner.state['phase']);rebuilt=self.owner();self.assertTrue(rebuilt.delete())
            self.assertEqual(1,self.stop_count);self.assertEqual(1,self.calls.count('DELETE'));self.assertEqual('failed',rebuilt.result()['status'])

    def test_ended_abort_archive_reopens_only_original_files_after_the_sdk_is_gone(self):
        with self.lock.held():
            owner=self.owner();owner.stop();self.quiet(owner);self.assertTrue(owner.delete());expected=owner.result()
            calls=list(self.calls);queries=list(self.os.queries)
            with (patch.object(self.runtime.adapter,'_candidate_guard',side_effect=AssertionError('No live factory during historical abort')),
                 patch.object(self.runtime.adapter,'_target',side_effect=AssertionError('No SDK resolver during historical abort'))):
                replay=IOSAvatarAbort.archive(self.feature,owner.previous);self.assertEqual(expected,replay.original_result())
            self.assertEqual(calls,self.calls);self.assertEqual(queries,self.os.queries)
            broken=deepcopy(owner.previous);broken['failure']['originalSha256']='f'*64
            owner.store.write(broken,owner.previous)
            with self.assertRaises(NativeUIError):IOSAvatarAbort.archive(self.feature,broken)

    def test_intent_save_failure_prevents_stop_and_changed_candidate_prevents_later_transports(self):
        with self.lock.held():
            owner=self.owner()
            with patch.object(owner.store,'write',side_effect=OSError('Actual intent save failed')):
                with self.assertRaises(OSError):owner.stop()
            self.assertEqual(0,self.stop_count);self.assertEqual(['GET'],self.calls)
            self.good=False
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual([],self.os.queries)

    def test_ignored_delete_ack_is_not_sdk_absence_and_cannot_authorize_a_resend(self):
        with self.lock.held():
            owner=self.owner();owner.stop();self.quiet(owner);self.delete_ignored=True
            self.assertFalse(owner.delete());rebuilt=self.owner();self.assertFalse(rebuilt.delete())
            with self.assertRaises(NativeUIError):rebuilt.result()
            self.assertEqual(1,self.calls.count('DELETE'));self.assertEqual('delete-issued',rebuilt.state['phase'])

    def test_lost_sdk_query_is_abandoned_before_a_distinct_new_query_without_another_delete(self):
        with self.lock.held():
            owner=self.owner();owner.stop();self.quiet(owner);self.get_lost=True
            with self.assertRaises(Exception):owner.delete()
            self.assertIsNotNone(owner.state['sdkPending']);rebuilt=self.owner();self.assertTrue(rebuilt.delete())
            self.assertEqual(['abandoned','absent'],[row['status'] for row in rebuilt.state['sdkQueries']])
            self.assertEqual(1,self.calls.count('DELETE'));self.assertEqual(1,self.stop_count)

    def test_original_abort_input_deadline_survives_reconstruction_and_slow_intent_save(self):
        with self.lock.held():
            owner=self.owner();original=owner.store.write
            def slow(value,previous):
                result=original(value,previous);self.os.clock+=26;return result
            with patch.object(owner.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(0,self.stop_count);rebuilt=self.owner();self.assertEqual('stop-issued',rebuilt.state['phase'])
            with self.assertRaises(NativeUIError):rebuilt.stop()
            self.assertEqual(0,self.stop_count)

    def test_ready_feature_and_mutated_failed_intent_never_qualify_abort(self):
        with self.lock.held():
            owner=self.owner();value=self.feature.store.read();rows=unpack(value['payload']);rows[0]['phase']='ready';value['payload']=pack(rows)
            self.feature.store.write(value,self.feature.store.read())
            with self.assertRaises(NativeUIError):owner.stop()
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(0,self.stop_count)

    def test_only_exact_cleanup_outer_is_temporarily_cleared_after_durable_stop_intent_and_restored_on_loss(self):
        with self.lock.held():
            owner=self.owner();base=self.runtime.adapter;base._operation='feature.avatar-people.cleanup';self.stop_lost=True
            with self.assertRaises(OSError):owner.stop()
            self.assertEqual('feature.avatar-people.cleanup',base._operation);self.assertFalse(base._session_recreation_forbidden)
            self.assertEqual('stop-issued',self.owner().state['phase'])
            with self.assertRaises(NativeUIError):self.owner().stop()
            self.assertEqual(1,self.stop_count)

    def test_foreign_outer_operation_cannot_issue_abort_stop(self):
        with self.lock.held():
            owner=self.owner();base=self.runtime.adapter;base._operation='feature.avatar-people.act'
            with self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual('feature.avatar-people.act',base._operation);self.assertEqual(0,self.stop_count)
            self.assertEqual('failed',self.owner().state['phase'])


if __name__=='__main__':unittest.main()
