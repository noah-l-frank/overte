"""Actual generic cleanup preserves retained Navigation scene responsibilities."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import unittest
from test_create_operation_binding import CreateOperationBindingTests
from adapters.pico4.navigation_scene_state import NAMES


class NavigationSceneBindingTests(CreateOperationBindingTests):
    def test_actual_root_and_rootless_scene_originals_block_before_native_input_or_base_stop(self):
        key=hashlib.sha256(('org.overte.pico\0'+self.native.target).encode()).hexdigest()[:32]
        names=(*NAMES,'navigation-scene-owner.json.frame-000.json','navigation-scene-raw.json.part-000.bin',
            'navigation-scene-raw.json.index-000.json','normal-scene-setup.json.pending-unknown')
        for index,name in enumerate(names):
            with self.subTest(name=name):
                if index:self.setUp()
                directory=Path(self.adapter.pico_configuration[1])/('feature-scripts-'+key)
                directory.mkdir(mode=0o700,exist_ok=True)
                (directory/name).write_bytes(b'original unknown retained source\n');(directory/name).chmod(0o600)
                self.refused_before_io()


def load_tests(loader,tests,pattern):
    return unittest.TestSuite([NavigationSceneBindingTests(
        'test_actual_root_and_rootless_scene_originals_block_before_native_input_or_base_stop')])

if __name__=='__main__':unittest.main()
