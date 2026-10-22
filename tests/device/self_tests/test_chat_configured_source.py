"""Actual configure helper over a disposable local Git source fixture only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
HELPER=ROOT/'cmake/e2e/FeatureSourceIdentity.cmake'


class ConfiguredSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='overte-chat-configure-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir(mode=0o700)
        self.git('init','-q','--initial-branch=test/fixture/e2e-source')
        (self.source/'producer.cpp').write_text('int main(){return 0;}\n')
        self.git('add','producer.cpp');self.git('-c','user.name=Overte E2E Fixture','-c','user.email=e2e-fixture@invalid.example','commit','-qm','Record original source fixture')
        self.revision=self.git('rev-parse','HEAD').strip()
    def git(self,*arguments):
        return subprocess.check_output(['git','-C',str(self.source),*arguments],text=True,stderr=subprocess.DEVNULL)
    def identity(self,source=None):
        script=self.root/'inspect.cmake';output=self.root/'identity.txt';source=self.source if source is None else source
        script.write_text(f'include("{HELPER}")\n'
            f'overte_e2e_source_identity("{source}")\n'
            f'file(WRITE "{output}" "${{OVERTE_E2E_CONFIGURED_SOURCE_REVISION}}\\n${{OVERTE_E2E_SOURCE_DEPENDENCIES}}")\n')
        subprocess.run(['cmake','-P',str(script)],check=True,capture_output=True,text=True,timeout=5)
        revision,dependencies=output.read_text().split('\n',1);return revision,dependencies.split(';') if dependencies else []
    def test_actual_clean_configure_revision_and_tracked_sources_are_original_dependencies(self):
        revision,dependencies=self.identity();self.assertEqual(self.revision,revision)
        self.assertIn(str(self.source/'producer.cpp'),dependencies);self.assertTrue(any(value.endswith('/HEAD') for value in dependencies))
    def test_modified_staged_untracked_and_non_root_sources_remain_unknown(self):
        for staged in (False,True):
            (self.source/'producer.cpp').write_text('int main(){return 1;}\n')
            if staged:self.git('add','producer.cpp')
            self.assertEqual(('',[]),self.identity())
            self.git('restore','--staged','producer.cpp');self.git('restore','producer.cpp')
        (self.source/'foreign.h').write_text('#define FOREIGN 1\n');self.assertEqual(('',[]),self.identity())
        (self.source/'foreign.h').unlink();nested=self.source/'nested';nested.mkdir()
        self.assertEqual(('',[]),self.identity(nested))
    def test_export_without_git_does_not_adopt_parent_or_expected_revision(self):
        export=self.root/'export';export.mkdir(mode=0o700)
        self.assertEqual(('',[]),self.identity(export))


if __name__=='__main__':unittest.main()
