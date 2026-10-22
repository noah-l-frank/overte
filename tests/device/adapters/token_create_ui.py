"""Normal Create controls on original native references; no entity-state verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_ui import NativeUIError

VERSION=1
UUID=r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
NONCE=r'(?:[0-9a-f]{32}|'+UUID+r')'
FIXED={'create.page','create.entry','create.host','create.import-host','create.resource','create.new-shape',
       'create.new-model','create.new-voxel','create.refresh','create.name','create.apply','create.delete',
       'create.undo','create.redo','create.import-url','create.import-submit','create.import-browse',
       'create.apply-typed','create.export','create.shape','create.filter','create.textures','create.scrollbar'}


def nonce(value):
    return type(value) is str and re.fullmatch(NONCE,value) is not None and value.replace('-','')!='0'*32


def navigation(identifier):
    return type(identifier) is str and (identifier=='tablet.home' or bool(re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',identifier)))


def control_id(identifier):
    if type(identifier) is not str:return False
    if identifier in FIXED or navigation(identifier):return True
    if re.fullmatch(r'create\.tab\.[0-4]',identifier):return True
    if re.fullmatch(r'create\.entity\.'+UUID,identifier):return nonce(identifier[len('create.entity.'):])
    return bool(re.fullmatch(r'create\.field\.(?:(?:position|rotation|dimensions)\.[xyz]|color\.(?:red|green|blue))',identifier))


def field(identifier):
    return identifier in {'create.name','create.resource','create.import-url','create.filter','create.textures'} or identifier.startswith('create.field.')


def choice(identifier):return identifier in {'create.host','create.import-host','create.shape'}


def ascii_text(value):
    need(type(value) is str and len(value)<=4096 and all(32<=ord(ch)<=126 for ch in value))
    return value


def scope(value):
    exact(value,{'instance','generation','sequence','elapsedMs','processId'})
    need(nonce(value['instance'])
         and (integer(value['generation']) or nonce(value['generation']))
         and integer(value['sequence']) and integer(value['elapsedMs']) and integer(value['processId'],1))
    return value


def metadata(row):
    need(type(row) is dict and control_id(row.get('id')) and nonce(row.get('token'))
         and type(row.get('enabled')) is bool)
    identifier=row['id'];base={'id','token','enabled'}
    if navigation(identifier):
        exact(row,base|({'focused'} if 'focused' in row else set())|({'inputReady'} if 'inputReady' in row else set()))
        need(all(type(row[k]) is bool for k in set(row)-base));return row
    base|={'focused','inputReady'}
    need(type(row.get('focused')) is bool and type(row.get('inputReady')) is bool)
    if identifier=='create.page':
        exact(row,base|{'profile','tab','selectedIds','statusError','statusText','componentSourceSha256'})
        need(row['profile']=='native-create-v1' and integer(row['tab'],0,4) and type(row['selectedIds']) is list
             and len(row['selectedIds'])<=256 and all(nonce(v) and re.fullmatch(UUID,v) for v in row['selectedIds'])
             and len(set(row['selectedIds']))==len(row['selectedIds']) and type(row['statusError']) is bool
             and type(row['statusText']) is str and len(row['statusText'])<=256
             and all(ord(c)>=32 and ord(c)!=127 for c in row['statusText'])
             and type(row['componentSourceSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['componentSourceSha256'])
             and row['inputReady'] is False)
    elif identifier=='create.scrollbar':
        exact(row,base|{'position','size'})
        need(all(type(row[k]) in (int,float) and math.isfinite(row[k]) for k in ('position','size'))
             and 0<=row['position']<=1 and 0<row['size']<=1 and row['position']+row['size']<=1.000001)
    elif field(identifier):exact(row,base|{'text'});ascii_text(row['text'])
    elif choice(identifier):
        exact(row,base|{'currentIndex','count'})
        need(integer(row['currentIndex']) and type(row['count']) is int and row['count']==(6 if identifier=='create.shape' else 2)
             and row['currentIndex']<row['count'])
    elif identifier.startswith('create.entity.'):
        exact(row,base|{'entityId'});need(row['entityId']==identifier[len('create.entity.'):])
    else:exact(row,base)
    return row


def snapshot(value):
    exact(value,{'createControlsVersion','open','ready','scope','controls'})
    need(type(value['createControlsVersion']) is int and value['createControlsVersion']==VERSION
         and all(type(value[k]) is bool for k in ('open','ready')) and type(value['controls']) is list and len(value['controls'])<=384)
    scope(value['scope']);seen=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in seen and row['token'] not in tokens);seen.add(row['id']);tokens.add(row['token'])
    need(value['open'] or not value['controls'])
    return value


def same_reference(original,current,identifier):
    """Backend admission before mutation; never silently retarget a new context."""
    snapshot(original);snapshot(current)
    need(all(original['scope'][key]==current['scope'][key] for key in ('instance','generation','sequence','processId'))
         and 0<=current['scope']['elapsedMs']-original['scope']['elapsedMs']<=5000)
    old=[row for row in original['controls'] if row['id']==identifier]
    new=[row for row in current['controls'] if row['id']==identifier]
    need(len(old)==len(new)==1 and old[0]==new[0])
    return old[0]


class TokenCreateUI:
    def __init__(self,io,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(callable(intent) and callable(monotonic) and callable(sleep))
        self.io,self.intent,self.monotonic,self.sleep=io,intent,monotonic,sleep
        self.last_clock=None;self.instance=None;self.pid=None;self.elapsed=0;self.sequence=0;self.generation=None

    def now(self):
        value=self.monotonic()
        need(type(value) in (int,float) and math.isfinite(value) and value>=0 and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def capture(self):
        value=deepcopy(snapshot(self.io.capture()));original=value['scope']
        need(self.instance in (None,original['instance']) and self.pid in (None,original['processId']) and original['elapsedMs']>=self.elapsed and original['sequence']>=self.sequence
             and (not (type(self.generation) is int and type(original['generation']) is int) or original['generation']>=self.generation))
        self.instance,self.pid,self.elapsed,self.sequence,self.generation=(original[k] for k in ('instance','processId','elapsedMs','sequence','generation'))
        return value

    @staticmethod
    def row(value,identifier,*,enabled=True):
        found=[r for r in value['controls'] if r['id']==identifier];need(len(found)<=1)
        return found[0] if found and (not enabled or found[0]['enabled'] and found[0].get('inputReady',True)) else None

    def page(self,value):
        row=self.row(value,'create.page',enabled=False);need(row is not None and value['open'] and value['ready']);return row

    def wait(self,predicate):
        deadline=self.now()+10
        for attempt in range(102):
            value=self.capture()
            if predicate(value):return value
            remaining=deadline-self.now()
            if remaining<=0 or attempt==101:break
            self.sleep(min(.1,remaining))
        raise NativeUIError('Normal Create control transition was not observed')

    def input(self,identifier,action='activate',value=None):
        need(control_id(identifier) and identifier!='create.page' and action in {'activate','replace','select-index','scroll'})
        if action=='scroll':need(identifier=='create.scrollbar' and value in ('up','down'))
        elif action=='activate':need(identifier!='create.scrollbar')
        if action=='replace':need(field(identifier));ascii_text(value)
        if action=='select-index':need(choice(identifier) and integer(value,0,31))
        before=self.capture();row=self.row(before,identifier);need(row is not None and before['open'] and before['ready'])
        if action=='replace':need(row['focused'])
        if action=='select-index':need(value<row['count'])
        self.intent(dict(createInputVersion=VERSION,action=action,controlId=identifier,controlToken=row['token'],scope=deepcopy(before['scope'])))
        if action=='activate':self.io.activate(identifier,reference=before)
        elif action=='replace':self.io.replace(identifier,value,reference=before)
        elif action=='select-index':self.io.select_index(identifier,value,reference=before)
        else:self.io.scroll(identifier,value,reference=before)
        after=self.capture()
        need(after['scope']['sequence']>before['scope']['sequence']) # Actual consumed native input, never an ACK cursor.
        return after

    def reveal(self,identifier):
        need(control_id(identifier))
        current=self.capture()
        if self.row(current,identifier):return current
        deadline=self.now()+10
        # Scan the actual visible ScrollView in both directions. Never set
        # contentY/position or manufacture an off-screen element reference.
        for direction in ('up','down'):
            for _ in range(32):
                if self.now()>=deadline:raise NativeUIError('Normal Create reveal timed out')
                before=self.capture()
                if self.row(before,identifier):return before
                bar=self.row(before,'create.scrollbar')
                if bar is None:break
                if direction=='up' and bar['position']<=.000001:break
                if direction=='down' and bar['position']+bar['size']>=.999999:break
                self.input('create.scrollbar','scroll',direction)
                observed=self.wait(lambda v:bool(self.row(v,'create.scrollbar') and
                    (self.row(v,'create.scrollbar')['position']<bar['position'] if direction=='up' else
                     self.row(v,'create.scrollbar')['position']>bar['position'])))
                if self.row(observed,identifier):return observed
        raise NativeUIError('Normal Create control could not be revealed')

    def replace(self,identifier,text):
        ascii_text(text);self.reveal(identifier);self.input(identifier)
        self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['focused']))
        self.input(identifier,'replace',text)
        self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['text']==text))

    def choose(self,identifier,index):
        need(choice(identifier) and integer(index,0,5));self.reveal(identifier);self.input(identifier)
        self.input(identifier,'select-index',index)
        self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['currentIndex']==index))

    def open_create(self):
        current=self.capture();need(current['open'] and current['ready'])
        if self.row(current,'tablet.home'):self.input('tablet.home')
        current=self.capture()
        pages=sorted((r['id'] for r in current['controls'] if navigation(r['id']) and r['id']!='tablet.home'),key=lambda v:int(v.rsplit('.',1)[1]))
        for page in [None,*pages]:
            if page is not None:self.input(page)
            until=self.now()+.6
            for _ in range(7):
                value=self.capture()
                if self.row(value,'create.entry'):
                    self.input('create.entry');self.wait_create();return
                remaining=until-self.now()
                if remaining<=0:break
                self.sleep(min(.1,remaining))
        raise NativeUIError('Normal Create entry is unavailable')

    def wait_create(self):self.wait(lambda value:value['open'] and value['ready'] and bool(self.row(value,'create.page',enabled=False)))
    def tab(self,index):
        need(integer(index,0,4));self.input('create.tab.'+str(index))
        self.wait(lambda value:self.page(value)['tab']==index)
    def create_cube(self):
        self.tab(0);self.choose('create.host',1);self.choose('create.shape',0)
        before=set(self.page(self.capture())['selectedIds']);self.reveal('create.new-shape');self.input('create.new-shape')
        self.wait(lambda value:self.page(value)['tab']==2 and len(self.page(value)['selectedIds'])==1
                  and self.page(value)['selectedIds'][0] not in before)
    def select_entity(self,identifier):
        need(type(identifier) is str and re.fullmatch(UUID,identifier.lower().strip('{}')))
        identifier=identifier.lower().strip('{}');self.tab(1);self.input('create.refresh')
        self.reveal('create.entity.'+identifier)
        self.input('create.entity.'+identifier)
        self.wait(lambda value:self.page(value)['selectedIds']==[identifier]);self.reveal('create.name')
    def name_entity(self,name):self.replace('create.name',name);self.reveal('create.apply');self.input('create.apply')
    def edit_properties(self,properties):
        from create_observation import properties as validate
        validate(properties)
        for group,values in properties.items():
            for component,value in values.items():self.replace('create.field.'+group+'.'+component,str(value))
        self.reveal('create.apply');self.input('create.apply')
    def delete_entity(self):
        need(len(self.page(self.capture())['selectedIds'])==1);self.reveal('create.delete');self.input('create.delete')
        self.wait(lambda value:self.page(value)['selectedIds']==[])
    def history(self,action):
        need(action in {'undo','redo'});self.input('create.'+action)
    def import_entities(self,url):
        from create_observation import owned_url
        owned_url(url,{'entities.json','missing.json'});self.tab(4);self.choose('create.import-host',1)
        self.replace('create.import-url',url);self.reveal('create.import-submit');self.input('create.import-submit')
