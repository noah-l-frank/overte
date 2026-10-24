// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// SDK/Tablet/grid/selection endpoints around the unchanged original Add code.
// No entity, volume, request, decoder or retirement result is supplied here.
var isActive=true,nativeCreate=null,nativeCreateEnabled=false,nativeMobileHost=false;
var HMD={active:true},buttonHandlers={},dialogWindow=null,dialogStack=[],dialogEvents=[];
var DEFAULT_DIMENSIONS={x:.2,y:.2,z:.2},DEFAULT_LIGHT_DIMENSIONS={x:4,y:4,z:4},DEFAULT_IMAGE='',DEFAULT_PARTICLE='';
var Camera={mode:'first person'},grid={snapToSurface:function(p){return p;},snapToGrid:function(p){return p;}};
var Menu={isOptionChecked:function(){return false;}},MENU_CREATE_ENTITIES_GRABBABLE='';
var Settings={getValue:function(){return false;}},INSUFFICIENT_PERMISSIONS_ERROR_MSG='Denied';
var Messages={sendLocalMessage:function(){throw Error('Unexpected tablet movement endpoint');}};
MyAvatar.position={x:0,y:1,z:0};Vec3.UNIT_Z={x:0,y:0,z:1};
Vec3.multiplyQbyV=function(q,v){if(q.x!==0||q.y!==0||q.z!==0||q.w!==1)throw Error('Foreign avatar orientation');return copy(v);};
createApp.getPositionToCreateEntity=function(){return {x:0,y:1,z:-2};};
tablet.toolbarMode=false;
tablet.pushOntoStack=function(url){if(dialogStack.length)throw Error('Nested host dialog');dialogStack.push(url);dialogEvents.push({event:'push',url:url});};
tablet.popFromStack=function(){if(dialogStack.length!==1)throw Error('No original dialog to pop');dialogEvents.push({event:'pop',url:dialogStack.pop()});};
Script.resolvePath=function(value){return 'file://'+originalCreateScriptDirectory+'/'+value;};
Script.setTimeout=function(){throw Error('PolyVox Add must not create a Model loading timer');};
SelectionManager.selections=[];
SelectionManager.setSelections=function(ids){this.selections=ids.slice();};
SelectionManager.addEntity=function(id){if(id!==entityID)throw Error('Foreign normal selection');};
SelectionManager._update=function(){};
entityListTool.sendUpdate=function(){};
Window.setFocus=function(){};
function adjustPositionPerBoundingBox(){throw Error('No alternate shape positioning is admitted');}
function print(){throw Error('The original Add message was malformed');}
var addCuboids=[];
Entities.addEntity=function(properties,host){entityID=nativeVoxel.add(properties,host);return entityID;};
Entities.editEntity=function(id,properties){return nativeVoxel.edit(id,properties);};
Entities.setVoxelsInCuboid=function(id,low,size,value){
    (value===255?addCuboids:cuboidCalls).push(copy({id:id,low:low,size:size,value:value}));
    return nativeVoxel.setCuboid(id,low,size,value);
};
