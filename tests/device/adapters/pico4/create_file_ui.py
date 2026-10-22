"""Ordinary Pico Create JSON/Save controls and original weak-root retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
import time
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact, integer, need
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import nonce, scope
from adapters.token_script_file_ui import file_url

VERSION = 1
IDS = frozenset('create-file.'+name for name in ('page','folder','name','accept','cancel'))
PROFILES = frozenset(('create-editor-v1','create-import-json-v1','create-export-json-v1'))


def component(value, suffix):
    need(type(value) is str and 1<=len(value)<=4096)
    parsed=urlsplit(value)
    need(parsed.scheme in ('file','qrc') and not parsed.netloc and not parsed.query and not parsed.fragment
         and parsed.path.endswith(suffix) and not any(ord(c)<32 for c in value))


def inventory(value):
    exact(value,{'inventoryVersion','instance','sequence','complete','roots','retiredRoots'})
    need(type(value['inventoryVersion']) is int and value['inventoryVersion']==VERSION
         and nonce(value['instance']) and integer(value['sequence'],1) and type(value['complete']) is bool
         and type(value['roots']) is list and len(value['roots'])<=16
         and type(value['retiredRoots']) is list and len(value['retiredRoots'])<=256)
    ids=[]
    for row in value['roots']:
        need(type(row) is dict and row.get('profile') in PROFILES)
        editor=row['profile']=='create-editor-v1'
        exact(row,{'id','profile','visible','inCurrentTree','componentSource'} | (set() if editor else {'closing','requestId'}))
        need(nonce(row['id']) and type(row['visible']) is bool and type(row['inCurrentTree']) is bool)
        component(row['componentSource'],'/system/create/qml/NativeCreate.qml' if editor else '/dialogs/NativeFileBrowser.qml')
        if not editor:
            need(type(row['closing']) is bool and type(row['requestId']) is str and len(row['requestId'])<=4096
                 and not any(ord(c)<32 for c in row['requestId']))
        ids.append(row['id'])
    retired=value['retiredRoots']
    need(ids==sorted(set(ids)) and retired==sorted(set(retired)) and all(nonce(v) for v in retired)
         and not set(ids)&set(retired) and (value['complete'] or not ids and not retired))
    return value


def metadata(row):
    need(type(row) is dict and row.get('id') in IDS and nonce(row.get('token')) and nonce(row.get('rootId'))
         and row.get('role') in ('import','export') and all(type(row.get(k)) is bool for k in ('enabled','focused','inputReady')))
    identifier=row['id'];fields={'id','token','rootId','role','enabled','focused','inputReady'}
    if identifier=='create-file.page':
        fields|={'caption','filter','directory','closing','requestId','errorText','componentSource'}
        need(row['inputReady'] is False and row.get('filter')=='*.json'
             and row.get('caption')==('Select .json to Import' if row['role']=='import' else 'Select Where to Save')
             and type(row.get('closing')) is bool)
        file_url(row['directory']);component(row['componentSource'],'/dialogs/NativeFileBrowser.qml')
        for key in ('requestId','errorText'):
            need(type(row[key]) is str and len(row[key])<=4096 and not any(ord(c)<32 for c in row[key]))
    elif identifier in ('create-file.folder','create-file.name'):
        fields.add('text');need(type(row.get('text')) is str and len(row['text'])<=4096
            and not any(ord(c)<32 for c in row['text']))
    exact(row,fields)
    return row


def project(original):
    need(type(original.get('createFileControlsVersion')) is int and original['createFileControlsVersion']==VERSION)
    value=dict(createFileControlsVersion=VERSION,open=original['open'],ready=original['ready'],
        scope=dict(instance=original['bridgeId'],generation=original['generation'],sequence=original['lastCommandSequence'],
            elapsedMs=original['elapsedMs'],processId=original['processId']),
        inventory=deepcopy(original['createUiInventory']),controls=deepcopy([r for r in original['controls'] if r['id'] in IDS]))
    return snapshot(value)


def snapshot(value):
    exact(value,{'createFileControlsVersion','open','ready','scope','inventory','controls'})
    need(type(value['createFileControlsVersion']) is int and value['createFileControlsVersion']==VERSION
         and type(value['open']) is bool and type(value['ready']) is bool and type(value['controls']) is list and len(value['controls'])<=5)
    scope(value['scope']);inventory(value['inventory'])
    ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token'])
    need(value['open'] or not value['controls'])
    return value


def same_reference(before,current,identifier):
    snapshot(before);snapshot(current)
    need(identifier in IDS and all(before['scope'][k]==current['scope'][k] for k in ('instance','generation','sequence','processId'))
         and 0<=current['scope']['elapsedMs']-before['scope']['elapsedMs']<=5000)
    previous=[r for r in before['controls'] if r['id']==identifier]
    latest=[r for r in current['controls'] if r['id']==identifier]
    need(len(previous)==len(latest)==1 and previous[0]==latest[0])
    old=[r for r in before['inventory']['roots'] if r['id']==previous[0]['rootId']]
    new=[r for r in current['inventory']['roots'] if r['id']==previous[0]['rootId']]
    need(before['inventory']['complete'] and current['inventory']['complete'] and old==new and len(old)==1
         and before['inventory']['instance']==current['inventory']['instance'] and current['inventory']['sequence']>=before['inventory']['sequence'])
    return previous[0]


def owned_path(value, identifier, role):
    need(identifier in ('create-file.folder','create-file.name') and role in ('import','export') and type(value) is str
         and len(value)<=4096 and '\\' not in value and not any(part in ('.','..') for part in value.split('/')))
    suffix='' if identifier=='create-file.folder' else '/entity-import.json' if role=='import' else '/export.json'
    need(re.fullmatch(r'/(?:[^/\x00-\x20]+/)*feature-create-[0-9a-f]{32}-[0-9a-f]{32}'+re.escape(suffix),value))
    return value


class PicoCreateFileIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def replace(self,identifier,text,*,reference):self.original.navigation.input(identifier,'replace',text,reference=reference)
    def submit(self,identifier,*,reference):self.original.navigation.input(identifier,'submit',reference=reference)


class CreateFileUI:
    def __init__(self,io,intent,directory,run,ticket,role,before,*,monotonic=time.monotonic,sleep=time.sleep):
        self.directory=file_url(directory)
        need(re.fullmatch('[0-9a-f]{32}',run) and re.fullmatch('[0-9a-f]{32}',ticket)
             and self.directory.endswith('/feature-create-'+run+'-'+ticket) and role in ('import','export')
             and callable(intent) and callable(monotonic) and callable(sleep))
        self.before=deepcopy(inventory(before));need(self.before['complete'])
        need(not any(row['profile']!='create-editor-v1' for row in before['roots']))
        need(len(before['roots'])==1 and before['roots'][0]['visible'] and before['roots'][0]['inCurrentTree'])
        self.editor=before['roots'][0]['id']
        self.io,self.intent,self.role,self.monotonic,self.sleep=io,intent,role,monotonic,sleep
        self.root=None;self.pending=None;self.last_clock=None;self.previous=None

    def now(self):
        value=self.monotonic();need(type(value) in (int,float) and math.isfinite(value)
            and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def capture(self):
        value=deepcopy(snapshot(self.io.capture()));observed=value['inventory'];need(observed['complete'])
        need(observed['instance']==self.before['instance'] and observed['sequence']>=self.before['sequence']
             and set(observed['retiredRoots'])>=set(self.before['retiredRoots']))
        if self.previous is not None:
            old=self.previous
            need(all(value['scope'][key]==old['scope'][key] for key in ('instance','generation','processId'))
                 and value['scope']['elapsedMs']>=old['scope']['elapsedMs'] and value['scope']['sequence']>=old['scope']['sequence']
                 and observed['sequence']>=old['inventory']['sequence']
                 and (observed['sequence']!=old['inventory']['sequence'] or observed==old['inventory']))
        self.previous=deepcopy(value);return value

    def page(self,value):
        found=[r for r in value['controls'] if r['id']=='create-file.page'];need(len(found)<=1)
        if not found:return None
        row=found[0];need(value['open'] and value['ready'] and row['role']==self.role)
        need(any(r['id']==self.editor and r['profile']=='create-editor-v1' and r['inCurrentTree'] for r in value['inventory']['roots']))
        oldids={r['id'] for r in self.before['roots']}|set(self.before['retiredRoots'])
        need(row['rootId'] not in oldids and self.root in (None,row['rootId'])
             and value['inventory']['sequence']>self.before['sequence'])
        new=[r for r in value['inventory']['roots'] if r['id'] not in oldids]
        need(len(new)==1 and new[0]['id']==row['rootId'] and new[0]['profile']=='create-'+self.role+'-json-v1'
             and new[0]['visible'] and new[0]['inCurrentTree'] and not row['closing'] and row['requestId']=='')
        self.root=row['rootId'];return row

    def input(self,identifier,action='activate',text=None):
        need(identifier in IDS and identifier!='create-file.page' and action in ('activate','replace','submit')
             and (self.pending is None or identifier=='create-file.cancel' and self.pending['controlId']!='create-file.cancel'))
        before=self.capture();page=self.page(before);need(page is not None)
        rows=[r for r in before['controls'] if r['id']==identifier];need(len(rows)==1)
        row=rows[0];need(row['enabled'] and row['inputReady'] and row['rootId']==page['rootId'] and row['role']==self.role)
        if action=='replace':
            owned_path(text,identifier,self.role);need(row['focused'] and text==self.directory+('' if identifier=='create-file.folder'
                else '/entity-import.json' if self.role=='import' else '/export.json'))
        elif action=='submit':need(identifier=='create-file.folder' and row['focused'] and text is None)
        else:need(text is None)
        original=dict(createFileInputVersion=VERSION,controlId=identifier,action=action,controlToken=row['token'],
            rootId=row['rootId'],role=self.role,scope=deepcopy(before['scope']),page=deepcopy(page))
        self.intent(deepcopy(original));self.pending=original
        if action=='activate':self.io.activate(identifier,reference=before)
        elif action=='replace':self.io.replace(identifier,text,reference=before)
        else:self.io.submit(identifier,reference=before)
        after=self.capture();need(after['scope']['sequence']>before['scope']['sequence'])
        self.pending=None;return after

    def wait(self,predicate):
        deadline=self.now()+10
        for attempt in range(102):
            value=self.capture()
            if predicate(value):return value
            remaining=deadline-self.now()
            if remaining<=0 or attempt==101:break
            self.sleep(min(.1,remaining))
        raise NativeUIError('Ordinary Create file transition did not produce original evidence')

    def wait_open(self):return self.wait(lambda value:self.page(value) is not None)

    def accept(self):
        self.wait_open();self.input('create-file.name')
        self.wait(lambda value:any(r['id']=='create-file.name' and r['focused'] for r in value['controls']))
        text=self.directory+('/entity-import.json' if self.role=='import' else '/export.json')
        self.input('create-file.name','replace',text)
        self.wait(lambda value:any(r['id']=='create-file.name' and r['text']==text for r in value['controls']))
        self.input('create-file.accept');return self.retired()

    def cancel(self):
        self.wait_open();self.input('create-file.cancel');return self.retired()

    def retired(self):
        need(self.root is not None);start=self.now();quiet=None;last=0
        original_ids={row['id'] for row in self.before['roots']}
        retired_ids=set(self.before['retiredRoots'])|original_ids|{self.root}
        for attempt in range(132):
            value=self.capture();observed=value['inventory'];sequence=observed['sequence']
            absent=not any(r['id']==self.root for r in observed['roots']) and self.root in observed['retiredRoots']
            if absent:
                need({row['id'] for row in observed['roots']}<=original_ids and set(observed['retiredRoots'])<=retired_ids
                     and any(row['id']==self.editor and row['inCurrentTree'] for row in observed['roots']))
            if absent and sequence>last:
                quiet=self.now() if quiet is None else quiet
                if self.now()-quiet>=3:return value
            else:quiet=None
            last=sequence
            need(self.now()-start<13 and attempt<131)
            self.sleep(.1)
        need(False)
