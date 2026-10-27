"""One literal Source construction, guarded through readonly child assembly.

Real files and existing typed native models execute; no native/SDK or device
qualification follows from these construction and ownership counterexamples.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import cProfile
import pstats
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_construction import construct
from ios.adapters.world_web_sources import WorldWebSources
from ios.self_tests import test_ios_world_web_sources as source_fixture


class WorldWebConstructionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=source_fixture.WorldWebSourcesTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def initial(self):
        f=self.fixture;source=f.sdk.owner(f.store,f.lock)
        return [source.capture('baseline'),source.capture('second')]
    def test_one_complete_constructor_read_and_independent_public_frames(self):
        f=self.fixture
        with f.held():
            references=self.initial();profile=cProfile.Profile();profile.enable()
            try:
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)) as source:
                    self.assertEqual(2,len(source.frames))
                    source.frames[0]['label']='public-copy-mutation'
                    for reference in references:
                        source.retained(reference);frame=source.frame(reference)
                        frame['label']='returned-copy-mutation'
                    self.assertEqual('baseline',source.frame(references[0])['label'])
            finally:profile.disable()
            code=WorldWebSources._decode_frames.__code__
            stats=pstats.Stats(profile).stats[(code.co_filename,code.co_firstlineno,code.co_name)]
            self.assertEqual(1,stats[1]);self.assertIsNone(source._round)
            self.assertIsNone(source._construction)
            self.assertEqual('baseline',source.frame(references[0])['label'])
    def test_factory_state_or_private_frame_mutation_cannot_borrow_constructor_proof(self):
        f=self.fixture
        with f.held():
            self.initial()
            for part in ('state','frame','extra-key'):
                def changing():
                    source=f.sdk.owner(f.store,f.lock,historical=True)
                    if part=='state':source.state['interrupted'].append(dict(fake=True))
                    elif part=='frame':next(iter(source._cache.values()))['label']='changed-private-frame'
                    else:source._cache[('extra',)]=dict(fake=True)
                    return source
                with self.subTest(part=part),self.assertRaises(NativeUIError):
                    with construct(changing):self.fail('Changed constructor result must not escape')
    def test_unknown_file_and_same_byte_carrier_replacement_are_refused(self):
        f=self.fixture
        with f.held():
            self.initial()
            with self.assertRaises(NativeUIError):
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)):
                    (f.root/'unknown-construction-file').write_bytes(b'unknown')
            # The next context owns its new actual inventory, then catches
            # replacement during use even though the record bytes are equal.
            with self.assertRaises(NativeUIError):
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)) as source:
                    path=source.record_store(1).path;retained=path.with_name(path.name+'.retained-original')
                    path.rename(retained);path.write_bytes(retained.read_bytes());path.chmod(0o600)
    def test_lost_tag_clears_own_round_but_never_clears_a_foreign_round(self):
        f=self.fixture
        with f.held():
            self.initial()
            with self.assertRaises(NativeUIError):
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)) as source:
                    source._construction=None
            self.assertIsNone(source._round);self.assertIsNone(source._round_pins)
            foreign=(None,{},[])
            with self.assertRaises(NativeUIError):
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)) as source:
                    source._round=foreign
            self.assertIs(foreign,source._round)
            with self.assertRaises(NativeUIError):
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)) as source:
                    next(iter(source._cache.values()))['label']='changed-during-readonly-assembly'
            self.assertIsNone(source._round)
    def test_changed_decoder_and_existing_owner_keep_literal_validation(self):
        f=self.fixture
        with f.held():
            refs=self.initial();literal=WorldWebSources.decode;calls=[]
            def changed(owner,value):calls.append(owner);return literal(owner,value)
            with patch.object(WorldWebSources,'decode',changed):
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)) as source:
                    self.assertIsNone(source._construction);self.assertEqual('baseline',source.frame(refs[0])['label'])
            self.assertEqual([source],calls)
            with construct(lambda:source) as existing:
                self.assertIs(source,existing);self.assertIsNone(existing._construction)
    def test_changed_validator_only_mutates_the_literal_public_predecessor_copy(self):
        f=self.fixture
        with f.held():
            refs=self.initial();literal=WorldWebSources.validate_frame
            def changing(owner,frame,previous=None):
                value=literal(owner,frame,previous)
                if previous is not None:previous['label']='literal-predecessor-copy'
                return value
            with patch.object(WorldWebSources,'validate_frame',changing):
                with construct(lambda:f.sdk.owner(f.store,f.lock,historical=True)) as source:
                    self.assertEqual('literal-predecessor-copy',source.frames[0]['label'])
                    self.assertEqual('baseline',source.frame(refs[0])['label'])


if __name__=='__main__':unittest.main()
