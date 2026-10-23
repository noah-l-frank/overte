"""Actual UIKit/DOM/native-call/compiled-code/page receive parity chain.

UIKit timestamps are not a synchronous WebKit DOM delivery interval. Ordered
real contact/gesture associations have a bounded asynchronous lag instead.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need,decode
from ios.adapters import tablet_web_source as native, tablet_web_dom as dom, uikit_input as uikit, web_script_emissions as emissions
from adapters.native_feature_observation import exact, integer
from ios.adapters.tablet_web_documents import completed


def decoded(raw):
    need(type(raw) is str and len(raw.encode('utf-8'))<=32768)
    value=decode(raw,limit=32768);need(type(value) is dict);return value


def packet(raw,*,reply=False):
    value=decoded(raw);exact(value,{'contract','action','sequence'}|({'surface'} if reply else set()))
    need(value['contract']=='overte-web-parity-v1' and value['action']=='echo' and integer(value['sequence'],1,1000000))
    if reply:need(value['surface']=='tablet')
    return value


def _view(value):return tuple(value[key] for key in ('handle','creation','grant'))


def _document(ledger,sources,document):
    records=completed(ledger,sources);view=document['source']['nativeView'];key=native.document_key(view)
    matches=[row for row in records if native.document_key(row['identity'])==key];need(len(matches)==1);record=matches[0]
    need(record['identity']==view and record['finished']['clock']['epochMs']<=document['source']['nativeFinishedEpochMs']
        <=record['verified']['clock']['epochMs']<=document['clockBefore']['epochMs'])
    return record


def attempts(ledger,document,touches):
    """Complete genuine WK contact/DOM gesture pairs; no input intent or ACK."""
    native.original(ledger);dom.original(document);uikit.original(touches)
    need(ledger['complete'] and touches['complete'] and document['status']=='ready'
        and all(ledger[key]==document[key]==touches[key] for key in ('runId','fixtureUrl','processId')))
    body=document['source']['dom'];view=document['source']['nativeView'];key=native.document_key(view)
    begins=[row for row in ledger['events'] if row['kind']=='document-began' and native.document_key(row['identity'])==key]
    need(len(begins)==1);birth=begins[0]
    end=min([row['clock']['epochMs'] for row in ledger['events'] if row['sequence']>birth['sequence']
        and _view(row['identity'])==_view(view) and row['kind'] in ('document-began','view-teardown','owner-destroyed')],default=ledger['clockAfter']['epochMs']+1)
    contacts=[]
    for row in touches['contacts']:
        source=row['source']
        if (row['kind']!='touch' or source is None or 'identity' not in source or _view(source['identity'])!=_view(view)
            or not birth['clock']['epochMs']<=row['began']['epochMs']<end):continue
        need(source['identity']['source']==view['source'] and source['view']==document['source']['presentationAfter']['view']
            and not row['active'] and row['ended'] is not None and row['ended']['epochMs']<end)
        callbacks=[dispatch for dispatch in touches['dispatches'] if any(phase['contact']==row['id'] for phase in dispatch['phases'])]
        need(callbacks and all(item['returned'] is not None and item['finally'] is not None for item in callbacks))
        contacts.append(row)
    gestures=[];pending={}
    for row in body['events']:
        if row['kind'] not in ('pointerdown','pointerup','pointercancel'):continue
        need(row['trusted'] and row['pointerType']=='touch' and birth['clock']['epochMs']<=row['capturedEpochMs']<end)
        pointer=row['pointerId']
        if row['kind']=='pointerdown':need(pointer not in pending);pending[pointer]=row
        else:
            need(pointer in pending);down=pending.pop(pointer)
            need(row['eventTimeMs']>=down['eventTimeMs'] and row['capturedEpochMs']>=down['capturedEpochMs'])
            gestures.append(dict(down=down,up=row))
    need(not pending and len(gestures)==len(contacts))
    contacts.sort(key=lambda row:(row['began']['epochMs'],row['id']));gestures.sort(key=lambda row:row['down']['ordinal'])
    if len(contacts)>1:need(all(a['ended']['epochMs']<=b['began']['epochMs'] for a,b in zip(contacts,contacts[1:])))
    for contact,gesture in zip(contacts,gestures):
        down,up=gesture['down'],gesture['up']
        need(0<=down['capturedEpochMs']-contact['began']['epochMs']<1500
            and 0<=up['capturedEpochMs']-contact['ended']['epochMs']<1500
            and (contact['phase']==3)==(up['kind']=='pointerup'))
        gesture['contact']=contact
    result=[];used=set()
    bridge=next(row for row in body['elements'] if row['id']=='bridge')
    for click in body['events']:
        if click['kind']!='click' or click['target']['id']!='bridge':continue
        need(click['trusted'] and click['target']['birth']==bridge['birth'])
        candidates=[row for row in gestures if row['up']['kind']=='pointerup' and row['down']['target']==row['up']['target']==click['target']
            and row['up']['ordinal']<click['ordinal'] and 0<=click['capturedEpochMs']-row['up']['capturedEpochMs']<1500
            and not any(other['kind'] in ('pointerdown','click') and row['up']['ordinal']<other['ordinal']<click['ordinal'] for other in body['events'])]
        need(len(candidates)==1 and candidates[0]['contact']['id'] not in used);gesture=candidates[0];used.add(gesture['contact']['id'])
        result.append(dict(ordinal=click['ordinal'],click=deepcopy(click),down=deepcopy(gesture['down']),up=deepcopy(gesture['up']),contact=deepcopy(gesture['contact'])))
    return result


def chain(ledger,sources,document,touches,emitter,profile,locations):
    """One actual document; callers retain its own original active ledger."""
    native.join_sources(ledger,sources);dom.join_sources(document,sources);uikit.join_sources(touches,sources,ledger);emissions.original(emitter)
    need(emitter['complete'] and all(emitter[key]==ledger[key] for key in ('runId','fixtureUrl','processId')))
    _document(ledger,sources,document)
    view=document['source']['nativeView'];key=native.document_key(view)
    events=[row for row in ledger['events'] if native.document_key(row['identity'])==key]
    returns={row['detail']['entry']:row for row in events if row['kind']=='signal-return'}
    inputs=attempts(ledger,document,touches);delivered=[];accepted=[];echoes=[];used=set();request_sequences=set();used_calls=set()
    for delivery in events:
        if delivery['kind']!='script-delivery':continue
        message=delivery['detail']['message'];request=packet(message)
        need(delivery['sequence'] in returns and request['sequence'] not in request_sequences);request_sequences.add(request['sequence'])
        envelopes=[]
        for row in events:
            if row['kind']!='native-envelope' or row['sequence'] not in returns:continue
            detail=row['detail'];body=decoded(detail['envelope'])
            if body.get('type')!=6 or body.get('object')!='eventBridge' or body.get('args')!=[message]:continue
            if (detail['mainFrame'] and detail['documentNonce']==view['nonce'] and detail['frame']==view['url']
                and row['sequence']<delivery['sequence']<returns[delivery['sequence']]['sequence']<returns[row['sequence']]['sequence']):envelopes.append(row)
        need(len(envelopes)==1)
        prior=[row for row in inputs if row['click']['capturedEpochMs']<=delivery['clock']['epochMs']]
        need(prior);latest=max(row['click']['capturedEpochMs'] for row in prior)
        prior=[row for row in prior if row['click']['capturedEpochMs']==latest]
        need(len(prior)==1 and prior[0]['ordinal'] not in used and delivery['clock']['epochMs']-latest<1500);used.add(prior[0]['ordinal'])
        native_delivery=dict(delivery=deepcopy(delivery),envelope=deepcopy(envelopes[0]),attempt=deepcopy(prior[0]));delivered.append(native_delivery)
        received=[row for row in document['source']['dom']['echoes'] if row['sequence']==request['sequence']]
        need(len(received)<=1)
        slots=[]
        for row in events:
            if (row['kind']!='script-event-slot' or not row['detail']['active'] or row['sequence'] not in returns
                or row['clock']['epochMs']<delivery['clock']['epochMs']):continue
            # This fixture emits only this closed parity reply. Actual native
            # messages are read, never synthesized from the requested count.
            reply=packet(row['detail']['message'],reply=True)
            if reply['sequence']==request['sequence']:slots.append(row)
        if not slots:need(not received);continue
        need(len(slots)==1);response=slots[0]['detail']['message']
        limit=received[0]['receivedEpochMs'] if received else document['clockAfter']['epochMs']
        need(slots[0]['clock']['epochMs']<=limit)
        pages=[row for row in events if row['kind']=='page-reply' and row['detail']['message']==response
            and delivery['clock']['epochMs']<=row['clock']['epochMs']<=limit and row['sequence'] in returns]
        need(len(slots)==len(pages)==1 and slots[0]['sequence']<pages[0]['sequence']<returns[pages[0]['sequence']]['sequence']<returns[slots[0]['sequence']]['sequence'])
        actual_sinks={}
        for kind,original_ in (('script-event-slot',slots[0]),('page-reply',pages[0])):
            # IOSBrowserTrace::Signal records its entry before constructing its
            # actual SinkScope member. Its destructor emits signal-return
            # before that member records normal return/finally. Equal clocks
            # are neither required nor manufactured across the two sources.
            candidates=[row for row in emitter['sinks'] if row['kind']==kind and row['identity']==view and row['message']==response
                and row['returned'] is not None and row['finally'] is not None
                and original_['clock']['epochMs']<=row['entered']['epochMs']<=returns[original_['sequence']]['clock']['epochMs']<=row['returned']['epochMs']
                and row['finally']['epochMs']<=limit]
            need(len(candidates)==1);actual_sinks[kind]=candidates[0]
        need(actual_sinks['script-event-slot']['call']==actual_sinks['page-reply']['call'])
        call=emissions.selected(emitter,actual_sinks['page-reply'],profile,locations)
        need(call['id'] not in used_calls and call['surface']=='tablet' and call['target']=='com.highfidelity.interface.tablet.system'
            and call['message']==response and delivery['clock']['epochMs']<=call['entered']['epochMs']<=slots[0]['clock']['epochMs']
            and call['finally']['epochMs']<=limit);used_calls.add(call['id'])
        consumed=dict(native_delivery,slot=deepcopy(slots[0]),pageReply=deepcopy(pages[0]),call=call);accepted.append(consumed)
        if received:
            need(received[0]['message']==response)
            echoes.append(dict(accepted=deepcopy(consumed),received=deepcopy(received[0])))
    need(len(echoes)==len(document['source']['dom']['echoes']))
    return dict(attempts=inputs,delivered=delivered,accepted=accepted,echoes=echoes)
