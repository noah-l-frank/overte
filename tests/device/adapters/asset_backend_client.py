"""Narrow passive Assets backend reader; no domain-control authority.

The caller supplies durable command intents and its current native/process
guard. Exports preserve both original byte identity and acquisition clocks.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,Request,build_opener
from adapters import asset_backend_source as source
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from fixture.asset_backend_control import command

VERSION=1
LIMIT=4*1024*1024


def configuration(value):
    exact(value,{'url','token','domainId','processIdentity','executableSha256','ownerSha256','sourceRootIdentity'})
    need(type(value['url']) is str);parsed=urlsplit(value['url'])
    try:valid=parsed.scheme=='http' and parsed.hostname is not None and ipaddress.ip_address(parsed.hostname).is_loopback and parsed.port is not None
    except ValueError:valid=False
    need(valid and parsed.path=='/v1/assets-backend' and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
        and type(value['token']) is str and re.fullmatch('[A-Za-z0-9_-]{40,128}',value['token']) is not None
        and type(value['processIdentity']) is str and re.fullmatch('[1-9][0-9]{0,9}:[1-9][0-9]{0,19}:[a-f0-9-]{36}',value['processIdentity']) is not None)
    source.work.identity(value['processIdentity'].rsplit(':',1)[1]);source.work.identity(value['domainId']);source.digest(value['executableSha256']);source.digest(value['ownerSha256']);source.root_identity(value['sourceRootIdentity']);return value


def original_record(value,limit):
    exact(value,{'reference','base64'});reference=value['reference'];exact(reference,{'name','identity','sha256'});source.stat(reference['identity']);source.digest(reference['sha256'])
    need(reference['identity']['mode']==str(0o600) and type(value['base64']) is str and len(value['base64'])<=4*((limit+2)//3))
    try:raw=base64.b64decode(value['base64'],validate=True)
    except (ValueError,TypeError):need(False)
    need(len(raw)==int(reference['identity']['bytes']) and len(raw)<=limit and base64.b64encode(raw).decode()==value['base64'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
    return raw,source.object_bytes(raw,limit)


def export(value,query,config):
    command(query);configuration(config)
    exact(value,{'assetBackendExportVersion','processIdentity','executableSha256','hostBefore','hostAfter','admission','intent','original','saved'})
    need(type(value['assetBackendExportVersion']) is int and value['assetBackendExportVersion']==VERSION
        and all(value[key]==config[key] for key in ('processIdentity','executableSha256')))
    for clock in ('hostBefore','hostAfter'):
        exact(value[clock],{'hostEpochMs','hostMonotonicMs'});need(all(source.integer(item,1) for item in value[clock].values()))
    need(all(value['hostAfter'][key]>=value['hostBefore'][key] for key in value['hostBefore']))
    _,admission=original_record(value['admission'],8192);source.admission(admission,pid=int(config['processIdentity'].split(':')[0]),owner=config['ownerSha256'])
    need(admission['domainId']==config['domainId'] and same(admission['sourceRootIdentity'],config['sourceRootIdentity'])
        and value['admission']['reference']['name']=='asset-backend-admission.json')
    _,intent=original_record(value['intent'],4096);source.query(intent,admission)
    need(all(intent[key]==query[key] for key in ('commandId','runId','ticket')) and value['intent']['reference']['name']=='asset-backend-query-'+query['commandId']+'.json')
    raw,packet=original_record(value['original'],2097152);source.observation(packet,intent,admission,value['admission']['reference']['sha256'])
    _,receipt=original_record(value['saved'],8192);source.saved(receipt,packet,raw)
    need(value['saved']['reference']['name']=='asset-backend-saved-'+query['commandId']+'.json'
        and value['original']['reference']['name']==receipt['original']['file'] and value['original']['reference']['identity']==receipt['original']['identity'])
    return packet


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*_args,**_kwargs):raise ValueError('Assets reader redirects are unavailable')


class AssetsBackendClient:
    def __init__(self,config,guard):
        self.config=deepcopy(configuration(config));need(callable(guard));self.guard=guard;self.latest=None

    def request(self,query,*,before_send):
        command(query);need(callable(before_send) and self.guard() is not False)
        # The caller owns the durable intent. An exception or missing receipt
        # forbids even this passive request, including polls and original reads.
        need(before_send(deepcopy(query)) is True and self.guard() is not False)
        raw=json.dumps(query,separators=(',',':'),allow_nan=False).encode();need(len(raw)<=1024)
        request=Request(self.config['url'],data=raw,method='POST',headers={'Content-Type':'application/json','X-Overte-Assets-Reader':self.config['token']})
        from adapters.operation_transport_guard import check as final_transport_guard
        final_transport_guard()
        with build_opener(NoRedirect()).open(request,timeout=5) as response:
            raw=response.read(LIMIT+1);need(response.status==200 and len(raw)<=LIMIT)
        need(self.guard() is not False)
        # The generic JSON decoder ceiling is deliberately unchanged. Decode
        # only this bounded outer byte envelope with the same duplicate guards.
        def pairs(rows):
            result={}
            for key,item in rows:need(key not in result);result[key]=item
            return result
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _value:need(False))
        exact(value,{'assetsBackendControlVersion','requestId','runId','ticket','status','original'})
        need(type(value['assetsBackendControlVersion']) is int and value['assetsBackendControlVersion']==VERSION
            and value['requestId']==query['commandId'] and all(value[key]==query[key] for key in ('runId','ticket')) and value['status'] in ('pending','original'))
        if value['status']=='pending':need(value['original'] is None);return value
        packet=export(value['original'],query,self.config)
        if query['operation']=='original':return value
        if self.latest is not None and packet['requestId']==self.latest['requestId']:need(same(packet,self.latest))
        else:self.latest=source.accept(self.latest,packet)
        return value
