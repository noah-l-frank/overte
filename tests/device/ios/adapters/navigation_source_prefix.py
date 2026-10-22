"""Historical Worlds source prefixes, including interrupted acquisitions.

These checks retain source births, clocks and histories. They neither turn an
incomplete group into a measurement nor authorize a repeated input or capture.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.native_navigation_replies import validate as reply_packet
from adapters.script_feature.history import same
from ios.adapters import location_bookmarks,places_model,places_http,navigation_dialogs,normal_input
from ios.adapters.navigation_state import validate as navigation_packet,ACTION

ORDER=('bookmarks','model','http','dialogs','replies','ui','currentNavigation')
MODULES=dict(bookmarks=location_bookmarks,model=places_model,http=places_http,dialogs=navigation_dialogs)


def validate(originals,run,pid):
    """Validate each accepted packet at its OWN historical clock endpoint."""
    for name,packet in originals.items():
        if name in MODULES:
            module=MODULES[name]
            action='feature-ios-location-bookmarks' if name=='bookmarks' else module.ACTION
            module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=action,runId=run),pid)
        elif name=='replies':
            reply_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],
                action='feature-navigation-replies',runId=run),pid,packet['capturedEpochMs'])
        elif name=='ui':
            normal_input.observation(packet,pid,packet['sampleEpochMs'])
            need(all(type(packet.get(key)) is int and packet[key]>=1
                for key in ('placesSourceSequence','navigationDialogSourceSequence')))
        elif name in ('navigationBefore','navigationAfter','currentNavigation'):
            navigation_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=ACTION,runId=run),pid)


def follow(previous,current,run,pid):
    """Extend every returned shared channel; missing channels gain no facts."""
    validate(previous,run,pid);validate(current,run,pid)
    for name,module in MODULES.items():
        if name not in previous or name not in current:continue
        packet=current[name]
        action='feature-ios-location-bookmarks' if name=='bookmarks' else module.ACTION
        module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=action,runId=run),
            pid,previous=previous[name])
    if 'replies' in previous and 'replies' in current:
        old,new=previous['replies'],current['replies']
        need(new['instance']==old['instance'] and new['sequence']>old['sequence']
            and new['commandId']!=old['commandId'] and new['capturedEpochMs']>=old['capturedEpochMs']
            and new['currentLookupGeneration']>=old['currentLookupGeneration']
            and len(new['events'])>=len(old['events']) and same(new['events'][:len(old['events'])],old['events']))
    if 'ui' in previous and 'ui' in current:
        old,new=previous['ui'],current['ui']
        need(new['instance']==old['instance'] and new['lastSequence']>=old['lastSequence']
            and new['elapsedMs']>=old['elapsedMs'] and new['sampleEpochMs']>=old['sampleEpochMs']
            and all(new[key]>old[key] for key in ('placesSourceSequence','navigationDialogSourceSequence')))
    if 'currentNavigation' in previous and 'navigationBefore' in current:
        packet=current['navigationBefore']
        navigation_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=ACTION,runId=run),
            pid,previous=previous['currentNavigation'])
