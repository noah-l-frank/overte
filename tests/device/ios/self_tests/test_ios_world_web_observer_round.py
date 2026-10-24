"""Round-local pure reuse preserves actual files, headers and outward aliases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as original_reads
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack
from ios.self_tests import test_ios_world_web_observer as fixture


class WorldWebObserverRoundTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.WorldWebObserverTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)

    def test_closed_browser_borrow_and_scoped_measurement_have_no_outward_alias(self):
        f=self.fixture
        with f.held():
            source=f.sdk.owner(f.source_store,f.lock);owner=f.observer(source);ref,expected=owner.capture()
            before=deepcopy(source.frames)
            with patch.object(source,'derive_browser',wraps=source.derive_browser) as derived:
                with owner.validation_round():
                    first=owner.validate_original(ref);first['public']['state']['open']=True
                    self.assertEqual(expected,owner.validate_original(ref));self.assertEqual(1,derived.call_count)
                self.assertEqual(expected,owner.validate_original(ref));self.assertEqual(2,derived.call_count)
            self.assertEqual(before,source.frames)
            state=source.derive_browser(origins=owner.origins);state['public']['open']=True
            self.assertFalse(source.derive_browser(origins=owner.origins)['public']['open'])

    def test_actual_live_dom_derivation_cannot_mutate_private_original_document(self):
        from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
        from ios.adapters.world_web_identity import WorldWebLease
        whole=ComposedWorldWeb();self.addCleanup(whole.close);source=whole.source
        actions=whole.actions();actions.act(whole.sdk.activate('open',{}));entry=actions.state['calls'][-1]
        lease=WorldWebLease(whole.scope,source,entry['before'],entry['after']);owned=lease.packet()
        arguments=dict(ownership=owned['files'],directory=owned['directory'],entity=owned['returned']['returned']['entityId'],origins=whole.sdk.origins)
        actual=source.derive_browser(**arguments);expected=deepcopy(actual)
        self.assertIsNotNone(actual['document']);actual['document']['source']['dom']['editor']['text']='poisoned external document'
        actual['public']['text']='poisoned external projection';arguments['ownership']['runId']='f'*32
        owned=lease.packet()
        self.assertEqual(expected,source.derive_browser(ownership=owned['files'],directory=owned['directory'],entity=owned['returned']['returned']['entityId'],origins=whole.sdk.origins))

    def test_equal_byte_original_replacement_is_rejected_on_warm_measurement(self):
        f=self.fixture
        with f.held():
            source=f.sdk.owner(f.source_store,f.lock);owner=f.observer(source);ref,_=owner.capture()
            path=source.record_store(1).path;raw=path.read_bytes()
            with self.assertRaises(NativeUIError),owner.validation_round():
                owner.validate_original(ref)
                replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
                owner.validate_original(ref)

    def test_warm_owner_header_and_actual_observation_membership_cannot_change(self):
        f=self.fixture
        with f.held():
            source=f.sdk.owner(f.source_store,f.lock);owner=f.observer(source);ref,_=owner.capture()
            with self.assertRaises(NativeUIError),owner.validation_round():
                owner.validate_original(ref);owner.origins['foreign']='http://changed.invalid';owner.validate_original(ref)
            owner.origins['foreign']='http://foreign.invalid'
            with self.assertRaises(NativeUIError),owner.validation_round():
                owner.validate_original(ref);owner.record_store(1).path.unlink();owner.validate_original(ref)

    def test_fresh_original_membership_requires_actual_derivation_instead_of_memo_hit(self):
        f=self.fixture
        with f.held():
            source=f.sdk.owner(f.source_store,f.lock);owner=f.observer(source);ref,expected=owner.capture()
            with patch.object(source,'derive_browser',wraps=source.derive_browser) as derived,owner.validation_round():
                owner.validate_original(ref)
                with original_reads(fresh=True) as paths:self.assertEqual(expected,owner.validate_original(ref))
                self.assertEqual(2,derived.call_count);self.assertIn(owner.record_store(1).path,paths)
            self.assertEqual(expected,owner.validate_original(ref))

    def test_replaced_prewarmed_parent_blocks_first_new_native_send(self):
        f=self.fixture;f.sdk.use_snapshot=True
        with f.held():
            source=f.sdk.owner(f.source_store,f.lock);owner=f.observer(source);owner.capture()
            frame=source.frame(source.state['records'][-1]);path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0]
            old=path.read_bytes();native=len(f.sdk.native.commands);snapshots=len(f.sdk.snapshot_native.commands);capture=owner._capture
            def replace(**arguments):
                replacement=path.with_suffix('.replacement');replacement.write_bytes(old);replacement.chmod(0o600);replacement.replace(path)
                return capture(**arguments)
            with patch.object(owner,'_capture',side_effect=replace),self.assertRaises(NativeUIError):owner.capture()
            self.assertEqual(native,len(f.sdk.native.commands));self.assertEqual(snapshots,len(f.sdk.snapshot_native.commands))

    def test_genuine_future_actor_capture_cannot_be_previous_primary_observation_floor(self):
        from ios.adapters.world_web_observer import WorldWebObserver
        from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
        from ios.self_tests.world_web_actor_fixture import IndependentActor
        whole=ComposedWorldWeb();self.addCleanup(whole.close);actor=IndependentActor(whole);self.addCleanup(actor.close)
        owner=WorldWebObserver(PrivateFeatureState(actor.root/'ios-world-web-actor-observer.json'),actor.primary,whole.sdk.origins,lambda:True,role='actor',peer=actor.peer)
        owner.capture();second,expected=owner.capture();self.assertEqual(expected,owner.validate_original(second))
        actual_future=actor.peer.capture('genuine-later-own-sdk-original')
        store=owner.record_store(1);previous=store.read();changed=deepcopy(previous);rows=unpack(changed['payload'])
        rows[0]['peer']=actual_future;changed['payload']=pack(rows);store.write(changed,previous)
        owner.state['records'][0]['sha256']=digest(changed);owner.save()
        with self.assertRaises(NativeUIError):owner.validate_original(second)


if __name__=='__main__':unittest.main()
