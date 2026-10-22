"""Original Asset Browser controls; normal input recipes, no mapping verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import unquote,urlsplit
from pathlib import PurePosixPath
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import TokenCreateUI,ascii_text,nonce,scope
from adapters.token_script_file_ui import file_url

FIXED={'assets.page','assets.tree','assets.filter','assets.close','assets.refresh','assets.import','assets.upload',
    'assets.rename','assets.delete','assets.baking','assets.rename.path','assets.destination.path','assets.model.url',
    'assets-file.name','assets-file.folder','assets-file.list','assets-file.primary','assets-file.accept','assets-file.cancel','assets-file.confirm',
    'assets-file.back','assets-file.review-cancel','tablet.home'}
FIXED|={'assets.'+dialog+'.'+operation for dialog in ('rename','delete','destination','model') for operation in ('accept','cancel')}
FIELDS={'assets.filter','assets.rename.path','assets.destination.path','assets.model.url','assets-file.name','assets-file.folder'}


def control_id(value):
    return type(value) is str and (value in FIXED or bool(re.fullmatch(r'assets(?:-file)?\.row\.(?:0|[1-9][0-9]{0,3})',value)))


def ui_text(value):
    need(type(value) is str and len(value)<=4096 and all(ord(ch)>=32 and ord(ch)!=127 for ch in value))
    return value


def picker(value):
    exact(value,{'caption','directory','error','closing','pendingDocuments','selectedUrls','review','bundleRoot','bundleUrls','relativePaths'})
    need(value['caption']=='Select an asset and its companion files' and all(type(value[k]) is bool for k in ('closing','pendingDocuments','review')))
    file_url(value['directory']);ui_text(value['error'])
    for key in ('selectedUrls','bundleUrls','relativePaths'):
        need(type(value[key]) is list and len(value[key])<=32 and len(set(value[key]))==len(value[key]))
        for item in value[key]:
            if key=='relativePaths':ascii_text(item);need(item and not item.startswith('/') and all(p not in ('','.','..') for p in item.split('/')))
            else:file_url(item)
    need(len(value['bundleUrls'])==len(value['relativePaths']))
    if value['review']:file_url(value['bundleRoot']);need(bool(value['bundleUrls']))
    else:need(value['bundleRoot']=='' and value['bundleUrls']==value['relativePaths']==[])
    return value


def mapping(value,*,name=False):
    exact(value,{'path','folder','status'}|({'name'} if name else set()))
    for key in ('path','status',*(['name'] if name else [])):ascii_text(value[key])
    need(type(value['folder']) is bool and value['path'].startswith('/') and (not name or bool(value['name'])))
    return value


def metadata(row):
    need(type(row) is dict and control_id(row.get('id')) and nonce(row.get('token'))
        and all(type(row.get(k)) is bool for k in ('enabled','focused','inputReady')))
    identifier=row['id'];fields={'id','token','enabled','focused','inputReady'}
    if identifier=='assets.page':
        exact(row,fields|{'profile','canWrite','canImport','busy','status','selectedPath','selectedUrl','selection','selectedStatus',
            'treeRevision','uploadedPrimaryUrl','uploadActive','pendingBundle'})
        need(row['profile']=='native-assets-v1' and row['inputReady'] is False and integer(row['treeRevision'])
            and all(type(row[k]) is bool for k in ('canWrite','canImport','busy','uploadActive','pendingBundle'))
            and type(row['selection']) is list and len(row['selection'])<=256)
        for item in row['selection']:mapping(item)
        for key in ('status','selectedPath','selectedUrl','selectedStatus','uploadedPrimaryUrl'):ui_text(row[key])
    elif identifier.startswith('assets-file.'):
        fields|={'picker'};picker(row['picker'])
        if identifier in ('assets-file.name','assets-file.folder'):fields|={'text'};ascii_text(row['text'])
        elif identifier=='assets-file.primary':
            fields|={'currentIndex','count','currentText'}
            need(integer(row['currentIndex'],0,31) and integer(row['count'],1,32) and row['currentIndex']<row['count']);ascii_text(row['currentText'])
        elif identifier.startswith('assets-file.row.'):
            fields|={'sourceUrl','directory','selected'};file_url(row['sourceUrl'])
            need(type(row['directory']) is bool and type(row['selected']) is bool)
        exact(row,fields)
    elif identifier in FIELDS:exact(row,fields|{'text'});ascii_text(row['text'])
    elif identifier.startswith('assets.row.'):exact(row,fields|{'mapping'});mapping(row['mapping'],name=True)
    elif identifier=='assets.baking':exact(row,fields|{'checked'});need(type(row['checked']) is bool)
    else:exact(row,fields)
    return row


def snapshot(value):
    exact(value,{'assetsControlsVersion','open','ready','scope','controls'})
    need(type(value['assetsControlsVersion']) is int and value['assetsControlsVersion']==1
        and all(type(value[k]) is bool for k in ('open','ready')) and type(value['controls']) is list and len(value['controls'])<=384)
    scope(value['scope']);ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
    need(value['ready'] or not value['controls']);return value


def same_reference(original,current,identifier):
    snapshot(original);snapshot(current)
    need(all(original['scope'][key]==current['scope'][key] for key in ('instance','generation','sequence','processId'))
        and 0<=current['scope']['elapsedMs']-original['scope']['elapsedMs']<=5000)
    old=[row for row in original['controls'] if row['id']==identifier];new=[row for row in current['controls'] if row['id']==identifier]
    need(len(old)==len(new)==1 and old[0]==new[0]);return old[0]


class TokenAssetsUI(TokenCreateUI):
    """Reuse the normal token clock/wait/row engine, with closed Assets schema."""
    def capture(self):
        value=deepcopy(snapshot(self.io.capture()));original=value['scope']
        need(self.instance in (None,original['instance']) and self.pid in (None,original['processId'])
            and original['elapsedMs']>=self.elapsed and original['sequence']>=self.sequence)
        self.instance,self.pid,self.elapsed,self.sequence,self.generation=(original[k] for k in ('instance','processId','elapsedMs','sequence','generation'))
        return value
    def page(self,value):return self.row(value,'assets.page',enabled=False)
    @staticmethod
    def file_picker(value):
        rows=[row['picker'] for row in value['controls'] if row['id'].startswith('assets-file.')]
        need(not rows or all(row==rows[0] for row in rows));return rows[0] if rows else None
    def input(self,identifier,action='activate',value=None):
        need(control_id(identifier) and identifier!='assets.page' and action in ('activate','probe-disabled','replace','submit','select-index','scroll'))
        if action=='probe-disabled':need(identifier=='assets.delete' and value is None)
        elif action=='replace':need(identifier in FIELDS);ascii_text(value)
        elif action=='submit':need(identifier=='assets-file.folder' and value is None)
        elif action=='select-index':need(identifier=='assets-file.primary' and integer(value,0,31))
        elif action=='scroll':need(identifier in ('assets.tree','assets-file.list') and value in ('up','down'))
        else:need(identifier not in ('assets.tree','assets-file.list') and value is None)
        before=self.capture();row=self.row(before,identifier,enabled=action!='probe-disabled');need(row is not None and before['open'] and before['ready'])
        if action=='probe-disabled':need(not row['enabled'] and not row['inputReady'])
        if action in ('replace','submit'):need(row['focused'])
        if action=='select-index':need(value<row['count'])
        original=dict(controlId=identifier,action=action,value=deepcopy(value),original=deepcopy(before))
        if self.audit is not None:need(self.audit('intent',deepcopy(original)) is not False)
        self.intent(dict(assetsInputVersion=1,action=action,controlId=identifier,controlToken=row['token'],scope=deepcopy(before['scope'])))
        if action=='probe-disabled':self.io.probe_disabled(identifier,reference=before)
        elif action=='activate':self.io.activate(identifier,reference=before)
        elif action=='replace':self.io.replace(identifier,value,reference=before)
        elif action=='submit':self.io.submit(identifier,reference=before)
        elif action=='select-index':self.io.select_index(identifier,value,reference=before)
        else:self.io.scroll(identifier,value,reference=before)
        after=self.capture();need(after['scope']['sequence']>before['scope']['sequence'])
        if self.audit is not None:need(self.audit('receipt',dict(intent=original,after=deepcopy(after))) is not False)
        return after
    def replace(self,identifier,text):
        need(identifier in FIELDS);ascii_text(text);self.input(identifier)
        self.wait(lambda value:bool(self.row(value,identifier) and self.row(value,identifier)['focused']))
        self.input(identifier,'replace',text)
        return self.wait(lambda value:bool(self.row(value,identifier) and self.row(value,identifier)['text']==text))
    def open_assets(self,create):
        need(self.page(self.capture()) is None)
        create.open_create();create.tab(3);create.reveal('create.assets');create.input('create.assets')
        return self.wait(lambda value:self.page(value) is not None)
    def close_assets(self):
        need(self.page(self.capture()) is not None and self.file_picker(self.capture()) is None)
        current=self.capture();identifier='assets.close' if self.row(current,'assets.close') else 'tablet.home'
        self.input(identifier);return self.wait(lambda value:self.page(value) is None)
    def select_mapping(self,path):
        ascii_text(path);need(path.startswith('/') and len(path)>1)
        self.replace('assets.filter',path)
        value=self.wait(lambda value:any(row.get('mapping',{}).get('path')==path for row in value['controls']))
        rows=[row for row in value['controls'] if row.get('mapping',{}).get('path')==path];need(len(rows)==1)
        self.input(rows[0]['id'])
        return self.wait(lambda value:bool(self.page(value) and self.page(value)['selectedPath']==path))
    def open_picker(self):
        need(self.file_picker(self.capture()) is None);self.input('assets.upload')
        return self.wait(lambda value:self.file_picker(value) is not None)
    def cancel_picker(self):
        need(self.file_picker(self.capture()) is not None)
        self.input('assets-file.review-cancel' if self.file_picker(self.capture())['review'] else 'assets-file.cancel')
        return self.wait(lambda value:self.file_picker(value) is None)
    def navigate_files(self,path):
        ascii_text(path);need(re.fullmatch(r'/(?:[^/]+/)*feature-assets-[0-9a-f]{32}(?:-stage[1-6])?(?:/(?:gltf-bundle|obj-bundle|fbx-bundle)(?:/(?:mesh|textures|materials))?)?',path)
            and all(part not in ('.','..') for part in path.split('/')))
        self.replace('assets-file.folder',path);self.input('assets-file.folder','submit')
        return self.wait(lambda value:bool(self.file_picker(value) and unquote(urlsplit(self.file_picker(value)['directory']).path).rstrip('/')==path.rstrip('/')))
    def select_file(self,path):
        actual=file_url(path)
        need(re.fullmatch(r'/(?:[^/]+/)*feature-assets-[0-9a-f]{32}(?:-stage[1-6])?/(?:gltf-bundle/(?:main\.gltf|mesh/triangle\.bin|textures/checker\.png)|obj-bundle/(?:main\.obj|materials/palette\.mtl|textures/checker\.png)|fbx-bundle/stand\.fbx)',actual))
        value=self.wait(lambda value:any(row.get('sourceUrl')==path and row.get('directory') is False for row in value['controls']))
        rows=[row for row in value['controls'] if row.get('sourceUrl')==path and row.get('directory') is False];need(len(rows)==1)
        self.input(rows[0]['id']);return self.wait(lambda value:path in self.file_picker(value)['selectedUrls'])
    def upload_bundle(self,directory,resource,destination):
        """Only common controlled INPUT bundles enter the normal file picker."""
        from feature_journeys.asset_fixture import BUNDLES
        need(resource in BUNDLES);ascii_text(directory);ascii_text(destination)
        need(re.fullmatch(r'/e2e-([0-9a-f]{32})/',destination) and directory.rsplit('feature-assets-',1)[-1].split('-stage')[0]==destination[5:-1])
        need(re.fullmatch(r'/(?:[^/]+/)*feature-assets-[0-9a-f]{32}(?:-stage[1-6])?',directory) and all(part not in ('.','..') for part in directory.split('/')))
        prefix='fbx-bundle' if resource=='asset-stand.fbx' else resource.split('/')[0]
        self.open_picker()
        from urllib.parse import quote
        primary,paths=BUNDLES[resource]
        selected=[]
        for name in paths:
            parent=str(PurePosixPath(name).parent);folder=directory+'/'+prefix+('' if parent=='.' else '/'+parent)
            self.navigate_files(folder);url='file://'+quote(directory+'/'+prefix+'/'+name,safe='/')
            self.select_file(url);selected.append(url)
        need(sorted(self.file_picker(self.capture())['selectedUrls'])==sorted(selected))
        self.review_bundle(primary);return self.destination(destination)

    def review_bundle(self,primary):
        ascii_text(primary);self.input('assets-file.accept')
        current=self.wait(lambda value:bool(self.file_picker(value) and self.file_picker(value)['review']))
        paths=self.file_picker(current)['relativePaths'];need(paths.count(primary)==1)
        self.input('assets-file.primary');self.input('assets-file.primary','select-index',paths.index(primary))
        self.wait(lambda value:bool(self.row(value,'assets-file.primary') and self.row(value,'assets-file.primary')['currentText']==primary))
        self.input('assets-file.confirm');return self.wait(lambda value:self.row(value,'assets.destination.path') is not None)
    def destination(self,path):
        ascii_text(path);need(re.fullmatch(r'/e2e-[0-9a-f]{32}/',path))
        self.replace('assets.destination.path',path);self.input('assets.destination.accept')
        return self.wait(lambda value:bool(self.page(value) and not self.page(value)['busy'] and not self.page(value)['uploadActive']))
    def import_selected(self):
        self.input('assets.import');self.wait(lambda value:self.row(value,'assets.model.url') is not None)
        self.input('assets.model.accept');return self.wait(lambda value:self.row(value,'assets.model.url') is None)
    def rename_folder(self,path):
        ascii_text(path);need(re.fullmatch(r'/renamed-[0-9a-f]{32}/',path))
        self.input('assets.rename');self.wait(lambda value:self.row(value,'assets.rename.path') is not None)
        self.replace('assets.rename.path',path);self.input('assets.rename.accept')
    def delete_selected(self):
        self.input('assets.delete');self.wait(lambda value:self.row(value,'assets.delete.accept') is not None)
        self.input('assets.delete.accept')
    def baking(self,enabled):
        need(type(enabled) is bool);current=self.capture();row=self.row(current,'assets.baking');need(row is not None)
        if row['checked']!=enabled:self.input('assets.baking')
        return self.wait(lambda value:bool(self.row(value,'assets.baking') and self.row(value,'assets.baking')['checked']==enabled))
