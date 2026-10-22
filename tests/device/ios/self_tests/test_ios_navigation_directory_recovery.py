"""Retained first-open originals and actual HTTP/JS materialization; SDK modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_places_state import directory_proof
from ios.self_tests import test_ios_navigation_observation_owner as fixture
from ios.self_tests.test_ios_places_settings import row as control
from navigation_observation import viewpoint_urls


class NavigationDirectoryRecoveryTests(unittest.TestCase):
    setUp=fixture.NavigationObservationOwnerTests.setUp
    child=fixture.NavigationObservationOwnerTests.child
    index=fixture.NavigationObservationOwnerTests.index
    activate=fixture.NavigationObservationOwnerTests.activate
    owner=fixture.NavigationObservationOwnerTests.owner
    take=fixture.NavigationObservationOwnerTests.take

    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except BaseException as caught:error=caught
        if error is not None:raise error

    def opened(self):
        self.activate('c'*32);native_barrier=self.sdk.gpu.epoch()
        provider_barrier=self.fixture.status()['capturedEpochMs']
        self.http_source.begin(self.harness.origin)
        status,raw,response=self.harness.get('/api/v1/places?status=online&per_page=1000')
        self.assertEqual(200,status);self.http_source.response(raw,response)
        # Existing helper executes the original places.js processing and QML
        # filter in Node. It never manufactures the expected normalized rows.
        page=self.http_source.model(raw,origin=self.harness.origin,run=self.run)['roots'][0]
        page.update(bookmarkAddresses={},popup='none',serverDraft='');page['lists']['bookmarks']['rows']=[]
        self.model_source.pages=[page];self.model_source.shown=True
        mutate=self.model_source.mutate
        def current(value):
            mutate(value);value['preferences']['metaverseOrigin']=self.harness.origin
        self.model_source.mutate=current
        capture=self.ui.capture
        def shown():
            value=capture();value['tabletShown']=True;value['controls']=[]
            for name in ('places.page','places.search'):
                item=control(name);item.update(rootId=page['rootId'],qmlSource=page['qmlSource'],
                    frame=dict(x=10,y=20,width=300,height=40))
                if name=='places.search':item['value']=''
                value['controls'].append(item)
            return value
        self.ui.capture=shown;owner=self.owner()
        with self.assertRaises(NativeUIError):self.take(owner)
        self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(owner.state['phaseAfter'])
        originals=owner.state['originals']
        proof=directory_proof(owner.binding,dict(http=originals['http'],model=originals['model'],
            provider=owner.state['phaseAfter']['originals']['navigation']),dict(runId=self.run,ticket='c'*32,
                inputs=self.harness.inputs,origin=self.harness.origin,nativeAfterEpochMs=native_barrier,
                providerAfterEpochMs=provider_barrier,afterEvent=0))
        return owner,proof

    def test_complete_old_group_gains_only_its_exact_directory_join_without_reads_or_new_clock(self):
        with self.held():
            owner,proof=self.opened();originals=deepcopy(owner.state['originals']);clock=deepcopy(owner.state['clockJoin'])
            commands=deepcopy(self.gpu.commands);reads=self.ui.reads;self.sdk.gpu.sleep(5.)
            rebuilt=self.owner(owner.request);rebuilt.recover(directory=proof);actual=rebuilt.archive()
            self.assertTrue(actual['state']['panel'])
            self.assertEqual([proof['materialized']['record']['id']],actual['state']['searchResults'])
            self.assertEqual(originals,rebuilt.state['originals']);self.assertEqual(clock,rebuilt.state['clockJoin'])
            self.assertEqual(commands,self.gpu.commands);self.assertEqual(reads,self.ui.reads)
            self.assertEqual(actual,self.owner(owner.request,historical=True).archive())

    def test_independently_valid_later_directory_proof_cannot_replace_this_groups_sources(self):
        with self.held():
            owner,proof=self.opened();old=deepcopy(owner.store.read())
            later=self.http_source.reader().read(self.run)
            changed=deepcopy(proof);changed['originals']['http']=later
            changed=directory_proof(owner.binding,changed['originals'],changed['admission'])
            with self.assertRaises(NativeUIError):owner.recover(directory=changed)
            self.assertEqual(old,owner.store.read());self.assertIsNone(owner.state['options']['directory'])
            owner.recover(directory=proof);self.assertTrue(owner.archive()['state']['panel'])

    def test_ignored_open_cannot_be_recovered_by_importing_a_directory_proof(self):
        with self.held():
            owner,proof=self.opened();owner.recover(directory=proof)
            # A new original acquisition actually observes a closed tablet.
            # A genuine old proof remains provenance, never requested openness.
            self.model_source.shown=False;self.model_source.pages=[]
            self.ui.capture=fixture.UI.capture.__get__(self.ui,fixture.UI)
            next_owner=self.owner(previous=owner)
            result=next_owner.acquire('c'*32,viewpoint_urls(self.harness.inputs['sceneUrl'])['A'],'A',
                1_000_000+self.sdk.gpu.clock*1000-1,baseline=self.baseline,provider_inputs=self.harness.inputs,directory=proof)
            self.assertFalse(result['state']['panel']);self.assertEqual([],result['state']['searchResults'])


if __name__=='__main__':unittest.main()
