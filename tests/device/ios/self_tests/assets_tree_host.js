// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original NativeModelTree/AssetServer QML JS. Model, mouse/focus, service and
// Qt dialog boundaries below are explicit host models, never native evidence.
'use strict';
module.exports=function({vm,fs,assets,treeSource,scope,qt,events,section}) {
    const original=fs.readFileSync(treeSource,'utf8'),data=new Map(),pending=[];
    let nodes=[],canWrite=true,renameVisible=false,deleteVisible=false,renameFocused=false,defer=false,mutationError='';
    const labels=['--','Not Baked','Pending','Baking','Baked','Error'];
    const model={rowCount:parent=>(parent?parent.children:nodes).length,hasChildren:index=>!!index&&index.children.length>0,
        index:(row,column,parent)=>row<0||column!==0?null:(parent?parent.children:nodes)[row]||null,
        data:(index,role)=>!index?undefined:role===0?index.name:role===256?index.path:role===257?index.folder:
            role===259?'atp:'+index.fullPath:role===260?index.fullPath:role===261?index.status:role===262?index.errors:undefined};
    const tree={sourceModel:model,filterText:'',multiSelect:false,pathRole:256,folderRole:257,statusRole:261,expanded:{},selectedKeys:[],rows:[],
        currentRow:-1,revision:0,previousCurrentKey:'',selectionChanged:()=>{},view:{forceActiveFocus:()=>{renameFocused=false;}}};
    Object.defineProperties(tree,{currentIndex:{get:()=>tree.currentRow>=0&&tree.currentRow<tree.rows.length?tree.rows[tree.currentRow].index:null},
        selectedIndexes:{get:()=>tree.rows.filter(row=>tree.selectedKeys.includes(row.key)).map(row=>row.index)}});
    tree.root=tree;vm.createContext(tree);vm.runInContext(section(original,'    function invalidateRows(', '    onSourceModelChanged:'),tree);
    function refresh() {
        tree.invalidateRows();nodes=[];const lookup=new Map();
        for(const [path,item] of [...data].sort((a,b)=>a[0].localeCompare(b[0]))) {
            if(path.startsWith('/.baked/'))continue;
            let parent=null,full='';const parts=path.slice(1).split('/');
            for(let i=0;i<parts.length;i++) {
                full+='/'+parts[i];let node=lookup.get(full);
                if(!node){const folder=i<parts.length-1;node={name:parts[i],path:full+(folder?'/':''),fullPath:full,folder,
                    status:folder?'--':labels[item.status||0],errors:item.errors||'',children:[],parent};lookup.set(full,node);(parent?parent.children:nodes).push(node);}
                parent=node;
            }
        }
        tree.rebuild();
    }
    function lineage(index) {const result=[];for(let node=index;node;node=node.parent)result.unshift((node.parent?node.parent.children:nodes).indexOf(node));return result;}
    function modelRow(index) {return {modelIndex:lineage(index),name:index.name,path:index.path,folder:index.folder,url:'atp:'+index.fullPath,
        fullPath:index.fullPath,status:index.status,bakingErrors:index.errors};}
    function allRows() {const result=[];function visit(items){for(const node of items){result.push(modelRow(node));visit(node.children);}}visit(nodes);return result;}
    function snapshot() {return {treeRevision:tree.revision,filterText:tree.filterText,selectedPaths:tree.selectedIndexes.map(node=>node.path),
        currentPath:tree.currentIndex?tree.currentIndex.path:'',currentUrl:tree.currentIndex?'atp:'+tree.currentIndex.fullPath:'',
        modelRows:allRows(),rows:tree.rows.map((row,index)=>({index,model:modelRow(row.index),depth:row.depth,selected:tree.selectedKeys.includes(row.key),expanded:row.folder&&!!tree.expanded[row.key]})),
        renameVisible,renameText:scope.renamePath.text,deleteVisible,canWrite,busy:scope.busy};}
    function finish(job) {
        const changes=[];let error=mutationError;
        if(!error) {
            const matching=[...data.keys()].filter(path=>job.kind==='rename'?(path===job.old||job.old.endsWith('/')&&path.startsWith(job.old)):
                job.paths.some(root=>path===root||root.endsWith('/')&&path.startsWith(root)));
            const renamed=path=>job.destination+(job.old.endsWith('/')?path.slice(job.old.length):'');
            if(job.kind==='rename'&&matching.some(path=>data.has(renamed(path))))error='Destination conflict';
            if(!error)for(const path of matching){const value=data.get(path);data.delete(path);const destination=job.kind==='rename'?job.destination+(job.old.endsWith('/')?path.slice(job.old.length):''):null;
                if(destination)data.set(destination,value);changes.push({from:path,to:destination,base64:value.base64});}
        }
        events.push({kind:'mapping-completed',operation:job.kind,error,changes});job.callback(error);events.push({kind:'mapping-callback-returned',operation:job.kind});
    }
    function issue(job) {events.push({kind:'mapping-started',operation:job.kind,old:job.old||'',destination:job.destination||'',paths:job.paths||[]});
        if(defer)pending.push(job);else qt.callLater(()=>finish(job));}
    scope.tree=tree;scope.assetProxyModel=model;scope.assetMappingsModel.refresh=refresh;
    scope.renamePath={text:''};scope.renameDialog={open:()=>{renameVisible=true;renameFocused=false;}};scope.deleteDialog={open:()=>{deleteVisible=true;}};
    scope.Entities={canWriteAssets:()=>canWrite};scope.assetWriteAllowed=canWrite;
    scope.Assets.isKnownFolder=path=>[...data.keys()].some(name=>name.startsWith(path));scope.Assets.isKnownMapping=path=>data.has(path);
    scope.Assets.renameMapping=(old,destination,callback)=>issue({kind:'rename',old,destination,callback});
    scope.Assets.deleteMappings=(paths,callback)=>issue({kind:'delete',paths,callback});
    vm.runInContext(section(assets,'    function writable(', '    property string pendingRenameOld:'),scope);
    Object.defineProperties(scope,{selectedPath:{configurable:true,get:()=>tree.currentIndex?tree.currentIndex.path:''},
        selectedUrl:{configurable:true,get:()=>tree.currentIndex?'atp:'+tree.currentIndex.fullPath:''},
        selectedItemCount:{get:()=>tree.selectedIndexes.length},currentIndex:{get:()=>tree.currentIndex}});
    function button(name) {
        const line=assets.split('\n').find(line=>line.includes('objectName: "'+name+'"'));
        const handler=line&&/onClicked: (.*) \}$/.exec(line);if(!handler)throw Error('Original Assets button changed: '+name);
        vm.runInContext(handler[1],scope);
    }
    function dialog(kind,accepted) {
        const declaration=section(assets,kind==='rename'?'        id: renameDialog':'        id: deleteDialog','    Dialog {');
        const handler=/(?:^|\n)        onAccepted: ([^\n]+)/.exec(declaration);
        if(accepted){if(!handler)throw Error('Original mutation dialog changed');vm.runInContext(handler[1],scope);}
        if(kind==='rename')renameVisible=false;else deleteVisible=false;tree.view.forceActiveFocus();
    }
    function dispatch(command) {
        const id=command.id;
        if(id.startsWith('assets.tree.row.')) {
            const index=Number(id.split('.').pop()),row=tree.rows[index];if(!row)throw Error('Missing actual modeled tree row');
            tree.index=index;tree.modelData=row;tree.list=tree.view;tree.mouse={modifiers:0,x:8};tree.Qt={ControlModifier:0x04000000};
            const handler=section(original,'                onClicked: function(mouse) {','                onDoubleClicked:');
            vm.runInContext('('+handler.trim().slice('onClicked: '.length)+')(mouse)',tree);return true;
        }
        if(id==='assets.refresh'){button('assetRefresh');return true;}
        if(id==='assets.rename'){if(canWrite&&!scope.busy&&scope.selectedItemCount===1)button('assetRename');return true;}
        if(id==='assets.delete'){if(canWrite&&!scope.busy&&scope.selectedItemCount>0)button('assetDelete');return true;}
        if(id==='assets.rename.path') {
            if(!renameVisible)throw Error('Missing real modeled rename dialog');
            if(command.action==='activate')renameFocused=true;
            else if(command.action==='replace'&&renameFocused)scope.renamePath.text=command.text;
            else throw Error('Missing actual modeled rename focus');return true;
        }
        if(id.startsWith('assets.rename.')||id.startsWith('assets.delete.')) {
            const kind=id.split('.')[1];if(!(kind==='rename'?renameVisible:deleteVisible))throw Error('Missing modeled mutation dialog');
            dialog(kind,id.endsWith('.accept'));return true;
        }
        return false;
    }
    function controls() {
        if(renameVisible)return [{id:'assets.rename.path',focused:renameFocused},{id:'assets.rename.accept'},{id:'assets.rename.cancel'}];
        if(deleteVisible)return [{id:'assets.delete.accept'},{id:'assets.delete.cancel'}];
        return [{id:'assets.upload'},{id:'assets.home'},{id:'assets.refresh'},...tree.rows.map((row,index)=>({id:'assets.tree.row.'+index})),
            {id:'assets.rename',enabled:canWrite&&!scope.busy&&scope.selectedItemCount===1},{id:'assets.delete',enabled:canWrite&&!scope.busy&&scope.selectedItemCount>0}];
    }
    refresh();
    return {snapshot,dispatch,controls,publish:rows=>{for(const row of rows)data.set(row.path,{base64:row.base64,status:0,errors:''});},
        configure:value=>{if('canWrite' in value){canWrite=value.canWrite;scope.assetWriteAllowed=canWrite;}
            if('deferMappings' in value)defer=value.deferMappings;if('mappingError' in value)mutationError=value.mappingError;
            if(value.completeMappings)while(pending.length){const job=pending.shift();qt.callLater(()=>finish(job));}
            if(value.serverRows){data.clear();for(const row of value.serverRows)data.set(row.path,{base64:row.base64,status:row.status||0,errors:row.errors||''});refresh();}}};
};
