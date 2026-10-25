"""Whole observer pending classification preserves actual nine-source history."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_runtime import TabletRuntimeObserver,TabletObservationPending
from ios.adapters.tablet_web_observer import TabletWebObserver
from ios.adapters.tablet_web_source_owner import ORDER
from ios.self_tests import test_ios_tablet_web_source_owner as source_tests
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS


class TabletWebLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):source_tests.TabletWebSourceOwnerTests.setUpClass()
    def setUp(self):
        self.fixture=source_tests.TabletWebSourceOwnerTests('test_actual_nine_queries_raw_ownership_full_facts_and_historical_source_original_replay')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.boundary.frame['state'].update(iosTabletWebStateVersion=2,presentations=[])
    def runtime(self,app=True):
        source=self.fixture.prepare() if app else self.fixture.owner()
        boundary=self.fixture.boundary
        observer=TabletWebObserver(source,{name:boundary.reader(name) for name in ORDER},boundary.native(),boundary.phase,
            lambda:deepcopy(boundary.frame['browser']),ORIGINS)
        runtime=object.__new__(TabletRuntimeObserver);runtime.observer=observer;return runtime
    def test_actual_active_loading_document_is_owned_pending_without_publication_or_clock_relabel(self):
        self.fixture.boundary.frame['document'].update(status='unavailable',source={})
        runtime=self.runtime();source=runtime.observer.source
        with self.assertRaises(TabletObservationPending):runtime.capture_source()
        self.assertEqual(1,len(source.state['records']));self.assertFalse(source.blocked);self.assertEqual(0,self.fixture.boundary.posts)
        row=source.originals.read(source.originals.expand(source.state['records'][0]));self.assertEqual('returned',row['status'])
        self.assertEqual(self.fixture.boundary.epoch,row['nativeBefore']['capturedEpochMs']+100)
    def reject_view(self,fault):
        frame=self.fixture.boundary.frame;frame['document'].update(status='unavailable',source={})
        if fault=='foreign':frame['state']['otherLiveTablets']=1
        else:frame['state']['owners'][0]['current']['sourceCurrent']=False
        runtime=self.runtime()
        try:runtime.capture_source()
        except TabletObservationPending:self.fail('A foreign/unstamped view became pending')
        except NativeUIError:pass
        else:self.fail('A foreign/unstamped view produced a normalized fact')
    def test_foreign_native_owner_is_fatal_not_pending(self):self.reject_view('foreign')
    def test_unstamped_active_page_is_fatal_not_pending(self):self.reject_view('unstamped')
    def test_ready_page_without_own_original_app_vm_profile_cannot_be_pending_or_publish(self):
        runtime=self.runtime(app=False)
        try:runtime.capture_source()
        except TabletObservationPending:self.fail('Missing actual app VM profile became pending')
        except NativeUIError:pass
        else:self.fail('Ready page without app provenance qualified')
        self.assertEqual(0,self.fixture.boundary.posts)


if __name__=='__main__':unittest.main()
