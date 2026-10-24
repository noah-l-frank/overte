"""Original publication ownership, immutable carriers and interrupted recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_observer import WorldWebObserver
from ios.self_tests.world_web_sources_fixture import SDK,RUN


class WorldWebObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.sdk=SDK()
        self.source_store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json');self.store=PrivateFeatureState(self.root/'ios-world-web-primary-observer.json')
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def observer(self,source):
        return WorldWebObserver(self.store,source,dict(primary='http://controlled.invalid',foreign='http://foreign.invalid'),lambda:True)
    def test_actual_baseline_native_original_publication_and_fresh_reconstruction(self):
        with self.held():
            source=self.sdk.owner(self.source_store,self.lock);owner=self.observer(source);ref,observed=owner.capture()
            self.assertEqual([],observed['public']['resources']);self.assertFalse(observed['public']['state']['open'])
            self.assertEqual(ref['reference']['index'],observed['public']['sequence']);self.assertEqual(RUN,observed['public']['runId'])
            fresh=self.observer(self.sdk.owner(self.source_store,self.lock))
            self.assertEqual(observed,fresh.validate_original(ref));second,_=fresh.capture();self.assertEqual(2,second['reference']['index'])
    def test_actual_record_bytes_are_rechecked_after_success_and_returned_values_do_not_alias(self):
        with self.held():
            owner=self.observer(self.sdk.owner(self.source_store,self.lock));ref,observed=owner.capture();expected=deepcopy(observed)
            observed['public']['state']['open']=True;self.assertEqual(expected,owner.validate_original(ref))
            store=owner.record_store(1);before=store.read();changed=deepcopy(before);entries=unpack(changed['payload']);entries[0]['ticket']='f'*32;changed['payload']=pack(entries);store.write(changed,before)
            with self.assertRaises(NativeUIError):owner.validate_original(ref)
    def test_unknown_passive_observation_retains_owned_intent_and_uses_distinct_new_source(self):
        with self.held():
            source=self.sdk.owner(self.source_store,self.lock);owner=self.observer(source);self.sdk.fail='geometry'
            with self.assertRaises(NativeUIError):owner.capture()
            first=deepcopy(owner.state['pending']);self.sdk.fail=None
            ref,_=owner.capture();self.assertEqual(first,owner.state['interrupted'][0]);self.assertEqual(1,ref['reference']['index'])
            self.assertEqual(1,len(source.state['interrupted']));self.assertGreater(len(source.state['interrupted'][0]['nativeQueries']),0)

    def test_literal_legacy_writer_before_capture_stays_readable_without_partial_scope_semantics(self):
        with self.held():
            owner=self.observer(self.sdk.owner(self.source_store,self.lock))
            # Configure the actual historical producer before its first
            # original. No completed packet or source identity is relabeled.
            owner.version=1
            reference,measured=owner.capture();original=deepcopy(owner.previous)
            self.assertEqual(1,original['iosWorldWebObserverVersion'])
            rebuilt=self.observer(self.sdk.owner(self.source_store,self.lock))
            self.assertEqual(original,rebuilt.previous);self.assertEqual(measured,rebuilt.validate_original(reference))
            entry=deepcopy(rebuilt.entries()[0]);entry['scope']={}
            with self.assertRaises(NativeUIError):rebuilt.derive(entry)


if __name__=='__main__':unittest.main()
