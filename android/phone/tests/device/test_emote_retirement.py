"""Whole ownership transfer with real source/role/work and explicit resource doubles.

View/Scene measurement internals are covered by test_emote_view/scene. These
cases double only that resource boundary; no product or device claim is made.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_actor
from test_emote_pixels import POLICY
from test_emote_sources import RUN
from adapters.normal_ui import NativeUIError
from overte_phone_emote_actor import PhoneEmoteActor
from overte_phone_emote_retirement import PhoneEmoteRetirement
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_script_history import same,unpack


class EmoteRetirementTests(unittest.TestCase):
    setUp=test_emote_actor.EmoteActorTests.setUp
    owner=test_emote_actor.EmoteActorTests.owner
    prepared=test_emote_actor.EmoteActorTests.prepared
    publication_server=test_emote_actor.EmoteActorTests.publication_server
    actor_run=test_emote_actor.EmoteActorTests.actor_run
    start=test_emote_actor.EmoteActorTests.start

    def closed(self,*,mixed_failures=False):
        flow=self.start();self.assertFalse(flow.step())
        with self.primary.lock.held():PhoneEmoteRole(self.primary,'primary',POLICY).read(0)
        self.model.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=18,runId=RUN));self.primary.cleanup_quiet('primary')
        self.assertFalse(flow.step());self.assertEqual('drained',flow.state['phase'])
        with self.primary.lock.held():
            role=PhoneEmoteRole(self.primary,'primary',POLICY);role.read(role.state['sequence'])
        if mixed_failures:
            with flow.run.lock.held():
                flow.run.load();role=PhoneEmoteRole(flow.run,'actor',POLICY);intent=role.originals.intent
                def role_lost(kind,value):
                    intent(kind,value)
                    if value['phase']=='opened':raise OSError('Synthetic interrupted role original')
                role.originals.intent=role_lost
                with self.assertRaises(OSError):role.read(role.state['sequence'])
                source=flow.run.source('actor');intent=source.originals.intent
                def source_lost(kind,value):
                    intent(kind,value)
                    if value['phase']=='opened':raise OSError('Synthetic interrupted source original')
                source.originals.intent=source_lost
                with self.assertRaises(OSError):source.read()
        self.reader.request('/runs/'+RUN,method='DELETE')
        self.assertTrue(PhoneEmoteActor(self.actor_run(self.client),POLICY).step())
        return self.primary

    def resource_boundary(self,owner):
        # These are explicitly doubled component proofs, never native facts.
        # Mandatory before-delete handoff and actual filesystem disappearance
        # still run, including the real namespace original replay.
        for key in ('scene','view'):
            name='phone-emote-'+key+'.json';saved=owner.get(key)
            if saved is None:
                saved=dict(unitResourceBoundaryVersion=1,header=owner.original(name))
                owner.retain(key,saved)
            self.assertTrue(same(saved['header'],owner.original(name)))
            actual=owner.file(name).read()
            if actual is not None:owner.file(name).discard(actual)
            self.assertIsNone(owner.file(name).read())
        lease=owner.namespace();lease.retire_closed(lambda proof:owner.retain('namespace',proof),retained=owner.get('namespace'))
        owner.retain('resources/'+str(owner.state['attempts']),dict(unitResourceBoundaryVersion=1))

    def finish(self,run=None):
        run=self.primary if run is None else run
        with run.lock.held():
            run.load();owner=PhoneEmoteRetirement(run,POLICY)
            with patch.object(owner,'retire_resources',side_effect=lambda:self.resource_boundary(owner)):
                result=owner.finalize()
            return owner,result

    def test_frozen_original_dependency_handoff_precedes_verified_whole_metadata_retirement(self):
        run=self.closed();owner,result=self.finish(run)
        self.assertEqual({'performed':True},result)
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))
        self.assertTrue(list(self.model.root.glob('emote-frame-retirement-*.json')))
        self.assertTrue(list(self.model.root.glob('emote-frame-sources-*.json')))
        self.assertGreaterEqual(owner.state['attempts'],1)
        self.assertIsNotNone(owner.state['verification'])
        from adapters.normal_feature_state import PrivateFeatureState
        handoff=PrivateFeatureState(next(self.model.root.glob('emote-retirement-handoff-*.json'))).read()
        self.assertEqual(1,handoff['emoteRetirementHandoffVersion'])
        state=unpack(handoff['retirementHeader']['payload'])[0]
        self.assertEqual(owner.state['items'],state['items']);self.assertEqual(owner.state['verification'],state['verification'])
        before=self.model.calls.count('native-read')
        with run.lock.held(),self.assertRaises(NativeUIError):owner.sources[('primary',0)].read_closed(lambda _:None)
        self.assertEqual(before,self.model.calls.count('native-read'))

    def test_ignored_metadata_deletion_retains_parent_and_never_reports_success(self):
        run=self.closed()
        with run.lock.held():
            run.load();owner=PhoneEmoteRetirement(run,POLICY);original=owner.file
            def ignored(name):
                store=original(name)
                if name=='phone-emote-primary-role.json':store.discard=lambda _previous:None
                return store
            with patch.object(owner,'retire_resources',side_effect=lambda:self.resource_boundary(owner)),patch.object(owner,'file',side_effect=ignored):
                with self.assertRaises(NativeUIError):owner.finalize()
            self.assertIsNotNone(owner.store.read());self.assertIsNotNone(original('phone-emote-primary-role.json').read())
        self.finish(run);self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))

    def test_partial_original_and_lost_saved_return_resume_exact_bytes_before_new_measurement(self):
        run=self.closed()
        with run.lock.held():
            run.load();owner=PhoneEmoteRetirement(run,POLICY);intent=owner.storage_intent
            def lost(kind,value):
                intent(kind,value)
                if value['phase']=='opened':raise OSError('Synthetic interrupted retirement original')
            owner.originals.intent=lost
            with self.assertRaises(OSError):owner.finalize()
            self.assertIsNotNone(owner.store.read());self.assertEqual('opened',owner.state['pending']['original']['phase'])
            retained=deepcopy(owner.state['pending']);path=owner.originals.path(retained['original'])
            self.assertTrue(path.exists());self.assertEqual(0,path.stat().st_size)
        owner,_result=self.finish(run)
        item=next(item for item in owner.state['items'] if item['key']==retained['key'])
        self.assertEqual(retained['original']['file'],{key:item['original'][key] for key in ('device','inode')})

    def test_unknown_or_foreign_control_cannot_be_erased_by_whole_retirement(self):
        run=self.closed()
        from adapters.normal_feature_state import PrivateFeatureState
        unknown=PrivateFeatureState(self.model.root/'phone-emote-foreign-scope.json');unknown.write(dict(foreign=True),None)
        with self.assertRaises(NativeUIError):self.finish(run)
        self.assertEqual(dict(foreign=True),unknown.read());self.assertTrue(run.store.path.exists())

    def test_readonly_retirement_context_cannot_send_normal_inputs_or_modify_source_history(self):
        run=self.closed()
        with run.lock.held():
            run.load();owner=PhoneEmoteRetirement(run,POLICY);source=owner.source();role=owner.role('primary');life=owner.lifetime(source)
            controls=deepcopy(self.model.controls.input_requests);header=deepcopy(source.previous)
            for call in (lambda:source.read(),lambda:source.save(),lambda:role.read(0),lambda:role.inputs.act({}),lambda:life.read()):
                with self.assertRaises(NativeUIError):call()
            self.assertEqual(controls,self.model.controls.input_requests);self.assertEqual(header,source.store.read())


    def test_lost_final_controller_removal_reobserves_native_state_after_all_child_controls_are_gone(self):
        run=self.closed()
        with run.lock.held():
            run.load();owner=PhoneEmoteRetirement(run,POLICY)
            with patch.object(owner,'retire_resources',side_effect=lambda:self.resource_boundary(owner)),                    patch.object(owner.store,'discard',side_effect=OSError('Synthetic lost controller retirement')):
                with self.assertRaises(OSError):owner.finalize()
            self.assertTrue(all(owner.file(name).read() is None for name in owner.names))
            self.assertIsNotNone(owner.store.read());self.assertIsNone(run.store.read())
            first=next(self.model.root.glob('emote-retirement-handoff-*.json'));original=first.read_bytes()
        before=self.model.calls.count('native-read');resumed,_result=self.finish(run)
        self.assertGreater(self.model.calls.count('native-read'),before)
        self.assertEqual(original,first.read_bytes());self.assertEqual(2,len(list(self.model.root.glob('emote-retirement-handoff-*.json'))))
        self.assertGreater(resumed.state['attempts'],1);self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))

    def test_missing_independent_actor_lifecycle_cannot_be_recreated_from_role_or_backend_receipts(self):
        run=self.closed()
        from adapters.normal_feature_state import PrivateFeatureState
        store=PrivateFeatureState(self.model.root/'phone-emote-actor-lifecycle.json');store.discard(store.read())
        with self.assertRaises(NativeUIError):self.finish(run)
        self.assertTrue(run.store.path.exists());self.assertTrue((self.model.root/'phone-emote-actor-role.json').exists())

    def test_changed_original_source_file_stops_recovery_before_any_new_native_read(self):
        run=self.closed()
        with run.lock.held():
            run.load();owner=PhoneEmoteRetirement(run,POLICY);retain=owner.retain
            def interrupted(key,value):
                retain(key,value)
                if key=='control/phone-emote-run.json':raise OSError('Synthetic interrupted control handoff')
            with patch.object(owner,'retain',side_effect=interrupted),self.assertRaises(OSError):owner.finalize()
            self.assertIsNotNone(owner.store.read())
        path=next(self.model.root.glob('emote-frame-sources-*.json'));path.write_bytes(b'{}')
        before=self.model.calls.count('native-read')
        with self.assertRaises(NativeUIError):self.finish(run)
        self.assertEqual(before,self.model.calls.count('native-read'));self.assertTrue(run.store.path.exists())


    def test_mixed_failed_source_and_role_originals_are_replayed_and_handed_off_without_measurement_promotion(self):
        run=self.closed(mixed_failures=True)
        with run.lock.held():
            run.load()
            from overte_phone_emote_failures import PhoneEmoteFailures
            failure=PhoneEmoteFailures(run)
            rows=failure.originals.restore(failure.state['manifests'],failure.state['count'])
            self.assertEqual(['admission','source','role'],[row['kind'] for row in rows])
            self.assertEqual(2,rows[1]['archive']['emoteSourceFailureArchiveVersion'])
            self.assertEqual(2,rows[2]['archive']['emoteRoleFailureArchiveVersion'])
            files={path:path.read_bytes() for path in self.model.root.glob('emote-frame-source-failures-*.json')}
        owner,_result=self.finish(run)
        self.assertTrue(files)
        self.assertEqual(files,{path:path.read_bytes() for path in files})
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))
        self.assertTrue(any(item['key']=='control/phone-emote-failures.json' for item in owner.state['items']))
