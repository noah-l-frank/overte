"""Separate original Tablet native callback/resource history, including inline.

The source preserves actual synthetic URLs and native SourceStamp provenance.
It is not an HTTP WebClosures DTO and cannot prove UIKit touch/GPU OS caches.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters import tablet_web_source as native
from ios.adapters.web_closures import KINDS,resources_for

VERSION=1
ACTION='feature-ios-tablet-web-closures'
FILE=ACTION+'.json'
LIMIT=1048576
RESOURCES=resources_for(5)
REQUIRED={'policy-grant','native-view','native-delegate','native-presentation'}


def command(value):
    need(type(value) is dict and value.get('action')==ACTION);native.command(dict(value,action=native.ACTION));return value


def descriptor(value,query):
    exact(value,{'handle','creation','grant','page','surface','identitySha256','sourceUrl','source'})
    need(integer(value['handle'],1) and integer(value['creation']) and integer(value['grant'],1) and integer(value['page'])
        and value['surface']=='tablet' and type(value['identitySha256']) is str and re.fullmatch('[0-9a-f]{64}',value['identitySha256']))
    native.source_reference(value['source'],query);url=value['sourceUrl'];need(type(url) is str)
    if value['source']['carrier'] is None:
        prefix=query['fixtureUrl']+'tickets/';need(url.startswith(prefix) and re.fullmatch(native.HEX+r'/(?:index|reference)\.html',url[len(prefix):]))
    else:need(re.fullmatch(r'http://[0-9a-f]{32}\.overte-inline\.invalid/index\.html',url))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosTabletWebClosuresVersion','commandId','runId','fixtureUrl','instance','sequence','processId','capturedEpochMs','complete','contexts'})
    need(type(value['iosTabletWebClosuresVersion']) is int and value['iosTabletWebClosuresVersion']==VERSION
        and all(value[k]==query[k] for k in ('commandId','runId','fixtureUrl')) and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['sequence'],1) and type(value['complete']) is bool and type(value['contexts']) is list and len(value['contexts'])<=1024
        and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    native.sources.identifier(value['instance']);fresh(value['capturedEpochMs'],value['capturedEpochMs'] if epoch is None else epoch)
    ordinal=0;descriptors=set()
    for row in value['contexts']:
        exact(row,{'id','descriptor','createdEpochMs','updatedEpochMs','callbacks','resources'})
        need(integer(row['id'],ordinal+1) and integer(row['createdEpochMs'],1,value['capturedEpochMs'])
            and integer(row['updatedEpochMs'],row['createdEpochMs'],value['capturedEpochMs']));ordinal=row['id']
        descriptor(row['descriptor'],query);key=json.dumps(row['descriptor'],sort_keys=True,separators=(',',':'))
        need(key not in descriptors);descriptors.add(key);exact(row['callbacks'],KINDS);exact(row['resources'],RESOURCES)
        for counter in list(row['callbacks'].values())+list(row['resources'].values()):
            exact(counter,{'created','retired','pending'});need(integer(counter['created']) and integer(counter['retired'],0,counter['created'])
                and integer(counter['pending']) and counter['pending']==counter['created']-counter['retired'])
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']
            and value['capturedEpochMs']>=previous['capturedEpochMs'] and len(value['contexts'])>=len(previous['contexts'])
            and (previous['complete'] or not value['complete']))
        for old,new in zip(previous['contexts'],value['contexts']):
            need(all(new[k]==old[k] for k in ('id','descriptor','createdEpochMs')) and new['updatedEpochMs']>=old['updatedEpochMs'])
            for collection in ('callbacks','resources'):
                for key,before in old[collection].items():
                    after=new[collection][key];need(after['created']>=before['created'] and after['retired']>=before['retired'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def join_sources(value,sources,transcript):
    """Original source/carrier and native grant/frame associations, no alias DTO."""
    original(value);native.join_sources(transcript,sources)
    need(value['complete'] and all(value[k]==sources[k]==transcript[k] for k in ('runId','fixtureUrl','processId')))
    for row in value['contexts']:
        item=row['descriptor'];ref=item['source'];matches=[]
        for event in transcript['events']:
            view=event['identity']
            if not (view['handle']==str(item['handle']) and view['grant']==item['grant'] and view['source']==ref and view['sourceUrl']==item['sourceUrl']
                    and hashlib.sha256(view['sourceIdentity'].encode()).hexdigest()==item['identitySha256']):continue
            if event['kind']=='view-created' and view['page']==item['page']:
                if view['creation']==item['creation'] and event['clock']['epochMs']<=row['createdEpochMs']:matches.append(event)
                elif view['creation']==item['creation']+1 and row['createdEpochMs']<=event['clock']['epochMs']:matches.append(event)
            elif view['creation']==item['creation'] and view['page']==item['page'] and event['clock']['epochMs']<=row['createdEpochMs']:
                matches.append(event)
        need(matches)
        # The native trace source itself joins the exact original input and
        # decoded inline bytes/carrier/binding, including invocation returns.
    return deepcopy(value)


def drained(value,admitted):
    original(admitted);validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'],previous=admitted)
    need(admitted['complete'] and value['complete'] and admitted['contexts']
        and all(any(row['resources'][key]['created']>0 for row in admitted['contexts']) for key in REQUIRED)
        and any(row['callbacks']['javascript']['created']>0 for row in admitted['contexts'])
        and all(counter['pending']==0 for row in value['contexts'] for counter in list(row['callbacks'].values())+list(row['resources'].values())))
    return deepcopy(value['contexts'])


class IOSTabletWebClosures(native.IOSTabletWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
    @staticmethod
    def _bounds(value):return value['capturedEpochMs'],value['capturedEpochMs']
    @staticmethod
    def _ready(value):need(value['complete']);return True
