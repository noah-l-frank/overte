"""Original normal navigation/Chat QML handlers in a synthetic Node boundary.

No Qt, keyboard, controller, lifecycle or device acceptance is established here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[3]
SETUP=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[1];
function original(path,start,end){
 const source=fs.readFileSync(root+'/'+path,'utf8'),a=source.indexOf(start),b=source.indexOf(end,a+start.length);
 assert(a>=0&&b>a,'Original QML boundary changed');return source.slice(a,b);
}
let navigations=[];
const scope={semanticBackTarget:'',semanticSourceHistory:[],loader:{source:'create.qml',item:{}},
 tabletProxy:{gotoHomeScreen:()=>navigations.push('home'),hideAndroidTablet:()=>navigations.push('hide'),
 loadQMLSource:source=>navigations.push(source)}};
vm.createContext(scope);
vm.runInContext(original('interface/resources/qml/hifi/tablet/WindowRoot.qml',
 '    function returnToPreviousSemanticScreen(', '    function loadWebContent('),scope);
'''


class LifecycleSourceSemantics(unittest.TestCase):
    def run_case(self,body):
        result=subprocess.run(['node','-e',SETUP+body,str(ROOT)],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_original_semantic_back_can_leave_the_page_on_its_first_press(self):
        self.run_case(r'''
assert.equal(scope.returnToPreviousSemanticScreen(),true);assert.deepEqual(navigations,['home']);
navigations=[];scope.semanticSourceHistory=['hifi/tablet/TabletHome.qml'];
assert.equal(scope.returnToPreviousSemanticScreen(),true);assert.deepEqual(navigations,['home']);
assert.equal(scope.semanticBackTarget,'hifi/tablet/TabletHome.qml');
assert.equal(scope.semanticSourceHistory.length,0);
''')

    def test_original_page_specific_back_can_consume_the_action_before_navigation(self):
        self.run_case(r'''
let calls=0;scope.loader.item={handleTabletBack(){calls++;return true;}};
assert.equal(scope.returnToPreviousSemanticScreen(),true);assert.equal(calls,1);
assert.equal(navigations.length,0);
// A generic "Back hides only the keyboard" assertion cannot cover both
// original page profiles. The actual Create page has no subordinate handler.
''')

    def test_original_chat_hidden_releases_focus_without_copying_or_clearing_its_draft(self):
        self.run_case(r'''
Object.assign(scope,{textArea:{text:'owned Chat draft',focus:true},keyboardRaised:true});
vm.runInContext(original('scripts/communityScripts/armored-chat/armored_chat.qml',
 '    function fromScript(', '    function toScript('),scope);
scope.fromScript({type:'chat.hidden'});assert.equal(scope.textArea.focus,false);
assert.equal(scope.keyboardRaised,false);assert.equal(scope.textArea.text,'owned Chat draft');
// The property proves source behavior; actual OS/VR keyboard absence still
// requires the independent original native keyboard observation.
''')


if __name__=='__main__':unittest.main()
