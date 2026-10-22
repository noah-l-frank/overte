"""Read-only Avatar/People attachment to original HTTPS service and phases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,fresh,need
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.avatar_people_service import session,validate_status
from feature_journeys.contract import identifier


class AvatarPeopleFixtureReader(PhaseFixtureReader):
    def __init__(self,client,run,**options):
        super().__init__(client,run,'avatar-people',**options)
        self.instance=getattr(client,'avatar_people_instance',None);self.domain=getattr(client,'avatar_people_domain',None)
        self.backend=getattr(client,'avatar_people_previous',None)
        parsed=urlsplit(client.url);need(parsed.scheme=='https');self.origin=parsed.scheme+'://'+parsed.netloc
    def attach(self):
        need(getattr(self.client,'run',None) in (None,self.run) and getattr(self.client,'area',None) in (None,self.area))
        provider=self.client.request('/avatar-people-provider')
        exact(provider,{'avatarPeopleServiceVersion','instance','domainId','transport','tlsVersion','internalErrors'})
        need(type(provider['avatarPeopleServiceVersion']) is int and provider['avatarPeopleServiceVersion']==1 and provider['transport']=='https'
            and provider['tlsVersion'] in ('TLSv1.2','TLSv1.3') and type(provider['internalErrors']) is int and provider['internalErrors']==0)
        identifier(provider['instance']);session(provider['domainId'])
        need(self.instance in (None,provider['instance']) and self.domain in (None,provider['domainId']))
        self.instance,self.domain=provider['instance'],provider['domainId']
        self.client.run,self.client.area=self.run,self.area
        self.client.avatar_people_instance,self.client.avatar_people_domain=self.instance,self.domain
        if not hasattr(self.client,'avatar_people_previous'):self.client.avatar_people_previous=None
    def status_backend(self,previous=None):
        self.attach();value=self.client.avatar_people_status()
        for old in (self.backend,previous):
            if old is not None and old['requestId']!=value['requestId']:validate_status(value,run=self.run,request=value['requestId'],instance=self.instance,previous=old)
        fresh(value['capturedEpochMs'],self.epoch_ms());need(value['domainId']==self.domain)
        self.backend=deepcopy(value);return deepcopy(value)
    def read(self,previous=None):
        self.attach();phase=super().read(previous);backend=self.status_backend()
        need(backend['active'] and backend['ticket']==phase['ticket']);phase['backend']=backend;return phase
    def credentials(self,role):
        need(role in ('primary','peer'));self.attach()
        value=self.client.request('/runs/'+self.run+'/avatar-people/credentials/'+role)
        exact(value,{'username','password'});need(all(type(v) is str and 0<len(v)<=4096 for v in value.values()))
        status=self.status_backend();need(value['username']==status['principals'][role]);return value
