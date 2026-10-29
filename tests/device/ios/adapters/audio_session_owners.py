"""Fail closed before ordinary SDK work with unretired Audio responsibility.

Page closure and tap retirement are useful components, not a complete Audio
callback/source/process retirement proof. No such final protocol exists yet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from feature_journeys.contract import identifier

PREFIX='ios-audio-'


def owners_absent(adapter,selector):
    root=adapter.state_path(selector).parent
    if not root.exists():return True
    PrivateFeatureState(root/'audio-entry-boundary.json')._parent()
    entries=list(root.iterdir());need(len(entries)<=4096)
    return not any(path.name.startswith(PREFIX) for path in entries)


def ensure_released(adapter,selector):
    if not owners_absent(adapter,selector):
        raise NativeUIError('Audio ownership requires original complete cleanup before ordinary session operations')
    return True


def register_scope(adapter,selector,binding,run,artifact_root):
    """Persist the source location before any Audio input or evidence write.

    This also keeps external artifact roots discoverable if their operation
    owner is lost. It supplies no native or cleanup fact.
    """
    root=Path(artifact_root);need(root.is_absolute() and root.resolve()==root)
    value=dict(iosAudioScopeVersion=1,binding=context(binding),runId=identifier(run),artifactRoot=str(root))
    store=PrivateFeatureState(adapter.state_path(selector).with_name('ios-audio-scope.json'));previous=store.read()
    if previous is None:store.write(value,None)
    else:need(same(previous,value))
    need(same(store.read(),value));return value


def recorded_entry(runtime,selector,owner,call):
    """Admit only this held normal owner; this does not retire any ownership.

    Typed historical decoders plus the existing original inventory lease qualify
    actual read membership for this invocation only. No memo or live fact escapes.
    The ordinary InstalledAdapter entrypoints never select this route.
    """
    from adapters.original_file_reads import collect,scope as original_scope,readonly
    from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
    from ios.adapters.audio_runtime import IOSAudioRuntime
    from ios.adapters.emote_original_lease import EmoteOriginalLease
    need(type(owner) is IOSAudioRecordedOwner and isinstance(runtime,IOSAudioRuntime)
        and not owner.historical and owner.version>=4 and call['runId']==owner.run
        and call['fixtureUrl']==owner.fixture_url
        and owner.store.path==runtime.state_path(selector).with_name('ios-audio-recorded-owner.json'))
    owner.lock.assert_held();need(same(owner.store.read(),owner.previous))
    root=owner.store.path.parent;need(owner.lock.path==root/'script-feature-sources.lock')
    scope=PrivateFeatureState(root/'ios-audio-scope.json')
    expected=dict(iosAudioScopeVersion=1,binding=owner.binding,runId=owner.run,artifactRoot=str(owner.root))
    need(same(scope.read(),expected))
    background=call['verb']=='background-resume'
    if background:
        # This existing OS-only source remains valid while the original Home
        # return is uncertain; native/UI foreground guards remain unmodified.
        from ios.adapters.lifecycle_background import LifecycleOSContext
        source=LifecycleOSContext(runtime,selector,owner.binding)
        check=lambda:source.probe() is not None
    else:
        source=runtime._sources(selector);need(same(source['binding'],owner.binding))
        check=source['check'];need(check() is not False)
    directories={root,owner.root}
    leases=[EmoteOriginalLease(directory,[]) for directory in directories]
    def census():
        paths=set()
        for directory in directories:
            entries=list(directory.iterdir());need(len(entries)<=4096)
            paths.update(path for path in entries if path.name.startswith(PREFIX))
        return paths
    before=census()
    with collect() as reads,original_scope(fresh=True),readonly():
        need(same(scope.read(),expected) and same(owner.store.read(),owner.previous))
        if owner.previous is None:
            # No saved Parent can delegate any orphan child responsibility.
            need(before=={scope.path})
            need(same(owner.decode(owner.envelope(owner.state)),owner.state))
        else:
            parent=IOSAudioRecordedOwner.archive(owner.store,owner.root,owner.binding,owner.run,owner.lock,owner.fixture_url)
            need(same(parent.state,owner.state))
            authorization=PrivateFeatureState(root/'ios-audio-authorization-owner.json')
            starts=PrivateFeatureState(root/'ios-audio-authorized-starts.json')
            if authorization.path.exists():
                from ios.adapters.audio_authorization_sources import AudioAuthorizationSources
                grants=AudioAuthorizationSources.archive(authorization,parent)
                if starts.path.exists():
                    from ios.adapters.audio_authorized_start import AudioAuthorizedStarts
                    AudioAuthorizedStarts.archive(starts,parent,grants)
            else:need(not starts.path.exists())
            for name in ('ios-audio-pcm-lease.json','ios-audio-close-lease.json'):
                store=PrivateFeatureState(root/name)
                if store.path.exists():
                    from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
                    IOSAudioPCMLease.archive(store,parent)
            store=PrivateFeatureState(root/'ios-audio-background.json')
            if store.path.exists():
                from adapters.script_feature.history import unpack
                from ios.adapters.audio_background import AudioBackground
                from ios.adapters.audio_background_bridge import RecordedPrefix
                from ios.adapters.lifecycle_background import LifecycleOSContext
                current=store.read();rows=unpack(current['payload']);need(len(rows)==1)
                prefix=RecordedPrefix(parent,rows[0]['parent'],parent.state)
                os_context=source if background else LifecycleOSContext(runtime,selector,owner.binding)
                AudioBackground.archive(store,prefix,os_context.gate.bundle)
        # A filename/header is not its own membership. Unknown, foreign,
        # missing-parent and unparsed child/Settings responsibilities refuse.
        need(before==census() and before.issubset(reads))
    need(check() is not False and same(owner.store.read(),owner.previous)
        and same(scope.read(),expected))
    for lease in leases:lease.guard()


def installed_entry(function=None,*,recorded_action=False):
    need(type(recorded_action) is bool)
    if function is None:return lambda actual:installed_entry(actual,recorded_action=recorded_action)
    @wraps(function)
    def entry(self,selector,*args,**kwargs):
        if recorded_action:
            from feature_journeys.contract import arguments
            from ios.adapters.audio_pcm_lease import INPUT_ORIGIN_PROFILE
            need(len(args)==1 and type(args[0]) is dict and set(kwargs)<=set(('runtime','pcm_profile')) and 'runtime' in kwargs)
            profile=kwargs.get('pcm_profile')
            need(profile is None or type(profile) is str and profile==INPUT_ORIGIN_PROFILE)
            args=(deepcopy(arguments('feature.audio.act',args[0])),)
            recorded_entry(kwargs['runtime'],selector,self,args[0])
        else:ensure_released(self,selector)
        return function(self,selector,*args,**kwargs)
    return entry
