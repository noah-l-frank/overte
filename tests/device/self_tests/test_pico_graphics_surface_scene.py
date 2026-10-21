"""Owned Pico cue scene through the existing normal VR Go To/Home stack."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_scene import PicoGraphicsSurfaceScenePolicy
from feature_journeys.graphics_fixture import pico_scene,PICO_PROFILE,PICO_RESOURCE
from feature_journeys.graphics_resources import GraphicsResources
from self_tests.test_pico_graphics_scene import Model,RUN,TICKET,BASE


class PicoGraphicsSurfaceSceneTests(unittest.TestCase):
    def model(self):
        value=Model();self.addCleanup(value.close);value.graphics_scene_policy=PicoGraphicsSurfaceScenePolicy()
        value.provider=GraphicsResources(BASE,clock_ms=lambda:value.native.epoch)
        value.provider.provision(RUN,profile=PICO_PROFILE);value.provider.activate(RUN,TICKET)
        value.client.graphics_instance=value.provider.instance;value.client.graphics_previous=None
        return value

    def test_normal_go_to_aligns_original_hmd_on_the_selected_scene_and_restores_without_input_replay(self):
        m=self.model()
        with patch('self_tests.test_pico_graphics_scene.scene_document',side_effect=pico_scene),m.lock.held():
            original=m.factory();proof=original.prepare()
            self.assertIn('/'+PICO_RESOURCE,proof['subject']['source']['sceneUrl'])
            self.assertEqual(3,sum(row['type']=='Web' for row in proof['subject']['source']['entities']))
            m.factory().prepare();self.assertEqual(2,len(m.destinations))
            m.factory().restore();m.factory().retire();self.assertEqual(3,len(m.destinations))
            self.assertTrue(all('/'+PICO_RESOURCE in url for url in m.destinations[:2]))
        self.assertTrue(any(event=='navigation.address:submit' for event in m.native.events))

    def test_foreign_legacy_provider_is_rejected_before_normal_navigation(self):
        m=self.model();m.provider=GraphicsResources(BASE,clock_ms=lambda:m.native.epoch)
        m.provider.provision(RUN);m.provider.activate(RUN,TICKET);m.client.graphics_instance=m.provider.instance
        with m.lock.held():
            owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual([],m.destinations)


if __name__=='__main__':unittest.main()
