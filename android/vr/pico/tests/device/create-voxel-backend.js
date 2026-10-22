// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Explicit host actors for original NativeCreate/Bridge/EditTools/EditVoxels.
// This is not a V8, domain, hardware, renderer, OpenXR or native timer source.
var module={exports:{}}, outputs=[],savedStrokes=[],cuboidCalls=[],intervals={},nextTimer=0;
var permission=true,entityID='88888888-8888-8888-8888-888888888888',volume=[];
for(var z=0;z<8;z++)for(var y=0;y<8;y++)for(var x=0;x<8;x++)volume.push(x>=2&&x<6&&y>=2&&y<6&&z>=2&&z<6?255:0);
function copy(value){return JSON.parse(JSON.stringify(value));}
function signal(){return {callbacks:[],connect:function(fn){this.callbacks.push(fn);},disconnect:function(fn){this.callbacks=this.callbacks.filter(function(f){return f!==fn;});},addListener:function(fn){this.connect(fn);},removeListener:function(fn){this.disconnect(fn);}};}
var mappings={};
var Controller={Standard:{RTClick:'rtclick',LTClick:'ltclick',RT:'rt',LT:'lt',LeftGrip:'left-grip',RightGrip:'right-grip',LeftHand:0,RightHand:1},
    newMapping:function(){return {channel:null,from:function(c){this.channel=c;return this;},peek:function(){return this;},to:function(fn){mappings[this.channel]=fn;return this;},enable:function(){},disable:function(){}};},
    getValue:function(){return 0;},mousePressEvent:signal(),mouseReleaseEvent:signal(),keyPressEvent:signal(),keyReleaseEvent:signal()};
var Script={include:function(){},resolvePath:function(){return 'file:///original/system/create/editModes/editVoxels.js';},resourcesPath:function(){return '';},update:signal(),scriptEnding:signal(),
    setInterval:function(fn,ms){if(ms!==100)throw Error('unexpected original timer');intervals[++nextTimer]=fn;return nextTimer;},clearInterval:function(id){delete intervals[id];}};
var SoundCache={getSound:function(url){return url;}},Audio={playSystemSound:function(){}},TRIGGER_ON_VALUE=.15;
var MyAvatar={sessionUUID:'22222222-2222-2222-2222-222222222222',SELF_ID:'self',orientation:{x:0,y:0,z:0,w:1}};
var Vec3={subtract:function(a,b){return {x:a.x-b.x,y:a.y-b.y,z:a.z-b.z};},sum:function(a,b){return {x:a.x+b.x,y:a.y+b.y,z:a.z+b.z};},
    multiply:function(a,b){if(typeof a==='number'){var c=b;b=a;a=c;}return {x:a.x*b,y:a.y*b,z:a.z*b};},normalize:function(a){var n=Math.sqrt(a.x*a.x+a.y*a.y+a.z*a.z);return {x:a.x/n,y:a.y/n,z:a.z/n};}};
var Quat={getUp:function(){return {x:0,y:0,z:-1};}};
function getControllerWorldLocation(){return {valid:true,translation:{x:0,y:1,z:0},rotation:{x:0,y:0,z:0,w:1}};}
var Picks={PICK_DOMAIN_ENTITIES:1,PICK_AVATAR_ENTITIES:2,PICK_LOCAL_ENTITIES:4};
var Entities={canRez:function(){return permission;},canRezTmp:function(){return false;},canRezAvatarEntities:function(){return false;},canAdjustLocks:function(){return false;},isVoxelDataReady:function(){return true;},
    getEntityProperties:function(id){if(id!==entityID)throw Error('foreign original');return {type:'PolyVox',entityHostType:'domain',locked:false,voxelData:JSON.stringify(volume)};},
    worldCoordsToVoxelCoords:function(id,p){if(id!==entityID)throw Error('foreign conversion');return {x:(p.x+.5)*8,y:(p.y-.5)*8,z:(p.z+2.5)*8};},
    findRayIntersection:function(ray,mask){if(mask!==7 || ray.direction.z!==-1)throw Error('unexpected ray');return {intersects:true,entityID:entityID,intersection:{x:0,y:1,z:-1.75}};},
    setVoxelsInCuboid:function(id,low,size,value){if(id!==entityID)throw Error('foreign mutation');cuboidCalls.push(copy({id:id,low:low,size:size,value:value}));var changed=false;
        for(var z=0;z<8;z++)for(var y=0;y<8;y++)for(var x=0;x<8;x++)if(x>=low.x&&x<low.x+size.x&&y>=low.y&&y<low.y+size.y&&z>=low.z&&z<low.z+size.z){var i=z*64+y*8+x;changed=changed||volume[i]!==value;volume[i]=value;}return changed;}};
var tablet={webEventReceived:signal(),emitScriptEvent:function(){}},windowActor={webEventReceived:signal(),emitScriptEvent:function(){}};
var Tablet={getTablet:function(){return tablet;}};
var SelectionManager={selections:[entityID],createApp:{pushVoxelStroke:function(edits){savedStrokes.push(copy(edits));}},pointingAtTabletLeft:false,pointingAtTabletRight:false,
    pointingAtDesktopWindowLeft:false,pointingAtDesktopWindowRight:false};
function initializeOriginalTools(){
    var tools=EditTools({createToolsWindow:windowActor}),voxels=EditVoxels();tools.addListener(voxels.updateEditSettings);
    var bridge=module.exports.createBridge({isActive:function(){return true;},entities:Entities,avatar:MyAvatar,selection:SelectionManager,
        history:{canUndo:function(){return savedStrokes.length>0;},canRedo:function(){return false;}},numericFocus:function(){},
        applyEditSettings:tools.applyNativeSettings,editSettings:tools.getSettings,send:function(message){outputs.push(copy(message));}});
    tools.onNativeUpdate=bridge.sendSettings;
    voxels.onStrokeStatus=bridge.reportStatus;voxels.onStrokeSettled=bridge.selection;
    return {handle:bridge.handle,settings:tools.getSettings,stroke:function(){mappings.rtclick(true);mappings.rtclick(false);
        Object.keys(intervals).forEach(function(id){intervals[id]();});return copy({calls:cuboidCalls,strokes:savedStrokes,volume:volume,remainingTimers:Object.keys(intervals)});}};
}
