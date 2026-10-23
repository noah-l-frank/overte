"""Fresh scope-three quiet joins actual global inputs and held native roots.

The legacy full-drain refresh/extension readers keep their original semantics.
These passive reads retain all ordinary ownership and cannot complete Emotes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters import original_marker_holders as holders
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.emote_marker_recovery import IOSEmoteMarkerRecovery
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope


def enter(scope,pointers,keys):
    need(type(scope) is IOSEmoteRootedMarkerScope
        and isinstance(pointers,IOSEmotePointers) and isinstance(keys,IOSEmoteKeys))
    need(all(owner.run==scope.run and owner.role==scope.role and owner.root==scope.root
        and same(owner.binding,scope.binding) and owner.lock.path==scope.lock.path for owner in (pointers,keys)))
    scope.bound();IOSEmoteMarkerRecovery(scope).recover()
    need(scope.state['phase']=='released' and scope.state['pending'] is None
        and scope.state['baseline'] is not None and len(scope.state['quiet'])>=3)


def frame(scope,pointers,keys,label):
    keys.abandon();keys.capture();pointers.abandon();pointers.capture()
    current=scope.capture(label);pointers.capture();keys.capture();return current


def validate(scope,current,previous=None):
    baseline=scope.frames[scope.state['baseline']-1]
    scope.ui_absent(current);scope.dialog_drained(current)
    need(current['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
    body_preserved(baseline['world'],current['world']);view_preserved(baseline['world'],current['world'])
    if scope.state['cleanupMode']=='unloaded':
        scope.unexecuted(current)
        need(current['world']['source']['tree']['entities']==baseline['world']['source']['tree']['entities'])
        admitted=baseline
    else:
        scope.restored_marker(baseline,current,scope.state['admission'],scope.state['stopBarrier'])
        admitted=scope.frames[scope.state['webAdmission']-1]
    holders.web('emote',current['web'],admitted['web'],partial=scope.state['cleanupMode']!='full')
    if previous is not None:
        scope.unchanged_roots(previous,current)
        need(previous['clockJoin']['nativeAfter']['animation']['history']['callSequence']
            ==current['clockJoin']['nativeAfter']['animation']['history']['callSequence'])


def refresh(scope,pointers,keys,*,clock,sleep):
    need(callable(clock) and callable(sleep));enter(scope,pointers,keys)
    candidate=[];started=clock()
    while clock()-started<10:
        current=frame(scope,pointers,keys,'rooted-retirement-refresh')
        try:validate(scope,current,None if not candidate else scope.frames[candidate[-1]-1])
        except NativeUIError:candidate=[]
        else:candidate.append(len(scope.frames))
        if len(candidate)>=3 and scope.quiet_interval(scope.frames[candidate[0]-1],current):
            originals=[scope.frames[index-1] for index in candidate]
            try:pointers.quiet(originals);keys.quiet(originals)
            except NativeUIError:candidate=[]
            else:
                scope.state['quiet']=candidate;scope.save();return True
        sleep(.15)
    raise NativeUIError('Original rooted Emote input and holder histories are not quiet')


def extend(scope,pointers,keys):
    enter(scope,pointers,keys)
    quiet=[scope.frames[index-1] for index in scope.state['quiet']]
    need(scope.quiet_interval(quiet[0],quiet[-1]))
    current=frame(scope,pointers,keys,'rooted-retirement-fresh-end')
    validate(scope,current,quiet[-1])
    need(current['clockJoin']['hostBeforeMonotonic']-quiet[0]['clockJoin']['hostAfterMonotonic']<45)
    candidate=list(scope.state['quiet'])+[len(scope.frames)]
    originals=[scope.frames[index-1] for index in candidate]
    pointers.quiet(originals);keys.quiet(originals)
    scope.state['quiet']=candidate;scope.save();return True
