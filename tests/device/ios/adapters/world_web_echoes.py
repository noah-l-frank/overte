"""Actual DOM/native/VM/page echo chain, without requested counts or ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib
from adapters.native_feature_observation import exact,integer,need
from ios.adapters import world_web_source as native,world_web_dom as dom,world_web_work as work
from ios.adapters.world_web_measurements import attempts


def decoded(raw):
    need(type(raw) is str and len(raw.encode('utf-8'))<=32768)
    def pairs(rows):
        result={}
        for key,value in rows:need(key not in result);result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False));need(type(value) is dict);return value


def packet(raw,*,reply=False):
    value=decoded(raw);exact(value,{'contract','action','sequence'}|({'surface'} if reply else set()))
    need(value['contract']=='overte-web-parity-v1' and value['action']=='echo' and integer(value['sequence'],1,1000000))
    if reply:need(value['surface']=='world')
    return value


def locations(ownership,assigned_url):
    """Independent pinned source callsites; never copied from observed frames."""
    from ios.adapters.world_web_files import originals
    source=originals(ownership['runId'],ownership['fixtureUrl'],ownership['ticket'],ownership['nonce'])['script-bundle/main.js'].decode('utf-8')
    raw=source.encode('utf-16le');url=hashlib.sha256(assigned_url.encode()).hexdigest();sha=hashlib.sha256(raw).hexdigest()
    result=[]
    for token in ('emitScriptEvent(entity, reply);','closure(); event(kind + "-return"','tracked("script-reply",','send(JSON.stringify({contract:',
                  'respond(message, "world",','closure(); event(kind + "-return"','tracked("world-event",'):
        need(source.count(token)==1);offset=source.index(token);line=source.count('\n',0,offset)+1;column=offset-source.rfind('\n',0,offset)
        result.append(dict(sourceUrlSha256=url,sha256=sha,codeUnits=len(raw)//2,line=line,column=column))
    return result


def chain(ledger,document,workers,ownership,directory,entity,*,emitters=None):
    """Qualify one original document's actual sends and matching page receives.

    A new document can start its sequence at one again. Its original nonce and
    native lifetime, full bytes and actual event times bind each independent
    boundary. The caller retains earlier actual documents rather than copying
    the current DOM backward into them.
    """
    native.original(ledger);dom.original(document);work.original(workers)
    need(ledger['complete'] and workers['source']['complete'] and ledger['runId']==document['runId']==workers['runId']
        and ledger['processId']==document['processId']==workers['processId'])
    worker=work.owned_worker(workers,ownership,directory,entity)
    work.worker(worker,workers['clockAfter']['epochMs'],workers['source']['eventSequence'])
    if emitters is not None:
        from ios.adapters import web_script_emissions as emission_source
        emission_source.original(emitters)
        need(emitters['runId']==ledger['runId'] and emitters['processId']==ledger['processId'] and emitters['complete'])
        manager=worker['manager'];profile=dict(engineInstance=manager['instance'],assignedUrl=manager['url'],loadGeneration=manager['loadGeneration'],
            assignedEpochMs=manager['assignedEpochMs'],code=deepcopy(worker['code']))
        pinned_locations=locations(ownership,manager['url'])
    view=document['source']['nativeView'];key=native.document_key(view)
    need(view['sourceIdentity']=='web-entity:'+entity)
    events=[row for row in ledger['events'] if native.document_key(row['identity'])==key]
    begins=[row for row in events if row['kind']=='document-began'];need(len(begins)==1);birth=begins[0]
    end=min([row['clock']['epochMs'] for row in ledger['events'] if row['sequence']>birth['sequence']
        and row['identity']['handle']==birth['identity']['handle'] and row['identity']['creation']==birth['identity']['creation']
        and row['kind'] in ('document-began','view-teardown','owner-destroyed')],default=ledger['clockAfter']['epochMs'])
    returns={row['detail']['entry']:row for row in events if row['kind']=='signal-return'}
    complete=[];stack=[]
    for event in worker['events']:
        if event['event']=='loaded':continue
        kind,phase=event['event'].rsplit('-',1)
        if phase=='enter':stack.append(dict(kind=kind,entry=event,returned=None,children=[]))
        elif phase=='return':stack[-1]['returned']=event
        else:
            row=stack.pop();row['finally']=event
            if stack:stack[-1]['children'].append(row)
            else:complete.append(row)
    inputs=attempts(ledger,document);deliveries=[row for row in events if row['kind']=='script-delivery'];accepted=[];echoes=[];used=set()
    for delivery in deliveries:
        message=delivery['detail']['message'];request=packet(message)
        need(delivery['sequence'] in returns)
        envelopes=[]
        for envelope in events:
            if envelope['kind']!='native-envelope' or envelope['sequence'] not in returns:continue
            detail=envelope['detail'];body=decoded(detail['envelope'])
            if body.get('type')!=6 or body.get('object')!='eventBridge' or body.get('args')!=[message]:continue
            if (detail['mainFrame'] and detail['documentNonce']==view['nonce'] and detail['frame']==view['url']
                and envelope['sequence']<delivery['sequence']<returns[delivery['sequence']]['sequence']<returns[envelope['sequence']]['sequence']):envelopes.append(envelope)
        need(len(envelopes)==1)
        candidates=[row for row in complete if row['kind']=='world-event' and row['entry']['payload']==dict(entityId=entity,message=message)
            and delivery['clock']['epochMs']<=row['entry']['invokedEpochMs']<=row['finally']['capturedEpochMs']<=end]
        need(len(candidates)==1);callback=candidates[0];need(callback['returned'] is not None)
        children=callback['children'];need(len(children)==1 and children[0]['kind']=='script-reply' and children[0]['returned'] is not None)
        reply=children[0];response=reply['entry']['payload']['message'];need(packet(response,reply=True)['sequence']==request['sequence'])
        need(reply['entry']['payload']['entityId']==entity)
        clicks=[row for row in inputs if row['click']['capturedEpochMs']<=delivery['clock']['epochMs']
            and not any(other['click']['capturedEpochMs']>row['click']['capturedEpochMs'] and other['click']['capturedEpochMs']<=delivery['clock']['epochMs'] for other in inputs)]
        need(len(clicks)==1 and clicks[0]['ordinal'] not in used);used.add(clicks[0]['ordinal'])
        # Native acceptance cannot grant a second-origin document; the native
        # completed-document/server-receipt join separately qualifies origin.
        accepted.append(dict(delivery=deepcopy(delivery),envelope=deepcopy(envelopes[0]),callback=deepcopy(callback),attempt=deepcopy(clicks[0])))
        received=[row for row in document['source']['dom']['echoes'] if row['sequence']==request['sequence'] and row['message']==response]
        need(len(received)<=1)
        if not received:continue
        original=received[0]
        slots=[row for row in events if row['kind']=='script-event-slot' and row['detail']==dict(message=response,active=True)
            and reply['entry']['invokedEpochMs']<=row['clock']['epochMs']<=original['receivedEpochMs'] and row['sequence'] in returns]
        page=[row for row in events if row['kind']=='page-reply' and row['detail']['message']==response
            and reply['entry']['invokedEpochMs']<=row['clock']['epochMs']<=original['receivedEpochMs'] and row['sequence'] in returns]
        need(len(slots)==len(page)==1 and slots[0]['sequence']<page[0]['sequence']<returns[page[0]['sequence']]['sequence']<returns[slots[0]['sequence']]['sequence'])
        if emitters is not None:
            call_id=None
            for observed in (slots[0],page[0]):
                sinks=[row for row in emitters['sinks'] if row['kind']==observed['kind'] and row['identity']==observed['identity']
                    and row['message']==response and row['entered']==observed['clock']]
                need(len(sinks)==1);api=emission_source.selected(emitters,sinks[0],profile,pinned_locations)
                need(api['target']==entity and reply['entry']['invokedEpochMs']<=api['entered']['epochMs']
                    <=api['finally']['epochMs']<=reply['finally']['capturedEpochMs'])
                if call_id is None:call_id=api['id']
                else:need(call_id==api['id'])
        echoes.append(dict(accepted=deepcopy(accepted[-1]),slot=deepcopy(slots[0]),pageReply=deepcopy(page[0]),received=deepcopy(original)))
    # An actual matching page receive cannot be backed only by an outgoing
    # Script reply, cooperative DOM event, or a different document's sequence.
    need(len(echoes)==len(document['source']['dom']['echoes']))
    return dict(attempts=deepcopy(inputs),accepted=accepted,echoes=echoes)
