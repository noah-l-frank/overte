"""Join original native/DOM, HTTP and service evidence; no expected-state input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,integer,need
from adapters.native_phone_web_runtime import validate as validate_runtime
from feature_journeys.contract import identifier,state
from overte_phone_world_web_source import identity


def browser_status(value,previous=None):
    exact(value,{'browserFixtureVersion','instance','ready','sequence','responses'})
    need(type(value['browserFixtureVersion']) is int and value['browserFixtureVersion']==1
        and type(value['ready']) is bool and integer(value['sequence'],0,256)
        and type(value['responses']) is list and len(value['responses'])==value['sequence'])
    identifier(value['instance']);seen=set();epoch=0
    for ordinal,row in enumerate(value['responses'],1):
        exact(row,{'sequence','responseId','capturedEpochMs','ticket','resource','origin','status','bytes','sha256'})
        identifier(row['responseId']);identifier(row['ticket'])
        need(type(row['sequence']) is int and row['sequence']==ordinal and row['responseId'] not in seen
            and integer(row['capturedEpochMs'],max(1,epoch)) and row['resource'] in {
                'index.html','reference.html','page-b.html','recovery.html','reference.js','client.js','injected.js','feature-marker.js','inline-input.json'}
            and row['origin'] in ('primary','foreign') and type(row['status']) is int and row['status'] in (200,404)
            and integer(row['bytes'],1,1024*1024) and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']))
        seen.add(row['responseId']);epoch=row['capturedEpochMs']
    if previous is not None:
        browser_status(previous)
        need(value['instance']==previous['instance'] and value['sequence']>=previous['sequence']
            and value['responses'][:len(previous['responses'])]==previous['responses'] and (not previous['ready'] or value['ready']))
    return value


def document(packet,status,root,foreign_root):
    """An actual consumed response ID joins one unchanged original receipt."""
    view,dom=packet['source']['nativeView'],packet['source']['dom'];actual=urlsplit(view['url'])
    if 'inline' in packet['source']:
        raw=base64.b64decode(view['sourceUrl'].split(',',1)[1],validate=True)
        match=re.findall(b'<meta name="overte-fixture-inline-input" content="([0-9a-f]{32})">',raw);need(len(match)==1)
        receipts=[row for row in status['responses'] if row['responseId']==match[0].decode()]
        need(len(receipts)==1);receipt=receipts[0]
        encoded=json.dumps(dict(dataUrl=view['sourceUrl']),separators=(',',':')).encode()
        need(receipt['resource']=='inline-input.json' and receipt['origin']=='primary' and receipt['status']==200
            and receipt['bytes']==len(encoded) and receipt['sha256']==hashlib.sha256(encoded).hexdigest()
            and receipt['capturedEpochMs']<=packet['capturedEpochMs']+250 and dom['document']['title']=='Overte owned inline parity')
        return dict(page='inline',origin='inline',httpStatus=0,text=dom['editor']['text'],focused=dom['editor']['focused'])
    roots=[urlsplit(base) for base in (root,foreign_root)]
    origin=None
    for label,base in zip(('primary','foreign'),roots):
        if (actual.scheme,actual.netloc)==(base.scheme,base.netloc):origin=label
    need(origin is not None and not actual.query and not actual.fragment)
    prefix=urlsplit(root).path+'tickets/'
    need(actual.path.startswith(prefix))
    suffix=actual.path[len(prefix):];match=re.fullmatch('([0-9a-f]{32})/(index|reference|page-b|recovery)\\.html',suffix)
    need(match is not None)
    ticket,name=match.group(1),match.group(2)+'.html'
    receipts=[row for row in status['responses'] if row['responseId']==dom['document']['responseId']]
    need(len(receipts)==1);receipt=receipts[0]
    need(receipt['ticket']==ticket and receipt['resource']==name and receipt['origin']==origin
        and receipt['capturedEpochMs']<=packet['capturedEpochMs']+250)
    need(view['httpErrorStatus'] in (0,receipt['status']))
    if 'title' in dom['document']:
        title='Overte web parity '+('foreign ' if origin=='foreign' else '')+('second' if name=='page-b.html' else
            'recovery unavailable' if receipt['status']==404 else 'recovery available' if name=='recovery.html' else 'reference')
        need(dom['document']['title']==title)
    page='foreign' if origin=='foreign'  else {'index.html':'reference','reference.html':'reference','page-b.html':'B','recovery.html':'recovery'}[name]
    return dict(page=page,origin=origin,httpStatus=receipt['status'],text=dom['editor']['text'],focused=dom['editor']['focused'])


def measurement(run,root,foreign_root,native,status,runtime,script_rows,script_url,*,area="world-web"):
    surface="tablet" if area=="tablet-web" else "world"
    browser_status(status)
    request=dict(schemaVersion=1,commandId=runtime['commandId'],action='feature-phone-web-runtime-observe',runId=run,fixtureUrl=root)
    validate_runtime(runtime,request,native['processId'],runtime['capturedEpochMs']);need(runtime['status']=='ready')
    source=native['source'];current=source['current'];docs=source['documents']
    # Original requests/replies must belong to actual retained documents and
    # matching passive histories, already checked by the native source reader.
    attempts=sum(len(row['source']['dom']['attempts']) for row in source['domHistory'].values())
    echoes=sum(len(row['source']['dom']['echoes']) for row in source['domHistory'].values())
    value=dict(surface=surface,text='',page='none',bridgeMessages=len(source['requests']),bridgeEchoes=echoes,
        attemptedMessages=attempts,documentLoads=len(docs),httpStatus=0,origin='none',documentKind='none',
        inlineLeases=0,deferredMessages=0,error='none',focused=False,open=bool(current))
    if current:
        need(docs and identity(current['source']['nativeView'])==identity(docs[-1]))
        value.update(document(current,status,root,foreign_root),documentKind='inline' if 'inline' in current['source'] else 'http')
        if value['documentKind']=='inline':value['inlineLeases']=int(current['source']['inline']['current'])
    # Every historical DOM document is qualified against its own actual receipt;
    # no old sample can borrow the new response/status or the current ticket.
    for packet in source['domHistory'].values():document(packet,status,root,foreign_root)
    if area=='tablet-web':
        deferred=source['deferred'];need(not deferred['armed'])
        value['deferredMessages']=int(deferred['pending'])
        held=deferred['held']
        if held is not None:
            key=identity(held);need(key in source['domHistory']);lease=source['domHistory'][key]['source']['inline']
            need(all(held[key]==lease[key] for key in ('token','revision','bodySha256','sourceSha256')))
        for delivery in deferred['deliveries']:
            need(not delivery['accepted'] and not delivery['leaseCurrent'] and held is not None
                and all(delivery[key]==held[key] for key in held))
    need(type(script_rows) is list and len(script_rows)<=1024)
    scripts=[row for row in script_rows if row.get('url')==script_url]
    need(len(scripts)<=1)
    resources=[]
    if scripts:resources.append('script:'+area+'-client')
    original_views=runtime['source']['nativeAfter']['views']
    java=runtime['source']['java']
    native_owned=[row for row in original_views if row['sourceOwned'] or row['documentOwned'] or row['creationOwned']]
    handles={row['handle'] for row in runtime['source']['nativeAfter']['knownHandles']}
    java_owned=[row for row in java['views'] if row['sourceOwned'] or row['documentOwned'] or area=='tablet-web' and row['handle'] in handles]
    pending=[row for row in java['creations'] if row['sourceOwned'] or area=='tablet-web' and row['handle'] in handles]
    if current:
        view=current['source']['nativeView']
        need(len(native_owned)==len(java_owned)==1 and not pending and bool(scripts))
        a,b=native_owned[0],java_owned[0]
        if value['documentKind']=='inline':
            wanted=hashlib.sha256(current['source']['inline']['transportUrl'].encode()).hexdigest()
            need(b['sourceSha256']==b['documentSha256']==wanted)
        need(a['surface']==surface and a['created'] and a['sessionActive'] and not a['suspended'] and not a['loading']
            and b['active'] and b['foreground'] and b['ownerCurrent'] and not b['destroyed'] and not b['closing'] and not b['loading']
            and all(a[key]==b[key]==view[key] for key in ('handle','creation','grant','page')))
    if native_owned or java_owned or pending:resources.append(('panel:tablet-web' if surface=='tablet' else 'entity:world-web'))
    if any(row['callbacks'] or row['scriptReplies'] or row['domPending'] for row in original_views):resources.append('connection:'+area)
    if value['focused']:resources.append('input:'+area)
    if value['deferredMessages']:resources.append('connection:tablet-inline-held')
    state(area,value,run)
    return deepcopy(value),resources
