"""Actual private graph replay with every native/live guard forbidden."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_rooted_archive import capture,read
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


if __name__=='__main__':unittest.main()
