"""Join actual configured compiled Emote source to passive cached FBX models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.emote_rig_measurements import asset_urls
from adapters.emote_source_profile import select_from_roots
from adapters.native_animation_inventory import validate as inventory_packet
from adapters.native_animation_source import controlled_model
from adapters.native_feature_observation import exact,need

VERSION=1


def ready(group,*,pid,epoch):
    """Return original matched rows only; never load/repair/cache an animation.

    The owning transport must acquire this whole group afresh, enforce its
    monotonic deadline and retain these originals. This is not playback,
    visible rendering, input delivery or whole-feature admission.
    """
    exact(group,{'rootsBefore','script','inventory','rootsAfter'})
    selected=select_from_roots(group['script'],group['rootsBefore'],group['rootsAfter'],pid=pid,epoch=epoch)
    need('compilation' in selected)
    packet=group['inventory'];need(type(packet) is dict and type(packet.get('commandId')) is str)
    request=dict(schemaVersion=1,commandId=packet['commandId'],action='feature-animation-inventory-observe')
    inventory_packet(packet,request,pid,epoch)
    need(packet['instance']==group['rootsBefore']['instance']
        and group['script']['capturedEpochMs']<=packet['requestedEpochMs']<=packet['capturedEpochMs']
        <=group['rootsAfter']['requestedEpochMs'])
    resources=[]
    for url,name in asset_urls(selected).items():
        digest=hashlib.sha256(url.encode()).hexdigest()
        matches=[row for row in packet['source']['resources'] if row['urlSha256']==digest]
        need(len(matches)==1);row=matches[0]
        need(row['loaded'] is True and row['failed'] is False and row['model'] is not None)
        controlled_model(row['model'],name,url,packet['capturedEpochMs'])
        resources.append(dict(name=name,resource=deepcopy(row)))
    return dict(emoteAnimationReadinessVersion=VERSION,group=deepcopy(group),resources=resources)
