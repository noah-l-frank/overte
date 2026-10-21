"""Join owned ordinary Emote input receipts to fresh original native effects.

This supplies current measured state, not images, independent publication or a
whole-feature cleanup verdict. It advertises no complete feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.emote_rig_measurements import playback,restoration
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.token_emote_ui import snapshot
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_originals import BLOCK
from overte_phone_script_history import same,unpack

VERSION=1
PLAYS={'play','sit','override'}


class PhoneEmoteEffects:
    def __init__(self,inputs):
        need(isinstance(inputs,PhoneEmoteInputs));self.inputs=inputs;self.source=inputs.source

    def original(self,reference):
        frame=self.inputs.original(reference)
        # Reopen the exact immutable original, rather than trusting a caller's
        # in-memory frame or a freshly computed digest of substituted values.
        index=reference['revision'];block=(index-1)//BLOCK
        entries=self.source.originals.manifest(self.source.state['manifests'][block])
        original=self.source.originals.read(self.source.originals.expand(entries[(index-1)%BLOCK]))
        need(same(original,frame));return frame

    def reference(self):return self.inputs.reference()

    def panel(self,frame):
        ui=snapshot(frame['ui']);pages=[row for row in ui['controls'] if row['id']=='emote.page']
        need(len(pages)<=1)
        return ui['open'] and ui['ready'] and len(pages)==1

    def after(self,row,reference):
        self.inputs.row(row);need(row['phase']=='acknowledged' and row['before'] is not None)
        frame=self.original(reference);before=self.original(row['before'])
        need(reference['revision']>row['before']['revision'])
        for phase in ('phaseBefore','phaseAfter'):self.inputs.active(row['call'],frame[phase])
        native=frame['group']['native'];floor=before['group']['native']['capturedEpochMs'];sequence=before['ui']['scope']['sequence']
        for item in row['intents']:
            need(item['after'] is not None)
            after=item['after'] if item['kind']=='qt' else self.original(item['after'])['ui']
            floor=max(floor,after['scope']['capturedEpochMs']);sequence=after['scope']['sequence']
        need(native['requestedEpochMs']>=floor and frame['ui']['scope']['sequence']==sequence)
        return frame

    def played(self,row,reference):
        need(row['call']['verb'] in PLAYS);frame=self.after(row,reference)
        intents=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
        need(len(intents)==1);intent=intents[0]
        before=self.original(intent['barrier'])
        proof=playback(frame['group'],before['group']['native'],pid=self.source.pid,epoch=frame['epochMs'])
        measured=proof['state']['animation']
        # The normal input and the measured loaded resource must agree. The
        # returned name/variant/progress still comes solely from native effects.
        selected='Sit' if row['call']['verb']=='sit' else row['call']['inputs']['name']
        from adapters.emote_rig_measurements import source
        _profile,_native,urls=source(frame['group'],self.source.pid,frame['epochMs'])
        name=urls[proof['event']['request']['url']]
        need((name.startswith('Sit') if selected=='Sit' else name==selected)
            and measured in ('idle','Sit' if name.startswith('Sit') else name))
        return proof

    def restore_play(self,reference):
        exact(reference,{'inputTicket','frame'})
        rows=self.inputs.state['history']
        plays=[row for row in rows if row['call']['verb'] in PLAYS]
        need(bool(plays) and reference['inputTicket']==plays[-1]['call']['ticket'])
        return self.played(plays[-1],reference['frame'])

    def measure(self,reference,*,played=None):
        owner,source=self.inputs,self.source
        started=source.monotonic();need(number(started,0,1e15));owner.bound()
        need(source.state['phase']=='ready' and source.state['pending'] is None
            and owner.history_state['pendingArchive'] is None and reference==self.reference())
        need(source.previous is not None and owner.previous is not None
            and same(unpack(source.previous['payload']),[source.state]))
        original_state,original_history=owner.decode(owner.previous)
        need(same(original_state,owner.state) and same(original_history,owner.history_state))
        native=source.adapter._native_feature_observer(source.selector,read_only=True)
        need(native.pid==source.pid and native.ios is False)
        epoch=native.clock_ms();host=source.phase.epoch_ms();clock=source.monotonic()
        need(integer(epoch,1) and number(host,1,1e15) and number(clock,started,1e15))
        row=owner.state['current'];need(row is not None);frame=self.after(row,reference)
        call=row['call'];verb=call['verb'];proof=None;play_reference=deepcopy(played)
        if verb in PLAYS:
            need(played is None);proof=self.played(row,reference)
            state=deepcopy(proof['state']);kind='playback'
            play_reference=dict(inputTicket=call['ticket'],frame=deepcopy(reference))
        elif verb=='cancel' and row['idleReset'] is not None:
            need(played is None and not frame['group']['native']['animation']['overrideActive'])
            # No new active-to-inactive ordinary input exists for an idle reset.
            # It cannot satisfy the final early-cancel requirement.
            state=dict(animation='idle',sit='none',override=False,poseProgress=0.,restoredBeforeNominalEnd=False);kind='idle-reset'
        elif played is not None:
            original=self.restore_play(played)
            barrier=None
            if verb=='cancel':
                intents=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
                need(len(intents)==1);barrier=self.original(intents[0]['barrier'])['group']['native']
            else:need(verb in ('wait-complete','open','close'))
            proof=restoration(frame['group'],original,pid=source.pid,epoch=frame['epochMs'],native_barrier=barrier)
            state=deepcopy(proof['state']);kind='restoration'
        else:
            need(verb in ('open','close') and not any(item['call']['verb'] in PLAYS for item in owner.state['history'])
                and frame['group']['native']['animation']['overrideActive'] is False)
            state=dict(animation='idle',sit='none',override=False,poseProgress=0.,restoredBeforeNominalEnd=False);kind='idle'
        state['panel']=self.panel(frame)
        if verb=='open':need(state['panel'])
        if verb=='close':need(state['panel'] is False and frame['ui']['open'] is False)
        value=dict(emoteEffectVersion=VERSION,runId=source.run,binding=deepcopy(source.binding),call=deepcopy(call),
            frame=deepcopy(reference),playbackReference=play_reference,kind=kind,state=state,proof=proof)
        # Check durable ownership and actual provider phase again after joins;
        # neither a stale frame nor a slow final guard may publish fresh facts.
        owner.bound();status=source.phase.status(frame['phaseAfter']);owner.active(call,status);owner.bound()
        delivered=native.clock_ms();delivered_host=source.phase.epoch_ms();owner.bound()
        returned=deepcopy(value);final=source.monotonic()
        need(number(final,clock,1e15) and final-started<5 and integer(delivered,epoch)
            and number(delivered_host,host,1e15))
        barrier=frame['group']['rootsBefore']['requestedEpochMs'];phase=frame['phaseBefore']['capturedEpochMs']
        fresh(barrier,delivered);fresh(phase,delivered_host)
        need(max(delivered-barrier,epoch-barrier+(final-clock)*1000)<=1500
            and max(delivered_host-phase,host-phase+(final-clock)*1000)<=1500)
        return returned
