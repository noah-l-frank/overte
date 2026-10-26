"""Real private WAL and canonical HTTP/AFC; Qt/UIKit/SDK are declared models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import hashlib
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import feature_observation,lifecycle_world as world
from ios.adapters.lifecycle_editors_runtime import IOSLifecycleEditorsRuntime
from ios.self_tests.test_ios_lifecycle_editors import EditorDomain
from ios.self_tests.test_ios_lifecycle_touch import TouchBoundary
from ios.self_tests.test_ios_scene_commit_origin import Boundary as SceneBoundary


class AttemptDomain:
    def __init__(self,case):
        self.d=EditorDomain(case);self.d.flow.open('create');self.d.flow.type('create','Overte ä Ω 東京 '+self.d.source.run)
        self.native=self.d.f.f;native=self.native
        class Scene(SceneBoundary):
            def epoch(self):return 20000+native.tick
            def clocks(self):return native.stamp()
        class Touch(TouchBoundary):
            def stamp(self):return dict(epochMs=20000+native.tick,monotonicMs=native.tick)
            def event(self,*args,**kwargs):native.stamp();return super().event(*args,**kwargs)
        self.boundary=Touch(Scene)
        self.raw={};self.geometry_sequence=0;self.calls=[];self.lost=None;self.ignore=False;self.wrong=False;self.moves=False;self.editor_lost=False;self.candidate_lost=False
        self.client=self.d.source.source['client'];previous_call=self.client.call;previous_execute=self.client.execute
        previous_post=feature_observation.post_request.side_effect
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']==world.ACTION:
                self.boundary.send(query);self.raw[world.FILE]=self.boundary.original()
            elif query['action']=='native-geometry-snapshot':
                self.geometry_sequence+=1
                self.raw['ios-ui-request-result.json']=json.dumps(dict(schemaVersion=1,commandId=query['commandId'],
                    observation=dict(schemaVersion=1,sampleEpochMs=native.stamp()['epochMs'],sampleSequence=self.geometry_sequence,
                        nativeUi=dict(valid=True,surfaceWidth=1000,surfaceHeight=640,safeInsetLeft=0,safeInsetTop=20,safeInsetRight=0,safeInsetBottom=20),
                        window=dict(width=1000,height=600))))
            else:return previous_post(request,timeout)
            raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        def execute(session,operation,values):
            if operation=='mobile: pullFile':
                name=values['remotePath'].rsplit('/',1)[-1]
                if name in self.raw:return base64.b64encode(self.raw[name].encode()).decode()
            return previous_execute(session,operation,values)
        def call(method,path,body=None):
            if path.endswith('/window/rect'):return dict(x=0,y=0,width=1000,height=640)
            if path.endswith('/actions'):
                self.calls.append((method,deepcopy(body)))
                if method=='POST' and not self.ignore:
                    actions=body['actions'][0]['actions'];start=actions[0];end=actions[2]
                    start=[start['x'],start['y']-20];end=[end['x'],end['y']-20]
                    if self.wrong:start[0]+=30;end[0]+=30
                    self.boundary.event('begin','pressed',start,'ui')
                    self.boundary.event('update','updated',end,'ui')
                    self.boundary.event('end','released',end,'ui')
                    if self.moves:self.boundary.position=[0.,0.,-.1]
                    if self.editor_lost:self.d.current().update(text='',textSha256=hashlib.sha256(b'').hexdigest(),textCodeUnits=0)
                    if self.candidate_lost:self.d.f.f.f.artifact.write_bytes(b'Actual modeled candidate change during POST')
                if method==self.lost:self.lost=None;raise OSError('Declared lost modeled SDK return')
                return None
            return previous_call(method,path,body)
        self.client.call=call;self.client.execute=execute
        case.enterContext(patch.object(feature_observation,'post_request',side_effect=post))
        self.runtime=IOSLifecycleEditorsRuntime(self.d.f.f.f.adapter);self.owner=self.reopen()
    def reopen(self):
        self.owner=self.runtime.world_attempt_child('test-only',self.d.flow);return self.owner
    def counts(self):return [method for method,_ in self.calls]


class LifecycleWorldAttemptTests(unittest.TestCase):
    def setUp(self):self.b=AttemptDomain(self)

    def test_normal_complete_touch_is_intercepted_and_preserves_original_editor_and_world(self):
        b=self.b;sessions=(b.d.f.f.f.sessions,b.d.f.f.f.launches);proof=b.owner.act()
        self.assertEqual(['POST','DELETE'],b.counts());self.assertEqual(0.,proof['facts']['worldDisplacement'])
        self.assertEqual('create',proof['editor']['editor']);self.assertTrue(proof['editor']['focused']);self.assertTrue(proof['editor']['keyboard'])
        self.assertEqual('released',proof['contact']['terminal']);self.assertEqual('ui',proof['contact']['route'])
        before=b.owner.frame(b.owner.state['before']);self.assertEqual(520,b.owner.state['body']['actions'][0]['actions'][0]['y'])
        self.assertEqual([100.,500.],before['originals']['world']['source']['pad']['center'])
        self.assertEqual(sessions,(b.d.f.f.f.sessions,b.d.f.f.f.launches))
        queries=len(b.boundary.queries);saved=deepcopy(proof);b.reopen();self.assertEqual(saved,b.owner.act())
        self.assertEqual(queries,len(b.boundary.queries));self.assertEqual(['POST','DELETE'],b.counts())

    def test_lost_post_return_is_resolved_only_from_original_contact_without_resend(self):
        b=self.b;b.lost='POST'
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual('issued',b.owner.state['phase']);self.assertFalse(b.owner.state['ack'])
        b.reopen();proof=b.owner.observe();self.assertEqual('released',proof['contact']['terminal'])
        self.assertEqual(['POST','DELETE'],b.counts());self.assertFalse(b.owner.state['ack'])

    def test_positive_ack_without_contact_never_qualifies_or_resends(self):
        b=self.b;b.ignore=True
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual(['POST','DELETE'],b.counts());b.reopen()
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual(['POST','DELETE'],b.counts())

    def test_actual_world_movement_under_the_editor_does_not_qualify(self):
        b=self.b;b.moves=True
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual(['POST','DELETE'],b.counts());self.assertEqual([0.,0.,-.1],b.boundary.position)

    def test_actual_editor_text_loss_does_not_qualify_an_intercepted_contact(self):
        b=self.b;b.editor_lost=True
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual(['POST','DELETE'],b.counts());self.assertEqual('',b.d.current()['text'])

    def test_foreign_contact_coordinates_do_not_borrow_owned_gesture(self):
        b=self.b;b.wrong=True
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual(['POST','DELETE'],b.counts())

    def test_lost_release_callback_is_still_owned_even_after_actual_native_pointer_up(self):
        b=self.b;b.lost='DELETE'
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual('issued',b.owner.state['release']);b.reopen()
        with self.assertRaises(NativeUIError):b.owner.observe()
        self.assertEqual(['POST','DELETE'],b.counts());self.assertEqual([],b.boundary.active)

    def test_saved_after_original_adopts_same_file_before_any_new_source_or_input(self):
        b=self.b;write=OriginalFrameStore.write
        def lost(store,index,frame):
            result=write(store,index,frame)
            if store.namespace=='ios-lifecycle-world-proof' and index==2:raise OSError('Declared interruption after saved original before parent CAS')
            return result
        with patch.object(OriginalFrameStore,'write',new=lost):
            with self.assertRaises(OSError):b.owner.act()
        original=deepcopy(b.owner.state['storage']['2']);path=b.owner.files().path(original);saved=(path.stat().st_ino,path.read_bytes())
        queries=len(b.boundary.queries);b.reopen();b.owner.observe()
        self.assertEqual(queries,len(b.boundary.queries));self.assertEqual(saved,(path.stat().st_ino,path.read_bytes()))
        self.assertEqual(['POST','DELETE'],b.counts())

    def test_candidate_change_refuses_before_any_owned_world_input(self):
        b=self.b;b.d.f.f.f.artifact.write_bytes(b'Foreign installed candidate after original scope construction')
        with self.assertRaises((ValueError,NativeUIError)):b.owner.act()
        self.assertEqual([],b.calls);self.assertEqual([],b.boundary.queries)

    def test_candidate_change_during_post_still_releases_exact_issued_session(self):
        b=self.b;b.candidate_lost=True
        with self.assertRaises((ValueError,NativeUIError)):b.owner.act()
        self.assertEqual(['POST','DELETE'],b.counts());self.assertEqual('returned',b.owner.store.read()['state']['release'])
        self.assertEqual('issued',b.owner.store.read()['state']['phase']);self.assertFalse(b.owner.store.read()['state']['ack'])

    def test_saved_preparation_is_adopted_without_requery_then_only_once_delivered(self):
        b=self.b;write=OriginalFrameStore.write
        def lost(store,index,frame):
            result=write(store,index,frame)
            if store.namespace=='ios-lifecycle-world-proof' and index==1:raise OSError('Declared interruption after saved preparation')
            return result
        with patch.object(OriginalFrameStore,'write',new=lost):
            with self.assertRaises(OSError):b.owner.act()
        ref=deepcopy(b.owner.state['storage']['1']);path=b.owner.files().path(ref);saved=(path.stat().st_ino,path.read_bytes())
        self.assertEqual([],b.calls);b.reopen();b.owner.act()
        self.assertEqual(2,len(b.boundary.queries));self.assertEqual(['POST','DELETE'],b.counts())
        self.assertEqual(saved,(path.stat().st_ino,path.read_bytes()))

    def test_expired_saved_preparation_does_not_issue_a_touch_from_old_geometry(self):
        b=self.b;save=b.owner.save
        def interrupt():
            save()
            if b.owner.state['phase']=='ready':raise OSError('Declared interruption after ready CAS')
        with patch.object(b.owner,'save',side_effect=interrupt):
            with self.assertRaises(OSError):b.owner.act()
        b.reopen();epoch,mono=b.owner.epoch_ms,b.owner.monotonic
        b.owner.epoch_ms=lambda:epoch()+1600;b.owner.monotonic=lambda:mono()+1.6
        with self.assertRaises(NativeUIError):b.owner.act()
        self.assertEqual([],b.calls);self.assertEqual('ready',b.owner.store.read()['state']['phase'])
