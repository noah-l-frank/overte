"""One prospective recovered Scene/Final -> held terminal connected host case.

TerminalDomain declares OS/SDK producers before capture; native/Qt/GPU remain
models. Canonical file-only verification is real, InstalledAdapter full dispatch
and device/native qualification remain outside this case.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from feature_journeys import terminal
from ios.adapters.avatar_terminal import AvatarTerminal
from ios.avatar_observer import run_flow
from ios.self_tests.avatar_terminal_domain import TerminalDomain
from ios.self_tests.avatar_prepare_fixture import RUN
from ios.self_tests.test_ios_avatar_recovered_final_handoff import AvatarRecoveredFinalHandoffTests as FinalCase


class AvatarRecoveredFinalTerminalTests(unittest.TestCase):
    retain_originals=True
    # Actual production owners are constructed only after this declared
    # original OS/SDK model is selected, before either preparation capture.
    domain_type=TerminalDomain
    domain=FinalCase.domain
    issued_original_pin=FinalCase.issued_original_pin
    recovered_public_preparation=FinalCase.recovered_public_preparation
    preparation_unchanged=FinalCase.preparation_unchanged
    recovered_scene=FinalCase.recovered_scene
    continue_final=FinalCase.continue_final

    @classmethod
    def setUpClass(cls):FinalCase.setUpClass()
    @classmethod
    def tearDownClass(cls):FinalCase.tearDownClass()

    def test_same_recovered_originals_reach_held_terminal_and_file_only_canonical_retirement(self):
        d=self.recovered_scene(continuation=self.continue_final)
        p,a=d.owners['primary'],d.owners['actor']
        call=dict(contractVersion=__import__('feature_journeys.contract',fromlist=['VERSION']).VERSION,runId=RUN)
        print('Avatar held terminal: inspect actual holds',flush=True)
        request=dict(contractVersion=1,runId=RUN,stage='inspect');description=p.terminal(request)['description']
        self.assertTrue(all(description['roles'][role]['heldResources'] for role in ('primary','actor')))
        print('Avatar held terminal: genuine paired live window',flush=True);samples=[]
        for index in range(3):
            print('Avatar held terminal: live cut '+str(index+1)+' actor',flush=True);a.observe(dict(call,afterSequence=0))
            print('Avatar held terminal: live cut '+str(index+1)+' primary',flush=True);public=p.observe(dict(call,afterSequence=0))
            witness=p.client.request('/runs/'+RUN)['entries'][-1];samples.append(dict(primary=public,actor=witness))
            if index<2:d.sleep(1.6)
        print('Avatar held terminal: seal actual window',flush=True)
        terminal.window(samples,description);seal=p.terminal(dict(request,stage='seal',description=description,samples=samples))['seal']
        from ios.adapters.avatar_feature import AvatarFeaturePending
        captured=len(d.scenes['actor'].domain.history)
        with self.assertRaises(AvatarFeaturePending):a.observe(dict(call,afterSequence=0))
        self.assertEqual(captured,len(d.scenes['actor'].domain.history))
        self.assertFalse(any(method=='DELETE' for _role,method in d.sdk_requests))
        self.assertTrue(all('app.stop' not in native.lifecycle_inputs for native in d.natives.values()))
        self.assertFalse(any(row.get('stage')=='complete' for row in d.server.phase_retirements.snapshot(RUN)['entries']))
        print('Avatar held terminal: once Stop/OS/SDK',flush=True);d.client.request('/runs/'+RUN,method='DELETE')
        end=p.terminal(dict(request,stage='finish',seal=seal))['end'];terminal.ended(end,seal)
        print('Avatar held terminal: both original OS/SDK ends retained',flush=True)
        for role in ('primary','actor'):
            self.assertEqual(1,d.natives[role].lifecycle_inputs.count('app.stop'))
            self.assertEqual(1,d.sdk_requests.count((role,'DELETE')));self.assertFalse(d.sdk_exists[role])
        counts=list(d.sdk_requests)
        print('Avatar held terminal: historical end graph',flush=True)
        with p.held(paired=True):p.load();owner=AvatarTerminal(p);self.assertEqual(end,owner.verify_end())
        print('Avatar held terminal: SDK-free canonical end graph',flush=True)
        self.assertTrue(p.verify_terminal_result(dict(request,stage='finish',seal=seal),dict(stage='finish',end=end)))
        from ios.adapters.avatar_ended_archive import verify
        from adapters.normal_feature_state import PrivateFeatureState
        coordinator=PrivateFeatureState(p.store.path).read();terminal_original=PrivateFeatureState(owner.store.path).read();members=set()
        with patch.object(d.runtime.adapter,'_target',side_effect=AssertionError('Historical Avatar end must not resolve a target')):
            for subject in ('primary','actor'):
                print('Avatar held terminal: '+subject+' file-only binding replay',flush=True)
                self.assertEqual(p.state['bindings'][subject],verify(d.runtime.adapter,p.selectors[subject],coordinator,terminal_original,membership=members))
        self.assertIn(p.store.path,members);self.assertIn(owner.store.path,members)
        self.assertEqual(counts,d.sdk_requests);self.assertTrue(a.terminal_actor_ended())

        # The original persistent Actor now executes its ACTUAL worker loop,
        # after the fixture has already retired and both SDKs were deleted.
        # Existing worker unit tests supply lambda verdicts; this uses the
        # same typed real-file ended graph just proved above.
        for role in ('primary','actor'):
            self.assertIsNone(d.runtime.adapter.read_session(role))
            self.assertIsNone(d.runtime.adapter._binding_store(role).read())
        original_inputs={role:list(native.input_log) for role,native in d.natives.items()}
        original_lifecycle={role:list(native.lifecycle_inputs) for role,native in d.natives.items()}
        original_sdk=list(d.sdk_requests)
        worker_config=dict(target=a.selector,primaryTarget=p.selector,durationSeconds=30)
        self.assertEqual(0,run_flow(a,worker_config,monotonic=a.monotonic,sleep=a.sleep))
        self.assertEqual(original_sdk,d.sdk_requests)
        self.assertEqual(original_inputs,{role:list(native.input_log) for role,native in d.natives.items()})
        self.assertEqual(original_lifecycle,{role:list(native.lifecycle_inputs) for role,native in d.natives.items()})
        self.assertFalse(any(a.root.glob('avatar-worker-failed-'+a.run+'.json')))
