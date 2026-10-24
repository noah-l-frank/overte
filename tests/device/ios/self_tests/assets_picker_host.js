// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Execute original QML JS bodies. Qt/UI roots, keyboard, model and lifetime
// boundaries below are explicit host models, not UIKit/Qt/device evidence.
const fs=require('node:fs'),vm=require('node:vm'),readline=require('node:readline');
const {pathToFileURL,fileURLToPath}=require('node:url');
const assets=fs.readFileSync(process.argv[2],'utf8'),picker=fs.readFileSync(process.argv[3],'utf8');
const navigation=fs.readFileSync(process.argv[4],'utf8');
function section(source,start,end) {
    const a=source.indexOf(start),b=source.indexOf(end,a+start.length);
    if(a<0||b<=a)throw Error('Original QML source boundary changed');return source.slice(a,b);
}
function signal() {const listeners=[];const emit=(...args)=>{for(const fn of listeners)fn(...args);};emit.connect=fn=>listeners.push(fn);return emit;}
let pageAlive=false,pickerAlive=false,editOpen=false,focused=false,folderText='',pickerScope=null;
let held=false,ignored='',lost='',uploads=0,canceled=0,selectedBundles=0,destinationCalls=0;
const queued=[];
const qt={callLater:fn=>queued.push(fn)};
function flush() {if(!held)while(queued.length)queued.shift()();}
const helper={
    pathToUrl:path=>pathToFileURL(path).href,urlToPath:url=>fileURLToPath(url),
    urlIsFile:url=>{try{return fs.lstatSync(fileURLToPath(url)).isFile();}catch(_){return false;}},
    urlIsDir:url=>{try{return fs.lstatSync(fileURLToPath(url)).isDirectory();}catch(_){return false;}},
    documentBundle:()=>{throw Error('Unavailable-file path must not prepare a bundle');},
    cancelDocuments:()=>{throw Error('No document request belongs to this vertical');}
};
function fileRows() {
    if(!pickerAlive)return [];
    return fs.readdirSync(fileURLToPath(pickerScope.dir)).sort().filter(name=>!name.startsWith('.')).map(name=>{
        const url=pathToFileURL(fileURLToPath(pickerScope.dir)+'/'+name).href;
        return {fileUrl:url,fileURL:url,fileName:name,fileIsDir:helper.urlIsDir(url)};
    });
}
function createPicker(properties) {
    if(pickerAlive)throw Error('A live picker already exists');pickerAlive=true;focused=false;
    const scope={dir:properties.dir,caption:'Select an asset and its companion files',bundleMode:true,multiSelect:true,
        selectDirectory:false,saveDialog:false,chosen:[],closing:false,requestId:'',error:'',bundle:null,
        primaryFilter:'',destroyOnCompletion:true,backStack:[],filename:{text:''},patterns:['*'],helper,Qt:qt,
        primary:{currentIndex:-1},selectedFile:signal(),selectedFiles:signal(),selectedBundle:signal(),
        canceled:signal(),destroy:()=>{pickerAlive=false;focused=false;},overwrite:{open:()=>{throw Error('No Save path');}}};
    scope.root=scope;scope.files={isFolder:index=>fileRows()[index].fileIsDir,get:(index,key)=>fileRows()[index][key]};
    vm.createContext(scope);
    vm.runInContext(section(picker,'    function finish(', '    function openSystemTree('),scope);
    vm.runInContext(section(picker,'    function cancel(', '    function openSystemPicker('),scope);
    vm.runInContext(section(picker,'    function enterDirectory(', '    onDirChanged:'),scope);
    scope.selectedBundle.connect(()=>selectedBundles++);scope.canceled.connect(()=>canceled++);
    pickerScope=scope;folderText=helper.urlToPath(scope.dir);return scope;
}
const assetScope={busy:false,status:'',pendingBundle:null,bundleRequest:'',selectedPath:'',currentDirectory:pathToFileURL('/tmp').href,
    writable:()=>true,Qt:qt,fileBrowser:{createObject:(_root,properties)=>createPicker(properties)},
    bundleDestination:{text:''},bundleDialog:{open:()=>{destinationCalls++;}},Assets:{uploadBundle:()=>{uploads++;throw Error('No upload expected');}}};
