"""Current recovery/scene/publication responsibility beside rooted live cuts.

Only actual existing original readers supply facts. This guard sends nothing,
retires no metadata and cannot authorize process or SDK end. Full unknown-
carrier coverage and the final ownership archive remain separate requirements.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import unpack,same
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE
from ios.adapters.avatar_record_cache import AvatarRecordCache
from ios.adapters.emote_final_recoveries import validate as recovery_originals
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedKeyedRetirement
from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
from ios.adapters.emote_rooted_gpu import validate as current_gpu
from ios.adapters.emote_scene_history import validate as scene_history
from ios.adapters.emote_scene_order import IOSEmoteSceneOrder
from ios.adapters.emote_scene_proof import rooted
from ios.adapters.peer_admission import validate as admitted


class IOSEmoteRootedResponsibility:
    def __init__(self,flow,parts,owner,live):
        need(type(owner) is IOSEmoteRootedKeyedRetirement and type(live) is IOSEmoteRootedLive
            and live.owner is owner and not owner.historical and flow.role==owner.role and flow.run==owner.run
            and flow.root==owner.root and flow.lock is owner.lock and flow.primary_lock is owner.primary_lock
            and same(flow.state['binding'],owner.binding) and same(flow.state['primaryBinding'],owner.primary_binding))
        self.flow=flow;self.values={};self.signatures=None
        roots={flow.root,flow.store.path.parent,flow.primary_lock.path.parent}
        leases=[EmoteOriginalLease(root,[]) for root in roots]
        with read_scope(fresh=True) as reads:
            self.values=self.metadata()
            self.validate(self.values,parts,owner,live)
            self.values.update({str(path):value for path,value in current_gpu(flow,parts).items()})
        for lease in leases:lease.guard()
        self.signatures=AvatarRecordCache.signatures(reads)
        self.carriers=self.original_carriers(parts)
        need(self.carriers<=reads);self.guard()

    def path(self,name,*,primary=False):
        flow=self.flow;selector=flow.primary_selector if primary else flow.selector
        return PrivateFeatureState(flow.runtime.state_path(selector).with_name(name))

    def metadata(self):
        f=self.flow;stores=[self.path('ios-emote-'+f.role+'-'+tail+'.json',primary=primary)
            for tail,primary in (('source-recovery',True),('marker-recovery',False),('sample-recovery',False),('scene-gate',False))]
        if f.role=='actor':
            stores.append(self.path('ios-emote-actor-peer-recovery.json'))
            stores.extend(self.path(prefix+'-emotes-'+f.run+'-actor.json') for prefix in ('phase-publication','phase-retirement'))
        else:
            stores.extend((self.path('ios-emote-primary-scene-order-'+f.run+'.json'),self.path('ios-emote-primary-peer-retirement.json')))
        values={str(store.path):store.read() for store in stores}
        if f.role=='actor':
            for cls,prefix in ((PhaseWitnessPublisher,'phase-publication'),(PhaseRetirementPublisher,'phase-retirement')):
                store=self.path(prefix+'-emotes-'+f.run+'-actor.json');value=values[str(store.path)];need(value is not None)
                rows=unpack(value['payload']);need(len(rows)==1 and rows[0]['pending'] is None)
                reader=object.__new__(cls);reader.store,reader.run,reader.area=store,f.run,'emotes'
                for reference in rows[0]['records']:
                    record=reader.record_store(reference['ordinal']);need(str(record.path) not in values)
                    values[str(record.path)]=record.read()
        return values

    def validate(self,values,parts,owner,live):
        f=self.flow
        raw=lambda name:values[str(self.path(name).path)]
        recovery_originals(self,values,parts['sources'],parts['peers'],parts['scope'],parts['samples'])
        scene_history(self,values,parts['scope'],parts['restoration'],validate_original=rooted)
        ticket=live.record(live.state['records'][-1])['measurement']['ticket']
        retirement=f.state['retirement'];need(retirement is not None and retirement['original'] in f.state['cleanup'])
        if f.role=='primary':
            need(retirement['kind']=='primary-scene-ordered' and raw('ios-emote-primary-peer-retirement.json') is None)
            path=self.path('ios-emote-primary-scene-order-'+f.run+'.json');value=values[str(path.path)];need(value is not None)
            reader=object.__new__(IOSEmoteSceneOrder);reader.store=Frozen(path.path,value)
            reader.binding,reader.run,reader.area=owner.binding,f.run,'emotes'
            reader.instance,reader.url,reader.stage=owner.phase_instance,f.client.url,WEB_SCENE_STAGE
            reader.admitted_original=f.state['actorAdmission']
            reader.validate_admission=lambda value:dict(runId=f.run,phaseInstance=owner.phase_instance,binding=admitted(value,owner.binding))
            reader.actor=reader.admission();state=reader.decode(value)
            need(state['records'] and retirement['peerReceipt'] in state['records'] and retirement['peerReceipt']['entry']['ticket']==ticket)
        else:
            need(retirement['kind']=='actor-published')
            for cls,prefix,callback in ((PhaseWitnessPublisher,'phase-publication',parts['observer'].validate_original),
                (PhaseRetirementPublisher,'phase-retirement',IOSEmoteRootedSceneRetirement(owner).actor_original)):
                class Retained(cls):
                    def record_store(_reader,ordinal):
                        path=super().record_store(ordinal).path;need(str(path) in values)
                        return Frozen(path,values[str(path)])
                path=self.path(prefix+'-emotes-'+f.run+'-actor.json');value=values[str(path.path)]
                state=Retained.archive(value,store=Frozen(path.path,value),binding=owner.binding,run=f.run,area='emotes',
                    fixture_url=f.client.url,phase_instance=owner.phase_instance,validate_original=callback)
                need(state['pending'] is None and state['records'])
                reader=object.__new__(Retained);reader.store=path;reader.binding=owner.binding;reader.run,reader.area=f.run,'emotes'
                reader.url,reader.instance,reader.validate_original,reader.live=f.client.url,owner.phase_instance,callback,False
                if cls is PhaseRetirementPublisher:
                    reference=retirement['publisher'];need(reference in state['records'])
                    row=reader.load(reference)
                    need(row['mode']=='published' and same(row['intent']['original'],retirement['original'])
                        and row['intent']['body']['ticket']==ticket and row['intent']['body']['stage']==WEB_SCENE_STAGE)
                    published=[reader.load(ref) for ref in state['records']]
                    need(sum(row['mode']=='published' and row['intent']['body']['ticket']==ticket for row in published)==1)
                else:
                    row=reader.load(state['records'][-1]);last=parts['observer'].state['records'][-1]
                    need(row['mode']=='published' and same(row['intent']['original'],dict(iosEmoteObservationReferenceVersion=1,**last)))

    def original_carriers(self,parts):
        f=self.flow;patterns=[(parts['sources'].root,'emote-source-abandoned-'+f.run+'-'+f.role+'-*.json'),
            (f.root,'emote-marker-read-abandoned-'+f.run+'-'+f.role+'-*.json'),
            (f.root,'emote-scene-ready-frame-inputs-'+f.run+'-'+f.role+'-*.json')]
        if f.role=='actor':
            patterns.append((f.root,'emote-peer-abandoned-'+f.run+'-actor-*.json'))
            patterns.extend((f.store.path.parent,prefix+'-emotes-'+f.run+'-actor-*.json')
                for prefix in ('phase-publication','phase-retirement'))
        self.patterns=patterns
        return {path for root,pattern in patterns for path in root.glob(pattern)}

    def guard(self):
        self.flow.lock.assert_held();self.flow.primary_lock.assert_held()
        need(all(same(PrivateFeatureState(path).read(),value) for path,value in self.values.items()))
        if self.signatures is not None:
            need(AvatarRecordCache.signatures(set(self.signatures))==self.signatures
                and {path for root,pattern in self.patterns for path in root.glob(pattern)}==self.carriers)
        return True
