"""Aborted setup ownership with actual sources/work and explicit resource doubles."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_retirement
from adapters.normal_ui import NativeUIError
from overte_phone_emote_actor import PhoneEmoteActor
from overte_phone_emote_retirement import PhoneEmoteRetirement
from overte_phone_script_history import unpack,pack
from test_emote_pixels import POLICY
from test_emote_sources import RUN


class SetupRetirementTests(unittest.TestCase):
    setUp=test_emote_retirement.EmoteRetirementTests.setUp
    owner=test_emote_retirement.EmoteRetirementTests.owner
    prepared=test_emote_retirement.EmoteRetirementTests.prepared
    publication_server=test_emote_retirement.EmoteRetirementTests.publication_server
    actor_run=test_emote_retirement.EmoteRetirementTests.actor_run

    def closed(self,stage):
        self.server,self.reader,self.client=self.publication_server();m=self.model;original=m.call
        def call(*args,**kwargs):
            value=original(*args,**kwargs);value['fixtureUrl']=self.client.url+'/runs/'+RUN+'/';return value
        m.call=call;self.setup_fault=stage;self.primary=self.owner()
        with self.assertRaises(NativeUIError):self.primary.prepare()
        self.assertFalse(self.primary.state['prepared']);self.assertIsNotNone(self.primary.state['admissionSha256'])
        self.setup_fault=None;m.journal.activate(RUN,'a'*32,'cleanup',{})
        self.primary.cleanup_resources(dict(contractVersion=17,runId=RUN));self.primary.cleanup_quiet('primary')
        self.assertFalse(self.primary.state['prepared']);flow=PhoneEmoteActor(self.actor_run(self.client),POLICY)
        self.assertFalse(flow.step());self.reader.request('/runs/'+RUN,method='DELETE');self.assertTrue(flow.step())
        self.assertEqual('unadmitted',flow.state['phase']);return self.primary

    def resource_boundary(self,owner):
        # Real View/Scene readers are exercised separately in test_emote_scene;
        # this doubles their completed transfer at the coordinator boundary.
        for key,flag in owner.owner_state['setup'].items():
            if flag=='issued':
                saved=owner.get(key)
                if saved is None:owner.retain(key,dict(unitResourceBoundaryVersion=1,header=owner.original('phone-emote-'+key+'.json')))
        owner.retire_namespace()
        owner.retain('resources/'+str(owner.state['attempts']),dict(unitResourceBoundaryVersion=1))

    def finish(self):
        with self.primary.lock.held():
            self.primary.load();owner=PhoneEmoteRetirement(self.primary,POLICY)
            self.assertEqual('setup',owner.state['mode'])
            with patch.object(owner,'retire_resources',side_effect=lambda:self.resource_boundary(owner)):
                self.assertEqual({'performed':True},owner.finalize())
            return owner

    def test_view_setup_abort_retains_only_owned_view_and_actual_primary_work(self):
        self.closed('view');self.assertEqual(dict(view='issued',scene='unissued'),self.primary.state['setup'])
        before=len(self.model.work_commands);owner=self.finish()
        keys={item['key'] for item in owner.state['items']}
        self.assertIn('view',keys);self.assertNotIn('scene',keys);self.assertIn('namespace',keys)
        self.assertGreater(len(self.model.work_commands),before);self.assertTrue(owner.state['verification'].startswith('work/'))
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))

    def test_scene_setup_abort_with_both_intents_is_distinct_from_completed_preparation(self):
        self.closed('scene');self.assertEqual(dict(view='issued',scene='issued'),self.primary.state['setup'])
        self.assertFalse(self.primary.state['prepared']);owner=self.finish()
        keys={item['key'] for item in owner.state['items']};self.assertTrue({'scene','view','namespace'}<=keys)
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))

    def test_legacy_both_issued_cleanup_cannot_borrow_new_failed_preparation_evidence(self):
        self.closed('scene')
        with self.primary.lock.held():
            legacy=deepcopy(self.primary.store.read());legacy['emoteRunVersion']=4
            state=unpack(legacy['payload'])[0];state.pop('prepared');legacy['payload']=pack([state])
            self.primary.store.write(legacy,self.primary.previous);self.primary.load()
            self.assertIsNone(self.primary.state['prepared']);owner=PhoneEmoteRetirement(self.primary,POLICY)
            self.assertEqual('observed',owner.state['mode']);before=self.model.calls.count('native-read')
            with self.assertRaises(NativeUIError):owner.finalize()
            self.assertEqual(before,self.model.calls.count('native-read'));self.assertEqual(legacy,self.primary.store.read())
