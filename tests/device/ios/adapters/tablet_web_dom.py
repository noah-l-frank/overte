"""Strict actual UIKit Tablet DOM originals; no World DOM translation.

DOM trust and editor snapshots alone prove neither native authority nor page
pixels. Actual native view/document/source and input ownership must be joined.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from ios.adapters.places_model import text
from ios.adapters import tablet_web_source as native

VERSION=1
DOM_VERSION=1
SOURCE_SHA256='50d6c55a46c1e8813e6fa6f600f253fc0887c964813679ea5ec60cf616419791'
ACTION='feature-ios-tablet-web-dom'
FILE=ACTION+'.json'
BODY_LIMIT=1048576
LIMIT=2097152
BASE_IDS={'text','bridge','back','reload','foreign','navigate','feature-marker','same-origin'}
OPTIONAL_IDS={'recovery','reference'}
EVENTS={'pointerdown','pointerup','pointercancel','click','input','focusin','focusout','compositionstart','compositionupdate','compositionend'}


def command(value):
    need(type(value) is dict and value.get('action')==ACTION);native.command(dict(value,action=native.ACTION));return value


def field(value,limit):
    text(value,limit*4);need(len(value.encode('utf-16-le'))//2<=limit);return value


def body(value,query,epoch,previous=None):
    command(query);exact(value,{'iosTabletWebDOMVersion','requestId','instance','sequence','capturedEpochMs','document','editor','elements','compositions','events','echoes'})
    need(type(value['iosTabletWebDOMVersion']) is int and value['iosTabletWebDOMVersion']==DOM_VERSION and value['requestId']==query['commandId']
        and integer(value['sequence'],1));native.sources.identifier(value['instance']);fresh(value['capturedEpochMs'],epoch)
    need(len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=BODY_LIMIT)
    doc=value['document'];exact(doc,{'runId','href','responseId','readyState','title','width','height','scroll','visualViewport'})
    need(doc['runId']==query['runId'] and doc['readyState']=='complete' and text(doc['href'],131072))
    text(doc['title'],4096)
    if doc['responseId'] is not None:native.sources.identifier(doc['responseId'])
    need(all(number(doc[k],1,16384) for k in ('width','height')) and type(doc['scroll']) is list and len(doc['scroll'])==2
        and all(number(v,-1e6,1e6) for v in doc['scroll']))
    viewport=doc['visualViewport'];exact(viewport,{'width','height','offsetLeft','offsetTop','pageLeft','pageTop','scale'})
    need(all(number(viewport[k],.01,16384) for k in ('width','height')) and number(viewport['scale'],.01,100)
        and all(number(viewport[k],-1e6,1e6) for k in ('offsetLeft','offsetTop','pageLeft','pageTop')))
    editor=value['editor'];exact(editor,{'text','focused'});field(editor['text'],512);need(type(editor['focused']) is bool)
    need(type(value['elements']) is list and len(BASE_IDS)<=len(value['elements'])<=len(BASE_IDS|OPTIONAL_IDS));ids=set();births=set();by_id={}
    for row in value['elements']:
        exact(row,{'id','birth','tag','type','value','focused','rect','enabled','visible','href','accessibilityLabel'})
        need(row['id'] in BASE_IDS|OPTIONAL_IDS and row['id'] not in ids and integer(row['birth'],1,2048) and row['birth'] not in births)
        ids.add(row['id']);births.add(row['birth']);by_id[row['id']]=row
        text(row['tag'],32);text(row['type'],32)
        need(all(type(row[k]) is bool for k in ('focused','enabled','visible')) and type(row['rect']) is list and len(row['rect'])==4
            and all(number(v,-1e6,1e6) for v in row['rect']))
        if row['id'] in ('text','foreign'):
            need(row['tag']=='INPUT' and row['type']==('text' if row['id']=='text' else 'url'));field(row['value'],512 if row['id']=='text' else 8192)
        else:need(row['value'] is None)
        for key in ('href','accessibilityLabel'):
            if row[key] is not None:text(row[key],131072 if key=='href' else 512)
        if row['visible']:
            left,top,right,bottom=row['rect'];need(viewport['offsetLeft']<=left<right<=viewport['offsetLeft']+viewport['width']
                and viewport['offsetTop']<=top<bottom<=viewport['offsetTop']+viewport['height'])
    need(BASE_IDS<=ids and by_id['text']['value']==editor['text'] and by_id['text']['focused']==editor['focused'] and sum(row['focused'] for row in value['elements'])<=1)
    need(type(value['events']) is list and len(value['events'])<=1024);last=0;compositions={}
    for index,event in enumerate(value['events'],1):
        exact(event,{'ordinal','kind','capturedEpochMs','eventTimeMs','trusted','target','x','y','pointerId','pointerType','composing'})
        need(type(event['ordinal']) is int and event['ordinal']==index and type(event['kind']) is str and event['kind'] in EVENTS
            and integer(event['capturedEpochMs'],max(1,last),value['capturedEpochMs']) and number(event['eventTimeMs'],0,1e15) and type(event['trusted']) is bool)
        last=event['capturedEpochMs'];target=event['target'];exact(target,{'id','birth'})
        need(target['id'] is None or target['id'] in BASE_IDS|OPTIONAL_IDS)
        need(target['birth'] is target['id'] is None or integer(target['birth'],1,2048))
        point=event['kind'] in ('pointerdown','pointerup','pointercancel','click');pointer=event['kind'].startswith('pointer')
        if point:need(number(event['x'],-1e6,1e6) and number(event['y'],-1e6,1e6))
        else:need(event['x'] is event['y'] is None)
        if pointer:need(integer(event['pointerId'],0) and event['pointerType'] in ('touch','mouse','pen',''))
        else:need(event['pointerId'] is event['pointerType'] is None)
        if event['kind'].startswith('composition'):
            need(type(event['composing']) is bool and event['composing']==(event['kind']!='compositionend'))
            if target['birth'] is not None:compositions[target['birth']]=event['composing']
        else:need(event['composing'] is None)
    need(type(value['compositions']) is list and len(value['compositions'])<=2048)
    for row in value['compositions']:
        exact(row,{'target','active'});need(integer(row['target'],1,2048) and type(row['active']) is bool)
    need(value['compositions']==[dict(target=target,active=active) for target,active in compositions.items()])
    need(type(value['echoes']) is list and len(value['echoes'])<=64);seen=set();last=0
    for echo in value['echoes']:
        exact(echo,{'sequence','surface','message','receivedEpochMs','observedEpochMs'})
        need(integer(echo['sequence'],1,1000000) and echo['sequence'] not in seen and echo['surface']=='tablet'
            and integer(echo['receivedEpochMs'],max(1,last),value['capturedEpochMs']) and integer(echo['observedEpochMs'],echo['receivedEpochMs'],value['capturedEpochMs']))
        field(echo['message'],4096);message=decode(echo['message']);exact(message,{'contract','action','sequence','surface'})
        need(message['contract']=='overte-web-parity-v1' and message['action']=='echo' and message['surface']=='tablet'
            and type(message['sequence']) is int and message['sequence']==echo['sequence'])
        seen.add(echo['sequence']);last=echo['receivedEpochMs']
    if previous is not None:
        body(previous,dict(query,commandId=previous['requestId']),previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and value['capturedEpochMs']>=previous['capturedEpochMs'])
        # Scroll/viewport/title can really change. Actual document ownership,
        # response and URL remain the same in a retained JavaScript document.
        for key in ('runId','href','responseId'):need(doc[key]==previous['document'][key])
        for key in ('events','echoes'):need(value[key][:len(previous[key])]==previous[key])
    return value



def continuity(previous,value):
    if previous is None:return
    need(value['instance']==previous['instance'] and all(value[k]==previous[k] for k in ('runId','fixtureUrl','processId')))
    if value['commandId']==previous['commandId']:
        need(value['sequence']==previous['sequence'] and value['clockBefore']==previous['clockBefore'])
        native.sources.stamp(value['clockAfter'],floor=previous['clockAfter'])
        if previous['status']!='pending':need(value==previous)
    else:
        need(value['sequence']>previous['sequence']);native.sources.stamp(value['clockBefore'],floor=previous['clockAfter'])


def validate(value,query,pid,epoch=None,previous=None):
    from ios.adapters.tablet_web_presentation import current
    command(query);exact(value,{'iosTabletWebDOMNativeVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','status','source'})
    need(type(value['iosTabletWebDOMNativeVersion']) is int and value['iosTabletWebDOMNativeVersion']==VERSION
        and all(value[k]==query[k] for k in ('commandId','runId','fixtureUrl')) and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-tablet-web-dom' and value['status'] in ('pending','ready','unavailable')
        and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    native.sources.identifier(value['instance']);a,b=native.sources.stamp(value['clockBefore']),native.sources.stamp(value['clockAfter'])
    native.sources.stamp(b,floor=a)
    if epoch is not None:fresh(b['epochMs'],epoch)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid);continuity(previous,value)
    if value['status']!='ready':exact(value['source'],set());return value
    need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    source=value['source'];exact(source,{'nativeView','nativeFinishedEpochMs','observerSha256','inlineLease','http','presentationBefore','presentationAfter','dom'})
    view=source['nativeView'];native.identity(view,query)
    need(all(view[k] for k in ('creation','grant','page','nonce')) and source['observerSha256']==SOURCE_SHA256
        and type(source['inlineLease']) is bool and integer(source['nativeFinishedEpochMs'],1,b['epochMs']))
    observed=source['dom'];body(observed,query,b['epochMs']);need(a['epochMs']<=observed['capturedEpochMs']<=b['epochMs']
        and source['nativeFinishedEpochMs']<=observed['capturedEpochMs'] and observed['document']['href']==view['url'])
    current(source['presentationBefore']);current(source['presentationAfter']);need(source['presentationBefore']==source['presentationAfter'])
    if source['inlineLease']:
        need(source['http'] is observed['document']['responseId'] is None and view['source']['carrier'] is not None)
        need(view['url']==view['sourceUrl'] and re.fullmatch(r'http://[0-9a-f]{32}\.overte-inline\.invalid/index\.html',view['sourceUrl']))
    else:
        http=source['http'];exact(http,{'status','responseId','url'});native.sources.identifier(http['responseId'])
        need(type(http['status']) is int and http['status'] in (200,404) and http['url']==view['url']
            and http['responseId']==observed['document']['responseId'] and view['source']['carrier'] is view['source']['binding'] is None)
    if previous is not None and previous['status']=='ready' and value['commandId']!=previous['commandId']:
        old=previous['source'];old_view=old['nativeView']
        if native.document_key(view)==native.document_key(old_view):
            need(view==old_view and source['nativeFinishedEpochMs']==old['nativeFinishedEpochMs'] and source['http']==old['http']
                and source['inlineLease']==old['inlineLease'] and source['presentationAfter']['view']==old['presentationAfter']['view'])
            body(observed,query,b['epochMs'],old['dom'])
        else:
            need(observed['instance']!=old['dom']['instance'] and view['nonce']!=old_view['nonce'])
            if view['handle']==old_view['handle'] and view['creation']==old_view['creation']:
                need(source['presentationAfter']['view']==old['presentationAfter']['view'])
            else:need(source['presentationAfter']['view']!=old['presentationAfter']['view'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def join_sources(value,sources):
    original(value);native.sources.original(sources);need(value['status']=='ready' and sources['complete']
        and all(value[k]==sources[k] for k in ('runId','fixtureUrl','processId')))
    view=value['source']['nativeView'];ref=view['source'];rows=[row for row in sources['navigations'] if row['id']==ref['navigation']]
    need(len(rows)==1);navigation=rows[0]
    need(navigation['root']==ref['root'] and navigation.get('returned',{}).get('invoked') is True
        and navigation['returned']['clock']['epochMs']<=value['clockBefore']['epochMs'])
    if navigation['kind']=='http':need(view['sourceUrl']==navigation['sourceUrl'] and not value['source']['inlineLease'])
    else:
        need(value['source']['inlineLease']);rows=[row for row in sources['carriers'] if row['id']==ref['carrier']];need(len(rows)==1);carrier=rows[0]
        need(carrier['navigation']==ref['navigation'] and carrier['root']==ref['root'] and carrier['identity']==view['sourceIdentity'])
        rows=[row for row in carrier['bindings'] if row['id']==ref['binding']];need(len(rows)==1);binding=rows[0]
        need(binding['transportUrl']==view['sourceUrl'] and 'returned' in binding
            and binding['returned']['epochMs']<=value['clockBefore']['epochMs'])
    return deepcopy(value)


class IOSTabletWebDOM(native.IOSTabletWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _limit=LIMIT
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.accepted=None
    def _validate(self,value,query,pid,epoch=None,previous=None):
        validate(value,query,pid,epoch,previous);continuity(self.accepted,value);self.accepted=deepcopy(value)
    @staticmethod
    def _ready(value):need(value['status']!='unavailable');return value['status']=='ready'
