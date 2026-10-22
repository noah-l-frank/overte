// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Whole original avatarapp.js, Pico path (no Phone global). Tablet/context,
// MyAvatar/native calls and timers are explicit host actors, never loaded models.
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {StringDecoder}=require('node:string_decoder');
const root=process.argv[2];assert(root);
class Signal {
    constructor(){this.callbacks=new Set();}
    connect(callback){assert.equal(typeof callback,'function');this.callbacks.add(callback);}
    disconnect(callback){assert(this.callbacks.delete(callback));}
    emit(...args){for(const callback of [...this.callbacks])callback(...args);}
}
const signals=[];function signal(){const value=new Signal();signals.push(value);return value;}
const button={clicked:signal(),editProperties(value){assert.equal(typeof value.isActive,'boolean');}};
let qml=[],calls=[],source='',timerId=0,scale=1;const timers=new Map(),bookmarkRows={},bookmarkCalls=[],scaleCalls=[];
const inputBuffer=Buffer.alloc(16384),inputDecoder=new StringDecoder('utf8');let pendingInput='';
function readLine(){for(;;){const end=pendingInput.indexOf('\n');if(end>=0){const value=pendingInput.slice(0,end);pendingInput=pendingInput.slice(end+1);return value;}
    const count=fs.readSync(0,inputBuffer,0,inputBuffer.length,null);if(count===0){assert.equal(inputDecoder.end(),'');assert.equal(pendingInput,'');return null;}pendingInput+=inputDecoder.write(inputBuffer.subarray(0,count));}}
function nativeBookmark(method,name=''){
    process.stdout.write(JSON.stringify({nativeBookmarkCall:{method,name,avatarUrl:avatar.skeletonModelURL,scale}})+'\n');
    const raw=readLine();assert.notEqual(raw,null);const response=JSON.parse(raw);assert.deepEqual(Object.keys(response),['nativeBookmarkReply']);
    const result=response.nativeBookmarkReply;assert(result&&typeof result.bookmarks==='object');
    for(const key of Object.keys(bookmarkRows))delete bookmarkRows[key];Object.assign(bookmarkRows,result.bookmarks);return result;
}
const nativeBookmarks=process.argv.includes('--native-bookmarks');
const tablet={fromQml:signal(),screenChanged:signal(),
    addButton(value){assert.equal(value.text,'AVATAR');return button;},removeButton(value){assert.equal(value,button);},
    loadQMLSource(value){assert.equal(value,'hifi/AvatarApp.qml');source=value;this.screenChanged.emit('QML',value);},
    gotoHomeScreen(){this.screenChanged.emit('Home','');},sendToQml(value){qml.push(JSON.parse(JSON.stringify(value)));}};
const avatar={displayName:'owned host',sessionUUID:'77777777-7777-4777-8777-777777777777',skeletonModelURL:'qrc:/meshes/defaultAvatar_full.fst',
    collisionSoundURL:'',getAvatarEntitiesVariant(){return [];},getJointNames(){return ['Hips'];},getAvatarScale(){return scale;},
    getDominantHand(){return 'right';},getHmdAvatarAlignmentType(){return 'head';},getCollisionsEnabled(){return true;},getOtherAvatarsCollisionsEnabled(){return true;},
    getAnimGraphUrl(){return '';},getAnimGraphOverrideUrl(){return '';},getFullAvatarURLFromPreferences(){return this.skeletonModelURL;},
    useFullAvatarURL(value){calls.push(value);const changed=this.skeletonModelURL!==value;this.skeletonModelURL=value;if(changed)this.skeletonModelURLChanged.emit();}};
