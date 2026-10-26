"""Actual ownership/admission decoders with explicit SDK/native host models.

No native/device execution or claim of two real processes. Fake host PIDs only
exercise role refusal; whole independent-worker qualification is still pending.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime,FACTORIES
from ios.adapters.tablet_web_observer import TabletWebDOMDisposition
from ios.adapters.tablet_web_dom import IOSTabletWebDOM
from ios.self_tests import test_ios_tablet_web_context as bootstrap_tests
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS
from ios.self_tests.test_ios_tablet_web_sources import ROOT,RUN
from feature_journeys.witness import Client


class TabletWebRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=bootstrap_tests.TabletWebContextTests('test_bootstrap_original_raw_precedes_interpretation_and_reconstructs_actual_native_birth')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root/'sdk';self.root.mkdir(mode=0o700)
        self.runtime=object.__new__(IOSTabletWebRuntime);self.runtime._existing=self.fixture.admission.existing
        self.runtime.state_path=lambda _:self.root/'session.json'
        actual=self.fixture.admission.runtime.adapter;scope=self.fixture.admission.fixture.scope
        self.runtime.adapter=SimpleNamespace(_binding=actual._binding,_candidate_guard=lambda:None,
            read_session=lambda _:dict(sessionId=scope['sessionId']),_scope=lambda *_:deepcopy(scope))
        self.factories=[];self.transports=[]
        outer=self
        class Transport:
            def __init__(self,client,session,target,process,**kwargs):
                self.process=process;self.clock=kwargs;outer.transports.append(self)
            def native_observer(self):self.process();return outer.fixture.reader()
            def bound_native_observer(self,clock):
                self.process();return NativeFeatureObservation(outer.fixture.native.send,outer.fixture.native.original,lambda:100000,
                    lambda:self.process() is not None,42,ios=True,native_clock_bound=True,monotonic=lambda:0.,sleep=lambda _:None)
        for name,method in FACTORIES.items():
            def factory(transport,clock,name=name):
                transport.process();outer.factories.append(name)
                if name=='dom':return IOSTabletWebDOM(lambda _:None,lambda:'',lambda:100000,lambda:True,42)
                return SimpleNamespace(pid=42)
            setattr(Transport,method,factory)
        self.patch=patch('ios.adapters.tablet_web_runtime.FeatureObservation',Transport);self.patch.start();self.addCleanup(self.patch.stop)
        self.client=Client(ROOT.split('/runs/')[0],'a'*64)
    def opened(self,role='primary'):
        return self.runtime.observer_runtime('private-existing-selector',RUN,role,self.client,ORIGINS,self.fixture.binding,self.fixture.setup,
            epoch_ms=lambda:90000,monotonic=lambda:0.,sleep=lambda _:None)
    def test_actual_existing_admission_bootstrap_and_all_source_factories_without_app_or_session_mutation(self):
        raw=self.fixture.admission.fixture.store.path.read_bytes();before=len(self.fixture.native.commands)
        with self.opened() as observer:
            self.assertEqual(FACTORIES.keys(),observer.observer.readers.keys())
            self.assertIsInstance(observer.observer.readers['dom'],TabletWebDOMDisposition)
            self.assertEqual([],observer.observer.source.state['apps']);self.assertEqual('returned',observer.bootstrap.state['status'])
            check=observer.observer.source.guard;self.assertTrue(check())
        with self.assertRaises(NativeUIError):check()
        self.assertEqual(before+1,len(self.fixture.native.commands));self.assertEqual(raw,self.fixture.admission.fixture.store.path.read_bytes())
        self.assertEqual([],list(self.root.glob('*app-files*')))
        self.assertEqual(list(FACTORIES),self.factories)
        # Reentry in the same real host process keeps the exact original
        # bootstrap; current SDK/candidate admission is performed separately.
        with self.opened() as rebuilt:self.assertEqual('returned',rebuilt.bootstrap.state['status'])
        self.assertEqual(before+1,len(self.fixture.native.commands))
    def test_cleanup_input_recovery_without_journal_creates_nothing_or_native_query(self):
        with self.opened() as observer:
            path=self.root/('tabletweb-inputs-'+RUN+'-primary.json');self.assertFalse(path.exists())
            before=len(self.fixture.native.commands);self.assertIsNone(observer.recover_inputs())
            self.assertFalse(path.exists());self.assertEqual(before,len(self.fixture.native.commands))
    def test_actor_cleanup_input_recovery_cannot_read_or_write_primary_journal(self):
        from ios.adapters.tablet_web_runtime import TabletRuntimeObserver
        observer=object.__new__(TabletRuntimeObserver)
        observer.observer=SimpleNamespace(source=SimpleNamespace(role='actor',bound=lambda:True))
        with patch('ios.adapters.tablet_web_runtime.PrivateFeatureState',side_effect=AssertionError('Actor must not access a Primary input journal')):
            self.assertIsNone(observer.recover_inputs())

    def test_actor_requires_real_primary_context_and_distinct_original_host_birth(self):
        with self.opened():pass
        before=len(self.fixture.native.commands)
        with self.assertRaises(NativeUIError),self.opened('actor'):pass
        self.assertEqual(before+1,len(self.fixture.native.commands))
        # Refusal retains the Actor's actual issued/returned bootstrap rather
        # than deleting it or claiming that this was an independent process.
        self.assertTrue((self.root/('tabletweb-context-'+RUN+'-actor.json')).exists())
    def test_missing_or_changed_setup_and_current_session_do_not_create_an_sdk_or_repair_binding(self):
        with self.opened():pass
        original=deepcopy(self.fixture.setup);self.fixture.setup['instance']='0'*32
        before=len(self.fixture.native.commands)
        with self.assertRaises(NativeUIError),self.opened():pass
        self.assertEqual(before,len(self.fixture.native.commands));self.fixture.setup=original
        self.runtime.adapter.read_session=lambda _:dict(sessionId='foreign-session')
        with self.assertRaises(NativeUIError),self.opened():pass
        self.assertEqual(before,len(self.fixture.native.commands))


if __name__=='__main__':unittest.main()
