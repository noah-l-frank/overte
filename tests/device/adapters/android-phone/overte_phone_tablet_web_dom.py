"""Phone-only inline DOM source joined to the original native document lease.

This separate command leaves the public HTTP-only DOM reader unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import re
from adapters.native_feature_observation import exact,integer,need,fresh
from adapters.native_web_dom import validate as http_validate,dom
from feature_journeys.contract import identifier


def validate(value,request,pid,epoch):
    need(request['action']=='feature-phone-tablet-dom-observe' and request['surface']=='tablet')
    original=request|{'action':'feature-web-dom-observe'}
    clean=deepcopy(value)
    if value.get('status')=='ready':
        document=clean['source']['dom']['document'];title=document.pop('title')
        need(type(title) is str and 0<len(title)<=512 and not any(ord(c)<32 or ord(c)==127 for c in title))
    if 'inline' not in value.get('source',{}):
        http_validate(clean,original,pid,epoch);return value
    exact(value,{'webNativeVersion','commandId','runId','surface','instance','sequence','processId','capturedEpochMs','status','source'})
    need(type(value['webNativeVersion']) is int and value['webNativeVersion']==1 and value['status']=='ready'
        and value['commandId']==request['commandId'] and value['runId']==request['runId'] and value['surface']=='tablet'
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1))
    identifier(value['instance']);fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'nativeView','dom','inline'})
    view=source['nativeView'];lease=source['inline']
    exact(view,{'handle','creation','grant','page','url','nativeFinished','httpErrorStatus','inlineLease','sourceUrl','sourceIdentity'})
    need(type(view['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',view['handle'])
        and all(integer(view[k],1) for k in ('creation','grant','page')) and view['nativeFinished'] is True
        and type(view['httpErrorStatus']) is int and view['httpErrorStatus']==0 and view['inlineLease'] is True
        and type(view['sourceIdentity']) is str and view['sourceIdentity'].startswith('tablet:') and len(view['sourceIdentity'])<=512)
    exact(lease,{'token','revision','transportUrl','sourceSha256','bodySha256','bytes','charset','scriptUrl','current'})
    identifier(lease['token']);need(integer(lease['revision'],1) and lease['current'] is True and lease['charset']=='utf-8')
    need(lease['transportUrl']=='http://'+lease['token']+'.overte-inline.invalid/index.html'
        and view['url']==lease['transportUrl'] and type(view['sourceUrl']) is str
        and view['sourceUrl'].startswith('data:text/html;charset=utf-8;base64,') and len(view['sourceUrl'])<=131072)
    raw=base64.b64decode(view['sourceUrl'].split(',',1)[1],validate=True)
    need(integer(lease['bytes'],1,131072) and lease['bytes']==len(raw)
        and hashlib.sha256(raw).hexdigest()==lease['bodySha256']
        and hashlib.sha256(view['sourceUrl'].encode()).hexdigest()==lease['sourceSha256']
        and ('<meta name="overte-fixture-owner" content="'+request['runId']+'">').encode() in raw
        and type(lease['scriptUrl']) is str and lease['scriptUrl'].startswith(request['fixtureUrl']+'tickets/')
        and re.fullmatch('[0-9a-f]{32}/injected\\.js',lease['scriptUrl'][len(request['fixtureUrl']+'tickets/'):]))
    dom(clean['source']['dom'],original,value['capturedEpochMs'])
    need(source['dom']['document']['href']==view['url'] and source['dom']['document']['responseId'] is None)
    return value