avatar.setAvatarScale=function(value){assert(Number.isFinite(value)&&value>=.1&&value<=4);const changed=scale!==value;scale=value;scaleCalls.push(value);if(changed)this.targetScaleChanged.emit();};
for(const [setter,value] of Object.entries({setDominantHand:'right',setHmdAvatarAlignmentType:'head',setCollisionsEnabled:true,setOtherAvatarsCollisionsEnabled:true,setAnimGraphOverrideUrl:''})){
    avatar[setter]=function(actual){assert.equal(actual,value);};
}
for(const name of ['skeletonModelURLChanged','dominantHandChanged','hmdAvatarAlignmentTypeChanged','collisionsEnabledChanged','otherAvatarsCollisionsEnabledChanged','newCollisionSoundURL','animGraphUrlChanged','targetScaleChanged'])avatar[name]=signal();
const clone=value=>JSON.parse(JSON.stringify(value));
const bookmarks={getBookmarks(){if(nativeBookmarks)nativeBookmark('all');return clone(bookmarkRows);},getBookmark(name){if(nativeBookmarks)return nativeBookmark('get',name).bookmark;return bookmarkRows[name]&&clone(bookmarkRows[name]);},
    addBookmark(name){assert.match(name,/^e2e-[0-9a-f]{32}$/);assert(!bookmarkRows[name]);bookmarkCalls.push(['save',name]);
        if(nativeBookmarks)nativeBookmark('save',name);else bookmarkRows[name]={version:3,avatarUrl:avatar.skeletonModelURL,avatarScale:scale,avatarEntites:[],avatarIcon:''};this.bookmarkAdded.emit(name);},
    loadBookmark(name){assert(bookmarkRows[name]);bookmarkCalls.push(['load',name]);const row=bookmarkRows[name];
        avatar.useFullAvatarURL(row.avatarUrl);avatar.setAvatarScale(row.avatarScale);this.bookmarkLoaded.emit(name);},
    removeBookmark(name){assert(bookmarkRows[name]);bookmarkCalls.push(['delete',name]);if(nativeBookmarks)nativeBookmark('delete',name);else delete bookmarkRows[name];this.bookmarkDeleted.emit(name);}};
for(const name of ['bookmarkLoaded','bookmarkDeleted','bookmarkAdded'])bookmarks[name]=signal();
const entities={addingWearable:signal(),deletingWearable:signal(),mousePressOnEntity:signal()};
const script={resolvePath(value){assert.equal(value,'html/js/marketplacesInject.js');return require('node:url').pathToFileURL(root+'/scripts/system/'+value).href;},include(value){assert.equal(value,'/~/system/libraries/controllers.js');},scriptEnding:signal(),
    setTimeout(callback,ms){assert.equal(typeof callback,'function');assert.equal(ms,300);timers.set(++timerId,callback);return timerId;},
    clearTimeout(id){assert(timers.delete(id));},setInterval(){throw Error('Unexpected wearable interval in URL-only scope');},clearInterval(){throw Error('Unexpected interval cleanup');}};
const context=vm.createContext({Script:script,Tablet:{getTablet(value){assert.equal(value,'com.highfidelity.interface.tablet.system');return tablet;}},
    MyAvatar:avatar,AvatarBookmarks:bookmarks,Entities:entities,HMD:{active:true},Camera:{mode:'first person'},Quat:{},
    AddressManager:{isConnected:true},Account:{},UserActivityLogger:{},Messages:{messageReceived:signal()},print(){},console:{debug(){},log(){},warn(){}}});
vm.runInContext(fs.readFileSync(root+'/scripts/system/avatarapp.js','utf8'),context,{filename:'original-avatarapp.js',timeout:2000});
button.clicked.emit();
function reply(){process.stdout.write(JSON.stringify({qml:qml.splice(0),avatarCalls:[...calls],bookmarkCalls:clone(bookmarkCalls),bookmarks:clone(bookmarkRows),scale,scaleCalls:[...scaleCalls],source,callbacks:signals.reduce((n,s)=>n+s.callbacks.size,0),pendingTimers:[...timers.keys()]})+'\n');}
reply();
for(let line;(line=readLine())!==null;){
    const value=JSON.parse(line);assert.deepEqual(Object.keys(value),['messages']);assert(Array.isArray(value.messages));
    for(const message of value.messages)tablet.fromQml.emit(message);
    // Explicit timer actor: run the original queued JS callbacks at this host
    // message boundary. This proves callback routing, not a real 300-ms quiet.
    for(let turn=0;turn<8&&timers.size;++turn){const pending=[...timers];timers.clear();for(const [,callback]of pending)callback();}
    assert.equal(timers.size,0);
    reply();
}
script.scriptEnding.emit();assert.equal(timers.size,0);assert.equal(signals.reduce((n,s)=>n+s.callbacks.size,0),1);
