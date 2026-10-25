"""Every shared Avatar step followed by the same genuine held-terminal end.

Full original AvatarApp/People/Pal/request JavaScript and private files execute
on the host. Qt, native renderer, GPU, SDK and OS sources are explicit models.
This is not native iOS or physical acquisition/API timing qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

from feature_journeys.contract import VERSION
from feature_journeys.engine import matches
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.self_tests.avatar_prepare_fixture import RUN
from ios.self_tests.avatar_strong_app_domain import StrongAvatarAppDomain
from ios.self_tests.avatar_terminal_domain import TerminalDomain
from ios.self_tests import test_ios_avatar_held_terminal as held


def retain_originals(domain):
    # Keep only these two owned byte graphs at their genuine paths/inodes
    # for a later SDK-free end replay. HTTP/Node/socket cleanups still run.
    for role,scene in domain.scenes.items():
        temporary=scene.setup.fixture.temp
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        print('Avatar retained original graph '+role+': '+str(scene.root),flush=True)


class RetainedTerminalDomain(TerminalDomain):
    def __init__(self,test):super().__init__(test);retain_originals(self)


class AvatarRetainedHeldEndTests(held.AvatarHeldTerminalTests):
    domain_type=RetainedTerminalDomain


class SharedTerminalDomain(TerminalDomain,StrongAvatarAppDomain):
    """The original JS producers and original OS/SDK lifecycle boundaries."""
    def __init__(self,test):
        super().__init__(test);retain_originals(self)


class AvatarSharedHeldEndTests(held.AvatarHeldTerminalTests):
    domain_type=SharedTerminalDomain

    def prepare(self):
        domain=super().prepare();self.whole_domain=domain
        primary,actor=domain.owners['primary'],domain.owners['actor'];latest={}
        call=dict(contractVersion=VERSION,runId=RUN)
        def observe():
            for role,owner in domain.owners.items():
                latest[role]=owner.observe(dict(call,afterSequence=latest.get(role,{}).get('sequence',0)))
            self.assertEqual(latest['primary']['state'],latest['actor']['state'])
            self.assertTrue(domain.client.observe()['entries'])
        observe()
        for index,step in enumerate(SCENARIOS['avatar-people']['steps'],1):
            verb=step['verb'];inputs=expand(step['inputs'],context(RUN));ticket=f'{index:032x}'
            print('Avatar shared step '+str(index)+'/15: '+verb,flush=True)
            domain.client.activate(ticket,verb,inputs)
            if verb in ('peer-accept','peer-reject'):actor.consent(actor.phase.read())
            self.assertEqual(dict(performed=True),primary.act(dict(call,ticket=ticket,
                fixtureUrl=primary.phase.fixture_url,verb=verb,inputs=inputs)))
            if verb=='connection-cancel':
                with actor.held(paired=True):
                    actor.load();parts=actor.components(actor.source_parts());parts['surfaces']['actor'].prepare(ticket)
            observe();self.assertTrue(matches(latest['primary']['state'],expand(step['state'],context(RUN))),verb)
        self.assertFalse(domain.social.snapshot(RUN)['connected'])
        self.assertEqual('original',latest['primary']['state']['avatar'])
        self.assertFalse(latest['primary']['state']['bookmarked'])
        return domain

    def test_baseline_cleanup_preserves_login_holds_until_paired_os_and_sdk_end(self):
        super().test_baseline_cleanup_preserves_login_holds_until_paired_os_and_sdk_end()
        from ios.avatar_observer import run_flow
        domain=self.whole_domain;actor=domain.owners['actor'];before=list(domain.sdk_requests)
        def forbidden(*_args,**_kwargs):raise AssertionError('An actually ended Actor must use only its original files')
        with patch.object(actor.phase,'status',side_effect=forbidden),patch.object(domain.runtime.adapter,'_target',side_effect=forbidden):
            self.assertEqual(0,run_flow(actor,dict(target='actor',primaryTarget='primary',durationSeconds=30),
                monotonic=lambda:domain.clock[0],sleep=domain.sleep))
        self.assertEqual(before,domain.sdk_requests)


if __name__=='__main__':unittest.main()
