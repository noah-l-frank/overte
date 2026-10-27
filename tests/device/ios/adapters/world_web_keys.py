"""Actual Qt keyboard/IME dispatch and held-key originals, never release ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import marshal
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from ios.adapters.places_model import IOSPlacesModel,text
from ios.adapters.create_state import command as state_command

VERSION=2
READS=(1,2)
ACTION='feature-ios-world-web-keys'
FILE=ACTION+'.json'
LIMIT=1048576
HEX='[0-9a-f]{32}'
_SOURCE_VALIDATION=ContextVar('world_web_pure_key_source_validation',default=None)
_SOURCE_ENTRIES=256
_SOURCE_BYTES=8*1024*1024
_SOURCE_INPUT_BYTES=8*1024*1024


def command(value):
    state_command(dict(value,action='feature-ios-create-state'));need(value['action']==ACTION);return value


def nonce(value):need(type(value) is str and re.fullmatch(HEX,value));return value


def _source(value,epoch):
    exact(value,{'iosWorldWebKeySourceVersion','instance','bornEpochMs','complete','startup','eventSequence','events','dispatches',
        'pendingDispatches','down','ended','preedit','devices','targets','qtModifiers'})
    version=value['iosWorldWebKeySourceVersion']
    need(type(version) is int and version in READS
        and type(value['complete']) is bool and integer(value['bornEpochMs'],1,epoch))
    nonce(value['instance']);startup=value['startup'];exact(startup,{'observed','epochMs','monotonicMs','windowCount','modifiers'})
    need(type(startup['observed']) is bool and integer(startup['epochMs'],0,epoch) and integer(startup['monotonicMs'])
        and type(startup['windowCount']) is int and -1<=startup['windowCount']<=10000 and type(startup['modifiers']) is int and startup['modifiers']>=-1)
    if value['complete']:need(startup['observed'] and startup['windowCount']==startup['modifiers']==0 and startup['epochMs']>=value['bornEpochMs'])
    need(integer(value['eventSequence'],0,3072) and type(value['events']) is list and len(value['events'])==value['eventSequence']
        and type(value['dispatches']) is list and len(value['dispatches'])<=1024 and integer(value['pendingDispatches'],0,1024)
        and integer(value['qtModifiers'],0,2**31-1))
    registries={}
    for name in ('devices','targets'):
        rows=value[name];need(type(rows) is list and len(rows)<=64);registry={}
        for row in rows:
            exact(row,{'id','bornEpochMs','className','alive'});nonce(row['id']);text(row['className'],256)
            need(row['id'] not in registry and integer(row['bornEpochMs'],value['bornEpochMs'],epoch) and type(row['alive']) is bool)
            registry[row['id']]=row
        registries[name]=registry
    rows={}
    for row in value['dispatches']:
        exact(row,{'id','batch','kind','target','device','detail','enteredSequence','enteredEpochMs','enteredMonotonicMs',
            'returnedSequence','returnedEpochMs','returnedMonotonicMs','deliveryResult','finallySequence','finallyEpochMs','finallyMonotonicMs'})
        nonce(row['id']);nonce(row['batch']);need(row['id'] not in rows and row['target'] in registries['targets']
            and row['kind'] in ('key-press','key-release','input-method'))
        detail=row['detail']
        if row['kind']=='input-method':
            need(row['device']=='')
            if version==1:
                exact(detail,{'commit','preedit','replacementStart','replacementLength'})
                text(detail['commit'],32768);text(detail['preedit'],32768)
                need(len(detail['commit'].encode('utf-16-le'))//2<=8192 and len(detail['preedit'].encode('utf-16-le'))//2<=8192
                    and type(detail['replacementStart']) is int and -8192<=detail['replacementStart']<=8192 and integer(detail['replacementLength'],0,8192))
            else:exact(detail,{'preeditActive'});need(type(detail['preeditActive']) is bool)
        else:
            exact(detail,({'key','text','scanCode','virtualKey'} if version==1 else {'keyId'})
                |{'modifiers','autoRepeat','qtTimestamp'}|({'count'} if version==1 else set()))
            need(row['device'] in registries['devices'] and integer(detail['modifiers'],0,2**31-1)
                and type(detail['autoRepeat']) is bool and number(detail['qtTimestamp'],0,1e15))
            if version==1:
                need(integer(detail['key'],0,2**31-1) and integer(detail['scanCode'],0,2**32-1) and integer(detail['virtualKey'],0,2**32-1)
                    and integer(detail['count'],0,65535))
                text(detail['text'],32768);need(len(detail['text'].encode('utf-16-le'))//2<=8192)
            else:nonce(detail['keyId'])
        need(integer(row['enteredSequence'],1,value['eventSequence']) and integer(row['enteredEpochMs'],value['bornEpochMs'],epoch)
            and integer(row['enteredMonotonicMs']) and (row['deliveryResult'] is None or type(row['deliveryResult']) is bool))
        for phase in ('returned','finally'):
            need(integer(row[phase+'Sequence'],0,value['eventSequence']) and integer(row[phase+'EpochMs'],0,epoch) and integer(row[phase+'MonotonicMs']))
            if row[phase+'Sequence']==0:need(row[phase+'EpochMs']==row[phase+'MonotonicMs']==0)
        need((row['returnedSequence']==0)==(row['deliveryResult'] is None));rows[row['id']]=row
    active=set();batches={};batch_facts={};seen_batches=set();seen_keys=set();down={};ended=[];preedit={};seen={};last_epoch=value['bornEpochMs'];last_mono=0
    for index,event in enumerate(value['events'],1):
        exact(event,{'sequence','dispatch','kind','epochMs','monotonicMs'})
        need(type(event['sequence']) is int and event['sequence']==index and event['dispatch'] in rows
            and event['kind'] in ('entered','returned','finally') and integer(event['epochMs'],last_epoch,epoch)
            and integer(event['monotonicMs'],last_mono))
        if index>1:need(abs(event['epochMs']-last_epoch-event['monotonicMs']+last_mono)<=250)
        last_epoch,last_mono=event['epochMs'],event['monotonicMs']
        row=rows[event['dispatch']];phase=event['kind']
        need(row[phase+'Sequence']==index and row[phase+'EpochMs']==event['epochMs'] and row[phase+'MonotonicMs']==event['monotonicMs'])
        marks=seen.setdefault(row['id'],[])
        if phase=='entered':
            need(not marks);active.add(row['id']);batch=row['batch'];nested=batch in batches;batches[batch]=batches.get(batch,0)+1
            if version>=2:
                facts=(row['kind'],row['device'],row['detail'])
                if nested:need(batch_facts[batch]==facts)
                else:batch_facts[batch]=facts
            if not nested:
                need(batch not in seen_batches);seen_batches.add(batch)
                detail=row['detail']
                if row['kind']=='input-method':
                    preedit[row['target']]=dict(target=row['target'],dispatch=row['id'],**(
                        dict(text=detail['preedit']) if version==1 else dict(active=detail['preeditActive'])))
                elif not detail['autoRepeat']:
                    key=row['device']+':'+str(detail['scanCode'])+':'+str(detail['key']) if version==1 else detail['keyId']
                    if row['kind']=='key-press':
                        need(key not in down)
                        if version>=2:need(key not in seen_keys);seen_keys.add(key)
                        down[key]=dict(device=row['device'],target=row['target'],pressDispatch=row['id'],releaseDispatch='',**(
                            dict(key=detail['key'],scanCode=detail['scanCode']) if version==1 else dict(keyId=key)))
                    else:
                        need(key in down and down[key]['device']==row['device']);previous=down.pop(key);previous['releaseDispatch']=row['id'];ended.append(previous)
                elif version>=2:need(detail['keyId'] in down and down[detail['keyId']]['device']==row['device'])
        elif phase=='returned':need(marks==['entered'] and row['id'] in active)
        else:
            need(marks==['entered','returned'] and row['id'] in active);active.remove(row['id'])
            batches[row['batch']]-=1
            if batches[row['batch']]==0:del batches[row['batch']]
        marks.append(phase)
    need(len(active)==value['pendingDispatches'] and value['down']==[down[k] for k in sorted(down)] and value['ended']==ended
        and value['preedit']==[preedit[k] for k in sorted(preedit)] and set(rows)==set(seen))
    for row in rows.values():
        expected=seen[row['id']]
        need(bool(row['returnedSequence'])==('returned' in expected) and bool(row['finallySequence'])==('finally' in expected))
    return value


def _source_metadata():
    readers=(_source,nonce,exact,integer,need,number,text,re.fullmatch,marshal.dumps,hashlib.sha256)
    return tuple((id(function),id(getattr(function,'__code__',None)),marshal.dumps((
        getattr(function,'__defaults__',None),getattr(function,'__kwdefaults__',None)),4)) for function in readers),marshal.dumps((HEX,READS),4)


# Keep the exact original objects alive as well as their identity numbers.
_ORIGINAL_SOURCE_READERS=(_source,nonce,exact,integer,need,number,text,re.fullmatch,marshal.dumps,hashlib.sha256)
_ORIGINAL_SOURCE_CODES=tuple(getattr(function,'__code__',None) for function in _ORIGINAL_SOURCE_READERS)
_ORIGINAL_SOURCE_METADATA=_source_metadata()


def _literal_source():
    try:return _source_metadata()==_ORIGINAL_SOURCE_METADATA
    except (TypeError,ValueError,OverflowError,RecursionError):return False


def _source_key(value,epoch):
    try:
        # Format2 has no shared-object reference encoding: independent JSON
        # reads of equal trees must not depend on Python aliases/refcounts.
        encoded=marshal.dumps((value,epoch),2)
        if len(encoded)<=_SOURCE_INPUT_BYTES:
            key=hashlib.sha256(encoded).digest()
            # Only this digest is retained; encoded inputs are discarded.
            return key,len(key)
    except (TypeError,ValueError,OverflowError,RecursionError):pass
    return None,0


@contextmanager
def validation_round():
    """Pure successes belong only to the enclosing, unchanged World API budget."""
    from ios.adapters.world_web_api_clock import active
    if not active() or _SOURCE_VALIDATION.get() is not None:yield;return
    token=_SOURCE_VALIDATION.set(dict(entries=set(),bytes=0))
    try:yield
    finally:_SOURCE_VALIDATION.reset(token)


def source(value,epoch):
    cache=_SOURCE_VALIDATION.get()
    if cache is None:return _source(value,epoch)
    from ios.adapters.world_web_api_clock import active,check
    if not active():return _source(value,epoch)
    check()
    if not _literal_source():return _source(value,epoch)
    # Marshal bytes preserve bool/int/float distinctions. No parser output,
    # packet, file membership or current clock enters the cache.
    key,cost=_source_key(value,epoch)
    if key is None:return _source(value,epoch)
    if key in cache['entries']:
        check()
        # Even the supplied monotonic callable may mutate memory. A successful
        # old tree cannot qualify changed bytes after the final budget check.
        need(_literal_source() and _source_key(value,epoch)[0]==key);return value
    result=_source(value,epoch);check()
    need(_literal_source() and _source_key(value,epoch)[0]==key)
    if (result is value and len(cache['entries'])<_SOURCE_ENTRIES and cache['bytes']+cost<=_SOURCE_BYTES):
        cache['entries'].add(key);cache['bytes']+=cost
    return result


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosWorldWebKeysVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosWorldWebKeysVersion']) is int and value['iosWorldWebKeysVersion'] in READS and value['requestId']==query['commandId']
        and value['runId']==query['runId'] and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and integer(value['sequence'],1) and value['clockDomain']=='native-main-ios-world-web-keys');nonce(value['instance'])
    a,b=value['clockBefore'],value['clockAfter']
    for clock in (a,b):exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    utc,mono=b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'];need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source(value['source'],a['epochMs'])
    need(value['source']['iosWorldWebKeySourceVersion']==value['iosWorldWebKeysVersion'])
    if previous is not None:
        original(previous);left,right=previous['source'],value['source']
        need(value['iosWorldWebKeysVersion']==previous['iosWorldWebKeysVersion'] and value['instance']==previous['instance']
            and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and a['epochMs']>=previous['clockAfter']['epochMs'] and a['monotonicMs']>=previous['clockAfter']['monotonicMs']
            and all(same_field(left[key],right[key]) for key in ('instance','bornEpochMs','startup')) and (left['complete'] or not right['complete'])
            and right['events'][:len(left['events'])]==left['events'] and len(right['dispatches'])>=len(left['dispatches']))
        mutable={prefix+suffix for prefix in ('returned','finally') for suffix in ('Sequence','EpochMs','MonotonicMs')}|{'deliveryResult'}
        for old,new in zip(left['dispatches'],right['dispatches']):
            need(all(old[key]==new[key] for key in old if key not in mutable))
            for prefix in ('returned','finally'):
                if old[prefix+'Sequence']:need(all(old[prefix+suffix]==new[prefix+suffix] for suffix in ('Sequence','EpochMs','MonotonicMs')))
            if old['deliveryResult'] is not None:need(old['deliveryResult']==new['deliveryResult'])
        for name in ('devices','targets'):
            need(len(right[name])>=len(left[name]))
            for old,new in zip(left[name],right[name]):need(all(old[k]==new[k] for k in old if k!='alive') and (old['alive'] or not new['alive']))
    return value


def same_field(left,right):return type(left) is type(right) and left==right


def original(value):return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def privacy_qualified(value):
    """Current production source, with no characters or physical key codes.

    Legacy originals remain readable at their original version. They cannot
    establish the current global-input privacy boundary for a whole feature.
    """
    original(value);need(value['iosWorldWebKeysVersion']==value['source']['iosWorldWebKeySourceVersion']==2)
    return value


def drained(value):
    original(value);source=value['source']
    need(source['complete'] and source['startup']['observed'] and source['pendingDispatches']==0 and source['down']==[]
        and source['qtModifiers']==0 and all(row['text']=='' if source['iosWorldWebKeySourceVersion']==1 else row['active'] is False
            for row in source['preedit']))
    return deepcopy(source)


def current_validate(value,query,pid,epoch=None,previous=None):
    validate(value,query,pid,epoch,previous);return privacy_qualified(value)


class IOSWorldWebKeys(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(current_validate)
    _limit=LIMIT
    _acquisition_key='iosWorldWebKeysAcquisitionVersion'
