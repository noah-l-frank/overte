/* Private HOST document, unchanged product editor.js consumer. No Qt/Chromium.
 * The only direct value assignment is the declared EMPTY document at birth.
 * Actual edits use product __overteEditor.edit -> normal setRangeText.
 */
'use strict';
const fs=require('fs'),vm=require('vm'),readline=require('readline');
const code=fs.readFileSync(process.argv[2],'utf8');
let config=null,editor=null,input=null,seq=0,issued=false,attempt=null,failed=false;
const emitted=[];let published=null,pointerIssued=false;
function keys(v,names){if(!v||Object.getPrototypeOf(v)!==Object.prototype)return false;const actual=Object.keys(v).sort(),expected=names.slice().sort();return actual.length===expected.length&&actual.every((k,i)=>k===expected[i]);}
const nonce=v=>typeof v==='string'&&/^[0-9a-f]{32}$/.test(v);
function need(v){if(!v)throw Error('Host DOM protocol unavailable');}
class Input{
 constructor(){this.value='';this.type='text';this.selectionStart=this.selectionEnd=0;this.isConnected=true;}
 setRangeText(text,start,end){this.value=this.value.slice(0,start)+text+this.value.slice(end);this.selectionStart=this.selectionEnd=start+text.length;}
 setSelectionRange(start,end,direction){this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction;}
 getBoundingClientRect(){return {x:80,y:60,width:160,height:80};}
 addEventListener(){} removeEventListener(){}
 dispatchEvent(event){if(event.type==='pointerdown'){need(config.controllerFocus);if(!config.ignorePointer&&event.forward&&event.entityId===config.entityId&&event.x>=80&&event.x<=240&&event.y>=60&&event.y<=140)editor.document.activeElement=input;return !config.ignorePointer;}emitted.push({type:event.type,inputType:event.inputType||null,data:event.data===undefined?null:event.data,isComposing:event.isComposing===true});need(emitted.length<=16);return !(event.type==='beforeinput'&&config.cancelBeforeInput===true);}
}
class TextArea{}
class Event{constructor(type,value){Object.assign(this,{type},value);}}
function scope(call){need(config&&call.ownerToken===config.ownerToken&&call.runId===config.runId);}
function publish(){editor.__overteEditor.publish();need(published!==null);return published;}
function handle(call){
 need(!failed&&nonce(call.commandId));seq++;
 if(call.operation==='init'){
  need(!config&&keys(call,['operation','commandId','runId','ownerToken','domInstance','responseId','url','cancelBeforeInput','controllerFocus','ignorePointer','entityId']));
  need(['runId','ownerToken','domInstance','responseId'].every(k=>nonce(call[k]))&&typeof call.url==='string'&&call.url.length<=1024&&typeof call.cancelBeforeInput==='boolean');
  need(typeof call.controllerFocus==='boolean'&&typeof call.ignorePointer==='boolean'&&typeof call.entityId==='string');
  config=call;input=new Input();
  editor={HTMLInputElement:Input,HTMLTextAreaElement:TextArea,InputEvent:Event,CompositionEvent:Event,KeyboardEvent:Event,
   __overteEditorTransport:{editor(state){published=state;}},
   document:{activeElement:call.controllerFocus?null:input,addEventListener(){}}};editor.window=editor;editor.top=editor;
  vm.runInContext(code,vm.createContext(editor),{timeout:500});
  return {ready:true,editor:publish()};
 }
 scope(call);
 if(call.operation==='controller-pointer'){
  need(config.controllerFocus&&!pointerIssued&&keys(call,['operation','commandId','runId','ownerToken','pointer','sessionRef']));
  const ref=call.sessionRef;need(keys(ref,['sessionNonce','sequence','inputId'])&&typeof ref.sessionNonce==='string'&&/^[0-9a-f]{64}$/.test(ref.sessionNonce)&&ref.sequence===1&&ref.inputId==='input-primary-1');
  const p=call.pointer;need(keys(p,['x','y','forward','entityId'])&&Number.isFinite(p.x)&&Number.isFinite(p.y)&&typeof p.forward==='boolean');
  pointerIssued=true;input.dispatchEvent(new Event('pointerdown',p));
  return {pointerDispatched:true,editor:publish()};
 }
 if(call.operation==='ime'){
  need(!issued&&keys(call,['operation','commandId','runId','ownerToken','observedText','cursor','anchor','product']));
  const p=call.product;need(keys(p,['action','commit','preedit','replaceStart','replaceLength','cursor'])&&p.action==='ime'
   &&typeof p.commit==='string'&&p.commit.length<=512&&p.preedit===''&&p.cursor===0
   &&Number.isInteger(p.replaceStart)&&Number.isInteger(p.replaceLength));
  need(input.value===call.observedText&&input.selectionStart===Math.min(call.cursor,call.anchor)&&input.selectionEnd===Math.max(call.cursor,call.anchor));
  issued=true;attempt=call.commandId;
  editor.__overteEditor.edit(p); // Actual unchanged product consumer, ONCE.
  return {issued:true,attemptNonce:attempt,editor:publish(),inputEvents:emitted.slice()};
 }
 need(call.operation==='snapshot'&&keys(call,['operation','commandId','runId','ownerToken']));
 const state=publish();
 return {webDOMVersion:1,requestId:call.commandId,instance:config.domInstance,sequence:seq,capturedEpochMs:Date.now(),
  document:{runId:config.runId,href:config.url,responseId:config.responseId,readyState:'complete'},
  editor:{text:input.value,focused:editor.document.activeElement===input&&state.active===true},attempts:[],echoes:[]};
}
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{
 let call=null;try{
  need(Buffer.byteLength(line,'utf8')<=8192);call=JSON.parse(line);const value=handle(call);
  const result={worldHostProductDomVersion:1,commandId:call.commandId,processId:process.pid,sequence:seq,capturedEpochMs:Date.now(),status:'ready',value};
  const raw=JSON.stringify(result)+'\n';need(Buffer.byteLength(raw,'utf8')<=8192);process.stdout.write(raw);
 }catch(error){failed=true;process.stdout.write(JSON.stringify({worldHostProductDomVersion:1,commandId:call&&call.commandId||'',processId:process.pid,sequence:seq,status:'unavailable'})+'\n');}
});
