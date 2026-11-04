"""Disjoint complete selector coverage without importing native fixtures."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]


class AudioPCStartCatalogTests(unittest.TestCase):
    def test_three_wrappers_select_all_owning_cases_once(self):
        names=[]
        for suffix in ('','_fences','_quiet'):
            tree=ast.parse((ROOT/'android/vr/pico/tests/device'/('test_audio_pc_start'+suffix+'.py')).read_text())
            declarations=[node for node in tree.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id=='CASE_NAMES' for target in node.targets)]
            self.assertEqual(1,len(declarations));values=ast.literal_eval(declarations[0].value)
            self.assertIs(type(values),tuple);self.assertTrue(values);names.extend(values)
            loaders=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='load_tests']
            self.assertEqual(1,len(loaders));self.assertEqual('return loader.loadTestsFromNames(CASE_NAMES)',ast.unparse(loaders[0].body[0]))
        self.assertEqual(len(names),len(set(names)));expected=set()
        for module,kind in (('test_pico_audio_cleanup_binding','CanonicalCleanupBinding'),
                ('test_pico_audio_cleanup','AudioCleanupTests'),
                ('test_pico_audio_cleanup_poll_period','AudioCleanupPollPeriodTests'),
                ('test_pico_audio_pc_start','AudioPCSourceTests'),
                ('test_pico_audio_pc_start','AudioPCStartTests'),
                ('test_pico_audio_pc_start_binding','AudioPCBindingTests'),
                ('test_pico_audio_raw_archive','AudioRawArchiveTests'),
                ('test_pico_audio_raw_transport','AudioRawTransportTests'),
                ('test_pico_audio_pc_start_catalog','AudioPCStartCatalogTests')):
            tree=ast.parse((ROOT/'tests/device/self_tests'/(module+'.py')).read_text())
            classes=[node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==kind];self.assertEqual(1,len(classes))
            expected.update('self_tests.'+module+'.'+kind+'.'+node.name for node in classes[0].body
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'))
        self.assertEqual(74,len(expected));self.assertEqual(expected,set(names))

if __name__=='__main__':unittest.main()
