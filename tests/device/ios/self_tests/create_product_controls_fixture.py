"""Modeled Qt widget buffers; real IOSCreateUI/NativeInput transport consumes them.

Only delivery of an admitted original token mutates this modeled product SDK.
No requested expected state, Action journal or observation result enters it.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
from ios.adapters import create_controls_v2 as grammar


class ProductControls:
    def __init__(self,fixture,instance,*,texts=None):
        self.fixture,self.product,self.instance=fixture,fixture.product,instance
        self.pid=42;self.generation=str(uuid.UUID('4'*32));self.sequence=0;self.focus=None;self.tab=0
        self.mode='home';self.texts={} if texts is None else texts;self.indexes={'create.host':0,'create.shape':0,'create.import-host':0}
        self.intents=[];self.inputs=[];self.polyvox=None
        self.product.search_original=lambda root:self.texts.get('create.property-search','')
    def editor(self):
        return next((row for row in self.product.value['source']['roots'] if row.get('kind')=='editor' and not row['destroyed']),None)
    def capture(self):
        source=self.product.value['source'];page=self.editor();selected=[] if page is None else page['page']['selectedIds'];rows=[]
        def row(id_,**extra):
            value=dict(id=id_,enabled=True,focused=self.focus==id_,inputReady=True,**extra)
            if id_.startswith('tablet.'):value.pop('inputReady')
            value['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([value,self.tab,selected],sort_keys=True)));rows.append(value)
        def field(id_,default=''):row(id_,text=self.texts.get(id_,default))
        def choice(id_,count):row(id_,count=count,currentIndex=self.indexes.get(id_,0))
        if source['tabletShown']:
            row('tablet.home')
            if self.mode!='create':row('create.entry')
            else:
                row('create.page',profile='native-create-v1',tab=self.tab,selectedIds=deepcopy(selected),statusError=page['page']['statusError'],
                    statusText=page['page']['statusText'],componentSourceSha256=page['page']['componentSourceSha256'])
                rows[-1]['inputReady']=False
                for index in range(5):row('create.tab.'+str(index))
                row('create.scrollbar',position=0.,size=1.)
                if self.tab==0:
                    choice('create.host',2);choice('create.shape',6);field('create.resource');row('create.new-shape');row('create.new-model')
                    choice('create.detailed-type',6);row('create.detailed-open')
                if self.tab==1:
                    row('create.refresh');field('create.filter')
                    for item in source['entities']:row('create.entity.'+item['id'],entityId=item['id'])
                if self.tab==2 and selected:
                    item=self.product.selected();field('create.name',item['name']);row('create.apply');row('create.delete')
                    for kind in ('position','dimensions'):
                        for axis,value in zip('xyz',item[kind]):field('create.field.'+kind+'.'+axis,str(value))
                    field('create.property-search');field('create.textures',item['textures']);row('create.apply-typed')
                if self.tab==3:
                    row('create.export');choice('create.voxel.mode',2)
                    for key,count in (('shape',3),('dynamics',2),('pointer',2)):choice('create.voxel.'+key,count)
                    row('create.voxel.remove',checked=self.product.page()['voxelSettings']['voxelRemove'])
                    field('create.voxel.diameter',str(self.product.page()['voxelSettings']['voxelSphereSize']))
                    field('create.voxel.reach',str(self.product.page()['voxelSettings']['voxelBrushLength']));row('create.voxel.apply')
                if self.tab==4:choice('create.import-host',2);row('create.import-browse')
                if self.polyvox is not None:
                    extra=dict(dialogRootId=self.polyvox,dialogSource='qrc:/system/create/qml/NewPolyVoxDialog.qml')
                    for id_ in ('texturePreset','surfaceStyle','initialShape'):choice('create.polyvox.'+id_,grammar.CHOICES['create.polyvox.'+id_]);rows[-1].update(extra)
                    for axis in 'XYZ':field('create.polyvox.volumeSize'+axis,'8');rows[-1].update(extra)
                    row('create.polyvox.accept',**extra);row('create.polyvox.cancel',**extra)
                for root in source['roots']:
                    if root.get('kind') not in ('import','export') or root['destroyed']:continue
                    role=root['kind'];extra=dict(picker=deepcopy(root['picker']))
                    field('create.'+role+'.filename');rows[-1].update(extra)
                    row('create.'+role+'.accept',**extra);row('create.'+role+'.cancel',**extra)
        value=dict(createControlsVersion=2,open=source['tabletShown'],ready=True,scope=dict(instance=self.instance,generation=self.generation,
            sequence=self.sequence,elapsedMs=round(self.fixture.domain.time*1000),processId=42),controls=rows)
        return grammar.snapshot(value)
    def input(self,id_,action,reference,value=None):
        grammar.same_reference(reference,self.capture(),id_);self.sequence+=1;self.inputs.append((id_,action))
        if action=='replace':self.texts[id_]=value;return
        if action=='select-index':
            self.indexes[id_]=value
            if id_=='create.voxel.mode':self.product.page()['voxelSettings']['createAppMode']=['object','voxel'][value]
            return
        if action=='scroll':return
        self.focus=id_;p=self.product
        if id_=='tablet.home':
            if self.editor() is not None:p.close()
            self.mode='home'
        elif id_=='create.entry':p.open();self.mode='create';self.tab=p.page()['page']['tab']
        elif id_.startswith('create.tab.'):self.tab=int(id_.rsplit('.',1)[1]);p.page()['page']['tab']=self.tab
        elif id_ in ('create.new-shape','create.new-model'):
            p.create('cube' if id_=='create.new-shape' else 'model',resource=self.texts.get('create.resource',''))
            if p.page()['page']['selectedIds']:self.select(p.selected()['id'])
        elif id_.startswith('create.entity.'):self.select(id_[len('create.entity.'):])
        elif id_=='create.apply':
            p.selected()['name']=self.texts.get('create.name',p.selected()['name'])
            for kind in ('position','dimensions'):
                p.selected()[kind]=[float(self.texts.get('create.field.'+kind+'.'+axis,str(current))) for axis,current in zip('xyz',p.selected()[kind])]
        elif id_=='create.apply-typed':
            texture=json.loads(self.texts['create.textures'])['checker.png'];p.texture(p.selected()['id'],texture)
        elif id_=='create.delete':
            p.delete();search=self.texts.get('create.property-search','');self.texts={'create.property-search':search};self.tab=2
        elif id_=='create.import-browse':p.picker('import')
        elif id_=='create.export':p.picker('export')
        elif id_.startswith(('create.import.','create.export.')) and id_.endswith(('.accept','.cancel')):
            role=id_.split('.')[1];root=p.picker_state(role)['rootId']
            if id_.endswith('.accept'):
                from pathlib import Path
                path=Path(self.texts['create.'+role+'.filename'])
                if role=='import':
                    document=json.loads(path.read_text());p.create('model',resource=document['Entities'][0]['modelURL']);p.selected()['position']=[0,1,-3]
                else:
                    item=p.selected();row={key:deepcopy(item[key]) for key in ('id','name','type','modelURL','textures')};row['dimensions']=dict(zip('xyz',item['dimensions']))
                    path.write_text(json.dumps(dict(DataVersion=0,Entities=[row])))
            p.dismiss(role,root)
        elif id_=='create.detailed-open':self.polyvox=str(uuid.uuid4())
        elif id_=='create.polyvox.accept':p.create('voxel');self.polyvox=None;self.select(p.selected()['id'])
        elif id_=='create.polyvox.cancel':self.polyvox=None
        elif id_=='create.voxel.remove':p.page()['voxelSettings']['voxelRemove']=not p.page()['voxelSettings']['voxelRemove']
        elif id_=='create.voxel.apply':
            p.voxel_settings(mode=self.indexes.get('create.voxel.mode',0),shape=self.indexes.get('create.voxel.shape',0),
                dynamics=self.indexes.get('create.voxel.dynamics',0),pointer=self.indexes.get('create.voxel.pointer',0),remove=p.page()['voxelSettings']['voxelRemove'],
                diameter=float(self.texts['create.voxel.diameter']),reach=float(self.texts['create.voxel.reach']))
    def select(self,id_):
        self.product.select(id_);self.tab=2;self.product.page()['page']['tab']=2;item=self.product.selected();self.texts['create.name']=item['name']
        for kind in ('position','dimensions'):
            for axis,value in zip('xyz',item[kind]):self.texts['create.field.'+kind+'.'+axis]=str(value)
