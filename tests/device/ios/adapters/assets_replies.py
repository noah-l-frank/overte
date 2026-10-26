"""Original independent AssetClient read requests and their actual lifetimes.

This is neither upload acknowledgement, a product model consumer nor an oven
inventory. Every positive server read needs original wire/source joins.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check as transport_check
from adapters.script_feature.history import same
from feature_journeys.asset_fixture import BUNDLES
from feature_journeys.contract import identifier
from ios.adapters.assets_budget import operation
from ios.adapters.assets_controls import identity
from ios.adapters import assets_reply_protocol as wire

VERSION=1
ACTION='feature-ios-assets-replies'
FILE=ACTION+'.json'
LIMIT=262144
STARTS=frozenset(('inventory','mapping','info','raw-server'))
SCOPE=('runId','ticket','ownerToken','resource','namespace')


def nonce(value):need(type(value) is str and re.fullmatch('ios-[a-f0-9]{32}',value));return value


def native_id(value):need(type(value) is str and re.fullmatch('[a-f0-9]{32}',value));return value


def command(value):
    need(type(value) is dict);kind=value.get('operation')
    exact(value,{'schemaVersion','commandId','action','runId','ticket','ownerToken','resource','namespace','operation'}
        |({'sourceJob','relativePath'} if kind in ('mapping','info','raw-server') else {'jobId'} if kind in ('observe','retire') else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']==ACTION
        and value['resource'] in BUNDLES and value['namespace'] in ('original','renamed') and kind in STARTS|{'observe','retire'}
        and type(value['ownerToken']) is str and re.fullmatch('[a-f0-9]{64}',value['ownerToken']))
    nonce(value['commandId']);identifier(value['runId']);identifier(value['ticket'])
    if kind in ('mapping','info','raw-server'):nonce(value['sourceJob']);need(value['relativePath'] in BUNDLES[value['resource']][1])
    if kind in ('observe','retire'):nonce(value['jobId'])
    return value


def stamp(value):exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']));return value


def clock_after(new,old):need(all(new[key]>=old[key] for key in ('epochMs','monotonicMs')))


def expected_path(query):return '/'+('e2e-' if query['namespace']=='original' else 'renamed-')+query['runId']+'/'+query['relativePath']


def events(source):
    job=source['job'];result=job['result'];kind=job['request']['operation'];stack=[];seen=set();messages={row['messageObject']:row for row in job['messages']}
    state=dict(started=False,sent=None,replies={},destroyed=False,expired=False,result=None);last=job['created'];observed=set();dead_messages=set()
    need(type(job['events']) is list and len(job['events'])<=128)
    for index,event in enumerate(job['events'],1):
        exact(event,{'sequence','eventId','kind','clock','details'});need(type(event['sequence']) is int and event['sequence']==index)
        native_id(event['eventId']);need(event['eventId'] not in seen);seen.add(event['eventId']);stamp(event['clock']);clock_after(event['clock'],last);clock_after(source['clock'],event['clock']);last=event['clock']
        tag=event['kind'];detail=event['details']
        if tag=='started':
            exact(detail,set());need(not state['started'] and not state['destroyed']);state['started']=True
        elif tag=='sent':
            exact(detail,{'operation','server','serverInstance','messageId','domainId','inputs'})
            need(state['started'] and not state['destroyed'] and state['sent'] is None and detail['operation']==('raw' if kind=='raw-server' else kind)
                and integer(detail['messageId'],1,2**32-1));identity(detail['server']);identity(detail['domainId']);native_id(detail['serverInstance'])
            inputs=detail['inputs'];wanted=job['inputs']
            if kind=='inventory':exact(inputs,set())
            elif kind=='mapping':exact(inputs,{'path'});need(inputs['path']==wanted['path'])
            elif kind=='info':exact(inputs,{'hash'});need(inputs['hash']==wanted['hash'])
            else:exact(inputs,{'hash','from','to'});need(inputs==dict(hash=wanted['hash'],**{'from':'0','to':wanted['size']}))
            state['sent']=event
        elif tag=='message-observed':
            exact(detail,{'messageObject','kind'});key=native_id(detail['messageObject']);need(state['sent'] is not None and not state['destroyed'] and key in messages and key not in observed
                and detail['kind']==messages[key]['kind']==('mapping' if kind in ('mapping','inventory') else 'raw' if kind=='raw-server' else 'info'))
            clock_after(event['clock'],messages[key]['observed']);observed.add(key)
        elif tag in ('mapping-reply','info-reply','raw-header','raw-body'):
            common={'sender','serverInstance','messageId','sameTarget','messageObject'}
            extra={'serverError','payload','messageComplete','messageFailed'} if tag=='mapping-reply' else (
                {'serverError','hash','size','messageBytes','messageComplete','messageFailed'} if tag=='info-reply' else
                {'serverError','hash','length'} if tag=='raw-header' else {'responseReceived','serverError','payload'})
            exact(detail,common|extra);need(state['sent'] is not None and not state['destroyed'] and tag not in state['replies'] and detail['messageObject'] in observed
                and type(detail['sameTarget']) is bool and integer(detail['serverError'],0,255))
            sent=state['sent']['details'];identity(detail['sender']);native_id(detail['serverInstance']);need(integer(detail['messageId'],1,2**32-1))
            if source['complete']:need(detail['sameTarget'] and detail['sender']==sent['server'] and detail['serverInstance']==sent['serverInstance'] and detail['messageId']==sent['messageId'])
            need((tag=='mapping-reply' and kind in ('inventory','mapping')) or (tag=='info-reply' and kind=='info') or (tag in ('raw-header','raw-body') and kind=='raw-server'))
            if tag in ('mapping-reply','info-reply'):need(type(detail['messageComplete']) is type(detail['messageFailed']) is bool)
            if tag in ('mapping-reply','raw-body'):wire.body(detail['payload'])
            if tag=='info-reply':
                wire.text(detail['hash'],64);need(re.fullmatch('[a-f0-9]{0,64}',detail['hash']) and type(detail['size']) is str and re.fullmatch('-?(?:0|[1-9][0-9]{0,19})',detail['size'])
                    and type(detail['messageBytes']) is str and re.fullmatch('0|[1-9][0-9]{0,19}',detail['messageBytes']))
            if tag=='raw-header':wire.text(detail['hash'],64);need(re.fullmatch('[a-f0-9]{0,64}',detail['hash']) and type(detail['length']) is str and re.fullmatch('-?(?:0|[1-9][0-9]{0,19})',detail['length']))
            if tag=='raw-body':need(type(detail['responseReceived']) is bool and 'raw-header' in state['replies'])
            state['replies'][tag]=event
        elif tag=='callback-enter':
            exact(detail,{'bodyId','callback','original'});native_id(detail['bodyId']);need(detail['callback'] in ('network','reader') and state['started'] and not state['destroyed'])
            need(not any(body==detail['bodyId'] for body,_ in stack))
            original=detail['original']
            if detail['callback']=='network':
                exact(original,{'responseReceived','serverError'});need(type(original['responseReceived']) is bool and integer(original['serverError'],0,255))
                if original['responseReceived']:
                    reply_kind='mapping-reply' if kind in ('mapping','inventory') else 'info-reply' if kind=='info' else 'raw-body'
                    need(reply_kind in state['replies'] and state['replies'][reply_kind]['details']['serverError']==original['serverError'])
            else:exact(original,set())
            stack.append((detail['bodyId'],event))
        elif tag=='callback-return':
            exact(detail,{'bodyId','normal'});need(stack and stack[-1][0]==detail['bodyId'] and detail['normal'] is True);stack.pop()
        elif tag=='result':
            exact(detail,{'bytes','sha256'});need(stack and not state['destroyed'] and state['result'] is None and integer(detail['bytes'],1));wire.sha(detail['sha256'])
            if result is not None:
                raw=wire.exact_result(job['resultBase64'],result,kind)
                need(detail['bytes']==len(raw) and detail['sha256']==hashlib.sha256(raw).hexdigest())
            else:need(not source['complete'] and detail['bytes']>160000)
            state['result']=event
        elif tag=='destroyed':exact(detail,set());need(not state['destroyed']);state['destroyed']=True
        elif tag=='retire-issued':exact(detail,set());need(not state.get('retire'));state['retire']=True
        elif tag=='token-expired-observed':
            exact(detail,set());need(not state['expired'] and job['tokenExpired'] is not None);clock_after(event['clock'],job['tokenExpired']);state['expired']=True
        elif tag=='message-expired-observed':
            exact(detail,{'messageObject'});key=detail['messageObject'];need(key in observed and key not in dead_messages and messages[key]['expired'] is not None)
            clock_after(event['clock'],messages[key]['expired']);dead_messages.add(key)
        else:need(False)
    need(job['pendingBodies']==len(stack) and job['alive'] is (not state['destroyed']) and job['retireIssued'] is bool(state.get('retire'))
        and job['tokenAlive'] is (not state['expired']) and observed==set(messages)
        and dead_messages=={key for key,row in messages.items() if not row['alive']})
    need((result is not None)==(state['result'] is not None) or not source['complete'])
    return state


def trace(value,query,pid):
    exact(value,{'iosAssetReplyTraceVersion','instance','sequence','processId','clock','layout','complete','job'})
    need(type(value['iosAssetReplyTraceVersion']) is int and value['iosAssetReplyTraceVersion']==VERSION and integer(value['sequence'],1)
        and type(value['processId']) is int and value['processId']==pid and type(value['complete']) is bool)
    native_id(value['instance']);stamp(value['clock']);need(value['layout']==dict(byteOrder='little',messageIdBytes=4,hashBytes=32,bakingStatusBytes=4))
    job=value['job'];exact(job,{'objectId','request','inputs','created','alive','pendingBodies','messages','tokenAlive','tokenExpired','retireIssued','events','result','resultBase64'})
    native_id(job['objectId']);command(job['request']);need(job['request']['operation'] in STARTS and all(query[key]==job['request'][key] for key in SCOPE)
        and job['request']['commandId']==(query['jobId'] if query['operation'] in ('observe','retire') else query['commandId'])
        and all(type(job[key]) is bool for key in ('alive','tokenAlive','retireIssued')) and integer(job['pendingBodies'],0,128))
    stamp(job['created']);clock_after(value['clock'],job['created'])
    if job['tokenExpired'] is not None:stamp(job['tokenExpired']);clock_after(value['clock'],job['tokenExpired']);clock_after(job['tokenExpired'],job['created'])
    need((job['tokenExpired'] is None)==job['tokenAlive'])
    inputs=job['inputs'];exact(inputs,{'path','hash','sourceJob','size'});kind=job['request']['operation']
    if kind=='inventory':need(all(item=='' for item in inputs.values()))
    else:
        need(inputs['path']==expected_path(job['request']) and inputs['sourceJob']==job['request']['sourceJob'])
        if inputs['hash']!='':wire.sha(inputs['hash'])
        if kind=='raw-server':need(type(inputs['size']) is str and re.fullmatch('[1-9][0-9]{0,4}',inputs['size']) and int(inputs['size'])<=32768)
        else:need(inputs['size']=='')
    need(type(job['messages']) is list and len(job['messages'])<=4);seen=set()
    for message in job['messages']:
        exact(message,{'messageObject','kind','sourceId','packetType','packetVersion','observed','alive','expired'})
        native_id(message['messageObject']);need(message['messageObject'] not in seen);seen.add(message['messageObject'])
        need(message['kind'] in ('mapping','info','raw') and type(message['alive']) is bool and integer(message['sourceId'],0,65535)
            and integer(message['packetType'],0,65535) and integer(message['packetVersion'],0,255))
        stamp(message['observed']);clock_after(message['observed'],job['created']);clock_after(value['clock'],message['observed'])
        if message['expired'] is not None:stamp(message['expired']);clock_after(message['expired'],message['observed']);clock_after(value['clock'],message['expired'])
        need(message['alive'] is (message['expired'] is None))
    if job['result'] is None:need(job['resultBase64'] is None)
    else:wire.exact_result(job['resultBase64'],job['result'],kind)
    events(value);return value


def validate(value,query,pid,epoch=None,previous=None,previous_job=None):
    command(query);exact(value,{'iosAssetsRepliesVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsRepliesVersion']) is int and value['iosAssetsRepliesVersion']==VERSION and value['requestId']==query['commandId']
        and value['runId']==query['runId'] and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and integer(value['sequence'],1,10**9) and value['clockDomain']=='native-main-assets-replies');native_id(value['instance'])
    a,b=stamp(value['clockBefore']),stamp(value['clockAfter']);clock_after(b,a)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500
        and abs((b['epochMs']-a['epochMs'])-(b['monotonicMs']-a['monotonicMs']))<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source=trace(value['source'],query,pid);need(a['epochMs']<=source['clock']['epochMs']<=b['epochMs'])
    if previous is not None:
        need(all(value[key]==previous[key] for key in ('instance','runId','processId')) and value['sequence']>previous['sequence']
            and source['instance']==previous['source']['instance'] and source['sequence']>previous['source']['sequence'])
        clock_after(a,previous['clockAfter']);clock_after(source['clock'],previous['source']['clock'])
    if previous_job is not None:
        old=previous_job['source']['job'];new=source['job'];need(all(same(old[key],new[key]) for key in ('objectId','request','inputs','created'))
            and new['events'][:len(old['events'])]==old['events'] and len(new['messages'])>=len(old['messages'])
            and (previous_job['source']['complete'] or not source['complete']) and (old['alive'] or not new['alive']) and (old['tokenAlive'] or not new['tokenAlive'])
            and (not old['retireIssued'] or new['retireIssued']))
        if old['tokenExpired'] is not None:need(same(old['tokenExpired'],new['tokenExpired']))
        if old['result'] is not None:need(same(old['result'],new['result']) and old['resultBase64']==new['resultBase64'])
        for first,last in zip(old['messages'],new['messages']):
            need(all(same(first[key],last[key]) for key in first if key not in ('alive','expired')) and (first['alive'] or not last['alive']))
            if first['expired'] is not None:need(same(first['expired'],last['expired']))
    return value


def drained(value):
    source=value['source'];job=source['job']
    return source['complete'] and not job['alive'] and not job['tokenAlive'] and job['pendingBodies']==0 and all(not row['alive'] for row in job['messages'])


def qualified(value):
    source=value['source'];job=source['job'];state=events(source);need(drained(value) and job['result'] is not None and state['sent'] is not None)
    kind=job['request']['operation'];result=job['result'];sent=state['sent']['details']
    expected='mapping-reply' if kind in ('inventory','mapping') else 'info-reply' if kind=='info' else 'raw-body'
    reply=state['replies'].get(expected);need(reply is not None);detail=reply['details']
    fresh(reply['clock']['epochMs'],value['clockAfter']['epochMs'])
    need(detail['sameTarget'] and detail['serverError']==0 and detail['sender']==sent['server'] and detail['serverInstance']==sent['serverInstance'] and detail['messageId']==sent['messageId'])
    network=[event for event in job['events'] if event['kind']=='callback-enter' and event['details']['callback']=='network']
    need(len(network)==1 and network[0]['details']['original']==dict(responseReceived=True,serverError=0))
    original=dict(kind=kind,path=job['inputs']['path'],hash=job['inputs']['hash'],captured=deepcopy(reply['clock']),
        binding={key:sent[key] for key in ('server','serverInstance','domainId')})
    if kind in ('inventory','mapping'):
        need(result['error']==0 and detail['messageComplete'] and not detail['messageFailed']);raw=wire.body(detail['payload'],required=True)
        if kind=='inventory':need(result['complete']);rows=wire.inventory(raw);need(same(rows,result['mappings']));original['mappings']=deepcopy(rows)
        else:parsed=wire.mapping(raw);need(all(same(parsed[key],result[key]) for key in parsed));original.update(parsed)
    elif kind=='info':
        need(result['responseReceived'] and result['serverError']==0 and detail['messageComplete'] and not detail['messageFailed']
            and detail['messageBytes']=='45' and result['hash']==detail['hash']==job['inputs']['hash']
            and result['size']==detail['size'] and 0<int(result['size'])<=32768)
        original['bytes']=int(result['size'])
    else:
        header=state['replies'].get('raw-header');need(header is not None);head=header['details'];size=int(job['inputs']['size'])
        need(result['responseReceived'] and result['serverError']==0 and detail['responseReceived'] and head['sameTarget'] and head['serverError']==0
            and head['sender']==sent['server'] and head['serverInstance']==sent['serverInstance'] and head['messageId']==sent['messageId']
            and head['hash']==job['inputs']['hash'] and head['length']==str(size) and head['messageObject']==detail['messageObject'])
        raw=wire.body(detail['payload'],required=True);got=wire.body(result['body'],required=True)
        need(raw==got and len(raw)==size and hashlib.sha256(raw).hexdigest()==job['inputs']['hash']);original['body']=deepcopy(detail['payload'])
    return original


class IOSAssetsReplies:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid;self.monotonic,self.sleep=monotonic,sleep
        self.last=None;self.jobs={}

    @operation
    def request(self,query,*,retain=None,retain_raw=None):
        command(query);need((retain is None or callable(retain)) and (retain_raw is None or callable(retain_raw)) and (retain is None or retain_raw is None));transport_check();need(self.guard() is not False)
        start=last=self.monotonic();requested=self.clock_ms();need(number(start,0,1e15) and integer(requested,1))
        self.send(deepcopy(query)) # Once only: polling uses new observe nonces.
        for attempt in range(61):
            transport_check();need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,last,start+1.5) and now-start<1.5);last=now
            if type(value) is dict and value.get('requestId')==query['commandId']:
                if retain_raw is not None:retain_raw(deepcopy(query),deepcopy(value),raw)
                if retain is not None:retain(deepcopy(query),deepcopy(value))
                job=query.get('jobId',query['commandId']);epoch=self.clock_ms();need(integer(epoch,requested))
                validate(value,query,self.pid,epoch,self.last,self.jobs.get(job));need(value['clockBefore']['epochMs']>=requested and self.guard() is not False)
                now=self.monotonic();need(number(now,last,start+1.5) and now-start<1.5)
                self.last=deepcopy(value);self.jobs[job]=deepcopy(value);return deepcopy(value)
            if attempt<60:self.sleep(.025)
        raise NativeUIError('Original Assets reply source did not produce this request')
