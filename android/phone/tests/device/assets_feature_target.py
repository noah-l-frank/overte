"""Explicit synthetic widget/backend/renderer endpoints for Assets composition.

Only the real private native file header is executed here. No public feature
operation/state/expectation is implemented by the target. The synthetic oven
endpoint retains original fixture FBX bytes; it supplies no real baked-product
qualification. Native worker/source contracts are tested separately.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import unquote,urlsplit
import uuid
from PIL import Image
from create_feature_target import Target as CreateTarget,Proxy as CreateProxy,Handler as CreateHandler,ROOT,RUN,DOMAIN,POLICY,raw
from adapters.token_assets_ui import TokenAssetsUI
from overte_phone_assets_controls import PhoneAssetsIO
from overte_phone_assets_files import PhoneAssetsFiles
from overte_phone_assets_source import PhoneAssetsSource
from overte_phone_assets_uploads import PhoneAssetsUploads
from adapters.normal_feature_state import PrivateFeatureState
from fixture.assets_permissions import AssetsPermissions,WRITE
from fixture.messages_mixer import start_identity
from overte_phone_assets_backend import sha

class Target(CreateTarget):
    def __init__(self,root,files):
        super().__init__(root,files);self.browser=False;self.selected='';self.asset_focus=None;self.asset_text={};self.asset_sequence=0;self.dialog=None
        self.picker=None;self.chosen=[];self.review=False;self.relative=[];self.pending_bundle=None;self.primary_index=0;self.uploaded=''
        self.mappings={};self.blobs={};self.jobs=[];self.bundles=[];self.uploads_retired=False;self.server_sequence=0;self.retired_ids=None
        for row in self.settings.security['standard_permissions']:row[WRITE]=True
        self.permissions=AssetsPermissions(files.process,lambda pid:pid==self.pid,self.settings.server_address[1],DOMAIN,PrivateFeatureState(root/'assets-domain-permissions.json'))
    def can_write(self):return self.settings.security['standard_permissions'][0][WRITE]
    def controls(self):
        rows=super().controls()
        if self.tablet and self.page and self.widgets.tab==3:rows.append(dict(id='create.assets',enabled=True,focused=False,inputReady=True,token='9'*32))
        return rows
    def ui(self,outer):
        request=outer['request']
        if request['action']=='activate' and request['controlId']=='create.assets':
            row=next(row for row in self.controls() if row['id']=='create.assets');assert request['controlToken']==row['token'];self.widgets.sequence+=1;self.browser=True;self.inputs.append(deepcopy(request))
            return dict(schemaVersion=1,commandId=request['commandId'],action=request['action'],performed=True,instance='4'*32,generation='5'*32,sequence=self.widgets.sequence,processId=self.pid)
        return super().ui(outer)
    def asset_rows(self):
        rows=[]
        def add(identifier,enabled=True,inputReady=None,**more):
            row=dict(id=identifier,enabled=enabled,focused=self.asset_focus==identifier,inputReady=enabled if inputReady is None else inputReady)|more
            row['token']=sha(json.dumps([row,self.selected,self.dialog,self.picker,self.review],sort_keys=True))[:32];rows.append(row)
        if not self.browser:return rows
        status='--' if self.selected not in self.mappings else {0:'--',1:'Not Baked',4:'Baked'}[self.mappings[self.selected]['bakeStatus']]
        selection=[] if not self.selected else [dict(path=self.selected,folder=self.selected.endswith('/'),status=status)]
        add('assets.page',inputReady=False,profile='native-assets-v1',canWrite=self.can_write(),canImport=True,busy=False,status='',selectedPath=self.selected,
            selectedUrl='atp:'+self.selected if self.selected else '',selection=selection,selectedStatus=status,treeRevision=len(self.mappings),uploadedPrimaryUrl=self.uploaded,uploadActive=False,pendingBundle=self.pending_bundle is not None)
        add('assets.close');add('assets.refresh');add('assets.tree');add('assets.filter',text=self.asset_text.get('assets.filter',''))
        add('assets.upload',self.can_write());add('assets.import',bool(self.selected and not self.selected.endswith('/')));add('assets.rename',bool(self.selected) and self.can_write());add('assets.delete',bool(self.selected) and self.can_write())
        bake=self.selected in self.mappings and self.mappings[self.selected]['bakeStatus']!=0
        add('assets.baking',bool(bake and self.can_write()),checked=bool(bake and self.mappings[self.selected]['bakeStatus']!=1))
        paths=set(self.mappings)
        for path in list(paths):
            if path.startswith('/.baked/'):continue
            parent=path.rsplit('/',1)[0]+'/'
            while parent!='/':paths.add(parent);parent=parent.rstrip('/').rsplit('/',1)[0]+'/'
        visible=[path for path in sorted(paths) if not path.startswith('/.baked/') and self.asset_text.get('assets.filter','') in path]
        for index,path in enumerate(visible):add('assets.row.'+str(index),mapping=dict(path=path,name=path.rstrip('/').rsplit('/',1)[1],folder=path.endswith('/'),status='--' if path.endswith('/') else {0:'--',1:'Not Baked',4:'Baked'}[self.mappings[path]['bakeStatus']]))
        if self.dialog:
            if self.dialog!='delete':add('assets.'+self.dialog+'.path' if self.dialog!='model' else 'assets.model.url',text=self.asset_text.get('assets.'+self.dialog+'.path', 'atp:'+self.selected if self.dialog=='model' else self.selected))
            add('assets.'+self.dialog+'.accept');add('assets.'+self.dialog+'.cancel')
        if self.picker is not None:
            original=dict(caption='Select an asset and its companion files',directory=Path(self.picker).as_uri(),error=self.error,closing=False,pendingDocuments=False,
                selectedUrls=list(self.chosen),review=self.review,bundleRoot=Path(self.bundle_root).as_uri() if self.review else '',bundleUrls=list(self.chosen) if self.review else [],relativePaths=list(self.relative) if self.review else [])
            def file(identifier,**more):add(identifier,picker=deepcopy(original),**more)
            file('assets-file.folder',text=self.asset_text.get('assets-file.folder',self.picker));file('assets-file.name',text='');file('assets-file.cancel');file('assets-file.accept');file('assets-file.list')
            if self.review:
                file('assets-file.primary',currentIndex=self.primary_index,count=len(self.relative),currentText=self.relative[self.primary_index]);file('assets-file.confirm');file('assets-file.review-cancel')
            else:
                for index,path in enumerate(sorted(Path(self.picker).iterdir())):file('assets-file.row.'+str(index),sourceUrl=path.as_uri(),directory=path.is_dir(),selected=path.as_uri() in self.chosen)
        return rows
    def assets_ui(self,outer):
        request=outer['request']
        if request['action']=='observe':return dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance='1'*32,generation='2'*32,sourceSequence=self.count('assets-ui'),lastCommandSequence=self.asset_sequence,
            elapsedMs=round((time.monotonic()-self.started)*1000),capturedEpochMs=self.now(),processId=self.pid,assetsControlsVersion=1,ready=True,controls=self.asset_rows())
        row=next(row for row in self.asset_rows() if row['id']==request['controlId']);assert row['token']==request['controlToken'] and request['sequence']==self.asset_sequence+1
        action=request['action'];identifier=request['controlId'];assert not row['enabled'] if action=='probe-disabled' else row['enabled']
        self.asset_sequence+=1;self.inputs.append(deepcopy(request))
        if identifier not in self.ignore:
            if action=='replace':self.asset_text[identifier]=request['text']
            elif action=='submit':self.picker=self.asset_text['assets-file.folder'];self.asset_text['assets-file.folder']=self.picker
            elif action=='select-index':self.primary_index=request['index']
            elif action=='activate':
                self.asset_focus=identifier
                if identifier=='assets.close':self.browser=False;self.selected='';self.dialog=None
                elif identifier.startswith('assets.row.'):self.selected=row['mapping']['path']
                elif identifier=='assets.upload':self.picker=str(self.files.directory);self.chosen=[];self.error='';self.review=False;self.asset_text.pop('assets-file.folder',None)
                elif identifier.startswith('assets-file.row.'):
                    if row['sourceUrl'] in self.chosen:self.chosen.remove(row['sourceUrl'])
                    else:self.chosen.append(row['sourceUrl'])
                elif identifier=='assets-file.accept':
                    if any(not Path(unquote(urlsplit(url).path)).is_file() for url in self.chosen):self.error='A selected file is no longer available.'
                    else:
                        assert self.chosen;self.review=True;self.bundle_root=os.path.commonpath([str(Path(unquote(urlsplit(url).path)).parent) for url in self.chosen]);self.relative=[str(Path(unquote(urlsplit(url).path)).relative_to(self.bundle_root)) for url in self.chosen];self.primary_index=0
                elif identifier=='assets-file.confirm':
                    self.pending_bundle=dict(root=self.bundle_root,paths=list(self.chosen),relative=list(self.relative),primary=self.relative[self.primary_index]);self.picker=None;self.review=False;self.dialog='destination'
                elif identifier in ('assets-file.cancel','assets-file.review-cancel'):self.picker=None;self.chosen=[];self.review=False;self.error=''
                elif identifier=='assets.destination.accept':self.upload(self.asset_text['assets.destination.path']);self.dialog=None
                elif identifier=='assets.rename':self.dialog='rename';self.asset_text['assets.rename.path']=self.selected
                elif identifier=='assets.rename.accept':
                    old=self.selected;new=self.asset_text['assets.rename.path'];self.mappings={path.replace(old,new,1) if path.startswith(old) else path:dict(value,path=path.replace(old,new,1) if path.startswith(old) else path) for path,value in self.mappings.items()};self.selected='';self.dialog=None
                elif identifier=='assets.delete':self.dialog='delete'
                elif identifier=='assets.delete.accept':
                    self.mappings={path:value for path,value in self.mappings.items() if not path.startswith(self.selected)};self.selected='';self.collect();self.dialog=None
                elif identifier=='assets.import':self.dialog='model'
                elif identifier=='assets.model.accept':self.create('Model','atp:'+self.selected);self.dialog=None
                elif identifier=='assets.baking':
                    digest=self.mappings[self.selected]['hash']
                    if self.mappings[self.selected]['bakeStatus']==1:self.bake(self.selected)
                    else:
                        self.mappings={path:value for path,value in self.mappings.items() if not path.startswith('/.baked/'+digest+'/')};self.mappings[self.selected]['bakeStatus']=1
                        self.mappings['/.baked/'+digest+'/asset.fbx']=dict(path='/.baked/'+digest+'/asset.fbx',hash=digest,bakeStatus=4,bakeError='');self.collect()
                elif identifier.endswith('.cancel') and identifier.startswith('assets.'):self.dialog=None;self.pending_bundle=None
        return dict(schemaVersion=1,commandId=request['commandId'],action=action,performed=True,instance='1'*32,generation='2'*32,sequence=self.asset_sequence,processId=self.pid)
    def collect(self):
        originals={row['hash'] for path,row in self.mappings.items() if not path.startswith('/.baked/')}
        self.mappings={path:row for path,row in self.mappings.items() if not path.startswith('/.baked/') or path.split('/')[2] in originals}
        referenced={row['hash'] for row in self.mappings.values()};self.blobs={key:value for key,value in self.blobs.items() if key in referenced}
    def upload(self,destination):
        bundle=self.pending_bundle;now=self.now();identifier=str(uuid.uuid4());requests=[];context=dict(domainId=DOMAIN,sessionId=DOMAIN,assetServerId=DOMAIN)
        for url,name in zip(bundle['paths'],bundle['relative']):
            path=unquote(urlsplit(url).path);data=Path(path).read_bytes();digest=sha(data);self.blobs[digest]=data
            requests.append(dict(instance=uuid.uuid4().hex,kind='upload',issuedEpochMs=now,completedEpochMs=now,destroyedEpochMs=now,original=dict(filenameSha256=sha(path),originalSha256=digest,originalBytes=len(data),errorCode=0,returnedHash=digest)))
        for url,name in zip(bundle['paths'],bundle['relative']):
            data=Path(unquote(urlsplit(url).path)).read_bytes();digest=sha(data);path=destination+name;self.mappings[path]=dict(path=path,hash=digest,bakeStatus=0,bakeError='')
            requests.append(dict(instance=uuid.uuid4().hex,kind='mapping',issuedEpochMs=now,completedEpochMs=now,destroyedEpochMs=now,original=dict(path=path,hash=digest,errorCode=0)))
        self.bundles.append(dict(id=identifier,runId=RUN,directorySha256=sha(bundle['root']),destination=destination,primary=bundle['primary'],files=[dict(relativePath=name,filenameSha256=sha(unquote(urlsplit(url).path))) for url,name in zip(bundle['paths'],bundle['relative'])],
            connection=context,createdEpochMs=now,active=False,finishedEpochMs=now,errorSha256=sha(''),requests=requests))
        self.uploaded='atp:'+destination+bundle['primary'];self.pending_bundle=None
        if self.uploaded.endswith('.fbx'):self.bake(destination+bundle['primary'])
    def bake(self,path):
        now=self.now();digest=self.mappings[path]['hash'];prefix='/.baked/'+digest+'/';fst=prefix+'stand.baked.fst';mesh=prefix+'stand.baked.fbx'
        # Explicit synthetic backend, not actual oven output: body is the
        # unchanged pinned original and the container is a controlled FST seam.
        fst_data=b'filename = stand.baked.fbx\n';meta=json.dumps(dict(bake_version=7,failed_last_bake=False,last_bake_errors='',redirect_target=fst)).encode()
        for p,data in ((mesh,self.blobs[digest]),(fst,fst_data),(prefix+'meta.json',meta)):
            h=sha(data);self.blobs[h]=data;self.mappings[p]=dict(path=p,hash=h,bakeStatus=4,bakeError='')
        self.mappings[path]['bakeStatus']=4
        self.jobs.append(dict(instance=uuid.uuid4().hex,hash=digest,path=path,version=7,queuedEpochMs=now,startedEpochMs=now,runExitedEpochMs=now,ovenProcessId=123,ovenFinishedEpochMs=now,exitCode=0,exitStatus=0,terminalEpochMs=now,outcome='complete',destroyedEpochMs=now))
    def backend(self):
        self.server_sequence+=1
        return dict(schemaVersion=1,runId=RUN,source=dict(assetsBakeOriginalsVersion=2,instance='b'*32,sequence=self.server_sequence,processId=self.pid,processStart=start_identity(self.pid),domainId=DOMAIN,assetServerId=DOMAIN,capturedEpochMs=self.now(),contextCapturedEpochMs=self.now(),valid=True,jobs=deepcopy(self.jobs),
            mappings=[dict(path=path,hash=row['hash']) for path,row in sorted(self.mappings.items())],blobs=[dict(hash=digest,actualSha256=sha(data),bytes=len(data)) for digest,data in sorted(self.blobs.items())],pending=0))
    def create(self,kind,url=None):
        super().create(kind,url)
        if kind!='Model' or not url or not url.startswith('atp:'):return
        path=url[4:];row=self.rows[-1];entry=self.mappings[path];digest=entry['hash'];source_path=path
        if entry['bakeStatus']==4:
            prefix='/.baked/'+digest+'/';source_path=prefix+'stand.baked.fbx';digest=self.mappings[source_path]['hash']
        geometry=row['render']['geometry'];geometry['reader']=dict(geometryInputVersion=1,instance=uuid.uuid4().hex,sourceSha256=sha('atp:'+source_path),originalSha256=digest,originalBytes=len(self.blobs[digest]),recordedEpochMs=self.now())
        geometry['sourcePresent']=not path.endswith('.obj');geometry['sourceSha256']=sha('atp:'+source_path) if geometry['sourcePresent'] else sha('');row['render']['recordedEpochMs']=self.now()
        texture=path.rsplit('/',1)[0]+'/textures/checker.png';geometry['textures']['rows']=[]
        if texture in self.mappings:
            digest=self.mappings[texture]['hash'];data=self.blobs[digest]
            with Image.open(io.BytesIO(data)) as image:w,h=image.size
            geometry['textures']['rows']=[dict(complete=True,revision=1,material=0,channel=0,name='checker.png',urlSha256=sha('atp:'+texture),loaded=True,failed=False,originalSha256=digest,originalBytes=len(data),gpuWidth=w,gpuHeight=h)]
    def source(self,key,request):
        if key=='assets-ui':return self.assets_ui(request)
        if key=='assets-files':
            self.files.send(request);value=deepcopy(self.files.value);value.update(requestedEpochMs=self.now(),capturedEpochMs=self.now());return value
        if key=='assets-uploads':
            if request['operation']=='release':
                assert request['instance']=='d'*32 and request['bundleIds']==sorted(row['id'] for row in self.bundles) if not self.uploads_retired else request['bundleIds']==self.retired_ids
                self.retired_ids=request['bundleIds'];self.bundles=[];self.uploads_retired=True
            source=dict(assetsUploadsVersion=1,instance='d'*32,runId=RUN,valid=True,retired=self.uploads_retired,activeBundles=0,liveRequests=0,retainedBundles=len(self.bundles),bundles=sorted(deepcopy(self.bundles),key=lambda row:row['id']))
            value=self.envelope(key,request,source);value.update(runId=RUN,operation=request['operation']);return value
        if key in ('assets','assets-download','assets-resolve'):
            if key=='assets':source=dict(phoneAssetsObservationVersion=2,domainId=DOMAIN,sessionId=DOMAIN,assetServerId=DOMAIN,canWrite=self.can_write(),complete=True,mappings=[deepcopy(row) for path,row in sorted(self.mappings.items())])
            elif key=='assets-download':
                data=self.blobs[request['hash']];source=dict(phoneAssetsDownloadVersion=2,domainId=DOMAIN,sessionId=DOMAIN,assetServerId=DOMAIN,hash=sha(data),bytes=len(data),base64=base64.b64encode(data).decode(),loadedFromCache=False)
            else:
                path=request['path'];digest=self.mappings[path]['hash'];redirect='/.baked/'+digest+'/stand.baked.fst' if self.mappings[path]['bakeStatus']==4 else ''
                source=dict(phoneAssetsResolveVersion=1,domainId=DOMAIN,sessionId=DOMAIN,assetServerId=DOMAIN,requestedPath=path,hash=self.mappings[redirect]['hash'] if redirect else digest,redirected=bool(redirect),redirectedPath=redirect)
            value=self.envelope(key,request,source);value.update(runId=RUN,activeRequests=0,retainedResults=0);return value
        value=super().source(key,request)
        if key=='draws':
            for draw in value['source']['modelTrace']['models']:
                row=next(row for row in self.rows if row['render'] and row['render']['modelInstance']==draw['modelInstance']);draw['loadedSourceSha256']=row['render']['geometry']['reader']['sourceSha256']
        return value

class Handler(CreateHandler):
    def do_POST(self):
        if self.path not in ('/v1/assets-originals','/v1/assets-permissions'):return super().do_POST()
        try:
            call=json.loads(self.rfile.read(int(self.headers['Content-Length'])));target=self.server.target
            with target.lock:
                if self.path.endswith('originals'):
                    assert self.headers.get('X-Overte-E2E-Token') in ('p'*64,'q'*64);value=target.backend()
                else:assert self.headers.get('X-Overte-E2E-Token')=='z'*64;value=target.permissions.request(call)
            body=json.dumps(value).encode();self.send_response(200)
        except Exception:
            import traceback;traceback.print_exc();self.server.errors.append('assets-source');body=b'{}';self.send_response(500)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

class Proxy(CreateProxy):
    def _assets_controls(self,_s,intent,**kw):return TokenAssetsUI(self.reader('assets-ui',PhoneAssetsIO),intent)
    def _assets_files(self,_s,*,stage=None,**kw):return self.reader('assets-files',PhoneAssetsFiles,stage=stage)
    def _assets_uploads(self,_s,**kw):return self.reader('assets-uploads',PhoneAssetsUploads)
    def _assets_source(self,_s,*,download=False,resolve=False,**kw):return self.reader('assets-download' if download else 'assets-resolve' if resolve else 'assets',PhoneAssetsSource,download=download,resolve=resolve)
