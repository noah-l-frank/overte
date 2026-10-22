"""Refresh original native quiet after local marker retirement, without inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.emote_marker_partial import drained_partial
from ios.adapters.web_closures import drained_owned_resources


def refresh(scope,*,clock,sleep,pointers=None,keys=None):
    need(isinstance(scope,IOSEmoteMarkerScope) and callable(clock) and callable(sleep))
    from ios.adapters.emote_marker_recovery import IOSEmoteMarkerRecovery
    scope.bound();IOSEmoteMarkerRecovery(scope).recover();need(scope.state['phase']=='released' and scope.state['pending'] is None and scope.state['baseline'] is not None)
    baseline=scope.frames[scope.state['baseline']-1];candidate=[];started=clock()
    while clock()-started<10:
        if keys is not None:keys.abandon();keys.capture()
        if pointers is not None:pointers.abandon();pointers.capture()
        frame=scope.capture('retirement-quiet-refresh')
        if pointers is not None:pointers.capture()
        if keys is not None:keys.capture()
        try:
            scope.ui_absent(frame);scope.dialog_drained(frame)
            need(frame['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
            body_preserved(baseline['world'],frame['world']);view_preserved(baseline['world'],frame['world'])
            if scope.state['cleanupMode']=='unloaded':
                scope.unexecuted(frame);need(frame['world']['source']['tree']['entities']==baseline['world']['source']['tree']['entities'])
                drained_partial(frame['web'],baseline['web'])
            else:
                scope.restored_marker(baseline,frame,scope.state['admission'],scope.state['stopBarrier'])
                drain=drained_partial if scope.state['cleanupMode'] in ('partial-execution','finished-execution') else drained_owned_resources
                drain(frame['web'],scope.frames[scope.state['webAdmission']-1]['web'])
        except NativeUIError:candidate=[]
        else:candidate.append(len(scope.frames))
        # Existing released quiet originals remain valid throughout every
        # passive read, including an interrupted first or middle acquisition.
        # Scope's own original/pending/recovery journals retain those reads.
        if len(candidate)>=3 and scope.quiet_interval(scope.frames[candidate[0]-1],frame):
            if pointers is not None:
                try:pointers.quiet([scope.frames[index-1] for index in candidate])
                except NativeUIError:candidate=[];sleep(.15);continue
            if keys is not None:
                try:keys.quiet([scope.frames[index-1] for index in candidate])
                except NativeUIError:candidate=[];sleep(.15);continue
            scope.state['quiet']=candidate;scope.save();return True
        sleep(.15)
    raise NativeUIError('Original Emote resources have not remained quiet after retirement')
