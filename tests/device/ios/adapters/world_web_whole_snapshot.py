"""Snapshot2: existing exact World, cache and closure originals in one batch.

Snapshot1 and its historical reader remain unchanged. Every selected result is
still its original native getter packet, command, call bracket and PID.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import re
from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters import world_web_snapshot as legacy

VERSION=2
ACTION='feature-ios-world-web-whole-snapshot'
FILE=ACTION+'.json'
LIMIT=legacy.LIMIT
PLAIN_LIMIT,COMPRESSED_LIMIT=legacy.PLAIN_LIMIT,legacy.COMPRESSED_LIMIT
IDENTITY,clock,bracket,unpack=legacy.IDENTITY,legacy.clock,legacy.bracket,legacy.unpack
ACTIONS=dict(legacy.ACTIONS,surfaces='feature-ios-world-web-surfaces',closures='feature-ios-web-closures',emissions='feature-ios-web-script-emissions')
_BODY=ContextVar('overte_world_web_whole_snapshot_body_validation',default=None)


def command(value):
    need(type(value) is dict and value.get('action')==ACTION)
    legacy.command(dict(value,action=legacy.ACTION));return value


@contextmanager
def validation_round():
    if _BODY.get() is not None:yield;return
    token=_BODY.set({})
    try:yield
    finally:_BODY.reset(token)


def _validated_body(value):
    proofs=_BODY.get();key=None if proofs is None else digest(value)
    if proofs is not None and key in proofs:return proofs[key]
    result=_body(value)
    if proofs is not None and len(proofs)<256:proofs[key]=result
    return result


def body(value):return deepcopy(_validated_body(value))


def selected(value,names):
    need(type(names) in (list,tuple) and len(names)==len(set(names)) and set(names)<=set(ACTIONS))
    _original,parts=_validated_body(value);return {name:deepcopy(parts[name]) for name in names}


def _body(value):
    from ios.adapters import world_web_source,world_web_dom,world_web_work,world_web_geometry,world_web_keys,emote_world,pointer_state,create_entities,world_web_surfaces,web_closures,web_script_emissions
    modules=dict(ledgerBefore=world_web_source,document=world_web_dom,world=emote_world,work=world_web_work,
        geometry=world_web_geometry,keys=world_web_keys,pointer=pointer_state,entities=create_entities,ledgerAfter=world_web_source,surfaces=world_web_surfaces,closures=web_closures,emissions=web_script_emissions)
    original=unpack(value['payload'])
    exact(original,{'iosWorldWebSnapshotBodyVersion','identity','queries','calls','originals'})
    need(type(original['iosWorldWebSnapshotBodyVersion']) is int and original['iosWorldWebSnapshotBodyVersion']==VERSION
        and same(original['identity'],{key:value[key] for key in IDENTITY}))
    commands,calls,selected=original['queries'],original['calls'],original['originals']
    exact(commands,set(ACTIONS));exact(selected,set(ACTIONS));need(type(calls) is list and 2<=len(calls)<=64)
    for name,request in commands.items():
        if request is None:need(selected[name] is None and (value['status']=='pending' or name=='document'));continue
        fields={'schemaVersion','commandId','action','runId'}|({'fixtureUrl'} if name in ('ledgerBefore','document','ledgerAfter','closures','emissions') else set())
        exact(request,fields);need(type(request['schemaVersion']) is int and request['schemaVersion']==1
            and request['action']==ACTIONS[name] and request['runId']==value['runId']
            and type(request['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',request['commandId']))
        if 'fixtureUrl' in fields:need(request['fixtureUrl']==value['fixtureUrl'])
    nonces=[request['commandId'] for request in commands.values() if request is not None];need(len(nonces)==len(set(nonces)) and value['commandId'] not in nonces)
    decoded=[];names=[];last=value['clockBefore'];seen={};document_previous=None
    for ordinal,row in enumerate(calls,1):
        exact(row,{'ordinal','name','command','clockBefore','clockAfter','resultJSON'})
        name=row['name'];need(type(row['ordinal']) is int and row['ordinal']==ordinal and name in ACTIONS and commands[name] is not None
            and same(row['command'],commands[name]) and type(row['resultJSON']) is str and len(row['resultJSON'].encode('utf-8'))<=modules[name].LIMIT)
        bracket(row['clockBefore'],row['clockAfter']);need(last['epochMs']<=row['clockBefore']['epochMs'] and last['monotonicMs']<=row['clockBefore']['monotonicMs'])
        last=row['clockAfter'];packet=decode(row['resultJSON'],limit=LIMIT);need(type(packet) is dict)
        key='commandId' if name in ('ledgerBefore','document','ledgerAfter','closures','emissions') else 'requestId'
        need(packet.get(key)==commands[name]['commandId'] and packet.get('runId')==value['runId'] and packet.get('processId')==value['processId'])
        if name in seen:
            need(name=='document' and decoded[seen[name]-1].get('status')=='pending')
        # Validate EVERY original, including an earlier native pending result.
        # Its acquisition may legitimately predate a later outer poll; use
        # that actual call's clock, never retime the retained packet.
        if name=='document':
            world_web_dom.validate(packet,commands[name],value['processId'],row['clockAfter']['epochMs'])
            if document_previous is not None:
                need(document_previous['status']=='pending' and packet['instance']==document_previous['instance'])
                if packet['status']=='pending':need(same(packet,document_previous))
                else:need(packet['sequence']>document_previous['sequence'] and packet['capturedEpochMs']>=document_previous['capturedEpochMs'])
            document_previous=packet
        elif name=='pointer':pointer_state.validate(packet,commands[name],value['processId'])
        else:modules[name].validate(packet,commands[name],value['processId'],row['clockAfter']['epochMs'])
        if name=='keys':world_web_keys.privacy_qualified(packet)
        before,after=(packet['capturedEpochMs'],packet['capturedEpochMs']) if name in ('document','closures') else (packet['clockBefore']['epochMs'],packet['clockAfter']['epochMs'])
        first=next((old for old in calls[:ordinal] if old['name']==name),row)
        need(first['clockBefore']['epochMs']<=before<=after<=row['clockAfter']['epochMs'])
        seen[name]=ordinal;names.append(name);decoded.append(packet)
    need(last['epochMs']<=value['clockAfter']['epochMs'] and last['monotonicMs']<=value['clockAfter']['monotonicMs'])
    expected=['ledgerBefore']+(['document']*names.count('document'))+([] if value['status']=='pending' else ['world','work','geometry','keys','pointer','entities','ledgerAfter','surfaces','closures','emissions'])
    need(names==expected and (commands['document'] is None)==('document' not in names))
    results={}
    for name,index in selected.items():
        if index is None:need(commands[name] is None and (value['status']=='pending' or name=='document'));results[name]=None;continue
        need(integer(index,1,len(calls)) and seen.get(name)==index and calls[index-1]['name']==name);results[name]=decoded[index-1]
        if name=='document':need(results[name].get('status')==('pending' if value['status']=='pending' else 'ready'))
    for name,packet in results.items():
        if packet is None:continue
        if name=='pointer':pointer_state.validate(packet,commands[name],value['processId'])
        else:modules[name].validate(packet,commands[name],value['processId'],value['clockAfter']['epochMs'])
        if name=='keys':world_web_keys.privacy_qualified(packet)
        before,after=(packet['capturedEpochMs'],packet['capturedEpochMs']) if name in ('document','closures') else (packet['clockBefore']['epochMs'],packet['clockAfter']['epochMs'])
        own=[row for row in calls if row['name']==name]
        need(own[0]['clockBefore']['epochMs']<=before<=after<=own[-1]['clockAfter']['epochMs'])
    from ios.adapters.world_web_trace import current_view
    need((current_view(results['ledgerBefore']) is None)==(commands['document'] is None))
    return original,results

def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,IDENTITY|{'status','complete','payload'})
    need(type(value['iosWorldWebSnapshotVersion']) is int and value['iosWorldWebSnapshotVersion']==VERSION
        and all(value[key]==query[key] for key in ('commandId','runId','fixtureUrl'))
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance']) and integer(value['sequence'],1)
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and value['clockDomain']=='native-main-ios-world-web-snapshot' and type(value['complete']) is bool
        and value['status'] in ('pending','ready','unavailable'))
    bracket(value['clockBefore'],value['clockAfter'])
    if epoch is not None:fresh(value['clockAfter']['epochMs'],epoch)
    if value['status'] in ('ready','pending'):
        if value['status']=='ready':need(value['complete'])
        _validated_body(value)
    else:need(value['payload'] is None)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']
            and value['clockBefore']['epochMs']>=previous['clockAfter']['epochMs'] and value['clockBefore']['monotonicMs']>=previous['clockAfter']['monotonicMs']
            and (previous['complete'] or not value['complete']))
    return value


def continued(value,previous):
    """Same actual acquisition; no recapture or outer-clock retiming."""
    need(previous['status']=='pending' and value['status'] in ('pending','ready','unavailable')
        and (previous['complete'] or not value['complete']))
    for key in IDENTITY-{'clockAfter'}:need(same(value[key],previous[key]))
    for key in ('epochMs','monotonicMs'):need(value['clockAfter'][key]>=previous['clockAfter'][key])
    if value['status']=='unavailable':return
    old,_=body(previous);new,_=body(value)
    need(new['calls'][:len(old['calls'])]==old['calls'])
    for name,query in old['queries'].items():
        if query is not None:need(same(new['queries'][name],query))
    if len(new['calls'])==len(old['calls']):need(same(value,previous))


class IOSWorldWebWholeSnapshot(legacy.IOSWorldWebSnapshot):
    _action=ACTION
    _command=staticmethod(command)
    def _validate(self,value,query,pid,epoch=None,previous=None):
        validate(value,query,pid,epoch,previous)
        old=self._pending_originals.get(query['commandId'])
        if old is not None:continued(value,old)
        if value['status']=='pending':
            need(len(self._pending_originals)<512 or query['commandId'] in self._pending_originals)
            self._pending_originals[query['commandId']]=deepcopy(value)
