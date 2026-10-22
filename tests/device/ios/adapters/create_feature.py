"""Create on existing candidate-bound sessions, with paired original cleanup.

Dispatch/capability activation is deliberately separate from these source
owners. No session creation, build, install or requested-result projection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import time
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import Client
from ios.adapters.create_marker_identity import PreparedCreateMarker
from ios.adapters.create_marker_scope import CreateMarkerScope
from ios.adapters.create_retirement import CreateRetirement
from ios.adapters.create_api_clock import operation as api_operation,check as api_check
from ios.adapters.peer_admission import admit_existing_peer,validate as peer_admission

VERSION=1


def archived_marker(value,*,root,binding,run,lock):
    """The original prepared admission remains verifiable after Scope release."""
    scope=CreateMarkerScope.archive(value,root=root,binding=binding,run=run,role='primary',lock=lock)
    state=scope.state;need(state['admission'] is not None and state['webAdmission'] is not None)
    before=scope.frames[state['baseline']-1];actual=scope.returned_entity()['returned']['entityId']
    rendered=[frame for frame in scope.frames if frame['label']=='rendered-marker'];need(rendered)
    for after in reversed([frame for frame in scope.frames if frame['label']=='marker-loaded']):
        try:
            marker=PreparedCreateMarker(binding,run,scope.fixture_url,before=before['create'],after=after['create'],
                scripts=after['world']['source']['scriptOriginal'],files=state['fileOwnership'],directory=state['directory'],
                after_epoch=state['loadBarrier'],domain_before=before['world'],domain_after=after['world'])
            need(marker.state['admission']['marker']['id']==actual)
            scope.rendered(rendered[-1],dict(state,admission=marker.state['admission']))
            return marker
        except NativeUIError:continue
    raise NativeUIError('No actual rendered Create marker admission survives in the retained Scope originals')


class IOSCreateFeature:
    def __init__(self,runtime,selector,client,run,role,settings,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        from ios.adapters.create_runtime import IOSCreateRuntime
        from ios.adapters.create_configuration import settings as configuration
        need(isinstance(runtime,IOSCreateRuntime) and isinstance(client,Client) and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.client,self.run,self.role=runtime,selector,client,identifier(run),role
        self.settings=configuration(settings,role=role,target=selector);self.root=Path(self.settings['artifactRoot']);self.policy=deepcopy(self.settings['imagePolicy'])
        self.primary_selector=selector if role=='primary' else self.settings['primaryTarget']
        self.lock=ScriptSourceLock(runtime.state_path(selector).with_name('script-feature-sources.lock'))
        self.primary_lock=self.lock if role=='primary' else ScriptSourceLock(runtime.state_path(self.primary_selector).with_name('script-feature-sources.lock'))
        self.phase=PhaseFixtureReader(client,run,'create',epoch_ms=epoch_ms,monotonic=monotonic)
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-create-'+role+'-feature.json'))
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep;self.previous=None;self.state=None

    @contextmanager
    def held(self):
        with self.lock.held():
            if self.role=='actor':
                with self.primary_lock.held():yield
            else:yield

    def envelope(self,state):
        return dict(iosCreateFeatureVersion=VERSION,runId=self.run,role=self.role,artifactRoot=str(self.root),
            fixtureUrl=self.phase.fixture_url,imagePolicy=self.policy,payload=pack([state]))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read();self.state=None
        if self.previous is None:return
        value=self.previous;exact(value,{'iosCreateFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosCreateFeatureVersion']) is int and value['iosCreateFeatureVersion']==VERSION
            and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','binding','primaryBinding','phaseInstance','initialTicket','actorAdmission','beforeImage','images','exports','retirement'})
        need(state['phase'] in ('preparing','ready','cleaning','cleaned','paired','retired') and type(state['images']) is list and len(state['images'])<=80
            and type(state['exports']) is list and len(state['exports'])<=32);context(state['binding']);context(state['primaryBinding'])
        identifier(state['phaseInstance']);identifier(state['initialTicket'])
        for name in state['images']+([] if state['beforeImage'] is None else [state['beforeImage']]):
            need(type(name) is str and name.startswith('ios-'));identifier(name[4:])
        if self.role=='primary':peer_admission(state['actorAdmission'],state['binding'])
        else:need(state['actorAdmission'] is state['beforeImage'] is None and state['images']==state['exports']==[])
        self.state=deepcopy(state)

    def save(self):
        api_check();self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);api_check()

    def parts(self):
        self.lock.assert_held();own=self.runtime._create_sources(self.selector,self.lock)
        scripts_root=own['roots'].read(0)['source']['defaultScriptsUrl']
        source=self.runtime._create_source_owner(self.selector,self.run,self.role,self.phase,scripts_root,self.lock)
        if self.state is not None:need(own['binding']==source.binding==self.state['binding'])
        if self.role=='primary':
            scope=self.runtime._create_marker(self.selector,self.root,self.run,'primary',self.phase.fixture_url,
                self.state['initialTicket'],self.lock)
            actions=None
            action_store=self.runtime._create_store(self.selector,'ios-create-actions.json')
            has_rendered=any(frame['label']=='rendered-marker' for frame in scope.frames)
            lease=None if not has_rendered else archived_marker(scope.snapshot(),root=self.root,binding=own['binding'],run=self.run,lock=self.lock)
            if action_store.read() is not None:
                need(lease is not None);actions=self.runtime._create_actions(self.selector,self.run,self.client,self.settings['rezAuthority'],self.lock,scope,prepared=lease)
            history=self.runtime._create_primary(self.selector,self.run,self.root,source,self.lock,actions=actions,marker=lease)
            before=None if self.state['beforeImage'] is None else self.runtime._create_sample(self.selector,self.run,'primary',self.state['beforeImage'],self.root,self.lock)
            retirement=None if before is None else CreateRetirement(self.runtime._create_store(self.selector,'ios-create-primary-retirement.json'),source,history,
                own['observer'].pointer_state(own['clock_source']),actions=actions,scope=scope,before_image=before,
                image_factory=lambda request:self.runtime._create_sample(self.selector,self.run,'primary',request,self.root,self.lock),
                epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
            return dict(own=own,source=source,scope=scope,lease=lease,actions=actions,history=history,before=before,retirement=retirement)
        primary=self.runtime._create_sources(self.primary_selector,self.primary_lock)
        need(primary['binding']==self.state['primaryBinding'])
        roots=primary['roots'].read(0)['source']['defaultScriptsUrl']
        primary_source=self.runtime._create_source_owner(self.primary_selector,self.run,'actor-primary',self.phase,roots,self.primary_lock)
        marker_store=self.runtime._create_store(self.primary_selector,'ios-create-primary-marker.json');marker=marker_store.read();lease=None
        if marker is not None:
            from adapters.script_feature.history import unpack
            marker_state=unpack(marker['payload'])[0]
            archived=CreateMarkerScope.archive(marker,root=self.root,binding=primary['binding'],run=self.run,role='primary',lock=self.primary_lock)
            if any(frame['label']=='rendered-marker' for frame in archived.frames):
                lease=archived_marker(marker,root=self.root,binding=primary['binding'],run=self.run,lock=self.primary_lock)
        history=self.runtime._create_actor_facts(self.selector,self.run,primary_source,source,self.lock,marker=lease)
        retirement=CreateRetirement(self.runtime._create_store(self.selector,'ios-create-actor-retirement.json'),source,history,
            own['observer'].pointer_state(own['clock_source']),epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
        return dict(own=own,source=source,history=history,retirement=retirement,lease=lease)

    def ensure(self):
        self.load();status=self.phase.read();need(status['status']['active'])
        if self.state is None:
            need(status['verb']=='baseline');own=self.runtime._create_sources(self.selector,self.lock)
            primary=own if self.role=='primary' else self.runtime._create_sources(self.primary_selector,self.primary_lock)
            admission=None if self.role=='actor' else admit_existing_peer(self.runtime,self.settings['actorTarget'],own['binding'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            self.state=dict(phase='preparing',binding=deepcopy(own['binding']),primaryBinding=deepcopy(primary['binding']),phaseInstance=status['status']['instance'],
                initialTicket=status['ticket'],actorAdmission=admission,beforeImage=None,images=[],exports=[],retirement=None);self.save()
        need(status['status']['instance']==self.state['phaseInstance']);parts=self.parts();history=parts['history']
        if not history.state['records']:
            if self.role=='primary':history.capture()
            else:history.capture(marker_active=False)
        if self.role=='primary' and self.state['beforeImage'] is None:
            need(parts['scope'].state['phase']=='new' and status['verb']=='baseline')
            self.state['beforeImage']='ios-'+uuid.uuid4().hex;self.save();parts=self.parts()
        if self.role=='primary' and parts['before'].state is None:parts['before'].capture(status['ticket'],status['afterEpochMs'])
        retirement=parts['retirement']
        if retirement.state['phase']=='new':
            uncertain=self.role=='primary' and parts['before'].state['phase']=='reading'
            if uncertain:need(status['verb']=='cleanup')
            retirement.admit(unexecuted=uncertain)
        if self.state['phase']=='preparing' and self.role=='actor':self.state['phase']='ready';self.save()
        return parts,status

    def prepare_inputs(self,parts):
        need(self.role=='primary' and self.state['phase'] in ('preparing','ready'))
        from ios.adapters.create_restoration_image import original
        original(parts['before']) # An uncertain pre-marker image never permits setup input.
        need(parts['source'].frames and parts['source'].frames[-1]['originals']['createAfter']['iosCreateStateVersion'] >= 4)
        if self.state['phase']=='preparing':
            with self.runtime.existing_input_session(self.selector):parts['scope'].prepare()
            parts['scope'].admit_rendered();lease=parts['scope'].prepared()
            actions=self.runtime._create_actions(self.selector,self.run,self.client,self.settings['rezAuthority'],self.lock,parts['scope'],prepared=lease)
            actions.prepare();self.state['phase']='ready';self.save();parts=self.parts()
        need(parts['actions'] is not None);return parts

    @api_operation
    def act(self,call):
        call=arguments('feature.create.act',call);need(self.role=='primary' and call['runId']==self.run)
        with self.held():
            parts,status=self.ensure();need(status['ticket']==call['ticket'])
            parts=self.prepare_inputs(parts)
            with self.runtime.existing_input_session(self.selector):return parts['actions'].act(call)

    @api_operation
    def observe(self,call):
        call=arguments('feature.create.observe',call);need(call['runId']==self.run)
        if self.role=='primary':
            with self.held():self.load();cleanup=self.phase.read()['verb']=='cleanup'
            if cleanup:
                self.cleanup(dict(contractVersion=16,runId=self.run))
                with self.held():
                    self.load();need(self.state['phase']=='paired');parts=self.parts()
                    value=parts['retirement'].validate_original(parts['retirement'].original())['public']
                    need(value['sequence']>call['afterSequence']);return value
        with self.held():
            parts,status=self.ensure()
            if status['verb']=='cleanup':
                value=self.clean_local(parts,status)
                if self.role=='actor':
                    self.publish_retirement(parts,value);parts['history'].publish(marker_active=False)
                public=parts['retirement'].validate_original(value)['public'];need(public['sequence']>call['afterSequence']);return public
            if self.role=='actor':
                history=parts['history'];history.publish(marker_active=status['verb']!='baseline')
                publisher=history.publisher();need(publisher.state['records']);receipt=publisher.load(publisher.state['records'][-1])
                need(receipt['mode']=='published' and receipt['intent']['body']['ticket']==status['ticket'])
                value=deepcopy(receipt['intent']['derived']['public']);need(value['sequence']>call['afterSequence']);return value
            sample=artifact=None
            if status['verb']!='baseline':
                parts=self.prepare_inputs(parts)
                rows=[step['evidence'] for step in SCENARIOS['create']['steps'] if step['verb']==status['verb'] and same(step['inputs'],status['inputs'])]
                need(rows and all(same(rows[0],row) for row in rows));required=set(rows[0])
                if required & {'image','changed'}:
                    request='ios-'+uuid.uuid4().hex;self.state['images'].append(request);self.save()
                    sample=self.runtime._create_sample(self.selector,self.run,'primary',request,self.root,self.lock)
                if 'file' in required:
                    request='ios-'+uuid.uuid4().hex;self.state['exports'].append(request);self.save()
                    artifact=self.runtime._create_export_artifact(self.selector,self.run,self.root,request,self.lock)
            value=parts['history'].capture(sample=sample,policy=self.policy,export_artifact=artifact)
            need(value['sequence']>call['afterSequence']);return value

    def clean_local(self,parts,status):
        need(status['verb']=='cleanup')
        self.state['phase']='cleaning';self.save()
        with self.runtime.existing_input_session(self.selector):value=parts['retirement'].cleanup(status['ticket'])
        self.state['phase']='cleaned';self.save();return value

    def publish_retirement(self,parts,value):
        need(self.role=='actor');publisher=PhaseRetirementPublisher(PrivateFeatureState(self.runtime.state_path(self.selector).with_name(
            'phase-retirement-create-'+self.run+'-actor.json')),self.state['binding'],self.phase,self.lock,parts['own']['check'],parts['retirement'].validate_original,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        if not publisher.resolve():raise NativeUIError('Original Create Actor retirement publication is unresolved')
        publisher.publish(value);need(publisher.state['pending'] is None and publisher.state['records'])
        receipt=publisher.load(publisher.state['records'][-1]);need(receipt['mode']=='published'
            and receipt['intent']['body']['originalSha256']==digest(value))
        self.state['retirement']=dict(localSha256=digest(value),publication=deepcopy(receipt));self.save();return publisher

    @api_operation
    def cleanup(self,call):
        call=arguments('feature.create.cleanup',call);need(call['runId']==self.run)
        with self.held():
            self.load()
            if self.state is not None and self.state['phase']=='retired':return self.finalize()
            status=self.phase.status()
            if not status['active']:return self.finalize(status)
        with self.held():
            parts,status=self.ensure();value=self.clean_local(parts,status)
            if self.role=='actor':self.publish_retirement(parts,value);return {'performed':True}
            binding=deepcopy(self.state['binding']);admission=deepcopy(self.state['actorAdmission']);instance=self.state['phaseInstance'];guard=parts['own']['check']
        # No Primary or Actor source lock is held while waiting. The Actor
        # requires Primary's lock for its independently acquired Primary facts.
        def admitted(original):return dict(runId=self.run,phaseInstance=instance,binding=peer_admission(original,binding))
        reader=PhaseRetirementReader(self.runtime._create_store(self.selector,'ios-create-primary-peer-retirement.json'),binding,self.phase,guard,
            admission,admitted,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        started=last=self.monotonic()
        while True:
            now=self.monotonic();need(number(now,last,started+20));last=now
            try:receipt=reader.read();break
            except NativeUIError:
                if now-started>=19.5:raise
                self.sleep(.15)
        with self.held():
            self.load();need(self.state['phase']=='cleaned');parts=self.parts();current=self.phase.read()
            need(current['verb']=='cleanup' and current['ticket']==receipt['entry']['ticket'] and current['status']['instance']==instance)
            confirmation=parts['retirement'].refresh();measured=parts['retirement'].validate_original(confirmation)
            need(measured['acquisition']['hostBeforeMonotonic']>=receipt['acquisition']['hostAfterMonotonic']
                and measured['acquisition']['hostBeforeEpochMs']>=receipt['acquisition']['hostAfterEpochMs'])
            self.state['retirement']=dict(localSha256=digest(confirmation),peerReceipt=deepcopy(receipt));self.state['phase']='paired';self.save()
            return {'performed':True}

    @api_operation
    def publish(self):
        need(self.role=='actor')
        with self.held():
            self.load()
            if self.state is not None and self.state['phase']=='retired':return self.finalize()
            status=self.phase.status()
            if not status['active']:return self.finalize(status)
        return self.observe(dict(contractVersion=16,runId=self.run,afterSequence=0))

    @api_operation
    def finalize(self,status=None):
        """Inactive-run evidence seal; repeated use never constructs SDK sources."""
        from ios.adapters.create_final_archive import CreateFinalArchive
        self.lock.assert_held();need(self.state is not None and self.state['retirement'] is not None)
        archive=CreateFinalArchive(PrivateFeatureState(self.store.path.with_name('ios-create-'+self.role+'-'+self.run+'-final.json')),
            self.root,self.state['binding'],self.run,self.role,self.lock)
        if archive.state is not None:
            if archive.state['phase']=='writing':archive.recover()
            frame=archive.verify();need(same(frame['feature'],dict(self.state,phase=frame['feature']['phase']))
                and frame['feature']['phase']==('paired' if self.role=='primary' else 'cleaned')
                and same(frame['coordinatorHeader'],{key:value for key,value in self.previous.items() if key!='payload'}))
        else:
            need(status is not None and status['active'] is False and self.state['phase']==('paired' if self.role=='primary' else 'cleaned'))
            parts=self.parts();whole=parts['retirement'];original=whole.original();need(digest(original)==self.state['retirement']['localSha256'])
            frozen=whole.frozen();paired=deepcopy(self.state['retirement'])
            witness_files=[]
            if self.role=='actor':
                witness_store=PrivateFeatureState(self.store.path.with_name('phase-publication-create-'+self.run+'-actor.json'))
                if witness_store.read() is not None:
                    witness=parts['history'].publisher()
                    # The actual inactive fixture can retire an issued/planned
                    # normal sample read-only. It never resends its old POST.
                    need(witness.resolve() and witness.state['pending'] is None)
                    with frozen.history.validation_round():
                        archived_witness=PhaseWitnessPublisher.archive(witness_store.read(),store=witness_store,
                            binding=self.state['binding'],run=self.run,area='create',fixture_url=self.client.url,
                            phase_instance=self.state['phaseInstance'],validate_original=frozen.history.validate_original)
                    need(archived_witness['pending'] is None)
                    witness_files.extend(self.store.path.parent.glob('phase-publication-create-'+self.run+'-actor*.json'))
                publisher_store=PrivateFeatureState(self.store.path.with_name('phase-retirement-create-'+self.run+'-actor.json'))
                published=PhaseRetirementPublisher.archive(publisher_store.read(),store=publisher_store,binding=self.state['binding'],run=self.run,
                    area='create',fixture_url=self.client.url,phase_instance=self.state['phaseInstance'],validate_original=frozen.validate_original)
                need(published['pending'] is None and published['records']);paired['publisherOriginal']=publisher_store.read()
            else:
                admission=deepcopy(self.state['actorAdmission']);binding=deepcopy(self.state['binding']);instance=self.state['phaseInstance']
                def admitted(value):return dict(runId=self.run,phaseInstance=instance,binding=peer_admission(value,binding))
                reader=PhaseRetirementReader(self.runtime._create_store(self.selector,'ios-create-primary-peer-retirement.json'),binding,self.phase,
                    lambda:True,admission,admitted,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
                need(reader.state['records'] and same(reader.state['records'][-1],paired['peerReceipt']))
                paired['readerOriginal']=deepcopy(reader.store.read())
                measured=frozen.validate_original(original);receipt=paired['peerReceipt']
                need(measured['acquisition']['hostBeforeEpochMs']>=receipt['acquisition']['hostAfterEpochMs']
                    and measured['acquisition']['hostBeforeMonotonic']>=receipt['acquisition']['hostAfterMonotonic'])
            extra=witness_files;directories=[str(self.store.path.parent),str(self.root)]
            if self.role=='actor':
                directories.append(str(self.runtime.state_path(self.primary_selector).parent))
                extra.extend(self.store.path.parent.glob('phase-retirement-create-'+self.run+'-actor*.json'))
            else:
                for sample in whole.all_samples():
                    extra.append(sample.store.path)
                    if sample.frame_owner.store.read() is not None:
                        extra.extend((sample.frame_owner.store.path,sample.frame_owner.root/sample.frame_owner.name))
                for export in parts['history'].owned_exports():extra.extend((export.store.path,export.root/export.state['name']))
            excluded=[]
            for directory in {Path(path) for path in directories}:
                excluded.extend(directory.glob('ios-create-*-feature.json'));excluded.extend(directory.glob('ios-create-*-'+self.run+'-final.json'))
                excluded.extend(directory.glob('ios-create-final-*.json'))
            archive.seal(phase_original=status,feature=deepcopy(self.state),original=original,validate=frozen.validate_original,
                paired=paired,directories=directories,extra=extra,excluded=excluded,
                coordinator_header={key:value for key,value in self.previous.items() if key!='payload'})
        if self.state['phase']!='retired':self.state['phase']='retired';self.save()
        return {'performed':True}
