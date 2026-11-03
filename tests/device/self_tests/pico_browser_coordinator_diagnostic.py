"""Explicit whole-run diagnostic, currently RED at Actor6 retirement/return.

Run this module explicitly; it is not a default green catalog/unit selection.
Candidate/VR sources are declared host models, never actual device automation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ENTRY=Path(__file__).with_name('pico_browser_coordinator_worker.py').resolve()


class BrowserCoordinatorTests(unittest.TestCase):
    def test_actual_common_parent_and_original_coordinator_return_actual_actor_six(self):
        temporary=tempfile.TemporaryDirectory(prefix='browser-coordinator-')
        self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        p=subprocess.Popen([sys.executable,str(ENTRY),'--area','tablet-web'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,
                OVT_BROWSER_COORDINATOR_ROOT=str(root),PYTHONDONTWRITEBYTECODE='1'))
        try:stdout,stderr=p.communicate(timeout=145)
        except BaseException:
            if p.poll() is None:p.terminate()
            stdout,stderr=p.communicate(timeout=20)
            (root/'parent.stdout.bin').write_bytes(stdout);(root/'parent.stderr.bin').write_bytes(stderr)
            raise
        (root/'parent.stdout.bin').write_bytes(stdout);(root/'parent.stderr.bin').write_bytes(stderr)
        self.assertEqual(0,p.returncode,stderr.decode('utf-8','replace'))
        self.assertEqual(b'',stdout)
        result=json.loads((root/'coordinator-result.json').read_text())
        self.assertTrue(result['sequenceCompleted'] and result['actualCoordinator'] and result['actualActorSix'])
        self.assertFalse(result['canonicalCandidateRouter'] or result['deviceAcceptance'])
        self.assertEqual(28,result['phases']);self.assertLess(result['elapsed'],120)
        for name in ('parent','child','actor'):
            source=json.loads((root/(name+'-sources.json')).read_text())
            self.assertEqual([],source['changed']);self.assertEqual(source['before'],source['after'])
        self.assertFalse(Path(f'/proc/{p.pid}').exists())


if __name__=='__main__':unittest.main()
