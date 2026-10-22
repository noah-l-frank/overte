"""Read-only attachment to actual phase and independently owned HTTP histories."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,fresh,need
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.navigation_fixture import configuration,validate_status
from overte_phone_script_history import same


class NavigationFixtureReader(PhaseFixtureReader):
    def __init__(self,client,run,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        super().__init__(client,run,'world-navigation',epoch_ms=epoch_ms,monotonic=monotonic)
        need(getattr(client,'run',None) in (None,run) and getattr(client,'area',None) in (None,'world-navigation')
            and getattr(client,'closed',False) is False)
        self.instance=getattr(client,'navigation_instance',None);self.inputs=getattr(client,'navigation_inputs',None)
        self.backend=getattr(client,'navigation_previous',None)

    def attach(self):
        need(getattr(self.client,'run',None) in (None,self.run) and getattr(self.client,'area',None) in (None,self.area))
        provider=self.client.request('/navigation-provider')
        exact(provider,{'navigationProviderVersion','instance','inputs','capturedEpochMs','ready','activeRuns','failedResponses','internalErrors'})
        need(type(provider['navigationProviderVersion']) is int and provider['navigationProviderVersion']==1
            and type(provider['ready']) is bool and type(provider['activeRuns']) is int and provider['activeRuns'] in (0,1)
            and type(provider['failedResponses']) is int and provider['failedResponses']==0
            and type(provider['internalErrors']) is int and provider['internalErrors']==0)
        identifier(provider['instance']);inputs,_=configuration(provider['inputs']);fresh(provider['capturedEpochMs'],self.epoch_ms())
        need(self.instance in (None,provider['instance']) and (self.inputs is None or same(self.inputs,inputs)))
        self.instance,self.inputs=provider['instance'],inputs
        self.client.run,self.client.area=self.run,self.area
        self.client.navigation_instance,self.client.navigation_inputs=self.instance,deepcopy(self.inputs)
        if not hasattr(self.client,'navigation_previous'):self.client.navigation_previous=None

    def navigation(self,previous=None):
        self.attach();before=self.backend
        if previous is not None:
            validate_status(previous,instance=self.instance,run=self.run,inputs=self.inputs)
            if before is None:before=previous
            elif not same(before,previous):
                if before['capturedEpochMs']>=previous['capturedEpochMs']:validate_status(before,instance=self.instance,run=self.run,inputs=self.inputs,previous=previous)
                else:validate_status(previous,instance=self.instance,run=self.run,inputs=self.inputs,previous=before);before=previous
        value=self.client.navigation_status();validate_status(value,instance=self.instance,run=self.run,inputs=self.inputs,previous=before)
        fresh(value['capturedEpochMs'],self.epoch_ms());self.backend=deepcopy(value);return deepcopy(value)

    def read(self,previous=None):
        self.attach();active=super().read(previous)
        backend=self.navigation()
        need(backend['active'] and backend['ticket']==active['ticket'])
        active['navigation']=backend;return active
