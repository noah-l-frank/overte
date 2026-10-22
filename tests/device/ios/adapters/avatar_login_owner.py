"""Ordinary Avatar account preparation with retained one-send ownership.

Native login/logout events and a separate protected native request establish
account use. Provider scopes supply input authority only. Interrupted input is
retained; reconstruction does not submit credentials or replay a pointer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from adapters.native_account_probe import bind_to_account,validate as probe_packet
from adapters.native_account_origin import validate as origin_packet
from adapters.native_feature_observation import exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import VERSION as CONTRACT_VERSION,identifier
from ios.adapters.account_preferences import validate_basis,validate_intent
from ios.adapters.authentication_causality import wait as account_ready,check as account_causality
from ios.adapters.authentication_samples import _native
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_runtime import IOSAvatarLoginRuntime
from ios.adapters.login_source import validate as login_packet

VERSION=1
EMPTY=hashlib.sha256(b'').hexdigest()


class AvatarLoginPending(NativeUIError):pass


class IOSAvatarLoginOwner:
    def __init__(self,runtime,selector,authority,lock,*,monotonic=time.monotonic,sleep=time.sleep,epoch_ms=lambda:time.time()*1000):
        need(isinstance(runtime,IOSAvatarLoginRuntime) and isinstance(authority,AvatarAuthorityReader)
             and isinstance(lock,ScriptSourceLock) and all(callable(fn) for fn in (monotonic,sleep,epoch_ms)))
        self.runtime,self.selector,self.authority,self.lock=runtime,selector,authority,lock
        self.monotonic,self.sleep,self.epoch_ms=monotonic,sleep,epoch_ms
        self.run,self.child,self.role=runtime.avatar_run,runtime.run,runtime.avatar_role
        need(authority.run==self.run and lock.path==runtime.state_path(selector).with_name('script-feature-sources.lock'))
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-avatar-'+self.role+'-login.json'))
        self.previous=self.state=None;self.failed=False
        self.principal=hashlib.sha256(('e2e-'+self.child).encode()).hexdigest()
        self.endpoints={hashlib.sha256(value.encode()).hexdigest() for value in (runtime.origin,runtime.origin+'/')}

    def envelope(self,state):
        return dict(iosAvatarLoginOwnerVersion=VERSION,runId=self.run,childRunId=self.child,role=self.role,payload=pack([state]))

    def scope(self,packet):
        native_packet(packet,packet.get('requestId'),packet.get('processId'),packet.get('capturedEpochMs'),require_account=True)
        value=packet['account'];observed=value['observation']
        need(value['principalSha256'] in (EMPTY,self.principal) and observed['credentialActive']
             and observed['endpointPresent'] and observed['endpointSha256'] in self.endpoints)

    def decode(self,value):
        exact(value,{'iosAvatarLoginOwnerVersion','runId','childRunId','role','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'binding','preferences','phase','samples','actions','protected','restoration'})
        context(state['binding']);basis=validate_basis(state['preferences'],self.runtime.origin)
        need(same(basis['binding'],state['binding']) and state['phase'] in ('prepared','login-issued','logged-in','logout-issued','logged-out','restore-issued','restored')
             and type(state['samples']) is list and 1<=len(state['samples'])<=256 and type(state['actions']) is list and len(state['actions'])<=3
             and type(state['protected']) is list and len(state['protected'])<=16)
        from adapters.native_account_observation import accept
        previous=None;account=None
        for packet in state['samples']:
            self.scope(packet);need(str(packet['processId'])==state['binding']['processIdentity'])
            account=accept(account,packet['account'])
            if previous:need(packet['requestId']!=previous['requestId'] and packet['instance']==previous['instance']
                and packet['sequence']>previous['sequence'] and packet['capturedEpochMs']>=previous['capturedEpochMs'])
            previous=packet
        stages=('login-submit','logout','restore')
        phases={'prepared':(0,False),'login-issued':(1,False),'logged-in':(1,True),'logout-issued':(2,False),
                'logged-out':(2,True),'restore-issued':(3,False),'restored':(3,True)}
        count,complete=phases[state['phase']];need(len(state['actions'])==count)
        for index,action in enumerate(state['actions']):
            exact(action,{'verb','ticket','before','after','intents','complete'});identifier(action['ticket'])
            need(action['verb'] in ('login-submit','logout','restore') and integer(action['before'],0,len(state['samples'])-1)
                 and type(action['intents']) is list and len(action['intents'])<=32 and type(action['complete']) is bool)
            need(action['verb']==stages[index] and action['complete']==(True if index<count-1 else complete))
            if action['complete']:
                need(integer(action['after'],action['before']+1,len(state['samples'])-1))
                if action['verb']!='restore':
                    call=dict(contractVersion=CONTRACT_VERSION,runId=self.child,fixtureUrl=self.authority.client.url+'/runs/'+self.child+'/',
                        ticket=action['ticket'],verb=action['verb'],inputs=dict(account='owned') if action['verb']=='login-submit' else {})
                    after=state['samples'][action['after']]
                    account_causality(call,state['samples'][action['before']],after,after['capturedEpochMs'])
            else:need(action['after'] is None and index==count-1)
            for item in action['intents']:
                exact(item,{'stage','control','original','barrier'});need(type(item['stage']) is str and type(item['control']) is str
                    and integer(item['barrier'],action['before'],len(state['samples'])-1))
                barrier=state['samples'][item['barrier']];original=item['original']
                if set(original)=={'native','receipt'}:
                    validate_intent(original,self.runtime.origin,self.child)
                    need(original['native']['instance']==barrier['instance'])
                elif 'account' in original and 'capturedEpochMs' in original:
                    self.scope(original);native_packet(original,original.get('requestId'),barrier['processId'],barrier['capturedEpochMs'],require_account=True)
                    need(original['instance']==barrier['instance'])
                else:
                    login_packet(original,original.get('commandId'),barrier['processId'],barrier['capturedEpochMs'])
                    pages=[row for row in original['controls'] if row['id']=='login.page']
                    if pages:
                        page=pages[0];account=barrier['account']['observation']
                        need(not page['domain'] and page['accountInstance']==account['instance']
                            and page['credentialGeneration']==account['credentialGeneration'] and page['endpointSha256']==account['endpointSha256'])
        for item in state['protected']:
            exact(item,{'ticket','phase','probe','accountIndex','owners','released','originAbsent'});identifier(item['ticket'])
            need(item['phase'] in ('reading','complete'))
            if item['probe'] is not None:
                need(integer(item['accountIndex'],0,len(state['samples'])-1))
                need(item['probe']['runId']==self.child and item['probe']['ticket']==item['ticket'])
                measured=bind_to_account(item['probe'],state['samples'][item['accountIndex']]['account'])
                need(measured['protectedAccess'] and measured['loggedIn'] and measured['principalSha256']==self.principal)
                owners=item['owners'];exact(owners,{'origin','probe'})
                for owner in owners.values():need(owner['ownershipVersion']==1 and same(owner['binding'],state['binding']))
                exact(owners['origin'],{'ownershipVersion','binding','instance','data'})
                exact(owners['origin']['data'],{'runId','ownerToken','origin'})
                need(owners['origin']['data']['runId']==self.child and owners['origin']['data']['origin']==self.runtime.origin
                    and owners['origin']['instance']==state['samples'][item['accountIndex']]['instance'])
                exact(owners['probe'],{'ownershipVersion','binding','probe'})
                need(owners['probe']['probe']==dict(schemaVersion=1,action='feature-account-probe',**{key:item['probe'][key]
                    for key in ('commandId','requestId','runId','ticket','operation')}))
            if item['released'] is not None:
                need(item['probe'] is not None);released=item['released']
                query=dict(schemaVersion=1,action='feature-account-probe',**{key:released[key] for key in ('commandId','requestId','runId','ticket','operation')})
                probe_packet(released,query,int(state['binding']['processIdentity']),released['capturedEpochMs'])
                need(released['operation']=='inspect' and all(released[key]==item['probe'][key] for key in ('requestId','runId','ticket','instance'))
                    and released['source']==dict(inflight=False,responseBytes=0,credentialBytes=0,released=True))
            if item['originAbsent'] is not None:
                need(item['owners'] is not None);owner=item['owners']['origin'];absent=item['originAbsent']
                query=dict(schemaVersion=1,action='feature-account-origin',commandId=absent['commandId'],operation='observe',
                    runId=self.child,ownerToken=owner['data']['ownerToken'],instance=owner['instance'])
                origin_packet(absent,query,int(state['binding']['processIdentity']),absent['capturedEpochMs'])
                original=absent['source'];need(original['retired'] and not original['originExists'] and not original['ownerExists']
                    and original['originBytes']==original['ownerBytes']==0)
            if item['phase']=='complete':need(item['probe'] is not None and item['released'] is not None and item['originAbsent'] is not None)
        if state['phase']=='restored':
            restored=validate_basis(state['restoration'],self.runtime.origin)
            need(same(restored['binding'],state['binding']) and same(restored['preferences'],basis['preferences']))
        else:need(state['restoration'] is None)
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous))
        source=self.runtime._sources(self.selector);need(same(source['binding'],self.state['binding']) and source['check']() is not False)

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def load(self):
        self.lock.assert_held();self.previous=self.store.read()
        self.state=None if self.previous is None else self.decode(self.previous)
        if self.state:self.bound()
        return deepcopy(self.state)

    def sample(self):
        self.bound();reader=self.runtime._native_feature_observer(self.selector,read_only=True)
        _native(reader,self.state['samples'][-1]);packet=reader.read(reader.sequence,require_account=True)
        self.scope(packet);self.state['samples'].append(deepcopy(packet));self.save();return reader,packet

    def prepare(self):
        with self.lock.held(),self.runtime.existing_input_session(self.selector):
            if self.load() is not None:return deepcopy(self.state)
            actual=self.authority.read();need(actual['phase'] in ('allocated','ready') and actual['accounts'][self.role]['runId']==self.child)
            basis=self.runtime._preference_basis(self.selector);source=self.runtime._sources(self.selector)
            need(all(store.read() is None for store in (self.runtime.account_origin_store(self.selector),
                self.runtime.account_probe_store(self.selector,role=self.role),self.runtime.private_login_input_store(self.selector))))
            reader=self.runtime._native_feature_observer(self.selector,read_only=True);packet=reader.read(reader.sequence,require_account=True)
            self.scope(packet);observed=packet['account']['observation']
            need(not packet['account']['loggedIn'] and packet['account']['principalSha256']==EMPTY
                 and not any(observed[key] for key in ('loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent')))
            self.state=dict(binding=deepcopy(source['binding']),preferences=basis,phase='prepared',samples=[packet],actions=[],protected=[],restoration=None)
            self.save();return deepcopy(self.state)

    def intent(self,stage,original,control):
        self.bound();need(self.state['phase'] in ('login-issued','logout-issued','restore-issued'))
        self.require_authority(self.state['actions'][-1]['ticket'])
        self.sample();action=self.state['actions'][-1]
        action['intents'].append(dict(stage=stage,control=control,original=deepcopy(original),barrier=len(self.state['samples'])-1));self.save()

    def begin(self,verb,ticket,expected,issued):
        identifier(ticket);self.load();need(self.state is not None)
        if self.state['phase']!=expected:raise AvatarLoginPending('Original Avatar account input remains owned; it is not replayed')
        self.require_authority(ticket)
        self.sample();self.state['actions'].append(dict(verb=verb,ticket=ticket,before=len(self.state['samples'])-1,after=None,intents=[],complete=False))
        self.state['phase']=issued;self.save()

    def require_authority(self,ticket):
        actual=self.authority.read()
        need(actual['phase'] in ('allocated','ready') and actual['ticket']==ticket
            and actual['accounts'][self.role]['runId']==self.child)
        return actual

    def terminal(self,verb,ticket):
        action=self.state['actions'][-1];need(action['verb']==verb and action['ticket']==ticket)
        reader,_packet=self.sample()
        call=dict(contractVersion=CONTRACT_VERSION,runId=self.child,fixtureUrl=self.authority.client.url+'/runs/'+self.child+'/',
            ticket=ticket,verb=verb,inputs=dict(account='owned') if verb=='login-submit' else {})
        def record(value):
            self.scope(value['native']);self.state['samples'].append(deepcopy(value['native']));self.save()
        result=account_ready(call,self.state['samples'][action['before']],reader,record=record,
            monotonic=self.monotonic,sleep=self.sleep,epoch_ms=self.epoch_ms)
        packet=result['native'];observed=packet['account']['observation']
        if verb=='login-submit':need(packet['account']['loggedIn'] and packet['account']['principalSha256']==self.principal
            and observed['tokenPresent'] and observed['tokenValid'] and observed['refreshPresent'])
        action.update(complete=True,after=len(self.state['samples'])-1);self.state['phase']='logged-in' if verb=='login-submit' else 'logged-out';self.save()
        return deepcopy(packet)

    def login(self,ticket):
        with self.lock.held(),self.runtime.existing_input_session(self.selector):
            self.begin('login-submit',ticket,'prepared','login-issued')
            controls=self.runtime._login_controls(self.selector,self.intent,self.child,self.runtime.origin)
            controls.open();credentials=self.authority.credentials(self.role)
            try:controls.fill(credentials);controls.submit()
            finally:credentials.clear()
            return self.terminal('login-submit',ticket)

    def logout(self,ticket):
        with self.lock.held(),self.runtime.existing_input_session(self.selector):
            self.begin('logout',ticket,'logged-in','logout-issued')
            self.runtime._account_menu(self.selector,self.intent,self.child,self.runtime.origin).logout()
            return self.terminal('logout',ticket)

    def restore_preferences(self,ticket):
        with self.lock.held(),self.runtime.existing_input_session(self.selector):
            self.begin('restore',ticket,'logged-out','restore-issued')
            actual=self.runtime._restore_account_preferences(self.selector,self.state['preferences'],self.intent)
            need(same(actual,self.state['preferences']['preferences']))
            source=self.runtime._sources(self.selector)
            self.sample()
            self.state['restoration']=dict(binding=deepcopy(source['binding']),receipt=deepcopy(source['preferenceReceipt']),preferences=deepcopy(source['preferences']))
            self.state['actions'][-1].update(complete=True,after=len(self.state['samples'])-1)
            self.state['phase']='restored';self.save();return deepcopy(actual)

    def protected(self,ticket):
        """A real protected native GET; retained native leases drain separately."""
        identifier(ticket)
        with self.lock.held(),self.runtime.existing_input_session(self.selector):
            self.load();need(self.state['phase']=='logged-in' and len(self.state['protected'])<16)
            self.require_authority(ticket)
            if self.state['protected'] and self.state['protected'][-1]['phase']!='complete':
                raise AvatarLoginPending('Original protected Avatar request remains owned')
            row=dict(ticket=ticket,phase='reading',probe=None,accountIndex=None,owners=None,released=None,originAbsent=None)
            self.state['protected'].append(row);self.save()
            origin=self.runtime._account_origin(self.selector);probe=self.runtime._account_probe(self.selector)
            origin.stage(self.child,self.runtime.origin)
            original=probe.acquire(self.child,ticket);_reader,account=self.sample()
            measured=bind_to_account(original,account['account'])
            need(measured['protectedAccess'] and measured['loggedIn'] and measured['principalSha256']==self.principal)
            owners=dict(origin=origin.owned(),probe=probe.owner.owned())
            row.update(probe=deepcopy(original),accountIndex=len(self.state['samples'])-1,owners=owners);self.save()
            row['released']=probe.release();self.save()
            origin.release();row['originAbsent']=origin.source.request(owners['origin']['data'],'observe');self.save()
            need(not self.runtime.account_origin_store(self.selector).read() and not self.runtime.account_probe_store(self.selector,role=self.role).read())
            row['phase']='complete';self.save();return deepcopy(row)
