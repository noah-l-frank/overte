"""Compact journal references retain unchanged original Sample and record DTOs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.emote_observer import IOSEmoteObserver
from ios.self_tests.emote_active_observer_fixture import ActiveObserverFixture


class ObserverSampleTests(unittest.TestCase):
    def rebuild(self,f):
        return IOSEmoteObserver(f.observer.store,f.sources,f.observer.binding,'primary',f.root,f.policy,f.phase,f.lock,
            lambda:True,samples=f.samples,epoch_ms=f.scope.epoch_ms,monotonic=f.scope.monotonic)

    def test_v2_journal_keeps_original_sample_file_reference_and_record_bytes(self):
        f=ActiveObserverFixture(self);public=f.observer.observe(0);before=f.observer.record_store(1).path.read_bytes()
        owner=self.rebuild(f);ref=owner.state['lastImage']
        self.assertEqual({'iosEmoteSampleReferenceVersion','requestId','sha256'},set(ref))
        self.assertEqual(2,owner.previous['iosEmoteObserverVersion']);self.assertEqual(1,owner.original(owner.state['records'][0])['iosEmoteObservationOriginalVersion'])
        self.assertEqual(public,owner.validate_original(dict(iosEmoteObservationReferenceVersion=1,**owner.state['records'][0]))['public'])
        self.assertEqual(before,owner.record_store(1).path.read_bytes())

    def test_literal_v1_full_sample_owner_remains_readable_and_migrates_only_metadata(self):
        f=ActiveObserverFixture(self);f.observer.observe(0);owner=f.observer;state=deepcopy(owner.state)
        state['lastImage']=owner.sample(state['lastImage']);record_bytes=owner.record_store(1).path.read_bytes()
        legacy=dict(iosEmoteObserverVersion=1,runId=owner.run,role='primary',binding=owner.binding,
            primaryBinding=f.sources.binding,fixtureUrl=f.phase.fixture_url,phaseInstance=owner.decoder.phase_instance,
            artifactRoot=str(f.root),imagePolicy=f.policy,payload=pack([state]))
        owner.store.write(legacy,owner.previous);rebuilt=self.rebuild(f)
        self.assertEqual(1,rebuilt.previous['iosEmoteObserverVersion']);self.assertIn('iosEmoteSampleReferenceVersion',rebuilt.state['lastImage'])
        rebuilt.save();self.assertEqual(2,rebuilt.previous['iosEmoteObserverVersion'])
        self.assertEqual(record_bytes,rebuilt.record_store(1).path.read_bytes())

    def test_tampered_hash_foreign_request_and_unknown_reference_version_fail_closed(self):
        f=ActiveObserverFixture(self);f.observer.observe(0);owner=f.observer;original=deepcopy(owner.previous)
        for field,value in (('sha256','0'*64),('requestId','ios-'+'0'*32),('iosEmoteSampleReferenceVersion',True),('iosEmoteSampleReferenceVersion',2)):
            state=deepcopy(owner.state);state['lastImage'][field]=value
            bad=dict(original,payload=pack([state]));owner.store.write(bad,original)
            with self.subTest(field=field,value=value),self.assertRaises(NativeUIError):self.rebuild(f)
            owner.store.write(original,bad)


if __name__=='__main__':unittest.main()
