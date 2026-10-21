"""Read-only attachment to an existing Graphics run and its original phase."""
# Pure read-only fixture attachment selected from frozen fe4684bf46585088370b3a328a738f147e670b97.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.graphics_resources import fixture_url,validate_status
from feature_journeys.witness import Client
from adapters.script_feature.history import same

VERSION=1


class GraphicsPhasePending(NativeUIError):
    """An actual existing fixture phase crossed a read-only observation."""


class GraphicsRunRetired(GraphicsPhasePending):
    def __init__(self,status):
        super().__init__('Original owned Graphics fixture run has retired')
        self.status=deepcopy(status)


class GraphicsFixtureReader:
    def __init__(self,client,run,*,epoch_ms=lambda:int(time.time()*1000)):
        identifier(run);need(isinstance(client,Client) and callable(epoch_ms));fixture_url(client.url)
        need(getattr(client,'run',None) in (None,run) and getattr(client,'area',None) in (None,'graphics')
            and type(getattr(client,'closed',False)) is bool)
        self.client,self.run,self.epoch_ms=client,run,epoch_ms
        self.base_url=client.url
        self.fixture_url=client.url+'/runs/'+run+'/'
        self.instance=getattr(client,'graphics_instance',None)
        if self.instance is not None:identifier(self.instance)
        self.previous=None;self.last_clock=None

    def clock(self):
        now=self.epoch_ms();need(number(now,1,1e15) and (self.last_clock is None or now>=self.last_clock))
        self.last_clock=now;return now

    def attach(self):
        need(self.client.url==self.base_url and getattr(self.client,'run',None) in (None,self.run) and getattr(self.client,'area',None) in (None,'graphics')
            and type(getattr(self.client,'closed',False)) is bool)
        previous=getattr(self.client,'graphics_previous',None)
        instance=getattr(self.client,'graphics_instance',None)
        if instance is not None:identifier(instance)
        if self.instance is not None:need(instance==self.instance)
        if previous is not None:
            need(instance is not None and type(previous) is dict)
            validate_status(previous,instance=instance,run=self.run,url=self.client.url,request=previous['requestId'])
        if self.previous is not None and previous is not None:
            # Another component on this same credentialed Client may have read
            # since our last read. It may advance history, never replace it.
            if not same(previous,self.previous):validate_status(previous,instance=instance,run=self.run,
                url=self.client.url,request=previous['requestId'],previous=self.previous)
        self.client.run,self.client.area=self.run,'graphics'
        if not hasattr(self.client,'graphics_instance'):self.client.graphics_instance=None
        if not hasattr(self.client,'graphics_previous'):self.client.graphics_previous=None
        if not hasattr(self.client,'closed'):self.client.closed=False

    def status(self,previous=None):
        self.attach()
        if previous is not None:
            need(self.instance is not None and type(previous) is dict)
            validate_status(previous,instance=self.instance,run=self.run,url=self.client.url,request=previous['requestId'])
            if self.previous is None:self.previous=deepcopy(previous)
            elif not same(self.previous,previous):
                # Independent samplers on this Client can advance the provider
                # between our reads. Adopt only a qualified prefix extension;
                # an older caller floor must instead be a prefix of ours.
                # An old active floor cannot revive an already retired source,
                # including equal original epochs and activation-prefix lengths.
                advances=((self.previous['active'] or not previous['active']) and
                    previous['capturedEpochMs']>=self.previous['capturedEpochMs'] and all(
                    len(previous[key])>=len(self.previous[key]) for key in ('activations','responses')))
                if advances:
                    validate_status(previous,instance=self.instance,run=self.run,url=self.client.url,
                        request=previous['requestId'],previous=self.previous)
                    self.previous=deepcopy(previous)
                else:
                    validate_status(self.previous,instance=self.instance,run=self.run,url=self.client.url,
                        request=self.previous['requestId'],previous=previous)
            current=getattr(self.client,'graphics_previous',None)
            if current is None:self.client.graphics_previous=deepcopy(self.previous)
            elif not same(current,self.previous):validate_status(current,instance=self.instance,run=self.run,
                url=self.client.url,request=current['requestId'],previous=self.previous)
        before=deepcopy(self.previous)
        value=self.client.graphics_status()
        identifier(getattr(self.client,'graphics_instance',None))
        need(self.instance in (None,self.client.graphics_instance))
        self.instance=self.client.graphics_instance
        validate_status(value,instance=self.instance,run=self.run,url=self.client.url,request=value['requestId'],previous=before)
        fresh(value['capturedEpochMs'],self.clock())
        need(not self.client.closed or value['active'] is False)
        self.previous=deepcopy(value);return deepcopy(value)

    def active(self,value):
        exact(value,{'schemaVersion','runId','area','ticket','stimulus'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.run and value['area']=='graphics')
        identifier(value['ticket']);exact(value['stimulus'],{'verb','inputs'})
        if value['stimulus']['verb'] in ('baseline','cleanup'):need(value['stimulus']['inputs']=={})
        else:arguments('feature.graphics.act',dict(contractVersion=CONTRACT_VERSION,runId=self.run,
            fixtureUrl=self.fixture_url,ticket=value['ticket'],**value['stimulus']))
        return value

    def read(self,previous=None):
        first=self.status(previous)
        if not first['active']:raise GraphicsRunRetired(first)
        active=deepcopy(self.active(self.client.request('/runs/'+self.run+'/active')))
        original=self.client.observe()
        exact(original,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(original['schemaVersion']) is int and original['schemaVersion']==1 and original['runId']==self.run
            and original['area']=='graphics' and type(original['entries']) is list and len(original['entries'])<=512
            and number(original['sampleEpochMs'],1,1e15))
        identifier(original['ticket']);fresh(original['sampleEpochMs'],self.clock())
        last=self.status()
        if not last['active']:raise GraphicsRunRetired(last)
        if len({first['ticket'],active['ticket'],original['ticket'],last['ticket']})!=1:
            raise GraphicsPhasePending('Original Graphics fixture phase changed during its read')
        need(last['activations'][-1]['activatedEpochMs']<=original['sampleEpochMs']<=last['capturedEpochMs'])
        # This is an original fixture read barrier. It is not an activation
        # timestamp, native clock, requested setting or measured product result.
        return deepcopy(dict(ticket=active['ticket'],verb=active['stimulus']['verb'],inputs=active['stimulus']['inputs'],
            afterEpochMs=math.ceil(original['sampleEpochMs']),status=last))
