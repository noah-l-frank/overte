// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Execute the complete original dispatcher, with only the native getter as a seam.
'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),vm=require('vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../../../../tests/device/probe/overte_e2e_probe.js'),'utf8');
const body=source.slice(source.indexOf('    function applyClientCommand(command) {'),source.indexOf('    function pollClientCommand()'));
const keys=source.slice(source.indexOf('    function objectKeysMatch('),source.indexOf('    function httpUrl('));
for(const operation of ['arm-current-consumption','observe-current-consumption','observe-current-keyboard']) {
  const keyboard=operation==='observe-current-keyboard';
  const getter=keyboard?'featurePicoWorldCurrentKeyboard':'featurePicoWorldCurrentConsumption';
  const output=keyboard?'feature-world-current-keyboard.json':'feature-world-current-consumption.json';
  const command={schemaVersion:1,commandId:'a'.repeat(32),action:'pico-world-web',operation};
  const original={commandId:command.commandId,status:'unavailable',source:{original:'literal native producer bytes'}};
  for(const fault of ['none','missing','throws','foreign']) {
    const saved=[],calls=[];
    const Test={saveObject:(packet,file)=>saved.push({packet,file})};
    if(fault!=='missing') Test[getter]=value=>{
      calls.push(value);
      if(fault==='throws') throw Error('original unavailable');
      return fault==='foreign'?{...original,commandId:'b'.repeat(32)}:original;
    };
    const context={Test}; vm.createContext(context);vm.runInContext(keys+'\n'+body,context);
    assert.strictEqual(context.applyClientCommand(command),true);
    assert.strictEqual(saved.length,1);assert.strictEqual(saved[0].file,output);
    assert.strictEqual(calls.length,fault==='missing'?0:1);
    if(fault==='none') assert.strictEqual(saved[0].packet,original);
    else assert.strictEqual(JSON.stringify(saved[0].packet),'{}');
  }
}
console.log('World consumption probe: 12 original-dispatch/missing-source cases passed (8 trace, 4 keyboard)');
