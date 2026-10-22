"""Original native missing-place modal, callback and actual lifetime evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit,unquote

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_navigation_replies import validate as replies_validate
from adapters.script_feature.history import same
from feature_journeys.navigation_fixture import configuration,validate_status
from ios.adapters.places_http import identifier,clock
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-navigation-dialogs'
FILE='feature-ios-navigation-dialogs.json'
LIMIT=262144
TEXT='There is no address information for that user or place'


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    identifier(value['runId']);return value


def component(value):
    need(type(value) is str and len(value)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in value))
    url=urlsplit(value);path=unquote(url.path,encoding='utf-8',errors='strict')
    need(url.scheme in ('qrc','file') and not url.netloc and not url.query and not url.fragment
         and (path.endswith('/dialogs/MessageDialog.qml') or path.endswith('/dialogs/TabletMessageBox.qml'))
         and not any(part in ('.','..') for part in path.split('/')))
    return value


def error_context(value,run,pid,epoch):
    exact(value,{'navigationErrorContextVersion','instance','processId','event'})
    need(type(value['navigationErrorContextVersion']) is int and value['navigationErrorContextVersion']==1
         and type(value['processId']) is int and value['processId']==pid);identifier(value['instance'])
    # Reuse the original named-error validator without inventing a new event.
    event=value['event'];need(type(event) is dict and event.get('runId')==run)
    query=dict(schemaVersion=1,commandId='ios-'+'0'*32,action='feature-navigation-replies',runId=run)
    packet=dict(navigationReplyVersion=1,commandId=query['commandId'],runId=run,instance=value['instance'],sequence=1,
        processId=pid,capturedEpochMs=epoch,currentLookupGeneration=event.get('lookupGeneration'),currentLookupActive=True,events=[event])
    replies_validate(packet,query,pid,epoch)
    need(event['contentNotFound'] and event['networkError']==203)
    return value


def history(value):
    need(type(value['events']) is list and len(value['events'])<=512)
    states={};ids=set();seen_errors=set();sequence=0;last=dict(epochMs=0,monotonicMs=0)
    for event in value['events']:
        exact(event,{'sequence','eventId','dialogId','kind','clock','details'})
        need(integer(event['sequence'],sequence+1,512));sequence=event['sequence']
        identifier(event['eventId']);identifier(event['dialogId']);need(event['eventId'] not in ids);ids.add(event['eventId'])
        now=clock(event['clock']);need(all(last[key]<=now[key]<=value['clockBefore'][key] for key in last));last=now
        detail=event['details'];kind=event['kind'];id=event['dialogId']
        if kind=='created':
            exact(detail,{'source','error','dialogCreated','listenerCreated','qmlSource'})
            need(id not in states and len(states)<128 and detail['source']=='AddressBarDialog.displayAddressNotFoundMessage'
                 and type(detail['dialogCreated']) is bool and type(detail['listenerCreated']) is bool
                 and (not detail['dialogCreated'] or detail['listenerCreated']))
            error_context(detail['error'],value['runId'],value['processId'],now['epochMs'])
            key=(detail['error']['instance'],detail['error']['event']['eventId']);need(key not in seen_errors);seen_errors.add(key)
            if detail['dialogCreated']:component(detail['qmlSource'])
            else:need(detail['qmlSource']=='')
            states[id]=dict(created=deepcopy(event),response=None,listenerDestroyed=not detail['listenerCreated'],
                dialogDestroyed=not detail['dialogCreated'],creatorDestroyed=False)
            continue
        need(id in states);state=states[id]
        if kind=='response':
            exact(detail,{'kind','value','valueSha256'})
            need(not state['listenerDestroyed'] and state['response'] is None and detail['kind'] in ('int','null','unsupported')
                 and (integer(detail['value'],0,2**31-1) if detail['kind']=='int' else detail['value'] is None)
                 and type(detail['valueSha256']) is str and re.fullmatch('[a-f0-9]{64}',detail['valueSha256']))
            state['response']=deepcopy(event)
        elif kind in ('dialog-destroyed','listener-destroyed','creator-destroyed'):
            exact(detail,set());field={'dialog-destroyed':'dialogDestroyed','listener-destroyed':'listenerDestroyed','creator-destroyed':'creatorDestroyed'}[kind]
            need(not state[field]);state[field]=True
        else:need(False)
    return states


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosNavigationDialogsVersion','requestId','runId','instance','processId','sequence','clockDomain',
        'clockBefore','clockAfter','complete','dialogs','events','enums','foreignModals'})
    need(type(value['iosNavigationDialogsVersion']) is int and value['iosNavigationDialogsVersion']==VERSION
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
         and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1_000_000_000)
         and value['clockDomain']=='native-main-navigation-dialogs' and type(value['complete']) is bool and integer(value['foreignModals'],0,1024))
    identifier(value['instance']);before,after=clock(value['clockBefore']),clock(value['clockAfter'])
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    exact(value['enums'],{'okButton','criticalIcon'});need(integer(value['enums']['okButton'],1,2**31-1) and integer(value['enums']['criticalIcon'],0,1000))
    states=history(value);need(type(value['dialogs']) is list and len(value['dialogs'])==len(states));seen=set()
    for entry in value['dialogs']:
        exact(entry,{'dialogId','listenerAlive','creatorAlive','creatorVisible','dialog'})
        identifier(entry['dialogId']);need(entry['dialogId'] in states and entry['dialogId'] not in seen);seen.add(entry['dialogId'])
        state=states[entry['dialogId']]
        for key in ('listenerAlive','creatorAlive','creatorVisible'):need(type(entry[key]) is bool)
        need(entry['listenerAlive']==(not state['listenerDestroyed']) and entry['creatorAlive']==(not state['creatorDestroyed'])
             and (not entry['creatorVisible'] or entry['creatorAlive']))
        if state['dialogDestroyed']:need(entry['dialog'] is None)
        else:
            root=entry['dialog'];exact(root,{'qmlSource','visible','windowPresent','text','buttons','icon','clickedButton'})
            component(root['qmlSource']);need(root['qmlSource']==state['created']['details']['qmlSource']
                and type(root['visible']) is bool and type(root['windowPresent']) is bool and (not root['visible'] or root['windowPresent'])
                and type(root['text']) is str and len(root['text'])<=4096)
            root['text'].encode('utf-8')
            for key in ('buttons','icon','clickedButton'):need(integer(root[key],0,2**31-1))
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        old=previous['events'];need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and len(value['events'])>=len(old) and same(value['events'][:len(old)],old)
            and same(value['enums'],previous['enums']) and all(before[key]>=previous['clockAfter'][key] for key in before))
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=LIMIT)
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def owned_missing(value,replies,*,provider_status,provider_instance,inputs,owned_origin,run,ticket,native_after_epoch,provider_after_epoch,after_event):
    """Actual current callback + original native-created visible modal + HTTP."""
    original(value);identifier(run);identifier(ticket)
    need(value['complete'] is True and value['foreignModals']==0 and value['runId']==run and integer(native_after_epoch,1) and integer(provider_after_epoch,1)
         and integer(after_event,0))
    configuration(inputs);validate_status(provider_status,instance=provider_instance,run=run,inputs=inputs)
    need(provider_status['active'] and provider_status['ticket']==ticket and provider_after_epoch<=provider_status['capturedEpochMs'])
    request=dict(schemaVersion=1,commandId=replies.get('commandId'),action='feature-navigation-replies',runId=run)
    replies_validate(replies,request,value['processId'],replies.get('capturedEpochMs'))
    need(replies['currentLookupActive'] and value['clockAfter']['epochMs']<=replies['capturedEpochMs']<value['clockAfter']['epochMs']+1500)
    receipts={row['responseId']:row for row in provider_status['responses'] if row['kind']=='missing-name' and row['ticket']==ticket
        and row['completedEpochMs']>=provider_after_epoch}
    found=[]
    for id,state in history(value).items():
        created=state['created'];context=created['details']['error'];event=context['event']
        if (created['sequence']<=after_event or event['callbackEpochMs']<native_after_epoch or event['origin']!=owned_origin
                or context['instance']!=replies['instance'] or event['lookupGeneration']!=replies['currentLookupGeneration']
                or event['responseId'] not in receipts or event['httpStatus']!=404 or state['response'] is not None):continue
        if not any(same(row,event) for row in replies['events']):continue
        entries=[entry for entry in value['dialogs'] if entry['dialogId']==id];need(len(entries)==1);entry=entries[0];root=entry['dialog']
        if root is None or not root['visible'] or not entry['listenerAlive']:continue
        need(root['text']==TEXT and root['buttons']==value['enums']['okButton'] and root['icon']==value['enums']['criticalIcon'])
        found.append(dict(dialogId=id,created=deepcopy(created),nativeError=deepcopy(event),http=deepcopy(receipts[event['responseId']]),
            dialog=deepcopy(root),creatorVisible=entry['creatorVisible']))
    need(len(found)==1);return found[0]


def drained(value,owned_ids,*,require_ok=False):
    original(value);need(value['complete'] is True and type(owned_ids) in (list,tuple) and bool(owned_ids)
         and len(set(owned_ids))==len(owned_ids) and type(require_ok) is bool)
    states=history(value)
    for id in owned_ids:
        identifier(id);need(id in states);state=states[id]
        if not state['dialogDestroyed'] or not state['listenerDestroyed']:return False
        if require_ok:
            response=state['response']
            if response is None or response['details']['kind']!='int' or response['details']['value']!=value['enums']['okButton']:return False
    return True


class IOSNavigationDialogs(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosNavigationDialogsAcquisitionVersion'
