"""Current original world WK/DOM acquisition, including normal untrusted input.

Untrusted events alone establish no input or bridge verdict. The cumulative
native transcript and exact document/response join remain mandatory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_web_dom import dom as legacy_dom
from ios.adapters.places_model import text
from ios.adapters import world_web_source as native

VERSION=1
ACTION='feature-ios-world-web-dom'
FILE=ACTION+'.json'
LIMIT=262144
SOURCE_SHA256='5737bc97d9bfaffb10a6f0a574e5ab92d5b9492a2cb99fe8802fe041cc906ae1'
IDS={'text','bridge','back','reload','foreign','navigate','recovery','reference','feature-marker','same-origin'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','fixtureUrl'});need(value['action']==ACTION)
    native.command(dict(value,action=native.ACTION));return value


def dom(value,query,epoch):
    exact(value,{'iosWorldWebDOMVersion','requestId','instance','sequence','capturedEpochMs','document','editor','elements','events','echoes'})
    need(type(value['iosWorldWebDOMVersion']) is int and value['iosWorldWebDOMVersion']==1
        and value['requestId']==query['commandId'] and type(value['instance']) is str and re.fullmatch(native.HEX,value['instance'])
        and integer(value['sequence'],1));fresh(value['capturedEpochMs'],epoch)
    document=value['document'];exact(document,{'runId','href','responseId','readyState','title','width','height'})
    need(document['runId']==query['runId'] and re.fullmatch(native.HEX,text(document['responseId'],32))
        and document['readyState']=='complete' and number(document['width'],1,2048) and number(document['height'],1,2048))
    text(document['href'],131072);text(document['title'],4096)
    editor=value['editor'];exact(editor,{'text','focused'});text(editor['text'],512)
    need(len(editor['text'].encode('utf-16-le'))//2<=512 and type(editor['focused']) is bool)
    need(type(value['elements']) is list and len(value['elements'])==len(IDS));ids=set();births=set()
    for row in value['elements']:
        exact(row,{'id','birth','tag','type','rect','enabled','visible','href'})
        need(row['id'] in IDS and row['id'] not in ids and integer(row['birth'],1,1024) and row['birth'] not in births)
        ids.add(row['id']);births.add(row['birth']);text(row['tag'],32);text(row['type'],32)
        need(type(row['rect']) is list and len(row['rect'])==4 and all(number(v,-1e6,1e6) for v in row['rect'])
            and type(row['enabled']) is bool and type(row['visible']) is bool and (row['href'] is None or type(row['href']) is str))
        if row['visible']:
            l,t,r,b=row['rect'];need(0<=l<r<=document['width'] and 0<=t<b<=document['height'])
    need(type(value['events']) is list and len(value['events'])<=1024);last=0
    for index,event in enumerate(value['events'],1):
        exact(event,{'ordinal','kind','capturedEpochMs','eventTimeMs','trusted','target','x','y','button','key'})
        need(type(event['ordinal']) is int and event['ordinal']==index and event['kind'] in ('mousedown','mouseup','click','keydown','input')
            and integer(event['capturedEpochMs'],max(1,last),value['capturedEpochMs']) and number(event['eventTimeMs'],0,1e15)
            and type(event['trusted']) is bool);last=event['capturedEpochMs']
        target=event['target'];exact(target,{'id','birth'})
        need(target['id'] is None or target['id'] in IDS)
        need(target['birth'] is None and target['id'] is None or integer(target['birth'],1,1024))
        if event['kind'] in ('mousedown','mouseup','click'):
            need(number(event['x'],-1e6,1e6) and number(event['y'],-1e6,1e6) and integer(event['button'],0,4) and event['key'] is None)
        else:
            need(event['x'] is event['y'] is event['button'] is None)
            if event['kind']=='keydown':text(event['key'],512)
            else:need(event['key'] is None)
    # Reuse only the common pure echo grammar, retaining each actual displayed
    # original handler result and message timestamp. No trust filter changes.
    old=dict(webDOMVersion=1,requestId=query['commandId'],instance=value['instance'],sequence=value['sequence'],
        capturedEpochMs=value['capturedEpochMs'],document={key:document[key] for key in ('runId','href','responseId','readyState')},
        editor=deepcopy(editor),attempts=[],echoes=deepcopy(value['echoes']))
    legacy_dom(old,dict(commandId=query['commandId'],runId=query['runId'],surface='world'),epoch)
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosWorldWebDOMNativeVersion','commandId','runId','surface','instance','sequence','processId','capturedEpochMs','status','source'})
    need(type(value['iosWorldWebDOMNativeVersion']) is int and value['iosWorldWebDOMNativeVersion']==VERSION
        and value['commandId']==query['commandId'] and value['runId']==query['runId'] and value['surface']=='world'
        and type(value['instance']) is str and re.fullmatch(native.HEX,value['instance']) and integer(value['sequence'],1)
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and value['status'] in ('pending','ready','unavailable') and integer(value['capturedEpochMs'],1))
    if epoch is not None:fresh(value['capturedEpochMs'],epoch)
    if value['status']!='ready':exact(value['source'],set());return value
    exact(value['source'],{'nativeView','dom'});view=value['source']['nativeView'];observed=value['source']['dom']
    exact(view,{'handle','creation','grant','page','url','nativeFinished','httpErrorStatus','inlineLease','sourceUrl','sourceIdentity',
        'httpStatus','responseId','nonce','finishedEpochMs','observerSha256'})
    native.identity({key:view[key] for key in ('handle','creation','grant','page','nonce','url','sourceUrl','sourceIdentity')}|dict(surface='world-entity'),query)
    need(all(view[key] for key in ('creation','grant','page','nonce')) and view['nativeFinished'] is True and view['inlineLease'] is False
        and type(view['httpStatus']) is int and view['httpStatus'] in (200,404)
        and type(view['httpErrorStatus']) is int and view['httpErrorStatus']==(404 if view['httpStatus']==404 else 0)
        and re.fullmatch(native.HEX,text(view['responseId'],32)) and view['observerSha256']==SOURCE_SHA256
        and integer(view['finishedEpochMs'],1,value['capturedEpochMs']))
    dom(observed,query,value['capturedEpochMs'])
    need(view['url']==observed['document']['href'] and view['responseId']==observed['document']['responseId'])
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        old=previous['source']['nativeView'];old_dom=previous['source']['dom']
        need(value['capturedEpochMs']>=previous['capturedEpochMs'])
        if value['instance']==previous['instance']:need(value['sequence']>previous['sequence'] and view['handle']==old['handle'])
        else:need(view['handle']!=old['handle'])
        if native.document_key(view)==native.document_key(old):
            need(view==old and observed['instance']==old_dom['instance'] and observed['sequence']>old_dom['sequence']
                and observed['capturedEpochMs']>=old_dom['capturedEpochMs'] and observed['document']==old_dom['document'])
            for key in ('events','echoes'):need(observed[key][:len(old_dom[key])]==old_dom[key])
        else:need(observed['instance']!=old_dom['instance'] and view['nonce']!=old['nonce'])
    return value


def original(value):
    view=value['source']['nativeView'];url=view['sourceUrl'];root=url[:url.index('/tickets/')+1]
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=root),value['processId'])


class IOSWorldWebDOM(native.IOSWorldWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
    @staticmethod
    def _bounds(value):return value['capturedEpochMs'],value['capturedEpochMs']
    @staticmethod
    def _ready(value):need(value['status']!='unavailable');return value['status']=='ready'
