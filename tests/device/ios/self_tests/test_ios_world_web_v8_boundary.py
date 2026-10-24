"""Real indexed Node/V8 source reads, with no Qt or feature owner imports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest


class WorldWebV8BoundaryTests(unittest.TestCase):
    def test_indexed_source_callsite_constructor_and_duplicate_context_are_actual_and_never_guessed(self):
        program=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),crypto=require('node:crypto');
const boundary=require(process.argv[1]);let epoch=1700000000000,result;
function execute(source,url){return vm.runInNewContext(source,{capture(){result=boundary.snapshot(url,()=>++epoch)}},{filename:url})}
const source='function callback(){capture();}callback();',url='file:///actual-callback.js';execute(source,url);
assert.equal(result.complete,true);assert.equal(result.frames.length,2);
const sha=crypto.createHash('sha256').update(Buffer.from(source,'utf16le')).digest('hex');
for(const frame of result.frames){assert.equal(frame.compiled.sha256,sha);assert.equal(frame.compiled.codeUnits,source.length);assert.equal(frame.isConstructor,false);assert.equal(frame.isEval,false);assert(frame.scriptId>0)}
assert.deepEqual(result.frames.map(row=>[row.line,row.column]),[[1,21],[1,32]]);
execute('function Owner(){capture();}new Owner();','file:///actual-constructor.js');assert.equal(result.frames[0].isConstructor,true);
const duplicate='file:///ambiguous-source.js';vm.runInNewContext('1+1',{}, {filename:duplicate});
assert.throws(()=>execute(source,duplicate),/Actual assigned VM source is ambiguous/);
'''
        path=Path(__file__).with_name('world_web_emission_boundary.js')
        result=subprocess.run(['node','-e',program,str(path)],capture_output=True,text=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