assetScope.root=assetScope;vm.createContext(assetScope);
vm.runInContext(section(assets,'    function uploadClicked(', '    function uploadSingleClicked('),assetScope);
const nav={modelData:{key:'home'},navigation:{homeRequested:()=>{pageAlive=false;},backRequested:()=>{throw Error('No Back input');},closeRequested:()=>{throw Error('No Close input');}}};
vm.createContext(nav);
const activate=section(navigation,'                function activate() {','            }\n        }');
vm.runInContext(activate,nav);
function snapshot() {
    const controls=[];
    if(pickerAlive) {
        controls.push({id:'asset-file.folder',focused,fieldText:folderText},...fileRows().map((row,index)=>({id:'asset-file.row.'+index,rowUrl:row.fileUrl})),
            {id:'asset-file.select'},{id:'asset-file.cancel'});
    } else if(pageAlive)controls.push({id:'assets.upload'},{id:'assets.home'});
    else controls.push({id:editOpen?'assets.open':'assets.menu'});
    return {pageAlive,pickerAlive,controls,ui:pickerScope?{directory:String(pickerScope.dir),chosen:pickerScope.chosen,
        closing:pickerScope.closing,requestId:pickerScope.requestId,error:pickerScope.error,bundleReview:pickerScope.bundle!==null}:null,
        page:{busy:assetScope.busy,bundleRequest:assetScope.bundleRequest,status:assetScope.status,pendingBundle:assetScope.pendingBundle!==null,destinationOpen:destinationCalls>0},
        uploads,canceled,selectedBundles,destinationCalls,queued:queued.length};
}
function dispatch(command) {
    const id=command.id,action=command.action;
    if(ignored===id){ignored='';return;}
    if(id==='assets.menu'){editOpen=true;return;}
    if(id==='assets.open'){pageAlive=true;editOpen=false;return;}
    if(id==='assets.upload'){assetScope.uploadClicked();return;}
    if(id==='assets.home'){nav.activate();return;}
    if(!pickerAlive)throw Error('Missing actual picker');
    if(id==='asset-file.folder') {
        if(action==='activate'){focused=true;return;}
        if(!focused)throw Error('Missing actual modeled keyboard focus');
        if(action==='replace'){folderText=command.text;return;}
        if(action==='submit') {
            const handler=/objectName: "fileFolderPath"[^\n]*onAccepted: \{ (.*) \} \}/.exec(picker);
            if(!handler)throw Error('Original folder keyboard handler changed');
            pickerScope.text=folderText;vm.runInContext(handler[1],pickerScope);folderText=helper.urlToPath(pickerScope.dir);return;
        }
    }
    if(id.startsWith('asset-file.row.')){pickerScope.choose(Number(id.split('.').pop()));return;}
    if(id==='asset-file.select'){pickerScope.accept();return;}
    if(id==='asset-file.cancel'){pickerScope.cancel();return;}
    throw Error('Unrecognized ordinary modeled control');
}
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{
    try {
        const command=JSON.parse(line);
        if(command.op==='configure') {
            if('hold' in command)held=command.hold;if('ignore' in command)ignored=command.ignore;if('lost' in command)lost=command.lost;
            if('initialDirectory' in command)assetScope.currentDirectory=pathToFileURL(command.initialDirectory).href;
        }
        if(command.op==='input')dispatch(command);
        flush();const result=snapshot();if(command.op==='input'&&lost===command.id){lost='';result.lost=true;}
        process.stdout.write(JSON.stringify(result)+'\n');
    } catch(error) {process.stdout.write(JSON.stringify({error:String(error)})+'\n');}
});
