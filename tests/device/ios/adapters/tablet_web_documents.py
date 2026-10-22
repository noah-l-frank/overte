"""Actual Tablet document completions joined to DOM, source and server originals.

Inline completion has no HTTP receipt. Native finish, observer installation and
verification are independent actual events; repeated callbacks count once.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,need
from ios.adapters import tablet_web_source as native,tablet_web_dom as dom
from ios.adapters.world_web_measurements import browser_original,origin


def completed(ledger,sources):
    native.join_sources(ledger,sources);need(ledger['complete'])
    documents={};views=set();closed=set();result=[]
    for event in ledger['events']:
        item=event['identity'];view=(item['handle'],item['creation'],item['grant'])
        key=native.document_key(item);kind=event['kind']
        if kind=='view-created':need(view not in views);views.add(view)
        elif kind in ('view-teardown','owner-destroyed'):closed.add(view)
        elif kind=='document-began':
            need(view in views and view not in closed and key not in documents and item['page']>0 and item['nonce'])
            documents[key]=dict(begin=event,response=None,finished=None,verified=None,observer=None)
        elif kind in ('main-response','native-finished','document-verified','dom-observer-installed'):
            need(key in documents and view not in closed);current=documents[key]
            if kind=='main-response':
                # Native NSURLResponse for the inline transport is not an HTTP
                # response and must never be replaced with a fixture receipt.
                need(item['source']['carrier'] is None)
                if current['response'] is None:current['response']=event
                else:need(current['response']['detail']==event['detail'])
            elif kind=='dom-observer-installed':
                need(current['observer'] is None);current['observer']=event
            elif kind=='native-finished':
                if current['finished'] is None:current['finished']=event
            elif current['verified'] is None:
                begin,installed,finished=current['begin'],current['observer'],current['finished']
                need(installed is not None and finished is not None
                    and begin['sequence']<installed['sequence']<finished['sequence']<event['sequence']
                    and installed['detail']['sourceSha256']==dom.SOURCE_SHA256
                    and finished['identity']['url']==item['url'])
                response=current['response']
                if item['source']['carrier'] is None:
                    need(response is not None and begin['sequence']<response['sequence']<=finished['sequence']
                        and response['detail']['responseId'] and response['detail']['url']==item['url'])
                else:need(response is None)
                current['verified']=event
                result.append(dict(identity=deepcopy(item),begin=deepcopy(begin),observer=deepcopy(installed),
                    response=deepcopy(response),finished=deepcopy(finished),verified=deepcopy(event)))
    return result


def current_document(ledger,sources,document,browser,origins):
    dom.join_sources(document,sources);browser_original(browser);exact(origins,{'primary','foreign'})
    need(all(ledger[key]==document[key] for key in ('runId','fixtureUrl','processId'))
        and origin(origins['primary'])!=origin(origins['foreign']))
    observed=document['source'];view=observed['nativeView'];key=native.document_key(view)
    roots=[row for row in sources['roots'] if row['id']==view['source']['root']];need(len(roots)==1 and roots[0]['alive'])
    documents=completed(ledger,sources);rows=[row for row in documents if native.document_key(row['identity'])==key]
    need(len(rows)==1);actual=rows[0]
    need(actual['identity']==view and actual['finished']['clock']['epochMs']<=observed['nativeFinishedEpochMs']
        <=actual['verified']['clock']['epochMs']<=document['clockBefore']['epochMs']
        and actual['observer']['detail']['sourceSha256']==observed['observerSha256']==dom.SOURCE_SHA256)
    # A historical ready DOM packet cannot remain current after the actual
    # owner closes, is recreated, or begins a different document.
    for event in ledger['events']:
        if event['sequence']<=actual['verified']['sequence'] or event['identity']['handle']!=view['handle']:continue
        identity=event['identity']
        if event['kind']=='view-created':need(False)
        if (identity['creation'],identity['grant'])==(view['creation'],view['grant']):
            need(event['kind'] not in ('view-teardown','owner-destroyed','document-began'))
    if observed['inlineLease']:
        need(actual['response'] is observed['http'] is None and view['source']['carrier'] is not None)
        carriers=[row for row in sources['carriers'] if row['id']==view['source']['carrier']];need(len(carriers)==1)
        carrier=carriers[0];bindings=[row for row in carrier['bindings'] if row['id']==view['source']['binding']]
        need(len(bindings)==1);binding=bindings[0]
        need(carrier['alive'] and 'retired' not in carrier and binding['current'] and binding['pageAlive'] and binding['contextAlive'])
        # The original decoded inline input is retained as source provenance;
        # there is deliberately no manufactured response/status/origin receipt.
        navigation=[row for row in sources['navigations'] if row['id']==carrier['navigation']];need(len(navigation)==1)
        return dict(document=deepcopy(actual),response=None,documentLoads=len(documents),page='inline',origin='inline',
            documentKind='inline',inlineInput=deepcopy(navigation[0]['body']))
    response=actual['response']['detail'];http=observed['http']
    need(response['responseId']==http['responseId'] and response['status']==http['status'] and response['url']==http['url'])
    receipts=[row for row in browser['responses'] if row['responseId']==response['responseId']];need(len(receipts)==1)
    receipt=receipts[0];need(receipt['resource'] in ('index.html','reference.html','page-b.html','recovery.html')
        and receipt['status']==response['status'])
    parsed=urlsplit(view['url']);base=urlsplit(ledger['fixtureUrl']);selected=urlsplit(origins[receipt['origin']])
    need((parsed.scheme,parsed.netloc)==(selected.scheme,selected.netloc) and not parsed.query and not parsed.fragment
        and parsed.username is parsed.password is None and parsed.path==base.path+'tickets/'+receipt['ticket']+'/'+receipt['resource'])
    return dict(document=deepcopy(actual),response=deepcopy(receipt),documentLoads=len(documents),
        page='foreign' if receipt['origin']=='foreign' else 'B' if receipt['resource']=='page-b.html'
            else 'recovery' if receipt['resource']=='recovery.html' else 'reference',origin=receipt['origin'],documentKind='http',inlineInput=None)
