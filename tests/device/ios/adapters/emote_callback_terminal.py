"""Explicit Callback Feature8 terminal inspect/seal on actual existing owners.

Only original Live2/Window2/Journal2 and current role responsibilities join.
Finish remains closed: no legacy State/ownership/fence/Stop/SDK end is admitted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys import terminal
from ios.adapters.emote_callback_live import IOSEmoteCallbackLive,IOSEmoteCallbackLiveFeature,PROFILE7
from ios.adapters.emote_callback_scene import IOSEmoteCallbackKeyedRetirement,IOSEmoteCallbackSceneRetirement
from ios.adapters.emote_callback_observation import IOSEmoteCallbackSampleRecovery
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_rooted_responsibility import IOSEmoteRootedResponsibility
from ios.adapters.emote_callback_window import IOSEmoteCallbackWindow
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal
from ios.adapters.emote_rooted_inventory import IOSEmoteRootedInventory
from ios.adapters.emote_terminal import IOSEmoteTerminal
from ios.adapters.emote_rooted_end_lock import held_existing
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_operation import operation
from ios.adapters import emote_callback_archive as archive
from ios.adapters import emote_callback_drain_originals as drains
from ios.adapters.emote_callback_current_state import current as current_state

PROFILE8=dict(PROFILE7,callbackProfileVersion=5,terminalWindowVersion=2,terminalJournalVersion=2)


class IOSEmoteCallbackTerminalFeature(IOSEmoteCallbackLiveFeature):
    FORMAT_VERSION=8
    PAIRED_FORMAT_VERSION=8

    def profile_envelope(self,state):
        value=IOSEmoteRootedFeature.profile_envelope(self,state)
        if self.previous is not None:need(self.previous.get('iosEmoteFeatureVersion')==8 and same(self.previous.get('callbackProfile'),PROFILE8))
        return dict(value,callbackProfile=deepcopy(PROFILE8))

    @operation(30)
    def terminal(self,call):
        need(self.role=='primary');call=terminal.arguments('emotes',call);need(call['runId']==self.run)
        return self.runtime._emote_callback_terminal(self).invoke(call)


class IOSEmoteCallbackResponsibility(IOSEmoteRootedResponsibility):
    Owner=IOSEmoteCallbackKeyedRetirement
    Live=IOSEmoteCallbackLive
    Scene=IOSEmoteCallbackSceneRetirement
    SampleRecovery=IOSEmoteCallbackSampleRecovery

    def gpu_originals(self,parts,owner,live):
        snapshot=archive.capture(owner,self.flow.state['cleanup'][-1])
        return current_state(snapshot,lock=owner.lock,primary_lock=owner.primary_lock)['currentGpu']

    def original_carriers(self,parts):
        result=super().original_carriers(parts)
        pattern=(self.flow.root,drains.NAMESPACE+'-*');self.patterns.append(pattern)
        result.update(pattern[0].glob(pattern[1]));return result


class IOSEmoteCallbackTerminalJournal(IOSEmoteTerminalJournal):
    Window=IOSEmoteCallbackWindow
    FORMAT_VERSION=2
    WINDOW_VERSION=2


class IOSEmoteCallbackInventory(IOSEmoteRootedInventory):
    Journal=IOSEmoteCallbackTerminalJournal


class IOSEmoteCallbackTerminal(IOSEmoteTerminal):
    Flow=IOSEmoteCallbackTerminalFeature
    Live=IOSEmoteCallbackLive
    Responsibility=IOSEmoteCallbackResponsibility
    Window=IOSEmoteCallbackWindow
    Journal=IOSEmoteCallbackTerminalJournal
    Inventory=IOSEmoteCallbackInventory
    snapshot_capture=staticmethod(archive.capture)

    def sample_envelope(self,raw):
        projection=raw['sampleOwners']
        need(type(projection) is dict and type(projection.get('iosEmoteCallbackSampleOwnersVersion')) is int
            and projection['iosEmoteCallbackSampleOwnersVersion']==4)
        return projection['samples']

    @staticmethod
    def existing_actor(primary):
        # No archived Finish fallback is available in this explicit new
        # profile. An absent current Actor feature remains unresolved.
        need(primary.lock._owner is None)
        path=primary.runtime.state_path(primary.actor_selector).with_name('ios-emote-actor-feature.json')
        actor_lock=ScriptSourceLock(path.with_name('script-feature-sources.lock'))
        with held_existing(actor_lock),held_existing(primary.lock):
            value=PrivateFeatureState(path).read();actual=deepcopy(value)
            need(type(value) is dict and type(value.get('iosEmoteFeatureVersion')) is int and value['iosEmoteFeatureVersion']==8)
            exact(value,{'iosEmoteFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload','targetPair','callbackProfile'})
            need(value['runId']==primary.run and value['role']=='actor' and value['fixtureUrl']==primary.phase.fixture_url
                and same(value['callbackProfile'],PROFILE8))
            from ios.adapters.emote_target_pair import selected
            pair=selected(value['targetPair']);need(same(pair,primary.configured_pair)
                and value['artifactRoot']==pair['actorArtifactRoot'] and str(primary.root)==pair['primaryArtifactRoot'])
            actor=IOSEmoteCallbackTerminalFeature(primary.runtime,primary.actor_selector,primary.client,primary.run,'actor',
                value['artifactRoot'],value['imagePolicy'],primary_selector=primary.selector,monotonic=primary.monotonic,
                epoch_ms=primary.epoch_ms,sleep=primary.sleep,target_pair=pair)
            actor.lock,actor.primary_lock=actor_lock,primary.lock
            actor.load();need(same(actor.previous,actual));return actor

    def invoke(self,call):
        call=terminal.arguments('emotes',call);need(call['runId']==self.flow.run)
        if call['stage']=='finish':
            raise EmoteObservationPending('Callback terminal seal retained; explicit copied-State/fence/process/SDK end profile remains closed')
        return super().invoke(call)
