"""Explicit Sample3: fresh original PNG with honest pending callback duty.

This opt-in class is not selected by the installed Runtime. Default Sample1/2
readers reject it. Pending duties cannot grant another slot or end/quiet proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import context
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.original_marker_restoration_frames import owns_slot
from adapters.script_feature.history import unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from ios.adapters.avatar_state import session
from ios.adapters.emote_images import compose,callback_duty
from ios.adapters.emote_samples import IOSEmoteSamples

VERSION=3


class EmoteCallbacksPending(MarkerNotReady):pass


def archived_sample(value,*,root,binding,run,role,lock,policy,marker_nonce,marker_url):
    """Original PNG and the duty observed in its own cut, never current absence."""
    need(isinstance(lock,ScriptSourceLock));lock.assert_held();context(binding);identifier(run)
    exact(value,{'iosEmoteSampleVersion','runId','role','binding','requestId','ticket','avatarId','phase','payload','owner'})
    need(type(value['iosEmoteSampleVersion']) is int and value['iosEmoteSampleVersion']==VERSION
        and value['runId']==run and value['role']==role and same(value['binding'],binding)
        and value['phase'] in ('observed','marker-pending') and value['requestId'].startswith('ios-'))
    identifier(value['requestId'][4:]);identifier(value['ticket'])
    if value['avatarId'] is not None:session(value['avatarId'])
    rows=unpack(value['payload']);owners=unpack(value['owner']);need(len(rows)==len(owners)==1)
    frame,owner=rows[0],owners[0];need(type(frame) is dict and type(owner) is dict and owns_slot(owner)
        and same(owner['frame'],frame['capture']) and owner['ticket']==value['ticket']
        and any(same(row['receipt'],frame['retirement']) for row in unpack(owner['transcript'])))
    args=(owner,Path(root),binding,run,role,0,value['requestId'],lock)
    if absent(frame['retirement']):raw=VulkanWorldFrameOwner.archive_original(*args)
    else:
        raw,duty=VulkanWorldFrameOwner.archive_callback_pending_original(*args)
        need(same(duty,frame['retirement']))
    try:
        result,_subject=compose(run,value['ticket'],binding,frame,raw,policy,marker_nonce=marker_nonce,
            marker_url=marker_url,avatar_id=value['avatarId'],callback_only=True)
    except MarkerNotReady:
        need(value['phase']=='marker-pending');return deepcopy(frame),raw,None,owner['name']
    need(value['phase']=='observed');return deepcopy(frame),raw,result,owner['name']


class IOSEmoteCallbackSamples(IOSEmoteSamples):
    SampleVersion=VERSION
    SampleReads=(VERSION,)
    ImageCompose=staticmethod(partial(compose,callback_only=True))
    ArchivedSample=staticmethod(archived_sample)

    def before_capture(self):
        # No new row/nonce/capture exists until every old duty is actually
        # absent. A fresh INSPECT is mandatory even after prior release return.
        self.bound()
        for row in self.state['rows']:
            owner=self.owner(row);saved=owner.store.read()
            if saved is None:need(row['phase'] in ('reserved','abandoned'));continue
            need(owns_slot(saved));proof=owner.release_once()
            if not absent(proof):
                need(callback_duty(proof))
                raise EmoteCallbacksPending('Original frame callback is still live')
        self.bound()

    def release_owner(self,owner):return owner.release_once()

    def owner_original(self,owner):
        value=owner.store.read();need(value is not None)
        args=(value,self.root,self.binding,self.run,self.role,0,owner.request_id,self.lock)
        if value['absence'] is not None:return VulkanWorldFrameOwner.archive_original(*args)
        raw,_duty=VulkanWorldFrameOwner.archive_callback_pending_original(*args)
        return raw
