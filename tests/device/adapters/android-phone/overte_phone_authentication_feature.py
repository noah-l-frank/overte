"""Phone Authentication run attachment and original fixture-phase observations.

This module never registers/activates a run or substitutes requested outcomes
for measured account state. The full feature owner is composed on this source.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import Client
from overte_phone_account_fixture import origin as fixture_origin
from overte_phone_authentication import provider_status

FIXTURE_READER_VERSION=1


class AuthenticationPhasePending(NativeUIError):
    """An independent actor must wait for the existing input/phase transaction."""


class AuthenticationRunRetired(AuthenticationPhasePending):
    def __init__(self,status):
        super().__init__('Owned Authentication fixture run has retired')
        self.status=deepcopy(status)


class AuthenticationFixtureReader:
    def __init__(self,client,run,*,epoch_ms=lambda:int(time.time()*1000)):
        identifier(run);need(isinstance(client,Client) and callable(epoch_ms))
        fixture_origin(client.url)
        need(getattr(client,'run',None) in (None,run) and getattr(client,'area',None) in (None,'authentication')
             and getattr(client,'closed',False) is False)
        self.client,self.run,self.epoch_ms=client,run,epoch_ms
        self.fixture_url=client.url+'/runs/'+run+'/'
        self.instance=getattr(client,'account_instance',None)
        if self.instance is not None:identifier(self.instance)
        self.last_clock=None

    def clock(self):
        current=self.epoch_ms();need(number(current,1,1e15) and (self.last_clock is None or current>=self.last_clock))
        self.last_clock=current;return current

    def active(self,value):
        exact(value,{'schemaVersion','runId','area','ticket','stimulus'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1
             and value['runId']==self.run and value['area']=='authentication')
        identifier(value['ticket']);exact(value['stimulus'],{'verb','inputs'})
        if value['stimulus']['verb'] in ('baseline','cleanup'):need(value['stimulus']['inputs']=={})
        else:arguments('feature.authentication.act',dict(contractVersion=CONTRACT_VERSION,runId=self.run,
            fixtureUrl=self.fixture_url,ticket=value['ticket'],**value['stimulus']))
        return value

    def attach(self):
        need(getattr(self.client,'run',None) in (None,self.run)
             and getattr(self.client,'area',None) in (None,'authentication')
             and getattr(self.client,'closed',False) is False
             and integer(getattr(self.client,'account_epoch',0)) and integer(getattr(self.client,'account_sequence',0)))
        prior_instance=getattr(self.client,'account_instance',None)
        if prior_instance is not None:identifier(prior_instance)
        if self.instance is not None:need(prior_instance==self.instance)
        provider=self.client.request('/account-provider')
        exact(provider,{'providerVersion','instance','transport','tlsVersion','internalErrors'})
        need(type(provider['providerVersion']) is int and provider['providerVersion']==2
             and provider['transport']=='https' and provider['tlsVersion'] in ('TLSv1.2','TLSv1.3')
             and type(provider['internalErrors']) is int and provider['internalErrors']==0)
        identifier(provider['instance']);need(self.instance in (None,provider['instance']) and prior_instance in (None,provider['instance']))
        self.instance=provider['instance']
        # Attach metadata to this role's credentialed existing Client only.
        # Client.register/activate/credentials/control are never called here.
        self.client.run,self.client.area=self.run,'authentication'
        self.client.account_instance=self.instance
        self.client.account_epoch=getattr(self.client,'account_epoch',0)
        self.client.account_sequence=getattr(self.client,'account_sequence',0)
        self.client.closed=getattr(self.client,'closed',False)

    def read(self,previous=None):
        self.attach()
        if previous is not None:
            provider_status(previous,self.run,self.instance,previous['capturedEpochMs'])
            self.client.account_epoch=max(self.client.account_epoch,previous['capturedEpochMs'])
            self.client.account_sequence=max(self.client.account_sequence,previous['eventSequence'])
        status=self.client.account_status();provider_status(status,self.run,self.instance,int(self.clock()))
        if not status['accountExists']:
            need(not status['grantsEnabled'] and not status['armedHold']
                 and not any(status[key] for key in ('heldRequests','inflightRequests','accessTokens','refreshTokens')))
            raise AuthenticationRunRetired(status)
        active=deepcopy(self.active(self.client.request('/runs/'+self.run+'/active')))
        original=self.client.observe()
        exact(original,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(original['schemaVersion']) is int and original['schemaVersion']==1 and original['runId']==self.run
             and original['area']=='authentication' and type(original['entries']) is list and len(original['entries'])<=512
             and number(original['sampleEpochMs'],1,1e15)
             and -250<=self.clock()-original['sampleEpochMs']<=1500)
        identifier(original['ticket'])
        if original['ticket']!=active['ticket']:
            raise AuthenticationPhasePending('Original Authentication fixture phase changed during its read')
        # This is a fresh original host read barrier, not an activation time or
        # measured product state. Native acquisition must follow it.
        return deepcopy(dict(ticket=active['ticket'],verb=active['stimulus']['verb'],inputs=active['stimulus']['inputs'],
            afterEpochMs=math.ceil(original['sampleEpochMs']),status=status))
