"""Owned current Emote input/Rig/PNG joins, independently acquired per role.

The full run owner still supplies approved scene/Script prerequisites, ordinary
actions, independent authenticated publication and whole-resource retirement.
This scope advertises no complete feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import uuid

from adapters.emote_rig_measurements import continuation
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_phone_avatar_configuration import NativePhoneAvatarConfiguration,controlled,validate as config_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_world_render import OwnedWorldRenderCapture
from feature_journeys.contract import identifier
from overte_phone_emote_capture import PhoneEmoteCapture
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_emote_originals import PhoneEmoteOriginals
from overte_phone_emote_sources import PhoneEmoteSources
from overte_phone_emote_pixels import measure as pixels
from overte_phone_script_history import pack,unpack,same

VERSION=1
HEADER_VERSION=2


class ObservationOriginals(PhoneEmoteOriginals):
    KINDS=frozenset({'observations'})


class PhoneEmoteObservation:
    def __init__(self,effects,index,policy):
        need(isinstance(effects,PhoneEmoteEffects) and effects.historical is False and integer(index,1,256))
        self.effects,self.source,self.index,self.policy=effects,effects.source,index,deepcopy(policy)
        exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        source=self.source;source.lock.assert_held()
        self.store=PrivateFeatureState(source.store.path.with_name('phone-emote-'+source.role+'-observation-'+str(index)+'.json'))
        self.previous=self.store.read();self.failed=False;self.started=self.clock=None
        self.scope_id=self.previous.get('scopeId') if self.previous is not None else uuid.uuid4().hex
        self.historical=False
        self.state=dict(phase='reserved',ticket=None,capture=None,outcome=None,pending=None,retirement=None)
        self.originals=ObservationOriginals(source.artifact_root,source.binding,source.run,source.role,self.bound,
            self.storage_intent,kind='observations',monotonic=source.monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def bound(self):
        source=self.source;source.lock.assert_held()
        need(not self.failed and source.guard() is not False)
        if self.historical:need(same(self.previous,self.archive_header))
        else:need(same(self.store.read(),self.previous))
        now=source.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<5));self.clock=now
        return now

    def decode(self,value):
        source=self.source
        need(type(value) is dict and type(value.get('emoteObservationVersion')) is int and value['emoteObservationVersion'] in (1,2))
        version=value['emoteObservationVersion']
        exact(value,{'emoteObservationVersion','runId','fixtureUrl','role','index','binding','artifactRoot','imagePolicy','payload'}
            |({'scopeId'} if version==2 else set()))
        if version==2:identifier(value['scopeId'])
        need(value.get('scopeId')==self.scope_id
            and value['runId']==source.run and value['fixtureUrl']==source.phase.fixture_url and value['role']==source.role
            and type(value['index']) is int and value['index']==self.index and same(value['binding'],source.binding)
            and value['artifactRoot']==str(source.artifact_root) and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','ticket','capture','outcome','pending','retirement'})
        need(state['phase'] in ('reserved','capturing','captured','measuring','complete')
            or version==2 and state['phase']=='preparing')
        if state['ticket'] is not None:identifier(state['ticket'])
        else:need(state['phase']=='reserved')
        for key,offset in (('capture',1),('outcome',2)):
            if state[key] is not None:
                ref=state[key];self.originals.expand(ref);need(ref['index']==(self.index-1)*2+offset)
                row=self.originals.read(self.originals.expand(ref));self.row(row,key,state['ticket'])
        if state['pending'] is not None:
            pending=state['pending'];exact(pending,{'kind','original'});need(pending['kind'] in ('capture','outcome') and state[pending['kind']] is None)
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==(self.index-1)*2+(1 if pending['kind']=='capture' else 2))
        if state['phase']=='reserved':need(all(state[key] is None for key in state if key!='phase'))
        if state['phase']=='preparing':need(all(state[key] is None for key in ('capture','outcome','pending','retirement')))
        if state['phase'] in ('captured','measuring','complete'):need(state['capture'] is not None)
        if state['retirement'] is not None:
            need(state['capture'] is not None)
            row=self.originals.read(self.originals.expand(state['capture']))
            _frame,_raw,record=PhoneEmoteCapture.archive(row['header'],source,self.index,self.policy)
            need(same(state['retirement'],dict(emoteCaptureCleanupVersion=1,completeImageRecord=True,
                retirement=record['retirement'],retainedPartialImage=False)))
        if state['phase']=='complete':need(state['outcome'] is not None and state['pending'] is None and state['retirement'] is not None)
        return deepcopy(state)

    def row(self,row,kind,ticket):
        need(kind in ('capture','outcome'))
        if kind=='capture':
            exact(row,{'emoteObservationFrameVersion','kind','ticket','before','header','played','previous'})
            frame,_raw,_state=PhoneEmoteCapture.archive(row['header'],self.source,self.index,self.policy)
            need(row['header'].get('parentScope')==self.scope_id)
            need(frame['ticket']==ticket)
            self.effects.current_original(row['before'])
            if row['played'] is not None:exact(row['played'],{'inputTicket','frame'});identifier(row['played']['inputTicket'])
            if row['previous'] is not None:
                exact(row['previous'],{'index','capture'})
                need(integer(row['previous']['index'],1,self.index-1))
                self.originals.expand(row['previous']['capture'])
                need(row['previous']['capture']['index']==(row['previous']['index']-1)*2+1)
        else:
            exact(row,{'emoteObservationFrameVersion','kind','ticket','after','configuration','effect','pixels'})
            frame=self.effects.current_original(row['after']);need(frame['phaseAfter']['activations'][-1]['ticket']==ticket)
            value=row['configuration'];config_packet(value,dict(schemaVersion=1,commandId=value.get('requestId'),
                action='phone-avatar-configuration-observe'),self.source.pid,value.get('capturedEpochMs'))
            effect=row['effect'];need(effect['emoteEffectVersion']==2 and effect['role']==self.source.role
                and effect['runId']==self.source.run and same(effect['binding'],self.source.binding)
                and same(effect['frame'],row['after']) and effect['call']['ticket']==ticket)
            need(row['pixels']['emotePixelsVersion']==1 and row['pixels']['ticket']==ticket)
        need(type(row['emoteObservationFrameVersion']) is int and row['emoteObservationFrameVersion']==VERSION
            and row['kind']==kind and row['ticket']==ticket)

    def save(self):
        need(self.historical is False)
        self.bound()
        value=dict(emoteObservationVersion=HEADER_VERSION if self.scope_id is not None else 1,runId=self.source.run,fixtureUrl=self.source.phase.fixture_url,
            role=self.source.role,index=self.index,binding=deepcopy(self.source.binding),artifactRoot=str(self.source.artifact_root),
            imagePolicy=deepcopy(self.policy),payload=pack([self.state]))
        if self.scope_id is not None:value['scopeId']=self.scope_id
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def storage_intent(self,kind,value):
        need(kind=='original' and self.state['pending'] is not None)
        pending=self.state['pending'];old=pending['original'];self.originals.original(value)
        need(value['index']==(self.index-1)*2+(1 if pending['kind']=='capture' else 2))
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
            and (old['phase']=='planned' or same(old['file'],value['file'])))
        pending['original']=deepcopy(value);self.save()

    def record(self,kind,row):
        need(self.state[kind] is None and self.state['pending'] is None);self.row(row,kind,self.state['ticket'])
        self.state['pending']=dict(kind=kind,original=None);self.save()
        reference=self.originals.write((self.index-1)*2+(1 if kind=='capture' else 2),row)
        self.state[kind]=reference;self.state['pending']=None;self.save()

    def load(self,kind):
        ref=self.state[kind];need(ref is not None)
        row=self.originals.read(self.originals.expand(ref));self.row(row,kind,self.state['ticket']);return row

    def previous_image(self,reference):
        if reference is None:return None
        row=self.originals.read(self.originals.expand(reference['capture']))
        need(row['kind']=='capture' and row['emoteObservationFrameVersion']==VERSION)
        frame,raw,_record=PhoneEmoteCapture.archive(row['header'],self.source,reference['index'],self.policy)
        need(frame['ticket']!=self.state['ticket'])
        return dict(frame=frame,png=raw)

    def join(self,captured,outcome):
        before=self.effects.current_original(captured['before']);after=self.effects.current_original(outcome['after'])
        native_before,native_after=before['group']['native'],after['group']['native']
        continuation(native_before,native_after,self.source.pid)
        image,raw,_record=PhoneEmoteCapture.archive(captured['header'],self.source,self.index,self.policy)
        need(native_before['capturedEpochMs']<=image['avatarBefore']['requestedEpochMs']
            and image['avatarAfter']['capturedEpochMs']<=after['group']['rootsBefore']['requestedEpochMs']
            and native_before['instance']==image['capture']['instance']==native_after['instance']
            and native_before['animation']['rigId']==image['avatarBefore']['source']['rigId']==native_after['animation']['rigId']
            and same(native_before['lifecycle'],native_after['lifecycle']))
        a,b=native_before['animation'],native_after['animation']
        need(a['overrideActive']==b['overrideActive']==outcome['effect']['state']['override']
            and all(a['history'][key]==b['history'][key] for key in ('instance','callSequence','overrideSequence')))
        if a['overrideActive']:
            need('clip' in a and 'clip' in b and a['clip']['loadedFrames']>0 and b['clip']['loadedFrames']>0
                and all(same(a['clip'][key],b['clip'][key]) for key in ('url','requestedUrl','firstFrame','lastFrame','framesPerSecond','loop','loadedFrames'))
                and a['clip']['evaluatedEpochMs']<=image['capture']['source']['renderTrace']['recordedEpochMs'])
            if 'animationSourceVersion' in a['clip'] or 'animationSourceVersion' in b['clip']:
                need(a['clip'].get('animationSourceVersion')==b['clip'].get('animationSourceVersion')==1
                    and a['clip'].get('assetSource') is not None and same(a['clip']['assetSource'],b['clip'].get('assetSource')))
        configuration=outcome['configuration']
        need(configuration['requestedEpochMs']>=native_after['capturedEpochMs'])
        controlled(configuration,image['avatarBefore']);controlled(configuration,image['avatarAfter'])
        need(outcome['pixels']['imageSha256']==image['capture']['source']['image']['sha256'])
        return image,raw,before,after

    def read(self,ticket,*,played=None,previous=None):
        """One new acquisition only; interruptions never replay this scope."""
        identifier(ticket);need(self.historical is False and self.previous is None and self.state['phase']=='reserved')
        self.started=self.bound();epoch_reader=self.source.adapter._native_feature_observer(self.source.selector,read_only=True)
        epoch=epoch_reader.clock_ms();host=self.source.phase.epoch_ms();need(integer(epoch,1) and number(host,1,1e15))
        try:
            self.effects.bound();self.state.update(phase='preparing',ticket=ticket);self.save()
            self.source.read();before=self.effects.reference()
            row=self.effects.inputs.state['current'];need(row is not None and row['call']['ticket']==ticket)
            self.effects.after(row,before)
            previous_ref=None
            if previous is not None:
                if isinstance(previous,PhoneEmoteObservation):
                    need(previous.index<self.index and previous.source.role==self.source.role and previous.source.run==self.source.run
                        and same(previous.source.binding,self.source.binding) and same(previous.policy,self.policy)
                        and previous.source.artifact_root==self.source.artifact_root)
                    previous.original();previous_ref=dict(index=previous.index,capture=deepcopy(previous.state['capture']))
                else:
                    need(type(previous) is dict and type(previous.get('header')) is dict)
                    index=previous['header'].get('index');need(integer(index,1,self.index-1))
                    original=self.archive(previous,self.effects,index,self.policy)
                    previous_ref=dict(index=index,capture=deepcopy(original['capture']))
            self.state['phase']='capturing';self.save()
            capture=PhoneEmoteCapture(self.source,self.index,self.policy,monotonic=self.source.monotonic,parent_scope=self.scope_id)
            capture.read(ticket);capture.original()
            captured=dict(emoteObservationFrameVersion=VERSION,kind='capture',ticket=ticket,before=before,
                header=deepcopy(capture.previous),played=deepcopy(played),previous=previous_ref)
            # The parent's immutable original is committed before child removal
            # or any source-header advancement. A lost cleanup return retains it.
            self.record('capture',captured);self.state['phase']='captured';self.save()
            self.state['retirement']=capture.cleanup();self.state['phase']='measuring';self.save()
            self.source.read();reference=self.effects.reference()
            effect=self.effects.measure(reference,played=played)
            configuration=self.source.adapter._avatar_configuration_observer(self.source.selector,read_only=True)
            need(isinstance(configuration,NativePhoneAvatarConfiguration) and configuration.pid==self.source.pid and configuration.ios is False)
            config=configuration.read()
            image,raw,_record=PhoneEmoteCapture.archive(captured['header'],self.source,self.index,self.policy)
            measured=pixels(self.source.run,image,raw,self.policy,self.source.pid,configuration.clock_ms,self.source.guard,
                previous=self.previous_image(previous_ref),monotonic=self.source.monotonic)
            outcome=dict(emoteObservationFrameVersion=VERSION,kind='outcome',ticket=ticket,after=reference,
                configuration=config,effect=effect,pixels=measured)
            self.join(captured,outcome);self.record('outcome',outcome);self.state['phase']='complete';self.save()
            result=self.original();self.delivery(result,epoch_reader,epoch,host);return result
        finally:self.started=None

    def original(self):
        """Historical originals only; reopening does not refresh an observation."""
        outer=self.started is None
        if outer:self.started=self.bound()
        try:return self._original()
        finally:
            if outer:self.started=None

    def _original(self):
        self.bound();need(self.previous is not None and same(self.decode(self.previous),self.state) and self.state['phase']=='complete')
        captured,outcome,measured=self._facts()
        value=dict(emoteObservationResultVersion=VERSION,role=self.source.role,index=self.index,runId=self.source.run,
            binding=deepcopy(self.source.binding),ticket=self.state['ticket'],state=deepcopy(outcome['effect']['state']),
            effect=deepcopy(outcome['effect']),pixels=measured,image=deepcopy(captured['header']),
            capture=deepcopy(self.state['capture']),outcome=deepcopy(self.state['outcome']))
        result=deepcopy(value);self.bound();return result

    def _facts(self):
        """Replay saved facts without changing or promoting the durable phase."""
        captured,outcome=self.load('capture'),self.load('outcome');image,raw,_before,_after=self.join(captured,outcome)
        effect=self.effects.recompute(outcome['after'],played=captured['played'],call=outcome['effect']['call'])
        need(same(effect,outcome['effect']))
        # Recompute pixel facts from retained original PNGs, including prior
        # role-local pixels. Stored statistics never replace measured bytes.
        measured=pixels(self.source.run,image,raw,self.policy,self.source.pid,lambda:outcome['configuration']['capturedEpochMs'],
            self.source.guard,previous=self.previous_image(captured['previous']),monotonic=self.source.monotonic)
        need(same(measured,outcome['pixels']))
        self.bound();return captured,outcome,measured

    def delivery(self,value,reader,epoch,host):
        self.effects.bound();need(reader.guard() is not False)
        captured,outcome=self.load('capture'),self.load('outcome');_image,_raw,before,_after=self.join(captured,outcome)
        phase=self.source.phase.status(_after['phaseAfter']);self.effects.inputs.active(outcome['effect']['call'],phase)
        need(value['ticket']==self.state['ticket']);self.bound()
        now=reader.clock_ms();host_now=self.source.phase.epoch_ms();self.bound();end=self.source.monotonic()
        need(integer(now,epoch) and number(host_now,host,1e15) and number(end,self.started,1e15) and end-self.started<5)
        floor=max(now,epoch+math.ceil((end-self.started)*1000));host_floor=max(host_now,host+math.ceil((end-self.started)*1000))
        fresh(before['group']['rootsBefore']['requestedEpochMs'],floor);fresh(before['phaseBefore']['capturedEpochMs'],host_floor)

    def retire(self,retain):
        """Retain exact completed original proof before removing this scope."""
        need(self.historical is False and callable(retain));self.started=self.bound()
        try:
            value=self.original();need(self.state['pending'] is None)
            child=PrivateFeatureState(self.source.store.path.with_name('phone-emote-'+self.source.role+'-capture-'+str(self.index)+'.json'))
            need(child.read() is None and self.state['retirement'] is not None)
            need(retain(deepcopy(value)) is not False);self.bound();need(child.read() is None);self.bound()
            self.store.discard(self.previous);need(self.store.read() is None)
            self.source.lock.assert_held();need(self.source.guard() is not False)
            end=self.source.monotonic();need(number(end,self.started,1e15) and end-self.started<5)
            return value
        finally:self.started=None

    @classmethod
    def archive(cls,value,effects,index,policy):
        """Rebuild historical observations after all live journals advanced.

        Replays exact retained contexts and immutable files. No fake live store,
        target getter, fixture query, acquisition or fresh verdict is involved.
        """
        need(isinstance(effects,PhoneEmoteEffects) and integer(index,1,256));source=effects.source
        started=source.monotonic();need(number(started,0,1e15));source.lock.assert_held();need(source.guard() is not False)
        exact(value,{'emoteObservationArchiveVersion','header','inputHeader','inputSourceHeader','sourceHeader','result'})
        need(type(value['emoteObservationArchiveVersion']) is int and value['emoteObservationArchiveVersion']==1)
        context=effects._archive_context(value['inputHeader'],value['inputSourceHeader'],value['sourceHeader'])
        scope=object.__new__(cls);scope.effects,scope.source,scope.index,scope.policy=context,context.source,index,deepcopy(policy)
        exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        scope.historical=True;scope.failed=False;scope.started=started;scope.clock=None
        scope.previous=deepcopy(value['header']);scope.archive_header=deepcopy(scope.previous)
        scope.scope_id=scope.previous.get('scopeId')
        scope.originals=ObservationOriginals(source.artifact_root,source.binding,source.run,source.role,scope.bound,
            lambda *_:need(False),kind='observations',monotonic=source.monotonic)
        scope.bound();scope.state=scope.decode(scope.previous);result=scope.original();need(same(result,value['result']))
        returned=deepcopy(result);scope.bound();return returned

    def transfer(self,retain):
        """Retain a complete replay context before removing scope metadata."""
        need(self.historical is False and callable(retain) and self.started is None)
        self.started=self.source.monotonic();need(number(self.started,0,1e15))
        try:
            self.bound()
            self.effects.bound();result=self.original();source=self.source;inputs=self.effects.inputs
            value=dict(emoteObservationArchiveVersion=1,header=deepcopy(self.previous),inputHeader=deepcopy(inputs.previous),
                inputSourceHeader=deepcopy(inputs.source.previous),sourceHeader=deepcopy(source.previous),result=result)
            self.archive(value,self.effects,self.index,self.policy);self.bound();self.effects.bound()
            child=PrivateFeatureState(source.store.path.with_name('phone-emote-'+source.role+'-capture-'+str(self.index)+'.json'))
            need(child.read() is None and self.state['retirement'] is not None)
            need(retain(deepcopy(value)) is not False);self.bound();self.effects.bound()
            self.archive(value,self.effects,self.index,self.policy);self.bound();self.effects.bound();need(child.read() is None)
            returned=deepcopy(value);self.bound();self.store.discard(self.previous);need(self.store.read() is None)
            source.lock.assert_held();need(source.guard() is not False)
            end=source.monotonic();need(number(end,self.started,1e15) and end-self.started<5);return returned
        finally:self.started=None

    @classmethod
    def incomplete_archive(cls,value,effects,index,policy):
        """Reopen an incomplete parent's retained originals; never a result."""
        need(isinstance(effects,PhoneEmoteEffects) and integer(index,1,256));source=effects.source
        started=source.monotonic();need(number(started,0,1e15));source.lock.assert_held();need(source.guard() is not False)
        exact(value,{'emoteObservationIncompleteArchiveVersion','header','inputHeader','inputSourceHeader','sourceHeader'})
        need(type(value['emoteObservationIncompleteArchiveVersion']) is int and value['emoteObservationIncompleteArchiveVersion']==1)
        context=effects._archive_context(value['inputHeader'],value['inputSourceHeader'],value['sourceHeader'],ready=False)
        scope=object.__new__(cls);scope.effects,scope.source,scope.index,scope.policy=context,context.source,index,deepcopy(policy)
        exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        scope.historical=True;scope.failed=False;scope.started=started;scope.clock=None
        scope.previous=deepcopy(value['header']);scope.archive_header=deepcopy(scope.previous)
        scope.scope_id=scope.previous.get('scopeId')
        scope.originals=ObservationOriginals(source.artifact_root,source.binding,source.run,source.role,scope.bound,
            lambda *_:need(False),kind='observations',monotonic=source.monotonic)
        scope.bound();scope.state=scope.decode(scope.previous)
        need(scope.state['phase'] in ('captured','measuring') and scope.state['pending'] is None
            and scope.state['capture'] is not None and scope.state['retirement'] is not None)
        scope.load('capture')
        if scope.state['outcome'] is not None:scope._facts()
        returned=deepcopy(value);scope.bound();return returned

    def transfer_incomplete(self,retain):
        """Transfer only a saved image parent's responsibility, preserving failure.

        Earlier acquisitions and partial parent files remain unresolved. This
        path issues no input, image or new native observation and cannot replace
        whole-run current quiet/resource cleanup.
        """
        need(self.historical is False and callable(retain) and self.started is None)
        self.started=self.source.monotonic();need(number(self.started,0,1e15))
        try:
            self.bound();need(self.previous is not None and same(self.decode(self.previous),self.state)
                and self.state['phase'] in ('captured','measuring') and self.state['pending'] is None
                and self.state['capture'] is not None)
            captured=self.load('capture');_frame,_raw,record=PhoneEmoteCapture.archive(captured['header'],self.source,self.index,self.policy)
            expected=dict(emoteCaptureCleanupVersion=1,completeImageRecord=True,
                retirement=deepcopy(record['retirement']),retainedPartialImage=False)
            need(expected['retirement'] is not None)
            source=self.source;inputs=self.effects.inputs;inputs.bound()
            need(source.guard() is not False and same(source.store.read(),source.previous))
            owned=source.adapter._world_render_capture(source.selector,read_only=True,role=source.role,require_frame_view=True)
            need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,source.binding)
                and owned.owner.role==source.role and owned.owner.store.read() is None)
            child=PrivateFeatureState(source.store.path.with_name('phone-emote-'+source.role+'-capture-'+str(self.index)+'.json'))
            if child.read() is not None:
                need(same(child.read(),captured['header']))
                capture=PhoneEmoteCapture(source,self.index,self.policy,monotonic=source.monotonic,parent_scope=self.scope_id)
                need(same(capture.cleanup(),expected))
            need(child.read() is None and owned.owner.store.read() is None);self.bound()
            if self.state['retirement'] is None:
                # The immutable complete child already contains the original
                # independently observed buffer/receipt retirement. Absence of
                # a child file alone could never supply this proof.
                self.state['retirement']=deepcopy(expected);self.save()
            else:need(same(self.state['retirement'],expected))
            value=dict(emoteObservationIncompleteArchiveVersion=1,header=deepcopy(self.previous),inputHeader=deepcopy(inputs.previous),
                inputSourceHeader=deepcopy(inputs.source.previous),sourceHeader=deepcopy(source.previous))
            self.incomplete_archive(value,self.effects,self.index,self.policy);self.bound();inputs.bound()
            need(retain(deepcopy(value)) is not False);self.bound();inputs.bound()
            need(same(source.store.read(),source.previous) and same(source.previous,value['sourceHeader'])
                and same(inputs.previous,value['inputHeader']) and same(inputs.source.previous,value['inputSourceHeader']))
            self.incomplete_archive(value,self.effects,self.index,self.policy);self.bound();inputs.bound()
            need(child.read() is None and owned.owner.store.read() is None)
            returned=deepcopy(value);self.bound();self.store.discard(self.previous);need(self.store.read() is None)
            source.lock.assert_held();need(source.guard() is not False)
            end=source.monotonic();need(number(end,self.started,1e15) and end-self.started<5);return returned
        finally:self.started=None

    def pending_diagnostic(self):
        pending=self.state['pending']
        if pending is None or pending['original'] is None:return None
        value=pending['original'];result=self.originals.diagnostic(value)
        if value['phase']=='saved':self.row(self.originals.read(value),pending['kind'],self.state['ticket'])
        return result

    @classmethod
    def failure_archive(cls,value,effects,index,policy):
        """Original failed child and partial-parent evidence, never a result."""
        need(isinstance(effects,PhoneEmoteEffects) and integer(index,1,256));source=effects.source
        started=source.monotonic();need(number(started,0,1e15));source.lock.assert_held();need(source.guard() is not False)
        exact(value,{'emoteObservationFailureArchiveVersion','header','inputHeader','inputSourceHeader','sourceHeader',
            'childRetirement','pendingDiagnostic'})
        need(type(value['emoteObservationFailureArchiveVersion']) is int and value['emoteObservationFailureArchiveVersion']==1)
        context=effects._archive_context(value['inputHeader'],value['inputSourceHeader'],value['sourceHeader'],ready=False)
        scope=object.__new__(cls);scope.effects,scope.source,scope.index,scope.policy=context,context.source,index,deepcopy(policy)
        exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        scope.historical=True;scope.failed=False;scope.started=started;scope.clock=None
        scope.previous=deepcopy(value['header']);scope.archive_header=deepcopy(scope.previous)
        scope.scope_id=scope.previous.get('scopeId')
        scope.originals=ObservationOriginals(source.artifact_root,source.binding,source.run,source.role,scope.bound,
            lambda *_:need(False),kind='observations',monotonic=source.monotonic)
        scope.bound();scope.state=scope.decode(scope.previous);need(scope.state['phase'] in ('preparing','capturing','captured','measuring'))
        need(scope.scope_id is not None);child=value['childRetirement']
        if scope.state['phase']=='preparing':
            need(child is None and scope.effects.inputs.state['current'] is not None
                and scope.effects.inputs.state['current']['call']['ticket']==scope.state['ticket'])
        else:
            PhoneEmoteCapture.retirement_archive(child,scope.source,index,scope.policy)
            need(child['header'].get('parentScope')==scope.scope_id)
            if scope.state['phase']=='capturing':need(same(child['sourceHeader'],value['sourceHeader']))
            child_state=unpack(child['header']['payload'])[0]
            if child_state['providerBefore'] is not None:
                need(child_state['providerBefore']['activations'][-1]['ticket']==scope.state['ticket'])
            _state,frames=PhoneEmoteSources.archive(child['sourceHeader'],phase=source.phase,artifact_root=source.artifact_root,
                binding=source.binding,guard=source.guard,monotonic=source.monotonic)
            need(same(scope.source.frames[:len(frames)],frames))
            if scope.state['capture'] is not None:need(same(scope.load('capture')['header'],child['header']))
            if scope.state['retirement'] is not None:need(same(scope.state['retirement'],child['cleanup']))
            if scope.state['outcome'] is not None:scope._facts()
        need(same(scope.pending_diagnostic(),value['pendingDiagnostic']))
        returned=deepcopy(value);scope.bound();return returned

    def failure_context(self,value):
        """The callback cannot replace or advance any live parent authority."""
        exact(value,{'emoteObservationFailureArchiveVersion','header','inputHeader','inputSourceHeader','sourceHeader',
            'childRetirement','pendingDiagnostic'})
        self.bound();inputs=self.effects.inputs;inputs.bound();source=self.source
        need(same(self.previous,value['header']) and same(inputs.previous,value['inputHeader'])
            and same(inputs.source.previous,value['inputSourceHeader']) and same(source.previous,value['sourceHeader'])
            and same(source.store.read(),source.previous));self.bound()

    def transfer_failed(self,retain,*,retained=None):
        """Transfer failed child/partial originals before either metadata deletion.

        A retained packet from the full owner's durable callback is required
        after a lost child deletion return. Missing child metadata is never
        adopted as proof of an early/not-dispatched acquisition.
        """
        need(self.historical is False and callable(retain) and self.started is None)
        self.started=self.source.monotonic();need(number(self.started,0,1e15))
        try:
            self.bound();need(self.previous is not None and same(self.decode(self.previous),self.state)
                and self.state['phase'] in ('preparing','capturing','captured','measuring'))
            source=self.source;inputs=self.effects.inputs;inputs.bound()
            need(source.guard() is not False and same(source.store.read(),source.previous))
            child=PrivateFeatureState(source.store.path.with_name('phone-emote-'+source.role+'-capture-'+str(self.index)+'.json'))
            owned=source.adapter._world_render_capture(source.selector,read_only=True,role=source.role,require_frame_view=True)
            need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,source.binding) and owned.owner.role==source.role)
            if retained is not None:
                self.failure_context(retained);self.failure_archive(retained,self.effects,self.index,self.policy)
                need(owned.owner.store.read() is None)
            packets=[]
            def hold(proof):
                self.bound();inputs.bound()
                value=dict(emoteObservationFailureArchiveVersion=1,header=deepcopy(self.previous),inputHeader=deepcopy(inputs.previous),
                    inputSourceHeader=deepcopy(inputs.source.previous),sourceHeader=deepcopy(source.previous),
                    childRetirement=deepcopy(proof),pendingDiagnostic=self.pending_diagnostic())
                if retained is not None:need(same(retained,value))
                self.failure_context(value);self.failure_archive(value,self.effects,self.index,self.policy)
                need(retain(deepcopy(value)) is not False);self.failure_context(value)
                self.failure_archive(value,self.effects,self.index,self.policy);self.bound();packets.append(value)
            if self.state['phase']=='preparing':
                need(child.read() is None and owned.owner.store.read() is None);hold(None)
            elif child.read() is not None:
                if retained is not None:need(same(child.read(),retained['childRetirement']['header']))
                capture=PhoneEmoteCapture(source,self.index,self.policy,monotonic=source.monotonic,parent_scope=self.scope_id)
                capture.cleanup(retain=hold)
            else:
                need(retained is not None);hold(retained['childRetirement'])
            need(len(packets)==1 and child.read() is None and owned.owner.store.read() is None)
            value=packets[0];self.failure_context(value);self.failure_archive(value,self.effects,self.index,self.policy)
            need(child.read() is None and owned.owner.store.read() is None)
            returned=deepcopy(value);self.bound();self.store.discard(self.previous);need(self.store.read() is None)
            source.lock.assert_held();need(source.guard() is not False)
            end=source.monotonic();need(number(end,self.started,1e15) and end-self.started<5);return returned
        finally:self.started=None
