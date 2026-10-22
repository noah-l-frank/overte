"""Other features keep their actual GPU owners; no native cleanup is inferred."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.create_feature import IOSCreateFeature
from ios.adapters.emote_foreign_gpu import ignored
from ios.adapters.emote_session_carriers import scoped
from self_tests.test_owned_vulkan_world_frame import owner,World,BINDING,RUN,REQUEST,TICKET


class ForeignGPUTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name);self.directory.chmod(0o700)
        self.root=self.directory/'create-artifacts';self.root.mkdir(mode=0o700)
        self.path=self.directory/('graphics-world-frame-actor-0-'+REQUEST[4:]+'.json')
        self.store=PrivateFeatureState(self.path);self.native=World()
        self.owner=owner(self.native,self.store,self.root,role='actor');self.owner.capture(TICKET)
        self.png=self.root/self.owner.name;self.candidates={self.path,self.png}
        feature=object.__new__(IOSCreateFeature);feature.role,feature.run,feature.root='actor',RUN,self.root
        feature.policy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128])
        feature.phase=SimpleNamespace(fixture_url='http://127.0.0.1:12345/feature-fixture/v1/runs/'+RUN+'/')
        state=dict(phase='preparing',binding=deepcopy(BINDING),primaryBinding=deepcopy(BINDING),phaseInstance='a'*32,
            initialTicket=TICKET,actorAdmission=None,beforeImage=None,images=[],exports=[],retirement=None)
        self.header=PrivateFeatureState(self.directory/'ios-create-actor-feature.json')
        self.header.write(feature.envelope(state),None)
        self.before={path:path.read_bytes() for path in self.candidates|{self.header.path}}
        self.commands=deepcopy(self.native.commands)

    def unchanged(self):
        self.assertEqual(self.commands,self.native.commands)
        self.assertEqual(self.before,{path:path.read_bytes() for path in self.before})

    def test_closed_actual_feature_header_and_full_owner_keep_both_foreign_files(self):
        self.assertEqual(self.candidates,ignored(self.directory,self.candidates));self.unchanged()
        # Responsibility exclusion is deliberately independent of release:
        # the actual other feature remains the owner of this captured GPU slot.
        self.assertEqual('captured',self.store.read()['phase'])
        self.assertEqual(set(),scoped(self.directory,{self.directory},explicit=True));self.unchanged()

    def test_run_root_and_binding_must_match_actual_other_feature(self):
        original=self.header.read()
        for fault in ('run','root','binding'):
            value=deepcopy(original)
            if fault=='run':value['runId']='b'*32;value['fixtureUrl']=value['fixtureUrl'].replace(RUN,'b'*32)
            elif fault=='root':value['artifactRoot']=str(self.directory)
            else:
                rows=unpack(value['payload']);rows[0]['binding']['artifactSha256']='c'*64;value['payload']=pack(rows)
            self.header.write(value,self.header.read())
            with self.subTest(fault=fault):self.assertEqual(set(),ignored(self.directory,self.candidates))
        self.header.write(original,self.header.read());self.unchanged()

    def test_malformed_or_missing_namespace_cannot_hide_a_gpu_owner(self):
        original=self.header.read()
        for fault in ('boolean-version','unknown-field','namespace'):
            value=deepcopy(original)
            if fault=='boolean-version':value['iosCreateFeatureVersion']=True
            elif fault=='unknown-field':value['cleanup']=True
            else:value['iosAvatarFeatureVersion']=value.pop('iosCreateFeatureVersion')
            self.header.write(value,self.header.read())
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):ignored(self.directory,self.candidates)
        self.header.discard(self.header.read());self.assertEqual(set(),ignored(self.directory,self.candidates))
        self.header.write(original,None);self.unchanged()

    def test_wrong_actual_gpu_filename_is_not_namespace_authority(self):
        changed=self.path.with_name('graphics-world-frame-actor-0-'+'6'*32+'.json')
        changed.write_bytes(self.path.read_bytes());changed.chmod(0o600)
        with self.assertRaises(NativeUIError):ignored(self.directory,{changed,self.png})
        self.unchanged()

    def test_default_without_emote_cue_does_not_adopt_or_decode_another_feature(self):
        self.assertEqual(set(),scoped(self.directory,{self.directory}));self.unchanged()

    def test_replacement_png_is_not_owned_by_the_foreign_headers_original_inode(self):
        raw=self.png.read_bytes();metadata=self.store.path.read_bytes()
        with self.png.open('rb') as retained:
            self.png.unlink();self.png.write_bytes(raw);self.png.chmod(0o600)
            with self.assertRaises(NativeUIError):ignored(self.directory,self.candidates)
            self.assertEqual(raw,retained.read())
        self.assertEqual(raw,self.png.read_bytes());self.assertEqual(metadata,self.store.path.read_bytes())
        self.assertEqual(self.commands,self.native.commands)
