"""Static owning selector coverage: no native fixture construction or imports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]


class NavigationGenerationFrameCatalogTests(unittest.TestCase):
    def test_focused_wrappers_are_disjoint_and_cover_actual_owning_cases(self):
        names=[]
        for name in ('test_navigation_generation_frames.py','test_navigation_generation_frame_fences.py'):
            tree=ast.parse((ROOT/'android/vr/pico/tests/device'/name).read_text())
            declarations=[node for node in tree.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id=='CASE_NAMES' for target in node.targets)]
            self.assertEqual(1,len(declarations));selected=ast.literal_eval(declarations[0].value)
            self.assertIs(type(selected),tuple);self.assertTrue(selected)
            self.assertTrue(all(type(value) is str for value in selected));names.extend(selected)
            loaders=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='load_tests']
            self.assertEqual(1,len(loaders))
            self.assertEqual("return loader.loadTestsFromNames(CASE_NAMES)",ast.unparse(loaders[0].body[0]))
        self.assertEqual(len(names),len(set(names)))
        expected=set()
        for module,kind in (('test_pico_navigation_generation_frames','NavigationGenerationFramesTests'),
                ('test_pico_navigation_capture_namespaces','NavigationRetiredCaptureNamespacesTests'),
                ('test_pico_navigation_generation_frame_catalog','NavigationGenerationFrameCatalogTests')):
            tree=ast.parse((ROOT/'tests/device/self_tests'/(module+'.py')).read_text())
            classes=[node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==kind]
            self.assertEqual(1,len(classes))
            expected.update('self_tests.'+module+'.'+kind+'.'+node.name for node in classes[0].body
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'))
        self.assertEqual(expected,set(names))

if __name__=='__main__':unittest.main()
