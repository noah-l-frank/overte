"""Original live Tablet disposal projection, preserving exact native holds.

A private cleanup frame alone supplies no feature fact. This decoder additionally
requires actual quiet VM/dialog/file/input/native closure originals, then derives
historical page facts from the same selected source frame. It cannot stop a
process or replace retained native objects with zero counters.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from feature_journeys.contract import result
from feature_journeys.terminal import held
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import quiet,inspect
from adapters.normal_ui import NativeUIError

VERSION=1


def candidates(runtime,before_reference,stop_reference,references):
    """Retain every attempted original; select only real settled suffixes.

    A valid but not-yet-quiescent native frame is never promoted to cleanup.
    Source/byte/history decoding errors propagate before this readiness test.
    No history, native counter, original timestamp or operation deadline resets.
    """
    tail=TabletWebTail(runtime,historical=True);before,stop=tail.read(before_reference),tail.read(stop_reference)
    source=tail.source();chain=[];previous=None;result=[]
    for reference in references:
        current=tail.read(reference);apps=source.app_sources(current['source']['apps'])
        try:proof=inspect(before,stop,current,apps)
        except NativeUIError:chain=[];previous=None;continue
        if previous is None or not same(previous,proof):chain=[]
        chain.append((reference,current));previous=proof
        if len(chain)<3:continue
        selected=[chain[0],*chain[-2:]]
        try:quiet(before,stop,[item[1] for item in selected],apps)
        except NativeUIError:continue
        result.append(dict(tabletWebCleanupObservationVersion=1,before=deepcopy(before_reference),stop=deepcopy(stop_reference),
            quiet=[deepcopy(item[0]) for item in selected]))
    # No previously settled window can qualify the latest still-active frame.
    if references and (not chain or chain[-1][0]!=references[-1]):return []
    return result


def validate(runtime,original):
    exact(original,{'tabletWebCleanupObservationVersion','before','stop','quiet'})
    need(type(original['tabletWebCleanupObservationVersion']) is int and original['tabletWebCleanupObservationVersion']==VERSION
        and type(original['quiet']) is list and 3<=len(original['quiet'])<=128)
    tail=TabletWebTail(runtime,historical=True)
    before,stop=tail.read(original['before']),tail.read(original['stop'])
    frames=[tail.read(ref) for ref in original['quiet']]
    need(tail.originals.expand(original['before'])['index']<=tail.originals.expand(original['stop'])['index']
        and tail.originals.expand(original['stop'])['index']<tail.originals.expand(original['quiet'][0])['index']
        and all(tail.originals.expand(b)['index']>tail.originals.expand(a)['index'] for a,b in zip(original['quiet'],original['quiet'][1:])))
    source=tail.source();selected=frames[-1];reference=selected['row']['source']['observation']['reference']
    facts,row,_frame=source.facts_at(reference,runtime.observer.origins)
    proof=quiet(before,stop,frames,source.app_sources(row['apps']))
    resources=held(proof['proof']['heldResources']);phase=row['phaseAfter']
    public=dict(schemaVersion=1,contractVersion=16,runId=source.run,sequence=row['index'],
        capturedEpochMs=selected['row']['before']['epochMs'],state=facts['public'],artifacts=[],resources=resources,
        lifecycle=deepcopy(row['nativeAfter']['lifecycle']))
    result('feature.tablet-web.observe',public)
    clock=selected['row'];acquisition=dict(hostBeforeEpochMs=clock['before']['epochMs'],hostAfterEpochMs=clock['after']['epochMs'],
        hostBeforeMonotonic=clock['before']['monotonic'],hostAfterMonotonic=clock['after']['monotonic'])
    return dict(ticket=phase['activations'][-1]['ticket'],public=public,acquisition=acquisition)
