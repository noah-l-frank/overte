"""Original cumulative WK document/input/Qt bridge transcript, never an ACK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
from adapters.native_clock_join import digest
import json
import re
import time
from urllib.parse import urlsplit,urlunsplit
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from ios.adapters.places_model import text,tree as json_tree
from ios.adapters import world_web_event_prefix as event_prefix

VERSION=3
READS=(1,2,3)
ACTION='feature-ios-world-web'
FILE=ACTION+'.json'
LEGACY_LIMIT=1048576
LIMIT=2097152
HEX=r'[0-9a-f]{32}'
SIGNALS={'key-enter','native-envelope','script-delivery','page-reply','script-event-slot'}
CALLS={'evaluation-enter','pointer-enter','dom-read-enter'}
KINDS=SIGNALS|CALLS|{'callback-enter','callback-return','signal-return','view-created','view-teardown',
    'owner-destroyed','document-began','main-response','native-finished','document-verified','dom-observer-installed'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','fixtureUrl'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-'+HEX,value['commandId'])
        and type(value['runId']) is str and re.fullmatch(HEX,value['runId']))
    raw=text(value['fixtureUrl'],512);parsed=urlsplit(raw);parsed.port
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is parsed.password is None
        and not parsed.query and not parsed.fragment and not any(ord(c)<=32 or ord(c)==127 for c in raw)
        and parsed.path=='/feature-fixture/v1/runs/'+value['runId']+'/' and urlunsplit(parsed)==raw)
    return value


def identity(value,query):
    exact(value,{'handle','creation','grant','page','nonce','url','sourceUrl','sourceIdentity','surface'})
    need(type(value['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',value['handle'])
        and all(integer(value[k]) for k in ('creation','grant','page')) and value['surface']=='world-entity')
    for key in ('url','sourceUrl'):text(value[key],131072)
    text(value['sourceIdentity'],512);need(value['sourceIdentity'])
    need(type(value['nonce']) is str and (value['nonce']=='' or re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['nonce'])))
    prefix=query['fixtureUrl']+'tickets/'
    need(value['sourceUrl'].startswith(prefix) and re.fullmatch(HEX+r'/(?:index|reference)\.html',value['sourceUrl'][len(prefix):]))
    return value


def document_key(value):
    return tuple(value[key] for key in ('handle','creation','grant','page','nonce'))


def detail(event,earlier):
    kind=event['kind'];value=event['detail'];need(type(value) is dict)
    if kind in {'view-created','view-teardown','owner-destroyed','native-finished','document-verified'}:exact(value,set())
    elif kind=='document-began':exact(value,{'frame'});text(value['frame'],131072)
    elif kind=='main-response':
        exact(value,{'url','status','responseId','mimeType'});text(value['url'],131072);text(value['mimeType'],256)
        need(integer(value['status'],100,599) and type(value['responseId']) is str
            and (value['responseId']=='' or re.fullmatch(HEX,value['responseId'])))
    elif kind=='pointer-enter':
        exact(value,{'type','x','y','width','height','button','codeSha256'})
        need(value['type'] in ('press','release','move') and integer(value['button'],0,2)
            and all(number(value[key],.001,100000) for key in ('width','height'))
            and number(value['x'],0,value['width']) and number(value['y'],0,value['height'])
            and re.fullmatch('[0-9a-f]{64}',text(value['codeSha256'],64)))
    elif kind=='evaluation-enter':
        exact(value,{'codeSha256'});need(re.fullmatch('[0-9a-f]{64}',text(value['codeSha256'],64)))
    elif kind=='dom-read-enter':
        exact(value,{'requestId'});need(re.fullmatch('ios-'+HEX,text(value['requestId'],36)))
    elif kind=='dom-observer-installed':
        exact(value,{'sourceSha256','wrapperSha256'})
        need(all(re.fullmatch('[0-9a-f]{64}',text(value[key],64)) for key in value))
    elif kind=='key-enter':
        exact(value,{'text','key','modifiers'});text(value['text'],8192)
        need(integer(value['key'],0,2**31-1) and integer(value['modifiers'],0,2**31-1))
    elif kind=='native-envelope':
        exact(value,{'envelope','documentNonce','frame','mainFrame'})
        for key in ('envelope','documentNonce','frame'):text(value[key],32768)
        need(type(value['mainFrame']) is bool)
    elif kind in ('script-delivery','page-reply'):
        exact(value,{'message'});json_tree(value['message'])
    elif kind=='script-event-slot':
        exact(value,{'message','active'});json_tree(value['message']);need(type(value['active']) is bool)
    else:
        fields={'entry','result'} if kind=='callback-enter' else {'entry'};exact(value,fields)
        need(integer(value['entry'],1,event['sequence']-1) and value['entry'] in earlier)
        original=earlier[value['entry']]
        need(original['identity']==event['identity'] and original['kind'] in (CALLS if kind.startswith('callback') else SIGNALS))
        if kind=='callback-enter':
            result=value['result'];expected={'error','result'} if original['kind']=='pointer-enter' else {'error'}
            exact(result,expected);need(type(result['error']) is bool)
            if 'result' in result:json_tree(result['result'])


_VALIDATION=ContextVar('overte_world_web_transcript_validation',default=None)


@contextmanager
def validation_round():
    """Synchronous pure validation reuse, never original bytes/file reuse."""
    if _VALIDATION.get() is not None:
        yield;return
    token=_VALIDATION.set(set())
    try:
        with event_prefix.scope():yield
    finally:_VALIDATION.reset(token)


def validate(value,query,pid,epoch=None,previous=None):
    proofs=_VALIDATION.get();proof=None
    if proofs is not None:
        try:proof=digest([value,query,pid,previous])
        except (TypeError,ValueError,OverflowError):pass
        if proof is not None and proof in proofs:
            if epoch is not None:fresh(value['clockAfter']['epochMs'],epoch)
            return value
    command(query)
    exact(value,{'iosWorldWebVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','complete','eventSequence','events'})
    need(type(value['iosWorldWebVersion']) is int and value['iosWorldWebVersion'] in READS
        and all(value[key]==query[key] for key in ('commandId','runId','fixtureUrl'))
        and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
        and integer(value['sequence'],1) and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and value['clockDomain']=='native-main-ios-world-web' and type(value['complete']) is bool
        and integer(value['eventSequence'],0) and type(value['events']) is list and len(value['events'])<=(4096 if value['iosWorldWebVersion']>=3 else 2048))
    # Historical original writers keep their original byte bound. The live
    # v3 writer alone supplies the measured full-callback journey capacity.
    bound=LIMIT if value['iosWorldWebVersion']>=3 else LEGACY_LIMIT
    need(len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8'))<=bound)
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    a,b=value['clockBefore'],value['clockAfter'];utc=b['epochMs']-a['epochMs'];mono=b['monotonicMs']-a['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    earlier={};ids=set();last_epoch=last_mono=last_sequence=0;callback_enter=set();callback_return=set();signal_return=set();offset=0
    prefix=event_prefix.start(value)
    if prefix is not None:
        offset,earlier,ids,last,callback_enter,callback_return,signal_return=prefix
        last_epoch,last_mono,last_sequence=last
    for event in value['events'][offset:]:
        exact(event,{'sequence','eventId','kind','clock','identity','detail'})
        need(integer(event['sequence'],last_sequence+1,value['eventSequence']) and type(event['eventId']) is str
            and re.fullmatch(HEX,event['eventId']) and event['eventId'] not in ids and event['kind'] in KINDS)
        ids.add(event['eventId']);identity(event['identity'],query)
        clock=event['clock'];exact(clock,{'epochMs','monotonicMs'})
        need(integer(clock['epochMs'],max(1,last_epoch),a['epochMs']) and integer(clock['monotonicMs'],last_mono,a['monotonicMs']))
        if last_epoch:need(abs(clock['epochMs']-last_epoch-clock['monotonicMs']+last_mono)<=250)
        last_epoch,last_mono,last_sequence=clock['epochMs'],clock['monotonicMs'],event['sequence'];detail(event,earlier)
        if event['kind'] in ('callback-enter','callback-return','signal-return'):
            entry=event['detail']['entry'];collection=callback_enter if event['kind']=='callback-enter' else callback_return if event['kind']=='callback-return' else signal_return
            need(entry not in collection);collection.add(entry)
            if event['kind']=='callback-return':need(entry in callback_enter)
        earlier[event['sequence']]=event
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(value['iosWorldWebVersion']==previous['iosWorldWebVersion'] and value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['eventSequence']>=previous['eventSequence']
            and a['epochMs']>=previous['clockAfter']['epochMs'] and a['monotonicMs']>=previous['clockAfter']['monotonicMs']
            and (previous['complete'] or not value['complete'])
            and same(value['events'][:len(previous['events'])],previous['events']))
    event_prefix.remember(value,earlier,ids,(last_epoch,last_mono,last_sequence),callback_enter,callback_return,signal_return)
    if proof is not None and len(proofs)<256:proofs.add(proof)
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def pending(value):
    original(value);need(value['complete'])
    calls={row['sequence'] for row in value['events'] if row['kind'] in CALLS|SIGNALS}
    ended={row['detail']['entry'] for row in value['events'] if row['kind'] in ('callback-return','signal-return')}
    return sorted(calls-ended)


def completed_documents(value):
    original(value);need(value['complete']);documents={};created=set();closed=set();result=[]
    for event in value['events']:
        item=event['identity'];key=document_key(item);view=key[:2];kind=event['kind']
        if kind=='view-created':need(view not in created);created.add(view)
        elif kind=='view-teardown':closed.add(view)
        elif kind=='document-began':
            need(view in created and view not in closed and key not in documents and all(item[k] for k in ('creation','grant','page','nonce')))
            documents[key]=dict(begin=event,response=None,finished=None,verified=None)
        elif kind in ('main-response','native-finished','document-verified'):
            need(key in documents and view not in closed);document=documents[key]
            if kind=='main-response':document['response']=event
            elif kind=='native-finished':document['finished']=event
            else:
                response,finished=document['response'],document['finished']
                need(response is not None and finished is not None and document['begin']['sequence']<response['sequence']<=finished['sequence']<event['sequence']
                    and response['detail']['responseId'] and response['detail']['url']==finished['identity']['url']==item['url'])
                if document['verified'] is None:
                    result.append(dict(identity=deepcopy(item),response=deepcopy(response),finished=deepcopy(finished),verified=deepcopy(event)))
                    document['verified']=event
    return result


class IOSWorldWebSource:
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
    @staticmethod
    def _bounds(value):return value['clockBefore']['epochMs'],value['clockAfter']['epochMs']
    @staticmethod
    def _ready(value):need(value['complete']);return True
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None
    def read(self,run,fixture_url,*,native_before_floor=None):
        try:
            native_before_floor=deepcopy(native_before_floor)
            query=self._command(dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action=self._action,runId=run,fixtureUrl=fixture_url))
            start=last=self.monotonic();need(number(start,0,1e15) and self.guard() is not False)
            if native_before_floor is None:before=self.clock_ms()
            else:
                from adapters.native_feature_observation import validate as native_floor
                native_floor(native_before_floor,native_before_floor['requestId'],self.pid,native_before_floor['capturedEpochMs'])
                before=native_before_floor['capturedEpochMs']
            need(integer(before,1));self.send(query)
            for attempt in range(16):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=self._limit)
                try:value=decode(raw,limit=self._limit) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,last,1e15) and now-start<1.5);last=now
                if type(value) is dict and value.get('commandId')==query['commandId']:
                    after=self.clock_ms();need(integer(after,before));self._validate(value,query,self.pid,after,self.last)
                    if self._ready(value):
                        earliest,latest=self._bounds(value);need(before<=earliest<=latest<=after)
                        need(self.guard() is not False);final=self.monotonic();need(number(final,last,1e15) and final-start<1.5)
                        final_epoch=self.clock_ms();need(integer(final_epoch,after));fresh(latest,final_epoch)
                        if native_before_floor is not None:need(final_epoch-before<1500)
                        need(self.guard() is not False);end=self.monotonic();need(number(end,final,1e15) and end-start<1.5)
                        self.last=deepcopy(value);return value
                if attempt<15:self.sleep(.1)
        except Exception:raise NativeUIError('Original iOS world Web transcript is unavailable or invalid') from None
        raise NativeUIError('Original iOS world Web transcript is unavailable or invalid')
