"""Actual private immutable peer archives; native fixtures remain synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.self_tests.test_ios_emote_peer import acquisition,ACTOR,RUN
from ios.self_tests.test_ios_emote_sources import phase


def original(later=False):
    peer=acquisition(later);join=peer['clockJoin']
    first=phase(3 if later else 1,join['hostBeforeEpochMs']);last=phase(4 if later else 2,join['hostAfterEpochMs'])
    return dict(peer=peer,phaseBefore=first,phaseAfter=last)


class PeerSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.store=PrivateFeatureState(self.root/'ios-emote-actor-peer-sources.json')
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def owner(self):return IOSEmotePeerSources(self.store,self.root,ACTOR,RUN,None,self.lock,lambda:True,historical=True)
    def archive(self,frames):
        owner=self.owner();owner.historical=False;owner.save()
        for value in frames:
            owner.state['pending']=dict(original=None,manifest=None,partial={});owner.save()
            item=owner.originals.write(len(owner.frames)+1,value);refs=owner.originals.append(owner.state['manifests'],item)
            owner.frames.append(deepcopy(value));owner.state.update(revision=len(owner.frames),manifests=refs,pending=None);owner.save()
        return owner
    def test_independent_receive_and_renderer4_round_trip_actual_immutable_files(self):
        before,after=original(),original(True);owner=self.archive([before,after]);reference=owner.reference()
        rebuilt=self.owner();self.assertEqual(after,rebuilt.original(reference));self.assertEqual(2,rebuilt.state['revision'])
        self.assertEqual(4,rebuilt.original(reference)['peer']['renderers']['iosAvatarRenderersVersion'])
        with self.assertRaises(NativeUIError):rebuilt.read()
    def test_historical_prefix_and_current_renderer_version_are_mandatory(self):
        before=original()
        for fault in ('renderer','clock','receive','phase'):
            after=original(True)
            if fault=='renderer':after['peer']['renderers']['iosAvatarRenderersVersion']=3
            elif fault=='clock':after['peer']['clockJoin']['nativeBefore']['sequence']=1
            elif fault=='receive':after['peer']['receive']['source']['selfSha256']='f'*64
            else:after['phaseAfter']['activations'][0]['stimulus']=dict(verb='open',inputs={})
            after['peer']['clockJoin']['originalsSha256']=digest({k:after['peer'][k] for k in ('world','receive','renderers')})
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.owner().validate_frame(after,before)
    def test_rewritten_or_missing_original_never_resolves_to_another_frame(self):
        owner=self.archive([original()]);ref=owner.reference();ref['sha256']='0'*64
        with self.assertRaises(NativeUIError):owner.original(ref)
        path=next(self.root.glob('emote-peer-frame-*.json'));path.write_bytes(b'{}')
        with self.assertRaises(NativeUIError):self.owner()


if __name__=='__main__':unittest.main()
