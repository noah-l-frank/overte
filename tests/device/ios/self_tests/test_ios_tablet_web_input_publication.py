"""Completed ordinary input orders independent acquisition, never its facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT
from ios.self_tests.test_ios_tablet_web_app_origin import BINDING


class TabletInputPublicationTests(unittest.TestCase):
    def setUp(self):
        self.feature=object.__new__(IOSTabletWebFeature);self.feature.binding=deepcopy(BINDING);self.feature.run=RUN
        self.phase=dict(status=dict(active=True),verb='open',ticket='b'*32,inputs={})
        self.reads=[]
        def phase():self.reads.append('actual-phase');return deepcopy(self.phase)
        self.observer=SimpleNamespace(observer=SimpleNamespace(phase=SimpleNamespace(read=phase),source=SimpleNamespace(fixture=ROOT)))
        self.state=dict(phase='active',initial={},cleanupBefore=None,cleanupStop=None,quiet=[],cleanupOriginal=None,lastCall=None,filesReleased=False)
        self.header=dict(tabletWebFeatureVersion=1,binding=deepcopy(BINDING),runId=RUN,role='primary',setupSha256='c'*64,origins={},screen=None)
    def primary(self):return dict(self.header,payload=pack([self.state]))
    def call(self,**changes):
        return dict(dict(contractVersion=16,runId=RUN,ticket=self.phase['ticket'],fixtureUrl=ROOT,verb='open',inputs={}),**changes)
    def test_missing_or_previous_call_cannot_publish_under_new_ticket(self):
        self.assertFalse(self.feature.input_returned(self.observer,self.primary()))
        self.state['lastCall']=self.call(ticket='c'*32)
        self.assertFalse(self.feature.input_returned(self.observer,self.primary()))
        self.assertEqual(['actual-phase']*2,self.reads)
    def test_actual_matching_return_only_allows_later_independent_acquisition(self):
        self.state['lastCall']=self.call();before=deepcopy(self.state)
        self.assertTrue(self.feature.input_returned(self.observer,self.primary()))
        self.assertEqual(before,self.state)
        self.assertNotIn('public',self.state);self.assertNotIn('facts',self.state)
    def test_baseline_does_not_require_an_input_or_invent_one(self):
        self.phase.update(verb='baseline',ticket='c'*32)
        self.assertTrue(self.feature.input_returned(self.observer,self.primary()))
        self.assertTrue(self.feature.input_returned(self.observer,None))
        self.assertIsNone(self.state['lastCall'])
    def test_missing_primary_owner_cannot_publish_an_activated_action(self):
        self.assertFalse(self.feature.input_returned(self.observer,None))
    def test_same_ticket_foreign_operands_binding_or_malformed_call_fail_closed(self):
        for fault in ('verb','inputs','fixture','run','binding','version'):
            self.state['lastCall']=self.call();value=self.primary()
            if fault=='verb':self.state['lastCall']['verb']='reload';value=self.primary()
            elif fault=='inputs':self.state['lastCall']['inputs']={'unexpected':'actual-operand'};value=self.primary()
            elif fault=='fixture':self.state['lastCall']['fixtureUrl']='http://foreign.invalid/';value=self.primary()
            elif fault=='run':self.state['lastCall']['runId']='f'*32;value=self.primary()
            elif fault=='binding':value['binding']['generation']+=1
            else:value['tabletWebFeatureVersion']=True
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                self.feature.input_returned(self.observer,value)
    def test_retired_or_cleanup_phase_does_not_bypass_own_cleanup_originals(self):
        self.state['lastCall']=self.call();self.phase['status']['active']=False
        with self.assertRaises(NativeUIError):self.feature.input_returned(self.observer,self.primary())
        self.phase['status']['active']=True;self.state['phase']='quiet'
        with self.assertRaises(NativeUIError):self.feature.input_returned(self.observer,self.primary())


if __name__=='__main__':unittest.main()
