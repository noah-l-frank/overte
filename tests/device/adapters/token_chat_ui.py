"""Original normal Chat input references; no UI/delivery/keyboard verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import nonce,navigation,scope
from feature_journeys.fixtures import context

VERSION=2
FIXED={'chat.page','chat.entry','chat.input','chat.send','chat.close','chat.local','chat.domain','chat.settings','chat.erase'}


def control_id(value):return type(value) is str and (value in FIXED or navigation(value))


def text(value):
    need(type(value) is str and (value=='' or re.fullmatch(r'(?:Overte ä Ω 東京 |(?:reply|hidden|retry)-)[0-9a-f]{32}',value)))
    return value


def metadata(value):
    need(type(value) is dict and control_id(value.get('id')) and nonce(value.get('token'))
         and type(value.get('enabled')) is bool)
    base={'id','token','enabled'};identifier=value['id']
    if navigation(identifier):
        exact(value,base|({'focused'} if 'focused' in value else set())|({'inputReady'} if 'inputReady' in value else set()))
        need(all(type(value[k]) is bool for k in set(value)-base));return value
    base|={'focused','inputReady'}
    need(type(value.get('focused')) is bool and type(value.get('inputReady')) is bool)
    if identifier=='chat.page':
        exact(value,base|{'profile','channel','keyboardRequested','localRowCount','domainRowCount','componentSourceSha256'})
        need(value['profile']=='armored-chat-native-v1' and value['channel'] in ('local','domain','settings')
             and type(value['keyboardRequested']) is bool and all(integer(value[k],0,1000) for k in ('localRowCount','domainRowCount'))
             and type(value['componentSourceSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['componentSourceSha256'])
             and value['inputReady'] is False)
    elif identifier=='chat.input':exact(value,base|{'text'});text(value['text'])
    elif identifier=='chat.erase':
        exact(value,base|{'historySha256'})
        need(type(value['historySha256']) is str and re.fullmatch('[0-9a-f]{64}',value['historySha256']))
    else:exact(value,base)
    return value


def snapshot(value):
    exact(value,{'chatControlsVersion','open','ready','scope','controls'})
    need(type(value['chatControlsVersion']) is int and value['chatControlsVersion'] in (1,VERSION)
         and all(type(value[k]) is bool for k in ('open','ready')) and type(value['controls']) is list and len(value['controls'])<=64)
    scope(value['scope']);ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
        if row['id'] in ('chat.settings','chat.erase'):need(value['chatControlsVersion']==2)
    need(value['open'] or not value['controls'])
    return value


def same_reference(original,current,identifier):
    snapshot(original);snapshot(current)
    need(original['chatControlsVersion']==current['chatControlsVersion']
         and all(original['scope'][k]==current['scope'][k] for k in ('instance','generation','sequence','processId'))
         and 0<=current['scope']['elapsedMs']-original['scope']['elapsedMs']<=5000)
    old=[r for r in original['controls'] if r['id']==identifier];new=[r for r in current['controls'] if r['id']==identifier]
    need(len(old)==len(new)==1 and old[0]==new[0])
    # Native tokens also bind original draft/channel/focus. Check the original
    # page and editor rows here so no backend may recapture a changed draft and
    # deliver a captured Send/Return to a replacement input state.
    for key in ('chat.page','chat.input'):
        need([r for r in original['controls'] if r['id']==key]==[r for r in current['controls'] if r['id']==key])
    return old[0]


class TokenChatUI:
    def __init__(self,io,intent,run,*,monotonic=time.monotonic,sleep=time.sleep):
        need(callable(intent) and callable(monotonic) and callable(sleep) and type(run) is str and re.fullmatch('[0-9a-f]{32}',run))
        self.io,self.intent,self.run=io,intent,run;self.monotonic,self.sleep=monotonic,sleep
        self.last_clock=None;self.instance=None;self.pid=None;self.sequence=0;self.elapsed=0;self.generation=None
        self.version=1
        self.erase_issued=False

    def now(self):
        from adapters.native_feature_observation import number
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def capture(self):
        value=deepcopy(snapshot(self.io.capture()));actual=value['scope']
        need(value['chatControlsVersion']>=self.version and self.instance in (None,actual['instance']) and self.pid in (None,actual['processId'])
             and actual['elapsedMs']>=self.elapsed and actual['sequence']>=self.sequence
             and (not (type(self.generation) is int and type(actual['generation']) is int) or actual['generation']>=self.generation))
        for row in value['controls']:
            if row['id']=='chat.input':need(row['text']=='' or row['text'] in self.allowed())
        self.instance,self.pid,self.sequence,self.elapsed,self.generation=(actual[k] for k in ('instance','processId','sequence','elapsedMs','generation'))
        self.version=value['chatControlsVersion']
        return value

    def allowed(self):return {context(self.run)[k] for k in ('unicode','reply','hidden','retry')}

    @staticmethod
    def row(value,identifier,*,enabled=True):
        found=[r for r in value['controls'] if r['id']==identifier];need(len(found)<=1)
        return found[0] if found and (not enabled or found[0]['enabled'] and found[0].get('inputReady',True)) else None

    def page(self,value):
        page=self.row(value,'chat.page',enabled=False);need(value['open'] and value['ready'] and page is not None);return page

    def wait(self,predicate):
        deadline=self.now()+10
        for attempt in range(102):
            current=self.capture()
            if predicate(current):return current
            remaining=deadline-self.now()
            if remaining<=0 or attempt==101:break
            self.sleep(min(.1,remaining))
        raise NativeUIError('Normal Chat control transition was not observed')

    def input(self,identifier,action='activate',value=None,*,reference=None):
        need(identifier!='chat.erase')  # Destructive input has its own admission recipe.
        return self._input(identifier,action,value,reference=reference)

    def _input(self,identifier,action='activate',value=None,*,reference=None):
        need(control_id(identifier) and identifier!='chat.page' and action in ('activate','replace','submit'))
        if action=='replace':need(identifier=='chat.input' and (value=='' or value in self.allowed()));text(value)
        elif action=='submit':need(identifier=='chat.input' and value is None)
        else:need(value is None)
        current=self.capture()
        if reference is None:original=current
        else:same_reference(reference,current,identifier);original=deepcopy(reference)
        row=self.row(original,identifier)
        need(original['open'] and original['ready'] and row is not None)
        if action in ('replace','submit'):need(row['focused'])
        scope_value=original['scope']
        self.intent(dict(controlId=identifier,action=action,instance=scope_value['instance'],generation=scope_value['generation'],
                         sequence=scope_value['sequence']+1))
        # Never retry an uncertain input or pass text through a journal.
        method={'activate':'activate','replace':'replace','submit':'submit'}[action]
        callback=getattr(self.io,method)
        if action=='replace':callback(identifier,value,reference=original)
        else:callback(identifier,reference=original)
        consumed=self.capture()['scope']
        need(consumed['sequence']==scope_value['sequence']+1 and consumed['instance']==scope_value['instance']
             and consumed['processId']==scope_value['processId'])
        return original

    def open(self):
        current=self.capture();need(current['open'] and current['ready'])
        if self.row(current,'chat.page',enabled=False) is None:
            if self.row(current,'chat.entry') is None:
                self.input('tablet.home')
                self.wait(lambda v:self.row(v,'chat.entry') is not None)
            self.input('chat.entry');self.wait(lambda v:self.row(v,'chat.page',enabled=False) is not None)
        self.page(self.capture())

    def type(self,value):
        need(value in self.allowed());self.page(self.capture())
        self.input('chat.input');self.wait(lambda v:(self.row(v,'chat.input') or {}).get('focused') is True)
        self.input('chat.input','replace',value)
        self.wait(lambda v:(self.row(v,'chat.input') or {}).get('text')==value)

    def select_channel(self,value):
        need(value in ('local','domain'))
        if self.page(self.capture())['channel']==value:return
        self.input('chat.'+value)
        self.wait(lambda v:self.page(v)['channel']==value)

    def send(self,*,enter=False):
        need(type(enter) is bool);current=self.capture();self.page(current)
        editor=self.row(current,'chat.input',enabled=False);need(editor is not None and editor['text'] in self.allowed())
        if enter:self.input('chat.input','submit')
        else:self.input('chat.send')
        self.wait(lambda v:(self.row(v,'chat.input') or {}).get('text')=='')
        # Editor clearing is an input effect only. The feature verdict still
        # needs actual UI/storage history and original independent peer receipt.

    def close(self):
        current=self.capture()
        if self.row(current,'chat.page',enabled=False) is None:return
        self.input('chat.close')
        self.wait(lambda v:self.row(v,'chat.page',enabled=False) is None)

    def erase_history(self,authorize):
        """Normal Erase only after the whole owner independently admits it.

        authorize must qualify this captured original model digest against its
        owned run/profile and actual storage. No generic Erase or settings write
        can adopt unowned content, and a changed digest cannot be recaptured.
        """
        need(callable(authorize) and not self.erase_issued);current=self.capture();need(current['chatControlsVersion']==2)
        self.page(current)
        editor=self.row(current,'chat.input',enabled=False);need(editor is None or editor['text']=='')
        if self.page(current)['channel']!='settings':
            self.input('chat.settings');self.wait(lambda v:self.page(v)['channel']=='settings')
        original=self.capture();need(self.row(original,'chat.erase') is not None and authorize(deepcopy(original)) is True)
        self.erase_issued=True
        self._input('chat.erase',reference=original)
        self.wait(lambda v:all(self.page(v)[key]==0 for key in ('localRowCount','domainRowCount')))
        # Independent actual storage and ordinary close/reopen history must be
        # checked by the owner; zero visible rows alone never retire ownership.
