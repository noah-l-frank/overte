"""Pure original nineteen-step World Web state derivation across documents."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from ios.adapters import world_web_source as native,world_web_dom as dom,world_web_work as work
from ios.adapters.world_web_measurements import browser_original,current_document
from ios.adapters.world_web_echoes import chain


from ios.adapters.world_web_trace import current_view


def documents(frames):
    """Latest genuine original per document, retaining all earlier prefixes."""
    result={}
    for frame in frames:
        document=frame['document']
        if document is None:continue
        dom.original(document);key=native.document_key(document['source']['nativeView'])
        if key in result:
            previous=result[key]
            # Historical native read instances/counters belong to one process;
            # every retained DOM prefix still validates against its own source.
            dom.validate(document,dict(schemaVersion=1,commandId=document['commandId'],action=dom.ACTION,runId=document['runId'],fixtureUrl=frame['ledger']['fixtureUrl']),
                document['processId'],previous=previous)
        result[key]=deepcopy(document)
    return result


def derive(frames,*,ownership=None,directory=None,entity=None,origins):
    need(type(frames) is list and frames);latest=frames[-1]
    previous=None
    for frame in frames:
        ledger=frame['ledger'];query=dict(schemaVersion=1,commandId=ledger['commandId'],action=native.ACTION,runId=ledger['runId'],fixtureUrl=ledger['fixtureUrl'])
        native.validate(ledger,query,ledger['processId'],previous=None if previous is None else previous['ledger'])
        browser_original(frame['browser'],None if previous is None else previous['browser'])
        packet=frame['work'];query=dict(schemaVersion=1,commandId=packet['requestId'],action=work.ACTION,runId=packet['runId'])
        work.validate(packet,query,ledger['processId'],previous=None if previous is None else previous['work'])
        need(packet['runId']==ledger['runId'] and packet['source']['complete'] and ledger['complete'])
        if 'emissions' in frame:
            from ios.adapters import web_script_emissions as emissions
            value=frame['emissions'];query=dict(schemaVersion=1,commandId=value['commandId'],action=emissions.ACTION,runId=ledger['runId'],fixtureUrl=ledger['fixtureUrl'])
            emissions.validate(value,query,ledger['processId'],previous=None if previous is None else previous['emissions']);need(value['complete'])
        if previous is not None:need(('emissions' in frame)==('emissions' in previous))
        previous=frame
    ledger,browser=latest['ledger'],latest['browser'];native.original(ledger);browser_original(browser)
    retained=documents(frames);completed=native.completed_documents(ledger);keys={native.document_key(row['identity']) for row in completed}
    need(set(retained)<=keys);current=current_view(ledger)
    inputs=[];accepted=[];echoes=[]
    if ownership is None:
        need(directory is entity is None and not retained and not ledger['events'])
    else:
        for document in retained.values():
            need(document['runId']==ledger['runId'] and document['processId']==ledger['processId'])
            measured=current_document(ledger,document,browser,origins)
            joined=chain(ledger,document,latest['work'],ownership,directory,entity,emitters=latest.get('emissions'))
            if measured['origin']=='foreign':need(not joined['accepted'] and not joined['echoes'])
            inputs.extend(joined['attempts']);accepted.extend(joined['accepted']);echoes.extend(joined['echoes'])
    # A sequence belongs to its actual document; duplicate bridge seq=1 after
    # resume remains a separate original, never a reset of a public run counter.
    state=dict(surface='world',text='',page='none',bridgeMessages=len(accepted),bridgeEchoes=len(echoes),attemptedMessages=len(inputs),
        documentLoads=len(completed),httpStatus=0,origin='none',documentKind='none',inlineLeases=0,deferredMessages=0,error='none',focused=False,open=False)
    original=None
    if current is not None:
        key=native.document_key(current);need(key in retained and latest['document'] is not None
            and native.document_key(latest['document']['source']['nativeView'])==key)
        original=retained[key];need(not original['source']['nativeView']['inlineLease'])
        measured=current_document(ledger,original,browser,origins);body=original['source']['dom']
        state.update(text=body['editor']['text'],focused=body['editor']['focused'],page=measured['page'],open=True,
            origin=measured['origin'],documentKind='http',httpStatus=measured['response']['status'])
    else:need(latest['document'] is None)
    return dict(public=state,document=deepcopy(original),attempts=inputs,accepted=accepted,echoes=echoes)
