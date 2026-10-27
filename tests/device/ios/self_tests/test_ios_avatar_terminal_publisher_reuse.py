"""Real publisher transfer guards; the existing original decoder is modeled.

These tests exercise the small post-save handoff, not Final facts or an Avatar
observe result. The genuine retained callback has separate qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import MethodType
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_witness_publisher import AvatarWitnessPublisher
from ios.adapters import avatar_operation_clock
from self_tests import test_phase_witness_publisher as fixture


class AvatarTerminalPublisherReuseTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PhaseWitnessPublisherTests();self.addCleanup(self.f.doCleanups)
        # Use the same protocol fixture methods with an owned retained root.
        # No TemporaryDirectory finalizer may remove original journals.
        self.f.root=Path(tempfile.mkdtemp(prefix='avatar-terminal-publisher-reuse-'))
        self.f.root.chmod(0o700);print('retained publisher original root',self.f.root,flush=True)
        self.f.server=fixture.make_server('r'*64,'a'*64)
        self.f.thread=threading.Thread(target=lambda:self.f.server.serve_forever(poll_interval=.01),daemon=True)
        self.f.thread.start();self.f.addCleanup(self.f.stop)
        self.f.url='http://127.0.0.1:'+str(self.f.server.server_address[1])+'/feature-fixture/v1'
        self.f.reader=fixture.Client(self.f.url,'r'*64);self.f.actor=fixture.Client(self.f.url,'a'*64)
        self.f.lock=ScriptSourceLock(self.f.root/'script-feature-sources.lock')
        self.f.known={};self.f.okay=True;self.f.validations=0;self.f.attach('avatar-people')
        self.feature=object.__new__(IOSAvatarFeature);owner=self.feature
        owner.role,owner.run,owner.phase,owner.lock='actor',self.f.run,self.f.phase,self.f.lock
        owner.store=PrivateFeatureState(self.f.root/'ios-avatar-actor-feature.json')
        owner.epoch_ms=lambda:time.time()*1000;owner.monotonic=time.monotonic
        owner.state=dict(phase='terminal-ready',bindings=dict(actor=deepcopy(fixture.BINDING)),
            cleanup=[dict(kind='admission',operationClock=avatar_operation_clock.begin(owner.epoch_ms(),owner.monotonic()))])
        # Reuse the existing publisher fixture's explicit modeled original
        # boundary. No Final/native callback or lifecycle verdict is replaced.
        def original(_owner,value):return self.f.validate_original(value)
        owner.terminal_witness_original=MethodType(original,owner)

    def publisher(self):
        owner=self.feature
        result=AvatarWitnessPublisher(PrivateFeatureState(self.f.root/('phase-publication-avatar-people-'+owner.run+'-actor.json')),
            owner.state['bindings']['actor'],owner.phase,owner.lock,owner.cleanup_deadline,owner.terminal_witness_original,
            epoch_ms=owner.epoch_ms,monotonic=owner.monotonic)
        self.assertTrue(result.resolve());return result

    def test_same_resolved_publisher_survives_separate_feature_metadata_cas_and_reads_fresh_phase(self):
        owner=self.feature
        with self.f.lock.held():
            publisher=self.publisher();before=dict(generation=1);owner.store.write(before,None)
            owner.store.write(dict(generation=2),before);original=self.f.original();calls,request=self.f.posts('normal')
            phase=deepcopy(self.f.phase.previous);validations=self.f.validations
            with patch.object(self.f.actor,'request',side_effect=request):
                self.assertEqual(1,owner.publish_terminal_witness(publisher,original))
            self.assertEqual(1,len(calls));self.assertEqual(1,len(publisher.state['records']))
            self.assertNotEqual(phase['requestId'],self.f.phase.previous['requestId'])
            self.assertGreater(self.f.validations,validations)
            self.assertEqual(dict(generation=2),owner.store.read())

    def test_changed_publisher_cas_never_sends_a_sample(self):
        owner=self.feature
        with self.f.lock.held():
            publisher=self.publisher();original=self.f.original();calls,request=self.f.posts('normal')
            changed=deepcopy(publisher.previous);changed['fixtureUrl']+='-foreign'
            publisher.store.write(changed,publisher.previous)
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(NativeUIError):
                owner.publish_terminal_witness(publisher,original)
            self.assertEqual([],calls)

    def test_changed_live_phase_never_sends_a_sample(self):
        # An actual server phase change cannot be hidden behind the old
        # resolved publisher's prior PhaseFixtureReader snapshot.
        owner=self.feature
        with self.f.lock.held():
            publisher=self.publisher();original=self.f.original();calls,request=self.f.posts('normal')
            self.f.server.journal.activate(self.f.run,'b'*32,'cleanup',{})
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(NativeUIError):
                owner.publish_terminal_witness(publisher,original)
            self.assertEqual([],calls)

    def test_foreign_binding_and_replaced_callback_deadline_clock_or_lock_cannot_borrow_publisher(self):
        owner=self.feature
        with self.f.lock.held():
            publisher=self.publisher();original=self.f.original();calls,request=self.f.posts('normal')
            fields=dict(terminal_witness_original=owner.terminal_witness_original,cleanup_deadline=owner.cleanup_deadline,
                monotonic=owner.monotonic,lock=owner.lock)
            for fault in ('binding','callback','deadline','clock','lock'):
                binding=deepcopy(owner.state['bindings']['actor'])
                try:
                    if fault=='binding':owner.state['bindings']['actor']['generation']+=1
                    elif fault=='callback':owner.terminal_witness_original=MethodType(lambda _self,value:self.f.validate_original(value),owner)
                    elif fault=='deadline':owner.cleanup_deadline=MethodType(lambda _self:0.,owner)
                    elif fault=='clock':owner.monotonic=lambda:time.monotonic()
                    else:owner.lock=ScriptSourceLock(self.f.lock.path)
                    with self.subTest(fault=fault),patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(NativeUIError):
                        owner.publish_terminal_witness(publisher,original)
                    self.assertEqual([],calls)
                finally:
                    owner.state['bindings']['actor']=binding
                    for name,value in fields.items():setattr(owner,name,value)


if __name__=='__main__':unittest.main()
