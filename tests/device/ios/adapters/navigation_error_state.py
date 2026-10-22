"""Original missing-place ownership and current modal/OK lifetime projection.

The original missing ticket stays historical after dismissal. No old callback
is retimed or relabelled as a response to the current input phase.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,need
from adapters.native_navigation_replies import validate as reply_packet
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters import navigation_dialogs as dialogs,navigation_dialog_controls as controls,navigation_ui
from ios.adapters.navigation_places_state import pid

VERSION=1
PROOF_VERSION=1
ORIGINALS=frozenset(('dialogs','replies','ui'))
ADMISSION=frozenset(('runId','ticket','inputs','origin','nativeAfterEpochMs','providerAfterEpochMs','afterEvent'))


def validate_originals(run,binding,originals,clock_join):
    identifier(run);process=pid(binding);exact(originals,ORIGINALS)
    clock=validate_join(clock_join,originals);first,last=clock['nativeBefore'],clock['nativeAfter']
    need(first['processId']==last['processId']==process and same(first['lifecycle'],last['lifecycle']))
    packet=originals['dialogs'];dialogs.validate(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),
        action=dialogs.ACTION,runId=run),process,last['capturedEpochMs'])
    need(packet['complete'] is True and packet['foreignModals']==0
         and first['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=last['capturedEpochMs'])
    replies=originals['replies'];reply_packet(replies,dict(schemaVersion=1,commandId=replies.get('commandId'),
        action='feature-navigation-replies',runId=run),process,last['capturedEpochMs'])
    ui=originals['ui'];need(ui['processId']==process);address=navigation_ui.project(ui)
    need(first['capturedEpochMs']<=replies['capturedEpochMs']<=last['capturedEpochMs']
         and first['capturedEpochMs']<=ui['sampleEpochMs']<=last['capturedEpochMs'])
    return clock,address


def missing_proof(binding,originals,clock_join,provider,admission):
    """Freeze a genuine same-ticket native error/modal/input-control join."""
    exact(admission,ADMISSION);run=identifier(admission['runId']);identifier(admission['ticket'])
    validate_originals(run,binding,originals,clock_join)
    need(admission['inputs']['sourceRevision']==binding['sourceRevision'])
    found=dialogs.owned_missing(originals['dialogs'],originals['replies'],provider_status=provider,
        provider_instance=provider['instance'],inputs=admission['inputs'],owned_origin=admission['origin'],run=run,
        ticket=admission['ticket'],native_after_epoch=admission['nativeAfterEpochMs'],
        provider_after_epoch=admission['providerAfterEpochMs'],after_event=admission['afterEvent'])
    controls.join_observation(controls.project(originals['ui']),originals['dialogs'],found['dialogId'])
    need(set(dialogs.history(originals['dialogs']))=={found['dialogId']}
         and same(originals['replies']['events'],[found['nativeError']]))
    return dict(iosNavigationMissingProofVersion=PROOF_VERSION,binding=deepcopy(binding),admission=deepcopy(admission),
        originals=deepcopy(originals),clockJoin=deepcopy(clock_join),originalsSha256=digest(originals),
        provider=deepcopy(provider),joined=found)


def validate_proof(value,binding,run):
    exact(value,{'iosNavigationMissingProofVersion','binding','admission','originals','clockJoin','originalsSha256','provider','joined'})
    need(type(value['iosNavigationMissingProofVersion']) is int and value['iosNavigationMissingProofVersion']==PROOF_VERSION
         and same(value['binding'],binding) and value['admission']['runId']==run
         and value['originalsSha256']==digest(value['originals']))
    expected=missing_proof(binding,value['originals'],value['clockJoin'],value['provider'],value['admission'])
    need(same(expected,value));return expected['joined']


def continuation(originals,previous,run,process,epoch):
    current,old=originals['dialogs'],previous['dialogs']
    if current['sequence']==old['sequence']:need(same(current,old))
    else:dialogs.validate(current,dict(schemaVersion=1,commandId=current['requestId'],action=dialogs.ACTION,runId=run),
                          process,epoch,old)
    current,old=originals['replies'],previous['replies']
    need(current['instance']==old['instance'] and current['sequence']>=old['sequence']
         and current['capturedEpochMs']>=old['capturedEpochMs']
         and current['currentLookupGeneration']>=old['currentLookupGeneration']
         and len(current['events'])>=len(old['events']) and same(current['events'][:len(old['events'])],old['events']))
    if current['sequence']==old['sequence']:need(same(current,old))
    else:need(current['commandId']!=old['commandId'])
    current,old=originals['ui'],previous['ui']
    need(current['instance']==old['instance'] and current['lastSequence']>=old['lastSequence']
         and current['elapsedMs']>=old['elapsedMs'] and current['sampleEpochMs']>=old['sampleEpochMs'])
    need(current['navigationDialogSourceSequence']>=old['navigationDialogSourceSequence'])
    if current['navigationDialogSourceSequence']==old['navigationDialogSourceSequence']:need(same(current,old))


def compose(run,binding,originals,clock_join,*,missing=None):
    """Current error and Go To fields, not arrival or whole-resource quiet."""
    clock,address=validate_originals(run,binding,originals,clock_join)
    actual=originals['dialogs'];replies=originals['replies'];ui=originals['ui'];current=controls.project(ui)
    states=dialogs.history(actual);state='none';drained=None
    if missing is None:
        # An unknown callback/modal cannot be silently adopted or reported as
        # cleared. The owner must retain a genuine pre-OK missing proof first.
        need(not states and not replies['events'] and not current['controls'])
    else:
        owned=validate_proof(missing,binding,run);id=owned['dialogId']
        continuation(originals,missing['originals'],run,pid(binding),clock['nativeAfter']['capturedEpochMs'])
        need(same(replies['events'],missing['originals']['replies']['events']))
        need(set(states)=={id});lifetime=states[id]
        need(same(lifetime['created'],owned['created']))
        entry=next(row for row in actual['dialogs'] if row['dialogId']==id);root=entry['dialog']
        if root is not None and root['visible'] and lifetime['response'] is None:
            event=owned['nativeError']
            need(replies['currentLookupActive'] and replies['currentLookupGeneration']==event['lookupGeneration']
                 and any(same(row,event) for row in replies['events']))
            controls.join_observation(current,actual,id);state='not-found';drained=False
        else:
            # Hiding/scheduling deletion and an OK input ACK are insufficient.
            need(dialogs.drained(actual,[id],require_ok=True) and not current['controls'])
            drained=True
    return dict(iosNavigationErrorStateVersion=VERSION,runId=run,binding=deepcopy(binding),
        fields=dict(error=state,addressDialog=address['addressDialog']),ownedDialogDrained=drained,
        originalsSha256=digest(originals),missingProofSha256=None if missing is None else digest(missing),
        nativeBeforeEpochMs=clock['nativeBefore']['capturedEpochMs'],nativeAfterEpochMs=clock['nativeAfter']['capturedEpochMs'],
        acquiredHostEpochMs=clock['hostBeforeEpochMs'])
