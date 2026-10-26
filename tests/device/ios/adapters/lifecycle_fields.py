"""Passive original Qt field/context census for the Lifecycle journey.

Object birth is first observation, not a construction timestamp. A new page
alias additionally requires an observed advance of its actual loader generation.
This codec does not make the complete Lifecycle adapter available.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from urllib.parse import urlsplit,unquote
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.keyboard_source import identifier,sha,clock

VERSION=1
IDS={'lifecycle.create.text':'create','lifecycle.scripts.filter':'scripts'}
NAMES={'create':'NativeCreateText','chat':'chatMessageInput','scripts':'scriptFilter'}
PATHS={'create':'/system/create/qml/NativeCreate.qml',
       'chat':'/communityScripts/armored-chat/armored_chat.qml',
       'scripts':'/hifi/dialogs/TabletRunningScripts.qml'}
KINDS={'fieldId':'field','rootId':'root','contextId':'context','windowId':'window','loaderId':'loader'}


def identity(value):
    exact(value,{'editor','componentSource','fieldName','loadGeneration'}|set(KINDS))
    editor=value['editor'];need(type(editor) is str and editor in NAMES and value['fieldName']==NAMES[editor])
    source=value['componentSource'];need(type(source) is str and len(source)<=4096)
    url=urlsplit(source);path=unquote(url.path)
    need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
         and path.startswith('/') and '..' not in path.split('/') and path.endswith(PATHS[editor]))
    need(integer(value['loadGeneration'],1))
    for key in KINDS:identifier(value[key])
    need(len({value[key] for key in KINDS})==len(KINDS))
    return value


def owned_text(text,editor):
    from re import fullmatch
    prefix={'create':'Overte ä Ω 東京 ','chat':'reply-','scripts':'retry-'}[editor]
    return type(text) is str and (text=='' or (text.startswith(prefix) and fullmatch('[a-f0-9]{32}',text[len(prefix):]) is not None))


def metadata(value):
    exact(value,{'identity','attached','visible','focused','enabled','readOnly','textOwned','text','textSha256','textCodeUnits'})
    identity(value['identity'])
    for key in ('attached','visible','focused','enabled','readOnly','textOwned'):need(type(value[key]) is bool)
    need(integer(value['textCodeUnits']))
    if value['textSha256'] is not None:sha(value['textSha256'])
    if value['textOwned']:
        text=value['text'];need(owned_text(text,value['identity']['editor']))
        need(value['textCodeUnits']==len(text.encode('utf-16-le'))//2
             and value['textSha256']==hashlib.sha256(text.encode()).hexdigest())
    else:need(value['text'] is None)
    return value


def validate(value,*,pid,epoch=None,previous=None):
    exact(value,{'iosLifecycleFieldsVersion','instance','sequence','processId','complete','clockBefore','clockAfter','fields','objects','loaders','pendingBindings'})
    need(type(value['iosLifecycleFieldsVersion']) is int and value['iosLifecycleFieldsVersion']==VERSION
         and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
         and integer(value['sequence'],1) and type(value['complete']) is bool)
    identifier(value['instance']);a,b=value['clockBefore'],value['clockAfter'];clock(a);clock(b,floor=a)
    need(b['monotonicMs']-a['monotonicMs']<1500 and b['epochMs']-a['epochMs']<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    need(type(value['objects']) is list and len(value['objects'])<=80
         and type(value['fields']) is list and len(value['fields'])<=16
         and type(value['loaders']) is list and len(value['loaders'])<=8
         and type(value['pendingBindings']) is list and len(value['pendingBindings'])<=64)
    objects={}
    for row in value['objects']:
        exact(row,{'id','kind','born','alive','expired'});identifier(row['id'])
        need(row['id'] not in objects and type(row['kind']) is str and row['kind'] in KINDS.values() and type(row['alive']) is bool)
        clock(row['born'],ceiling=b)
        if row['expired'] is None:need(row['alive'])
        else:clock(row['expired'],floor=row['born'],ceiling=b);need(not row['alive'])
        objects[row['id']]=row
    def member(oid,kind,alive=False):
        need(oid in objects and objects[oid]['kind']==kind and (not alive or objects[oid]['alive']))
    loaders={}
    for row in value['loaders']:
        exact(row,{'loaderId','loadGeneration','rootId','windowId','sourceSha256'})
        identifier(row['loaderId']);need(row['loaderId'] not in loaders and integer(row['loadGeneration']))
        member(row['loaderId'],'loader',True);sha(row['sourceSha256'])
        for key in ('rootId','windowId'):
            if row[key] is not None:identifier(row[key]);member(row[key],KINDS[key],True)
        loaders[row['loaderId']]=row
    seen=set();identities=[]
    for row in value['fields']:
        exact(row,{'identity','current'});original=identity(row['identity'])
        key=(original['fieldId'],original['rootId'],original['contextId'],original['loadGeneration'])
        need(key not in seen);seen.add(key)
        identities.append(original)
        for name,kind in KINDS.items():member(original[name],kind)
        if row['current'] is not None:
            current=metadata(row['current']);need(same(current['identity'],original))
            for name,kind in KINDS.items():member(original[name],kind,True)
            if current['attached']:
                loader=loaders.get(original['loaderId']);need(loader is not None)
                need(all(loader[key]==original[key] for key in ('loadGeneration','rootId','windowId')))
    tokens=set()
    for row in value['pendingBindings']:
        exact(row,{'token','identity'});identifier(row['token']);identity(row['identity'])
        need(row['token'] not in tokens and row['identity']['editor']=='scripts' and row['identity'] in identities)
        tokens.add(row['token'])
    if previous is not None:
        validate(previous,pid=pid);need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'])
        clock(a,floor=previous['clockAfter'])
        need(len(value['objects'])>=len(previous['objects']) and len(value['fields'])>=len(previous['fields'])
             and (previous['complete'] or not value['complete']))
        for old,new in zip(previous['objects'],value['objects']):
            need(all(same(old[key],new[key]) for key in ('id','kind','born')))
            if old['expired'] is not None:need(same(old,new))
        for old,new in zip(previous['fields'],value['fields']):need(same(old['identity'],new['identity']))
        need(same(previous['pendingBindings'],value['pendingBindings'][:len(previous['pendingBindings'])]))
        for old in previous['loaders']:
            new=loaders.get(old['loaderId'])
            if new is None:need(not value['complete'] or not objects[old['loaderId']]['alive'])
            else:
                need(new['loadGeneration']>=old['loadGeneration'])
                if new['loadGeneration']==old['loadGeneration']:
                    need(all(same(old[key],new[key]) for key in ('loaderId','loadGeneration','windowId','sourceSha256')))
                    if old['rootId'] is not None:need(new['rootId']==old['rootId'])
                    elif new['rootId'] is not None:
                        # TabletPageLoader completes asynchronous creation after
                        # its actual generation/source advance, without another load.
                        clock(objects[new['rootId']]['born'],floor=previous['clockAfter'])
    return value


def active(value):
    validate(value,pid=value['processId']);need(value['complete'])
    rows=[row['current'] for row in value['fields'] if row['current'] is not None
          and row['current']['attached'] and row['current']['visible']]
    need(len(rows)<=1)
    return deepcopy(rows[0]) if rows else None


def alias_transition(before,after,editor,generation):
    """Qualify a newly loaded actual field, never a command acknowledgment."""
    validate(after,pid=before['processId'],previous=before);need(before['complete'])
    need((editor,generation) in (('create',1),('chat',2),('scripts',3),('scripts',4)))
    current=active(after);need(current is not None and current['identity']['editor']==editor
                            and current['textOwned'] and current['text']=='')
    original=current['identity'];known={row['id'] for row in before['objects']}
    need(all(original[key] not in known for key in ('fieldId','rootId','contextId')))
    loaders=[row for row in before['loaders'] if row['loaderId']==original['loaderId']];need(len(loaders)==1)
    need(original['loadGeneration']>loaders[0]['loadGeneration'] and original['rootId']!=loaders[0]['rootId'])
    if generation==4:need(not current['focused'])
    return dict(generation=generation,identity=deepcopy(original))


def reference(value,identifier):
    need(type(identifier) is str and identifier in IDS and value.get('lifecycleFieldsVersion')==1)
    rows=[row for row in value['controls'] if row['id']==identifier];need(len(rows)==1)
    row=rows[0];metadata(row['lifecycleField']);need(row['lifecycleField']['identity']['editor']==IDS[identifier])
    return dict(scope={key:deepcopy(value[key]) for key in ('instance','processId','lastSequence','elapsedMs')},control=deepcopy(row))


def current_reference(original,value,identifier):
    exact(original,{'scope','control'});exact(original['scope'],{'instance','processId','lastSequence','elapsedMs'})
    actual=reference(value,identifier)
    need(same(original['control'],actual['control']) and all(same(original['scope'][key],actual['scope'][key])
         for key in ('instance','processId','lastSequence'))
         and integer(original['scope']['elapsedMs']) and actual['scope']['elapsedMs']>=original['scope']['elapsedMs'])
    return actual


def join_pending(fields,pending,request):
    """Join the native owner's actual weak-field token to the Qt census.

    The iOS native IdentityObserver records the token/object relation during
    the actual owner response. Matching text or a caller-supplied alias alone
    cannot establish this relation.
    """
    from adapters.pending_commit_owner import validate as pending_packet
    validate(fields,pid=fields['processId']);need(fields['complete'])
    pending_packet(pending,request,fields['processId'],fields['clockAfter']['epochMs'])
    need(pending['capturedEpochMs']<=fields['clockBefore']['epochMs']
         and set(pending['resources']['pendingRuns'])<={request['runId']})
    bindings={row['token']:row['identity'] for row in fields['pendingBindings']}
    objects={row['id']:row for row in fields['objects']}
    def existed(original,epoch):
        need(all(objects[original[key]]['born']['epochMs']<=epoch
                 and (objects[original[key]]['expired'] is None or objects[original[key]]['expired']['epochMs']>=epoch)
                 for key in KINDS))
    current=active(fields);actual=pending['current'];current_identity=None;held_identity=None
    if actual['status']=='ready':
        current_identity=bindings.get(actual['token']);need(current_identity is not None and current is not None)
        need(same(current_identity,current['identity']) and current_identity['componentSource']==actual['componentUrl']
             and current['textOwned'] and current['text']==actual['text'] and current['focused']==actual['focused'])
        existed(current_identity,pending['capturedEpochMs'])
    else:need(actual['status']=='none' and (current is None or current['identity']['editor']!='scripts'))
    if pending['commit']:
        commit=pending['commit'];held_identity=bindings.get(commit['fieldToken']);need(held_identity is not None)
        need(held_identity['componentSource']==commit['observation']['source']['componentUrl'])
        existed(held_identity,commit['observation']['createdEpochMs'])
    return deepcopy(dict(current=current_identity,held=held_identity,commit=pending['commit'],resources=pending['resources']))
