// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Execute original QML JS bodies. Qt/UI roots, keyboard, model and lifetime
// boundaries below are explicit host models, not UIKit/Qt/device evidence.
const fs=require('node:fs'),vm=require('node:vm'),readline=require('node:readline');
const {pathToFileURL,fileURLToPath}=require('node:url');
const pathUtil=require('node:path'),crypto=require('node:crypto');
const assets=fs.readFileSync(process.argv[2],'utf8'),picker=fs.readFileSync(process.argv[3],'utf8');
const navigation=fs.readFileSync(process.argv[4],'utf8');
function section(source,start,end) {
    const a=source.indexOf(start),b=source.indexOf(end,a+start.length);
    if(a<0||b<=a)throw Error('Original QML source boundary changed');return source.slice(a,b);
}
function signal() {const listeners=[];const emit=(...args)=>{for(const fn of listeners)fn(...args);};emit.connect=fn=>listeners.push(fn);return emit;}
let pageAlive=false,pickerAlive=false,editOpen=false,focused=false,folderText='',pickerScope=null;
let held=false,ignored='',lost='',uploads=0,canceled=0,selectedBundles=0,destinationCalls=0;
let allowBundleUploads=false,destinationVisible=false,destinationFocused=false,primaryFocused=false,deferUpload=false,uploadError='';
const serviceEvents=[],serviceJobs=new Map();
const queued=[];
const qt={callLater:fn=>queued.push(fn)};
function flush() {if(!held)while(queued.length)queued.shift()();}
const helper={
    pathToUrl:path=>pathToFileURL(path).href,urlToPath:url=>fileURLToPath(url),
    urlIsFile:url=>{try{return fs.lstatSync(fileURLToPath(url)).isFile();}catch(_){return false;}},
    urlIsDir:url=>{try{return fs.lstatSync(fileURLToPath(url)).isDirectory();}catch(_){return false;}},
    documentBundle:(urls,directory)=>{
        if(!allowBundleUploads)throw Error('Unavailable-file path must not prepare a bundle');
        if(!urls.length||urls.length>32)return {error:'Invalid controlled selection'};
        let root=directory?fileURLToPath(directory):pathUtil.dirname(fileURLToPath(urls[0]));
        for(const url of urls)while(pathUtil.relative(root,fileURLToPath(url)).startsWith('../'))root=pathUtil.dirname(root);
        const relative=[],files=[],seen=new Set();
        for(const url of urls){const file=fileURLToPath(url),stat=fs.lstatSync(file),name=pathUtil.relative(root,file);
            if(!stat.isFile()||stat.isSymbolicLink()||seen.has(name)||name.startsWith('../'))return {error:'Invalid original file'};
            seen.add(name);relative.push(name);files.push(url);}
        return {root:pathToFileURL(root).href,urls:files,relativePaths:relative,error:''};
    },
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
    bundleDestination:{text:''},bundleDialog:{open:()=>{destinationCalls++;destinationVisible=true;}},
    lifecycle:{active:true},assetMappingsModel:{autoRefreshEnabled:true},uploadedPrimaryUrl:'',fileDialogHelper:helper,reload:()=>{},Assets:{
        uploadBundle:(files,relative,destination,primary,progress,completed)=>{
            uploads++;if(!allowBundleUploads)throw Error('No upload expected');
            const id=crypto.randomUUID();const job={id,files,relative,destination,primary,completed};serviceJobs.set(id,job);
            serviceEvents.push({kind:'started',id,files,relative,destination,primary});
            if(!deferUpload)qt.callLater(()=>finishUpload(id));return id;
        },
        cancelUploadBundle:id=>{serviceEvents.push({kind:'cancel-issued',id});qt.callLater(()=>finishUpload(id,'Canceled'));}
    }};
