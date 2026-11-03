"""Private normal Emote cycle joined to an original second-client stereo PNG.

This is draw/PNG ownership, not clip recognition, marker/pixel qualification or
an independent worker/whole Actor verdict. The local Capture1 stays separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path

from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact, fresh, integer, need, number
from adapters.native_fd_owner import require_directory
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner
from adapters.graphics_journey.originals import record as image_record
from adapters.pico4.avatar_remote import remote_draws
from adapters.pico4.avatar_remote_source import PicoRemoteAvatarSource
from adapters.pico4.emote_capture import PicoEmoteCapture, FIELDS
from adapters.pico4.emote_model_draws import PicoWorldModelDraws, validate as draw_packet, command as draw_command, ACTION
from adapters.pico4.emote_native_cycle import PicoEmoteNativeCycle
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical, same, pack, unpack
from adapters.world_render_evidence import original_pixels, validate as capture_packet
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet

VERSION = 2
REMOTE_FIELDS = FIELDS | {'primary', 'cycleAfter', 'failure', 'modelRequest'}
UNRESOLVED_HOST_FILES = []


@contextmanager
def held(parent, primary, viewer):
    """Take the actual two target locks in one order, outside normal actions."""
    need(isinstance(parent,PicoEmoteNativeCycle) and isinstance(primary,PicoRemoteAvatarSource)
         and isinstance(viewer,PicoRemoteAvatarSource) and primary.lock is parent.source.lock
         and primary.lock.path != viewer.lock.path)
    locks=sorted((primary.lock,viewer.lock),key=lambda value:str(value.path))
    need(all(lock._owner is None for lock in locks))
    with ExitStack() as stack:
        for lock in locks: stack.enter_context(lock.held())
        yield


class PicoEmoteRemoteCapture(PicoEmoteCapture):
    """One Capture2 transaction using the unchanged NativeCycle1 Parent."""
    def __init__(self,parent,primary,viewer,index,world,models):
        need(isinstance(parent,PicoEmoteNativeCycle) and isinstance(primary,PicoRemoteAvatarSource)
             and isinstance(viewer,PicoRemoteAvatarSource) and integer(index,1,32)
             and callable(world) and callable(models))
        self.parent,self.primary,self.source=parent,primary,viewer
        self.lock,self.monotonic=viewer.lock,parent.source.monotonic
        self.world,self.models=world,models
        self.binding,self.pid=deepcopy(viewer.binding),viewer.pid
        self.run,self.role,self.root,self.index=parent.source.run,'actor',Path(parent.source.artifact_root),index
        need(primary.lock is parent.source.lock and primary.lock.path != viewer.lock.path
             and same(primary.binding,parent.source.binding) and primary.run == viewer.run == self.run
             and primary.phase.area == viewer.phase.area == 'emotes'
             and primary.phase.fixture_url == viewer.phase.fixture_url == parent.source.phase.fixture_url
             and primary.identity['picoRemoteAvatarSourceVersion'] == viewer.identity['picoRemoteAvatarSourceVersion'] == 3
             and primary.identity['producerHostProcessIdentity'] == viewer.identity['producerHostProcessIdentity']
             == parent.identity['parentHostProcessIdentity'] == host_identity()
             and primary.binding['targetFingerprint'] != viewer.binding['targetFingerprint']
             and viewer.primary is not None and viewer.identity['primarySha256']==hashlib.sha256(canonical(viewer.primary)).hexdigest())
        # Generic binding.sessionId is the actual QML bridge, not an Avatar UUID.
        # Only the independently retained Native client original supplies these.
        origin=viewer.primary['source']
        self.avatar_sessions=dict(primary=origin['selfSessionId'],viewer=origin['subjectSessionId'])
        need(primary.subject==self.avatar_sessions['viewer'] and viewer.subject==self.avatar_sessions['primary'])
        self.identity=dict(picoEmoteCaptureVersion=VERSION,mode='remote-avatar',runId=self.run,
            fixtureUrl=viewer.phase.fixture_url,index=index,binding=self.binding,artifactRoot=str(self.root),
            parentIdentity=deepcopy(parent.identity),primaryIdentity=deepcopy(primary.identity),viewerIdentity=deepcopy(viewer.identity),
            avatarSessions=deepcopy(self.avatar_sessions))
        key=hashlib.sha256(canonical(self.binding)).hexdigest()[:16]
        self.store=PrivateFeatureState(parent.store.path.with_name(parent.store.path.name+'.child-remote-capture-'+key+'-'+str(index)+'.json'))
        self.previous=None;self.failed=False;self.started=self.clock=None;self.recovering=False
        self.state={key:None for key in REMOTE_FIELDS};self.state['phase']='ready'
        self.parent_prefix=None;self.guard=self.bound
        self.file=object.__new__(LifecycleProcessFile)
        try:
            self.locks()
            need(not any(value.store.path==self.store.path for value in UNRESOLVED_HOST_FILES))
            self.store._parent()
            with os.scandir(self.store.path.parent) as entries:
                for count,entry in enumerate(entries):
                    need(count<4096 and not entry.name.startswith(self.store.path.name+'.pending-'))
            LifecycleProcessFile.__init__(self.file,self.store)
            self.previous=self.store.read()
            if self.previous is not None:
                exact(self.previous,set(self.identity)|{'parentPrefix','payload'})
                need(all(same(self.previous[k],v) for k,v in self.identity.items()))
                self.parent_prefix=deepcopy(self.previous['parentPrefix'])
                values=unpack(self.previous['payload']);need(len(values)==1);self.state=values[0]
                self.recovering=self.state['phase'] in ('reading','failed')
            else:
                self.parent_prefix=deepcopy(parent.previous)
                need(parent.state is not None and parent.state['phase']=='ready' and len(parent.state['steps'])==2)
            self.bound()
            original=PicoRemoteAvatarSource.archive(primary.store,primary.phase,guard=self.candidate,monotonic=self.monotonic)
            need(any(same(packet,viewer.primary) for packet in original['packets']))
            self.decode();self.recovering=False
        except BaseException:
            self.failed=True
            if hasattr(self.file,'parent') and not self.file.close_host():UNRESOLVED_HOST_FILES.append(self.file)
            raise

    def locks(self):
        self.parent.source.lock.assert_held();self.lock.assert_held()

    def candidate(self):
        self.locks();need(not self.failed);self.parent.bound()
        self.file.guard();require_directory(self.file.parent,self.store.path.parent)
        need(same(self.store.read(),self.previous))
        if self.parent_prefix is not None:
            old=self.parent_prefix;now=self.parent.previous
            need(type(old) is dict and all(same(old[k],now[k]) for k in self.parent.identity))
            for key in ('started','epochMs','hostEpochMs','baseline'):need(same(old['state'][key],now['state'][key]))
            need(len(old['state']['steps'])==2 and same(old['state']['steps'],now['state']['steps'][:2])
                 and old['state']['steps'][1]['call']['verb']=='play' and old['state']['steps'][1]['frame'] is not None)
        return True

    def bound(self):
        self.candidate()
        for source in (self.primary,self.source):
            if self.recovering:
                source.file.guard();source.chunks.verify();need(same(source.store.read(),source.previous))
                need(source.original_guard() is not False)
            else:source.guard()
        now=self.monotonic();need(number(now,0 if self.clock is None else self.clock,1e15)
            and (self.started is None or now-self.started<5));self.clock=now;return now

    def phase_ticket(self,value):
        phase_packet(value,run=self.run,area='emotes',request=value.get('requestId'),epoch=value.get('capturedEpochMs'))
        original=self.parent.effects.current_original(self.parent_prefix['state']['steps'][1]['frame'])['phaseAfter']
        need(value['active'] and value['activations'] and value['instance']==original['instance'])
        return value['activations'][-1]['ticket']

    def source_original(self,source,packet,ticket):
        """Reopen actual immutable source bytes, not a mutable returned DTO."""
        archive=PicoRemoteAvatarSource.archive(source.store,source.phase,guard=self.candidate,monotonic=self.monotonic)
        header=archive['header'];need(all(same(header[k],v) for k,v in source.identity.items()))
        role='primary' if source is self.primary else 'viewer'
        need(packet['source']['selfSessionId']==self.avatar_sessions[role]
            and packet['source']['subjectSessionId']==self.avatar_sessions['viewer' if role=='primary' else 'primary'])
        matches=[i for i,value in enumerate(archive['packets']) if value['requestId']==packet['requestId']]
        need(len(matches)==1 and same(archive['packets'][matches[0]],packet))
        rows=ChatSourceChunks(source.store,source.identity).load(header['chunks']);record=header['records'][matches[0]]
        for key in ('before','after'):
            row=rows[record[key]];exact(row,{'kind','value'});need(row['kind']=='phase' and self.phase_ticket(row['value'])==ticket)
        self.candidate();return packet

    def decode(self):
        state=self.state;exact(state,REMOTE_FIELDS);need(state['phase'] in ('ready','reading','failed','complete','cycle-complete'))
        need(state['failure']==('acquisition-refused' if state['phase']=='failed' else None))
        ticket=self.parent_prefix['state']['steps'][1]['call']['ticket']
        for key in ('providerBefore','providerAfter'):
            if state[key] is not None:need(self.phase_ticket(state[key])==ticket)
        if state['primary'] is not None:self.source_original(self.primary,state['primary'],ticket)
        for key in ('avatarBefore','avatarAfter'):
            if state[key] is not None:self.source_original(self.source,state[key],ticket)
        if state['captureIntent'] is not None:WorldRenderOwner.acquisition(state['captureIntent'])
        if state['capture'] is not None:
            packet=state['capture'];capture_packet(packet,packet['requestId'],self.pid,packet['capturedEpochMs'],stereo=True,require_cameras=True)
            need(state['captureIntent'] is not None and packet['requestId']==state['captureIntent']['commandId'])
        if state['modelRequest'] is not None:
            draw_command(state['modelRequest']);need(state['capture'] is not None
                and state['modelRequest']['captureRequestId']==state['capture']['requestId'])
        if state['draws'] is not None:
            packet=state['draws'];need(state['capture'] is not None)
            need(state['modelRequest'] is not None and packet['requestId']==state['modelRequest']['commandId'])
            draw_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=ACTION,
                captureRequestId=state['capture']['requestId']),self.pid,packet['capturedEpochMs'],capture=state['capture'])
        if state['image'] is not None:
            image_record(state['image']);need(same(state['image']['binding'],self.binding) and state['image']['role']=='actor'
                and state['image']['runId']==self.run and state['image']['ticket']==ticket and state['image']['stage']==0
                and same(state['image']['capture'],state['capture']))
        if state['retirement'] is not None:self.validate_retirement(state['retirement'],state['retirement']['owner'])
        if state['phase']=='ready':need(all(state[k] is None for k in REMOTE_FIELDS-{'phase'}))
        if state['phase'] in ('complete','cycle-complete'):
            need(all(state[k] is not None for k in REMOTE_FIELDS-{'phase','cycleAfter','failure'}) and state['image']['phase']=='saved')
            self.validate_frame(self.frame(),self.images().read(state['image']),state['avatarAfter']['capturedEpochMs'])
        if state['phase']=='cycle-complete':
            need(state['cycleAfter'] is not None and same(state['cycleAfter'],self.parent.previous))
            self.parent.validate();need(self.parent.state['phase']=='native-quiet')
        else:need(state['cycleAfter'] is None)

    def save(self):
        self.bound();value=dict(self.identity,parentPrefix=deepcopy(self.parent_prefix),payload=pack([self.state]))
        try:self.file.write(value,self.previous);self.previous=deepcopy(value);self.bound()
        except BaseException:self.failed=True;raise

    def fail_record(self):
        """Persist refusal even after live clocks expire; no product operation.

        Only this exact original host/OFD may record its own terminal failure.
        An uncertain or lost journal stays strongly owned and prevents reopen.
        """
        self.state.update(phase='failed',failure='acquisition-refused',cycleAfter=None)
        if self.failed:
            if self.file not in UNRESOLVED_HOST_FILES:UNRESOLVED_HOST_FILES.append(self.file)
            return
        try:
            self.locks();self.file.guard();require_directory(self.file.parent,self.store.path.parent)
            need(same(self.store.read(),self.previous))
            value=dict(self.identity,parentPrefix=deepcopy(self.parent_prefix),payload=pack([self.state]))
            self.file.write(value,self.previous);self.previous=deepcopy(value)
        except BaseException:
            self.failed=True
            if self.file not in UNRESOLVED_HOST_FILES:UNRESOLVED_HOST_FILES.append(self.file)

    def image_root(self):
        key=hashlib.sha256(canonical(self.binding)).hexdigest()[:16]
        return self.root/('emote-remote-images-'+self.run+'-'+key+'-'+str(self.index))

    def owned(self):
        owned=super().owned()
        for obj in (owned.owner,owned.capture,owned.storage,owned.receipts.cleanup):
            original=obj.guard
            def guarded(original=original):self.bound();need(original() is not False);return True
            obj.guard=guarded
        return owned

    def validate_retirement(self,proof,owner):
        super().validate_retirement(proof,owner)
        before=self.state['avatarBefore'];need(before is not None
            and proof['memory']['instance']==before['source']['worldRenderInstance'])
        if self.state['capture'] is not None:need(proof['memory']['instance']==self.state['capture']['instance'])
        need(same(owner['capture'],self.state['captureIntent']) and same(proof['memory'],self.state['storage'])
            and same(proof['files']['absent'],self.state['inventory']))

    def frame(self):
        ticket=self.parent_prefix['state']['steps'][1]['call']['ticket']
        return dict(ticket=ticket,primary=deepcopy(self.state['primary']),
            **{k:deepcopy(self.state[k]) for k in ('avatarBefore','avatarAfter','capture','draws')})

    def validate_frame(self,frame,raw,epoch):
        exact(frame,{'ticket','primary','avatarBefore','avatarAfter','capture','draws'})
        row=remote_draws(frame['primary'],frame['avatarBefore'],frame['avatarAfter'],frame['capture'],frame['draws'],self.pid,epoch)
        original_pixels(frame['capture'],raw)
        # Both executed used-eye rows and submitted PNG bytes are established.
        # No local scene/marker or requested Emote is assigned to these pixels.
        return row

    @contextmanager
    def source_admission(self):
        originals=[]
        try:
            for source in (self.primary,self.source):
                original=source.original_guard;originals.append((source,original))
                def guarded(original=original):self.candidate();need(original() is not False);return True
                source.original_guard=guarded
            yield
        finally:
            for source,original in originals:source.original_guard=original

    def read(self,ticket):
        identifier(ticket);self.bound()
        need(self.previous is None and self.state['phase']=='ready' and self.parent.state['phase']=='ready'
            and len(self.parent.state['steps'])==2 and self.parent.state['steps'][1]['call']['ticket']==ticket
            and len((self.primary.previous or {}).get('records',[]))<32
            and len((self.source.previous or {}).get('records',[]))<=30)
        self.started=self.clock;owned=None;begin=self.started;epoch=self.source.clock_ms()
        try:
            self.state['phase']='reading';self.save()
            phase=self.parent.source.phase.status(self.parent.effects.current_original(self.parent_prefix['state']['steps'][1]['frame'])['phaseAfter'])
            need(self.phase_ticket(phase)==ticket);self.remember('providerBefore',phase)
            with self.source_admission():
                self.remember('primary',self.primary.read());self.remember('avatarBefore',self.source.read())
                before=self.state['avatarBefore'];need(type(before['source']['worldRenderInstance']) is str)
                owned=self.owned();need(owned.owner.store.read() is None)
                reader=self.models();need(isinstance(reader,PicoWorldModelDraws) and reader.pid==self.pid and not reader.ios)
                model_guard,model_send,model_get=reader.guard,reader.send,reader.original
                def guard_model():
                    self.bound();need(model_guard() is not False);self.bound();return True
                def send_model(command):
                    need(self.state['modelRequest'] is None);draw_command(command)
                    self.remember('modelRequest',command);self.bound();model_send(command)
                def get_model():
                    self.bound();value=model_get();self.bound();return value
                reader.guard,reader.send,reader.original=guard_model,send_model,get_model
                intent,send=owned.capture.intent,owned.capture.send
                def reserve(command):
                    need(self.state['captureIntent'] is None);self.remember('captureIntent',command);intent(command);self.bound()
                def acquire(command):
                    need(same(command,self.state['captureIntent']) and same(owned.owner.owned()['capture'],command));self.bound();send(command)
                owned.capture.intent,owned.capture.send=reserve,acquire
                packet,raw=owned.read(0);self.remember('capture',packet)
                # File responsibility precedes any later model/remote failure.
                self.images(create=True).write(ticket,packet,raw)
                self.remember('draws',reader.read(packet));self.remember('avatarAfter',self.source.read())
                self.validate_frame(self.frame(),raw,max(self.source.clock_ms(),epoch+math.ceil((self.bound()-begin)*1000)))
                self.release(owned)
            host_anchor=self.parent.source.phase.epoch_ms();host_begin=self.bound()
            phase=self.parent.source.phase.status(phase);need(self.phase_ticket(phase)==ticket);self.remember('providerAfter',phase)
            self.state['phase']='complete';self.save()
            result=deepcopy(self.frame());self.validate_frame(result,self.images().read(self.state['image']),
                max(self.source.clock_ms(),epoch+math.ceil((self.bound()-begin)*1000)))
            self.bound();native_end=self.source.clock_ms();need(integer(native_end,epoch));self.bound()
            host_end=self.parent.source.phase.epoch_ms();need(number(host_end,host_anchor,1e15));end=self.bound()
            floor=max(native_end,epoch+math.ceil((end-begin)*1000))
            for stamp in (result['primary']['capturedEpochMs'],result['avatarBefore']['capturedEpochMs'],result['avatarAfter']['capturedEpochMs'],
                    result['draws']['capturedEpochMs'],result['capture']['source']['renderTrace']['recordedEpochMs'],
                    result['capture']['source']['capturedEpochMs']):fresh(stamp,floor)
            fresh(phase['capturedEpochMs'],max(host_end,host_anchor+math.ceil((end-host_begin)*1000)))
            return result
        except BaseException:
            if owned is not None and not self.failed:
                self.recovering=True
                try:
                    if owned.owner.store.read() is not None and self.state['captureIntent'] is not None:self.release(owned)
                except BaseException:pass
                finally:self.recovering=False
            self.fail_record()
            raise NativeUIError('Original remote Emote capture failed; responsibility remains retained') from None
        finally:self.started=None

    def original(self):
        self.bound();need(self.state['phase'] in ('complete','cycle-complete'));self.decode()
        return deepcopy(self.frame()),self.images().read(self.state['image'])

    def recover(self):
        self.recovering=True
        try:
            self.bound();need(self.previous is not None and self.state['phase'] in ('reading','failed'))
            owned=self.owned()
            if self.state['captureIntent'] is None:
                need(owned.owner.store.read() is None)
                return dict(captureIssued=False,wholeFeatureComplete=False,originalsRetained=True)
            if owned.owner.store.read() is not None:self.release(owned)
            self.validate_retirement(self.state['retirement'],self.state['retirement']['owner']);return deepcopy(self.state['retirement'])
        finally:self.recovering=False

    def finish_cycle(self):
        self.bound();need(self.state['phase']=='complete');self.decode();self.parent.validate()
        need(self.parent.state['phase']=='native-quiet' and len(self.parent.state['steps'])==4)
        self.state.update(phase='cycle-complete',cycleAfter=deepcopy(self.parent.previous));self.save()
        return dict(picoEmoteRemoteCycleVersion=1,normalCycleClosed=True,remoteDrawPngRetired=True,
            wholeFeatureComplete=False,independentActorQualified=False,pixelsQualified=False,originalsRetained=True)

    def close_host(self):
        value=self.file.close_host();self.failed=True
        if not value and self.file not in UNRESOLVED_HOST_FILES:UNRESOLVED_HOST_FILES.append(self.file)
        return value


def create(adapter,viewer_target,parent,primary,viewer,index=1):
    """Typed Emote viewer capture/exclusion and actual model-draw readers."""
    parent.source.lock.assert_held();viewer.lock.assert_held()
    need(viewer.lock.path==adapter._script_journey().state_path(viewer_target).with_name('script-sources.lock'))
    _ui,_native,binding=adapter._script_runtime(viewer_target)
    need(same(binding,viewer.binding))
    return PicoEmoteRemoteCapture(parent,primary,viewer,index,
        lambda:adapter._emote_world_render_capture(viewer_target,viewer),
        lambda:adapter._emote_model_draws_observer(viewer_target))
