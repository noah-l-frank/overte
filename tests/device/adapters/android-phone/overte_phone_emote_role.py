"""Own per-role Emote measurements, original archives and public sequences.

No input operation or target fact forwarding is provided. The enclosing feature
still owns admission/setup, authenticated actor lifetime and whole retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.emote_rig_measurements import continuation,source as source_group
from adapters.native_animation_caller import selected as selected_caller
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.contract import result,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection
from feature_journeys.evidence import rectangle
from overte_phone_emote_run import PhoneEmoteRun
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_effects import PhoneEmoteEffects,PLAYS
from overte_phone_emote_namespaces import PhoneEmoteNamespaces
from overte_phone_emote_originals import PhoneEmoteOriginals,BLOCK
from overte_phone_emote_observation import PhoneEmoteObservation
from overte_phone_emote_capture import PhoneEmoteCapture
from overte_phone_emote_motion_files import PhoneEmoteMotionFiles
from overte_phone_script_history import pack,unpack,same

VERSION=1
LIMIT=1024


class RoleOriginals(PhoneEmoteOriginals):
    KINDS=frozenset({'role-observations'})


class PhoneEmoteRole:
    def __init__(self,run,role,image_policy):
        need(isinstance(run,PhoneEmoteRun) and role in ('primary','actor'))
        run.lock.assert_held();need(run.state is not None)
        exact(image_policy,{'source','marker','subject'});need(image_policy['source']=='world-render-target')
        rectangle(image_policy['marker'],(16384,16384));rectangle(image_policy['subject'],(16384,16384))
        self.run,self.role,self.policy=run,role,deepcopy(image_policy)
        if run.image_policy is not None:need(same(run.image_policy,self.policy))
        self.source=run.source(role);self.inputs=PhoneEmoteInputs(self.source if role=='primary' else run.source())
        self.effects=PhoneEmoteEffects(self.inputs,current_source=self.source)
        self.binding=deepcopy(context(self.source.binding));self.started=self.clock=None;self.failed=False
        self.store=PrivateFeatureState(self.source.store.path.with_name('phone-emote-'+role+'-role.json'))
        self.previous=self.store.read()
        self.state=dict(phase='ready',segment=self.source.segment,index=0,sequence=0,manifests=[],last=None,
            played=None,lastImage=None,compare=None,pending=None)
        self.originals=RoleOriginals(self.source.artifact_root,self.binding,self.source.run,role,self.bound,self.storage_intent,
            kind='role-observations',monotonic=self.source.monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def bound(self):
        source=self.source;source.lock.assert_held()
        need(not self.failed and source.guard() is not False and same(self.store.read(),self.previous)
            and same(source.store.read(),source.previous) and same(self.inputs.store.read(),self.inputs.previous)
            and same(self.run.store.read(),self.run.previous))
        now=source.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<20));self.clock=now

    def references(self,manifests,count):
        need(type(manifests) is list and len(manifests)<=LIMIT//BLOCK and integer(count,0,LIMIT))
        refs=[]
        for index,item in enumerate(manifests,1):
            self.originals.manifest_reference(item);need(item['block']==index and (index==len(manifests) or item['count']==BLOCK))
            refs.extend(self.originals.manifest(item))
        need(len(refs)==count)
        for index,item in enumerate(refs,1):self.originals.expand(item);need(item['index']==index)
        return refs

    def stored(self,index):
        need(integer(index,1,self.state['sequence']))
        manifest=self.state['manifests'][(index-1)//BLOCK]
        ref=self.originals.manifest(manifest)[(index-1)%BLOCK]
        value=self.originals.read(self.originals.expand(ref));self.record(value,index)
        return value

    def decode(self,value):
        exact(value,{'emoteRoleVersion','runId','fixtureUrl','role','binding','artifactRoot','imagePolicy','payload'})
        need(type(value['emoteRoleVersion']) is int and value['emoteRoleVersion']==VERSION and value['runId']==self.source.run
            and value['fixtureUrl']==self.source.phase.fixture_url and value['role']==self.role and same(value['binding'],self.binding)
            and value['artifactRoot']==str(self.source.artifact_root) and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','segment','index','sequence','manifests','last','played','lastImage','compare','pending'})
        need(state['phase'] in ('ready','acquiring','retaining') and integer(state['segment'],0,15)
            and integer(state['index'],0,256) and integer(state['sequence'],0,LIMIT) and state['index']<=state['sequence']
            and (state['segment']!=0 or state['index']==state['sequence']))
        self.references(state['manifests'],state['sequence'])
        need(state['last'] is None if state['sequence']==0 else type(state['last']) is int and state['last']==state['sequence'])
        for key in ('lastImage','compare'):
            if state[key] is not None:
                exact(state[key],{'segment','record'});need(integer(state[key]['segment'],0,state['segment']) and integer(state[key]['record'],1,state['sequence']))
        if state['played'] is not None:
            exact(state['played'],{'segment','reference'});need(integer(state['played']['segment'],0,15) and state['played']['segment']==state['segment'])
            exact(state['played']['reference'],{'inputTicket','frame'});identifier(state['played']['reference']['inputTicket'])
            reference=state['played']['reference']['frame'];exact(reference,{'revision','sha256'})
            need(integer(reference['revision'],1,LIMIT) and type(reference['sha256']) is str and len(reference['sha256'])==64
                and all(c in '0123456789abcdef' for c in reference['sha256']))
        pending=state['pending']
        if state['phase']=='ready':need(pending is None)
        else:
            exact(pending,{'ticket','image','index','scopeId','motion','original','manifest'})
            identifier(pending['ticket']);need(type(pending['image']) is bool and integer(pending['index'],1,256)
                and pending['index']==state['index']+1 and state['index']<256)
            if pending['scopeId'] is not None:identifier(pending['scopeId']);need(pending['image'])
            if pending['motion'] is not None:
                motion=PhoneEmoteMotionFiles.record(pending['motion'])
                need(pending['image'] and same(motion['binding'],self.binding) and motion['runId']==self.source.run
                    and motion['role']==self.role and motion['stage']==state['sequence']+1 and motion['ticket']==pending['ticket'])
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(state['phase']=='retaining' and pending['original']['index']==state['sequence']+1)
            if pending['manifest'] is not None:
                exact(pending['manifest'],{'emoteManifestVersion','reference','phase'});self.originals.manifest_reference(pending['manifest']['reference'])
                need(type(pending['manifest']['emoteManifestVersion']) is int and pending['manifest']['emoteManifestVersion']==1
                    and pending['manifest']['phase'] in ('planned','saved') and pending['original'] is not None and pending['original']['phase']=='saved'
                    and pending['manifest']['reference']['block']==state['sequence']//BLOCK+1
                    and pending['manifest']['reference']['count']==state['sequence']%BLOCK+1)
        return deepcopy(state)

    def save(self):
        try:
            self.bound()
            value=dict(emoteRoleVersion=VERSION,runId=self.source.run,fixtureUrl=self.source.phase.fixture_url,role=self.role,
                binding=self.binding,artifactRoot=str(self.source.artifact_root),imagePolicy=self.policy,payload=pack([self.state]))
            self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def storage_intent(self,kind,value):
        pending=self.state['pending'];need(pending is not None and kind in ('original','manifest'))
        old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==self.state['sequence']+1)
            if old is None:need(value['phase']=='planned')
            else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                and (old['phase']=='planned' or same(value['file'],old['file'])))
        else:
            exact(value,{'emoteManifestVersion','reference','phase'});self.originals.manifest_reference(value['reference'])
            need(type(value['emoteManifestVersion']) is int and value['emoteManifestVersion']==1
                and value['reference']['block']==self.state['sequence']//BLOCK+1 and value['reference']['count']==self.state['sequence']%BLOCK+1)
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved' and same(old['reference'],value['reference']))
        pending[kind]=deepcopy(value);self.save()

    def motion_intent(self,value):
        PhoneEmoteMotionFiles.record(value);pending=self.state['pending'];need(pending is not None)
        need(value['runId']==self.source.run and value['role']==self.role and same(value['binding'],self.binding)
            and value['stage']==self.state['sequence']+1 and value['ticket']==pending['ticket'])
        old=pending['motion']
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file'])))
        pending['motion']=deepcopy(value);self.save()

    def record(self,row,sequence):
        exact(row,{'emoteRoleRecordVersion','sequence','segment','index','ticket','image','archive','effect','frame',
            'inputHeader','inputSourceHeader','sourceHeader','played','background','motion','public'})
        need(type(row['emoteRoleRecordVersion']) is int and row['emoteRoleRecordVersion']==1 and type(row['sequence']) is int and row['sequence']==sequence
            and integer(row['segment'],0,15) and integer(row['index'],1,256) and type(row['image']) is bool)
        context=self.effects._archive_context(row['inputHeader'],row['inputSourceHeader'],row['sourceHeader'])
        need(same(row['frame'],row['effect']['frame']))
        if row['image']:
            need(row['archive'] is not None and all(same(row[key],row['archive'][key]) for key in ('inputHeader','inputSourceHeader','sourceHeader')))
            value=PhoneEmoteObservation.archive(row['archive'],context,row['index'],self.policy)
            need(value['ticket']==row['ticket'] and same(value['effect'],row['effect']))
        else:
            need(row['archive'] is None)
            effect=(context.background_recompute(row['frame'],**row['background']) if row['background'] is not None
                else context.phase_recompute(row['frame']) if 'emotePhaseEffectVersion' in row['effect']
                else context.pending_restore(row['frame'],row['played']) if 'emotePendingRestoreVersion' in row['effect']
                else context.recompute(row['frame'],played=row['played'],call=row['effect']['call']))
            need(same(effect,row['effect']))
        frame=context.current_original(row['frame']);value=row['public'];result('feature.emotes.observe',value)
        need(value['runId']==self.source.run and value['sequence']==sequence and value['capturedEpochMs']==frame['hostEpochMs']
            and same(value['state'],row['effect']['state']) and same(value['lifecycle'],frame['group']['native']['lifecycle']))
        need(frame['phaseAfter']['activations'][-1]['ticket']==row['ticket'])
        need((row['motion'] is not None)==(row['image'] and row['effect'].get('call',{}).get('verb') in PLAYS))
        artifacts=[]
        if row['image']:
            _image,_raw,captured=PhoneEmoteCapture.archive(row['archive']['result']['image'],context.source,row['index'],self.policy)
            original=captured['image'];artifacts.append(dict(kind='image',name=original['name'],sequence=sequence,
                capturedEpochMs=original['capture']['source']['capturedEpochMs'],ticket=row['ticket'],source='world-render-target'))
        if row['motion'] is not None:
            motion=row['motion'];raw=PhoneEmoteMotionFiles.archive(self.source.artifact_root,motion);packet=json.loads(raw)
            from feature_journeys.emote_motion import original
            need(motion['role']==self.role and motion['stage']==sequence and motion['ticket']==row['ticket']
                and same(motion['binding'],self.binding) and same(motion['call'],row['effect']['call'])
                and same(motion['state'],row['effect']['state']) and same(packet['after'],original(frame))
                and same(packet['before']['group']['native'],row['effect']['proof']['barrier']))
            artifacts.append(dict(kind='file',name=motion['name'],sequence=sequence,capturedEpochMs=motion['capturedEpochMs'],ticket=row['ticket']))
        need(same(value['artifacts'],artifacts) and same(value['resources'],
            ['panel:emotes'] if row['effect']['state']['panel'] else ['panel:tablet'] if frame['ui']['open'] else []))
        if sequence>1:
            previous_index=sequence-1
            manifest=self.state['manifests'][(previous_index-1)//BLOCK]
            ref=self.originals.manifest(manifest)[(previous_index-1)%BLOCK]
            previous=self.originals.read(self.originals.expand(ref))
            old=context._archive_context(previous['inputHeader'],previous['inputSourceHeader'],previous['sourceHeader'])
            before=old.current_original(previous['frame'])
            need(previous['sequence']==previous_index and row['segment'] in (previous['segment'],previous['segment']+1)
                and (row['index']>previous['index'] if row['segment']==previous['segment'] else row['index']==1))
            continuation(before['group']['native'],frame['group']['native'],self.source.pid)
            need(frame['hostEpochMs']>=before['hostEpochMs'])
        return row

    def phase(self):
        value=self.source.phase.status();need(value['active'] and value['activations'])
        active=value['activations'][-1];verb=active['stimulus']['verb']
        if verb!='cleanup':self.run.admitted()
        if verb=='baseline':need(self.run.state['phase']=='prepared')
        elif verb=='cleanup':need(self.run.state['phase']=='resources-restored' and active['ticket']==self.run.state['cleanupTicket'])
        else:
            need(self.run.state['phase']=='active' and self.run.state['call'] is not None)
            self.inputs.active(self.run.state['call'],value) if verb!='background-resume' else self.run.active(call=self.run.state['call'])
        return active

    def sync_segment(self):
        current=self.source.segment
        if current==self.state['segment']:return
        need(current==self.state['segment']+1 and self.state['phase']=='ready')
        lease=PhoneEmoteNamespaces(self.source);need(lease.state['current']==current and lease.state['closed'][-1]['segment']==current-1)
        self.state.update(segment=current,index=0,played=None,compare=None);self.save()

    def picture(self,verb):
        if verb in ('baseline','cleanup','open','close','background-resume'):return False
        if self.role=='primary':return True
        if verb!='cancel':return False
        rows=self.inputs.state['history'];plays=[row for row in rows if row['call']['verb'] in PLAYS]
        return bool(plays and plays[-1]['call']['verb']=='override')

    def playback_frame(self,frame):
        """Await actual native history, never an expected state or input replay.

        Only absent calls/loading/short measured windows are pending. Foreign
        calls, malformed originals and a qualified but frozen pose fail closed.
        The ordinary effect reader still validates provenance and movement.
        """
        row=self.inputs.state['current'];need(row is not None and row['call']['verb'] in PLAYS)
        intents=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
        need(len(intents)==1);barrier=self.effects.original(intents[0]['barrier'])['group']['native']
        started=self.source.monotonic()
        for attempt in range(32):
            self.bound();self.effects.after(row,self.effects.reference())
            selected,current,urls=source_group(frame['group'],self.source.pid,frame['epochMs'])
            continuation(barrier,current,self.source.pid)
            history=current['animation']['history']
            events=[item for item in history['events'] if item['kind']=='override'
                and item['eventSequence']>barrier['animation']['history']['callSequence']]
            need(len(events)<=1)
            if events:
                event=events[0];selected_caller(event,selected,after_epoch=barrier['capturedEpochMs'])
                chosen='Sit' if row['call']['verb']=='sit' else row['call']['inputs']['name']
                need(event['request']['url'] in urls)
                name=urls[event['request']['url']];need(name.startswith('Sit') if chosen=='Sit' else name==chosen)
                request=event['request'];need(request['loop'] is False and request['framesPerSecond']==60.)
                need(current['animation']['overrideActive'] and history['overrideSequence']==event['overrideSequence'])
                frames=[item for item in history['frames'] if item['overrideActive'] and item['overrideSequence']==event['overrideSequence']
                    and 'clip' in item and item['clip']['loadedFrames']>0 and frame['epochMs']-1500<=item['capturedEpochMs']]
                duration=1000*(request['lastFrame']-request['firstFrame'])/request['framesPerSecond']
                required=max(150.,min(500.,duration/4))
                if len(frames)>=3 and frames[-1]['capturedEpochMs']-frames[0]['capturedEpochMs']>=required:return frame
            need(self.source.monotonic()-started<3 and attempt<31)
            self.run.sleep(.075);frame=self.source.read()
        need(False)

    def read(self,after_sequence):
        need(integer(after_sequence,0,LIMIT) and self.started is None);self.started=self.source.monotonic()
        try:
            self.bound();need(self.state['phase']=='ready' and self.state['sequence']>=after_sequence and self.state['sequence']<LIMIT)
            self.sync_segment();PhoneEmoteNamespaces(self.source).assert_acquiring();active=self.phase();verb=active['stimulus']['verb'];ticket=active['ticket']
            previous=self.stored(self.state['last']) if self.state['last'] is not None else None
            if previous is None or previous['ticket']!=ticket:
                self.state['compare']=deepcopy(self.state['lastImage']);self.save()
            native=self.source.adapter._native_feature_observer(self.source.selector,read_only=True)
            epoch,host=native.clock_ms(),self.source.phase.epoch_ms()
            played=None if verb in PLAYS else (deepcopy(self.state['played']['reference']) if self.state['played'] is not None else None)
            self.state.update(phase='acquiring',pending=dict(ticket=ticket,image=False,index=self.state['index']+1,scopeId=None,motion=None,original=None,manifest=None));self.save()
            frame=self.source.read()
            if verb in PLAYS:frame=self.playback_frame(frame)
            ref=self.effects.reference();background=None;scope=None;motion=None
            if verb=='background-resume':
                need(self.state['lastImage'] is not None);old=self.stored(self.state['lastImage']['record']);need(old['image'])
                background=dict(previous=old['archive'],header=deepcopy(self.run.background().previous),image_policy=self.policy)
                effect=self.effects.measure(ref,background=background)
            elif verb in ('baseline','cleanup'):effect=self.effects.phase_measure(ref)
            elif verb in ('cancel','wait-complete') and frame['group']['native']['animation']['overrideActive']:
                effect=self.effects.pending_restore(ref,played)
            else:effect=self.effects.measure(ref,played=played)
            image=self.picture(verb) and 'emotePendingRestoreVersion' not in effect
            self.state['pending']['image']=image;self.save()
            if image:
                scope=PhoneEmoteObservation(self.effects,self.state['pending']['index'],self.policy)
                need(scope.previous is None);self.state['pending']['scopeId']=scope.scope_id;self.save()
                compare=self.state['compare'];prior=None
                if compare is not None and compare['segment']==self.state['segment']:
                    old=self.stored(compare['record']);prior=old['archive']
                value=scope.read(ticket,played=played,previous=prior);effect=value['effect'];ref=effect['frame']
                frame=self.effects.current_original(ref)
                if verb in PLAYS:
                    raw=scope.motion_bytes();packet=json.loads(raw)
                    capture=dict(call=deepcopy(effect['call']),state=deepcopy(effect['state']),capturedEpochMs=packet['after']['hostEpochMs'],
                        requestId=packet['after']['group']['native']['requestId'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                    files=PhoneEmoteMotionFiles(self.source.artifact_root,self.binding,self.source.run,self.role,self.state['sequence']+1,
                        self.bound,self.motion_intent,monotonic=self.source.monotonic)
                    motion=files.write(ticket,capture,raw)
            sequence=self.state['sequence']+1;artifacts=[]
            if image:
                _image,_raw,captured=PhoneEmoteCapture.archive(value['image'],self.source,scope.index,self.policy)
                original=captured['image'];artifacts.append(dict(kind='image',name=original['name'],sequence=sequence,
                    capturedEpochMs=original['capture']['source']['capturedEpochMs'],ticket=ticket,source='world-render-target'))
            if motion is not None:artifacts.append(dict(kind='file',name=motion['name'],sequence=sequence,capturedEpochMs=motion['capturedEpochMs'],ticket=ticket))
            public=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.source.run,sequence=sequence,capturedEpochMs=frame['hostEpochMs'],
                state=deepcopy(effect['state']),resources=['panel:emotes'] if effect['state']['panel'] else ['panel:tablet'] if frame['ui']['open'] else [],
                lifecycle=deepcopy(frame['group']['native']['lifecycle']),artifacts=artifacts)
            row=dict(emoteRoleRecordVersion=1,sequence=sequence,segment=self.state['segment'],index=self.state['pending']['index'],ticket=ticket,
                image=image,archive=None,effect=deepcopy(effect),frame=deepcopy(ref),inputHeader=deepcopy(self.inputs.previous),
                inputSourceHeader=deepcopy(self.inputs.source.previous),sourceHeader=deepcopy(self.source.previous),played=played,
                background=background,motion=deepcopy(motion),public=public)
            self.state['phase']='retaining';self.save()
            def retain(value):
                row['archive']=deepcopy(value);self.record(row,sequence)
                original=self.originals.write(sequence,row);manifests=self.originals.append(self.state['manifests'],original)
                self.state['pending']['original']=self.originals.expand(original)
                self.pending_manifests=manifests
            if image:scope.transfer(retain)
            else:retain(None)
            self.commit(row,self.pending_manifests);need(self.phase()['ticket']==ticket)
            returned=deepcopy(public);self.bound();now=native.clock_ms();current_host=self.source.phase.epoch_ms();self.bound();end=self.source.monotonic()
            need(number(end,self.started,1e15) and max(current_host-public['capturedEpochMs'],host-public['capturedEpochMs']+(end-self.started)*1000)<=1500)
            fresh(frame['group']['rootsBefore']['requestedEpochMs'],now)
            for artifact in artifacts:
                clock=current_host if artifact['kind']=='file' else now
                base=host if artifact['kind']=='file' else epoch
                need(-250<=clock-artifact['capturedEpochMs']<=1500 and base-artifact['capturedEpochMs']+(end-self.started)*1000<=1500)
            return returned
        finally:self.started=None

    def commit(self,row,manifests):
        sequence=self.state['sequence']+1;self.record(row,sequence)
        need(row['index']==self.state['pending']['index'] and row['ticket']==self.state['pending']['ticket'])
        played=row['effect'].get('playbackReference')
        if played is not None:self.state['played']=dict(segment=self.state['segment'],reference=deepcopy(played))
        self.state.update(phase='ready',index=row['index'],sequence=sequence,manifests=deepcopy(manifests),last=sequence,pending=None)
        if row['image']:self.state['lastImage']=dict(segment=self.state['segment'],record=sequence)
        self.save()

    def recover(self):
        """Retain a completed interrupted transfer, without re-emitting its result.

        Partial/missing evidence remains owned and fails. No input, source
        acquisition, file adoption or timestamp replacement occurs here.
        """
        self.bound();need(self.state['phase']=='retaining')
        pending=self.state['pending'];original=pending['original'];need(original is not None and original['phase'] in ('opened','saved'))
        row=self.originals.read(original);self.record(row,self.state['sequence']+1)
        need(row['image']==pending['image'] and same(row['motion'],pending['motion']))
        if original['phase']=='opened':
            original=deepcopy(original);original['phase']='saved';self.storage_intent('original',original)
        ref=self.originals.compact(original);manifest=pending['manifest']
        if manifest is None:manifests=self.originals.append(self.state['manifests'],ref)
        else:
            entries=self.originals.manifest(manifest['reference']);need(same(entries[-1],ref))
            expected=[] if len(entries)==1 else self.originals.manifest(self.state['manifests'][-1])
            need(same(entries[:-1],expected))
            if manifest['phase']=='planned':self.storage_intent('manifest',dict(manifest,phase='saved'))
            manifests=deepcopy(self.state['manifests'])
            if len(entries)>1:manifests.pop()
            manifests.append(deepcopy(manifest['reference']))
        if row['image']:
            need(row['archive']['header']['scopeId']==pending['scopeId'])
            scope=PhoneEmoteObservation(self.effects,row['index'],self.policy)
            if scope.previous is not None:
                need(same(scope.previous,row['archive']['header']))
                def retain(actual):need(same(actual,row['archive']))
                scope.transfer(retain)
            else:
                child=PrivateFeatureState(self.source.store.path.with_name('phone-emote-'+self.role+'-capture-'+str(row['index'])+'.json'))
                need(child.read() is None)
        else:need(pending['scopeId'] is None)
        self.commit(row,manifests)

    def motion_diagnostic(self,pending):
        value=pending['motion']
        if value is None:return None
        files=PhoneEmoteMotionFiles(self.source.artifact_root,self.binding,self.source.run,self.role,value['stage'],
            lambda:self.source.guard() is not False,lambda _value:need(False),monotonic=self.source.monotonic)
        return files.diagnostic(value)

    def failure_archive(self,value):
        return self._failure_archive(value,phase_only=False)

    def phase_archive(self,value):
        return self._failure_archive(value,phase_only=True)

    def _failure_archive(self,value,*,phase_only):
        """Historical failed ownership; no new sample or product verdict."""
        field='emoteRolePhaseRetirementVersion' if phase_only else 'emoteRoleFailureArchiveVersion'
        provider='phase' if phase_only else 'cleanup'
        exact(value,{field,'segment','header','inputHeader','inputSourceHeader','sourceHeader',
            'scope','originalDiagnostic','manifestDiagnostic','motionDiagnostic',provider})
        need(type(value[field]) is int and value[field] in (1,2)
            and integer(value['segment'],0,15))
        self.source.lock.assert_held();started=self.source.monotonic();need(number(started,0,1e15))
        frozen=deepcopy(value['header'])
        def bound():
            self.source.lock.assert_held();need(self.source.guard() is not False and same(value['header'],frozen))
            now=self.source.monotonic();need(number(now,started,1e15) and now-started<20)
        context=self.effects._archive_context(value['inputHeader'],value['inputSourceHeader'],value['sourceHeader'])
        scope=object.__new__(type(self));scope.__dict__=self.__dict__.copy();scope.bound=bound
        scope.source,scope.inputs,scope.effects=context.source,context.inputs,context
        scope.previous=frozen;scope.originals=RoleOriginals(self.source.artifact_root,self.binding,self.source.run,self.role,bound,
            lambda *_:need(False),kind='role-observations',monotonic=self.source.monotonic)
        scope.state=scope.decode(frozen);state=scope.state;pending=state['pending']
        need(state['phase'] in ('acquiring','retaining') and state['segment']==value['segment'])
        if phase_only:
            need(self.role=='actor')
            if value[field]==1:
                need(state['phase']=='acquiring' and pending['image'] is False
                    and all(pending[key] is None for key in ('scopeId','motion','original','manifest')))
        if not phase_only and value[field]==2:
            need(self.role=='actor' and pending['ticket']==value['cleanup']['activations'][-1]['ticket']
                and pending['image'] is False and pending['scopeId'] is None and pending['motion'] is None)
        # Retain exact immutable historical bytes; replay dependencies actually
        # used by restoration separately instead of issuing replacement reads.
        references=scope.references(state['manifests'],state['sequence'])
        for reference in references:scope.originals.read(scope.originals.expand(reference))
        needed={state['last']} if state['last'] is not None else set()
        for key in ('lastImage','compare'):
            if state[key] is not None:needed.add(state[key]['record'])
        for index in needed:scope.stored(index)
        original=pending['original'];diagnostic=None
        row=None
        if original is not None:
            diagnostic=scope.originals.diagnostic(original)
            if original['phase']=='saved':row=scope.originals.read(original);scope.record(row,state['sequence']+1)
        need(same(diagnostic,value['originalDiagnostic']))
        manifest=pending['manifest'];observed=None
        if manifest is not None:
            present=PrivateFeatureState(scope.originals.manifest_path(manifest['reference'])).read() is not None
            need(present or manifest['phase']=='planned')
            if present:
                entries=scope.originals.manifest(manifest['reference']);need(same(entries[-1],scope.originals.compact(original)))
                prior=[] if len(entries)==1 else scope.originals.manifest(state['manifests'][-1])
                need(same(entries[:-1],prior))
            observed=dict(present=present)
        need(same(observed,value['manifestDiagnostic']) and same(scope.motion_diagnostic(pending),value['motionDiagnostic']))
        child=value['scope']
        if pending['scopeId'] is None:need(child is None and pending['motion'] is None)
        else:
            exact(child,{'kind','archive'});need(child['kind'] in ('complete','failed','absent'))
            archive=child['archive']
            if child['kind']=='absent':
                need(archive is None and state['phase']=='acquiring' and pending['original'] is None
                    and pending['manifest'] is None and pending['motion'] is None)
            else:
                need(archive['header']['scopeId']==pending['scopeId'] and archive['header']['index']==pending['index'])
                if child['kind']=='complete':
                    result=PhoneEmoteObservation.archive(archive,context,pending['index'],self.policy)
                    need(result['ticket']==pending['ticket'])
                    if pending['motion'] is not None and pending['motion']['phase']=='saved':
                        motion=pending['motion'];raw=PhoneEmoteMotionFiles.archive(self.source.artifact_root,motion)
                        packet=json.loads(raw);frame=context.current_original(result['effect']['frame'])
                        from feature_journeys.emote_motion import original as motion_original
                        need(same(packet['after'],motion_original(frame)) and same(motion['state'],result['effect']['state']))
                    if row is not None:need(same(row['archive'],archive))
                else:PhoneEmoteObservation.failure_archive(archive,context,pending['index'],self.policy)
        cleanup=value[provider]
        from feature_journeys.phase_fixture import validate as phase_packet
        phase_packet(cleanup,run=self.source.run,area='emotes',request=cleanup['requestId'],epoch=cleanup['capturedEpochMs'])
        need(type(cleanup['active']) is bool and cleanup['activations'])
        if phase_only:
            need(cleanup['active'])
            need(cleanup['activations'][-1]['ticket']!=pending['ticket']
                and any(row['ticket']==pending['ticket'] for row in cleanup['activations'][:-1]))
        else:need(cleanup['active'] is (value[field]==1) and cleanup['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        if context.source.frames:
            prior=context.source.frames[-1]['phaseAfter'];rows=prior['activations']
            need(prior['instance']==cleanup['instance'] and prior['createdEpochMs']==cleanup['createdEpochMs']
                and len(cleanup['activations'])>=len(rows) and same(cleanup['activations'][:len(rows)],rows))
        bound();return deepcopy(value)

    def phase_intent(self):
        """Classify an obsolete owned attempt before an enclosing write."""
        self.bound();need(self.role=='actor' and self.state['phase'] in ('acquiring','retaining')
            and self.state['segment']==self.source.segment and self.source.state['phase']=='ready'
            and self.source.state['pending'] is None)
        previous=self.source.frames[-1]['phaseAfter'] if self.source.frames else self.inputs.source.frames[-1]['phaseAfter']
        current=self.source.phase.status(previous);pending=self.state['pending']
        need(current['active'] and current['activations'][-1]['ticket']!=pending['ticket']
            and any(row['ticket']==pending['ticket'] for row in current['activations'][:-1]))
        return current

    def transfer_phase(self,retain,*,retained=None,archive_version=None):
        need(archive_version is None or type(archive_version) is int and archive_version in (1,2))
        version=(retained.get('emoteRolePhaseRetirementVersion') if type(retained) is dict else
            2 if archive_version is None else archive_version)
        need(type(version) is int and version in (1,2) and (archive_version is None or archive_version==version))
        if version==1:return self._transfer_phase_v1(retain,retained=retained)
        return self._transfer_pending(retain,retained=retained,phase_only=True)

    def phase_snapshot(self):
        self.bound();need(self.role=='actor' and self.state['phase']=='acquiring'
            and self.state['segment']==self.source.segment and self.source.state['phase']=='ready' and self.source.state['pending'] is None)
        return dict(emoteRolePhaseRetirementVersion=1,segment=self.state['segment'],header=deepcopy(self.previous),
            inputHeader=deepcopy(self.inputs.previous),inputSourceHeader=deepcopy(self.inputs.source.previous),
            sourceHeader=deepcopy(self.source.previous),scope=None,originalDiagnostic=None,manifestDiagnostic=None,
            motionDiagnostic=None,phase=self.source.phase.status())

    def _transfer_phase_v1(self,retain,*,retained=None):
        """Retain an obsolete actor read before any image scope was allocated.

        This cannot release GPU/native resources or replace cleanup. It clears
        only a proved obsolete, resource-free host observation attempt.
        """
        need(callable(retain) and self.started is None and self.role=='actor');self.started=self.source.monotonic()
        try:
            self.bound();need(self.source.state['phase']=='ready' and self.source.state['pending'] is None)
            if retained is None:
                proof=self.phase_snapshot()
            else:proof=deepcopy(retained)
            self.phase_archive(proof)
            expected=deepcopy(proof['header'])
            if self.state['phase']=='ready':
                rows=unpack(expected['payload']);rows[0].update(phase='ready',pending=None);expected['payload']=pack(rows)
            need(same(expected,self.previous))
            def check():
                self.bound();PhoneEmoteNamespaces(self.source).no_scopes(self.role)
                from adapters.owned_world_render import OwnedWorldRenderCapture
                owned=self.source.adapter._world_render_capture(self.source.selector,read_only=True,role=self.role,require_frame_view=True)
                need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,self.binding)
                    and owned.owner.role==self.role and owned.owner.store.read() is None)
                from feature_journeys.phase_fixture import validate as phase_packet
                previous=proof['phase'];current=self.source.phase.status(previous)
                phase_packet(current,run=self.source.run,area='emotes',request=current['requestId'],
                    epoch=current['capturedEpochMs'],previous=previous)
                pending=unpack(proof['header']['payload'])[0]['pending']
                need(current['active'] and current['activations'][-1]['ticket']!=pending['ticket'])
                self.bound();need(self.source.monotonic()-self.started<5)
            check();need(retain(deepcopy(proof)) is not False)
            self.phase_archive(proof);check()
            if self.state['phase']!='ready':self.state.update(phase='ready',pending=None);self.save()
            check();return deepcopy(proof)
        finally:self.started=None

    def transfer_failed(self,retain,*,retained=None,provider_retired=False):
        need(type(provider_retired) is bool)
        return self._transfer_pending(retain,retained=retained,phase_only=False,provider_retired=provider_retired)

    def _transfer_pending(self,retain,*,retained,phase_only,provider_retired=False):
        """Retain exact child retirement before clearing an owned attempt."""
        need(self.started is None and callable(retain));self.started=self.source.monotonic()
        try:
            self.bound()
            if phase_only:
                need(self.role=='actor' and self.source.state['phase']=='ready' and self.source.state['pending'] is None)
                cleanup=self.phase_intent() if retained is None else self.source.phase.status()
            else:
                need(self.run.state['phase']==('resources-restored' if provider_retired else 'cleaning-inputs'));cleanup=self.source.phase.status()
                need(cleanup['active'] is (not provider_retired) and cleanup['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
            self.bound();archive=self.phase_archive if phase_only else self.failure_archive
            field='emoteRolePhaseRetirementVersion' if phase_only else 'emoteRoleFailureArchiveVersion'
            provider='phase' if phase_only else 'cleanup'
            if retained is None:need(self.state['phase'] in ('acquiring','retaining'))
            else:
                archive(retained)
                expected=deepcopy(retained['header'])
                if self.state['phase']=='ready':
                    rows=unpack(expected['payload']);rows[0].update(phase='ready',pending=None);expected['payload']=pack(rows)
                need(same(expected,self.previous))
                old=retained[provider];need(old['instance']==cleanup['instance'] and old['createdEpochMs']==cleanup['createdEpochMs'])
                if phase_only:
                    need(cleanup['active'] and len(cleanup['activations'])>=len(old['activations'])
                        and same(cleanup['activations'][:len(old['activations'])],old['activations']))
                else:need(same(old['activations'],cleanup['activations']))
            frozen=deepcopy(self.previous if retained is None else retained['header']);state=unpack(frozen['payload'])[0];pending=state['pending']
            results=[]
            def hold(child):
                self.bound()
                value=dict(segment=state['segment'],header=frozen,
                    inputHeader=deepcopy(self.inputs.previous),inputSourceHeader=deepcopy(self.inputs.source.previous),sourceHeader=deepcopy(self.source.previous),
                    scope=deepcopy(child),originalDiagnostic=None if pending['original'] is None else self.originals.diagnostic(pending['original']),
                    manifestDiagnostic=None if pending['manifest'] is None else dict(present=PrivateFeatureState(
                        self.originals.manifest_path(pending['manifest']['reference'])).read() is not None),
                    motionDiagnostic=self.motion_diagnostic(pending))
                value[field]=(2 if phase_only or provider_retired else 1) if retained is None else retained[field]
                value[provider]=cleanup if retained is None else deepcopy(retained[provider])
                if retained is not None:need(same(value,retained))
                archive(value);need(retain(deepcopy(value)) is not False);self.bound();archive(value);results.append(value)
            index=pending['index'];path=self.source.store.path.with_name('phone-emote-'+self.role+'-observation-'+str(index)+'.json')
            from adapters.owned_world_render import OwnedWorldRenderCapture
            owned=self.source.adapter._world_render_capture(self.source.selector,read_only=True,role=self.role,require_frame_view=True)
            need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,self.binding) and owned.owner.role==self.role)
            if pending['scopeId'] is None:
                if phase_only or provider_retired:PhoneEmoteNamespaces(self.source).no_scopes(self.role);need(owned.owner.store.read() is None)
                hold(None)
            elif PrivateFeatureState(path).read() is not None:
                scope=PhoneEmoteObservation(self.effects,index,self.policy);need(scope.scope_id==pending['scopeId'])
                if scope.state['phase']=='complete':scope.transfer(lambda value:hold(dict(kind='complete',archive=value)))
                else:
                    old=None if retained is None else retained['scope']['archive']
                    scope.transfer_failed(lambda value:hold(dict(kind='failed',archive=value)),retained=old)
            else:
                child=PrivateFeatureState(self.source.store.path.with_name('phone-emote-'+self.role+'-capture-'+str(index)+'.json'))
                need(child.read() is None and owned.owner.store.read() is None)
                if retained is not None:hold(retained['scope'])
                elif state['phase']=='retaining' and pending['original'] is not None and pending['original']['phase']=='saved':
                    row=self.originals.read(pending['original']);self.record(row,state['sequence']+1)
                    hold(dict(kind='complete',archive=row['archive']))
                else:hold(dict(kind='absent',archive=None))
            need(len(results)==1 and PrivateFeatureState(path).read() is None and owned.owner.store.read() is None)
            final=self.source.phase.status(cleanup);self.bound();need(final['active'] is (not provider_retired))
            if phase_only:
                need(final['activations'][-1]['ticket']!=pending['ticket']);PhoneEmoteNamespaces(self.source).no_scopes(self.role)
            else:need(final['activations'][-1]['ticket']==cleanup['activations'][-1]['ticket'])
            if self.state['phase']!='ready':self.state.update(phase='ready',pending=None);self.save()
            self.bound();return deepcopy(results[0])
        finally:self.started=None

    def publication(self):
        """Build a new actor packet; its owner posts after releasing this lock."""
        need(self.role=='actor');started=self.source.monotonic();host=self.source.phase.epoch_ms()
        need(number(started,0,1e15) and number(host,1,1e15))
        value=self.read(0);ticket=self.stored(self.state['last'])['ticket']
        payload=dict(ticket=ticket,actor='owned-observer',actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],
            facts=projection('emotes',value['state']))
        self.bound();need(self.phase()['ticket']==ticket)
        now=self.source.phase.epoch_ms();self.bound();end=self.source.monotonic()
        need(number(end,started,1e15) and end-started<20 and number(now,value['capturedEpochMs'],1e15)
            and max(now-value['capturedEpochMs'],host-value['capturedEpochMs']+(end-started)*1000)<=1500)
        return payload
