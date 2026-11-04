"""Actual probe settings dispatch; Native getter/file writer are declared leaves."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import subprocess
from pathlib import Path
import unittest

PROBE=Path(__file__).resolve().parents[1]/'probe/overte_e2e_probe.js'


class SnapshotSettingsProbeTests(unittest.TestCase):
    def setUp(self):
        source=PROBE.read_text();position=source.index('command.action === "feature-pico-snapshot-settings-originals"')
        start=source.rindex('        if (command && command.schemaVersion === 1',0,position)
        end=source.index('        if (command && command.schemaVersion === 1',position)
        helper=source.index('    function objectKeysMatch(');helper_end=source.index('\n    }',helper)+6
        self.program='''const assert=require('node:assert/strict');
let lastSnapshotSettingsRequest='',commands=[],saved=[],throwSave=false;
let Test={featureSnapshotSettingsOriginals:c=>{commands.push(c);return {commandId:c.commandId,declaredNativeLeaf:'unchanged'};},saveObject:(value,path)=>{saved.push({value,path});if(throwSave)throw Error('unknown save response');}};
'''+source[helper:helper_end]+'\nfunction applyClientCommand(command){\n'+source[start:end]+'''\n}
function command(id,scope){let c={schemaVersion:1,commandId:id.repeat(32),runId:'f'.repeat(32),action:'feature-pico-snapshot-settings-originals'};if(scope!==undefined)c.settingsScope=scope;return c;}
'''

    def run_node(self,assertions):
        result=subprocess.run(['node','-e',self.program+assertions],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5,check=False)
        self.assertEqual(0,result.returncode,result.stderr.decode('utf-8','replace'))

    def test_original_default_and_explicit_scope2_route_exact_native_command_once(self):
        self.run_node('''
for(let [id,scope] of [['a',undefined],['b',2]]){
 let c=command(id,scope);applyClientCommand(c);applyClientCommand(c);
 assert.equal(commands.at(-1),c);assert.deepEqual(saved.at(-1).value,{commandId:c.commandId,declaredNativeLeaf:'unchanged'});
 assert.equal(saved.at(-1).path,'feature-pico-snapshot-settings-originals.json');
}
assert.equal(commands.length,2);assert.equal(saved.length,2);
''')

    def test_unknown_scope_or_extra_fields_refuse_before_native_or_nonce_consumption(self):
        self.run_node('''
for(let scope of [1,3,'2',true,null,[],{}]){applyClientCommand(command('a',scope));}
let extra=command('b',2);extra.desired=true;applyClientCommand(extra);
let malformed=command('c',2);malformed.commandId=true;applyClientCommand(malformed);
assert.equal(commands.length,0);assert.equal(saved.length,0);assert.equal(lastSnapshotSettingsRequest,'');
''')

    def test_scope2_missing_or_throwing_native_stays_unavailable_and_unknown_save_never_repeats(self):
        self.run_node('''
delete Test.featureSnapshotSettingsOriginals;applyClientCommand(command('a',2));
assert.deepEqual(saved.at(-1).value,{snapshotSettingsOriginalsVersion:2,commandId:'a'.repeat(32),available:false});
Test.featureSnapshotSettingsOriginals=c=>{commands.push(c);throw Error('declared native failure');};
applyClientCommand(command('b',2));assert.equal(saved.at(-1).value.available,false);
throwSave=true;assert.throws(()=>applyClientCommand(command('c',2)));let count=saved.length;
applyClientCommand(command('c',2));assert.equal(saved.length,count);assert.equal(commands.length,2);
''')


if __name__=='__main__':unittest.main()
