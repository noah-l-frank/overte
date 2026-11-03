"""Explicit old-origin authority transfer to one genuine G1 cleanup owner.

Historical G0 packets remain historical. A fresh old-PID absence, current G1
native/Settings/account/Session bracket and durable parent phase authorize only
normal restoration of that exact old original QString selection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,fresh,need,number,validate as native_packet
from adapters.native_navigation_environment import logged_out,validate as environment_packet
from adapters.native_process_presence import validate as presence_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation_originals import read_original
from adapters.script_journey.history import pack,unpack,same

VERSION=1


class NavigationOriginRestart:
    def __init__(self,parent):
        from adapters.pico4.navigation_generation_restoration import NavigationGenerationRestoration
        need(isinstance(parent,NavigationGenerationRestoration))
        self.parent=parent;self.flow=parent.flow;self.store=PrivateFeatureState(parent.lock.path.with_name('navigation-prefix-generation-1-origin-restart.json'))

    def old_origin(self):
        p=self.parent;p.host();old=self.flow.parent.origin
        need(old.state is not None and old.state['navigationOriginVersion']==2
            and same(old.binding,self.flow.restart.binding) and old.state['homeMode']=='ray'
            and old.state['operation']['stage']==4 and old.state['operation']['quiet']
            and old.state['operation']['restoring'] is False)
        raw=old.store.read();need(same(raw,old.disk_state));original=old.state['original'];old.archive(original)
        need(original['navigationEnvironmentVersion']==2 and original['selectedSettingPresent']
            and original['settings']['selectedType']=='string')
        need(same(old.original_packet(raw['original']),original)
            and original['otherSettingsSha256']==old.state['last']['otherSettingsSha256'])
        return old,raw,original

    def originals(self):
        old,raw,_original=self.old_origin()
        return [read_original(old.store.path),read_original(old.packet_store(raw['original']['sha256']).path)]

    def create(self):
        p=self.parent;p.guard();need(self.store.read() is None)
        old,raw,original=self.old_origin();pins=self.originals();runtime=p.runtime
        started=p.now();requested=runtime['native'].clock_ms();phase=p.guard()
        packet=runtime['native'].read(0)
        exited=runtime['presence'].require_absent(int(old.binding['processIdentity'].split(':',1)[0]))
        environment=runtime['environment'].read(p.run);logged_out(environment)
        with runtime['session']._lock():session=deepcopy(runtime['session']._load())
        value=dict(scope=p.scope(),oldBinding=deepcopy(old.binding),newBinding=deepcopy(p.binding),oldOrigin=deepcopy(raw),
            oldOriginal=deepcopy(original),originals=pins,phase=deepcopy(phase),native=packet,exit=exited,
            environment=environment,session=session,startedMonotonic=started,requestedEpochMs=requested)
        self.validate_value(value)
        body=dict(navigationOriginRestartVersion=VERSION,payload=pack([value]));self.store.write(body,None)
        reference=dict(navigationOriginRestartReferenceVersion=VERSION,original=read_original(self.store.path))
        # The transfer's actual sources are still aged after its durable CAS.
        self.read(reference);p.guard();epoch=runtime['native'].clock_ms();now=p.now()
        need(now>=started and epoch>=requested)
        effective=max(epoch,requested+(now-started)*1000)
        for stamp in (packet['capturedEpochMs'],exited['capturedEpochMs'],environment['capturedEpochMs'],phase['status']['capturedEpochMs']):
            fresh(stamp,int(effective))
        return reference

    def validate_value(self,value):
        p=self.parent;old,raw,original=self.old_origin()
        exact(value,{'scope','oldBinding','newBinding','oldOrigin','oldOriginal','originals','phase','native','exit',
            'environment','session','startedMonotonic','requestedEpochMs'})
        need(number(value['startedMonotonic'],0,1e15) and number(value['requestedEpochMs'],1,1e15))
        need(same(value['scope'],p.scope()) and same(value['oldBinding'],old.binding) and same(value['newBinding'],p.binding)
            and same(value['oldOrigin'],raw) and same(value['oldOriginal'],original) and same(value['originals'],self.originals()))
        phase=value['phase'];need(phase['verb']=='cleanup' and phase['inputs']=={} and phase['ticket']==p.state['ticket']
            and same(phase['status']['activations'],p.state['fixture']['activations']))
        pid=int(p.binding['processIdentity'].split(':',1)[0]);native=value['native'];epoch=value['environment']['capturedEpochMs']
        native_packet(native,native['requestId'],pid,epoch)
        plan=self.flow.restart.inputs.read();new=plan['newNative']
        need(plan['phase']=='observed' and same(plan['oldBinding'],old.binding) and same(plan['newBinding'],p.binding)
            and native['instance']==new['instance'] and native['lifecycle']==new['lifecycle'] and native['processId']==new['pid'])
        exited=value['exit'];presence_packet(exited,dict(schemaVersion=1,commandId=exited['commandId'],
            action='feature-process-presence',queryProcessId=int(old.binding['processIdentity'].split(':',1)[0])),pid,epoch)
        need(exited['presence']=='absent')
        environment=value['environment'];environment_packet(environment,dict(schemaVersion=1,commandId=environment['commandId'],
            action='feature-navigation-environment',runId=p.run),pid,epoch);logged_out(environment)
        need(environment['navigationEnvironmentVersion']==2 and environment['selectedSettingPresent']
            and environment['settings']['selectedType']=='string' and environment['selectedServer']==environment['effectiveServer']==old.state['ownedServer']
            and environment['otherSettingsSha256']==original['otherSettingsSha256']
            and environment['settings']['rawSettingsSha256']==old.state['last']['settings']['rawSettingsSha256'])
        before=self.flow.state['frames'][-1]['after']['environment']['account']['observation']
        observed=environment['account']['observation']
        last=self.flow.state['frames'][-1]['after']['environment']
        need(environment['instance']==last['instance'] and environment['sequence']>last['sequence']
            and environment['settings']['instance']==last['settings']['instance'])
        need(all(observed[key]==before[key] for key in ('instance','credentialGeneration','eventSequence','endpointSha256'))
            and not environment['ui']['loginPageAlive'] and not environment['ui']['open'] and not environment['ui']['ready'])
        session=value['session'];exact(session,{'schemaVersion','processIdentity','sessionNonce','nextSequence'})
        need(type(session['schemaVersion']) is int and session['schemaVersion']==1 and session['processIdentity']==p.binding['processIdentity']
            and session['sessionNonce']==self.flow.restart.state['newSession']['sessionNonce']
            and session['nextSequence']==self.flow.restart.state['newSession']['nextSequence']+len(self.flow.state['controllers']))

    def read(self,reference):
        p=self.parent;p.host();exact(reference,{'navigationOriginRestartReferenceVersion','original'})
        need(type(reference['navigationOriginRestartReferenceVersion']) is int and reference['navigationOriginRestartReferenceVersion']==VERSION
            and reference['original']['path']==str(self.store.path) and same(read_original(self.store.path),reference['original']))
        body=self.store.read();exact(body,{'navigationOriginRestartVersion','payload'})
        need(type(body['navigationOriginRestartVersion']) is int and body['navigationOriginRestartVersion']==VERSION)
        rows=unpack(body['payload']);need(len(rows)==1);self.validate_value(rows[0]);return rows[0]

    def validate(self,reference,origin):
        value=self.read(reference);p=self.parent
        need(origin.restoration_authority is self and origin.store.path==p.origin_path and origin.run==p.run
            and same(origin.binding,p.binding) and origin.native is p.runtime['environment'])
        return value

    def target(self,reference):return self.read(reference)['oldOriginal']['selectedServer']

    def baseline(self,reference,packet,origin):
        value=self.validate(reference,origin);previous=value['environment'];logged_out(packet)
        need(packet['navigationEnvironmentVersion']==2 and packet['instance']==previous['instance']
            and packet['processId']==previous['processId'] and packet['sequence']>previous['sequence']
            and packet['settings']['instance']==previous['settings']['instance']
            and packet['settings']['selectedType']==previous['settings']['selectedType']=='string'
            and packet['settings']['rawSettingsSha256']==previous['settings']['rawSettingsSha256']
            and packet['otherSettingsSha256']==value['oldOriginal']['otherSettingsSha256']
            and packet['selectedServer']==packet['effectiveServer']==previous['selectedServer']
            and packet['ui']['loginPageAlive'] and packet['ui']['bridgeId']==origin.binding['sessionId']
            and packet['ui']['sequence']==self.parent.state['entry']['scope']['sequence']+1
            and all(packet['account']['observation'][key]==previous['account']['observation'][key]
                for key in ('instance','credentialGeneration','eventSequence','endpointSha256')))
