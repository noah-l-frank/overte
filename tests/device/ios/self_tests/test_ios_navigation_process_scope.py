"""Real private restart/source journals and normal UI; SDK/kernel modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,places_controls
from ios.adapters.navigation_process_scope import NavigationProcessScope,owner_path,NAMES
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
from ios.self_tests import test_ios_navigation_process_owner as process_tests
from ios.self_tests.test_ios_navigation_address_inputs import RetainedBoundary
from ios.self_tests.test_ios_places_controls import row as place_row


class NavigationProcessScopeTests(unittest.TestCase):
    def setUp(self):
        self.h=process_tests.NavigationProcessOwnerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.lock=self.h.lock
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def scope(self):
        owner=self.h.owner();self.h.take(owner);return NavigationProcessScope(owner)

    def sdk(self,scope):
        basis=scope.archive();floor=basis['originals']['ui'];b=RetainedBoundary()
        b.native_boundary.pid=43;b.native_boundary.instance=floor['instance']
        # The old shared test boundary hardcodes PID 42 in edit receipts.
        # This explicitly modeled second SDK reports its actual current PID.
        original_post=b.native_boundary.post
        def native_post(request,timeout):
            result=original_post(request,timeout)
            if 'status' in b.native_boundary.receipt:
                b.native_boundary.receipt['status']['processId']=b.native_boundary.pid
            return result
        b.native_boundary.post=native_post
        b.source_sequence=floor['navigationDialogSourceSequence']
        b.sequence_native=b.native_boundary.sequence=floor['lastSequence']
        b.native_epoch=lambda:floor['sampleEpochMs']+100+round(b.clock*1000)
        old=b.observed;counter=floor['placesSourceSequence'];root=str(uuid.uuid4())
        def observed():
            nonlocal counter
            packet=old();counter+=1
            packet.update(processId=43,placesControlsVersion=2,placesSourceSequence=counter,
                elapsedMs=floor['elapsedMs']+100+round(b.clock*1000))
            if b.screen=='places':
                page=place_row('places.page');page.update(profile=places_controls.PROFILES[2],rootId=root,
                    checked=None,rowIndex=None,popup='none',frame=dict(x=1,y=1,width=100,height=100))
                packet['controls'].append(page)
            return packet
        b.observed=observed;return b,b.native()

    def test_actual_new_floor_and_original_static_baseline_are_distinct_and_no_sources_are_reread(self):
        with self.held():
            scope=self.scope();reads=list(self.h.reads);before=deepcopy(scope.owner.store.read())
            basis=scope.archive();initial=scope.original_admission()
            self.assertEqual('43',basis['binding']['processIdentity']);self.assertEqual('42',initial['binding']['processIdentity'])
            self.assertNotIn('iosNavigationSceneAdmissionVersion',basis)
            self.assertEqual(self.h.proof.initial,initial);self.assertEqual(self.h.proof.initial['bookmarkBaseline'],basis['bookmarkBaseline'])
            self.assertEqual(reads,self.h.reads);self.assertEqual(before,scope.owner.store.read())
            paths=[owner_path(scope,name) for name in NAMES]
            self.assertEqual(len(NAMES),len(set(paths)));self.assertTrue(all(path.name.endswith('-43.json') and not path.exists() for path in paths))

    def test_partial_historical_or_changed_current_process_cannot_supply_a_live_scope(self):
        with self.held():
            pending=self.h.owner()
            with self.assertRaises(NativeUIError):NavigationProcessScope(pending)
            self.h.take(pending);scope=NavigationProcessScope(pending);before=list(self.h.reads)
            with self.assertRaises(NativeUIError):NavigationProcessScope(self.h.owner(historical=True))
            self.h.okay=False
            with self.assertRaises(NativeUIError):scope.archive()
            self.assertEqual(before,self.h.reads)

    def test_normal_surface_open_close_after_restart_uses_new_source_and_separate_input_journal(self):
        with self.held():
            scope=self.scope();b,native=self.sdk(scope);initial=deepcopy(scope.original_admission())
            path=owner_path(scope,'ios-navigation-surface-actions.json');old_path=path.with_name('ios-navigation-surface-actions.json')
            old=PrivateFeatureState(old_path);old.write({'retainedOldProcessInput':True},None);old_bytes=old_path.read_bytes()
            def owner():return NavigationSurfaceActions(PrivateFeatureState(path),scope,b.ui,native,monotonic=lambda:b.clock)
            def action(verb):
                ticket=uuid.uuid4().hex;self.h.proof.h.h.fixture.harness.client.activate(ticket,verb,{})
                return dict(contractVersion=16,runId=scope.run,ticket=ticket,verb=verb,inputs={},fixtureUrl=scope.fixture.fixture_url)
            with patch.object(normal_input,'urlopen',b.post):
                current=owner();self.assertEqual({'performed':True},current.act(action('open')))
                self.assertEqual('places',b.screen);self.assertEqual('43',current.binding['processIdentity'])
                current=owner();self.assertEqual({'performed':True},current.act(action('close')))
                self.assertIsNone(b.screen);self.assertEqual(2,len(current.state['actions']))
                self.assertTrue(all(row['before']['processId']==43 for row in current.state['actions']))
                old_packet=deepcopy(self.h.proof.before['originals']['ui'])
                with self.assertRaises(NativeUIError):current.packet(old_packet)
                current_packet=deepcopy(current.state['actions'][-1]['after'])
                for key in ('placesSourceSequence','navigationDialogSourceSequence'):
                    bad=deepcopy(current_packet);bad[key]=1
                    with self.subTest(source=key),self.assertRaises(NativeUIError):current.packet(bad)
            self.assertEqual(old_bytes,old_path.read_bytes());self.assertEqual(initial,scope.original_admission())

    def test_sealed_basis_keeps_live_original_checks_and_cannot_hide_mutated_owner_or_cache(self):
        with self.held():
            scope=self.scope();original=scope.archive();initial=scope.original_admission()
            # Callers receive copies, while the exact source carrier remains
            # checked on every cache use without refreshing any old clock.
            changed=scope.archive();changed['originals']['ui']['processId']=42
            self.assertEqual(original,scope.archive());self.assertEqual(initial,scope.original_admission())
            saved=deepcopy(scope.owner.state);scope.owner.state['context']['currentScope']['originalsSha256']='0'*64
            with self.assertRaises(NativeUIError):scope.archive()
            scope.owner.state=saved
            scope._basis['binding']['processIdentity']='42'
            with self.assertRaises(NativeUIError):scope.archive()

    def test_runtime_factories_share_actual_new_process_context_and_refuse_foreign_candidate(self):
        with self.held():
            scope=self.scope();b,native=self.sdk(scope)
            source=dict(binding=scope.binding,check=lambda:scope.bound(),client=b,session=scope.binding['sessionId'],native=native,
                observer=SimpleNamespace(navigation_state=lambda _:scope.sources['navigation'],places_model=lambda _:scope.sources['model']),clock_source=None)
            class Runtime(IOSNavigationRuntime):
                def _sources(_self,_selector):return source
                def state_path(_self,_selector):return scope.store.path.with_name('session.json')
            runtime=object.__new__(Runtime)
            composite=runtime._navigation_composite_actions('actual-existing',scope)
            missing=runtime._navigation_missing_actions('actual-existing',scope)
            original_return=runtime._navigation_process_return('actual-existing',scope)
            self.assertIs(scope,original_return.scope);self.assertIsNone(original_return.store.read())
            self.assertIs(scope,composite.admission);self.assertIs(scope,composite.places.scope)
            self.assertIs(scope,missing.admission);self.assertTrue(composite.store.path.name.endswith('-43.json'))
            self.assertEqual(43,composite.navigation.pid);self.assertIsNone(composite.store.read());self.assertIsNone(missing.store.read())
            source['binding']=dict(scope.binding,artifactSha256='f'*64)
            with self.assertRaises(NativeUIError):runtime._navigation_surface_actions('foreign',scope)
            self.assertEqual([],b.inputs)


if __name__=='__main__':unittest.main()
