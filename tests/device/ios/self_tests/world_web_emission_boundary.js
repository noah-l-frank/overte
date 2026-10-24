// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual Node/V8 indexed source and call locations; Qt remains a host model.
'use strict';
const inspector=require('node:inspector');
const crypto=require('node:crypto');
const session=new inspector.Session();session.connect();
const scripts=new Map();const observed=new Map();
session.on('Debugger.scriptParsed',({params})=>scripts.set(params.scriptId,params));
session.post('Debugger.enable');
function sha(bytes){return crypto.createHash('sha256').update(bytes).digest('hex')}
function snapshot(url,clock){
 let result=null,failure=null;
 const previous=Error.prepareStackTrace;let actualStack;
 try{Error.prepareStackTrace=(_error,frames)=>frames;actualStack=new Error().stack}
 finally{Error.prepareStackTrace=previous}
 const onPause=({params})=>{
  try {
   const roots=Array.from(scripts.values()).filter(row=>row.url===url);
   if(roots.length!==1)throw Error('Actual assigned VM source is ambiguous');
   const context=roots[0].executionContextId;
   const callFrames=params.callFrames.filter(frame=>scripts.get(frame.location.scriptId)?.executionContextId===context);
   const urls=new Set(callFrames.map(frame=>scripts.get(frame.location.scriptId).url));
   const flags=actualStack.filter(frame=>urls.has(frame.getScriptNameOrSourceURL()));
   if(flags.length!==callFrames.length)throw Error('Actual structured V8 callsite inventory differs');
   const frames=callFrames.map((frame,index)=>{
    const parsed=scripts.get(frame.location.scriptId);let source;
    const actual=flags[index];
    if(actual.getLineNumber()!==frame.location.lineNumber+1||actual.getColumnNumber()!==frame.location.columnNumber+1)throw Error('Actual V8 callsite differs');
    session.post('Debugger.getScriptSource',{scriptId:frame.location.scriptId},(error,value)=>{if(error)throw error;source=value.scriptSource});
    if(typeof source!=='string')throw Error('Actual indexed V8 source unavailable');
    const urlSha256=sha(Buffer.from(parsed.url,'utf8')),bytes=Buffer.from(source,'utf16le');
    const candidate={urlSha256,encoding:'utf-16le-code-units',codeUnits:bytes.length/2,sha256:sha(bytes)};
    if(!observed.has(frame.location.scriptId))observed.set(frame.location.scriptId,{...candidate,firstObservedEpochMs:clock()});
    const compiled=observed.get(frame.location.scriptId);
    for(const key of Object.keys(candidate))if(compiled[key]!==candidate[key])throw Error('Actual compiled ScriptId changed');
    return {scriptId:Number(frame.location.scriptId),line:frame.location.lineNumber+1,column:frame.location.columnNumber+1,
     sourceUrlSha256:urlSha256,compiled:{...compiled},isEval:actual.isEval(),isConstructor:actual.isConstructor()};
   });
   result={emitStackVersion:1,instance:INSTANCE,complete:frames.length>0&&frames.length<=32,frames};
  }catch(error){failure=error}
  finally{session.post('Debugger.resume')}
 };
 session.once('Debugger.paused',onPause);session.post('Debugger.pause');
 if(failure)throw failure;if(!result)throw Error('Actual V8 pause observation unavailable');return result;
}
const INSTANCE=crypto.randomBytes(16).toString('hex');
module.exports={snapshot};
