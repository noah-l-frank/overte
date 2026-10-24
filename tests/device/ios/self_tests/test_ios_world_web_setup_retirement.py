"""Unexecuted setup owns actual native/GPU/file originals without a lease.

Boundary producers are declared SDK/Qt/GPU models; original storage, clocks,
normal Scope cleanup and production owner/decoders remain real host code.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebSetupRetirementTests(unittest.TestCase):
    def fixture(self):
        f=FeatureWorldWeb();self.addCleanup(f.close)
        f.primary.observe(dict(contractVersion=16,runId=f.network.run,afterSequence=0))
        f.sdk.activate('cleanup',{})
        return f

    def test_actual_node_loaded_null_sdk_entity_return_retires_vm_without_invented_entity_or_renderer(self):
        f=FeatureWorldWeb();self.addCleanup(f.close);f.sdk.deny_entity_rez=True
        f.primary.observe(dict(contractVersion=16,runId=f.network.run,afterSequence=0))
        with self.assertRaises(NativeUIError):f.primary.act(f.sdk.activate('open',{}))
        self.assertTrue(f.whole.domain.running);self.assertIsNone(f.whole.domain.marker)
        self.assertEqual('loaded',f.sdk.node_work[0]['value']['event'])
        self.assertEqual(dict(entityId=None),f.sdk.node_work[0]['value']['payload'])
        self.assertIsNone(f.sdk.entity_calls[0]['entityId']);self.assertIsNone(f.sdk.page_source)
        f.sdk.activate('cleanup',{})
        failure=None
        with f.primary.held():
            try:
                f.primary.load();owner=f.primary.parts()['retirement']
                self.assertIs(type(owner),WorldWebSetupRetirement)
                original=owner.cleanup(f.sdk.ticket);owner.validate_original(original)
                proof=owner.qualification(owner.state)
                self.assertEqual('partial-execution',owner.scope.state['cleanupMode'])
                self.assertIsNone(proof['native']['returned']['returned']['entityId'])
                self.assertIsNone(proof['native']['returned']['birth'])
                self.assertEqual([],proof['native']['surfaces']);self.assertEqual([],proof['native']['leases'])
                self.assertEqual(['add-returned'],[row['kind'] for row in f.sdk.entity_calls])
                self.assertEqual('ending-finally',f.sdk.node_work[-1]['value']['event'])
                self.assertFalse(f.whole.domain.running);self.assertFalse(proof['public']['state']['open'])
                self.assertEqual(0,proof['pixels']['changedPixels'])
            except BaseException as original:
                # Keep the real failure visible outside the source lock's
                # intentionally closed public serialization error boundary.
                failure=original
        if failure is not None:
            # A nested shared source lock intentionally hides body exceptions
            # at its public boundary. Only this host diagnostic unwraps those
            # exact wrappers; production ownership and lock checks stay strict.
            seen=set()
            while (type(failure) is NativeUIError and str(failure) in (
                    'Script source serialization is unavailable',
                    'Original iOS geometry is unavailable or lost its native binding')
                    and failure.__context__ is not None and id(failure) not in seen):
                seen.add(id(failure));failure=failure.__context__
            raise failure from None

    def test_unexecuted_actual_scope_restoration_pixels_gpu_quiet_and_historical_rebuild(self):
        f=self.fixture()
        with f.primary.held():
            f.primary.load();parts=f.primary.parts();owner=parts['retirement']
            self.assertIs(type(owner),WorldWebSetupRetirement);self.assertIsNone(parts['lease'])
            original=owner.cleanup(f.sdk.ticket);measured=owner.validate_original(original)
            self.assertEqual('unloaded',owner.scope.state['cleanupMode'])
            self.assertIsNone(owner.scope.state['admission']);self.assertIsNone(owner.scope.state['fileOwnership'])
            self.assertEqual(['native-process-resources'],measured['scene']['remaining'])
            qualified=owner.qualification(owner.state)
            self.assertEqual([],qualified['held']);self.assertEqual([],qualified['public']['resources'])
            self.assertEqual(0,qualified['pixels']['changedPixels'])
            self.assertFalse(qualified['public']['state']['open'])
            self.assertEqual([],f.sdk.entity_calls)
            self.assertTrue(all(owner.values(row)['files'] is None for row in owner.state['records']))
            rebuilt=WorldWebSetupRetirement(owner.store,owner.scope,owner.observer,owner.baseline,
                baseline_image=owner.baseline_image,files=owner.files,sample_factory=owner.sample_factory,sleep=f.sdk.sleep)
            self.assertEqual(original,rebuilt.original())
            bad=deepcopy(original)
            # A removed restoration barrier cannot borrow the first quiet
            # sample's later timestamp as the before-pixels native proof.
            from adapters.script_feature.history import pack,unpack
            state=unpack(bad['owner']['payload'])[0];state['barrier']=None;bad['owner']['payload']=pack([state])
            with self.assertRaises(NativeUIError):rebuilt.validate_original(bad)

    def test_unknown_planned_component_birth_blocks_before_any_next_native_query(self):
        f=self.fixture()
        with f.primary.held():
            f.primary.load();owner=f.primary.parts()['retirement'];owner.scope.cleanup()
            owner.state.update(ticket=f.sdk.ticket,phase='cleaning');owner.save()
            original_parts=owner.parts
            def interrupted(row):
                store=original_parts(row);intent=store.intent
                def record(kind,value):
                    intent(kind,value)
                    if value['phase']=='planned':raise RuntimeError('Modeled crash after real durable original plan')
                store.intent=record;return store
            owner.parts=interrupted
            with self.assertRaisesRegex(RuntimeError,'durable original plan'):owner.capture()
            owner.parts=original_parts
            self.assertEqual('planned',owner.state['pending']['carrier']['phase'])
            previous=deepcopy(owner.previous);native=owner.source.native.sequence;requests=deepcopy(f.requests)
            with self.assertRaises(NativeUIError):owner.capture()
            self.assertEqual(previous,owner.previous);self.assertEqual(native,owner.source.native.sequence)
            self.assertEqual(requests,f.requests)


if __name__=='__main__':unittest.main()
