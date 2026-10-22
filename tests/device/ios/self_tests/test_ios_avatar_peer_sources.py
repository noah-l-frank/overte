"""Private peer archives and untouched native source DTOs at explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_avatar_peer_sources import OriginalAvatarPeerSources
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
from ios.adapters.avatar_sources import AvatarPhaseChanged
from ios.adapters.emote_sources import EmotePhaseChanged
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests import test_ios_emote_peer_sources as legacy
from ios.self_tests.test_ios_emote_peer import ACTOR,RUN


def frame(later=False):
    value=legacy.original(later)
    for name in ('phaseBefore','phaseAfter'):value[name]['area']='avatar-people'
    return value


class AvatarPeerSourcesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.lock=ScriptSourceLock(self.path/'script-feature-sources.lock')
        self.store=PrivateFeatureState(self.path/'ios-avatar-actor-peer-sources.json')
    def owner(self):return IOSAvatarPeerSources(self.store,self.path,ACTOR,RUN,None,self.lock,lambda:True,historical=True)
    def archive(self,frames):
        owner=self.owner();owner.historical=False;owner.save()
        for value in frames:
            owner.state['pending']=dict(original=None,manifest=None,partial={});owner.save()
            item=owner.originals.write(len(owner.frames)+1,value);refs=owner.originals.append(owner.state['manifests'],item)
            owner.frames.append(deepcopy(value));owner.state.update(revision=len(owner.frames),manifests=refs,pending=None);owner.save()
        return owner

    def test_avatar_namespace_keeps_original_world_receive_renderer_and_clocks_unchanged(self):
        before,after=frame(),frame(True)
        with self.lock.held():
            owner=self.archive([before,after]);reference=owner.reference();rebuilt=self.owner()
            self.assertEqual(after,rebuilt.original(reference));self.assertEqual(2,rebuilt.state['revision'])
            self.assertEqual(1,rebuilt.original(reference)['peer']['world']['iosEmoteWorldVersion'])
            self.assertEqual(4,rebuilt.original(reference)['peer']['renderers']['iosAvatarRenderersVersion'])
            self.assertEqual(after['peer']['receive'],rebuilt.original(reference)['peer']['receive'])
            self.assertIn('iosAvatarPeerSourcesVersion',self.store.read());self.assertNotIn('iosEmotePeerSourcesVersion',self.store.read())
        self.assertTrue(list(self.path.glob('avatar-peer-frame-*.json')));self.assertFalse(list(self.path.glob('emote-peer-frame-*.json')))

    def test_explicit_frozen_emote_v1_envelope_and_original_filenames_remain_readable_without_new_facade_writer(self):
        store=PrivateFeatureState(self.path/'ios-emote-actor-peer-sources.json')
        with self.lock.held():
            original=legacy.original()
            archive=OriginalFrameStore(self.path,ACTOR,RUN,'actor',lambda:True,lambda *_:None,
                namespace='emote-peer',schema_prefix='emotePeer')
            item=archive.write(1,original);manifests=archive.append([],item)
            # Frozen v1 wire fields; do not generate this through a new facade.
            frozen=dict(iosEmotePeerSourcesVersion=1,binding=ACTOR,runId=RUN,artifactRoot=str(self.path),
                payload=pack([dict(revision=1,manifests=manifests,pending=None)]))
            store.write(frozen,None);files={path.name:path.read_bytes() for path in self.path.glob('emote-peer-*.json')}
            reader=OriginalAvatarPeerSources(store,self.path,ACTOR,RUN,None,self.lock,lambda:True,
                profile='emote',phase_changed=EmotePhaseChanged,historical=True)
            self.assertEqual(original,reader.original(reader.reference()))
            self.assertEqual(files,{path.name:path.read_bytes() for path in self.path.glob('emote-peer-*.json')})

    def test_foreign_namespace_or_candidate_or_replaced_inode_cannot_be_adopted(self):
        with self.lock.held():
            owner=self.archive([frame()]);reference=owner.reference()
            with self.assertRaises(NativeUIError):
                OriginalAvatarPeerSources(self.store,self.path,ACTOR,RUN,None,self.lock,lambda:True,
                    profile='emote',phase_changed=EmotePhaseChanged,historical=True)
            with self.assertRaises(NativeUIError):
                IOSAvatarPeerSources(self.store,self.path,ACTOR|dict(artifactSha256='0'*64),RUN,None,self.lock,lambda:True,historical=True)
            path=next(self.path.glob('avatar-peer-frame-*.json'));raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
            with self.assertRaises(NativeUIError):self.owner()
            reference['sha256']='0'*64
            with self.assertRaises(NativeUIError):owner.original(reference)

    def test_lost_original_phase_read_is_retained_and_no_sdk_or_phase_call_is_replayed(self):
        calls=[];phase=object.__new__(PhaseFixtureReader);phase.run=RUN;phase.area='avatar-people'
        def missing(*_args):calls.append('phase');raise NativeUIError('Explicit synthetic missing phase original')
        phase.read=missing
        runtime=object.__new__(IOSScriptRuntime)
        def sources(_selector):
            calls.append('sdk');return dict(binding=ACTOR,observer=SimpleNamespace(bound_native_observer=lambda _:None,
                emote_world=lambda _:None,avatar_renderers=lambda _:None),clock_source=None)
        runtime._sources=sources;runtime._avatar_receive=lambda _:None
        def make():return IOSAvatarPeerSources(self.store,self.path,ACTOR,RUN,phase,self.lock,lambda:True,runtime=runtime,selector='actor')
        with self.lock.held():
            with self.assertRaises(NativeUIError):make().read()
            rebuilt=make();self.assertIsNotNone(rebuilt.state['pending'])
            with self.assertRaises(NativeUIError):rebuilt.read()
            self.assertEqual(['sdk','phase'],calls)

    def test_own_phase_and_original_receiver_history_are_mandatory(self):
        with self.lock.held():
            owner=self.owner();before,after=frame(),frame(True)
            self.assertTrue(owner.validate_frame(after,before))
            after['phaseAfter']['area']='emotes'
            with self.assertRaises((NativeUIError,ValueError)):owner.validate_frame(after,before)


if __name__=='__main__':unittest.main()
