"""Extend an already proved original quiet window with fresh passive sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.emote_marker_partial import drained_partial
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_marker_recovery import IOSEmoteMarkerRecovery
from ios.adapters.web_closures import drained_owned_resources


def extend(scope,pointers):
    """No timer wait is claimed: actual original histories cover the interval."""
    need(isinstance(scope,IOSEmoteMarkerScope) and isinstance(pointers,IOSEmotePointers))
    scope.bound();IOSEmoteMarkerRecovery(scope).recover()
    need(scope.state['phase']=='released' and scope.state['pending'] is None and len(scope.state['quiet'])>=3)
    quiet=[scope.frames[index-1] for index in scope.state['quiet']];baseline=scope.frames[scope.state['baseline']-1]
    need(scope.quiet_interval(quiet[0],quiet[-1]))
    pointers.abandon();pointers.capture();frame=scope.capture('retirement-fresh-end');pointers.capture()
    scope.ui_absent(frame);scope.dialog_drained(frame)
    before=quiet[0]['clockJoin']['nativeAfter'];after=frame['clockJoin']['nativeAfter']
    need(after['animation']['overrideActive'] is False and before['animation']['history']['callSequence']==after['animation']['history']['callSequence']
        and frame['clockJoin']['hostBeforeMonotonic']-quiet[0]['clockJoin']['hostAfterMonotonic']<45)
    body_preserved(baseline['world'],frame['world']);view_preserved(baseline['world'],frame['world'])
    if scope.state['cleanupMode']=='unloaded':
        scope.unexecuted(frame);need(frame['world']['source']['tree']['entities']==baseline['world']['source']['tree']['entities'])
        drained_partial(frame['web'],baseline['web'])
    else:
        scope.restored_marker(baseline,frame,scope.state['admission'],scope.state['stopBarrier'])
        drain=drained_partial if scope.state['cleanupMode'] in ('partial-execution','finished-execution') else drained_owned_resources
        drain(frame['web'],scope.frames[scope.state['webAdmission']-1]['web'])
    candidate=list(scope.state['quiet'])+[len(scope.frames)]
    pointers.quiet([scope.frames[index-1] for index in candidate]);scope.state['quiet']=candidate;scope.save();return True
