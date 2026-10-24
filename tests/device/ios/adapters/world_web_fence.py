"""Original inactive-fixture foreground fence immediately before one normal Stop.

This never changes held counters and grants no post-exit resource fact. It reads
actual native/Qt/cache originals only while the originally admitted app lives.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.world_web_retired import native_retired,activity
from ios.adapters.emote_native_prefix import follow


def phase(value,flow):
    phase_packet(value,run=flow.run,area='world-web',request=value['requestId'],epoch=value['capturedEpochMs'])
    need(value['active'] is False and value['instance']==flow.state['phaseInstance'] and value['activations']
        and value['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
    return value


def original(owner):
    owner.decode(owner.previous)
    from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
    if type(owner) is WorldWebSetupRetirement:key='iosWorldWebSetupRetirementOriginalVersion'
    else:key='iosWorldWebRetirementOriginalVersion' if owner.role=='primary' else 'iosWorldWebActorRetirementOriginalVersion'
    return {key:1,'owner':deepcopy(owner.previous)}


def acquire(flow,parts):
    before=phase(flow.phase.status(),flow);owner=parts['retirement'];need(owner is not None and owner.state['phase']=='retired')
    retained=original(owner);measured=owner.validate_original(retained)
    need(measured['ticket']==before['activations'][-1]['ticket'] and measured['acquisition']['hostAfterEpochMs']<=before['retiredEpochMs'])
    files=None
    if flow.role=='primary':files=deepcopy(owner.frame(owner.state['quiet'][-1])['files'])
    primary=parts['source'].capture('final-fence',retired=True)
    own=None if flow.role=='primary' else parts['peer'].capture('final-fence',retired=True)
    after=phase(flow.phase.status(),flow)
    value=dict(iosWorldWebFinalFenceVersion=1,runId=flow.run,role=flow.role,binding=deepcopy(flow.state['binding']),
        phaseBefore=before,phaseAfter=after,primary=primary,own=own,files=files,sceneSha256=digest(retained))
    validate(value,flow,parts);return value


def validate(value,flow,parts):
    exact(value,{'iosWorldWebFinalFenceVersion','runId','role','binding','phaseBefore','phaseAfter','primary','own','files','sceneSha256'})
    need(type(value['iosWorldWebFinalFenceVersion']) is int and value['iosWorldWebFinalFenceVersion']==1 and value['runId']==flow.run
        and value['role']==flow.role and same(value['binding'],flow.state['binding']))
    a,b=phase(value['phaseBefore'],flow),phase(value['phaseAfter'],flow)
    phase_packet(b,run=flow.run,area='world-web',request=b['requestId'],epoch=b['capturedEpochMs'],previous=a)
    primary=parts['source'].frame(value['primary']);owner=parts['retirement']
    need(digest(original(owner))==value['sceneSha256'])
    if flow.role=='primary':
        need(value['own'] is None)
        from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
        if type(owner) is WorldWebSetupRetirement:
            from ios.adapters.world_web_setup_measurements import original as setup_original
            proof=setup_original(owner.scope,owner.source,owner.baseline,value['primary'])
            ownership=owner.scope.state['fileOwnership']
            if ownership is None:need(value['files'] is None)
            else:
                receipt=owner.files.original(value['files'])
                need(receipt['kind']=='absent' and same(receipt['ownership'],ownership)
                    and receipt['clockJoin']['nativeAfter']['capturedEpochMs']<=primary['clockJoin']['nativeBefore']['capturedEpochMs'])
        else:
            need(value['files'] is not None)
            proof=native_retired(owner.lease,owner.state['baseline'],value['primary'],owner.files.original(value['files']))
        previous=parts['source'].frame(owner.frame(owner.state['quiet'][-1])['after']);current=primary
    else:
        need(value['own'] is not None and value['files'] is None);current=parts['peer'].frame(value['own'])
        owner.native_frames(primary,current)
        previous_entry=owner.entry(owner.state['quiet'][-1]);previous=parts['peer'].frame(previous_entry['peer'])
        proof=None
    need(current['phaseBefore']['active'] is False and current['phaseAfter']['active'] is False and primary['phaseBefore']['active'] is False
        and primary['phaseAfter']['active'] is False and current['ticket']==a['activations'][-1]['ticket']==primary['ticket']
        and a['capturedEpochMs']<=primary['clockJoin']['hostBeforeEpochMs']<=current['clockJoin']['hostAfterEpochMs']<=b['capturedEpochMs'])
    follow(previous['clockJoin']['nativeAfter'],current['clockJoin']['nativeBefore']);need(same(activity(previous),activity(current)))
    return dict(native=deepcopy(current['clockJoin']['nativeAfter']),acquisition=deepcopy(current['clockJoin']),
        acquisitions=[deepcopy(primary['clockJoin'])]+([] if flow.role=='primary' else [deepcopy(current['clockJoin'])]),proof=proof)


def current(value,flow,parts):
    native=(parts['source'] if flow.role=='primary' else parts['peer']).frame(value['primary'] if flow.role=='primary' else value['own'])['clockJoin']
    return current_clocks(native,flow)


def current_clocks(native,flow):
    """Original qualified acquisition only; no new query or retiming."""
    epoch,mono=flow.epoch_ms(),flow.monotonic()
    need(number(epoch,native['hostAfterEpochMs'],native['hostBeforeEpochMs']+1500) and epoch-native['hostBeforeEpochMs']<1500
        and number(mono,native['hostAfterMonotonic'],native['hostBeforeMonotonic']+1.5) and mono-native['hostBeforeMonotonic']<1.5
        and abs(epoch-native['hostBeforeEpochMs']-(mono-native['hostBeforeMonotonic'])*1000)<=250)
    return True
