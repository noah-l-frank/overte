"""Once-issued actual iOS PCM snapshot/release ownership, independent absence.

Stored PCM is original input/sink evidence, never proof of acoustic playback.
Uncertain allocation is not resent. Uncertain release permits files queries
only. A cleanup outcome cannot replace an unavailable original snapshot.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import io
from pathlib import Path
import time
import uuid
import wave
from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import NativeFeatureObservation,exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.recorded_preview_evidence import RecordedPreviewEvidence
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.audio_api_clock import operation
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_pcm_originals import AudioPCMOriginals
from ios.adapters import audio_pcm_validation as validation
from ios.adapters.graphics_history import follow_native


VERSION=3
READS=(1,2,3)
INPUT_ORIGIN_VERSION=2
CLOSE_VERSION=3
INPUT_ORIGIN_PROFILE='qt-source-read-to-preview-tap'


class IOSAudioPCMLease:
    def __init__(self,store,recorded,*,native,preview,profile=None,close_only=False):
        need(isinstance(store,PrivateFeatureState) and type(recorded) is IOSAudioRecordedOwner and not recorded.historical
            and isinstance(native,NativeFeatureObservation) and native.ios and not native.native_clock_bound
            and isinstance(preview,RecordedPreviewEvidence) and preview.ios and native.pid==preview.pid==int(recorded.binding['processIdentity']))
        self.initialize(store,recorded,profile=profile,close_only=close_only);self.native,self.preview=native,preview;self.historical=False
        self.phase,self.epoch_ms,self.monotonic=recorded.phase,recorded.epoch_ms,recorded.monotonic
        self.previous=store.read();self.state=dict(phase='new',allocation=None,release=None,queries=[],records=[],pending=None,snapshot=None,absence=None)
        self.originals=AudioPCMOriginals(self)
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.originals.inventory(self.state)
        tail=recorded.original(recorded.state['records'][-1])['clockJoin']['nativeAfter']
        for reference in self.state['records']:
            frame=self.originals.read(reference)
            if frame['audioPCMKind'] in ('snapshot','absence'):tail=frame['clockJoin']['nativeAfter']
        restore(native,tail);preview.instance=tail['instance'];preview.cycle=self.recording['cycle']
        if self.state['snapshot'] is not None:
            packet=self.originals.read(self.state['snapshot'])['packet'];preview.sequence=packet['sequence'];preview.event_sequence=packet['source']['events'][-1]['eventSequence']
        if self.state['absence'] is not None:preview.sequence=self.originals.read(self.state['absence'])['packet']['sequence']
        send=native.send
        def native_send(command):self.query_intent(command);return send(command)
        native.send=native_send
        send_preview=preview.send
        def preview_send(command):self.query_intent(command);return send_preview(command)
        preview.send=preview_send
        self.raw_packets={};read=preview.original
        def original():
            raw=read()
            from adapters.native_feature_observation import decode
            try:value=decode(raw) if raw else None
            except ValueError:value=None
            if type(value) is dict and any(value.get('requestId')==query['commandId'] for query in self.state['queries']):
                self.raw_packets[value['requestId']]=deepcopy(value)
            return raw
        preview.original=original

    def initialize(self,store,recorded,*,profile=None,close_only=False):
        need(type(close_only) is bool and (not close_only or profile is None))
        need(profile is None or type(profile) is str and profile==INPUT_ORIGIN_PROFILE)
        need(type(recorded) is IOSAudioRecordedOwner);recorded.bound()
        need(recorded.state['pending'] is recorded.state['observation'] is None and same(recorded.envelope(recorded.state),recorded.previous))
        starts=[value for value in recorded.state['operations'] if value['verb']=='record-start'];need(starts)
        self.store,self.recorded,self.root,self.binding,self.run,self.lock=store,recorded,recorded.root,recorded.binding,recorded.run,recorded.lock
        def recording(selected):
            original=recorded.original(selected['after'])
            return dict(ticket=selected['ticket'],cycle=original['originals']['native']['audio']['recordedVoice']['cycle'],
                original=selected['after'],operationSha256=digest(selected))
        saved=store.read()
        if saved is None:self.version=CLOSE_VERSION if close_only else 1 if profile is None else INPUT_ORIGIN_VERSION
        else:
            need(type(saved) is dict and type(saved.get('iosAudioPCMLeaseVersion')) is int
                and saved['iosAudioPCMLeaseVersion'] in READS)
            self.version=saved['iosAudioPCMLeaseVersion']
            # A strict request cannot reclassify an existing legacy allocation.
            # Default recovery preserves the actual durable stronger profile.
            if profile is not None:need(self.version==2 and saved.get('profile')==profile)
        need(not close_only or self.version==CLOSE_VERSION)
        self.profile=INPUT_ORIGIN_PROFILE if self.version==2 else None
        self._requested_profile=(self.version,self.profile)
        if saved is None:self.recording=recording(starts[-1])
        else:
            # An existing lease owns its original Start, even when subsequent
            # normal cycles have extended the parent history. Recompute the
            # whole binding from actual owned operations; never adopt a saved
            # ticket/cycle/reference independently or relabel it as latest.
            need(type(saved) is dict);saved_recording=saved.get('recording')
            exact(saved_recording,{'ticket','cycle','original','operationSha256'})
            candidates=[recording(row) for row in starts if row['ticket']==saved_recording['ticket']]
            matches=[row for row in candidates if same(row,saved['recording'])]
            need(len(matches)==1);self.recording=matches[0]
        self.closing=None
        if self.version==CLOSE_VERSION:
            closes=[row for row in recorded.state['operations'] if row['verb']=='close' and row['after'] is not None]
            need(len(closes)==1 and recorded.state['operations'][-1] is closes[0])
            chosen=closes[0];tail=recorded.original(chosen['after'])['originals']['native']['audio']['recordedVoice']
            start=recorded.original(self.recording['original'])['originals']['native']['audio']['recordedVoice']
            need(chosen['cycle']==tail['cycle']==start['cycle']==self.recording['cycle'] and not tail['active']
                and tail['startedEpochMs']==start['startedEpochMs'])
            self.closing=dict(ticket=chosen['ticket'],original=deepcopy(chosen['after']),operationSha256=digest(chosen))
            if saved is not None:need(same(saved.get('closing'),self.closing))
        self._close_identity=(deepcopy(self.recording),deepcopy(self.closing))

    def expected_release(self):
        source=self.recorded.original(self.recording['original'])['originals']['native']
        return dict(instance=source['instance'],cycle=self.recording['cycle'],startedEpochMs=source['audio']['recordedVoice']['startedEpochMs'])

    @classmethod
    def archive(cls,store,recorded):
        need(recorded.historical);owner=object.__new__(cls);owner.initialize(store,recorded)
        owner.historical=True;owner.monotonic=time.monotonic;owner.previous=store.read();need(owner.previous is not None)
        owner.originals=AudioPCMOriginals(owner);owner.state=unpack(owner.previous['payload'])[0]
        owner.state=owner.decode(owner.previous);return owner

    def envelope(self,state):
        return dict(iosAudioPCMLeaseVersion=self.version,runId=self.run,binding=self.binding,artifactRoot=str(self.root),recordedStore=str(self.recorded.store.path),recording=self.recording,payload=pack([state])) | ({'profile':self.profile} if self.version==2 else {}) | ({'closing':self.closing} if self.version==CLOSE_VERSION else {})

    def bound(self):
        self.recorded.bound()
        if self.version==CLOSE_VERSION:need(same((self.recording,self.closing),self._close_identity))
        need(type(self.version) is int and (self.version,self.profile)==self._requested_profile
            and same(self.store.read(),self.previous)
            and self.recorded.state['pending'] is self.recorded.state['observation'] is None
            and same(self.recorded.envelope(self.recorded.state),self.recorded.previous));return True

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    @staticmethod
    def command(value):
        need(type(value) is dict)
        exact(value,{'schemaVersion','commandId','action'} | ({'expected'} if value.get('schemaVersion')==2 else set()))
        if value.get('schemaVersion')==2:
            exact(value['expected'],{'instance','cycle','startedEpochMs'})
            need(value['action']=='feature-recorded-audio-release' and type(value['expected']['instance']) is str)
            identifier(value['expected']['instance'])
            from adapters.native_feature_observation import integer
            need(integer(value['expected']['cycle'],1,1000000000) and integer(value['expected']['startedEpochMs'],1,1000000000000000))
        need(type(value['schemaVersion']) is int and value['schemaVersion'] in (1,2) and value['action'] in (
            'feature-native-observe','feature-recorded-audio-observe','feature-recorded-audio-release','feature-recorded-audio-files')
            and type(value['commandId']) is str and value['commandId'].startswith('ios-'));identifier(value['commandId'][4:])

    def query_intent(self,query):
        self.bound();need(not self.historical and self.state['phase']!='retired');self.command(query)
        need(len(self.state['queries'])<512 and all(old['commandId']!=query['commandId'] for old in self.state['queries']))
        if query['action']=='feature-recorded-audio-observe':
            need(self.version!=CLOSE_VERSION)
            need(self.state['phase']=='allocating' and self.state['allocation'] is None);self.state['allocation']=deepcopy(query)
        if query['action']=='feature-recorded-audio-release':
            need(self.state['release'] is None and self.state['phase'] in ('allocating','captured'))
            if self.version==CLOSE_VERSION:need(query['schemaVersion']==2 and same(query['expected'],self.expected_release()))
            else:need(query['schemaVersion']==1)
            self.state['release']=deepcopy(query);self.state['phase']='release-issued'
        self.state['queries'].append(deepcopy(query));self.save()

    def storage_intent(self,event,wire):
        self.bound();need(event=='original' and not self.historical);self.state['pending']=deepcopy(wire);self.save();return True

    def decode(self,value):
        exact(value,{'iosAudioPCMLeaseVersion','runId','binding','artifactRoot','recordedStore','recording','payload'} | ({'profile'} if self.version==2 else set()) | ({'closing'} if self.version==CLOSE_VERSION else set()));rows=unpack(value['payload'])
        need(type(value['iosAudioPCMLeaseVersion']) is int and value['iosAudioPCMLeaseVersion']==self.version and len(rows)==1
            and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','allocation','release','queries','records','pending','snapshot','absence'})
        need(state['phase'] in ('new','allocating','captured','release-issued','retired') and type(state['queries']) is list and len(state['queries'])<=512
            and type(state['records']) is list and len(state['records'])<=1024)
        ids=set()
        for query in state['queries']:self.command(query);need(query['commandId'] not in ids);ids.add(query['commandId'])
        for key,action in (('allocation','feature-recorded-audio-observe'),('release','feature-recorded-audio-release')):
            matches=[query for query in state['queries'] if query['action']==action]
            need(len(matches)<=1 and (not matches and state[key] is None or len(matches)==1 and same(matches[0],state[key])))
        need(state['phase']!='new' or state['queries']==[] and state['records']==[] and state['pending'] is None)
        need(state['phase']!='captured' or state['snapshot'] is not None)
        need(state['phase'] not in ('release-issued','retired') or state['release'] is not None)
        need(state['release'] is None or state['allocation'] is not None or self.version==CLOSE_VERSION)
        if self.version==CLOSE_VERSION:
            need(state['allocation'] is state['snapshot'] is None and state['phase']!='captured')
            for query in state['queries']:
                need(query['action']!='feature-recorded-audio-observe')
                if query['action']=='feature-recorded-audio-release':need(query['schemaVersion']==2 and same(query['expected'],self.expected_release()))
        else:need(all(query['schemaVersion']==1 for query in state['queries']))
        # Validation helpers use this exact state for command/original joins.
        prior=getattr(self,'state',None);self.state=state
        try:
            preceding=None
            for index,reference in enumerate(state['records'],1):
                need(reference['index']==index);frame=self.originals.read(reference)
                if frame.get('audioPCMKind')=='chunk':self.originals.chunk(frame)
                elif frame.get('audioPCMKind')=='snapshot':
                    need(state['allocation'] is not None);validation.snapshot(self,frame)
                    need(all(chunk in state['records'][:index-1] for values in frame['chunks'].values() for chunk in values))
                elif frame.get('audioPCMKind')=='absence':validation.absence(self,frame)
                else:need(False)
                if frame['audioPCMKind'] in ('snapshot','absence'):
                    if preceding is not None:
                        a,b=preceding['clockJoin'],frame['clockJoin'];follow_native(a['nativeAfter'],b['nativeBefore'])
                        need(b['hostBeforeEpochMs']>=a['hostAfterEpochMs'] and b['hostBeforeMonotonic']>=a['hostAfterMonotonic']
                            and frame['packet']['sequence']>preceding['packet']['sequence'])
                    preceding=frame
            for key,kind in (('snapshot','snapshot'),('absence','absence')):
                reference=state[key]
                if reference is not None:need(reference in state['records'] and self.originals.read(reference)['audioPCMKind']==kind)
            need(state['phase']!='retired' or state['absence'] is not None)
            if state['pending'] is not None:self.originals.files.original(state['pending'])
            self.originals.inventory(state)
        finally:self.state=prior
        return deepcopy(state)

    def current_cycle(self):
        # NativeClockAcquisition.begin has already read this original. This
        # check never turns retained recording metadata into a current sample.
        packet=self.native.read(self.native.sequence,require_recorded_history=True)
        need(packet['audio']['recordedVoice']['cycle']==self.recording['cycle'])
        if self.version==CLOSE_VERSION:
            wanted=self.expected_release();voice=packet['audio']['recordedVoice']
            need(packet['instance']==wanted['instance'] and voice['startedEpochMs']==wanted['startedEpochMs'] and not voice['active'])
        return packet

    def recover_proofs(self):
        """Adopt fully saved originals after a lost metadata return, no send."""
        self.originals.recover();changed=False
        for reference in self.state['records']:
            frame=self.originals.read(reference)
            if frame['audioPCMKind']=='snapshot':
                validation.snapshot(self,frame)
                if self.state['snapshot'] is None:self.state['snapshot']=deepcopy(reference);changed=True
                else:need(same(self.state['snapshot'],reference))
            elif frame['audioPCMKind']=='absence':
                validation.absence(self,frame)
                if self.state['absence'] is None:self.state['absence']=deepcopy(reference);changed=True
                else:need(same(self.state['absence'],reference))
        if self.state['absence'] is not None and self.state['phase']!='retired':self.state['phase']='retired';changed=True
        elif self.state['snapshot'] is not None and self.state['phase']=='allocating':self.state['phase']='captured';changed=True
        if changed:self.save()

    @operation
    def capture(self):
        need(self.version in (1,2));self.bound();need(not self.historical);self.recover_proofs()
        if self.state['snapshot'] is not None:return self.snapshot()
        need(self.state['phase']=='new');self.state['phase']='allocating';self.save()
        before=self.phase.status();need(before['active']);acquisition=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        first=acquisition.begin(self.epoch_ms());self.current_cycle()
        # Normal recording already owns native evidence memory. Existing tap
        # files, however, may belong to an unknown prior snapshot and must not
        # be overwritten or swept after loss of its lease metadata.
        request=self.preview._request('feature-recorded-audio-files');preflight=self.preview._packet(request,self.monotonic());preflight_query=deepcopy(self.state['queries'][-1])
        validation.files_packet(self,preflight,preflight_query)
        need(preflight['instance']==self.native.instance and preflight['requestedEpochMs']>=first and all(row['exists'] is False for row in preflight['files']))
        self.preview.sequence=preflight['sequence']
        packet,raw=self.preview.read(self.preview.sequence,after_cycle=self.recording['cycle']-1)
        join=acquisition.finish(dict(snapshot=packet,preflight=preflight),[('snapshot','capturedEpochMs'),('preflight','capturedEpochMs')]);after=self.phase.status(before)
        # Preserve the bytes returned by the existing native pullFile reader.
        chunks={kind:self.originals.chunks(kind,raw[kind]) for kind in ('input','sink')}
        frame=dict(audioPCMKind='snapshot',audioPCMSnapshotVersion=1,recording=self.recording,packet=packet,chunks=chunks,
            clockJoin=join,phaseBefore=before,phaseAfter=after,preflight=preflight,preflightQuery=preflight_query)
        validation.snapshot(self,frame);reference=self.originals.write(frame)
        self.state.update(snapshot=reference,phase='captured');self.save();return self.snapshot()

    def snapshot(self):
        self.bound();need(self.state['snapshot'] is not None);frame=self.originals.read(self.state['snapshot']);validation.snapshot(self,frame)
        return dict(recording=deepcopy(self.recording),original=deepcopy(self.state['snapshot']),packet=deepcopy(frame['packet']),
            pcm={kind:self.originals.pcm(frame,kind) for kind in ('input','sink')})

    def input_wav(self):
        """Lossless host WAV framing of original input PCM, never acoustic output.

        The native originals remain PCM16LE chunks. Only a standard container
        header is added for the common file detector; samples, rate and channel
        order are taken exclusively from the validated original snapshot.
        """
        original=self.snapshot();source=original['packet']['source'];output=io.BytesIO()
        with wave.open(output,'wb') as container:
            container.setparams((source['channels'],2,source['sampleRate'],0,'NONE','not compressed'))
            container.writeframes(original['pcm']['input'])
        return output.getvalue()

    @operation
    def retire(self):
        self.bound();need(not self.historical);self.recover_proofs()
        if self.state['phase']=='retired':return self.retired()
        if self.version==CLOSE_VERSION and self.state['phase']=='new':self.state['phase']='allocating';self.save()
        need(self.state['phase'] in ('allocating','captured','release-issued') and (self.state['allocation'] is not None or self.version==CLOSE_VERSION))
        before=self.phase.status();acquisition=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        acquisition.begin(self.epoch_ms());self.current_cycle()
        if self.state['release'] is None:
            if self.version==CLOSE_VERSION:
                # No Observe allocation. Refuse all files rather than sweep
                # artifacts that this cleanup-only lease never created.
                request=self.preview._request('feature-recorded-audio-files')
                preflight=self.preview._packet(request,self.monotonic());query=self.state['queries'][-1]
                validation.files_packet(self,preflight,query)
                need(preflight['instance']==self.native.instance and all(not row['exists'] for row in preflight['files']))
                command=dict(schemaVersion=2,commandId='ios-'+uuid.uuid4().hex,action='feature-recorded-audio-release',expected=self.expected_release())
                self.preview.send(command)  # query_intent persists BEFORE this actual send.
                answer=self.preview._packet(command['commandId'],self.monotonic())
                exact(answer,{'schemaVersion','requestId','released'});need(type(answer['schemaVersion']) is int and answer['schemaVersion']==1 and answer['released'] is True)
                request=self.preview._request('feature-recorded-audio-files');self.preview._packet(request,self.monotonic())
            else:self.preview.release()
            queries=[query for query in self.state['queries'] if query['action']=='feature-recorded-audio-files'];need(queries)
            query=queries[-1];packet=self.raw_packets.get(query['commandId']);need(packet is not None)
        else:
            # A release with uncertain delivery is never sent again. Only a
            # fresh independent read-only files/memory observation is allowed.
            request=self.preview._request('feature-recorded-audio-files')
            packet=self.preview._packet(request,self.monotonic());query=self.state['queries'][-1]
        join=acquisition.finish(dict(absence=packet),[('absence','capturedEpochMs')]);after=self.phase.status(before)
        frame=dict(audioPCMKind='absence',audioPCMAbsenceVersion=1,recording=self.recording,packet=packet,query=query,
            clockJoin=join,phaseBefore=before,phaseAfter=after)
        validation.absence(self,frame);reference=self.originals.write(frame)
        self.state.update(absence=reference,phase='retired');self.save();return self.retired()

    def retired(self):
        self.bound();need(self.state['phase']=='retired' and self.state['release'] is not None and self.state['absence'] is not None)
        validation.absence(self,self.originals.read(self.state['absence']))
        if self.state['snapshot'] is not None:validation.snapshot(self,self.originals.read(self.state['snapshot']))
        return dict(retired=True,captured=self.state['snapshot'] is not None,recording=deepcopy(self.recording),absence=deepcopy(self.state['absence']))
