"""Fresh original native absence after a historically proved Emote retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.emote_marker_partial import drained_partial
from ios.adapters.emote_native_prefix import follow as native_prefix
from ios.adapters.web_closures import drained_owned_resources


def validate(scope,entities,files,pointers,prior_native):
    scope.lock.assert_held();need(scope.state['phase']=='released' and scope.state['pending'] is None and len(scope.state['quiet'])>=3 and scope.state['quiet'][-1]==len(scope.frames))
    baseline=scope.frames[scope.state['baseline']-1];quiet=[scope.frames[index-1] for index in scope.state['quiet']]
    need(scope.quiet_interval(quiet[0],quiet[-1]))
    native_prefix(prior_native,quiet[0]['clockJoin']['nativeBefore'])
    calls=prior_native['animation']['history']['callSequence']
    for frame in quiet:
        scope.ui_absent(frame);scope.dialog_drained(frame)
        need(frame['clockJoin']['nativeAfter']['animation']['overrideActive'] is False
            and frame['clockJoin']['nativeAfter']['animation']['history']['callSequence']==calls)
        body_preserved(baseline['world'],frame['world']);view_preserved(baseline['world'],frame['world'])
        if scope.state['cleanupMode']=='unloaded':
            scope.unexecuted(frame);need(frame['world']['source']['tree']['entities']==baseline['world']['source']['tree']['entities'])
            drained_partial(frame['web'],baseline['web'])
        else:
            scope.restored_marker(baseline,frame,scope.state['admission'],scope.state['stopBarrier'])
            drain=drained_partial if scope.state['cleanupMode'] in ('partial-execution','finished-execution') else drained_owned_resources
            drain(frame['web'],scope.frames[scope.state['webAdmission']-1]['web'])
    entities.closed(scope);end=entities.latest()['clockJoin']['nativeAfter']
    if scope.state['fileOwnership'] is not None:
        need(files is not None and files.state['pending'] is None and files.state['records'])
        last=files.original(files.state['records'][-1]);need(last['kind']=='absent' and last['ownership']==scope.state['fileOwnership'])
        native_prefix(end,last['clockJoin']['nativeBefore']);end=last['clockJoin']['nativeAfter']
    else:need(files is None)
    need(end['animation']['overrideActive'] is False and end['animation']['history']['callSequence']==calls)
    closure=pointers.closed(scope);final=closure['last']['clockJoin']
    native_prefix(end,final['nativeBefore']);end=final['nativeAfter']
    need(end['animation']['overrideActive'] is False and end['animation']['history']['callSequence']==calls)
    return end