assetScope.root=assetScope;vm.createContext(assetScope);
const treeHarness=process.argv[5]?require('./assets_tree_host.js')({vm,fs,assets,treeSource:process.argv[5],scope:assetScope,qt,events:serviceEvents,section}):null;
vm.runInContext(section(assets,'    function uploadClicked(', '    function uploadSingleClicked('),assetScope);
vm.runInContext(section(assets,'    function uploadBundle(', '    function importUploadedMain('),assetScope);
function finishUpload(id,error=uploadError){
    const job=serviceJobs.get(id);if(!job)return;
    const prefix=job.destination.replace(/\/+$/,'')+'/',published=error?[]:job.relative.map(name=>prefix+name);
    const actual=error?[]:job.files.map((file,index)=>{const raw=fs.readFileSync(file);return {path:published[index],base64:raw.toString('base64'),sha256:crypto.createHash('sha256').update(raw).digest('hex')};});
    serviceEvents.push({kind:'completion-entered',id,error,actual});
    if(treeHarness)treeHarness.publish(actual);
    job.completed(error,JSON.stringify(published),prefix+job.primary);
    serviceEvents.push({kind:'completion-returned',id});serviceJobs.delete(id);
}
const nav={modelData:{key:'home'},navigation:{homeRequested:()=>{pageAlive=false;},backRequested:()=>{throw Error('No Back input');},closeRequested:()=>{throw Error('No Close input');}}};
vm.createContext(nav);
const activate=section(navigation,'                function activate() {','            }\n        }');
vm.runInContext(activate,nav);
function snapshot() {
    const controls=[];
    if(pickerAlive && allowBundleUploads && pickerScope.bundle) {
        controls.push({id:'asset-file.bundle-primary',focused:primaryFocused},{id:'asset-file.bundle-use'},
            {id:'asset-file.bundle-back'},{id:'asset-file.cancel'});
    } else if(pickerAlive) {
        controls.push({id:'asset-file.folder',focused,fieldText:folderText},...fileRows().map((row,index)=>({id:'asset-file.row.'+index,rowUrl:row.fileUrl})),
            {id:'asset-file.select'},{id:'asset-file.cancel'});
    } else if(pageAlive && destinationVisible)controls.push({id:'assets.destination',focused:destinationFocused,fieldText:assetScope.bundleDestination.text},
        {id:'assets.destination.accept'},{id:'assets.destination.cancel'});
    else if(pageAlive)controls.push(...(treeHarness?treeHarness.controls():[{id:'assets.upload'},{id:'assets.home'}]));
    else controls.push({id:editOpen?'assets.open':'assets.menu'});
    const value={pageAlive,pickerAlive,controls,ui:pickerScope?{directory:String(pickerScope.dir),chosen:pickerScope.chosen,
        closing:pickerScope.closing,requestId:pickerScope.requestId,error:pickerScope.error,bundleReview:pickerScope.bundle!==null}:null,
        page:{busy:assetScope.busy,bundleRequest:assetScope.bundleRequest,status:assetScope.status,pendingBundle:assetScope.pendingBundle!==null,destinationOpen:allowBundleUploads?destinationVisible:destinationCalls>0},
        uploads,canceled,selectedBundles,destinationCalls,queued:queued.length};
    if(allowBundleUploads)value.bundleInfo={picker:pickerScope&&pickerScope.bundle?{...pickerScope.bundle,primaryIndex:pickerScope.primary.currentIndex,
        primaryPath:pickerScope.primary.currentIndex<0?'':pickerScope.bundle.relativePaths[pickerScope.primary.currentIndex]}:null,
        page:assetScope.pendingBundle?{...assetScope.pendingBundle,primaryIndex:assetScope.pendingBundle.relativePaths.indexOf(assetScope.pendingBundle.primaryPath)}:null,
        destinationVisible,destinationText:assetScope.bundleDestination.text,uploadedPrimaryUrl:assetScope.uploadedPrimaryUrl,serviceEvents};
    if(treeHarness)value.treeInfo=treeHarness.snapshot();
    return value;
}
function dispatch(command) {
    const id=command.id,action=command.action;
    if(ignored===id){ignored='';return;}
    if(id==='assets.menu'){editOpen=true;return;}
    if(id==='assets.open'){pageAlive=true;editOpen=false;assetScope.lifecycle={active:true};return;}
    if(id==='assets.upload'){assetScope.uploadClicked();return;}
    if(id==='assets.home'){
        nav.activate();const original=/Component\.onDestruction: \{ ([^\n]+) \}/.exec(assets);
        if(!original)throw Error('Original page destruction changed');vm.runInContext(original[1],assetScope);return;
    }
    if(id==='assets.destination'){
        if(!destinationVisible)throw Error('Destination is not visible');
        if(action==='activate'){destinationFocused=true;return;}
        if(action==='replace'&&destinationFocused){assetScope.bundleDestination.text=command.text;return;}
        throw Error('Missing actual modeled destination focus');
    }
    if(id==='assets.destination.accept'||id==='assets.destination.cancel'){
        if(!destinationVisible)throw Error('Destination is not visible');destinationVisible=false;destinationFocused=false;
        const declaration=section(assets,'        id: bundleDialog;','    Dialog {');
        const original=new RegExp(id.endsWith('accept')?'onAccepted: ([^\\n]+)':'onRejected: ([^\\n]+)').exec(declaration);
        if(!original)throw Error('Original destination handler changed');vm.runInContext(original[1],assetScope);return;
    }
    if(treeHarness&&treeHarness.dispatch(command))return;
    if(!pickerAlive)throw Error('Missing actual picker');
    if(id==='asset-file.bundle-primary'){
        if(action==='activate'){primaryFocused=true;return;}
        if(action==='select-index'&&primaryFocused&&Number.isInteger(command.index)&&command.index>=0&&command.index<pickerScope.bundle.relativePaths.length){pickerScope.primary.currentIndex=command.index;return;}
        throw Error('Missing actual modeled primary choice focus');
    }
    if(id==='asset-file.bundle-use'){pickerScope.confirmBundle();return;}
    if(id==='asset-file.bundle-back'){pickerScope.bundle=null;pickerScope.error='';return;}
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
    if(id.startsWith('asset-file.row.')){pickerScope.choose(Number(id.split('.').pop()));folderText=helper.urlToPath(pickerScope.dir);return;}
    if(id==='asset-file.select'){pickerScope.accept();return;}
    if(id==='asset-file.cancel'){pickerScope.cancel();return;}
    throw Error('Unrecognized ordinary modeled control');
}
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{
    try {
        const command=JSON.parse(line);
        if(command.op==='configure') {
            if(treeHarness)treeHarness.configure(command);
            if('hold' in command)held=command.hold;if('ignore' in command)ignored=command.ignore;if('lost' in command)lost=command.lost;
            if('initialDirectory' in command)assetScope.currentDirectory=pathToFileURL(command.initialDirectory).href;
            if('allowBundleUploads' in command)allowBundleUploads=command.allowBundleUploads;
            if('deferUpload' in command)deferUpload=command.deferUpload;if('uploadError' in command)uploadError=command.uploadError;
            if(command.completeUpload)for(const id of serviceJobs.keys())qt.callLater(()=>finishUpload(id));
        }
        if(command.op==='input')dispatch(command);
        flush();const result=snapshot();if(command.op==='input'&&lost===command.id){lost='';result.lost=true;}
        process.stdout.write(JSON.stringify(result)+'\n');
    } catch(error) {process.stdout.write(JSON.stringify({error:String(error)})+'\n');}
});
