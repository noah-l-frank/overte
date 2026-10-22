"""Actual passive geometry JS in a synthetic DOM; no browser/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from self_tests import test_web_dom_observation as original

GEOMETRY='''
w.innerWidth=640;w.innerHeight=480;w.visualViewport={scale:1,offsetLeft:0,offsetTop:0};
doc.title='Owned document';let top=node('text');doc.elementFromPoint=()=>top;
for(const id of ['text','foreign','bridge']){const item=node(id);item.contains=other=>item===other;
item.getBoundingClientRect=()=>({left:80,top:60,width:160,height:80});item.selectionStart=1;item.selectionEnd=3;item.selectionDirection='backward';}
node('text').value='old';node('foreign').tagName='INPUT';node('foreign').type='url';node('foreign').value='http://example.invalid/';
'''
class PicoBrowserGeometryTests(unittest.TestCase):
    def run_case(self,body):original.WebDOMTests.run_case(self,GEOMETRY+body)
    def test_actual_rect_hit_focus_native_selection_and_read_only_profile(self):
        self.run_case('''doc.activeElement=node('text');const a=source.readGeometry(nonce,'text');
assert.deepEqual(a.center,{x:160,y:100});assert.equal(a.hit,true);assert.equal(a.editor.focused,true);
assert.deepEqual(a.editor,{text:'old',focused:true,cursor:1,anchor:3});assert.equal(node('text').value,'old');
assert.equal(requests.length,0);assert.equal(source.read(nonce).document.title,undefined);
assert.equal(source.readOwned(nonce).document.title,'Owned document');
const b=source.readGeometry(nonce,'text');assert.equal(b.instance,a.instance);assert(b.sequence>a.sequence);''')
    def test_original_occlusion_disabled_disconnected_and_foreign_focus_are_not_success(self):
        self.run_case('''top={};node('text').disabled=true;node('text').isConnected=false;doc.activeElement=node('foreign');
const a=source.readGeometry(nonce,'text');assert.equal(a.hit,false);assert.equal(a.enabled,false);
assert.equal(a.connected,false);assert.equal(a.editor.focused,false);assert.equal(requests.length,0);''')
    def test_unknown_selector_missing_or_nonfinite_original_geometry_refuses(self):
        for edit in ("source.readGeometry(nonce,'password');", "node('text').getBoundingClientRect=()=>({left:NaN,top:0,width:1,height:1});source.readGeometry(nonce,'text');",
                     "node('text').getBoundingClientRect=()=>({left:0,top:0,width:0,height:1});source.readGeometry(nonce,'text');"):
            with self.subTest(edit=edit):self.run_case("assert.throws(()=>{"+edit+"},/UNAVAILABLE/);assert.equal(requests.length,0);")
    def test_actual_viewport_offset_and_scale_are_preserved_without_scroll_or_zoom(self):
        self.run_case('''w.visualViewport={scale:2,offsetLeft:7,offsetTop:9};const a=source.readGeometry(nonce,'text');
assert.deepEqual(a.viewport,{width:640,height:480,scale:2,offsetLeft:7,offsetTop:9});assert.equal(node('text').value,'old');''')
    def test_retired_source_cannot_supply_new_geometry(self):
        self.run_case("source.readGeometry(nonce,'text');source.retire();assert.throws(()=>source.readGeometry(nonce,'text'),/UNAVAILABLE/);")
if __name__=='__main__':unittest.main()
