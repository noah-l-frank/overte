"""Actual native document/server response and original normal-input joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import urlsplit,urlunsplit
from adapters.native_feature_observation import exact,integer,need,number
from ios.adapters.places_model import text
from ios.adapters import world_web_source as native,world_web_dom as dom


def browser_original(value,previous=None):
    exact(value,{'browserFixtureVersion','instance','ready','sequence','responses'})
    need(type(value['browserFixtureVersion']) is int and value['browserFixtureVersion']==1
        and re.fullmatch(native.HEX,text(value['instance'],32)) and type(value['ready']) is bool
        and integer(value['sequence'],0,256) and type(value['responses']) is list and len(value['responses'])==value['sequence'])
    ids=set();last=0
    for index,row in enumerate(value['responses'],1):
        exact(row,{'sequence','responseId','capturedEpochMs','ticket','resource','origin','status','bytes','sha256'})
        need(type(row['sequence']) is int and row['sequence']==index and integer(row['capturedEpochMs'],max(1,last))
            and re.fullmatch(native.HEX,text(row['responseId'],32)) and row['responseId'] not in ids
            and re.fullmatch(native.HEX,text(row['ticket'],32)) and row['origin'] in ('primary','foreign')
            and row['resource'] in ('index.html','reference.html','page-b.html','recovery.html','reference.js','client.js','injected.js','feature-marker.js')
            and type(row['status']) is int and row['status'] in (200,404) and integer(row['bytes'],1,1048576)
            and re.fullmatch('[0-9a-f]{64}',text(row['sha256'],64)))
        ids.add(row['responseId']);last=row['capturedEpochMs']
    if previous is not None:
        browser_original(previous)
        need(value['instance']==previous['instance'] and value['sequence']>=previous['sequence']
            and value['responses'][:len(previous['responses'])]==previous['responses'] and (not previous['ready'] or value['ready']))
    return value


def origin(value):
    parsed=urlsplit(text(value,512));parsed.port
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is parsed.password is None
        and not parsed.query and not parsed.fragment and parsed.path in ('','/') and urlunsplit(parsed)==value)
    return parsed.scheme,parsed.netloc


def current_document(ledger,document,browser,origins):
    native.original(ledger);dom.original(document);browser_original(browser);exact(origins,{'primary','foreign'})
    need(ledger['complete'] and ledger['runId']==document['runId'] and ledger['processId']==document['processId']
        and origin(origins['primary'])!=origin(origins['foreign']))
    view=document['source']['nativeView'];key=native.document_key(view)
    documents=native.completed_documents(ledger);matched=[row for row in documents if native.document_key(row['identity'])==key]
    need(len(matched)==1);actual=matched[0];response=actual['response']['detail']
    need(actual['identity']['url']==view['url'] and response['responseId']==view['responseId']
        and response['status']==view['httpStatus']
        and actual['finished']['clock']['epochMs']<=view['finishedEpochMs']<=actual['verified']['clock']['epochMs'])
    installed=[row for row in ledger['events'] if row['kind']=='dom-observer-installed'
        and native.document_key(row['identity'])==key and row['sequence']<actual['verified']['sequence']]
    need(len(installed)==1 and installed[0]['detail']['sourceSha256']==view['observerSha256']
        ==dom.SOURCE_PINS[document['source']['dom']['iosWorldWebDOMVersion']])
    rows=[row for row in browser['responses'] if row['responseId']==response['responseId']]
    need(len(rows)==1);receipt=rows[0];need(receipt['resource'] in ('index.html','reference.html','page-b.html','recovery.html')
        and receipt['status']==response['status'])
    parsed=urlsplit(view['url']);base=urlsplit(ledger['fixtureUrl']);selected=urlsplit(origins[receipt['origin']])
    need((parsed.scheme,parsed.netloc)==(selected.scheme,selected.netloc)
        and not parsed.query and not parsed.fragment and parsed.username is parsed.password is None
        and parsed.path==base.path+'tickets/'+receipt['ticket']+'/'+receipt['resource'])
    # URL/header/body opaque IDs are all actual consumed native/DOM originals.
    # A host GET or the recovery ready flag cannot replace any of these joins.
    return dict(document=deepcopy(actual),response=deepcopy(receipt),documentLoads=len(documents),
        page='foreign' if receipt['origin']=='foreign' else 'B' if receipt['resource']=='page-b.html'
            else 'recovery' if receipt['resource']=='recovery.html' else 'reference',origin=receipt['origin'])


def attempts(ledger,document):
    native.original(ledger);dom.original(document);need(ledger['complete'])
    view=document['source']['nativeView'];key=native.document_key(view);observed=document['source']['dom']
    native_events=[row for row in ledger['events'] if native.document_key(row['identity'])==key]
    entered={row['detail']['entry']:row for row in native_events if row['kind']=='callback-enter'}
    returned={row['detail']['entry']:row for row in native_events if row['kind']=='callback-return'}
    candidates=[row for row in native_events if row['kind']=='pointer-enter' and row['detail']['type']=='release']
    result=[];used=set()
    for index,click in enumerate(observed['events']):
        if click['kind']!='click' or click['target']['id']!='bridge':continue
        need(index>0);up=observed['events'][index-1]
        # HTMLElement.click() in the actual reviewed native route has zero
        # client coordinates. Its preceding actual MouseEvent retains x/y.
        need(up['kind']=='mouseup' and up['target']==click['target'] and click['ordinal']==up['ordinal']+1
            and up['button']==click['button']==0 and up['trusted'] is click['trusted'] is False)
        matches=[]
        for row in candidates:
            entry=row['sequence'];detail=row['detail']
            if entry not in entered or entry not in returned or entered[entry]['detail']['result']['error']:continue
            x=detail['x']*min(detail['width'],2048)/detail['width'];y=detail['y']*min(detail['height'],2048)/detail['height']
            if (abs(x-up['x'])<=.01 and abs(y-up['y'])<=.01
                and row['clock']['epochMs']<=up['capturedEpochMs']<=click['capturedEpochMs']
                    <=entered[entry]['clock']['epochMs']<=returned[entry]['clock']['epochMs']):matches.append(row)
        need(len(matches)==1 and matches[0]['sequence'] not in used);used.add(matches[0]['sequence'])
        result.append(dict(domInstance=observed['instance'],ordinal=click['ordinal'],click=deepcopy(click),
            mouseup=deepcopy(up),nativeDispatch=deepcopy(matches[0]),nativeReturn=deepcopy(returned[matches[0]['sequence']])))
    return result
