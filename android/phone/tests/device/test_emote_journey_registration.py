"""Execute the existing runner's selection with subprocesses fully intercepted.

The complete original-file replay is expensive host composition, not a product
deadline or device verdict. Existing mandatory profile selection stays intact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import redirect_stdout
import io
from pathlib import Path
import runpy
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
ENTRY=ROOT/'android/phone/tests/phone-e2e-runtime-regressions.py'
FULL='test_emote_feature_journey.py'


class EmoteJourneyRegistrationTests(unittest.TestCase):
    def select(self,*flags):
        calls=[]
        def intercept(command,**kwargs):
            calls.append((Path(command[1]).name,kwargs['timeout']))
            return subprocess.CompletedProcess(command,0)
        with patch.object(sys,'argv',[str(ENTRY),*flags]),patch('subprocess.run',side_effect=intercept),redirect_stdout(io.StringIO()):
            module=runpy.run_path(str(ENTRY),run_name='__main__')
        return module,calls

    def test_default_profile_preserves_required_checks_and_declares_full_composition(self):
        module,calls=self.select();self.assertIn(str(ROOT/'android/phone/tests/device'/FULL),[str(ROOT/name) for name in module['CHECKS']])
        self.assertNotIn(FULL,[name for name,_ in calls])
        for name in module['DEPENDENCY_LIGHT_CHECKS']+module['COMMON_HOST_CHECKS']:
            self.assertIn(Path(name).name,[actual for actual,_ in calls])

    def test_extended_selection_runs_real_entry_once_with_separate_aggregate_host_budget(self):
        module,calls=self.select('--extended');self.assertEqual([(FULL,10800)],[row for row in calls if row[0]==FULL])
        for name,timeout in calls:
            if name==FULL:continue
            self.assertEqual(240 if name in ('test_graphics_feature.py','test_create_feature.py') else 90,timeout)

    def test_prepared_selection_does_not_silently_claim_the_extended_composition(self):
        module,calls=self.select('--execute');self.assertNotIn(FULL,[name for name,_ in calls])
        for name in module['PREPARED_HOST_CHECKS']:self.assertIn(Path(name).name,[actual for actual,_ in calls])


if __name__=='__main__':unittest.main()
