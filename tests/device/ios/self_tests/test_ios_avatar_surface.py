"""Real normal transport and source archives at explicit synthetic Qt seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input
from ios.adapters.avatar_surface import IOSAvatarSurface,AvatarSurfacePending
from ios.self_tests import test_ios_avatar_actions as fixture


class AvatarSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarActionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        held=self.f.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.widget=self.f.fixture.widget;self.widget.tab='nearbyTab';self.widget.invitation=None;self.fetches=0
        self.f.fixture.prototypes['people']['source']['roots'][0].update(rootId=self.widget.root(),
            qmlSource='file:///app.bundle/qml/hifi/Pal.qml')
        original_rows=self.widget.rows
        def rows():
            result=original_rows()
            if self.widget.screen!='people':return result
            page=next(row for row in result if row['id']=='people.page');page['activeTab']=self.widget.tab
            if self.widget.invitation:page['connectionState'].update(self.widget.invitation)
            for identifier in ('people.nearby','people.connections'):
                result.append(dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier)),enabled=True,focused=False,
                    inputReady=True,rootId=self.widget.root(),qmlSource='file:///app.bundle/qml/hifi/Pal.qml'))
            return result
        self.widget.rows=rows;original_post=self.widget.post
        def post(request,timeout):
            p=json.loads(request.data);selected=None
            if p['operation']=='edit':
                matches=[row['id'] for row in rows() if row['token']==p['input']['fieldToken']]
                if matches:selected=matches[0]
            result=original_post(request,timeout)
            if selected=='people.connections':self.widget.tab='connectionsTab';self.fetches+=1
            elif selected=='people.nearby':self.widget.tab='nearbyTab'
            return result
        transport=patch.object(normal_input,'urlopen',post);transport.start();self.addCleanup(transport.stop)
        self.f.source=self.f.make_sources()
    def owner(self):
        return IOSAvatarSurface(PrivateFeatureState(self.f.path/'ios-avatar-primary-primary-surface.json'),
            self.f.source,self.f.sdk,observer_role='primary',subject_role='primary')
    def test_each_phase_uses_ordinary_connections_fetch_and_separate_original_input_ownership(self):
        first=self.owner().prepare('1'*32);self.assertTrue(first['ui']['open']);self.assertEqual(1,self.fetches)
        restored=self.owner();delivered=sum(row['operation']=='edit' for row in self.widget.requests);restored.prepare('1'*32)
        self.assertEqual(delivered,sum(row['operation']=='edit' for row in self.widget.requests));self.assertEqual(1,self.fetches)
        self.f.action('avatar-scale',dict(value=1.5),'2'*32);restored.prepare('2'*32)
        self.assertEqual(2,self.fetches);events=restored.state['calls'][-1]['events']
        self.assertEqual(['people.nearby','people.connections'],[row['intent']['controlId'] for row in events])
        self.assertTrue(all(row['observed'] is not None for row in events))
        self.assertFalse((self.f.path/'ios-avatar-primary-inputs.json').exists())
    def test_pending_invitation_keeps_exact_actual_UUID_and_sends_no_accept_decline_or_cancel(self):
        self.widget.shown=True;self.widget.screen='people';self.widget.dialog='connection';self.widget.phase='incoming'
        original=dict(peer='00000000-0000-4000-8000-000000000002',requestId='00000000-0000-4000-8000-000000000003',phase='incoming')
        self.widget.invitation=deepcopy(original);owner=self.owner();owner.prepare('1'*32)
        self.assertEqual(original,owner.state['calls'][0]['invitation']);self.assertEqual([],owner.state['calls'][0]['events'])
        self.assertEqual(0,self.fetches)
    def test_lost_pointer_delivery_preserves_original_intent_and_never_refetches_or_replays(self):
        self.widget.shown=True;self.widget.screen='people';self.widget.lost=True;owner=self.owner()
        with self.assertRaises(NativeUIError):owner.prepare('1'*32)
        event=owner.state['calls'][-1]['events'][-1];self.assertIsNone(event['delivery'])
        original=deepcopy(event['intent']);requests=len(self.widget.requests)
        restored=self.owner()
        with self.assertRaises(AvatarSurfacePending):restored.prepare('1'*32)
        self.assertEqual(requests,len(self.widget.requests));self.assertEqual(original,restored.state['calls'][-1]['events'][-1]['intent'])

    def test_terminal_peer_consent_waits_without_admitting_or_closing_observer_input(self):
        self.widget.shown=True;self.widget.screen='people';self.widget.dialog='connection';self.widget.phase='success'
        owner=self.owner();before=sum(row['operation']=='edit' for row in self.widget.requests)
        with self.assertRaises(AvatarSurfacePending):owner.prepare('1'*32)
        self.assertEqual([],owner.state['calls']);self.assertEqual(before,sum(row['operation']=='edit' for row in self.widget.requests))
        self.assertEqual('connection',self.widget.dialog)
        # Explicit synthetic product-owner completion, outside observation.
        self.widget.dialog='none';self.widget.phase='idle';restored=self.owner();restored.prepare('1'*32)
        self.assertEqual('ready',restored.state['calls'][0]['phase']);self.assertEqual(1,self.fetches)


if __name__=='__main__':unittest.main()
