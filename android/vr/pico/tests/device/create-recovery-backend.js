// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Explicit host permission/storage/math/runtime actors around whole original
// fromQml/nativeCreateBridge/createNewEntity/deleteSelectedEntities bodies.
var module={exports:{}},outputs=[],permission=false,created=[],deleted=[],rows={},timerCalls=0;
function copy(value){return JSON.parse(JSON.stringify(value));}
var isActive=true,nativeCreate=null,nativeCreateEnabled=false,buttonHandlers={},dialogWindow=null;
var DEFAULT_DIMENSIONS={x:.2,y:.2,z:.2},DEFAULT_LIGHT_DIMENSIONS={x:4,y:4,z:4},DEFAULT_IMAGE='',DEFAULT_PARTICLE='';
var Camera={mode:'first person'},MyAvatar={position:{x:0,y:1,z:0},orientation:{x:0,y:0,z:0,w:1},sessionUUID:'22222222-2222-2222-2222-222222222222',SELF_ID:'self'};
var Vec3={UNIT_Z:{x:0,y:0,z:1},multiplyQbyV:function(q,v){return copy(v);},sum:function(a,b){return {x:a.x+b.x,y:a.y+b.y,z:a.z+b.z};}};
var Quat={multiply:function(a,b){return copy(b);}},Uuid={NONE:'00000000-0000-0000-0000-000000000000'};
var Settings={getValue:function(){return false;}},Messages={sendLocalMessage:function(){throw Error('unexpected tablet setting');}};
var Menu={isOptionChecked:function(){return false;}},MENU_CREATE_ENTITIES_GRABBABLE='';
var Script={setTimeout:function(){timerCalls++;throw Error('Shape must not schedule Model load timers');}};
var Window={setFocus:function(){},notifyEditError:function(message){throw Error('unexpected editor rejection: '+message);}};
var INSUFFICIENT_PERMISSIONS_ERROR_MSG='insufficient',audioFeedback={rejection:function(){throw Error('unexpected deletion rejection');}};
var Entities={canRez:function(){return permission;},canRezTmp:function(){return false;},canRezAvatarEntities:function(){return false;},canAdjustLocks:function(){return true;},
    addEntity:function(properties,host){if(!permission)throw Error('unexpected denied storage write');var id='33333333-3333-3333-3333-333333333333';
        if(Object.keys(rows).length)throw Error('unexpected duplicate creation');created.push(copy({properties:properties,host:host}));
        rows[id]=copy(properties);rows[id].entityHostType=host;rows[id].locked=false;rows[id].name='Shape';return id;},
    getEntityProperties:function(id){if(!rows[id])throw Error('foreign entity read');return copy(rows[id]);},
    getMultipleEntityProperties:function(ids){return ids.map(function(id){return Entities.getEntityProperties(id);});},
    getChildrenIDs:function(){return [];},isChildOfParent:function(){return false;},
    deleteEntity:function(id){if(!rows[id])throw Error('foreign deletion');deleted.push(id);delete rows[id];}};
var SelectionManager={selections:[],savedProperties:{},addEntity:function(){},saveProperties:function(){
        this.savedProperties={};this.selections.forEach(function(id){SelectionManager.savedProperties[id]=Entities.getEntityProperties(id);});},
    setSelections:function(ids){this.selections=ids.slice();},clearSelections:function(){this.selections=[];},
    hasSelection:function(){return this.selections.length>0;},hasUnlockedSelection:function(){return this.selections.every(function(id){return !rows[id].locked;});}};
var selectionManager=SelectionManager;
var createApp={getPositionToCreateEntity:function(){return {x:0,y:1,z:-2};},pushCommandForSelections:function(){}};
var grid={snapToGrid:function(p){return p;},snapToSurface:function(p){return p;}};
function adjustPositionPerBoundingBox(p){return p;}
var entityListTool={sendUpdate:function(){if(nativeCreate)nativeCreate.acceptList({type:'update',entities:Object.keys(rows).map(function(id){return {id:id,name:rows[id].name,type:rows[id].type};})});},deleteEntities:function(){}};
var tablet={sendToQml:function(message){outputs.push(copy(message));}},Tablet={getTablet:function(){return tablet;}};
function print(){throw Error('unexpected malformed original QML message');}
function initializeOriginalRecovery(){
    nativeCreate=originalNativeBridge.createBridge({entities:Entities,avatar:MyAvatar,selection:selectionManager,app:createApp,
        history:{canUndo:function(){return created.length>0;},canRedo:function(){return false;}},isActive:function(){return isActive&&nativeCreateEnabled;},
        send:tablet.sendToQml,euler:function(q){return q;},propertyView:copy,refresh:entityListTool.sendUpdate,
        create:createNewEntity,numericFocus:function(){}});
    return {handle:fromQml};
}
function recoveryState(){return copy({creates:created,deletes:deleted,rows:Object.keys(rows).map(function(id){return rows[id];}),timers:timerCalls});}
