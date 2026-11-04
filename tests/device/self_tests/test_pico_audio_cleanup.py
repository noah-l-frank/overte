"""Actual host source/archive ownership; Android, UI and media are SDK models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import unittest

from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_cleanup_io import PicoAudioCleanupIO1
from adapters.pico4.audio_cleanup_owner import PicoAudioCleanupOwner1
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1
from adapters.host_process_identity import host_identity
from self_tests.test_pico_chat_restart_io import RestartBoundary

TARGET='explicit-audio-boundary'

def configuration(root):return ('declared-pico-audio-layer',root)

def selected_fixture(case,*,selected=True):
    from self_tests.test_audio_preview import BINDING
    from self_tests.test_pico_audio_pages import BRIDGE
    from self_tests.test_pico_audio_page_owner import Boundary
    from self_tests.test_pico_audio_recipe import AudioRecipeFixture
    from self_tests.test_pico_audio_pc_start import AudioPCStartTests
    def boundary(path,**fields):
        binding=dict(BINDING,sessionId=BRIDGE,targetFingerprint=hashlib.sha256(
            (TARGET+'\x00'+str(configuration(path))).encode()).hexdigest())
        return Boundary(path,**fields,binding=binding)
    class Recipe(AudioRecipeFixture):boundary_factory=staticmethod(boundary)
    class PCFixture(AudioPCStartTests):
        recipe_fixture=Recipe
        def create_cleanup_budget(self):
            self.budget=None
            if selected:
                began=time.monotonic()
                self.budget=AudioCleanupBudget1(dict(picoAudioCleanupProfileVersion=1,runId=self.f.run,
                    binding=deepcopy(self.f.native.binding),hostProcessIdentity=host_identity(),
                    startedMonotonic=began,deadlineMonotonic=began+120),self.f.native.lock)
            return self.budget
    fixture=PCFixture();case.addCleanup(fixture.doCleanups);fixture.setUp();return fixture

class _SDK(RestartBoundary):
    """Cold low-level SDK data model; all original IO/parser/bank logic runs."""
    def __init__(self,fixture,*,grow=False,delay=0):
        audio=fixture.f.native;root=fixture.f.path
        self.audio=audio;self.selected_budget=fixture.budget;self.grow=grow;self.delay=delay;self.did_growth=False
        self.pico_configuration=configuration(root);self.cold_binding=deepcopy(audio.binding)
        self.profile=dict(package='org.overte.pico',e2e_activity='org.overte.pico/.E2eLauncherActivity')
        self.adb=self;self.target=TARGET;self.identity=self.cold_binding['processIdentity']
        self.running=True;self.effect=True;self.lost=None;self.trace=[];self.commands=[]
        self.session=audio.session;self.digest=self.cold_binding['artifactSha256']
        self.command=[sys.executable,'-c',"print('PID\\n123')"]
        self.settings_send=audio.owner().settings.send
    def binding(self):return deepcopy(self.cold_binding)
    def _installation(self,target):
        self.require(target);sampler=self.selected_budget.sampler
        if self.grow and sampler is not None and getattr(sampler,'partial_output',None) is not None and not self.did_growth:
            with (self.audio.path/'actual-growth-at-final-candidate.bin').open('wb') as stream:stream.truncate(16*1024*1024)
            self.did_growth=True
        return dict(schemaVersion=1,installedCandidateVerified=True,
            sourceRevision=self.cold_binding['sourceRevision'],artifactSha256=self.digest)
    def epoch_milliseconds(self,target):self.require(target);return self.audio.epoch()
    def write_control_command(self,target,identity,operation,request):
        self.require(target);self.commands.append(('send',deepcopy(request)))
        if identity!=self.identity:raise ValueError('Declared candidate identity changed')
        if request['action']=='feature-native-observe':self.audio.native.send(request)
        elif request['action']=='feature-audio-settings-observe':self.settings_send(request)
        else:raise ValueError('Only original read-only Audio SDK commands selected')
    def read_debug_app_file(self,target,package,path,attempts):
        self.require(target);self.commands.append(('read',path))
        if package!='org.overte.pico' or attempts!=1:raise ValueError('Declared Audio SDK ABI changed')
        if path.endswith('/feature-native-observation.json'):
            if self.delay:time.sleep(self.delay)
            return self.audio.native.original()
        if path.endswith('/feature-audio-settings.json'):return self.audio.settings.read()
        if path.endswith('/navigation-ui-observation.json'):return json.dumps(self.audio.capture())
        raise ValueError('Unexpected original source filename')

class AudioCleanupTests(unittest.TestCase):
    def sampler(self,*,handback=True,preserve=True,grow=False,delay=0):
        self.fixture=selected_fixture(self);self.budget=self.fixture.budget
        self.sdk=_SDK(self.fixture,grow=grow,delay=delay)
        self.io=PicoAudioCleanupIO1(self.sdk,TARGET,self.budget,monotonic=time.monotonic);self.addCleanup(self.io.close_host)
        sampler=self.budget.create_old_sampler(self.io)
        seal=self.budget.book_decode_seal(sampler,success_handback=handback,preserve_other_decode=preserve)
        return sampler,seal
    def test_default_none_actor_still_observes_original_owner(self):
        fixture=selected_fixture(self,selected=False);fixture.owner.prepare();frame=fixture.actor.observe()
        self.assertIsNone(fixture.actor.cleanup_budget);self.assertEqual('observation',frame['kind'])
        self.assertIsNone(fixture.actor.state['pending']);self.assertFalse(fixture.actor.raws.stopped)
    def test_selected_budget_is_registered_in_original_raw_family_before_source_io(self):
        sampler,seal=self.sampler();self.assertIs(self.budget.actor,self.fixture.actor)
        self.assertIs(self.budget.sampler,sampler);self.assertIs(self.budget.restart_io,self.io)
        self.assertEqual([],self.io.references);self.assertEqual([],self.sdk.commands)
        self.assertLessEqual(seal.metadata_bound,self.budget.decode_seal_metadata)
        self.assertEqual(262144,self.budget.decode_seal_metadata)
    def test_unprepared_common_factory_refuses_before_credit_or_getter(self):
        self.sampler();owner=PicoAudioCleanupOwner1(self.fixture.owner,self.budget,self.fixture.f.source,
            action_started=time.monotonic(),monotonic=time.monotonic);self.addCleanup(owner.close_host)
        reads=self.fixture.actor.raws.state['reads']
        with self.assertRaises(NativeUIError):self.budget.create_common_cleanup()
        self.assertEqual(0,self.budget.common_credit);self.assertIsNone(self.budget.common_owner)
        self.assertEqual(reads,self.fixture.actor.raws.state['reads']);self.assertEqual([],self.sdk.commands)
    def test_three_original_literals_precede_successful_closed_handback(self):
        sampler,seal=self.sampler();raw=sampler.sample();value=json.loads(raw)
        self.assertEqual(1,value['sequence']);self.assertEqual('old',value['epoch'])
        self.assertEqual(3,len(self.io.references));self.assertEqual([],self.fixture.actor.raws.state['pending'])
        self.assertIsNone(seal.active);self.assertIsNone(seal.staged)
        self.assertEqual(seal.retained,self.budget.decode_hold);self.assertIs(raw,sampler.last_output)
        for row in self.io.references:self.assertTrue(self.fixture.actor.raws.literal(row['reference']))
    def test_eight_samples_preserve_reader_roots_and_replace_only_own_work(self):
        sampler,seal=self.sampler()
        for index in range(8):
            raw=sampler.sample();self.assertEqual(index+1,json.loads(raw)['sequence'])
            self.assertEqual(seal.retained,self.budget.decode_hold);self.assertIsNone(seal.active)
        self.assertEqual(24,len(self.io.references));self.assertFalse(self.budget.failed)
    def test_default_false_keeps_conservative_decoder_sum(self):
        sampler,seal=self.sampler(handback=False,preserve=False);sampler.sample();first=self.budget.decode_hold
        sampler.sample();self.assertGreater(self.budget.decode_hold,first);self.assertEqual(0,seal.retained)
    def test_actual_extra_caller_graph_charge_survives_later_success(self):
        sampler,seal=self.sampler();sampler.sample()
        raw=self.fixture.actor.raws.literal(self.io.references[0]['reference'])
        self.budget.hold_decode(self.io,raw);self.side_graph=json.loads(raw)
        side=self.budget.decode_hold-seal.retained
        for _ in range(3):sampler.sample();self.assertEqual(side+seal.retained,self.budget.decode_hold)
        self.assertEqual('dict',type(self.side_graph).__name__)
    def test_actual_late_source_preserves_full_sum_and_first_traceback(self):
        sampler,seal=self.sampler(delay=1.6)
        with self.assertRaises(NativeUIError):sampler.sample()
        first=sampler.failure;gc.collect();self.assertIs(first,sampler.failure);self.assertIsNotNone(first[1])
        self.assertTrue(sampler.failed and self.budget.failed);self.assertIsNotNone(seal.active)
        self.assertIsNone(sampler.last_output);self.assertGreater(self.budget.decode_hold,0)
    def test_actual_final_candidate_corpus_growth_refuses_before_handback(self):
        sampler,seal=self.sampler(grow=True)
        with self.assertRaises(NativeUIError):sampler.sample()
        first=sampler.failure;gc.collect();self.assertTrue(self.sdk.did_growth)
        self.assertEqual(3,len(self.io.references));self.assertEqual([],self.fixture.actor.raws.state['pending'])
        self.assertIsNone(self.io.query);self.assertIsNotNone(sampler.partial_output)
        self.assertIsNotNone(seal.active);self.assertIsNotNone(seal.staged);self.assertEqual(0,seal.retained)
        self.assertEqual(0,sampler.sequence);self.assertIs(first,sampler.failure);self.assertIsNotNone(first[1])
    def test_actual_same_bytes_new_inode_after_success_refuses_next_source(self):
        sampler,_seal=self.sampler();sampler.sample();before=len(self.sdk.commands)
        path=self.fixture.actor.raws.path;replacement=path.with_name('actual-new-raw-root.json')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        with self.assertRaises(NativeUIError):sampler.sample()
        self.assertEqual(before,len(self.sdk.commands));self.assertTrue(sampler.failed)
