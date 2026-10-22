"""Actual original Source/Qt input for Actor's cancelled invitation closure."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_surface import IOSAvatarSurface,AvatarSurfacePending
from ios.adapters import normal_input
from ios.self_tests import test_ios_avatar_surface as original_surface
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarSurfaceV2Tests(unittest.TestCase):
    def setUp(self):
        self.f=original_surface.AvatarSurfaceTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.widget=self.f.widget;self.widget.shown=True;self.widget.screen='people';self.widget.dialog='connection';self.widget.phase='incoming'
        self.widget.invitation=dict(peer='00000000-0000-4000-8000-000000000002',requestId='00000000-0000-4000-8000-000000000003',phase='incoming')
        f=self.f.f
        self.sources=IOSAvatarSources(PrivateFeatureState(f.path/'ios-avatar-actor-sources.json'),f.root,BINDING,f.fixture.run,'actor',f.lock,
            lambda:True,f.fixture.phase,readers=f.readers,monotonic=lambda:f.fixture.clock,epoch_ms=f.fixture.host)
        original=normal_input.urlopen
        def post(request,timeout):
            p=json.loads(request.data);selected=None
            if p['operation']=='edit':selected=next(row['id'] for row in self.widget.rows() if row['token']==p['input']['fieldToken'])
            result=original(request,timeout)
            if selected=='people.cancel':self.widget.invitation['phase']=self.widget.phase
            return result
        transport=patch.object(normal_input,'urlopen',side_effect=post);transport.start();self.addCleanup(transport.stop)
    def owner(self,subject='actor'):
        f=self.f.f
        return IOSAvatarSurface(PrivateFeatureState(f.path/('ios-avatar-actor-'+subject+'-surface.json')),self.sources,f.sdk,
            observer_role='actor',subject_role=subject)
    def admit(self):
        owner=self.owner();owner.prepare('1'*32)
        self.f.f.action('connection-cancel',{},'2'*32);self.widget.phase='cancelled';self.widget.invitation['phase']='cancelled';return owner
    def test_only_actual_owned_actor_cancelled_UUID_gets_one_normal_terminal_close_then_fresh_table(self):
        owner=self.admit();owner.prepare('2'*32);self.assertEqual(('idle','none'),(self.widget.phase,self.widget.dialog))
        call=owner.state['calls'][-1];self.assertEqual('cancelled',call['terminal']['phase'])
        self.assertEqual(['people.cancel','people.connections'],[event['intent']['controlId'] for event in call['events']])
        before=sum(row['operation']=='edit' for row in self.widget.requests);self.owner().prepare('2'*32);self.assertEqual(before,sum(row['operation']=='edit' for row in self.widget.requests))
        self.assertEqual(2,owner.previous['iosAvatarSurfaceVersion'])
        legacy=deepcopy(owner.previous);legacy['iosAvatarSurfaceVersion']=1;state=unpack(legacy['payload'])[0]
        for item in state['calls']:item.pop('terminal',None)
        legacy['payload']=pack([state])
        with self.assertRaises(NativeUIError):owner.decode(legacy)
    def test_unadmitted_replaced_or_foreign_subject_terminal_never_sends_close(self):
        for fault in ('unadmitted','uuid','foreign'):
            with self.subTest(fault=fault):
                if fault!='unadmitted':self.tearDown();self.setUp();self.admit()
                else:self.f.f.action('connection-cancel',{},'2'*32);self.widget.phase='cancelled';self.widget.invitation['phase']='cancelled'
                if fault=='uuid':self.widget.invitation['requestId']='00000000-0000-4000-8000-000000000004'
                before=len(self.widget.requests)
                with self.assertRaises(AvatarSurfacePending):self.owner('primary' if fault=='foreign' else 'actor').prepare('2'*32)
                self.assertFalse(any(row['operation']=='edit' for row in self.widget.requests[before:]))
    def test_legacy_v1_remains_readable_and_cannot_carry_v2_terminal_or_close(self):
        owner=self.owner();owner.prepare('1'*32);legacy=owner.envelope(deepcopy(owner.state),version=1)
        state=unpack(legacy['payload'])[0]
        for call in state['calls']:call.pop('terminal',None)
        legacy['payload']=pack([state]);self.assertEqual(state,owner.decode(legacy))
        bad=deepcopy(state);bad['calls'][0]['terminal']=dict(peer=self.widget.invitation['peer'])
        with self.assertRaises(NativeUIError):owner.decode(dict(legacy,payload=pack([bad])))
    def test_same_peer_new_UUID_after_durable_cancel_admission_is_not_closed(self):
        self.admit();owner=self.owner();save=owner.save
        def changed():
            save()
            if owner.state['calls'][-1].get('terminal') is not None:self.widget.invitation['requestId']='00000000-0000-4000-8000-000000000004'
        owner.save=changed;before=sum(row['operation']=='edit' for row in self.widget.requests)
        with self.assertRaises(NativeUIError):owner.prepare('2'*32)
        self.assertEqual(before,sum(row['operation']=='edit' for row in self.widget.requests))

    def test_lost_terminal_return_retains_exact_command_and_never_sends_it_again(self):
        self.admit();self.widget.lost=True
        with self.assertRaises(NativeUIError):self.owner().prepare('2'*32)
        count=len(self.widget.requests);self.widget.lost=False
        with self.assertRaises(AvatarSurfacePending):self.owner().prepare('2'*32)
        self.assertEqual(count,len(self.widget.requests))


if __name__=='__main__':unittest.main()
