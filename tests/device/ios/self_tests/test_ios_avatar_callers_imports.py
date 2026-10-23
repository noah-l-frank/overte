"""Fresh-process reader imports cannot hide cycles behind an existing runtime."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import subprocess
import sys
import unittest


class AvatarCallersImportTests(unittest.TestCase):
    def run_order(self,first):
        program='import '+first+'\nfrom ios.adapters import avatar_call_stack,avatar_scripts,avatar_social_http,avatar_entities\n'
        program+='assert avatar_scripts.VERSION==2 and avatar_social_http.VERSION==2\n'
        result=subprocess.run([sys.executable,'-c',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
    def test_normal_input_can_be_imported_before_actual_caller_sources(self):self.run_order('ios.adapters.normal_input')
    def test_actual_caller_sources_can_be_imported_before_normal_input(self):self.run_order('ios.adapters.avatar_call_stack')


if __name__=='__main__':unittest.main()
