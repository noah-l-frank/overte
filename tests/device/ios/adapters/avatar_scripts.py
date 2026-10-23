"""Original evaluated Avatar/People code and actual protocol timer lifetimes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re

from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.native_script_membership import validate as membership, accept as accept_membership
from adapters.native_script_observation import validate_code
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_state import identity
from ios.adapters.places_http import installed
from ios.adapters.places_model import IOSPlacesModel

VERSION=2
READS=(1,2)
ACTION='feature-ios-avatar-scripts'
FILE=ACTION+'.json'
LIMIT=262144
SUFFIXES=('/system/avatarapp.js','/system/pal.js','/system/libraries/peopleConnection.js','/modules/request.js','/system/request-service.js')
SHA=re.compile('[a-f0-9]{64}\\Z')


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    identity(value['runId']);return value


def code_source(value):
    need(type(value) is str and any(value.endswith(suffix) for suffix in SUFFIXES))
    installed(value,next(suffix for suffix in SUFFIXES if value.endswith(suffix)));return value


def code_projection(source,after_epoch):
    """Validate actual code-only projection; no fabricated empty timer ledger."""
    exact(source,{'avatarScriptVersion','instance','complete','code'})
    need(type(source['avatarScriptVersion']) is int and source['avatarScriptVersion'] in READS and identity(source['instance'])
         and type(source['complete']) is bool and type(source['code']) is list and len(source['code'])<=128)
    last=0
    for sequence,code in enumerate(source['code'],1):
        exact(code,{'sequence','url','submittedEpochMs','encoding','codeUnits','sha256'})
        need(type(code['sequence']) is int and code['sequence']==sequence and integer(code['submittedEpochMs'],max(1,last),after_epoch)
             and code['encoding']=='utf-16le-code-units' and integer(code['codeUnits'],1,4194304)
             and type(code['sha256']) is str and SHA.fullmatch(code['sha256']))
        code_source(code['url']);last=code['submittedEpochMs']
    return source


def timer_states(source, after_epoch):
    version=source.get('avatarScriptVersion') if type(source) is dict else None
    exact(source,{'avatarScriptVersion','instance','complete','code','events'}|({'callerStacks'} if version==2 else set()))
    code_projection({key:source[key] for key in ('avatarScriptVersion','instance','complete','code')},after_epoch)
    need(type(source['events']) is list and len(source['events'])<=2048)
    from ios.adapters import avatar_call_stack
    caller_table=avatar_call_stack.table(source['callerStacks'],after_epoch,single_engine=True) if version==2 else {}
    used_callers=set();stack_history=avatar_call_stack.History();states={};handles={};last=0
    for sequence,event in enumerate(source['events'],1):
        exact(event,{'sequence','timerId','kind','capturedEpochMs','details'})
        need(type(event['sequence']) is int and event['sequence']==sequence and identity(event['timerId'])
             and integer(event['capturedEpochMs'],max(1,last),after_epoch))
        last=event['capturedEpochMs'];key=event['timerId'];kind=event['kind'];detail=event['details']
        if kind=='created':
            exact(detail,{'handle','active','singleShot','intervalMs','remainingMs'}|
                ({'callerChain'} if version==1 else {'callerStackId'}))
            need(key not in states and len(states)<256 and integer(detail['handle'],1,2**31-1)
                 and detail['handle'] not in handles)
            if version==1:
                chain=detail['callerChain'];need(type(chain) is list and 1<=len(chain)<=32
                    and any(type(caller) is str and caller.endswith('/system/libraries/peopleConnection.js') for caller in chain))
                for caller in chain:
                    need(type(caller) is str and len(caller)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in caller))
                    if caller.endswith('/system/libraries/peopleConnection.js'):installed(caller,'/system/libraries/peopleConnection.js')
            else:
                identity(detail['callerStackId']);need(detail['callerStackId'] in caller_table);actual=caller_table[detail['callerStackId']]
                need(actual['callerModules'])
                avatar_call_stack.evaluated(actual['callerStack'],actual['callerModules'],event['capturedEpochMs'],source['code'])
                stack_history.accept(actual['callerStack']);used_callers.add(actual['id'])
            need(type(detail['active']) is bool and type(detail['singleShot']) is bool
                 and integer(detail['intervalMs'],-2**31,2**31-1) and integer(detail['remainingMs'],-1,2**31-1)
                 and (detail['remainingMs']>=0 if detail['active'] else detail['remainingMs']==-1))
            states[key]=dict(created=deepcopy(event),destroyed=False,fired=0,entered=0,depth=0)
            handles[detail['handle']]=key;continue
        need(key in states);state=states[key]
        if kind=='fired':
            exact(detail,{'active','remainingMs'})
            need(not state['destroyed'] and type(detail['active']) is bool and integer(detail['remainingMs'],-1,2**31-1)
                 and (detail['remainingMs']>=0 if detail['active'] else detail['remainingMs']==-1))
            state['fired']+=1
        elif kind in ('callback-enter','callback-leave'):
            exact(detail,set())
            if kind=='callback-enter':
                need(state['entered']<state['fired'] and state['depth']<16);state['entered']+=1;state['depth']+=1
            else:need(state['depth']>0);state['depth']-=1
        elif kind=='destroyed':
            exact(detail,set());need(not state['destroyed']);state['destroyed']=True
            del handles[state['created']['details']['handle']]
        else:need(False)
    if version==2 and source['complete']:need(used_callers==set(caller_table))
    return states


def members(source):
    return dict(complete=source['complete'],revision=source['revision'],managers=[row['membership'] for row in source['workers']])


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAvatarScriptsVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    version=value['iosAvatarScriptsVersion']
    need(type(version) is int and version in READS
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and identity(value['instance'])
         and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
         and integer(value['sequence'],1,1000000000) and value['clockDomain']=='native-main-avatar-scripts')
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','revision','workers'})
    need(source['complete'] is True and integer(source['revision'],0,9007199254740991)
         and type(source['workers']) is list and len(source['workers'])<=128)
    ids=[];births=set();membership(members(source),after['epochMs'])
    for worker in source['workers']:
        exact(worker,{'membership','code','running','stopping','finished','done','avatar'}|({'uiWork'} if 'uiWork' in worker else set()))
        for key in ('running','stopping','finished','done'):need(type(worker[key]) is bool)
        validate_code(worker['code'],after['epochMs']);timer_states(worker['avatar'],after['epochMs'])
        need(worker['avatar']['avatarScriptVersion']==version)
        if 'uiWork' in worker:
            from ios.adapters.avatar_ui_work import validate as ui_work
            ui_work(worker['uiWork'],after['epochMs'])
            need(worker['uiWork']['avatarUiWorkVersion']==version)
        ids.append(worker['membership']['instance']);birth=worker['avatar']['instance'];need(birth not in births);births.add(birth)
    need(ids==sorted(set(ids)) and len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
             and version==previous['iosAvatarScriptsVersion']
             and value['requestId']!=previous['requestId'] and value['runId']==previous['runId']
             and all(before[key]>=previous['clockAfter'][key] for key in before))
        accept_membership(members(previous['source']),members(source),set(),after['epochMs'])
        old={row['membership']['instance']:row for row in previous['source']['workers']}
        for row in source['workers']:
            prior=old.get(row['membership']['instance'])
            if prior is None:continue
            need(row['avatar']['instance']==prior['avatar']['instance'])
            if prior['code']['submitted']:need(row['code']==prior['code'])
            for key in ('code','events')+(('callerStacks',) if version==2 else ()):
                original=prior['avatar'][key];need(len(row['avatar'][key])>=len(original) and row['avatar'][key][:len(original)]==original)
            if version==2:
                for event in row['avatar']['events'][len(prior['avatar']['events']):]:
                    need(event['capturedEpochMs']>=previous['clockBefore']['epochMs'])
            need(prior['avatar']['complete'] or not row['avatar']['complete'])
            if 'uiWork' in prior:
                need('uiWork' in row)
                from ios.adapters.avatar_ui_work import validate as ui_work
                ui_work(row['uiWork'],after['epochMs'],prior['uiWork'])
                if version==2:
                    old_ids={timer['timerId'] for timer in prior['uiWork']['timers']}
                    for timer in row['uiWork']['timers']:
                        if timer['timerId'] not in old_ids:need(timer['createdEpochMs']>=previous['clockBefore']['epochMs'])
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def worker(value,manager_id):
    original(value);identity(manager_id)
    rows=[row for row in value['source']['workers'] if row['membership']['instance']==manager_id];need(len(rows)==1)
    row=rows[0];need(row['membership']['assigned'] and row['code']['submitted'] and row['avatar']['complete']
        and row['running'] and not any(row[key] for key in ('stopping','finished','done')))
    return deepcopy(row)


def drained(value,manager_ids):
    original(value);need(type(manager_ids) is set and manager_ids)
    for manager_id in manager_ids:
        selected=worker(value,manager_id)
        if not all(state['destroyed'] and state['depth']==0 for state in timer_states(selected['avatar'],value['clockAfter']['epochMs']).values()):return False
    return True


def bound_code(value,manager_id,expected):
    """Compare actually submitted originals with a separately bound source map.

    The trusted caller must obtain expected UTF16 identities from its candidate
    source manifest. Native records are never used to generate that manifest.
    """
    selected=worker(value,manager_id)
    need(type(expected) is dict and expected and set(expected)<=set(SUFFIXES))
    for source in expected.values():
        exact(source,{'codeUnits','sha256'})
        need(integer(source['codeUnits'],1,4194304) and type(source['sha256']) is str and SHA.fullmatch(source['sha256']))
    found={};urls={}
    for code in selected['avatar']['code']:
        suffix=next(suffix for suffix in SUFFIXES if code['url'].endswith(suffix))
        need(suffix in expected and code['codeUnits']==expected[suffix]['codeUnits'] and code['sha256']==expected[suffix]['sha256'])
        need(suffix not in urls or urls[suffix]==code['url']);urls[suffix]=code['url']
        found.setdefault(suffix,[]).append(deepcopy(code))
    need(set(found)==set(expected));return found


def join_http_code(value,http_value,consumption,expected,*,require_actual=False):
    """Join actual XHR caller to actual compiled module bytes and manager birth."""
    from ios.adapters import avatar_social_http as http
    original(value);http.original(http_value);need(type(require_actual) is bool)
    if require_actual:need(value['iosAvatarScriptsVersion']==2 and http_value['iosAvatarSocialHttpVersion']==2)
    exact(consumption,{'xhrId','nativeCreated','nativeSent','nativeReply','nativeRead','http'})
    actual=http.events(http_value);need(consumption['xhrId'] in actual)
    state=actual[consumption['xhrId']]
    need(state['created']==consumption['nativeCreated'] and value['processId']==http_value['processId']
         and value['runId']==http_value['runId'] and value['clockBefore']['epochMs']>=http_value['clockAfter']['epochMs'])
    need(type(consumption['nativeSent']) is dict and type(consumption['nativeSent'].get('details')) is dict)
    reply=state['replies'].get(consumption['nativeSent']['details'].get('replyId'))
    need(reply is not None and reply['sent']==consumption['nativeSent'] and reply['finished']==consumption['nativeReply']
         and reply['read']==consumption['nativeRead'])
    source=state['created']['details'];selected=worker(value,source['engine']['instance'])
    need(selected['membership']==source['engine'] and selected['code']==source['submitted'])
    found=bound_code(value,source['engine']['instance'],expected)
    if http_value['iosAvatarSocialHttpVersion']==1:
        for caller in source['callerChain']:
            suffix=next((suffix for suffix in SUFFIXES if caller.endswith(suffix)),None)
            if suffix is None:continue
            need(suffix in found and any(code['url']==caller and code['submittedEpochMs']<=state['created']['clock']['epochMs']
                                        for code in found[suffix]))
    else:
        from ios.adapters import avatar_call_stack
        table=avatar_call_stack.table(http_value['callerStacks'],http_value['clockBefore']['epochMs'])
        caller=table[source['callerStackId']];actual=caller['callerStack'];modules=caller['callerModules']
        required={'/modules/request.js'}
        owner_names={'/system/pal.js','/system/libraries/peopleConnection.js','/system/request-service.js'}
        observed={suffix for module in modules for suffix in owner_names if module['url'].endswith(suffix)}
        need(observed);required|=observed
        avatar_call_stack.bound(actual,modules,state['created']['clock']['epochMs'],selected['avatar']['code'],expected,
            required=required,top='/modules/request.js')
        read=consumption['nativeRead'];details=read['details']
        caller=table[details['callerStackId']]
        avatar_call_stack.bound(caller['callerStack'],caller['callerModules'],read['clock']['epochMs'],selected['avatar']['code'],expected,
            required={'/modules/request.js'},top='/modules/request.js')
        avatar_call_stack.continuity(actual,caller['callerStack'])
    return dict(manager=deepcopy(selected['membership']),submitted=deepcopy(selected['code']),codeSources=found,
                nativeCreated=deepcopy(state['created']))


class IOSAvatarScripts(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAvatarScriptsAcquisitionVersion'
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.retired=set();self.poisoned=False
    def read(self,run):
        need(not self.poisoned);previous=deepcopy(self.last)
        value=super().read(run)
        try:
            _current,retired=accept_membership(members(previous['source']) if previous else None,members(value['source']),self.retired,value['clockAfter']['epochMs'])
        except Exception:
            self.poisoned=True;raise NativeUIError('Original Avatar script membership continuity is unavailable') from None
        self.retired=retired;return value
    def restore(self,frames):
        need(type(frames) is list and len(frames)<=1024 and self.last is None and not self.retired and not self.poisoned)
        previous=None;retired=set()
        for value in frames:
            query=dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId'))
            validate(value,query,self.pid,previous=previous)
            _current,retired=accept_membership(members(previous['source']) if previous else None,members(value['source']),retired,value['clockAfter']['epochMs'])
            previous=deepcopy(value)
        self.last,self.retired=previous,retired
