"""Inspect the real runner selection while forbidding contract subprocesses.

The complete original-file replay is expensive host composition, not a product
deadline or device verdict. Existing mandatory profile selection stays intact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import redirect_stdout
from collections import Counter
import io
import importlib.util
import json
from pathlib import Path
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
        # Import the runner as the CLI would, then intercept its host dispatch.
        # The grouped runner uses Popen; intercepting the obsolete subprocess.run
        # seam would no longer prevent actual contract execution.
        with patch.object(sys,'path',[str(ENTRY.parent),*sys.path]):
            spec=importlib.util.spec_from_file_location('emote_registration_runner',ENTRY)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        def intercept(groups,**kwargs):
            for group in groups:
                for name in group['files']:
                    command=module.file_command(name)
                    self.assertEqual([sys.executable,str(ROOT/name)],command[:2])
                    calls.append((name,module.file_timeout(name)))
            return 0
        with patch.object(module,'run_groups',side_effect=intercept) as dispatch,\
                patch.object(subprocess,'Popen',side_effect=AssertionError('Selection must not execute contracts')),\
                redirect_stdout(io.StringIO()):
            self.assertEqual(0,module.main(list(flags)))
            dispatch.assert_called_once()
        return vars(module),calls

    def test_default_profile_preserves_required_checks_and_declares_full_composition(self):
        module,calls=self.select();self.assertIn(str(ROOT/'android/phone/tests/device'/FULL),[str(ROOT/name) for name in module['CHECKS']])
        self.assertNotIn(FULL,[Path(name).name for name,_ in calls])
        expected=module['DEPENDENCY_LIGHT_CHECKS']+module['COMMON_HOST_CHECKS']
        self.assertEqual(Counter(expected),Counter(name for name,_ in calls))

    def test_extended_selection_runs_real_entry_once_with_separate_aggregate_host_budget(self):
        module,calls=self.select('--extended');self.assertEqual([(str(Path('android/phone/tests/device')/FULL),10800)],[row for row in calls if Path(row[0]).name==FULL])
        expected=module['DEPENDENCY_LIGHT_CHECKS']+module['COMMON_HOST_CHECKS']+module['EXTENDED_HOST_CHECKS']
        self.assertEqual(Counter(expected),Counter(name for name,_ in calls))
        baseline=json.loads((ENTRY.parent/'phone-runtime-coverage-baseline.json').read_text())
        helper=sys.modules['phone_runtime_groups']
        calibrated={row['file']:row for row in helper.load_calibration()['files']}
        for name,timeout in calls:
            original=baseline['checks'][name]['timeoutSeconds']
            self.assertEqual(original,helper.original_file_timeout(name),name)
            if name in calibrated:
                self.assertEqual(original,calibrated[name]['originalSeconds'],name)
                self.assertEqual(calibrated[name]['calibratedSeconds'],timeout,name)
            else:
                self.assertEqual(original,timeout,name)

    def test_prepared_selection_does_not_silently_claim_the_extended_composition(self):
        module,calls=self.select('--execute');self.assertNotIn(FULL,[Path(name).name for name,_ in calls])
        expected=module['PREPARED_HOST_CHECKS']+module['COMMON_HOST_CHECKS']
        self.assertEqual(Counter(expected),Counter(name for name,_ in calls))


if __name__=='__main__':unittest.main()
