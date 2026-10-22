// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original bridge and original createNewEntity body. Entity/network/selection,
// clock and native Script timeout dispatch are declared substituted boundaries.
'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),vm=require('vm');
const root=path.resolve(__dirname,'../../../../..');
const edit=fs.readFileSync(path.join(root,'scripts/system/create/edit.js'),'utf8');
const defaults=edit.slice(edit.indexOf('    function copyProperties(a, b) {'),edit.indexOf('    var fcreateNewEntity;'));
const create=edit.slice(edit.indexOf('        function createNewEntity('),edit.indexOf('        fcreateNewEntity = createNewEntity;'));
assert(create.startsWith('        function createNewEntity(') && create.trim().endsWith('}'));
const {createBridge}=require(path.join(root,'scripts/system/create/modules/nativeCreateBridge.js'));
function scenario(loadedAt,deny=false) {
    let time=0,next=0,registrations=0,invocations=0,canRez=!deny,rows=new Map(),edits=[],events=[],pending=new Map();
    const entity='33333333-3333-3333-3333-333333333333';
    const dimensions={x:2,y:1,z:.2},position={x:0,y:1,z:-2};
    const clone=v=>JSON.parse(JSON.stringify(v));
    const selection={selections:[],setSelections:ids=>{selection.selections=ids.slice();},_update:()=>{},addEntity:()=>{},saveProperties:()=>{}};
    const entities={canRez:()=>canRez,canRezTmp:()=>false,canRezAvatarEntities:()=>false,canAdjustLocks:()=>false,
        addEntity:(properties,host)=>{assert.equal(host,'domain');assert(!rows.size);rows.set(entity,clone({...properties,id:entity,entityHostType:'domain',dimensions:{x:.2,y:.2,z:.2}}));return entity;},
        isLoaded:id=>{assert.equal(id,entity);return time>=loadedAt;},
        getEntityProperties:(id,fields)=>{assert(rows.has(id));return clone({...rows.get(id),naturalDimensions:dimensions,registrationPoint:{x:.5,y:.5,z:.5}});},
        editEntity:(id,properties)=>{assert(rows.has(id));edits.push({time,properties:clone(properties)});Object.assign(rows.get(id),clone(properties));}};
    const sandbox={console,DEFAULT_DIMENSIONS:{x:.2,y:.2,z:.2},DEFAULT_LIGHT_DIMENSIONS:{x:4,y:4,z:4},DEFAULT_IMAGE:'',DEFAULT_PARTICLE:'',
        Entities:entities,Camera:{mode:'first person'},MyAvatar:{orientation:{x:0,y:0,z:0,w:1}},
        Vec3:{UNIT_Z:{x:0,y:0,z:1},multiplyQbyV:(q,v)=>v,equal:(a,b)=>JSON.stringify(a)===JSON.stringify(b)},
        createApp:{getPositionToCreateEntity:()=>clone(position),pushCommandForSelections:()=>{}},
        grid:{snapToSurface:p=>p,snapToGrid:p=>p},Menu:{isOptionChecked:()=>false},MENU_CREATE_ENTITIES_GRABBABLE:'',
        Settings:{getValue:()=>false},Messages:{sendLocalMessage:()=>{throw Error('unexpected tablet move');}},
        Script:{setTimeout:(callback,interval)=>{assert.equal(typeof callback,'function');registrations++;pending.set(++next,{callback,due:time+interval});return next;}},
        SelectionManager:selection,selectionManager:selection,entityListTool:{sendUpdate:()=>{}},
        Window:{setFocus:()=>{},notifyEditError:m=>events.push(m)},INSUFFICIENT_PERMISSIONS_ERROR_MSG:'denied',
        adjustPositionPerBoundingBox:p=>p};
    vm.createContext(sandbox);vm.runInContext(defaults+'\n'+create,sandbox,{timeout:1000});
    const bridge=createBridge({isActive:()=>true,entities,selection,avatar:{sessionUUID:'actor',SELF_ID:'self'},
        create:(props,host)=>sandbox.createNewEntity(props,host),send:m=>events.push(clone(m)),euler:q=>q,
        history:{canUndo:()=>false,canRedo:()=>false}});
    const url='http://controlled.test/feature-fixture/v1/runs/'+'a'.repeat(32)+'/tickets/'+'b'.repeat(32)+'/gltf-bundle/main.gltf';
    bridge.handle({method:'nativeCreate.create',params:{host:'domain',properties:{type:'Model',modelURL:url}}});
    if (deny) {assert.equal(rows.size,0);assert.equal(pending.size,0);assert(events.some(m=>m.params&&m.params.error));return;}
    assert.equal(rows.get(entity).visible,false);assert.equal(rows.get(entity).modelURL,url);assert.deepEqual(selection.selections,[entity]);
    assert.equal(pending.size,1);assert.equal(registrations,1);
    const tick=()=>{const [handle,job]=Array.from(pending).sort((a,b)=>a[1].due-b[1].due||a[0]-b[0])[0];pending.delete(handle);time=job.due;invocations++;job.callback();};
    while (time<loadedAt && time<10000) {tick();if (time<loadedAt && time<10000) assert.equal(rows.get(entity).visible,false);}
    assert.equal(rows.get(entity).visible,true);assert.deepEqual(rows.get(entity).dimensions,dimensions);
    assert.equal(pending.size,1); // The genuine second dimension adjustment chain still owns work.
    while (pending.size) {assert(invocations<120);tick();}
    assert.equal(registrations,invocations);assert.equal(time,Math.min(loadedAt,10000)+2000);
    assert.equal(edits.length,1); // Stable natural dimensions cause no invented later position update.
    const original=clone(rows.get(entity));time+=3000;assert.deepEqual(rows.get(entity),original);assert.equal(pending.size,0);
    return {time,registrations,invocations};
}
const loaded=scenario(600);assert.equal(loaded.registrations,16);
const timeout=scenario(20000);assert.equal(timeout.registrations,110); // Product sets visible even on timeout; actual isLoaded remains false.
scenario(600,true);
console.log('PASS original nativeCreateBridge -> original edit.js Model create/selection/load and dimension timers; timeout and denied host; substituted native actor/clock, no V8 or device claim');
