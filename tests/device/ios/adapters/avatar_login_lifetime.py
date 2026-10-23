"""Whole-only Login operand holds from unchanged original owners and packets.

These proofs retain actual resources. They do not establish weak death from a
successful login, hidden controls, ordinary cancel or a process-end request.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import hashlib
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.avatar_login_owner import IOSAvatarLoginOwner
from ios.adapters import login_root_ownership
from ios.adapters.normal_input import observation as widgets

VERSION=1


class AvatarLoginLifetime:
    def __init__(self,original,*,binding,run,child_run,role,authority):
        from ios.adapters.avatar_authority import AvatarAuthorityReader
        from ios.adapters.authentication_origin import origin as endpoint
        need(isinstance(authority,AvatarAuthorityReader) and authority.run==run)
        origin=endpoint(authority.client.url)
        need(role in ('primary','actor'));self.binding=deepcopy(context(binding));self.run=identifier(run)
        self.child,self.role,self.origin=identifier(child_run),role,origin
        owner=object.__new__(IOSAvatarLoginOwner);owner.run,owner.child,owner.role=self.run,self.child,role
        owner.authority=authority;owner.runtime=SimpleNamespace(origin=origin);owner.principal=hashlib.sha256(('e2e-'+self.child).encode()).hexdigest()
        owner.endpoints={hashlib.sha256(endpoint.encode()).hexdigest() for endpoint in (origin,origin+'/')}
        state=owner.decode(original);need(same(state['binding'],self.binding));self.original=deepcopy(original)
        self.ui=[];initial=state['preferences']['receipt']['observation']
        self.add(initial,initial['sampleEpochMs'])
        self.initial=deepcopy(self.ui[0]);need(self.initial['complete'] and not any(row['weakAlive'] for row in self.initial['ownership']['roots']))
        for action in state['actions']:
            for intent in action['intents']:
                source=intent['original'];barrier=state['samples'][intent['barrier']]['capturedEpochMs']
                if source.get('originalKind')=='ios-normal-login-ui-v1':
                    self.add(source['originalReceipt']['observation'],barrier)
                elif set(source)=={'native','receipt'}:
                    self.add(source['receipt']['observation'],source['native']['capturedEpochMs'])
        self.ui.sort(key=lambda row:row['ownership']['sequence']);unique=[]
        for row in self.ui:
            if unique and row['ownership']['sequence']==unique[-1]['ownership']['sequence']:need(same(row,unique[-1]))
            else:
                if unique:login_root_ownership.validate(row,pid=int(self.binding['processIdentity']),previous=unique[-1])
                unique.append(row)
        self.ui=unique

    def add(self,original,epoch):
        pid=int(self.binding['processIdentity']);widgets(original,pid,epoch)
        self.ui.append(deepcopy(login_root_ownership.membership(original,pid=pid,epoch=epoch)))

    def _at_widgets(self,original,*,original_sha256):
        pid=int(self.binding['processIdentity']);widgets(original,pid,original['sampleEpochMs'])
        current=login_root_ownership.membership(original,pid=pid,epoch=original['sampleEpochMs']);need(current['complete'])
        source=current['ownership'];initial=self.initial['ownership'];need(source['available'] and source['complete'] and source['wholeTreeReady']
            and source['instance']==initial['instance'] and source['sequence']>=initial['sequence'])
        before=[];admitted={};baseline={row['observedIdentity'] for row in initial['roots']}
        for value in self.ui:
            prior=value['ownership']
            if prior['sequence']>source['sequence']:
                need(prior['capturedEpochMs']>=source['capturedEpochMs']);continue
            need(prior['capturedEpochMs']<=source['capturedEpochMs'])
            if before:login_root_ownership.validate(value,pid=pid,previous=before[-1])
            before.append(value)
            for control in value['controls']:
                identity=control['observedIdentity']
                if identity in baseline:continue
                row=next(row for row in prior['roots'] if row['observedIdentity']==identity)
                if identity in admitted:need(all(same(row[k],admitted[identity][k]) for k in row if k not in
                    ('weakAlive','weakExpiredObservedEpochMs','weakExpiredObservedMonotonicMs')))
                else:admitted[identity]=deepcopy(row)
        need(before)
        if source['sequence']==before[-1]['ownership']['sequence']:need(same(current,before[-1]))
        else:login_root_ownership.validate(current,pid=pid,previous=before[-1])
        held=[];ends=[];known={row['observedIdentity'] for row in source['roots']};need(set(admitted)<=known)
        # An unadmitted new operand is still unresolved responsibility. It may
        # only leave this stronger consumer after separately proven OS end.
        need(known<=baseline|set(admitted))
        for identity,admission in sorted(admitted.items()):
            row=login_root_ownership.follow(admission,current,pid=pid,epoch=original['sampleEpochMs'])
            resource='panel:avatar-login-'+self.role+'-'+identity
            endpoint=dict(observedIdentity=identity,original=deepcopy(row),originalSha256=digest(row))
            if row['weakAlive']:held.append(dict(resource=resource,kind='qt-root',originalSha256=digest(endpoint)))
            ends.append(endpoint)
        return dict(iosAvatarLoginLifetimeVersion=VERSION,runId=self.run,role=self.role,binding=deepcopy(self.binding),
            loginOriginalSha256=digest(self.original),sourceOriginalSha256=original_sha256,ownership=deepcopy(current),
            admissions=deepcopy(admitted),endpoints=ends,heldResources=held)

    def source(self,owner,reference):
        from ios.adapters.avatar_sources import IOSAvatarSources
        from ios.adapters.avatar_facts import retained
        need(isinstance(owner,IOSAvatarSources) and owner.run==self.run and same(owner.binding,self.binding))
        owner.lock.assert_held();frame=retained(owner,reference);owner.validate_frame(frame)
        return self._at_widgets(frame['originals']['widgets'],original_sha256=digest(frame))

    def tail(self,owner,reference):
        from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
        need(isinstance(owner,IOSAvatarPostLogoutTail) and owner.run==self.run and owner.subject==self.role and same(owner.binding,self.binding))
        owner.lock.assert_held();state=owner.parse(owner.previous)
        need(any(row['status']=='observed' and same(row['reference'],reference) for row in state['rows']))
        record=owner.validate(owner.record(reference))
        # The existing typed owner validates original native brackets and all
        # unchanged widgets bytes. This wrapper adds no acquisition or retime.
        return self._at_widgets(record['widgetsReceipt']['observation'],original_sha256=digest(record))
