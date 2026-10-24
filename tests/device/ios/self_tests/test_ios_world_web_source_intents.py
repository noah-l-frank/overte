"""Unqualified pending writes never replace actual full original validation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebSourceIntentTests(unittest.TestCase):
    def test_matching_but_foreign_process_pending_raw_can_be_journaled_but_never_decoded_or_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);sdk=SDK();lock=ScriptSourceLock(root/'script-feature-sources.lock')
            caught=None
            with lock.held():
                try:
                    source=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock);sdk.fail='world'
                    with self.assertRaises(NativeUIError):source.capture('interrupted-native-original')
                    query=source.state['pending']['nativeQueries'][0];raw=json.loads(query['raws'][0]);raw['processId']+=1;query['raws'][0]=json.dumps(raw)
                    source.save() # This is only a durable unknown passive raw.
                    with self.assertRaises(NativeUIError):source.decode(source.previous)
                    with self.assertRaises(NativeUIError):sdk.owner(source.store,lock,historical=True)
                    self.assertEqual([],source.state['records'])
                except Exception as error:caught=error
            if caught is not None:raise caught


    def test_warm_native_decode_cache_still_reopens_actual_chunk_inode_even_when_bytes_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);sdk=SDK();lock=ScriptSourceLock(root/'script-feature-sources.lock');caught=None
            with lock.held():
                try:
                    source=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock);reference=source.capture('real-original');source.frame(reference)
                    from adapters.script_feature.history import unpack
                    row=unpack(source.record_store(1).read()['payload'])[0];part=row['originals']['keys'];store=source.parts.store('keys');path=store.path(store.expand(part['chunks'][0]))
                    replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
                    with self.assertRaises(NativeUIError):source.frame(reference)
                except Exception as error:caught=error
            if caught is not None:raise caught

    def test_returned_browser_prefix_cannot_mutate_an_active_validated_read_round(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);sdk=SDK();lock=ScriptSourceLock(root/'script-feature-sources.lock');caught=None
            with lock.held():
                try:
                    source=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock);reference=source.capture('real-original')
                    with source.validation_round():
                        frames=source.browser_frames();frames[0]['ledger']['complete']=False
                        self.assertTrue(source.browser_frames()[0]['ledger']['complete']);self.assertTrue(source.frame(reference)['originals']['ledgerAfter']['complete'])
                except Exception as error:caught=error
            if caught is not None:raise caught

    def test_public_decode_does_not_alias_private_borrowed_cache_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);sdk=SDK();lock=ScriptSourceLock(root/'script-feature-sources.lock');caught=None
            with lock.held():
                try:
                    source=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock);reference=source.capture('real-original')
                    with source.validation_round():
                        _,frames=source.decode(source.previous);frames[0]['label']='poisoned-public-decode'
                        self.assertEqual('real-original',source.frame(reference)['label'])
                    self.assertEqual('real-original',source.frame(reference)['label'])
                except Exception as error:caught=error
            if caught is not None:raise caught


if __name__=='__main__':unittest.main()
