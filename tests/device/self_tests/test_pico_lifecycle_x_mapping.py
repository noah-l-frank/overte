"""Execute the original Pico X mapping in explicit JS/Controller boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[3]
SETUP=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[1],source=fs.readFileSync(root+'/scripts/system/tablet-ui/tabletUI.js','utf8');
const start=source.indexOf('    var picoBackMapping = null;'),end=source.indexOf('    var updateShowTabletTimer',start);
assert(start>=0 && end>start,'Original normal Pico Back mapping boundary changed');
let events=[],press=null,enabled=0,setting=true;
const scope={Settings:{getValue:(name,fallback)=>{assert.equal(name,'deferTabletCreationUntilOpen');return setting;}},
 controllerStandard:{LeftPrimaryThumb:501},Controller:{newMapping:name=>{
 assert.equal(name,'pico-tablet-x-back');return {from:button=>{assert.equal(button,501);return {
 peek:()=>({to:callback=>{press=callback;}})};},enable:()=>enabled++};}},
 checkTablet:()=>events.push('check'),HMD:{closeTablet:flag=>{assert.equal(flag,false);events.push('close');}},
 print:()=>{},gTablet:{tabletShown:true,onHomeScreen:()=>false,gotoHomeScreen:()=>events.push('home')}};
vm.createContext(scope);function install(){vm.runInContext(source.slice(start,end),scope);}
'''


class PicoLifecycleXMappingTests(unittest.TestCase):
    def run_case(self,body):
        result=subprocess.run(['node','-e',SETUP+body,str(ROOT)],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
    def test_first_actual_x_press_on_a_shown_create_page_goes_home_and_release_does_nothing(self):
        self.run_case("install();assert.equal(enabled,1);press(0);assert.deepEqual(events,[]);press(1);assert.deepEqual(events,['check','home']);")
    def test_next_actual_x_press_on_home_closes_the_tablet(self):
        self.run_case("install();scope.gTablet.onHomeScreen=()=>true;press(1);assert.deepEqual(events,['check','close']);")
    def test_no_tablet_hidden_tablet_and_disabled_pico_setting_do_not_navigate(self):
        self.run_case("install();scope.gTablet.tabletShown=false;press(1);scope.gTablet=null;press(1);assert.deepEqual(events,['check','check']);")
        self.run_case("setting=false;install();assert.equal(press,null);assert.equal(enabled,0);")


if __name__=='__main__':unittest.main()
