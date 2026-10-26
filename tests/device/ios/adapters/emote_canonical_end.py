"""Canonical post-end verification without recreating either deleted SDK.

Only a physically present complete typed end journal permits replay. A public
ACK/result or an incomplete end cannot authorize another Stop or SDK DELETE.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,unpack
from feature_journeys import terminal
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_terminal import IOSEmoteTerminal


def completed(flow,seal,*,actor=None):
    need(type(flow) is IOSEmoteRootedFeature and flow.role=='primary')
    terminal.sealed(seal);need(seal['description']['runId']==flow.run and seal['description']['area']=='emotes')
    store=PrivateFeatureState(flow.store.path.with_name('ios-emote-primary-'+flow.run+'-rooted-end.json'))
    value=store.read();exact(value,{'iosEmoteRootedEndArchiveVersion','runId','archiveSha256','seal','payload'})
    need(type(value['iosEmoteRootedEndArchiveVersion']) is int and value['iosEmoteRootedEndArchiveVersion']==1
        and value['runId']==flow.run and same(value['seal'],seal))
    rows=unpack(value['payload']);need(len(rows)==1 and type(rows[0]) is dict
        and rows[0].get('phase')=='complete' and rows[0].get('pending') is None)
    # This preliminary check authorizes only a pure replay. The actual paired
    # controller below reopens every native, file, pixel, OS and SDK original,
    # its exact end-index/CAS authority and the retained inactive phase.
    controller=IOSEmoteTerminal(flow,actor)
    actual=controller.invoke(dict(contractVersion=1,runId=flow.run,stage='finish',seal=seal))
    for owned in (controller.flow,controller.actor):
        need(owned.state is not None)
        scope={key:item for key,item in owned.state['binding'].items() if key!='processIdentity'}
        owned.runtime.adapter._retired_candidate_scope(owned.selector,scope)
    return actual


def verify(flow,call,result):
    call=terminal.arguments('emotes',call);need(call['stage']=='finish' and call['runId']==flow.run)
    exact(result,{'stage','end'});need(result['stage']=='finish');terminal.ended(result['end'],call['seal'])
    actual=completed(flow,call['seal']);need(same(actual,result));return actual
