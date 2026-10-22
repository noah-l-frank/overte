"""Live owner metadata recovery over actual source archives; native reads fake."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.emote_observer import IOSEmoteObserver,EmoteObservationPending
from ios.self_tests.emote_original_fixtures import Originals
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase
from ios.self_tests.test_ios_emote_actions import URL


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.fixture=Originals(self.root,self.lock);self.calls=0
        def read():
            self.calls+=1;self.fixture.append(18800,baseline=True);return deepcopy(self.fixture.owner.frames[-1])
        self.fixture.owner.read=read
        self.phase=object.__new__(PhaseFixtureReader);self.phase.run,self.phase.area,self.phase.fixture_url=RUN,'emotes',URL
        self.phase.previous=phase(1,90000);self.sequence=10
        def status(_floor=None):
            self.sequence+=1;self.phase.previous=phase(self.sequence,90000)
            return dict(ticket='4'*32,verb='baseline',inputs={},afterEpochMs=89900,status=deepcopy(self.phase.previous))
        self.phase.read=status
        self.store=PrivateFeatureState(self.root/'ios-emote-primary-observer.json')
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def owner(self):return IOSEmoteObserver(self.store,self.fixture.owner,BINDING,'primary',self.root,dict(source='world-render-target'),
        self.phase,self.lock,lambda:True,epoch_ms=lambda:90000.,monotonic=lambda:1.)
    def test_baseline_live_owner_replays_only_historical_sources_without_guard_or_native_reads(self):
        owner=self.owner();public=owner.observe(0);count=self.calls
        self.assertEqual('idle',public['state']['animation']);self.assertEqual(1,public['sequence'])
        rebuilt=self.owner();self.assertEqual(count,self.calls)
        def forbidden():raise AssertionError('Historical validation must not invoke a live candidate guard')
        self.fixture.owner.guard=self.fixture.owner.originals.guard=forbidden;rebuilt.guard=forbidden
        reference=dict(iosEmoteObservationReferenceVersion=1,**rebuilt.state['records'][-1])
        self.assertEqual(public,rebuilt.validate_original(reference)['public']);self.assertEqual(count,self.calls)
    def test_lost_local_record_return_adopts_exact_original_without_any_second_acquisition(self):
        owner=self.owner();retain=owner.retain
        def lost(original):retain(original);raise OSError('Synthetic lost original-file return')
        with patch.object(owner,'retain',side_effect=lost),self.assertRaises(OSError):owner.observe(0)
        self.assertEqual(1,self.calls);self.assertEqual([],owner.state['records'])
        rebuilt=self.owner();self.assertTrue(rebuilt.resolve());self.assertEqual(1,self.calls)
        self.assertEqual(1,len(rebuilt.state['records']));self.assertIsNone(rebuilt.state['pending'])
    def test_failed_completed_passive_read_is_retained_and_never_published_as_a_sample(self):
        read=self.fixture.owner.read
        def lost():read();raise OSError('Synthetic lost already archived read return')
        self.fixture.owner.read=lost;owner=self.owner()
        with self.assertRaises(OSError):owner.observe(0)
        with self.assertRaises(EmoteObservationPending):self.owner().observe(0)
        self.assertEqual(1,self.calls);rebuilt=self.owner();self.assertTrue(rebuilt.abandon_read())
        self.assertEqual(1,len(rebuilt.state['abandoned']));self.assertEqual([],rebuilt.state['records'])
        self.assertEqual(1,len(self.fixture.owner.frames));self.assertEqual(1,self.calls)
    def test_unresolved_child_read_is_not_abandoned_by_outer_metadata_cleanup(self):
        def failed():
            self.calls+=1;self.fixture.owner.state['phase']='reading';raise OSError('Synthetic partial child read')
        self.fixture.owner.read=failed;owner=self.owner()
        with self.assertRaises(OSError):owner.observe(0)
        with self.assertRaises(NativeUIError):self.owner().abandon_read()
        self.assertIsNotNone(self.owner().state['pending']);self.assertEqual(1,self.calls)


if __name__=='__main__':unittest.main()
