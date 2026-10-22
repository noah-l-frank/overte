"""Independent whole Actor setup, effect publication and complete retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from ios.self_tests.emote_whole_primary_fixture import WholePrimaryFixture
from ios.self_tests.emote_whole_actor_fixture import WholeActorFixture
from ios.self_tests.emote_scene_pair_fixture import connect


class WholeActorTests(unittest.TestCase):
    def test_independent_actor_publishes_real_baseline_playback_and_rendered_retirement(self):
        p=WholePrimaryFixture(self);a=WholeActorFixture(self,p);connect(p,a)
        call=dict(contractVersion=16,runId=p.flow.run,afterSequence=0)
        p.flow.observe(call);baseline=a.flow.observe(call);self.assertEqual('idle',baseline['state']['animation'])
        p.flow.act(p.call('play',name='Waving'));p.target.native.sleep(.25);p.flow.observe(call)
        played=a.flow.observe(dict(call,afterSequence=baseline['sequence']));self.assertTrue(played['state']['override'])
        p.call('cleanup')
        with p.flow.held(30):
            p.flow.load();p.flow.phase.read();p.flow.clean_local(p.flow.components())
        self.assertEqual({'performed':True},a.flow.cleanup(dict(contractVersion=16,runId=p.flow.run)))
        receipt=p.target.server.phase_retirements.snapshot(p.flow.run)['entries'][-1]
        self.assertEqual([],receipt['cleanup']['resources']);self.assertNotIn('state',receipt['cleanup'])
        self.assertEqual('actor-published',a.flow.state['retirement']['kind'])
        self.assertFalse(a.target.domain.running);self.assertFalse(a.target.domain.files.root.exists())
        self.assertTrue(a.target.packet_bytes);self.assertEqual([],p.target.vm.state['timers'])
        from unittest.mock import patch
        from feature_journeys.witness import Client
        from ios.adapters.emote_finalization import IOSEmoteFinalization
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.script_feature.history import unpack
        Client(p.target.client.url,'r'*64).request('/runs/'+p.flow.run,method='DELETE')
        def owned_components(finalization):
            finalization.guard();return a.parts
        from contextlib import contextmanager
        original_held=a.flow.held
        @contextmanager
        def diagnosed(*args,**kwargs):
            with original_held(*args,**kwargs):
                try:yield
                except Exception:
                    import traceback;traceback.print_exc();raise
        a.flow.held=diagnosed
        with patch.object(IOSEmoteFinalization,'local_components',owned_components):
            self.assertEqual({'performed':True},a.flow.finalize())
            self.assertIsNone(a.flow.store.read())
            self.assertEqual({'performed':True},a.flow.finalize())
        from contextlib import nullcontext
        for fixture in (a.target.fixture,p.target.f.fixture):
            fixture.held.__exit__(None,None,None);fixture.held=nullcontext()
        from ios.adapters.emote_completed_archive import verify
        archive_path=a.target.root/('ios-emote-actor-'+p.flow.run+'-finalization.json')
        plan=PrivateFeatureState(archive_path).read()
        members=set()
        try:
            self.assertEqual(a.flow.state['binding'],verify(a.target.root,archive_path,plan,membership=members))
            from ios.adapters.emote_session_carriers import covered
            covered({a.target.root},members)
        except Exception:
            import traceback;traceback.print_exc();raise
        self.assertEqual('complete',unpack(plan['payload'])[0]['phase'])
        self.assertTrue(list(a.target.root.glob('emote-restoration-*.json')))
        from adapters.normal_ui import NativeUIError
        copy=PrivateFeatureState(a.target.root/('emote-final-'+p.flow.run+'-actor-1.json'))
        previous=copy.read();copy.write(dict(previous,iosEmoteFinalCopyVersion=True),previous)
        with self.assertRaises(NativeUIError):verify(a.target.root,archive_path,plan)
        self.assertEqual(plan,PrivateFeatureState(archive_path).read())


    def test_paired_primary_wait_releases_actual_sdk_lock_and_repeated_cleanup_reacquires_originals(self):
        from contextlib import nullcontext
        p=WholePrimaryFixture(self);a=WholeActorFixture(self,p);connect(p,a)
        # Construction created the actual children under their SDK locks.
        # End those setup leases: all remaining locking belongs to production.
        for fixture in (a.target.fixture,p.target.f.fixture):
            fixture.held.__exit__(None,None,None);fixture.held=nullcontext()
        call=dict(contractVersion=16,runId=p.flow.run,afterSequence=0)
        p.flow.observe(call);a.flow.observe(call)
        p.flow.act(p.call('play',name='Waving'));p.target.native.sleep(.25);p.flow.observe(call);a.flow.observe(call)
        p.call('cleanup');cleanup=dict(contractVersion=16,runId=p.flow.run);admissions=[]
        def waiting(seconds):
            if p.target.lock._owner is None:
                self.assertIsNone(a.target.lock._owner)
                admissions.append(True);a.flow.cleanup(cleanup)
            p.target.domain.sleep(seconds)
        p.flow.sleep=waiting
        from contextlib import contextmanager
        original_held=p.flow.held
        @contextmanager
        def diagnosed(*args,**kwargs):
            with original_held(*args,**kwargs):
                try:yield
                except Exception:
                    import traceback;traceback.print_exc();raise
        p.flow.held=diagnosed
        self.assertEqual({'performed':True},p.flow.cleanup(cleanup))
        self.assertEqual([True],admissions);self.assertEqual('primary-paired',p.flow.state['retirement']['kind'])
        first=p.flow.state['retirement']['original'];before=len(p.target.native.requests)
        self.assertEqual({'performed':True},p.flow.cleanup(cleanup))
        self.assertEqual([True,True],admissions)
        self.assertGreater(p.flow.state['retirement']['original']['index'],first['index'])
        self.assertEqual(before,len(p.target.native.requests));self.assertIsNone(p.target.lock._owner)
        self.assertIsNone(a.target.lock._owner)
        from unittest.mock import patch
        from feature_journeys.witness import Client
        from ios.adapters.emote_finalization import IOSEmoteFinalization
        Client(p.target.client.url,'r'*64).request('/runs/'+p.flow.run,method='DELETE')
        def own_components(finalization):finalization.guard();return p.parts
        with patch.object(IOSEmoteFinalization,'local_components',own_components):
            self.assertEqual({'performed':True},p.flow.finalize())
            self.assertEqual({'performed':True},p.flow.finalize())
        from ios.adapters.emote_completed_archive import verify
        archive_path=p.target.root/('ios-emote-primary-'+p.flow.run+'-finalization.json')
        plan=PrivateFeatureState(archive_path).read()
        try:self.assertEqual(p.flow.state['binding'],verify(p.target.root,archive_path,plan))
        except Exception:
            import traceback;traceback.print_exc();raise
        self.assertIsNone(p.flow.store.read())
        def actor_components(finalization):finalization.guard();return a.parts
        with patch.object(IOSEmoteFinalization,'local_components',actor_components):
            self.assertEqual({'performed':True},a.flow.finalize())
        # The independent Actor retires only its own originals in the Primary
        # SDK directory. Reconstruct then qualify all remaining actual carriers.
        members=set();self.assertEqual(p.flow.state['binding'],verify(p.target.root,archive_path,plan,membership=members))
        from ios.adapters.emote_session_carriers import covered
        covered({p.target.root},members)


if __name__=='__main__':unittest.main()
