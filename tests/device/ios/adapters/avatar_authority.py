"""Read actual owned Avatar account authority; never a client login verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,integer,need,number
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from feature_journeys.avatar_accounts import session_binding
from ios.adapters.authentication_origin import origin
from ios.adapters.authentication_samples import provider_status

VERSION=1
ROLES=('primary','actor')


class AvatarAuthorityReader:
    def __init__(self,client,run,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        need(isinstance(client,Client) and callable(epoch_ms) and callable(monotonic));identifier(run);origin(client.url)
        self.client,self.run,self.epoch_ms,self.monotonic=client,run,epoch_ms,monotonic
        self.last=None;self.last_epoch=self.last_mono=None

    def validate(self,value,epoch,previous=None):
        exact(value,{'avatarAccountsVersion','instance','runId','ticket','phase','providerInstance','socialInstance','accounts','social'}
            | ({'sessionBinding'} if 'sessionBinding' in value else set()))
        need(type(value['avatarAccountsVersion']) is int and value['avatarAccountsVersion']==VERSION and value['runId']==self.run
             and value['phase'] in ('allocated','ready','revoking'))
        for key in ('instance','providerInstance','socialInstance'):identifier(value[key])
        identifier(value['ticket']);exact(value['accounts'],set(ROLES));children=set()
        for role in ROLES:
            row=value['accounts'][role];identifier(row['runId']);children.add(row['runId'])
            need(row['runId']!=self.run);provider_status(row,row['runId'],value['providerInstance'],epoch)
            if value['phase'] in ('allocated','ready'):need(row['accountExists'] and row['grantsEnabled'])
        need(len(children)==2)
        if value['phase']=='allocated':need(value['social'] is None)
        else:need(value['social'] is None or type(value['social']) is dict)
        if 'sessionBinding' in value:session_binding(value['sessionBinding'])
        if previous:
            for key in ('instance','providerInstance','socialInstance','runId'):need(value[key]==previous[key])
            if 'sessionBinding' in previous:need('sessionBinding' in value and value['sessionBinding']==previous['sessionBinding'])
            for role in ROLES:
                left,right=previous['accounts'][role],value['accounts'][role]
                need(left['runId']==right['runId'] and right['capturedEpochMs']>=left['capturedEpochMs']
                     and right['eventSequence']>=left['eventSequence'])
            need(previous['phase']!='revoking' or value['phase']=='revoking')
            need(previous['phase']!='ready' or value['phase'] in ('ready','revoking'))
        return deepcopy(value)

    def read(self):
        before=self.epoch_ms();started=self.monotonic()
        need(number(before,1,1e15) and number(started,0,1e15)
             and (self.last_epoch is None or before>=self.last_epoch) and (self.last_mono is None or started>=self.last_mono))
        value=self.client.request('/runs/'+self.run+'/avatar/accounts')
        after=self.epoch_ms();ended=self.monotonic()
        need(number(after,before,before+1500) and number(ended,started,started+1.5)
             and after-before<1500 and ended-started<1.5)
        value=self.validate(value,after,self.last)
        for row in value['accounts'].values():need(max(after-row['capturedEpochMs'],before-row['capturedEpochMs']+(ended-started)*1000)<=1500)
        self.last,self.last_epoch,self.last_mono=deepcopy(value),after,ended
        return deepcopy(value)

    def credentials(self,role):
        need(role in ROLES);actual=self.read();need(actual['phase'] in ('allocated','ready'))
        value=self.client.request('/runs/'+self.run+'/avatar/credentials/'+role)
        exact(value,{'username','password'})
        need(value['username']=='e2e-'+actual['accounts'][role]['runId']
             and type(value['password']) is str and 1<=len(value['password'])<=4096
             and all(32<=ord(c)<=126 for c in value['password']))
        # Never cache credentials in this reader or any public evidence object.
        return deepcopy(value)
