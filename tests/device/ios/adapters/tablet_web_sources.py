"""Actual native tablet source inputs/carriers; no loaded-page/effect verdict.

Navigation invocation is input provenance only. Native document completion,
original DOM/response bytes, bridge receipts and pixels remain separate joins.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import re
from urllib.parse import urlsplit,urlunsplit
from adapters.native_feature_observation import exact,fresh,integer,need,number
from ios.adapters.places_model import text
from ios.adapters.world_web_source import IOSWorldWebSource

VERSION=1
ACTION='feature-ios-tablet-sources'
FILE=ACTION+'.json'
LIMIT=2097152
HEX=r'[0-9a-f]{32}'


def identifier(value):need(type(value) is str and re.fullmatch(HEX,value));return value


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','fixtureUrl'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and re.fullmatch('ios-'+HEX,text(value['commandId'],36)));identifier(value['runId'])
    root=text(value['fixtureUrl'],512);url=urlsplit(root);url.port
    need(url.scheme in ('http','https') and url.hostname and url.username is url.password is None and not url.query and not url.fragment
        and not any(ord(c)<=32 or ord(c)==127 for c in root) and url.path=='/feature-fixture/v1/runs/'+value['runId']+'/' and urlunsplit(url)==root)
    return value


def stamp(value,ceiling=None,floor=None):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']))
    if ceiling is not None:need(value['epochMs']<=ceiling['epochMs'] and value['monotonicMs']<=ceiling['monotonicMs'])
    if floor is not None:
        utc=value['epochMs']-floor['epochMs'];mono=value['monotonicMs']-floor['monotonicMs'];need(utc>=0 and mono>=0 and abs(utc-mono)<=250)
    return value


def optional(value,base,extras):
    need(type(value) is dict and base<=set(value)<=base|set(extras));return value


def original_navigation(row,query,ceiling):
    optional(row,{'id','root','fixtureUrl','tablet','sourceUrl','sourceSha256','scriptUrl','kind','body','clock'},['returned'])
    identifier(row['id']);identifier(row['root']);need(row['fixtureUrl']==query['fixtureUrl']);text(row['tablet'],512);text(row['scriptUrl'],4096)
    source=text(row['sourceUrl'],1048576);need(hashlib.sha256(source.encode()).hexdigest()==row['sourceSha256']);stamp(row['clock'],ceiling)
    if row['kind']=='http':
        prefix=query['fixtureUrl']+'tickets/';need(source.startswith(prefix) and re.fullmatch(HEX+r'/(?:index|reference)\.html',source[len(prefix):]) and row['body'] is None)
    else:
        need(row['kind']=='inline');body=row['body'];exact(body,{'base64','sha256','charset'})
        raw=base64.b64decode(text(body['base64'],349528),validate=True);need(0<len(raw)<=262144 and base64.b64encode(raw).decode()==body['base64']
            and hashlib.sha256(raw).hexdigest()==body['sha256'] and body['charset']=='utf-8'
            and source=='data:text/html;charset=utf-8;base64,'+body['base64'])
        need(raw.count(('<meta name="overte-fixture-owner" content="'+query['runId']+'">').encode())==1)
    if 'returned' in row:
        exact(row['returned'],{'clock','invoked'});need(type(row['returned']['invoked']) is bool);stamp(row['returned']['clock'],ceiling,row['clock'])
    return row


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosTabletSourcesVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','complete','roots','navigations','carriers'})
    need(type(value['iosTabletSourcesVersion']) is int and value['iosTabletSourcesVersion']==VERSION
        and all(value[k]==query[k] for k in ('commandId','runId','fixtureUrl')) and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and value['clockDomain']=='native-main-ios-tablet-sources' and type(value['complete']) is bool and integer(value['sequence'],1))
    identifier(value['instance']);a,b=stamp(value['clockBefore']),stamp(value['clockAfter']);stamp(b,floor=a)
    need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    need(type(value['roots']) is list and len(value['roots'])<=32 and type(value['navigations']) is list and len(value['navigations'])<=128
        and type(value['carriers']) is list and len(value['carriers'])<=128)
    roots={};navigations={};carriers={};ids=set()
    def birth(row):identifier(row['id']);need(row['id'] not in ids);ids.add(row['id'])
    for row in value['roots']:
        optional(row,{'id','clock','alive'},['destroyed']);birth(row);stamp(row['clock'],a);need(type(row['alive']) is bool)
        if 'destroyed' in row:stamp(row['destroyed'],a,row['clock']);need(not row['alive'])
        if not row['alive']:need('destroyed' in row)
        roots[row['id']]=row
    for row in value['navigations']:
        original_navigation(row,query,a);birth(row);need(row['root'] in roots);stamp(row['clock'],a,roots[row['root']]['clock']);navigations[row['id']]=row
    # Inline association comes from an earlier actual fixture HTTP input on
    # this same original native root, never a requested query or DOM label.
    for index,row in enumerate(value['navigations']):
        if row['kind']=='inline':need(any(old['root']==row['root'] and old['kind']=='http' for old in value['navigations'][:index]))
    for row in value['carriers']:
        optional(row,{'id','navigation','root','identity','clock','alive','bindings'},['retired','retireReturned','destroyed']);birth(row)
        need(row['navigation'] in navigations);nav=navigations[row['navigation']];need(nav['kind']=='inline' and row['root']==nav['root'])
        need(text(row['identity'],512).startswith('tablet:') and type(row['alive']) is bool);stamp(row['clock'],a,nav['clock'])
        for key in ('retired','retireReturned','destroyed'):
            if key in row:stamp(row[key],a,row['clock'])
        if 'retireReturned' in row:need('retired' in row);stamp(row['retireReturned'],a,row['retired'])
        if 'destroyed' in row:need(not row['alive'])
        if not row['alive']:need('destroyed' in row)
        need(type(row['bindings']) is list and len(row['bindings'])<=128);revision=0;live=0
        for binding in row['bindings']:
            optional(binding,{'id','clock','token','revision','transportUrl','sha256','charset','current','contextAlive','pageAlive'},['revoked','returned']);birth(binding)
            identifier(binding['token']);need(integer(binding['revision'],revision+1) and binding['sha256']==nav['body']['sha256'] and binding['charset']==nav['body']['charset'])
            revision=binding['revision'];need(binding['transportUrl']=='http://'+binding['token']+'.overte-inline.invalid/index.html');stamp(binding['clock'],a,row['clock'])
            need(all(type(binding[k]) is bool for k in ('current','contextAlive','pageAlive')))
            if 'returned' in binding:stamp(binding['returned'],a,binding['clock'])
            if 'revoked' in binding:stamp(binding['revoked'],a,binding['clock']);need(not binding['current'])
            if not binding['current']:need('revoked' in binding)
            else:need(row['alive'] and binding['contextAlive'] and binding['pageAlive'] and 'retired' not in row);live+=1
        need(live<=1);carriers[row['id']]=row
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']
            and (previous['complete'] or not value['complete']));stamp(a,floor=previous['clockAfter'])
        for key,mutable in (('roots',{'alive','destroyed'}),('navigations',{'returned'}),('carriers',{'alive','retired','retireReturned','destroyed','bindings'})):
            need(len(value[key])>=len(previous[key]))
            for old,new in zip(previous[key],value[key]):
                need({k:v for k,v in old.items() if k not in mutable}=={k:v for k,v in new.items() if k not in mutable})
                for field in mutable-{'alive','bindings'}:
                    if field in old:need(new.get(field)==old[field])
                if 'alive' in old:need(old['alive'] or not new['alive'])
                if key=='carriers':
                    need(len(new['bindings'])>=len(old['bindings']))
                    for before,after in zip(old['bindings'],new['bindings']):
                        dynamic={'current','contextAlive','pageAlive','revoked','returned'}
                        need({k:v for k,v in before.items() if k not in dynamic}=={k:v for k,v in after.items() if k not in dynamic})
                        for field in dynamic-{'revoked','returned'}:need(before[field] or not after[field])
                        for field in ('revoked','returned'):
                            if field in before:need(after.get(field)==before[field])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def inline(value,identity):
    original(value);need(value['complete']);rows=[row for row in value['carriers'] if row['identity']==identity];need(len(rows)==1)
    row=rows[0];need(row['alive'] and 'retired' not in row);bindings=[binding for binding in row['bindings'] if binding['current']];need(len(bindings)==1 and 'returned' in bindings[0])
    return deepcopy(row),deepcopy(bindings[0])


def retired(value,identity):
    original(value);need(value['complete']);rows=[row for row in value['carriers'] if row['identity']==identity];need(len(rows)==1)
    row=rows[0];need(not row['alive'] and 'destroyed' in row and 'retired' in row and 'retireReturned' in row
        and all(not binding['current'] and 'revoked' in binding and not binding['pageAlive'] for binding in row['bindings']))
    return deepcopy(row)


class IOSTabletSources(IOSWorldWebSource):
    # Reuse the bounded guarded transport only; no WorldWeb DTO is translated.
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
