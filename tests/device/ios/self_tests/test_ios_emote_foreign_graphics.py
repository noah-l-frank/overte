"""Recognize actual closed Graphics scope headers without acquiring its facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from feature_journeys.graphics_resources import GraphicsResources
from ios.adapters.emote_foreign_gpu import ignored
from ios.adapters.graphics_feature import IOSGraphicsFeature
from ios.adapters.graphics_observer import VERSION as OBSERVER_VERSION
from self_tests.test_owned_vulkan_world_frame import owner,World,BINDING,RUN,REQUEST,TICKET


class ForeignGraphicsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name);self.directory.chmod(0o700)
        self.root=self.directory/'graphics-artifacts';self.root.mkdir(mode=0o700)
        self.provider=GraphicsResources('http://127.0.0.1:12345/feature-fixture/v1',clock_ms=lambda:1000)
        self.provider.provision(RUN);self.status=self.provider.snapshot(RUN,'a'*32)
        self.policy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128])

    def captured(self,role):
        store=PrivateFeatureState(self.directory/('graphics-world-frame-'+role+'-0-'+REQUEST[4:]+'.json'))
        native=World();frame=owner(native,store,self.root,role=role);frame.capture(TICKET)
        return native,store,{store.path,self.root/frame.name}

    def test_graphics_feature_scope_is_closed_and_matches_its_actual_primary_owner(self):
        native,store,paths=self.captured('primary')
        state=dict(phase='preparing',stage=0,binding=BINDING,backend=self.status,ticket=None,call=None,calibration=None,
            restartReady=None,backgroundArchive=None,cleanup=[],cleanupWindow=None,restartBarrier=None,
            restartRejoined=dict(primary=None,actor=None))
        feature=object.__new__(IOSGraphicsFeature);feature.run,feature.root,feature.policy=RUN,self.root,self.policy
        feature.fixture_url=self.provider.url+'/runs/'+RUN+'/'
        header=PrivateFeatureState(self.directory/'ios-graphics-feature.json');value=feature.envelope(state);header.write(value,None)
        commands=deepcopy(native.commands);actual={path:path.read_bytes() for path in paths|{header.path}}
        self.assertEqual(paths,ignored(self.directory,paths))
        self.assertEqual(commands,native.commands);self.assertEqual(actual,{path:path.read_bytes() for path in actual})
        header.write(dict(value,iosGraphicsFeatureVersion=True),value)
        with self.assertRaises(NativeUIError):ignored(self.directory,paths)
        self.assertEqual('captured',store.read()['phase']);self.assertEqual(commands,native.commands)

    def test_graphics_observer_uses_its_own_pure_typed_archive_decoder(self):
        native,store,paths=self.captured('actor')
        state=dict(phase='ready',binding=BINDING,stage=0,sequence=0,capturedEpochMs=0,backend=self.status,
            baseline=None,last=None,offFrames=dict(haze=None,mirror=None),effects=[],restart=None,pending=None,
            retirements=[],currentEffects=[],currentEffectsAfter=0,disabledEffects=[],disabledEffectsAfter=0,nativeFloor=None)
        value=dict(iosGraphicsObserverVersion=OBSERVER_VERSION,runId=RUN,fixtureUrl=self.provider.url,
            providerInstance=self.provider.instance,role='actor',artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([state]))
        header=PrivateFeatureState(self.directory/'ios-graphics-actor-observer.json');header.write(value,None)
        before={path:path.read_bytes() for path in paths|{header.path}};commands=deepcopy(native.commands)
        self.assertEqual(paths,ignored(self.directory,paths))
        self.assertEqual(before,{path:path.read_bytes() for path in before});self.assertEqual(commands,native.commands)
        self.assertEqual('captured',store.read()['phase'])
        wrong=deepcopy(value);wrong['providerInstance']='b'*32;header.write(wrong,value)
        with self.assertRaises(ValueError):ignored(self.directory,paths)
        self.assertEqual(commands,native.commands)
