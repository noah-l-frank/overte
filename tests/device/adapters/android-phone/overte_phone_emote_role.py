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
