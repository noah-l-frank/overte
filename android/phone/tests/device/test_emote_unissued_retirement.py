"""Original failed admission and watcher-only retirement; no device use."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_retirement
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_emote_actor import PhoneEmoteActor
from overte_phone_emote_retirement import PhoneEmoteRetirement
from overte_phone_script_history import unpack,pack
from test_emote_pixels import POLICY
from test_emote_sources import RUN


class UnissuedRetirementTests(unittest.TestCase):
    setUp=test_emote_retirement.EmoteRetirementTests.setUp
    owner=test_emote_retirement.EmoteRetirementTests.owner
    prepared=test_emote_retirement.EmoteRetirementTests.prepared
    publication_server=test_emote_retirement.EmoteRetirementTests.publication_server
    actor_run=test_emote_retirement.EmoteRetirementTests.actor_run

    def failed(self,fault='world'):
        self.server,self.reader,self.client=self.publication_server();m=self.model
        original=m.call
        def call(*args,**kwargs):
            value=original(*args,**kwargs);value['fixtureUrl']=self.client.url+'/runs/'+RUN+'/';return value
        m.call=call
        if fault=='world':m.admission_fault='wrong-domain'
        elif fault=='cache':m.inventory.resources[0]['model']['sha256']='f'*64
        else:self.assertEqual('tablet',fault);m.widgets.tablet=True
        self.primary=self.owner()
        with self.assertRaises(NativeUIError):self.primary.prepare()
        self.assertEqual(dict(view='unissued',scene='unissued'),self.primary.state['setup'])
        self.model.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=17,runId=RUN))
        return PhoneEmoteActor(self.actor_run(self.client),POLICY)

    def closed(self,fault='world'):
        flow=self.failed(fault);before=self.model.calls.count('native-read');work=len(self.model.work_commands)
        self.assertFalse(flow.step());self.assertIsNone(flow.store.read())
        self.reader.request('/runs/'+RUN,method='DELETE');self.assertTrue(flow.step())
        self.assertEqual('unadmitted',flow.state['phase']);self.assertIsNone(flow.state['last']);self.assertIsNone(flow.state['quiet'])
        self.assertEqual(before,self.model.calls.count('native-read'));self.assertEqual(work,len(self.model.work_commands))
        self.assertEqual(3,flow.previous['emoteActorVersion']);return flow

    def finish(self):
        with self.primary.lock.held():
            self.primary.load();owner=PhoneEmoteRetirement(self.primary,POLICY)
            self.assertEqual('unissued',owner.state['mode'])
            with patch.object(owner,'retire_resources',side_effect=AssertionError('Unissued resources queried native restoration')),\
                    patch.object(self.model,'_native_feature_observer',side_effect=AssertionError('Ownership-only cleanup queried native facts')),\
                    patch.object(self.model,'_script_work',side_effect=AssertionError('Ownership-only cleanup invented quiet proof')):
                self.assertEqual({'performed':True},owner.finalize())
            return owner

    def test_failed_initial_world_admission_transfers_owned_journals_without_native_peer_or_quiet_verdict(self):
        flow=self.closed();header=deepcopy(flow.previous);before=self.model.calls.count('native-read')
        self.assertTrue(flow.step());self.assertEqual(header,flow.previous);self.assertEqual(header,flow.store.read())
        owner=self.finish();self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))
        self.assertEqual(before,self.model.calls.count('native-read'));self.assertEqual([],self.model.controls.input_requests)
        self.assertTrue(owner.state['verification'].startswith('unissued/'))
        handoff=PrivateFeatureState(next(self.model.root.glob('emote-retirement-handoff-*.json'))).read()
        state=unpack(handoff['retirementHeader']['payload'])[0]
        self.assertEqual('unissued',state['mode']);self.assertFalse(any(item['key'].startswith('work/') for item in state['items']))

    def test_failed_cache_after_real_baseline_can_retire_only_explicitly_unissued_resources(self):
        self.closed('cache');self.assertIsNotNone(self.primary.state['baseline']);self.finish()
        self.assertEqual([],self.setup_calls);self.assertEqual([],self.model.controls.input_requests)
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))

    def test_initial_unowned_tablet_survives_without_native_idle_or_dismissal_claim(self):
        self.closed('tablet');self.assertTrue(self.model.widgets.tablet);owner=self.finish()
        self.assertTrue(self.model.widgets.tablet);self.assertEqual([],self.model.tablet_inputs)
        self.assertEqual('unissued',owner.state['mode'])

    def test_unadmitted_terminal_cannot_hide_later_actor_source_role_or_capture_ownership(self):
        flow=self.closed();root=self.model.root
        for name in ('phone-emote-actor-role.json','phone-emote-actor-sources-segment-1.json','phone-emote-actor-capture-unknown.json','phone-emote-actor-sources-segment-99.json'):
            store=PrivateFeatureState(root/name);store.write(dict(unknown=True),None)
            with self.subTest(name=name),self.assertRaises(NativeUIError):flow.step()
            self.assertEqual(dict(unknown=True),store.read());store.discard(store.read())
        self.assertTrue(flow.step())

    def test_ignored_unissued_controller_deletion_retries_exact_originals_with_a_new_provider_observation(self):
        self.closed()
        with self.primary.lock.held():
            self.primary.load();owner=PhoneEmoteRetirement(self.primary,POLICY)
            with patch.object(owner.store,'discard',side_effect=OSError('Synthetic lost unissued controller removal')),self.assertRaises(OSError):owner.finalize()
            self.assertIsNotNone(owner.store.read());self.assertIsNone(self.primary.store.read())
        first=next(self.model.root.glob('emote-retirement-handoff-*.json'));original=first.read_bytes()
        owner=self.finish();self.assertEqual(2,owner.state['attempts']);self.assertEqual(original,first.read_bytes())
        self.assertEqual(2,len(list(self.model.root.glob('emote-retirement-handoff-*.json'))))


    def test_actor_v2_cannot_borrow_the_new_unadmitted_terminal_meaning(self):
        flow=self.closed();header=deepcopy(flow.previous);header['emoteActorVersion']=2
        flow.store.write(header,flow.previous)
        with self.assertRaises(NativeUIError):PhoneEmoteActor(self.actor_run(self.client),POLICY).step()
        self.assertEqual(header,flow.store.read())

    def test_retirement_v1_remains_observed_and_cannot_infer_unissued_success(self):
        self.closed()
        with self.primary.lock.held():
            self.primary.load();owner=PhoneEmoteRetirement(self.primary,POLICY);owner.save()
            legacy=deepcopy(owner.previous);legacy['emoteRetirementVersion']=1
            state=unpack(legacy['payload'])[0];state.pop('mode');legacy['payload']=pack([state]);owner.store.write(legacy,owner.previous)
            before=self.model.calls.count('native-read');current=PhoneEmoteRetirement(self.primary,POLICY)
            self.assertEqual('observed',current.state['mode']);self.assertEqual(legacy,current.store.read())
            with self.assertRaises(NativeUIError):current.finalize()
            self.assertEqual(before,self.model.calls.count('native-read'));self.assertEqual(legacy,current.store.read())
