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


    def test_empty_requested_selection_still_decodes_all_actual_publisher_originals(self):
        from adapters.original_file_reads import scope as read_scope
        f=self.f
        with f.lock.held():
            terminal,parts,_samples,publisher=self.journal()
            with patch.object(f.actor,'request',side_effect=AssertionError('No HTTP in custody replay')),read_scope(fresh=True) as reads:
                self.assertEqual([],terminal.actor_publications(parts,[]))
                self.assertIn(publisher.store.path,reads)
                for reference in publisher.state['records']:self.assertIn(publisher.record_store(reference['ordinal']).path,reads)
            self.assertIsNone(terminal.actor.phase.previous)

    def test_empty_selection_cannot_hide_same_inode_record_rewrite_inside_actual_archive_decode(self):
        import os
        import time
        f=self.f
        with f.lock.held():
            terminal,parts,_samples,publisher=self.journal();path=publisher.record_store(1).path
            validate=parts['retirement'].observer.validate_original;changed=[]
            def rewritten(value):
                result=validate(value)
                if not changed:
                    changed.append(True);before=path.stat();raw=path.read_bytes();time.sleep(.002)
                    path.write_bytes(raw);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
                    self.assertEqual(before.st_ino,path.stat().st_ino);self.assertEqual(raw,path.read_bytes())
                return result
            parts['retirement'].observer.validate_original=rewritten
            with self.assertRaises(NativeUIError):terminal.actor_publications(parts,[])
            self.assertEqual([True],changed)


    def test_absent_unrequested_publisher_is_not_created_and_record_only_orphan_refuses(self):
        f=self.f
        with f.lock.held():
            terminal=object.__new__(WorldWebTerminal);terminal.flow=SimpleNamespace(run=f.run)
            terminal.actor=SimpleNamespace(store=PrivateFeatureState(f.root/'ios-world-web-actor-feature.json'),lock=f.lock)
            parts=dict(retirement=SimpleNamespace(observer=SimpleNamespace(guard=lambda:True,round_guard=lambda:None)))
            path=f.root/('phase-publication-world-web-'+f.run+'-actor.json')
            with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Read must not create a publisher')):
                self.assertEqual([],terminal.actor_publications(parts,[]));self.assertFalse(path.exists())
                with self.assertRaises(NativeUIError):terminal.actor_publications(parts,[dict(unqualifiedSelection=True)])
            orphan=PrivateFeatureState(path.with_name(path.stem+'-1.json'));value=dict(unqualifiedOrphan=True)
            orphan.write(value,None)
            with self.assertRaises(NativeUIError):terminal.actor_publications(parts,[])
            self.assertEqual(value,orphan.read());self.assertFalse(path.exists())


if __name__=='__main__':unittest.main()
