// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Whole original avatarapp.js, Pico path (no Phone global). Tablet/context,
// MyAvatar/native calls and timers are explicit host actors, never loaded models.
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),readline=require('node:readline'),assert=require('node:assert/strict');
const root=process.argv[2];assert(root);
class Signal {
    constructor(){this.callbacks=new Set();}
    connect(callback){assert.equal(typeof callback,'function');this.callbacks.add(callback);}
    disconnect(callback){assert(this.callbacks.delete(callback));}
    emit(...args){for(const callback of [...this.callbacks])callback(...args);}
}
const signals=[];function signal(){const value=new Signal();signals.push(value);return value;}
const button={clicked:signal(),editProperties(value){assert.equal(typeof value.isActive,'boolean');}};
let qml=[],calls=[],source='',timerId=0;const timers=new Map();
const tablet={fromQml:signal(),screenChanged:signal(),
    addButton(value){assert.equal(value.text,'AVATAR');return button;},removeButton(value){assert.equal(value,button);},
    loadQMLSource(value){assert.equal(value,'hifi/AvatarApp.qml');source=value;this.screenChanged.emit('QML',value);},
    gotoHomeScreen(){this.screenChanged.emit('Home','');},sendToQml(value){qml.push(JSON.parse(JSON.stringify(value)));}};
const avatar={displayName:'owned host',sessionUUID:'77777777-7777-4777-8777-777777777777',skeletonModelURL:'qrc:/meshes/defaultAvatar_full.fst',
    collisionSoundURL:'',getAvatarEntitiesVariant(){return [];},getJointNames(){return ['Hips'];},getAvatarScale(){return 1;},
    getDominantHand(){return 'right';},getHmdAvatarAlignmentType(){return 'head';},getCollisionsEnabled(){return true;},getOtherAvatarsCollisionsEnabled(){return true;},
    getAnimGraphUrl(){return '';},getAnimGraphOverrideUrl(){return '';},getFullAvatarURLFromPreferences(){return this.skeletonModelURL;},
    useFullAvatarURL(value){calls.push(value);this.skeletonModelURL=value;this.skeletonModelURLChanged.emit();}};
for(const name of ['skeletonModelURLChanged','dominantHandChanged','hmdAvatarAlignmentTypeChanged','collisionsEnabledChanged','otherAvatarsCollisionsEnabledChanged','newCollisionSoundURL','animGraphUrlChanged','targetScaleChanged'])avatar[name]=signal();
const bookmarks={getBookmarks(){return {};}};for(const name of ['bookmarkLoaded','bookmarkDeleted','bookmarkAdded'])bookmarks[name]=signal();
const entities={addingWearable:signal(),deletingWearable:signal(),mousePressOnEntity:signal()};
const script={resolvePath(value){assert.equal(value,'html/js/marketplacesInject.js');return require('node:url').pathToFileURL(root+'/scripts/system/'+value).href;},include(value){assert.equal(value,'/~/system/libraries/controllers.js');},scriptEnding:signal(),
    setTimeout(callback,ms){assert.equal(typeof callback,'function');assert.equal(ms,300);timers.set(++timerId,callback);return timerId;},
    clearTimeout(id){assert(timers.delete(id));},setInterval(){throw Error('Unexpected wearable interval in URL-only scope');},clearInterval(){throw Error('Unexpected interval cleanup');}};
const context=vm.createContext({Script:script,Tablet:{getTablet(value){assert.equal(value,'com.highfidelity.interface.tablet.system');return tablet;}},
    MyAvatar:avatar,AvatarBookmarks:bookmarks,Entities:entities,HMD:{active:true},Camera:{mode:'first person'},Quat:{},
    AddressManager:{isConnected:true},Account:{},UserActivityLogger:{},Messages:{messageReceived:signal()},print(){},console:{debug(){},log(){},warn(){}}});
vm.runInContext(fs.readFileSync(root+'/scripts/system/avatarapp.js','utf8'),context,{filename:'original-avatarapp.js',timeout:2000});
button.clicked.emit();
function reply(){process.stdout.write(JSON.stringify({qml:qml.splice(0),avatarCalls:[...calls],source,callbacks:signals.reduce((n,s)=>n+s.callbacks.size,0),pendingTimers:[...timers.keys()]})+'\n');}
reply();
readline.createInterface({input:process.stdin}).on('line',line=>{
    const value=JSON.parse(line);assert.deepEqual(Object.keys(value),['messages']);assert(Array.isArray(value.messages));
    for(const message of value.messages)tablet.fromQml.emit(message);
    reply();
}).on('close',()=>{script.scriptEnding.emit();assert.equal(timers.size,0);assert.equal(signals.reduce((n,s)=>n+s.callbacks.size,0),1);});
