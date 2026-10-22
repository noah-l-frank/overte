// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual Qt callback -> original validation/fromQml/dialog/createNewEntity.
// Tablet, entity storage, avatar math and native execution remain actor seams.
'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),vm=require('vm');
const root=path.resolve(__dirname,'../../../../..');
const edit=fs.readFileSync(path.join(root,'scripts/system/create/edit.js'),'utf8');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
function original(signature){const start=edit.indexOf(signature);assert(start>=0);let end=edit.indexOf('{',start)+1,depth=1;
    while(depth){depth+=(edit[end]==='{')-(edit[end]==='}');end++;}return edit.slice(start,end);}
const defaults=edit.slice(edit.indexOf('    function copyProperties(a, b) {'),edit.indexOf('    var fcreateNewEntity;'));
const create=edit.slice(edit.indexOf('        function createNewEntity('),edit.indexOf('        fcreateNewEntity = createNewEntity;'));
for(const denied of [false,true]){
    const rows=new Map(),volume=new Uint8Array(512),events=[],stack=[];let next=0;
    const clone=value=>JSON.parse(JSON.stringify(value));
    const tablet={toolbarMode:false,pushOntoStack:url=>{stack.push(url);events.push('push');},
        popFromStack:()=>{assert.equal(stack.length,1);stack.pop();events.push('pop');}};
    const selection={selections:[],setSelections:ids=>{selection.selections=ids.slice();},_update:()=>{},addEntity:()=>{},saveProperties:()=>{}};
    const entities={canRez:()=>!denied,canRezTmp:()=>false,canRezAvatarEntities:()=>false,
        addEntity:(properties,host)=>{assert.equal(host,'domain');assert.equal(properties.type,'PolyVox');assert(!rows.size);
            const id='33333333-3333-3333-3333-'+String(++next).padStart(12,'0');rows.set(id,clone(properties));events.push('create');return id;},
        getEntityProperties:id=>{assert(rows.has(id));return clone(rows.get(id));},
        editEntity:(id,properties)=>{assert(rows.has(id));Object.assign(rows.get(id),clone(properties));events.push('edit');},
        setVoxelsInCuboid:(id,low,size,value)=>{assert(rows.has(id));assert.deepEqual(clone(low),{x:2,y:2,z:2});assert.deepEqual(clone(size),{x:4,y:4,z:4});assert.equal(value,255);
            for(let z=low.z;z<low.z+size.z;z++)for(let y=low.y;y<low.y+size.y;y++)for(let x=low.x;x<low.x+size.x;x++)volume[z*64+y*8+x]=value;
            events.push('volume');},setVoxel:()=>{throw Error('unexpected alternate shape');}};
    const sandbox={console,isActive:true,nativeCreate:null,nativeCreateEnabled:false,HMD:{active:true},nativeMobileHost:false,
        Tablet:{getTablet:name=>{assert.equal(name,'com.highfidelity.interface.tablet.system');return tablet;}},buttonHandlers:{},dialogWindow:null,
        validatePicoQmlMessage:require(path.join(root,'scripts/system/create/modules/picoQmlMessageValidation.js')),
        DEFAULT_DIMENSIONS:{x:.2,y:.2,z:.2},DEFAULT_LIGHT_DIMENSIONS:{x:4,y:4,z:4},DEFAULT_IMAGE:'',DEFAULT_PARTICLE:'',
        Entities:entities,Camera:{mode:'first person'},MyAvatar:{position:{x:0,y:1,z:0},orientation:{x:0,y:0,z:0,w:1}},
        Vec3:{UNIT_Z:{x:0,y:0,z:1},multiplyQbyV:(q,v)=>clone(v),sum:(a,b)=>({x:a.x+b.x,y:a.y+b.y,z:a.z+b.z})},
        createApp:{getPositionToCreateEntity:()=>({x:0,y:1,z:-2}),pushCommandForSelections:()=>{}},
        grid:{snapToSurface:p=>p,snapToGrid:p=>p},Menu:{isOptionChecked:()=>false},MENU_CREATE_ENTITIES_GRABBABLE:'',
        Settings:{getValue:()=>false},Messages:{sendLocalMessage:()=>{throw Error('unexpected tablet setting');}},
        Script:{setTimeout:()=>{throw Error('PolyVox must not invent a Model load timer');},resolvePath:value=>'file:///original/system/create/'+value},
        SelectionManager:selection,selectionManager:selection,entityListTool:{sendUpdate:()=>{}},
        Window:{setFocus:()=>{},notifyEditError:()=>events.push('denied')},INSUFFICIENT_PERMISSIONS_ERROR_MSG:'denied',
        adjustPositionPerBoundingBox:p=>p,print:()=>{throw Error('unexpected malformed callback');}};
    vm.createContext(sandbox);
    vm.runInContext(defaults+'\n'+create+'\n'+
        'var shouldUseEditTabletApp='+original('function() {\n        return HMD.active')+';\n'+
        ['function createNewEntityDialogButtonCallback(','function handleNewPolyVoxDialogResult(',
         'function closeExistingDialogWindow(','function fromQml('].map(original).join('\n')+
        '\nbuttonHandlers.newPolyVoxButton=createNewEntityDialogButtonCallback("PolyVox");',sandbox,{timeout:1000});
    sandbox.fromQml(input.detail);assert.deepEqual(events,['push']);assert(stack[0].endsWith('/qml/NewPolyVoxDialog.qml'));
    sandbox.fromQml(input.polyvox);assert.equal(stack.length,0);assert.equal(events[1],'pop');
    const count=rows.size;sandbox.fromQml(input.detail);assert.equal(stack.length,1);sandbox.fromQml(input.cancel);
    assert.equal(stack.length,0);assert.equal(rows.size,count);
    if(denied){assert.equal(rows.size,0);assert.deepEqual(events,['push','pop','denied','push','pop']);continue;}
    assert.equal(rows.size,1);const actual=rows.values().next().value;
    assert.deepEqual(actual.voxelVolumeSize,{x:8,y:8,z:8});assert.deepEqual(actual.dimensions,{x:8,y:8,z:8});
    assert.deepEqual(actual.position,{x:0,y:1,z:-12.8});assert.equal(actual.name,'terrain');
    assert.equal(actual.voxelSurfaceStyle,3);assert.equal(selection.selections.length,1);
    assert.equal(volume.filter(v=>v!==0).length,64);
    for(let z=0;z<8;z++)for(let y=0;y<8;y++)for(let x=0;x<8;x++)assert.equal(volume[z*64+y*8+x],x>=2&&x<6&&y>=2&&y<6&&z>=2&&z<6?255:0);
}
console.log('PASS actual Qt callbacks through original fromQml/Tablet push/pop/PolyVox/createNewEntity and 64 original cuboid values; denied no entity; native actor boundaries explicit');
