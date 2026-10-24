"""Real HTTP publisher originals and immutable-carrier terminal projection.

The native observer/frame/retirement calls are explicit model sentinels. This
checks readonly publisher reconstruction and byte/inode joins, not native quiet,
rendering or an accepted terminal result. No Node or physical SDK is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.world_web_terminal import WorldWebTerminal
from self_tests import test_phase_witness_publisher as publication_fixture
from self_tests.test_completed_frame_lease import BINDING


class WorldWebTerminalPublicationsTests(unittest.TestCase):
    def setUp(self):
        self.f=publication_fixture.PhaseWitnessPublisherTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.attach('world-web')

    def journal(self):
        f=self.f;publisher=f.owner();original=f.original();measured=f.known[digest(original)]
        original['reference']=dict(index=1,sha256='e'*64);f.known[digest(original)]=measured
        publisher.publish(original);entry=publisher.load(publisher.state['records'][0])['entry']
        fresh=PhaseFixtureReader(f.actor,f.run,'world-web');self.assertIsNone(fresh.previous)
        terminal=object.__new__(WorldWebTerminal);terminal.flow=SimpleNamespace(run=f.run)
        def forbidden(*_args,**_kwargs):raise AssertionError('No live publisher/native/phase query during readonly projection')
        terminal.actor=SimpleNamespace(store=PrivateFeatureState(f.root/'ios-world-web-actor-feature.json'),lock=f.lock,
            state=dict(binding=deepcopy(BINDING),phaseInstance=f.phase.previous['instance']),client=f.actor,phase=fresh,publisher=forbidden)
        observer=SimpleNamespace(guard=lambda:f.okay,round_guard=lambda:None,validate_original=f.validate_original,
            entries=lambda:[dict(source=dict(index=1),peer=dict(index=1))],
            source=SimpleNamespace(frame=lambda ref:dict(explicitPrimaryModel=ref['index'])),peer=SimpleNamespace(frame=lambda ref:dict(explicitPeerModel=ref['index'])))
        owner=SimpleNamespace(observer=observer,native_frames=lambda a,b:None)
        return terminal,dict(retirement=owner),[dict(actor=entry)],publisher

    def test_fresh_actor_phase_never_needs_a_new_live_original_for_retained_publications(self):
        f=self.f
        with f.lock.held():
            terminal,parts,samples,_publisher=self.journal()
            with patch.object(f.actor,'request',side_effect=AssertionError('No HTTP during retained-original selection')):
                value=terminal.actor_publications(parts,samples)
                self.assertEqual(samples[0]['actor'],value[0]['publication']['entry']);self.assertIsNone(terminal.actor.phase.previous)
                value[0]['publication']['entry']['facts']['open']=True
                self.assertFalse(terminal.actor_publications(parts,samples)[0]['publication']['entry']['facts']['open'])
                self.assertEqual(1,terminal.actor_publications(parts,samples,historical=True)[0]['primary']['explicitPrimaryModel'])

    def test_current_guard_and_foreign_original_phase_instance_fail_without_queries(self):
        f=self.f
        with f.lock.held():
            terminal,parts,samples,publisher=self.journal();f.okay=False
            with self.assertRaises(NativeUIError):terminal.actor_publications(parts,samples)
            f.okay=True;old=publisher.store.read();changed=deepcopy(old);changed['phaseInstance']='f'*32;publisher.store.write(changed,old)
            with self.assertRaises(NativeUIError):terminal.actor_publications(parts,samples)

    def test_unrecorded_original_and_same_bytes_replaced_record_after_use_are_refused(self):
        f=self.f
        with f.lock.held():
            terminal,parts,samples,publisher=self.journal();path=publisher.record_store(1).path
            orphan=publisher.record_store(2);orphan.write(publisher.record_store(1).read(),None)
            with self.assertRaises(NativeUIError):terminal.actor_publications(parts,samples)
            orphan.discard(orphan.read())
            def replaced(_a,_b):
                other=path.with_suffix('.replacement');other.write_bytes(path.read_bytes());other.chmod(0o600);other.replace(path)
            parts['retirement'].native_frames=replaced
            with self.assertRaises(NativeUIError):terminal.actor_publications(parts,samples)


if __name__=='__main__':unittest.main()
