"""Original native Tablet WK/bridge transcript and independent source join.

Only transport and the identical callback-detail protocol are reused from the
World reader. Native source identity, instance, clock and raw DTO remain Tablet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters.places_model import text
from ios.adapters import tablet_web_sources as sources
from ios.adapters.world_web_source import IOSWorldWebSource,detail,document_key

VERSION=1
ACTION='feature-ios-tablet-web'
FILE=ACTION+'.json'
LIMIT=2097152
HEX=sources.HEX
SIGNALS={'native-envelope','script-delivery','page-reply','script-event-slot'}
CALLS={'evaluation-enter','pointer-enter','dom-read-enter'}
KINDS=SIGNALS|CALLS|{'callback-enter','callback-return','signal-return','view-created','view-teardown',
    'owner-destroyed','document-began','main-response','native-finished','document-verified','dom-observer-installed'}


def command(value):
    need(type(value) is dict and value.get('action')==ACTION)
    sources.command(dict(value,action=sources.ACTION));return value


def source_reference(value,query):
    exact(value,{'root','navigation','fixtureUrl','carrier','binding'})
    sources.identifier(value['root']);sources.identifier(value['navigation']);need(value['fixtureUrl']==query['fixtureUrl'])
    need((value['carrier'] is None and value['binding'] is None)
        or (type(value['carrier']) is str and type(value['binding']) is str))
    if value['carrier'] is not None:sources.identifier(value['carrier']);sources.identifier(value['binding'])
    return value


def identity(value,query):
    exact(value,{'handle','creation','grant','page','nonce','url','sourceUrl','sourceIdentity','surface','source'})
    need(re.fullmatch('[1-9][0-9]{0,18}',text(value['handle'],19)) and integer(value['creation'],1) and integer(value['grant'],1) and integer(value['page'])
        and value['surface']=='tablet' and text(value['sourceIdentity'],512))
    for key in ('url','sourceUrl'):text(value[key],131072)
    need(type(value['nonce']) is str and (value['nonce']=='' or re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['nonce'])))
    source_reference(value['source'],query);return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosTabletWebVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','complete','eventSequence','events'})
    need(type(value['iosTabletWebVersion']) is int and value['iosTabletWebVersion']==VERSION
        and all(value[k]==query[k] for k in ('commandId','runId','fixtureUrl')) and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-tablet-web' and type(value['complete']) is bool
        and integer(value['eventSequence']) and type(value['events']) is list and len(value['events'])<=4096
        and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    sources.identifier(value['instance']);a,b=sources.stamp(value['clockBefore']),sources.stamp(value['clockAfter'])
    sources.stamp(b,floor=a);need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    earlier={};ids=set();last=None;ordinal=0;entered=set();returned=set();signals=set()
    for event in value['events']:
        exact(event,{'sequence','eventId','kind','clock','identity','detail'})
        need(integer(event['sequence'],ordinal+1,value['eventSequence']) and event['kind'] in KINDS)
        sources.identifier(event['eventId']);need(event['eventId'] not in ids);ids.add(event['eventId'])
        identity(event['identity'],query);sources.stamp(event['clock'],a,last)
        need(len(json.dumps(event['detail'],ensure_ascii=False,separators=(',',':')).encode())<=32768)
        # Same original callback argument/result protocol; no World identity or
        # normalized effect is constructed or accepted by this reader.
        detail(event,earlier)
        kind=event['kind']
        if kind in ('callback-enter','callback-return','signal-return'):
            entry=event['detail']['entry'];collection=entered if kind=='callback-enter' else returned if kind=='callback-return' else signals
            need(entry not in collection);collection.add(entry)
            if kind=='callback-return':need(entry in entered)
        last=event['clock'];ordinal=event['sequence'];earlier[ordinal]=event
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['eventSequence']>=previous['eventSequence']
            and (previous['complete'] or not value['complete']) and value['events'][:len(previous['events'])]==previous['events'])
        sources.stamp(a,floor=previous['clockAfter'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def join_sources(value,source):
    """Join each actual native grant to the original source/carrier birth.

    Source and WK transcript clocks have distinct monotonic origins. Only the
    original process/epoch ordering is compared across those actual sources.
    Historical revoked carriers are valid provenance, never current authority.
    """
    original(value);sources.original(source)
    need(value['complete'] and source['complete'] and all(source[k]==value[k] for k in ('runId','fixtureUrl','processId')))
    navigations={row['id']:row for row in source['navigations']};carriers={row['id']:row for row in source['carriers']}
    grants={}
    for event in value['events']:
        item=event['identity'];ref=item['source'];need(ref['navigation'] in navigations);nav=navigations[ref['navigation']]
        need(ref['root']==nav['root'] and nav.get('returned',{}).get('invoked') is True
            and nav['returned']['clock']['epochMs']<=event['clock']['epochMs'])
        grant=(item['handle'],item['creation'],item['grant']);binding=(deepcopy(ref),item['sourceIdentity'],item['sourceUrl'])
        if grant in grants:need(grants[grant]==binding)
        else:grants[grant]=binding
        if nav['kind']=='http':need(ref['carrier'] is ref['binding'] is None and item['sourceUrl']==nav['sourceUrl'])
        else:
            need(ref['carrier'] in carriers);carrier=carriers[ref['carrier']]
            need(carrier['root']==ref['root'] and carrier['navigation']==ref['navigation'] and carrier['identity']==item['sourceIdentity'])
            rows=[row for row in carrier['bindings'] if row['id']==ref['binding']];need(len(rows)==1);actual=rows[0]
            need(item['sourceUrl']==actual['transportUrl'] and 'returned' in actual
                and actual['returned']['epochMs']<=event['clock']['epochMs'])
    return deepcopy(value)


def pending(value):
    original(value);need(value['complete'])
    calls={row['sequence'] for row in value['events'] if row['kind'] in CALLS|SIGNALS}
    ended={row['detail']['entry'] for row in value['events'] if row['kind'] in ('callback-return','signal-return')}
    return sorted(calls-ended)


class IOSTabletWebSource(IOSWorldWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
