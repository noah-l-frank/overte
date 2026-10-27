"""Actual product default loader; menu/Script boundaries are read-only models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[4]


class SnapshotDefaultLoaderTests(unittest.TestCase):
    def test_actual_default_loader_includes_snapshot_and_keeps_separate_debug_mode_distinct(self):
        program='''const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(SOURCE,'utf8');
for(const separate of [false,true]){
 const included=[],loaded=[];let writes=0;
 const context=vm.createContext({Window:{interstitialModeEnabled:false},
  Settings:{getValue:(key,fallback)=>key==='_debugDefaultScriptsIsChecked'?separate:fallback,setValue:()=>{writes++;throw Error('unexpected setting mutation');}},
  Menu:{menuExists:()=>false,menuItemExists:()=>false,isOptionChecked:()=>separate,
   menuItemEvent:{connect:()=>{}},triggerOption:()=>{throw Error('unexpected option mutation');}},
  ScriptDiscoveryService:{getRunning:()=>[]},Script:{include:path=>included.push(path),load:path=>loaded.push(path),scriptEnding:{connect:()=>{}}},
  console:{log:()=>{}}});
 vm.runInContext(source,context,{timeout:1000});
 const snapshots=(rows)=>rows.filter(path=>path==='system/snapshot.js').length;
 if(writes!==0 || snapshots(included)!==(separate?0:1) || snapshots(loaded)!==(separate?1:0))throw Error('wrong actual include/load source path');
}
'''.replace('SOURCE',json.dumps(str(ROOT/'scripts/defaultScripts.js')))
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
