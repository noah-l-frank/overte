// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Execute the complete original command dispatcher; only native/clock/timer endpoints are seams.
'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),vm=require('vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../../../../tests/device/probe/overte_e2e_probe.js'),'utf8');
const body=source.slice(source.indexOf('    function applyClientCommand(command) {'),source.indexOf('    function pollClientCommand()'));
const keys=source.slice(source.indexOf('    function objectKeysMatch('),source.indexOf('    function httpUrl('));
assert(body.startsWith('    function applyClientCommand'));assert(keys.startsWith('    function objectKeysMatch'));
function fixture(getter) {
 const queue=[],saved=[],calls=[];const sandbox={Date:{now:()=>1000},lastPicoAssetsReadRequest:'',lastPicoAssetsReadRetirementRequest:'',
  Script:{setTimeout:(callback,delay)=>{assert.equal(delay,20);queue.push(callback);}},Test:{saveObject:(packet,file)=>saved.push({packet,file})}};
 for(const name of ['featurePicoAssetsRead','featurePicoAssetsReadRetire'])sandbox.Test[name]=(...args)=>{calls.push({name,args:JSON.parse(JSON.stringify(args))});return getter(...args);};
 vm.createContext(sandbox);vm.runInContext(keys+'\n'+body,sandbox);return {sandbox,saved,calls,drain(){let count=0;while(queue.length){assert(++count<=230);queue.shift()();}return count;}};
}
const run='b'.repeat(32),id='a'.repeat(32);
for(const [action,extra,file] of [['observe',{},'observation'],['download',{hash:'c'.repeat(64)},'download'],['resolve',{path:'/e2e-'+run+'/main.gltf'},'resolve']]){
 const command={schemaVersion:1,commandId:id,runId:run,action:'feature-pico-assets-'+action,...extra};
 const f=fixture(value=>({schemaVersion:1,requestId:value.commandId,available:true,source:{original:'native endpoint boundary'}}));
 f.sandbox.applyClientCommand(command);f.sandbox.applyClientCommand(command);assert.equal(f.calls.length,1);assert.equal(f.saved.length,1);
 assert.equal(f.saved[0].file,'feature-pico-assets-'+file+'.json');assert.deepStrictEqual(f.calls[0].args,[command,false]);
}
{
 let attempts=0;const command={schemaVersion:1,commandId:id,runId:run,action:'feature-pico-assets-observe'};
 const f=fixture(value=>++attempts<3?{requestId:value.commandId,pending:true}:{requestId:value.commandId,available:true});
 f.sandbox.applyClientCommand(command);assert.equal(f.saved.length,0);f.drain();assert.equal(attempts,3);assert.equal(f.saved.length,1);
}
{
 const command={schemaVersion:1,commandId:id,runId:run,action:'feature-pico-assets-observe'};
 const f=fixture(value=>({requestId:value.commandId,pending:true}));f.sandbox.applyClientCommand(command);f.drain();
 assert.equal(f.calls.length,230);assert.equal(f.calls[223].args[1],false);assert.equal(f.calls[224].args[1],true);
 assert.equal(f.saved[0].packet.available,false);assert.equal(f.saved[0].packet.pending,undefined);
}
{
 const original={schemaVersion:1,commandId:'d'.repeat(32),runId:run,action:'feature-pico-assets-observe'};
 const command={schemaVersion:1,commandId:id,action:'feature-pico-assets-read-retire',original};
 const f=fixture(value=>({requestId:value.commandId,available:true}));f.sandbox.applyClientCommand(command);f.sandbox.applyClientCommand(command);
 assert.equal(f.calls.length,1);assert.equal(f.calls[0].name,'featurePicoAssetsReadRetire');assert.deepStrictEqual(f.calls[0].args,[command]);
 assert.equal(f.saved[0].file,'feature-pico-assets-read-retirement.json');
 const pending=fixture(value=>({requestId:value.commandId,pending:true}));pending.sandbox.applyClientCommand(command);pending.drain();
 assert.equal(pending.calls.length,230);assert.equal(pending.saved[0].packet.available,false);
}
for(const result of [()=>{throw Error('native unavailable');},()=>({requestId:'e'.repeat(32),available:true})]){
 const f=fixture(result);f.sandbox.applyClientCommand({schemaVersion:1,commandId:id,runId:run,action:'feature-pico-assets-observe'});
 assert.equal(f.saved.length,1);assert.equal(f.saved[0].packet.available,false);
}
console.log('Original Assets probe dispatcher: 8 bounded source/retirement cases passed');
