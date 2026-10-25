"""Original Home delegates may die; ordinary input needs their new identities.

Qt object lifetimes are explicit weak host models. The real source codec and
immutable preparation-origin joins run unchanged; no native execution claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
from pathlib import Path
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_buttons as buttons,tablet_web_app_origin as origin
from ios.adapters.tablet_web_runtime import TabletRuntimeObserver
from ios.self_tests.test_ios_tablet_web_app_origin import originals_boundary,EPOCH,BINDING
from ios.self_tests.test_ios_tablet_web_buttons import Boundary


class TabletHomeControlTests(unittest.TestCase):
    def test_destroyed_Home_delegates_need_new_current_controls_while_origin_stays_original(self):
        values=originals_boundary();owner,files,scripts,_buttons,_controls,_raw=values;native=Boundary()
        native.manager=deepcopy(scripts['source']['membership']['managers'][0]);native.code=deepcopy(scripts['source']['engines'][0]['code'])
        old={verb:native.bind(native.add(verb)) for verb in ('open','inline','return')};before=native.snapshot();original=deepcopy(before)
        proof=origin.admitted(owner,files,scripts,before,old,BINDING,after_epoch=EPOCH)
        for control in old.values():native.strong.pop(control['control'])
        gc.collect();native.snapshot();new={verb:native.bind(old[verb]['button']) for verb in old};current=native.snapshot()
        buttons.validate(current,dict(schemaVersion=1,action=buttons.ACTION,commandId=current['commandId'],runId=current['runId'],fixtureUrl=current['fixtureUrl']),31,previous=before)
        actual=TabletRuntimeObserver.returned_controls(current,owner);self.assertEqual(new,actual)
        for verb in old:
            self.assertNotEqual(old[verb]['control'],actual[verb]['control']);self.assertEqual(old[verb]['button'],actual[verb]['button'])
            with self.assertRaises(NativeUIError):buttons.selected(current,old[verb],proof['profile'])
            buttons.selected(current,actual[verb],proof['profile'])
        self.assertEqual(original,before);self.assertEqual(proof,origin.admitted(owner,files,scripts,before,old,BINDING,after_epoch=EPOCH))
    def test_real_loader_destroys_old_items_and_the_input_recipe_uses_fresh_metadata(self):
        root=Path(__file__).resolve().parents[4];qml=(root/'interface/resources/qml/hifi/tablet/TabletRoot.qml').read_text()
        self.assertIn('loader.item.destroy()',qml)
        recipe=(root/'tests/device/ios/adapters/tablet_web_actions.py').read_text()
        self.assertIn('self.runtime.returned_controls(actual,self.apps.ownership(generation))[verb]',recipe)
        self.assertIn("if key!='control'",recipe)


if __name__=='__main__':unittest.main()
