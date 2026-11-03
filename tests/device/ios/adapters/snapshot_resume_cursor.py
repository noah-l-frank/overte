"""Join actual resumed UI cursor to the complete original normal-input prefix.

This does not acquire evidence, repeat an input, establish its product effect,
prove an OS interruption or authorize a fresh feature observation. Its caller
must reopen the actual Page3 and native packet owners before using this join.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.normal_input import observation
from ios.adapters.snapshot_owned_packet import qualified
from ios.adapters import snapshot_inputs,snapshot_combined_work


def cursor(page,packet,binding,run):
    context(binding);identifier(run);need(binding['processIdentity'].isdecimal() and int(binding['processIdentity'])>0)
    pid=int(binding['processIdentity'])
    need(type(page['iosSnapshotPageObservationVersion']) is int and page['iosSnapshotPageObservationVersion']==3)
    for current,previous in ((page['phaseBefore'],None),(page['phaseAfter'],page['phaseBefore'])):
        phase_packet(current,run=run,area='snapshots',request=current['requestId'],epoch=current['capturedEpochMs'],previous=previous)
        need(current['active'] and current['activations'] and current['activations'][-1]['stimulus']==dict(verb='background-resume',inputs={}))
    need(same(page['phaseBefore']['activations'],page['phaseAfter']['activations']))
    page_join=validate_join(page['clockJoin'],page['originals']);ui=observation(page['originals']['ui'],pid,page_join['nativeAfter']['capturedEpochMs'])
    work=snapshot_combined_work.original(page['originals']['work']);need(work['processId']==pid and work['runId']==run)
    span=qualified(packet,pid,'inputs');native=packet['packet'];snapshot_inputs.original(native)
    need(native['runId']==run and native['source']['complete'])
    follow_native(page_join['nativeAfter'],span['nativeBefore'])
    need(same(page_join['nativeAfter']['lifecycle'],span['nativeBefore']['lifecycle'])
        and same(span['nativeBefore']['lifecycle'],span['nativeAfter']['lifecycle'])
        and span['hostBeforeEpochMs']>=page_join['hostAfterEpochMs']
        and span['hostBeforeMonotonic']>=page_join['hostAfterMonotonic']
        and ui['sampleEpochMs']<=span['nativeBefore']['capturedEpochMs']
        and span['nativeAfter']['capturedEpochMs']-ui['sampleEpochMs']<1500)
    received=[row for row in native['source']['events'] if row['kind']=='received']
    returned={row['inputId']:row for row in native['source']['events'] if row['kind']=='returned'}
    need(received and len(received)==len(returned) and {row['inputId'] for row in received}==set(returned))
    commands=[row['details']['command'] for row in received]
    need(len({row['commandId'] for row in commands})==len(commands)
        and len({row['details']['outerCommandId'] for row in received})==len(received)
        and all(row['instance']==ui['instance'] for row in commands)
        and all(row['observedElapsedMs']<=ui['elapsedMs'] for row in commands)
        and all(a['sequence']<b['sequence'] for a,b in zip(commands,commands[1:])))
    for row in received:
        status=returned[row['inputId']]['details']['status']
        need(status['performed'] is True and status['sampleEpochMs']<=ui['sampleEpochMs']
            and returned[row['inputId']]['clock']['epochMs']<=ui['sampleEpochMs'])
    latest=received[-1];command=commands[-1]
    controls=[row for row in ui['controls'] if row['id']=='snapshot.capture'];need(len(controls)==1)
    need(command['sequence']==ui['lastSequence']
        and latest['details']['root']==dict(rootId=controls[0]['snapshotRootId'],qmlSource=controls[0]['snapshotQmlSource']))
    return dict(iosSnapshotResumeInputCursorVersion=1,runId=run,processId=pid,inputInstance=ui['instance'],
        sequence=ui['lastSequence'],lastCommandId=command['commandId'],rootId=controls[0]['snapshotRootId'],
        pageOriginalSha256=digest(page),inputOriginalSha256=digest(packet),normalInputOutcomeRequired=True,
        originalPageAndPacketOwnersRequired=True,originalOSBridgeRequired=True,
        renderedResumeRequired=True,independentActorSceneRequired=True,wholeFeatureRequired=True)
