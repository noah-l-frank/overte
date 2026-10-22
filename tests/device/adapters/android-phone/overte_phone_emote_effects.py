"""Join owned ordinary Emote input receipts to fresh original native effects.

This supplies current measured state, not images, independent publication or a
whole-feature cleanup verdict. It advertises no complete feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.emote_rig_measurements import playback,replacement,restoration,continuation,source as source_group
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.token_emote_ui import snapshot
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_sources import PhoneEmoteSources
from overte_phone_emote_originals import BLOCK
from overte_phone_script_history import same,unpack,canonical

VERSION=2
BACKGROUND_VERSION=1
PLAYS={'play','sit','override'}


class PhoneEmoteEffects:
    def __init__(self,inputs,*,current_source=None):
        need(isinstance(inputs,PhoneEmoteInputs));self.inputs=inputs;self.input_source=inputs.source
        self.source=self.input_source if current_source is None else current_source
        need(isinstance(self.source,PhoneEmoteSources) and self.input_source.role=='primary'
            and self.source.role in ('primary','actor') and (self.source.role=='actor' or self.source is self.input_source)
            and self.source.run==self.input_source.run and self.source.phase.fixture_url==self.input_source.phase.fixture_url
            and same(self.source.admission,self.input_source.admission)
            and same(self.source.binding,self.input_source.binding) and self.source.lock.path==self.input_source.lock.path)
        self.source.lock.assert_held()
        self.historical=False

    @staticmethod
    def stored(source,reference):
        exact(reference,{'revision','sha256'});need(integer(reference['revision'],1,len(source.frames)))
        frame=source.frames[reference['revision']-1]
        need(reference['sha256']==hashlib.sha256(canonical(frame)).hexdigest())
        # Both roles reopen their OWN immutable originals. Primary pre-input
        # barriers are stimulus/correlation only, never this role's effect facts.
        index=reference['revision'];block=(index-1)//BLOCK
        entries=source.originals.manifest(source.state['manifests'][block])
        original=source.originals.read(source.originals.expand(entries[(index-1)%BLOCK]))
        need(same(original,frame));return original

    def original(self,reference):return self.stored(self.input_source,reference)
    def current_original(self,reference):return self.stored(self.source,reference)

    def reference(self):
        need(self.source.frames and self.source.state['phase']=='ready')
        return dict(revision=len(self.source.frames),sha256=hashlib.sha256(canonical(self.source.frames[-1])).hexdigest())

    def bound(self):
        need(self.historical is False)
        self.inputs.bound();self.source.lock.assert_held()
        need(not self.source.failed and self.source.guard() is not False
            and same(self.source.store.read(),self.source.previous) and self.source.state['phase']=='ready'
            and self.source.state['pending'] is None)

    def _archive_context(self,input_header,input_source_header,source_header,*,ready=True):
        """Private read-only views rebuilt from retained original journals."""
        source=self.source;started=source.monotonic();need(number(started,0,1e15) and type(ready) is bool)
        source.lock.assert_held();need(source.guard() is not False)
        def sources(actual,header):
            need(type(header) is dict and header.get('role')==actual.role)
            need(same(header.get('admissionPolicy'),actual.admission))
            state,frames=PhoneEmoteSources.archive(header,phase=actual.phase,artifact_root=actual.artifact_root,
                binding=actual.binding,guard=actual.guard,monotonic=actual.monotonic)
            if ready:need(state['phase']=='ready' and state['pending'] is None)
            view=object.__new__(PhoneEmoteSources);view.__dict__=actual.__dict__.copy()
            view.previous,view.state,view.frames=deepcopy(header),state,frames
            view.historical=True
            return view
        primary=sources(self.input_source,input_source_header)
        if source.role=='primary':
            need(same(input_source_header,source_header));current=primary
        else:current=sources(source,source_header)
        owner=object.__new__(PhoneEmoteInputs);owner.__dict__=self.inputs.__dict__.copy();owner.source=primary
        owner.previous=deepcopy(input_header)
        if input_header is None:
            need(bool(primary.frames))
            for frame in primary.frames:
                for key in ('phaseBefore','phaseAfter'):
                    packet=frame[key];rows=packet['activations']
                    need(packet['active'] and len(rows) in (1,2)
                        and rows[0]['stimulus']==dict(verb='baseline',inputs={})
                        and (len(rows)==1 or rows[1]['stimulus']==dict(verb='cleanup',inputs={})))
            # Historical absence is valid only before any normal fixture action.
            # Baseline -> cleanup owns no ordinary input; a normal action in
            # either original phase forbids borrowing this absent context.
            # This read-only view cannot create or act through a live store.
            owner.state=dict(history=[],current=None);owner.history_state=dict(count=0,manifests=[],pendingArchive=None)
        else:owner.state,owner.history_state=owner.decode(owner.previous)
        need(owner.history_state['pendingArchive'] is None)
        context=PhoneEmoteEffects(owner,current_source=current);context.historical=True
        source.lock.assert_held();need(source.guard() is not False)
        end=source.monotonic();need(number(end,started,1e15) and end-started<5)
        return context

    def panel(self,frame):
        ui=snapshot(frame['ui']);pages=[row for row in ui['controls'] if row['id']=='emote.page']
        need(len(pages)<=1)
        return ui['open'] and ui['ready'] and len(pages)==1

    def after(self,row,reference):
        self.inputs.row(row);need(row['phase']=='acknowledged' and row['before'] is not None)
        frame=self.current_original(reference);before=self.original(row['before'])
        if self.source is self.input_source:need(reference['revision']>row['before']['revision'])
        for phase in ('phaseBefore','phaseAfter'):self.inputs.active(row['call'],frame[phase])
        native=frame['group']['native'];floor=before['group']['native']['capturedEpochMs'];sequence=before['ui']['scope']['sequence']
        for item in row['intents']:
            need(item['after'] is not None)
            after=item['after'] if item['kind']=='qt' else self.original(item['after'])['ui']
            floor=max(floor,after['scope']['capturedEpochMs']);sequence=after['scope']['sequence']
        need(native['requestedEpochMs']>=floor and frame['ui']['scope']['sequence']==sequence
            and frame['ui']['scope']['instance']==before['ui']['scope']['instance']
            and frame['ui']['scope']['generation']==before['ui']['scope']['generation'])
        return frame

    def played(self,row,reference):
        need(row['call']['verb'] in PLAYS);frame=self.after(row,reference)
        intents=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
        need(len(intents)==1);intent=intents[0]
        before=self.original(intent['barrier'])
        reader=replacement if row['call']['verb']=='override' else playback
        proof=reader(frame['group'],before['group']['native'],pid=self.source.pid,epoch=frame['epochMs'])
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

    def restore_play(self,reference,rows=None):
        exact(reference,{'inputTicket','frame'})
        rows=self.inputs.state['history'] if rows is None else rows
        plays=[row for row in rows if row['call']['verb'] in PLAYS]
        need(bool(plays) and reference['inputTicket']==plays[-1]['call']['ticket'])
        return self.played(plays[-1],reference['frame'])

    def pending_restore(self,reference,played):
        """Actual still-playing state after a handled cancel/wait input.

        A consumed input never supplies an inactive native result. This keeps
        ordinary automatic completion observable while its real timer runs.
        """
        row=self.inputs.state['current'];need(row is not None and row['call']['verb'] in ('cancel','wait-complete'))
        frame=self.after(row,reference);original=self.restore_play(played)
        proof=playback(frame['group'],original['barrier'],pid=self.source.pid,epoch=frame['epochMs'])
        need(proof['state']['override'] is True and same(proof['event'],original['event']))
        state=deepcopy(proof['state']);state['panel']=self.panel(frame)
        return dict(emotePendingRestoreVersion=1,role=self.source.role,runId=self.source.run,binding=deepcopy(self.source.binding),
            call=deepcopy(row['call']),frame=deepcopy(reference),played=deepcopy(played),state=state,proof=proof)

    def recompute(self,reference,*,played=None,call=None):
        """Reopen actual originals and derive historical state without queries.

        A supplied call selects its owned original history prefix, not a future
        input's playback. This never asserts current durable ownership/freshness.
        """
        owner,source=self.inputs,self.source
        started=source.monotonic();need(number(started,0,1e15));source.lock.assert_held();need(source.guard() is not False)
        original_state,original_history=owner.decode(owner.previous)
        need(same(original_state,owner.state) and same(original_history,owner.history_state))
        rows=owner.state['history']+([owner.state['current']] if owner.state['current'] is not None else [])
        selected=owner.state['current']['call'] if call is None and owner.state['current'] is not None else call
        need(type(selected) is dict)
        positions=[index for index,row in enumerate(rows) if same(row['call'],selected)]
        need(len(positions)==1);position=positions[0];row=rows[position]
        frame=self.after(row,reference)
        call=row['call'];verb=call['verb'];proof=None;play_reference=deepcopy(played)
        if verb in PLAYS:
            need(played is None);proof=self.played(row,reference)
            state=deepcopy(proof['state']);kind='playback'
            play_reference=dict(inputTicket=call['ticket'],frame=deepcopy(reference))
        elif verb=='cancel' and row['idleReset'] is not None:
            need(not frame['group']['native']['animation']['overrideActive'])
            if played is not None:
                # A completed previous play remains retained for provenance.
                # An ordinary Stop on an already idle chooser neither erases
                # that original nor claims a second active-to-idle transition.
                original=self.restore_play(played,rows[:position])
                proof=restoration(frame['group'],original,pid=source.pid,epoch=frame['epochMs'])
            # No new active-to-inactive ordinary input exists for an idle reset.
            # It cannot satisfy the final early-cancel requirement.
            state=dict(animation='idle',sit='none',override=False,poseProgress=0.,restoredBeforeNominalEnd=False);kind='idle-reset'
        elif played is not None:
            original=self.restore_play(played,rows[:position])
            barrier=None
            if verb=='cancel':
                intents=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
                need(len(intents)==1);barrier=self.original(intents[0]['barrier'])['group']['native']
            else:need(verb in ('wait-complete','open','close'))
            proof=restoration(frame['group'],original,pid=source.pid,epoch=frame['epochMs'],native_barrier=barrier)
            state=deepcopy(proof['state']);kind='restoration'
        else:
            need(verb in ('open','close') and not any(item['call']['verb'] in PLAYS for item in rows[:position])
                and frame['group']['native']['animation']['overrideActive'] is False)
            state=dict(animation='idle',sit='none',override=False,poseProgress=0.,restoredBeforeNominalEnd=False);kind='idle'
        state['panel']=self.panel(frame)
        if verb=='open':need(state['panel'])
        if verb=='close':need(state['panel'] is False and frame['ui']['open'] is False)
        value=dict(emoteEffectVersion=VERSION,role=source.role,runId=source.run,binding=deepcopy(source.binding),call=deepcopy(call),
            frame=deepcopy(reference),playbackReference=play_reference,kind=kind,state=state,proof=proof)
        returned=deepcopy(value);source.lock.assert_held();need(source.guard() is not False)
        end=source.monotonic();need(number(end,started,1e15) and end-started<5);return returned

    def background_context(self,*,previous,header,image_policy):
        """Reopen historical dependencies only; no new-frame effect verdict."""
        from overte_phone_emote_observation import PhoneEmoteObservation
        from overte_phone_emote_background import PhoneEmoteBackground
        source=self.source;started=source.monotonic();need(number(started,0,1e15))
        source.lock.assert_held();need(source.guard() is not False)
        need(type(previous) is dict and type(previous.get('header')) is dict)
        need(previous['header'].get('emoteObservationVersion') in (1,2)
            and type(previous.get('result')) is dict and previous['result'].get('emoteObservationResultVersion')==1)
        prior=PhoneEmoteObservation.archive(previous,self,previous['header'].get('index'),image_policy)
        effect=prior['effect']
        need(prior['role']==source.role and type(effect.get('emoteEffectVersion')) is int
            and effect['emoteEffectVersion']==2 and effect['kind']=='restoration'
            and effect['call']['verb']=='cancel' and effect['state']['override'] is False
            and effect['state']['restoredBeforeNominalEnd'] is True)
        proof=effect['proof'];need(proof['kind']=='restoration' and proof['barrier'] is not None)
        cycle,before,after=PhoneEmoteBackground.completed_archive(header,source);call=cycle['call']
        for key in ('phaseBefore','phaseAfter'):
            rows=before[-1][key]['activations'];need(len(rows)>=2)
            need(rows[-2]['ticket']==effect['call']['ticket']
                and same(rows[-2]['stimulus'],dict(verb='cancel',inputs=effect['call']['inputs'])))
        source.lock.assert_held();need(source.guard() is not False)
        end=source.monotonic();need(number(end,started,1e15) and end-started<5)
        return prior,cycle,before,after

    def background_recompute(self,reference,*,previous,header,image_policy):
        """Current-frame facts joined to this role's original cancel and OS cycle.

        The old ordinary input remains an old input. No background input row,
        synthetic ACK, old measured state or peer fact is adopted as current.
        """
        source=self.source;started=source.monotonic();need(number(started,0,1e15))
        prior,cycle,before,after=self.background_context(previous=previous,header=header,image_policy=image_policy)
        effect=prior['effect'];proof=effect['proof'];call=cycle['call']
        frame=self.current_original(reference)
        for key in ('phaseBefore','phaseAfter'):
            packet=frame[key];self.inputs.active(call,packet)
            phase_packet(packet,run=source.run,area='emotes',request=packet['requestId'],epoch=frame['hostEpochMs'],
                previous=after[-1]['phaseAfter'])
            rows=packet['activations'];need(len(rows)>=2)
            last=rows[-2]
            need(last['ticket']==effect['call']['ticket']
                and same(last['stimulus'],dict(verb='cancel',inputs=effect['call']['inputs'])))
        continuation(proof['group']['native'],before[-1]['group']['native'],source.pid)
        continuation(after[-1]['group']['native'],frame['group']['native'],source.pid)
        need(same(frame['group']['native']['lifecycle'],after[-1]['group']['native']['lifecycle']))
        current=restoration(frame['group'],proof['played'],pid=source.pid,epoch=frame['epochMs'],native_barrier=proof['barrier'])
        animation=frame['group']['native']['animation']
        need(animation['animationsEnabled'] is True and animation['graphLoaded'] is True
            and current['state']['restoredBeforeNominalEnd'] is True)
        state=deepcopy(current['state']);state['panel']=self.panel(frame)
        value=dict(emoteBackgroundEffectVersion=BACKGROUND_VERSION,role=source.role,runId=source.run,binding=deepcopy(source.binding),
            call=deepcopy(call),frame=deepcopy(reference),previousTicket=effect['call']['ticket'],state=state,proof=current)
        source.lock.assert_held();need(source.guard() is not False)
        end=source.monotonic();need(number(end,started,1e15) and end-started<5);return deepcopy(value)

    def measure(self,reference,*,played=None,background=None):
        owner,source=self.inputs,self.source
        started=source.monotonic();need(number(started,0,1e15));self.bound()
        need(source.state['phase']=='ready' and source.state['pending'] is None
            and owner.source.state['phase']=='ready' and owner.source.state['pending'] is None
            and owner.history_state['pendingArchive'] is None and reference==self.reference())
        need(source.previous is not None and owner.previous is not None
            and same(unpack(source.previous['payload']),[source.state])
            and same(unpack(owner.source.previous['payload']),[owner.source.state]))
        native=source.adapter._native_feature_observer(source.selector,read_only=True)
        need(native.pid==source.pid and native.ios is False and native.guard() is not False)
        epoch=native.clock_ms();host=source.phase.epoch_ms();clock=source.monotonic()
        need(integer(epoch,1) and number(host,1,1e15) and number(clock,started,1e15))
        if background is None:
            value=self.recompute(reference,played=played);frame=self.after(owner.state['current'],reference)
        else:
            exact(background,{'previous','header','image_policy'});need(played is None)
            value=self.background_recompute(reference,**background);frame=self.current_original(reference)
        call=value['call']
        # Check durable ownership and actual provider phase again after joins;
        # neither a stale frame nor a slow final guard may publish fresh facts.
        self.bound();status=source.phase.status(frame['phaseAfter']);owner.active(call,status);self.bound()
        delivered=native.clock_ms();delivered_host=source.phase.epoch_ms();self.bound()
        returned=deepcopy(value);need(native.guard() is not False);self.bound();final=source.monotonic()
        need(number(final,clock,1e15) and final-started<5 and integer(delivered,epoch)
            and number(delivered_host,host,1e15))
        barrier=frame['group']['rootsBefore']['requestedEpochMs'];phase=frame['phaseBefore']['capturedEpochMs']
        fresh(barrier,delivered);fresh(phase,delivered_host)
        need(max(delivered-barrier,epoch-barrier+(final-started)*1000)<=1500
            and max(delivered_host-phase,host-phase+(final-started)*1000)<=1500)
        return returned

    def phase_identity(self,packet):
        phase_packet(packet,run=self.source.run,area='emotes',request=packet.get('requestId'),epoch=packet.get('capturedEpochMs'))
        need(packet['active'] and packet['activations']);current=packet['activations'][-1]
        need(current['stimulus']['verb'] in ('baseline','cleanup') and current['stimulus']['inputs']=={})
        if current['stimulus']['verb']=='baseline':need(len(packet['activations'])==1)
        return current['stimulus']['verb'],current['ticket']

    def phase_recompute(self,reference):
        """Historical idle-phase facts without a fabricated ordinary input.

        Early restoration describes a qualified ordinary action, which these
        fixture-only phases do not have. Historical input/restore evidence is
        preserved and is not erased or replaced by this phase projection.
        """
        source=self.source;started=source.monotonic();need(number(started,0,1e15))
        source.lock.assert_held();need(source.guard() is not False)
        frame=self.current_original(reference)
        phase,ticket=self.phase_identity(frame['phaseBefore']);need((phase,ticket)==self.phase_identity(frame['phaseAfter']))
        _selected,native,_urls=source_group(frame['group'],source.pid,frame['epochMs']);animation=native['animation']
        need(animation['animationsEnabled'] is True and animation['graphLoaded'] is True and animation['overrideActive'] is False)
        # These are the defined absent-override values, admitted only by the
        # original native idle observation. Panel remains an actual UI reading.
        state=dict(animation='idle',sit='none',override=animation['overrideActive'],poseProgress=0.,
            restoredBeforeNominalEnd=False,panel=self.panel(frame))
        value=dict(emotePhaseEffectVersion=1,role=source.role,runId=source.run,binding=deepcopy(source.binding),
            phase=phase,ticket=ticket,frame=deepcopy(reference),state=state)
        result=deepcopy(value);source.lock.assert_held();need(source.guard() is not False)
        end=source.monotonic();need(number(end,started,1e15) and end-started<5);return result

    def phase_measure(self,reference):
        """Fresh idle phase observation; no input, image or cleanup verdict."""
        source=self.source;started=source.monotonic();need(number(started,0,1e15));self.bound()
        need(reference==self.reference() and self.input_source.state['phase']=='ready'
            and self.input_source.state['pending'] is None and self.inputs.history_state['pendingArchive'] is None)
        for actual in (source,self.input_source):
            need(actual.previous is not None and actual.state['revision']==len(actual.frames)
                and same(unpack(actual.previous['payload']),[actual.state]))
        reader=source.adapter._native_feature_observer(source.selector,read_only=True)
        need(reader.pid==source.pid and reader.ios is False and reader.guard() is not False)
        epoch,host=reader.clock_ms(),source.phase.epoch_ms();need(integer(epoch,1) and number(host,1,1e15));self.bound()
        value=self.phase_recompute(reference);frame=self.current_original(reference)
        status=source.phase.status(frame['phaseAfter']);need(self.phase_identity(status)==(value['phase'],value['ticket']));self.bound()
        returned=deepcopy(value);need(reader.guard() is not False);self.bound()
        now,host_now=reader.clock_ms(),source.phase.epoch_ms();self.bound();end=source.monotonic()
        need(integer(now,epoch) and number(host_now,host,1e15) and number(end,started,1e15) and end-started<5)
        floor=frame['group']['rootsBefore']['requestedEpochMs'];host_floor=frame['phaseBefore']['capturedEpochMs']
        fresh(floor,now);fresh(host_floor,host_now)
        need(max(now-floor,epoch-floor+(end-started)*1000)<=1500
            and max(host_now-host_floor,host-host_floor+(end-started)*1000)<=1500)
        return returned
