"""Actual factory assembly shares guarded reads without leaking their lifetime.

Normal Node/Script/DOM, HTTP, files and PNGs execute. Native/SDK/Qt/WK/GPU and
clocks are declared host models; this does not qualify real API CPU bounds.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
import cProfile
import pstats
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters import world_web_factories as factories
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_sources import WorldWebSources
from ios.self_tests.retained_host_roots import retain_owned_root
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebPartsRoundTests(unittest.TestCase):
    def test_actual_normal_unicode_factory_reconstruction_and_changed_carrier_exit(self):
        fixture=FeatureWorldWeb();self.addCleanup(fixture.close)
        primary_root=retain_owned_root(fixture.whole.fixture.fixture.temp,expected_root=fixture.whole.scope.root)
        actor_root=retain_owned_root(fixture.actor.temp,expected_root=fixture.actor.root)
        print('Retained World construction originals: '+str(primary_root)+'; '+str(actor_root),flush=True)
        flow=fixture.primary;call=dict(contractVersion=16,runId=fixture.network.run,afterSequence=0)
        baseline=flow.observe(call);self.assertFalse(baseline['state']['open'])
        actor_baseline=fixture.secondary.observe(call);self.assertFalse(actor_baseline['state']['open'])
        self.assertEqual(dict(performed=True),flow.act(fixture.sdk.activate('open',{})))
        text=context(fixture.network.run)['unicode']
        self.assertEqual(dict(performed=True),flow.act(fixture.sdk.activate('focus-type',dict(text=text))))
        observed=fixture.secondary.observe(dict(call,afterSequence=actor_baseline['sequence']))
        self.assertEqual(text,observed['state']['text'])

        def census():
            rows={}
            for root in (primary_root,actor_root):
                for path in root.rglob('*'):
                    if path.is_file():
                        before=EmoteOriginalLease.signature(path.lstat());raw=path.read_bytes()
                        self.assertEqual(before,EmoteOriginalLease.signature(path.lstat()))
                        rows[str(path)]=(before,sha256(raw).hexdigest())
            return rows

        def calls(profile,method):
            code=method.__code__
            return pstats.Stats(profile).stats[(code.co_filename,code.co_firstlineno,code.co_name)][1]
        before=census();posts=len(fixture.sdk.posted);requests=list(fixture.requests)
        with flow.held():
            profile=cProfile.Profile();profile.enable(subcalls=False,builtins=False)
            try:parts=flow.parts()
            finally:profile.disable()
            # Keep production reader identities intact: the full literal
            # constructor itself supplies this same guarded assembly round.
            self.assertEqual(1,calls(profile,WorldWebSources._decode_frames))
            self.assertEqual(2,calls(profile,WorldWebLease._derive))
            self.assertIsNone(parts['source']._round);self.assertIsNone(parts['lease']._round)
        self.assertEqual(before,census());self.assertEqual(posts,len(fixture.sdk.posted))
        self.assertEqual(requests,fixture.requests)
        before=census()
        with fixture.secondary.held():
            profile=cProfile.Profile();profile.enable(subcalls=False,builtins=False)
            try:actor_parts=fixture.secondary.parts()
            finally:profile.disable()
            self.assertEqual(2,calls(profile,WorldWebSources._decode_frames))
            self.assertEqual(2,calls(profile,WorldWebLease._derive))
            for owner in (actor_parts['peer'],actor_parts['source'],actor_parts['lease']):self.assertIsNone(owner._round)
        self.assertEqual(before,census());self.assertEqual(posts,len(fixture.sdk.posted))
        self.assertEqual(requests,fixture.requests)
        with flow.held():
            source=parts['source'];frame=source.frame(source.capture('constructed-independent-editor'))
            self.assertEqual(text,frame['originals']['document']['source']['dom']['editor']['text'])

        actions=factories.actions;replaced=[]
        def changing(*args,**kwargs):
            value=actions(*args,**kwargs);source=args[2];path=source.record_store(1).path
            retained=path.with_name(path.name+'.retained-original')
            self.assertFalse(retained.exists());path.rename(retained)
            path.write_bytes(retained.read_bytes());path.chmod(0o600)
            replaced.append((retained,path));return value
        with flow.held(),patch.object(factories,'actions',changing):
            with self.assertRaises(NativeUIError):flow.parts()
        self.assertEqual(1,len(replaced));self.assertTrue(replaced[0][0].is_file())
        self.assertEqual(replaced[0][0].read_bytes(),replaced[0][1].read_bytes())
        self.assertEqual(posts,len(fixture.sdk.posted))


if __name__=='__main__':unittest.main()
