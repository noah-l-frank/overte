"""Real module/Journey/session ordering with a declared protocol-owner model.

This does not qualify the production operation owner, candidate or native VR.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

from feature_journeys.engine import Journey
from self_tests.test_feature_journeys import Boundary, POLICY, RUN
from self_tests.test_pico_browser_session import BrowserSessionTests

ENTRY = Path(__file__).resolve().parents[1]/'modules/feature_journey.py'


class BrowserModuleScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = BrowserSessionTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture; self.boundary = Boundary('tablet-web')
        self.entry_pin = self.pin()
        self.addCleanup(lambda:self.assertEqual(self.entry_pin, self.pin()))

    def pin(self):
        s = ENTRY.lstat()
        return dict(sha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
            physical=[s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns])

    def execute(self, *, uncertain_close=False):
        f, boundary = self.f, self.boundary
        original = f.owner.browser_component
        def component(run, url, operation, arguments, *, whole_budget):
            if operation == 'begin': f.whole = deepcopy(whole_budget)
            return original(run, url, operation, arguments, whole_budget=whole_budget)
        f.owner.browser_component = component
        f.session.pico_openxr = True
        f.session.ensure_controlled_scene = lambda:f.events.append('prepare')
        f.session.feature_operation = lambda area, kind, fields:boundary.invoke('feature.'+area+'.'+kind, fields)
        f.client.register = lambda area:(RUN, f.url)
        f.client.activate = boundary.activate; f.client.observe = boundary.witness
        if uncertain_close:
            original_context = f.session.operation_host
            @contextmanager
            def failed_context(artifacts):
                with original_context(artifacts) as owner: yield owner
                raise OSError('Declared unknown CLI close result')
            f.session.operation_host = failed_context
        policy_path = f.root/'policy.json'; policy_path.write_text(json.dumps({'tablet-web':POLICY}))
        environment = dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(f.owner.manifest),
            OVERTE_DEVICE_TARGET_SELECTOR=f.owner.target, OVERTE_DEVICE_ARTIFACT_DIR=str(f.root),
            OVERTE_E2E_FEATURE_IMAGE_POLICY=str(policy_path), OVERTE_PICO_FEATURE_TABLET_WEB='1',
            OVERTE_PICO_BROWSER_RUN_CONFIG=str(f.config.path))
        import importlib
        captured = []
        with patch.dict(os.environ, environment), patch.object(sys, 'argv', [str(ENTRY), '--area', 'tablet-web']):
            support = importlib.import_module('module_support')
            with patch.object(support, 'module_main', side_effect=captured.append): runpy.run_path(str(ENTRY))
            self.assertEqual(1, len(captured)); main = captured[0]; scope = main.__globals__
            def journey(*args, **options):
                options.update(monotonic=lambda:boundary.clock, epoch_ms=boundary.epoch, sleep=boundary.sleep)
                return Journey(*args, **options)
            def write(name, value):
                if name == 'feature-browser-finalization.json': self.assertEqual([None], f.exits)
                f.events.append('write:'+name); (f.root/name).write_text(json.dumps(value))
            scope.update(Client=lambda *_args:f.client, OverteSession=lambda:f.session,
                ARTIFACT_DIR=f.root, Journey=journey, process_identity=lambda:'declared-native-model',
                assert_process=lambda *_args:None, assert_foreground=lambda *_args:None,
                read_private_artifact=lambda _root,name:boundary.files[name], write_json=write)
            prefix = ['python', 'adapter.py', '--kind', 'pico', '--native-binding', '--apk', 'owned.apk']
            with patch('adapters.pico4.browser_session.pico_command', return_value=prefix): main()
        (f.root/'entry-source-pin.json').write_text(json.dumps(self.entry_pin))

    def test_actual_module_runs_common_recipe_inside_one_scope_and_writes_final_only_after_exit(self):
        self.execute()
        f = self.f
        self.assertEqual(1, f.events.count('begin')); self.assertEqual(1, f.events.count('actor.start'))
        self.assertLess(f.events.index('begin'), f.events.index('prepare'))
        self.assertLess(f.events.index('prepare'), f.events.index('actor.start'))
        self.assertLess(f.events.index('consume'), f.events.index('fixture.close'))
        self.assertEqual(1, f.events.count('fixture.close')); self.assertEqual([None], f.exits)
        self.assertTrue((f.root/'feature-browser-finalization.json').exists())
        self.assertEqual('write:feature-browser-finalization.json', f.events[-1])
        report = json.loads((f.root/'feature-journey-observation.json').read_text())
        self.assertEqual(28, len(report['phases'])); self.assertTrue(report['sequenceCompleted'])

    def test_uncertain_original_cli_close_produces_no_final_success_artifact_or_delete_replay(self):
        with self.assertRaises(RuntimeError): self.execute(uncertain_close=True)
        f = self.f
        self.assertEqual(1, f.events.count('fixture.close'))
        self.assertEqual([None], f.exits)
        self.assertFalse((f.root/'feature-browser-finalization.json').exists())
        self.assertNotIn('write:feature-browser-finalization.json', f.events)


if __name__ == '__main__':
    unittest.main()
