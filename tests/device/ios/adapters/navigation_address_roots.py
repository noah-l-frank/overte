"""Original ordinary Go To root ownership, distinct from visible controls.

The caller must durably record the actual ordinary HUD opening intent before
delivery and retain the fresh opened original. This module sends no command,
destroys no product object and cannot turn hidden retained roots into absence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.navigation_ui import project
from ios.adapters.normal_input import observation

VERSION=1


def packet(binding,value):
    context(binding);observation(value,int(binding['processIdentity']),value.get('sampleEpochMs'))
    return project(value)


def follow(before,after):
    for value in (before,after):
        need(type(value.get('navigationDialogControlsVersion')) is int and value['navigationDialogControlsVersion']==1
             and type(value.get('navigationDialogSourceSequence')) is int and value['navigationDialogSourceSequence']>0)
    need(before['instance']==after['instance'] and before['processId']==after['processId']
         and after['lastSequence']>=before['lastSequence'] and after['elapsedMs']>=before['elapsedMs']
         and after['sampleEpochMs']>=before['sampleEpochMs']
         and after['navigationDialogSourceSequence']>=before['navigationDialogSourceSequence'])
    if after['navigationDialogSourceSequence']==before['navigationDialogSourceSequence']:need(same(before,after))


def admit(binding,run,opening,opened):
    """A root observed after ordinary input; no arrival or destruction verdict.

    Opening ownership comes from the enclosing durable input journal, not an
    adapter acknowledgment. An opaque SDK element ID alone supplies no root.
    """
    identifier(run);exact(opening,{'method','path','body','original','lookup'})
    lookup=opening['lookup'];exact(lookup,{'using','value','elements'})
    need(lookup['using']=='accessibility id' and lookup['value']=='OverteNavigation.hud.goto'
         and type(lookup['elements']) is list and len(lookup['elements'])==1
         and opening['path']==NativeUI._element(lookup['elements'][0])+'/click')
    need(opening['method']=='POST' and type(opening['path']) is str
         and re.fullmatch(r'/element/[A-Za-z0-9_.:%-]{1,480}/click',opening['path']) and opening['body']=={})
    before=opening['original'];prior=packet(binding,before);actual=packet(binding,opened);follow(before,opened)
    need(not prior['roots'] and not before['tabletShown'] and not opened['tabletShown']
         and opened['lastSequence']==before['lastSequence'] and actual['addressDialog'] and len(actual['roots'])==1)
    hud=[row for row in before['controls'] if row['id']=='hud.goto'];need(len(hud)==1 and hud[0]['enabled'])
    controls=[row for row in opened['controls'] if row['id']=='address.field'];need(len(controls)==1 and controls[0]['enabled'])
    root=actual['roots'][0]
    need(root['shown'] and root['visible'] and root['windowPresent'] and root['field']['visible'])
    return dict(iosNavigationAddressRootVersion=VERSION,binding=deepcopy(binding),runId=run,
        opening=deepcopy(opening),opened=deepcopy(opened),rootId=root['rootId'],qmlSource=root['qmlSource'],
        originalsSha256=digest(dict(opening=opening,opened=opened)))


def validate(value):
    exact(value,{'iosNavigationAddressRootVersion','binding','runId','opening','opened','rootId','qmlSource','originalsSha256'})
    need(type(value['iosNavigationAddressRootVersion']) is int and value['iosNavigationAddressRootVersion']==VERSION)
    expected=admit(value['binding'],value['runId'],value['opening'],value['opened'])
    need(same(value,expected));return deepcopy(expected)


def current(value,ui,*,closed=False):
    """Observe the same actual root or positive current inventory absence.

    A hidden object is retained responsibility. Its field text remains actual
    data; a future normal input owner must separately validate owned text and
    its own latest input/source floor before acting on it.
    """
    value=validate(value);need(type(closed) is bool);state=packet(value['binding'],ui)
    follow(value['opened'],ui);need(len(state['roots'])<=1)
    if not state['roots']:
        need(not state['addressDialog'] and not any(row['id'].startswith('address.') for row in ui['controls']))
        status='absent'
    else:
        root=state['roots'][0];need(root['rootId']==value['rootId'] and root['qmlSource']==value['qmlSource'])
        status='visible' if state['addressDialog'] else 'retained'
        if closed:need(not root['shown'] and not root['visible'] and not root['field']['visible'] and not root['field']['focused']
            and not any(row['id'].startswith('address.') for row in ui['controls']))
    if closed:need(status!='visible')
    return dict(iosNavigationAddressRootStateVersion=VERSION,leaseSha256=digest(value),original=deepcopy(ui),
        status=status,drained=status=='absent')
