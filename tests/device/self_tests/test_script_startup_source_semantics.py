"""Execute original mobile default entry points; no C++/module/device proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
OWNED = 'file:///private/feature-script-' + 'a' * 32 + '/script-bundle/main.js'


class ScriptStartupSourceTests(unittest.TestCase):
    def execute_entry(self, relative):
        source = (ROOT / relative).read_text()
        program = '''
const owned=OWNED;const requests=[],settings=[];
const Script={include:p=>requests.push({kind:"include",path:p}),require:p=>requests.push({kind:"require",path:p}),
load:p=>requests.push({kind:"load",path:p}),isDebugMode:()=>false,scriptEnding:{connect:()=>{}}};
const Settings={getValue:key=>{settings.push(key);return key==="RunningScripts"?[owned]:false;},setValue:()=>{}};
const Menu={menuExists:()=>false,menuItemExists:()=>false,addMenuItem:()=>{},isOptionChecked:()=>false,
removeMenuItem:()=>{},menuItemEvent:{connect:()=>{}}};
const LODManager={};
SOURCE
process.stdout.write(JSON.stringify({requests,settings}));
'''.replace('OWNED', json.dumps(OWNED)).replace('SOURCE', source)
        result = subprocess.run(['node', '-e', program], text=True, capture_output=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)
        value = json.loads(result.stdout)
        self.assertGreater(len(value['requests']), 3)
        self.assertNotIn('RunningScripts', value['settings'])
        self.assertNotIn(OWNED, [row['path'] for row in value['requests']])
        return value

    def test_original_phone_touch_defaults_do_not_replay_a_saved_user_source(self):
        value = self.execute_entry('scripts/+android_phoneInterface/defaultScripts.js')
        self.assertTrue(any(row['kind'] == 'load' for row in value['requests']))
        self.assertTrue(any(row['kind'] == 'require' for row in value['requests']))

    def test_original_legacy_android_defaults_do_not_replay_a_saved_user_source(self):
        value = self.execute_entry('scripts/+android_interface/defaultScripts.js')
        self.assertTrue(any(row['kind'] == 'include' for row in value['requests']))


if __name__ == '__main__': unittest.main()
