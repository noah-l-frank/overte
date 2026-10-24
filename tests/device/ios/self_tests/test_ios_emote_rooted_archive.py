"""Actual private graph replay with every native/live guard forbidden."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from adapters.original_file_reads import scope as original_reads
from ios.adapters.emote_rooted_archive import capture,read,grouped
from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
from ios.self_tests.test_ios_emote_rooted_retirement import RootedRetirementCompositionTests


class RootedArchiveTests(unittest.TestCase):
    def setUp(self):
        self.f=RootedRetirementCompositionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_actual_latest_component_envelopes_replay_without_live_metadata_sdk_or_native_queries(self):
        f=self.f;owner=f.keyed;snapshot=capture(owner,f.keyed_ref)
        expected=IOSEmoteRootedSceneRetirement(owner).read(f.keyed_ref)
        domain=f.f.domain;history=len(domain.history);actions=list(domain.io.actions)
        def forbidden(*_args,**_kwargs):self.fail('Historical graph queried or changed live ownership')
        for part in (owner,owner.rendered_owner,owner.rendered_owner.native_owner,owner.keys_owner,owner.rendered_owner.frames_owner):
            part.guard=forbidden
        files={p:(p.stat().st_ino,p.read_bytes()) for p in owner.root.rglob('*') if p.is_file()}
        actual=read(snapshot,lock=owner.lock,primary_lock=owner.primary_lock)
        self.assertEqual(expected,actual);self.assertEqual(history,len(domain.history));self.assertEqual(actions,domain.io.actions)
        self.assertEqual(files,{p:(p.stat().st_ino,p.read_bytes()) for p in owner.root.rglob('*') if p.is_file()})
        for fault in ('role','pid','reference','path','legacy','primary-lock','native-path'):
            value=deepcopy(snapshot)
            if fault=='role':value['role']='actor'
            elif fault=='pid':value['binding']['processIdentity']='52'
            elif fault=='reference':value['reference']['sha256']='f'*64
            elif fault=='path':value['paths']['keys']=value['paths']['native']
            elif fault=='legacy':value['owners']['keyed']['iosEmoteKeyedRetirementVersion']=1
            elif fault=='primary-lock':value['primaryLock']=str(owner.root/'foreign-lock')
            else:del value['owners']['native']['paths']['sources']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                read(value,lock=owner.lock,primary_lock=owner.primary_lock)

    def test_historical_prefix_stays_exact_after_later_records_without_weakening_current_orphan_checks(self):
        f=self.f;owner=f.keyed;snapshot=capture(owner,f.keyed_ref)
        expected=read(snapshot,lock=owner.lock,primary_lock=owner.primary_lock)
        rendered=owner.rendered_owner;native=rendered.native_owner
        # Keep genuine original measurements unchanged. Later bookkeeping
        # records do not turn the older measurement into a newer observation.
        nr=native.retain(native.original(f.f.native_reference))
        ro=rendered.original(f.rendered_ref);ro['nativeReference']=nr;rr=rendered.retain(ro)
        ko=owner.original(f.keyed_ref);ko['renderedReference']=rr;owner.retain(ko)
        self.assertEqual(expected,read(snapshot,lock=owner.lock,primary_lock=owner.primary_lock))
        from ios.adapters.emote_retirement import Frozen
        with self.assertRaises(NativeUIError):
            type(owner)(Frozen(owner.store.path,snapshot['owners']['keyed']),rendered,owner.keys_owner)
        # An archive is read-only even with a deliberately writable store.
        historical=type(owner)(owner.store,rendered,owner.keys_owner,historical=True)
        with self.assertRaises(NativeUIError):historical.retain(ko)

    def test_grouped_read_keeps_dependency_cursors_serial_types_and_read_membership(self):
        f=self.f;owner=f.keyed;snapshot=capture(owner,f.keyed_ref)
        expected=read(snapshot,lock=owner.lock,primary_lock=owner.primary_lock)
        class ForeignMapping(dict):pass
        with grouped([snapshot],lock=owner.lock,primary_lock=owner.primary_lock) as checked:
            with original_reads(fresh=True) as reads:actual=checked.read(deepcopy(snapshot))
            self.assertEqual(expected,actual);actual['public']['sequence']=999
            self.assertEqual(expected,checked.read(snapshot))
            # A different in-memory serialization order may miss the memo;
            # the actual literal parser must still accept the same DTO.
            self.assertEqual(expected,checked.read(dict(reversed(list(snapshot.items())))))
            self.assertIn(owner.rendered_owner.native_owner.record_store(f.f.native_reference['index']).path,reads)
            self.assertTrue(any(path.suffix=='.png' for path in reads))
            # Every old metadata envelope still passes its literal decoder.
            # The already cached derivation cannot hide missing dependencies.
            for fault in ('native-parent','rendered-parent','frame-cursor','key-serial','nested-mapping','outer-mapping'):
                value=deepcopy(snapshot)
                if fault in ('native-parent','rendered-parent'):
                    name='native' if fault=='native-parent' else 'rendered'
                    state=unpack(value['owners'][name]['payload'])[0];state['records']=[]
                    value['owners'][name]['payload']=pack([state])
                elif fault=='frame-cursor':
                    state=unpack(value['owners']['frames']['payload'])[0];state['cursors']['native']=None
                    value['owners']['frames']['payload']=pack([state])
                elif fault=='key-serial':
                    state=unpack(value['owners']['keys']['payload'])[0];state['serial']=0
                    value['owners']['keys']['payload']=pack([state])
                elif fault=='nested-mapping':value['owners']=ForeignMapping(value['owners'])
                else:value=ForeignMapping(value)
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):checked.read(value)
        with self.assertRaises(NativeUIError):checked.read(snapshot)

    def test_grouped_typed_read_cannot_survive_an_original_file_change(self):
        f=self.f;owner=f.keyed;snapshot=capture(owner,f.keyed_ref)
        with self.assertRaises(NativeUIError):
            with grouped([snapshot],lock=owner.lock,primary_lock=owner.primary_lock) as checked:
                path=owner.rendered_owner.native_owner.record_store(f.f.native_reference['index']).path
                path.write_bytes(path.read_bytes()+b' ');checked.read(snapshot)


if __name__=='__main__':unittest.main()
