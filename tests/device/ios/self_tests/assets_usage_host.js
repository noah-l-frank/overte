// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Execute original normal baking/import handlers behind modeled Qt/native APIs.
// Service statuses and entity returns below are explicit models, never oven or
// actual model/rendering evidence.
'use strict';
module.exports=function({vm,crypto,assets,scope,tree,qt,events,section}) {
    let write=true,rez=true,rezTmp=false,visible=false,focused=false,defer=false,bakeError='',entityDenied=false;
    const pending=[];
    scope.Entities.canWriteAssets=()=>write;scope.Entities.canRez=()=>rez;scope.Entities.canRezTmp=()=>rezTmp;
    scope.importAllowed=true;scope.modelUrl={text:''};scope.shape={currentIndex:0};scope.dynamic={checked:false};scope.modelName='';scope.modelPosition=null;
    Object.defineProperty(scope.dynamic,'enabled',{get:()=>vm.runInContext('shape.currentIndex !== 3',scope)});
    scope.modelDialog={open:()=>{visible=true;focused=false;}};
    scope.MyAvatar={position:{x:0,y:1,z:0},orientation:{x:0,y:0,z:0,w:1}};
    scope.Quat={getForward:()=>({x:0,y:0,z:-1})};scope.MenuInterface={isOptionChecked:()=>false};
    scope.Vec3={sum:(a,b)=>({x:a.x+b.x,y:a.y+b.y,z:a.z+b.z}),multiply:(a,b)=>typeof a==='number'?{x:a*b.x,y:a*b.y,z:a*b.z}:{x:a.x*b,y:a.y*b,z:a.z*b},fromPolar:()=>({x:0,y:-1,z:0})};
    function entity(kind,args) {
        const id=entityDenied?'00000000-0000-0000-0000-000000000000':crypto.randomUUID();events.push({kind:'entity-returned',type:kind,args,id});return id;
    }
    scope.Entities.addModelEntity=(...args)=>entity('Model',args);scope.Entities.addImageEntity=(...args)=>entity('Image',args);
    function finish(job) {
        const status=job.enabled?(bakeError?5:4):1;tree.status(job.paths,status,bakeError);
        events.push({kind:'baking-completed',paths:job.paths,enabled:job.enabled,status,error:bakeError});job.callback(bakeError);
    }
    scope.Assets.setBakingEnabled=(paths,enabled,callback)=>{
        const job={paths:[...paths],enabled,callback};events.push({kind:'baking-started',paths:job.paths,enabled});
        if(defer)pending.push(job);else qt.callLater(()=>finish(job));
    };
    vm.runInContext(section(assets,'    function bakingAvailable(', '    property string modelName:'),scope);
    vm.runInContext(section(assets,'    function importModel(', '    function uploadFile('),scope);
    vm.runInContext(section(assets,'    function importUploadedMain(', '    Component.onCompleted:'),scope);
    function line(name) {const value=assets.split('\n').find(value=>value.includes('objectName: "'+name+'"'));if(!value)throw Error('Original usage control changed');return value;}
    function expression(name,property) {
        const match=new RegExp('; '+property+': ([^;]+);').exec(line(name));if(!match)throw Error('Original usage expression changed');return vm.runInContext(match[1],scope);
    }
    function button(name) {
        const match=/onClicked: (.*) \}$/.exec(line(name));if(!match)throw Error('Original usage button changed');vm.runInContext(match[1],scope);
    }
    function checked() {return expression('assetBaking','checked');}
    function snapshot() {
        return {permissions:{canWriteAssets:write,canRez:rez,canRezTmp:rezTmp},importAllowed:scope.importAllowed,uploadedPrimaryUrl:scope.uploadedPrimaryUrl,
            baking:{checked:checked(),enabled:expression('assetBaking','enabled')},importEnabled:expression('assetImport','enabled'),
            uploadedImportVisible:expression('assetUploadedImport','visible'),uploadedImportEnabled:expression('assetUploadedImport','enabled'),
            model:{visible,url:scope.modelUrl.text,shapeIndex:scope.shape.currentIndex,shapeCount:6,dynamicChecked:scope.dynamic.checked,dynamicEnabled:scope.dynamic.enabled,
                name:scope.modelName,position:visible?scope.modelPosition:null}};
    }
    function controls(original) {
        if(visible)return [{id:'assets.model.url',focused},{id:'assets.model.shape'},{id:'assets.model.dynamic',enabled:scope.dynamic.enabled},{id:'assets.model.accept'},{id:'assets.model.cancel'}];
        const state=tree.snapshot();if(state.renameVisible||state.deleteVisible)return original;
        const current=snapshot();return [...original,{id:'assets.baking',enabled:current.baking.enabled},{id:'assets.import',enabled:current.importEnabled},
            ...(current.uploadedImportVisible?[{id:'assets.import-uploaded',enabled:current.uploadedImportEnabled}]:[])];
    }
    function dispatch(command) {
        const id=command.id;
        if(id==='assets.baking') {
            if(!expression('assetBaking','enabled'))return true;scope.checked=!checked();
            const handler=/onToggled: (.*) \}$/.exec(line('assetBaking'));if(!handler)throw Error('Original baking handler changed');vm.runInContext(handler[1],scope);return true;
        }
        if(id==='assets.import'){button('assetImport');return true;}
        if(id==='assets.import-uploaded'){button('assetUploadedImport');return true;}
        if(!id.startsWith('assets.model.'))return false;
        if(!visible)throw Error('No original model dialog');
        if(id==='assets.model.url') {if(command.action==='activate')focused=true;else if(command.action==='replace'&&focused)scope.modelUrl.text=command.text;return true;}
        if(id==='assets.model.dynamic'){if(scope.dynamic.enabled)scope.dynamic.checked=!scope.dynamic.checked;return true;}
        if(id==='assets.model.shape')return true;
        if(id==='assets.model.accept'||id==='assets.model.cancel') {
            const original=assets.slice(assets.indexOf('        id: modelDialog'));
            if(id.endsWith('accept')){const handler=/\n        onAccepted: ([^\n]+)/.exec(original);if(!handler)throw Error('Original model handler changed');vm.runInContext(handler[1],scope);}
            visible=false;focused=false;const closed=/\n        onClosed: ([^\n]+)/.exec(original);if(closed)vm.runInContext(closed[1],scope);return true;
        }
        return false;
    }
    function configure(value) {
        if('canWrite' in value)write=value.canWrite;if('effectiveWrite' in value)write=value.effectiveWrite;
        if('canRez' in value)rez=value.canRez;if('canRezTmp' in value)rezTmp=value.canRezTmp;
        if('canRez' in value||'canRezTmp' in value)scope.importAllowed=rez||rezTmp;if('uiImportAllowed' in value)scope.importAllowed=value.uiImportAllowed;
        if('modelUrl' in value)scope.modelUrl.text=value.modelUrl;if('shapeIndex' in value){scope.shape.currentIndex=value.shapeIndex;if(!scope.dynamic.enabled)scope.dynamic.checked=false;}
        if('uploadedPrimaryUrl' in value)scope.uploadedPrimaryUrl=value.uploadedPrimaryUrl;
        if('entityDenied' in value)entityDenied=value.entityDenied;if('deferBaking' in value)defer=value.deferBaking;if('bakeError' in value)bakeError=value.bakeError;
        if(value.completeBaking)while(pending.length){const job=pending.shift();qt.callLater(()=>finish(job));}
    }
    return {snapshot,controls,dispatch,configure};
};
