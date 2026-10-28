"""Private explicit Feature4 consumer, not selected by public configuration.

Only this prospective profile combines rooted Marker/Observer3/Sample3 and
Recovery2; all ordinary/default classes remain literal. No whole flag is set.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.contract import arguments
from ios.adapters.emote_callback_observation import IOSEmoteCallbackRootedObserver,RESOURCE
from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples,EmoteCallbacksPending
from ios.adapters.emote_feature import EmoteObservationPending,EmoteImagePending
from ios.adapters.emote_operation import operation
from ios.adapters.emote_scene_operation import retry_scene
from ios.adapters.emote_observation_operation import retry_observation,ObservationPending
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature

PROFILE=dict(callbackProfileVersion=1,sampleVersion=3,imageVersion=3,observerOwnerVersion=3,
    sampleRecoveryVersion=2,resourceAlias=RESOURCE)


class IOSEmoteCallbackFeature(IOSEmoteRootedFeature):
    FORMAT_VERSION=4
    PAIRED_FORMAT_VERSION=4
    PROFILE_FIELDS=frozenset({'callbackProfile'})
    PAIRED_PROFILE_FIELDS=frozenset({'targetPair','callbackProfile'})
    Samples=IOSEmoteCallbackSamples
    Observer=IOSEmoteCallbackRootedObserver

    def profile_envelope(self,state):
        value=super().profile_envelope(state)
        if self.previous is not None:
            need(self.previous.get('iosEmoteFeatureVersion')==4 and same(self.previous.get('callbackProfile'),PROFILE))
        return dict(value,callbackProfile=PROFILE.copy())

    @operation(30)
    @retry_scene
    @retry_observation
    def observe(self,call):
        call=arguments('feature.emotes.observe',call);need(call['runId']==self.run)
        with self.held(30):
            try:
                parts=self.prepare();observer=parts['observer'];current=self.phase.read()
                need(isinstance(parts['samples'],self.Samples) and isinstance(observer,self.Observer))
                observer.abandon_read()
                if current['verb']=='cleanup':
                    self.clean_local(parts);result=self.retirement_sample(parts,call['afterSequence'])
                    if self.role=='actor':self.publish_retirement(parts)
                    return result
                need(self.state['phase']=='ready')
                barrier=(self.state['inputBarrier'] if self.role=='primary' and self.state['lastCall'] is not None
                    and self.state['lastCall']['ticket']==current['ticket'] else None)
                result=observer.observe(call['afterSequence'],input_barrier=barrier)
            except (EmoteCallbacksPending,EmoteObservationPending,EmoteImagePending):
                # Original WALs/duties survive; both SDK locks unwind before
                # the existing typed readiness wait. No input/PNG is replayed.
                status=self.phase.previous;need(status is not None and status['active'] and status['activations'])
                raise ObservationPending(status['activations'][-1]['ticket']) from None
            if self.role=='actor':observer.publish_latest()
            return result
