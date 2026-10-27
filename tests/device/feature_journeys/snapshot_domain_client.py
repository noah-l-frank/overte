"""Narrow passive owned-domain reader; no domain-control credential or action."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import ipaddress
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request,build_opener
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from fixture.create_rez_authority import NoRedirect,process


def configuration(value):
    exact(value,{'url','token','binding','instance'});url=urlsplit(value['url'])
    need(url.scheme=='http' and url.hostname is not None and ipaddress.ip_address(url.hostname).is_loopback and url.port is not None
        and url.path=='/v1/snapshot-domain-policy' and not url.username and not url.password and not url.query and not url.fragment
        and type(value['token']) is str and re.fullmatch('[A-Za-z0-9_-]{32,128}',value['token']))
    process(value['binding']);identifier(value['instance']);return value


def public_configuration(value):
    exact(value,{'url','tokenSha256','binding','instance'});url=urlsplit(value['url'])
    need(url.scheme=='http' and url.hostname is not None and ipaddress.ip_address(url.hostname).is_loopback and url.port is not None
        and url.path=='/v1/snapshot-domain-policy' and not url.username and not url.password and not url.query and not url.fragment
        and type(value['tokenSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['tokenSha256']))
    process(value['binding']);identifier(value['instance']);return value


def packet(value,config,run,nonce):
    configuration(config);return _packet(value,config,run,nonce)


def public_packet(value,config,run,nonce):
    public_configuration(config);return _packet(value,config,run,nonce)


def _packet(value,config,run,nonce):
    identifier(run);identifier(nonce)
    exact(value,{'snapshotDomainPolicyVersion','instance','sequence','runId','requestId','binding','clockDomain','clockBefore','clockAfter','domainId','online',
        'standardConnect','restriction','idOriginal','settingsOriginal','externalRegistrationRequired','controlledFixtureProjectionOnly','resourceRetirementRequired'})
    need(type(value['snapshotDomainPolicyVersion']) is int and value['snapshotDomainPolicyVersion']==1 and integer(value['sequence'],1)
        and value['instance']==config['instance'] and value['runId']==run and value['requestId']==nonce and same(process(value['binding']),config['binding'])
        and value['domainId']==config['binding']['domainId'] and value['domainId']!='00000000-0000-0000-0000-000000000000' and value['online'] is True
        and value['clockDomain']=='owned-domain-policy-host' and value['externalRegistrationRequired'] is value['controlledFixtureProjectionOnly'] is value['resourceRetirementRequired'] is True)
    for clock in ('clockBefore','clockAfter'):
        exact(value[clock],{'epochMs','monotonicMs'});need(integer(value[clock]['epochMs'],1) and number(value[clock]['monotonicMs'],0,1e15))
    elapsed={key:value['clockAfter'][key]-value['clockBefore'][key] for key in ('epochMs','monotonicMs')};need(all(0<=item<5000 for item in elapsed.values()) and abs(elapsed['epochMs']-elapsed['monotonicMs'])<=250)
    policy=value['standardConnect'];exact(policy,{'anonymous','loggedIn'});need(type(policy['anonymous']) is type(policy['loggedIn']) is bool)
    need(value['restriction']==('open' if policy['anonymous'] else 'hifi' if policy['loggedIn'] else 'acl'))
    for key,limit in (('idOriginal',128),('settingsOriginal',1024*1024)):
        original=value[key];exact(original,{'bytes','sha256'});need(integer(original['bytes'],1,limit) and type(original['sha256']) is str and re.fullmatch('[0-9a-f]{64}',original['sha256']))
    return value


class SnapshotDomainClient:
    def __init__(self,config,*,guard=lambda:True,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        self.config=deepcopy(configuration(config));need(all(callable(value) for value in (guard,epoch_ms,monotonic)))
        self.guard,self.epoch_ms,self.monotonic=guard,epoch_ms,monotonic;self.latest=None
    def public(self):
        return {**{key:deepcopy(value) for key,value in self.config.items() if key!='token'},'tokenSha256':hashlib.sha256(self.config['token'].encode()).hexdigest()}
    def read(self,run,nonce):
        identifier(run);identifier(nonce);need(self.guard() is not False);before=dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000)
        request=Request(self.config['url'],method='GET',headers={'X-Overte-Snapshot-Domain-Reader':self.config['token'],'X-Overte-Snapshot-Run':run,'X-Overte-Snapshot-Read':nonce})
        from adapters.operation_transport_guard import check as final_transport_guard
        final_transport_guard()
        with build_opener(NoRedirect()).open(request,timeout=5) as response:
            raw=response.read(16385);need(response.status==200 and len(raw)<=16384)
        need(self.guard() is not False);after=dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000)
        elapsed={key:after[key]-before[key] for key in before};need(all(0<=value<5000 for value in elapsed.values()) and abs(elapsed['epochMs']-elapsed['monotonicMs'])<=250)
        value=packet(decode(raw.decode('utf-8'),limit=16384),self.config,run,nonce)
        need(before['epochMs']-250<=value['clockBefore']['epochMs']<=value['clockAfter']['epochMs']<=after['epochMs']+250 and after['epochMs']-value['clockAfter']['epochMs']<=1500)
        if self.latest is not None:
            old=self.latest['packet'];need(value['instance']==old['instance'] and same(value['binding'],old['binding']))
            if value['requestId']==old['requestId']:need(same(value,old) and raw==self.latest['raw'])
            else:need(value['sequence']>old['sequence'] and all(value['clockBefore'][key]>=old['clockAfter'][key] for key in ('epochMs','monotonicMs')))
        record=dict(packet=deepcopy(value),raw=raw,hostBefore=before,hostAfter=after,configuration=self.public())
        self.latest=deepcopy(record);return record
