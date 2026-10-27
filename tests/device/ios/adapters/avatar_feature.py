"""Paired ordinary Avatar preparation, actions and independent observations.

The two SDK roles keep separate input and original-source ownership. Paired
reads are serialized in a stable order; normal actions never hold the peer's
lock while waiting for that peer's genuine consent. This module advertises no
capability until complete paired retirement is integrated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy,copy
import hashlib
from pathlib import Path
import time
from types import SimpleNamespace

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.operation_transport_guard import scope as transport_scope
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from ios.adapters.avatar_witness_publisher import AvatarWitnessPublisher
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from feature_journeys.retirement_receipts import AVATAR_SCOPED_STAGE as SCENE_STAGE
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.avatar_accounts import session_binding
from feature_journeys.contract import arguments,identifier,VERSION as CONTRACT_VERSION
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.witness import Client
from feature_journeys.scenarios import SCENARIOS
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_facts import retained
from ios.adapters.avatar_code import pins
from ios.adapters.avatar_configuration import authority_client,settings
from ios.adapters.avatar_login_owner import IOSAvatarLoginOwner,AvatarLoginPending
from ios.adapters.avatar_observer import IOSAvatarObserver
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_api_entry import operation as api_operation
from ios.adapters.avatar_whole_snapshots import AvatarWholeSnapshots
from ios.adapters.avatar_scene import IOSAvatarScene,Frozen
from ios.adapters.avatar_final import IOSAvatarFinal,checked as final_checked
from ios.adapters.avatar_pointers import IOSAvatarPointers
from ios.adapters.emote_native_prefix import follow
from ios.adapters.avatar_scene_transports import owners as scene_receipts
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
from ios.adapters.avatar_observation import source_history
from ios.adapters.avatar_cleanup_plan import next_step as cleanup_next
from ios.adapters import avatar_operation_clock as operation_clock
from ios.adapters.avatar_surface import IOSAvatarSurface
from ios.adapters.avatar_peer import state_original
from ios.adapters.emote_world import actual_domain
from ios.adapters.peer_admission import admit_existing_peer,validate as peer_admission

VERSION=1
ROLES=('primary','actor')


class AvatarFeaturePending(NativeUIError):pass


class WholeAvatarObserver(IOSAvatarObserver):
    """Whole-only stronger source admission; historical component APIs stay 1/2."""
    @staticmethod
    def exact_sources(baseline,current):
        from ios.adapters import avatar_exact_callers,avatar_call_stack,avatar_scripts,avatar_social_http
        old,new=baseline['originals'],current['originals']
        managers={row['membership']['instance'] for row in old['scripts']['source']['workers'] if row['avatar']['code']}
        avatar_exact_callers.owned_timers(old['scripts'],new['scripts'],managers)
        entities=old['entities']['source']['events'];events=new['entities']['source']['events']
        need(same(events[:len(entities)],entities))
        for event in events[len(entities):]:avatar_exact_callers.entity(event['caller'],event['clock']['epochMs'])
        before,after=old['http'],new['http'];need(before['iosAvatarSocialHttpVersion']==after['iosAvatarSocialHttpVersion']==2)
        prefix=before['events'];need(same(after['events'][:len(prefix)],prefix))
        table=avatar_call_stack.table(after['callerStacks'],after['clockBefore']['epochMs'])
        for xhr in avatar_social_http.events(after).values():
            created=xhr['created']
            if created['sequence']<=len(prefix):continue
            source=created['details'];worker=avatar_scripts.worker(new['scripts'],source['engine']['instance'])
            need(same(worker['membership'],source['engine']) and same(worker['code'],source['submitted']))
            calls=[(created,'xhr-open')]
            calls.extend((reply['read'],'xhr-read') for reply in xhr['replies'].values() if reply['read'] is not None)
            for event,kind in calls:
                actual=table[event['details']['callerStackId']]
                avatar_exact_callers.qualify(actual['callerStack'],actual['callerModules'],event['clock']['epochMs'],worker['avatar']['code'],kind=kind)

    def decoder(self,record):
        decoder=super().decoder(record)
        for subject in ROLES:
            self.exact_sources(retained(decoder.sources[subject],record['facts']['baseline'][subject]),
                retained(decoder.sources[subject],record['facts']['current'][subject]))
        return decoder


class IOSAvatarFeature:
    @classmethod
    def archive(cls,runtime,value,client,locks):
        """Closed original-file reconstruction; no live factory or SDK call."""
        from ios.adapters.avatar_configuration import selector
        from ios.adapters.graphics_configuration import settings as image_settings
        need(isinstance(runtime,IOSAvatarRuntime) and isinstance(client,Client) and type(value) is dict)
        role=value['role'];need(role in ROLES);exact(value['selectors'],set(ROLES));exact(locks,set(ROLES))
        for target in value['selectors'].values():selector(target)
        image_settings(dict(artifactRoot=value['artifactRoot'],imagePolicy=value['imagePolicy']))
        result=object.__new__(cls);result.runtime,result.client,result.run,result.role=runtime,client,identifier(value['runId']),role
        result.selectors=deepcopy(value['selectors']);result.selector=result.selectors[role];result.root=Path(value['artifactRoot']);result.policy=deepcopy(value['imagePolicy'])
        result.locks,result.lock=locks,locks[role];path=runtime.state_path(result.selector).with_name('ios-avatar-'+role+'-feature.json')
        result.store=Frozen(path,value);result.phase=SimpleNamespace(fixture_url=client.url+'/runs/'+result.run+'/',client=client)
        result.authority=AvatarAuthorityReader(client,result.run);result.load();return result

    def __init__(self,runtime,selector,client,run,role,configuration,*,
                 epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(runtime,IOSAvatarRuntime) and isinstance(client,Client) and role in ROLES
            and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.client,self.run,self.role=runtime,selector,client,identifier(run),role
        config=settings(configuration,role=role,target=selector)
        self.root,self.policy=Path(config['artifactRoot']),deepcopy(config['imagePolicy'])
        peer='actorTarget' if role=='primary' else 'primaryTarget'
        self.selectors={role:selector,('actor' if role=='primary' else 'primary'):config[peer]}
        self.locks={subject:ScriptSourceLock(runtime.state_path(target).with_name('script-feature-sources.lock'))
            for subject,target in self.selectors.items()}
        need(self.locks['primary'].path!=self.locks['actor'].path)
        self.lock=self.locks[role]
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-avatar-'+role+'-feature.json'))
        self.phase=PhaseFixtureReader(client,run,'avatar-people',epoch_ms=epoch_ms,monotonic=monotonic)
        self.authority=AvatarAuthorityReader(authority_client(client,run,role,config),run,epoch_ms=epoch_ms,monotonic=monotonic)
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.previous=self.state=None;self.deadline=None;self.last_clock=None

    def clock(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock)
            and (self.deadline is None or value<self.deadline));self.last_clock=value;return value

    @contextmanager
    def held(self,*,paired=False,seconds=30):
        old=self.deadline;now=self.clock();self.deadline=now+seconds if old is None else min(old,now+seconds)
        try:
            # Both roles acquire exactly the same path order for paired reads.
            # Actions acquire only their own SDK: actor consent must remain
            # possible while primary waits for an actual terminal dialog.
            selected=sorted(self.locks.values(),key=lambda lock:str(lock.path)) if paired else [self.lock]
            failure=None
            with ExitStack() as stack:
                for lock in selected:stack.enter_context(lock.held())
                try:
                    yield
                    self.clock()
                except Exception as error:failure=(error,error.__traceback__)
            # Keep the original closed pending/error category after each real
            # lock has validated its ownership and released its descriptor.
            if failure is not None:raise failure[0].with_traceback(failure[1])
        finally:self.deadline=old

    def envelope(self,state):
        return dict(iosAvatarFeatureVersion=VERSION,runId=self.run,role=self.role,selectors=self.selectors,
            artifactRoot=str(self.root),imagePolicy=self.policy,fixtureUrl=self.phase.fixture_url,payload=pack([state]))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read()
        if self.previous is None:self.state=None;return
        exact(self.previous,{'iosAvatarFeatureVersion','runId','role','selectors','artifactRoot','imagePolicy','fixtureUrl','payload'})
        rows=unpack(self.previous['payload']);need(len(rows)==1 and same(self.previous,self.envelope(rows[0])))
        value=rows[0];exact(value,{'phase','bindings','peerAdmission','phaseInstance','initialTicket','protected','sessions','lastCall','cleanup','snapshots','initial','initialBarrier','preparationClose'})
        need(value['phase'] in ('preparing','ready','cleaning','terminal-ready','cleaned','retired'));exact(value['bindings'],set(ROLES))
        for binding in value['bindings'].values():context(binding)
        peer_admission(value['peerAdmission'],value['bindings'][self.role]);identifier(value['phaseInstance']);identifier(value['initialTicket'])
        if value['protected'] is not None:need(integer(value['protected'],1,16))
        if value['sessions'] is not None:
            row=value['sessions'];exact(row,{'phase','input','sources','peers','authority'})
            need(row['phase'] in ('issued','bound'));session_binding(dict(avatarSessionBindingVersion=1,**row['input']))
            for kind in ('sources','peers'):
                exact(row[kind],set(ROLES))
                for ref in row[kind].values():exact(ref,{'index','sha256'});need(integer(ref['index'],1))
            if row['phase']=='bound':need(type(row['authority']) is dict and row['authority']['sessionBinding']==dict(avatarSessionBindingVersion=1,**row['input']))
            else:need(row['authority'] is None and self.role=='primary')
        if value['lastCall'] is not None:
            row=value['lastCall'];exact(row,{'call','phase'});arguments('feature.avatar-people.act',row['call'])
            need(row['call']['runId']==self.run and row['call']['fixtureUrl']==self.phase.fixture_url and row['phase'] in ('issued','complete'))
        need(type(value['cleanup']) is list and len(value['cleanup'])<=128)
        control_index=0;unique=set()
        for index,event in enumerate(value['cleanup']):
            need(type(event) is dict)
            if index==0:
                exact(event,{'kind','ticket','baseline','source','operationClock'});need(event['kind']=='admission')
                identifier(event['ticket']);operation_clock.validate(event['operationClock'])
                for ref in (event['baseline'],event['source']):exact(ref,{'index','sha256'});need(integer(ref['index'],1))
            elif event.get('kind')=='control':
                control_index+=1
                exact(event,{'kind','index','plan','complete'});need(event['index']==control_index and type(event['complete']) is bool)
                exact(event['plan'],{'step','inputs'})
                from ios.adapters.avatar_cleanup_inputs import call as cleanup_call
                cleanup_call(dict(avatarCleanupInputCallVersion=2,contractVersion=CONTRACT_VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,
                    ticket=value['cleanup'][0]['ticket'],index=control_index,**event['plan']))
                if index<len(value['cleanup'])-1:need(event['complete'])
            elif event.get('kind')=='checkpoint':
                exact(event,{'kind','reference','published','publisher'});need(type(event['published']) is bool
                    and ((event['published'] and self.role=='actor' and type(event['publisher']) is dict)
                        or (not event['published'] and event['publisher'] is None)))
                reference=event['reference'];exact(reference,{'index','ticket','status','original'}|({'staged'} if 'staged' in reference else set()))
                need(integer(reference['index'],1) and reference['ticket']==value['cleanup'][0]['ticket'] and reference['status']=='observed')
                need('checkpoint' not in unique);unique.add('checkpoint')
            elif event.get('kind')=='final-observation':
                exact(event,{'kind','owner','references','inputs'});need(type(event['references']) is list and len(event['references'])>=3)
            elif event.get('kind') in ('native-scene','native-scene-barrier','scene','scene-publication','actor-scene','scene-barrier','postlogout','account-close','accounts-retired','final-ready','final-barrier','complete-publication','actor-complete'):
                kind=event['kind'];need(kind not in unique);unique.add(kind)
                if kind=='native-scene':exact(event,{'kind','owner'})
                elif kind=='native-scene-barrier':exact(event,{'kind','subject','owner'});need(event['subject'] in ROLES and event['subject']!=self.role)
                elif kind=='scene':
                    exact(event,{'kind','reference','owner','login','scoped'});exact(event['reference'],{'index','sha256'})
                elif kind=='scene-publication':
                    exact(event,{'kind','reference','owner','login','scoped','published','publisher'});need(self.role=='actor' and type(event['published']) is bool)
                    exact(event['reference'],{'index','sha256'})
                elif kind=='actor-scene':exact(event,{'kind','owner'});need(self.role=='primary')
                elif kind in ('final-ready','complete-publication'):
                    exact(event,{'kind','owner','references','inputs'}|({'published','publisher'} if kind=='complete-publication' else set()))
                    need(type(event['references']) is list and len(event['references'])>=3 and type(event['inputs']) is dict)
                    if kind=='complete-publication':need(self.role=='actor' and type(event['published']) is bool)
                elif kind=='final-barrier':exact(event,{'kind','subject','owner','references','lastSha256'});need(event['subject'] in ROLES and event['subject']!=self.role)
                elif kind=='actor-complete':exact(event,{'kind','owner'});need(self.role=='primary')
                elif kind=='scene-barrier':exact(event,{'kind','subject','owner','reference','recordSha256'});need(event['subject'] in ROLES and event['subject']!=self.role)
                elif kind=='postlogout':exact(event,{'kind','owners','rows'});exact(event['owners'],set(ROLES));exact(event['rows'],set(ROLES))
                elif kind=='account-close':
                    exact(event,{'kind','phase','input','login','beforeOwner','before','afterOwner','after'})
                    need(event['phase'] in ('issued','delivered','observed') and type(event['input']) is bool
                        and (event['input'] or event['phase']=='observed') and ((event['afterOwner'] is event['after'] is None) if event['phase']!='observed' else event['afterOwner'] is not None and event['after'] is not None))
                    exact(event['before'],{'index','sha256'})
                    if event['after'] is not None:exact(event['after'],{'index','sha256'})
                else:exact(event,{'kind','before','phase','after'});need(self.role=='primary' and event['phase'] in ('issued','retired'))
            elif event.get('kind')=='primary-logout':
                exact(event,{'kind','source','owner','actorSource','actorOwner'});exact(event['source'],{'index','sha256'});exact(event['actorSource'],{'index','sha256'});need(integer(event['source']['index'],1))
                need(self.role=='actor' and 'primary-logout' not in unique);unique.add('primary-logout')
            elif event.get('kind')=='checkpoint-barrier':
                exact(event,{'kind','subject','owner','reference','recordSha256'})
                need(event['subject'] in ROLES and event['subject']!=self.role and 'checkpoint-barrier' not in unique)
                exact(event['reference'],{'index','ticket','status','original'}|({'staged'} if 'staged' in event['reference'] else set()));need(event['reference']['ticket']==value['cleanup'][0]['ticket']
                    and event['reference']['status']=='observed');unique.add('checkpoint-barrier')
            else:need(False)
        close=value['preparationClose']
        if close is not None:
            exact(close,{'phase','before','after'});need(close['phase'] in ('issued','delivered','observed'))
            exact(close['before'],{'index','sha256'});need(close['phase']=='observed' or close['after'] is None)
            if close['after'] is not None:exact(close['after'],{'index','sha256'})
        if value['cleanup']:need(value['phase'] in ('cleaning','terminal-ready','cleaned','retired'))
        self.state=deepcopy(value);self.snapshot_ledger().validate()
        if self.state['initial'] is not None:
            exact(self.state['initial'],{'owner','reference'});self.kept(self.state['initial']['owner'])
        if self.state['initialBarrier'] is not None:
            exact(self.state['initialBarrier'],{'subject','owner','reference'});self.kept(self.state['initialBarrier']['owner'])
        if self.state['preparationClose'] is not None:
            for key in ('before','after'):
                if self.state['preparationClose'][key] is not None:self.kept(self.state['preparationClose'][key])
        for event in self.state['cleanup']:
            for key in ('owner','actorOwner','publisher'):
                if event.get(key) is not None:self.kept(event[key])
            if event['kind'] in ('final-ready','complete-publication','final-observation'):self.kept(event['inputs'])
            if event['kind']=='postlogout':
                for ref in event['owners'].values():self.kept(ref)
            if event['kind']=='account-close':
                for key in ('login','beforeOwner','afterOwner'):
                    if event[key] is not None:self.kept(event[key])
            if event['kind'] in ('scene','scene-publication'):
                self.kept(event['login']);self.kept(event['scoped'])
            if event['kind']=='accounts-retired':
                self.kept(event['before'])
                if event['after'] is not None:self.kept(event['after'])

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def snapshot_ledger(self):
        def guard():self.lock.assert_held();need(same(self.store.read(),self.previous));return True
        return AvatarWholeSnapshots(self.root,self.state['bindings'][self.role],self.run,self.role,
            lambda:self.state['snapshots'],guard,self.save)

    def keep(self,value):
        self.lock.assert_held();return self.snapshot_ledger().retain(value)

    def kept(self,reference):
        self.lock.assert_held();return self.snapshot_ledger().read(reference)

    def actual(self):
        result={subject:self.runtime._sources(target) for subject,target in self.selectors.items()}
        bindings={subject:context(source['binding']) for subject,source in result.items()}
        a,b=bindings.values();need(a['sessionId']!=b['sessionId'] and a['targetFingerprint']!=b['targetFingerprint']
            and all(a[key]==b[key] for key in ('artifactSha256','sourceRevision')))
        if self.state is not None:need(same(bindings,self.state['bindings']))
        for value in result.values():need(value['check']() is not False)
        return result

    def initialize(self):
        self.load();phase=self.phase.read();actual=self.actual()
        if self.state is None:
            need(phase['verb']=='baseline')
            other='actor' if self.role=='primary' else 'primary'
            admission=admit_existing_peer(self.runtime,self.selectors[other],actual[self.role]['binding'],
                epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            self.state=dict(phase='preparing',bindings={key:deepcopy(row['binding']) for key,row in actual.items()},
                peerAdmission=admission,phaseInstance=phase['status']['instance'],initialTicket=phase['ticket'],
                protected=None,sessions=None,lastCall=None,cleanup=[],snapshots=[],initial=None,initialBarrier=None,preparationClose=None);self.save()
        need(self.state['phaseInstance']==phase['status']['instance']);return actual,phase

    def login(self):
        """Only this role's account inputs; no peer lock or peer credential."""
        self.lock.assert_held();need(self.state is not None and self.state['phase']=='preparing')
        path=self.store.path.with_name('ios-avatar-'+self.role+'-login.json')
        runtime=self.runtime._avatar_login(self.selector,self.authority,self.role,initial=not path.exists(),lock=self.lock)
        owner=IOSAvatarLoginOwner(runtime,self.selector,self.authority,self.lock,epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
        owner.prepare();owner.load();phase=owner.state['phase'];ticket=self.state['initialTicket']
        need(owner.state['preferences']['receipt']['observation']['tabletShown'] is False)
        if phase=='prepared':owner.login(ticket)
        elif phase=='login-issued':owner.terminal('login-submit',ticket)
        elif phase!='logged-in':raise AvatarFeaturePending('Owned Avatar account is already in retirement; login is not repeated')
        if self.state['protected'] is None:
            if owner.state['protected']:
                row=owner.state['protected'][-1]
                if row['phase']!='complete':raise AvatarLoginPending('Original Avatar protected request remains owned')
                need(row['ticket']==ticket)
            else:owner.protected(ticket)
            self.state['protected']=len(owner.state['protected']);self.save()
        need(owner.state['protected'][self.state['protected']-1]['phase']=='complete');return owner

    def preparation_source(self,reference):
        value=self.kept(reference);exact(value,{'owner','recovery','frame'})
        path=self.store.path.with_name('ios-avatar-'+self.role+'-sources.json')
        source=source_history(value['owner'],value['recovery'],store=Frozen(path,value['owner']),root=self.root,
            binding=self.state['bindings'][self.role],run=self.run,role=self.role,lock=self.lock)
        return retained(source,value['frame'])

    def preparation_reference(self,source):
        return self.keep(dict(owner=deepcopy(source.previous),recovery=deepcopy(IOSAvatarSourceRecovery(source).store.read()),
            frame=IOSAvatarObserver.reference(source)))

    def close_preparation_tablet(self):
        """Own one ordinary UIKit close after our completed normal login."""
        self.lock.assert_held();event=self.state['preparationClose']
        if event is not None and event['phase']=='observed':self.preparation_closed_original();return
        if event is not None and event['phase']=='issued':
            raise AvatarFeaturePending('Original preparation tablet close remains owned; UIKit input is not repeated')
        source=self.own_source();IOSAvatarSourceRecovery(source).recover()
        if event is None:
            frame=source.read();need(not any(row['id'] in ('avatar.page','people.page') for row in frame['ui']['controls']))
            before=self.preparation_reference(source)
            if not frame['ui']['open']:
                self.state['preparationClose']=dict(phase='observed',before=before,after=before);self.save();self.preparation_closed_original();return
            event=dict(phase='issued',before=before,after=None);self.state['preparationClose']=event;self.save()
            actual=self.runtime._sources(self.selector);need(same(actual['binding'],self.state['bindings'][self.role]))
            sdk=NativeUI(actual['client'],actual['session'],actual['check']);private=copy(sdk)
            def continuous():self.clock();need(sdk.check_continuity() is not False);self.clock();return True
            private.check_continuity=continuous
            from adapters.normal_ui import Locator
            private.click(Locator('accessibility id','OverteTabletClose'));event['phase']='delivered';self.save()
        for _ in range(101):
            frame=source.read();self.clock()
            if not frame['ui']['open']:
                event.update(phase='observed',after=self.preparation_reference(source));self.save();self.preparation_closed_original();return
            self.sleep(.1)
        raise AvatarFeaturePending('Original owned preparation tablet has not actually closed')

    def preparation_closed_original(self):
        self.lock.assert_held();event=self.state['preparationClose'];need(event is not None and event['phase']=='observed' and event['after'] is not None)
        before,after=(self.preparation_source(event[key]) for key in ('before','after'))
        need(not after['ui']['open'] and not any(row['id'] in ('avatar.page','people.page') for row in before['ui']['controls']))
        if same(event['before'],event['after']):need(not before['ui']['open'] and same(before,after))
        else:follow(before['originals']['native'],after['originals']['native'])
        need(before['originals']['native']['account']['loggedIn'] and after['originals']['native']['account']['loggedIn'])
        return after

    def source_parts(self):
        for lock in self.locks.values():lock.assert_held()
        actual=self.actual();sources={};peers={}
        for subject in ROLES:
            directory=self.root if subject==self.role else self.root/(subject+'-sdk-originals')
            if not directory.exists():directory.mkdir(mode=0o700)
            PrivateFeatureState(directory/'avatar-whole-root-check')._parent()
            target,lock=self.selectors[subject],self.locks[subject]
            sources[subject]=self.runtime._avatar_sources(target,self.client,self.run,self.role,directory,lock)
            peers[subject]=self.runtime._avatar_peer_sources(target,self.client,self.run,self.role,directory,lock)
        return dict(actual=actual,sources=sources,peers=peers)

    def sessions(self,parts):
        """Retain actual SDK originals before once-only control-plane binding."""
        self.lock.assert_held();current=self.authority.read();row=self.state['sessions']
        if row is not None:
            need(self.session_inputs(parts,row,current)==row['input'])
            if row['phase']=='bound':
                need(current.get('sessionBinding')==dict(avatarSessionBindingVersion=1,**row['input']));return
            if 'sessionBinding' not in current:
                raise AvatarFeaturePending('Original Avatar session-binding POST is unresolved; it is not sent again')
            need(current['sessionBinding']==dict(avatarSessionBindingVersion=1,**row['input']))
            row.update(phase='bound',authority=current);self.save();return
        if self.role=='actor' and current['phase']!='ready':
            raise AvatarFeaturePending('Waiting for primary admission of both actual native Avatar sessions')
        refs=dict(sources={},peers={});sessions={};domains=[]
        for subject in ROLES:
            source,peer=parts['sources'][subject],parts['peers'][subject]
            IOSAvatarSourceRecovery(source).recover();frame=source.read();state_original(frame,source.binding)
            native=frame['originals']['native'];account=native['account']
            principal=hashlib.sha256(('e2e-'+current['accounts'][subject]['runId']).encode()).hexdigest()
            if not account['loggedIn'] or account['principalSha256']!=principal:
                raise AvatarFeaturePending('The independent SDK has not yet established its owned native account')
            need(account['observation']['tokenPresent'] and account['observation']['tokenValid'])
            sessions[subject]=frame['originals']['state']['source']['sessionId']
            refs['sources'][subject]=IOSAvatarObserver.reference(source)
            OriginalAvatarPeerRecovery(peer).recover();packet=peer.read();refs['peers'][subject]=peer.reference()
            domains.append(actual_domain(packet['peer']['world'])['domainId'])
        need(domains[0]==domains[1]);inputs=dict(sessions=sessions,domain=domains[0]);session_binding(dict(avatarSessionBindingVersion=1,**inputs))
        if current['phase']=='ready':
            need(current.get('sessionBinding')==dict(avatarSessionBindingVersion=1,**inputs))
            self.state['sessions']=dict(phase='bound',input=inputs,authority=current,**refs);self.save();return
        need(self.role=='primary' and current['phase']=='allocated')
        self.state['sessions']=dict(phase='issued',input=inputs,authority=None,**refs);self.save()
        # The original inputs and issued responsibility precede the socket.
        self.client.request('/runs/'+self.run+'/avatar/sessions',inputs,method='POST')
        self.sessions(parts)

    def session_inputs(self,parts,row,status):
        """Reopen the actual native/session originals, even after admission."""
        sessions={};domains=[]
        for subject in ROLES:
            owner=parts['sources'][subject];frame=retained(owner,row['sources'][subject]);state_original(frame,owner.binding)
            account=frame['originals']['native']['account']
            principal=hashlib.sha256(('e2e-'+status['accounts'][subject]['runId']).encode()).hexdigest()
            need(account['loggedIn'] and account['principalSha256']==principal and account['observation']['tokenPresent']
                and account['observation']['tokenValid'])
            sessions[subject]=frame['originals']['state']['source']['sessionId']
            peer=retained(parts['peers'][subject],row['peers'][subject]);domains.append(actual_domain(peer['peer']['world'])['domainId'])
        need(domains[0]==domains[1]);return dict(sessions=sessions,domain=domains[0])

    def marker_scope(self):
        from ios.adapters.avatar_marker_history import scope_type
        from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
        value=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-marker.json')).read()
        kind=IOSAvatarHeldMarkerScope if value is None else scope_type(value)
        factory=self.runtime._avatar_held_marker_scope if kind is IOSAvatarHeldMarkerScope else self.runtime._avatar_marker_scope
        return factory(self.selector,self.client,self.run,self.role,self.root,self.state['initialTicket'],self.lock)

    def components(self,parts):
        scope=self.marker_scope()
        samples=self.runtime._avatar_samples(self.selector,scope,self.client,self.root,self.policy,self.lock)
        surfaces={}
        for subject in ROLES:
            source=parts['sources'][subject];actual=parts['actual'][subject]
            surfaces[subject]=IOSAvatarSurface(PrivateFeatureState(source.store.path.with_name('ios-avatar-'+self.role+'-'+subject+'-surface.json')),
                source,NativeUI(actual['client'],actual['session'],actual['check']),observer_role=self.role,subject_role=subject)
        observer=WholeAvatarObserver(PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-observer.json')),
            parts['sources'],parts['peers'],surfaces,samples,self.authority,self.phase,role=self.role,guard=parts['actual'][self.role]['check'],
            expected_code=pins(),epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        return parts|dict(scope=scope,samples=samples,surfaces=surfaces,observer=observer)

    def prepare(self):
        with self.held():
            # A failed preparation has entered a separate lifecycle. Do not
            # complete setup or renew any original input merely to clean it.
            abort=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-abort.json'))
            need(abort.read() is None)
            _actual,current=self.initialize()
            if self.state['phase']=='preparing':
                need(current['verb']=='baseline');self.login();self.close_preparation_tablet()
        with self.held(paired=True):
            self.load();need(self.state['phase'] in ('preparing','ready'));parts=self.source_parts();self.sessions(parts)
            if self.state['phase']=='preparing':
                # The closed Avatar restoration facade is supplied by the
                # separately reviewed common original-frame owner. It captures
                # untouched pre-marker pixels before the first setup input.
                from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
                scope=self.marker_scope()
                restoration=IOSAvatarRestorationFrames(self.runtime,self.selector,scope,self.root,self.lock,
                    epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
                restoration.resolve()
                if not restoration.state['records']:restoration.capture('initial')
                entities=self.runtime._avatar_marker_entities(self.selector,scope,self.root,self.lock);entities.abandon()
                if not entities.state['records']:entities.capture()
                pointers=scene_receipts(self.runtime,self.selector,scope,epoch_ms=self.epoch_ms,monotonic=self.monotonic)['pointers']
                pointers.abandon()
                if not pointers.state['records']:pointers.capture()
                if self.state['initial'] is None:
                    initial=[row for row in restoration.state['records'] if restoration.original(row)['kind']=='initial'];need(len(initial)==1)
                    self.state['initial']=dict(owner=self.keep(restoration.previous),reference=deepcopy(initial[0]));self.save()
        # LookAt changes the original AvatarMixer position serialization.
        # Both untouched images must exist before either ordinary camera
        # selection, despite the marker entities themselves being local.
        self.wait_peer_initial()
        with self.held(paired=True):
            self.load();parts=self.source_parts()
            if self.state['phase']=='preparing':
                scope=self.marker_scope()
                with self.runtime.existing_input_session(self.selector):scope.prepare()
                if scope.state['webAdmission'] is None:scope.admit_rendered()
                self.state['phase']='ready';self.save()
            return self.components(parts)

    def initial_original(self):
        from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
        from ios.adapters.avatar_world import actual_domain as avatar_domain
        from ios.adapters.avatar_peer import session_sha
        self.lock.assert_held();row=self.state['initial'];need(row is not None)
        value=self.kept(row['owner']);path=self.store.path.with_name('ios-avatar-'+self.role+'-restoration-frames.json')
        owner=IOSAvatarRestorationFrames.archive(value,store=Frozen(path,value),root=self.root,binding=self.state['bindings'][self.role],
            run=self.run,role=self.role,lock=self.lock)
        need(owner.state['pending'] is None and owner.state['records']==[row['reference']] and owner.original(row['reference'])['kind']=='initial')
        frame,_raw=owner.frame(row['reference']);need(avatar_domain(frame['worldBefore'])['domainId']==self.state['sessions']['input']['domain']
            ==avatar_domain(frame['worldAfter'])['domainId'])
        for name in ('worldBefore','worldAfter'):
            need(avatar_domain(frame[name])['selfSha256']==session_sha(self.state['sessions']['input']['sessions'][self.role]))
        return frame

    def wait_peer_initial(self):
        other='actor' if self.role=='primary' else 'primary';path=self.runtime.state_path(self.selectors[other]).with_name('ios-avatar-'+other+'-feature.json')
        for _ in range(251):
            with self.held(paired=True):
                self.load();self.initial_original();saved=self.state['initialBarrier']
                raw=self.kept(saved['owner']) if saved is not None else PrivateFeatureState(path).read()
                if raw is not None:
                    peer=IOSAvatarFeature.archive(self.runtime,raw,self.client,self.locks)
                    need(same(peer.state['bindings'],self.state['bindings']) and peer.state['phaseInstance']==self.state['phaseInstance']
                        and peer.state['initialTicket']==self.state['initialTicket'])
                    if peer.state['initial'] is not None:
                        peer.initial_original();event=dict(subject=other,owner=self.keep(raw),reference=deepcopy(peer.state['initial']['reference']))
                        if saved is None:self.state['initialBarrier']=event;self.save()
                        else:need(same(saved,event))
                        return
            self.sleep(.1)
        raise AvatarFeaturePending('Both untouched initial render originals must precede either ordinary marker camera change')

    def peer(self):
        need(self.state['sessions'] is not None and self.state['sessions']['phase']=='bound');status=self.authority.read()
        other='actor' if self.role=='primary' else 'primary'
        return dict(sessionId=self.state['sessions']['input']['sessions'][other],username='e2e-'+status['accounts'][other]['runId'])

    def own_source(self):
        self.lock.assert_held();self.actual()
        return self.runtime._avatar_sources(self.selector,self.client,self.run,self.role,self.root,self.lock)

    @api_operation
    def act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.avatar-people.act',call))
        need(call['runId']==self.run and call['fixtureUrl']==self.phase.fixture_url)
        self.prepare()
        with self.held():
            self.load();need(self.state['phase']=='ready');status=self.phase.read()
            need(status['ticket']==call['ticket'] and status['verb']==call['verb'] and same(status['inputs'],call['inputs']))
            before=self.state['lastCall']
            if before is not None and before['call']['ticket']==call['ticket']:need(same(before['call'],call))
            else:
                need(before is None or before['phase']=='complete');self.state['lastCall']=dict(call=call,phase='issued');self.save()
            source=self.own_source();actions=self.runtime._avatar_actions(self.selector,source,self.peer())
            if actions.state is None:actions.prepare()
            with self.runtime.existing_input_session(self.selector):result=actions.act(call)
            self.state['lastCall']['phase']='complete';self.save();return result

    def consent(self,current):
        """Actor's own input lock only; normalized primary facts are unused."""
        need(self.role=='actor');verb=current['verb']
        if verb not in ('peer-accept','peer-reject'):return
        with self.held():
            self.load();need(self.state['phase']=='ready');fresh=self.phase.read()
            if not (fresh['ticket']==current['ticket'] and fresh['verb']==verb and same(fresh['inputs'],current['inputs'])):
                raise AvatarFeaturePending('The actual consent phase changed before input admission')
            source=self.own_source();peer=self.peer()
            authority=self.authority.read();username='e2e-'+authority['accounts']['actor']['runId']
            consent=self.runtime._avatar_consent(self.selector,source,peer['sessionId'],username)
            call=dict(contractVersion=CONTRACT_VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,ticket=current['ticket'],verb=verb,inputs=current['inputs'])
            with self.runtime.existing_input_session(self.selector):consent.act(call)

    def actor_input_returned(self,current):
        """Order fresh Actor acquisition after input; never supply its effects.

        Preparation releases the paired locks before actual input starts.
        Publishing the old native state under that new ticket in this gap
        would leave stale journal entries at the first Common checkpoint.
        Consent still runs before this gate, so Primary input can finish.
        """
        need(self.role=='actor')
        for lock in self.locks.values():lock.assert_held()
        need(current['status']['active'] and current['status']['instance']==self.state['phaseInstance'])
        if current['verb']=='cleanup':return False
        if current['verb']=='baseline':return True
        barrier=self.state['initialBarrier'];need(barrier is not None and barrier['subject']=='primary')
        admitted=self.kept(barrier['owner']);path=self.runtime.state_path(self.selectors['primary']).with_name('ios-avatar-primary-feature.json')
        raw=PrivateFeatureState(path).read()
        if raw is None:return False
        need(set(raw)==set(admitted) and all(same(raw[key],admitted[key]) for key in raw if key!='payload'))
        primary=IOSAvatarFeature.archive(self.runtime,raw,self.client,self.locks)
        need(primary.role=='primary' and primary.run==self.run and same(primary.selectors,self.selectors)
            and same(primary.state['bindings'],self.state['bindings']) and primary.state['phaseInstance']==self.state['phaseInstance'])
        last=primary.state['lastCall']
        if primary.state['phase']!='ready' or last is None or last['phase']!='complete' or last['call']['ticket']!=current['ticket']:return False
        call=arguments('feature.avatar-people.act',last['call'])
        need(call['runId']==self.run and call['fixtureUrl']==self.phase.fixture_url and call['verb']==current['verb']
            and same(call['inputs'],current['inputs']));return True

    @api_operation
    def observe(self,call):
        call=arguments('feature.avatar-people.observe',call);need(call['runId']==self.run)
        current=self.phase.read()
        if current['verb']=='cleanup':
            # No active prepare/read path may reopen a peer page or demand a
            # nonnull Avatar UUID after either participant starts logout.
            with self.held():
                self.load();cleaned=self.state is not None and self.state['phase'] in ('cleaned','terminal-ready')
            if not cleaned:self.cleanup(dict(contractVersion=CONTRACT_VERSION,runId=self.run))
            with self.held():self.load();terminal_ready=self.state['phase']=='terminal-ready'
            if terminal_ready:return self.observe_terminal(call['afterSequence'])
            return self.observe_cleaned(call['afterSequence'])
        self.prepare()
        if self.role=='actor':self.consent(current)
        with self.held(paired=True):
            self.load();need(self.state['phase']=='ready')
            if self.role=='actor' and not self.actor_input_returned(self.phase.read()):
                raise AvatarFeaturePending('The actual Primary input has not returned for this Actor acquisition')
            parts=self.components(self.source_parts());owner=parts['observer']
            if self.role=='actor':owner.publisher().resolve()
            public=owner.observe(call['afterSequence'])
            if self.role=='actor':owner.publish_latest()
            return public

    @api_operation
    def cleanup(self,call):
        previous=getattr(self,'requested_cleanup_clock',None)
        self.requested_cleanup_clock=operation_clock.begin(self.epoch_ms(),self.monotonic())
        try:
            with transport_scope(self.cleanup_deadline):return self._cleanup(call)
        finally:self.requested_cleanup_clock=previous

    def _cleanup(self,call):
        call=arguments('feature.avatar-people.cleanup',call);need(call['runId']==self.run)
        requested_clock=deepcopy(self.requested_cleanup_clock)
        preparing=self.preparation_cleanup_requested()
        if preparing:return self.cleanup_preparation()
        with self.held():
            self.load();need(self.state is not None and self.state['phase'] in ('ready','cleaning','terminal-ready','cleaned'))
            checkpoint=any(row['kind']=='checkpoint' for row in self.state['cleanup'])
            cleaned=self.state['phase']=='cleaned'
            terminal_ready=self.state['phase']=='terminal-ready'
            publication_pending=self.role=='actor' and checkpoint and not next(row for row in self.state['cleanup'] if row['kind']=='checkpoint')['published']
        if cleaned:
            with self.held(paired=True):self.load();self.completed_original()
            return dict(performed=True)
        if terminal_ready:
            with self.held(paired=True):
                self.load();self.terminal_live_proof(next(row for row in self.state['cleanup'] if row['kind']=='final-ready'))
            return dict(performed=True)
        if not checkpoint:
            if not self.restore_inputs(call,requested_clock):raise AvatarFeaturePending('Original Avatar restoration is not yet complete')
            self.cleanup_checkpoint()
        elif publication_pending:self.cleanup_checkpoint()
        if self.role=='primary':self.wait_actor_checkpoint()
        self.wait_peer_checkpoint()
        self.cleanup_native_scene(call)
        self.wait_peer_native_scene()
        self.cleanup_scene(call)
        self.wait_peer_scene()
        if self.role=='actor':self.publish_scene()
        else:self.wait_actor_scene()
        self.cleanup_account()
        self.cleanup_postlogout()
        self.cleanup_account_surface()
        self.cleanup_authority()
        self.cleanup_final()
        self.wait_peer_final()
        with self.held(paired=True):
            self.load();ready=next(row for row in self.state['cleanup'] if row['kind']=='final-ready')
            terminal=self.terminal_live_proof(ready)
            if any(terminal['heldResources'].values()):
                self.state['phase']='terminal-ready';self.save();self.cleanup_deadline();return dict(performed=True)
        if self.role=='actor':self.publish_complete()
        else:self.wait_actor_complete()
        with self.held(paired=True):
            self.load();self.cleanup_deadline();self.completed_original()
            self.state['phase']='cleaned';self.save();self.cleanup_deadline()
            return dict(performed=True)

    def cleanup_preparation(self):
        """Retire failed setup without resuming setup or issuing success facts."""
        from ios.adapters.avatar_failed_preparation import AvatarFailedPreparation,FailedPreparationPending
        for _ in range(256):
            with self.held(paired=True):
                self.load();need(self.state is not None and self.state['phase'] in ('preparing','ready'))
                owner=AvatarFailedPreparation(self)
                try:
                    if owner.state['phase']=='failed-ended':owner.original_result();return dict(performed=True)
                    owner.guard();owner.restore_account()
                    if owner.process_round():
                        owner.retire_provider();owner.result();return dict(performed=True)
                except FailedPreparationPending:owner.abort.input_guard()
            # The independent SDK actor keeps its own account/resource/Stop
            # ownership. Never wait for it while either source lock is held.
            self.sleep(.1)
        raise AvatarFeaturePending('Failed preparation remains owned; no completed input or Stop is repeated')

    def preparation_cleanup_requested(self):
        from ios.adapters.avatar_paired_failure import prepare
        from ios.adapters.avatar_failed_preparation import FailedPreparationPending
        for _ in range(256):
            with self.held(paired=True):
                self.load()
                if self.state is None or self.state['phase'] not in ('preparing','ready'):return False
                if self.state['phase']=='preparing':return True
                existing=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-abort.json')).read()
                if existing is not None and 'pairedPreparationFailure' in existing:return True
                try:return prepare(self) is not None
                except FailedPreparationPending:pass
            self.cleanup_deadline();self.sleep(.1)
        raise AvatarFeaturePending('Independent preparation outcome remains owned')

    def verify_failed_cleanup_result(self,call,result):
        """Closed post-call verification after an abort has ended its SDKs."""
        from ios.adapters.avatar_failed_preparation import AvatarFailedPreparation
        call=arguments('feature.avatar-people.cleanup',call);need(call['runId']==self.run and result==dict(performed=True))
        with self.held(paired=True):
            self.load();need(self.state is not None and self.state['phase'] in ('preparing','ready'))
            store=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-failed-preparation.json'))
            original=store.read();need(original is not None)
            owner=AvatarFailedPreparation.archive(self,original);proof=owner.original_result()
            need(proof['performed'] and proof['status']=='failed');return True

    def failed_preparation_ended(self):
        """Worker exit uses actual abort originals and preserves failed status."""
        from ios.adapters.avatar_failed_preparation import AvatarFailedPreparation
        with self.held(paired=True):
            self.load()
            if self.state is None or self.state['phase'] not in ('preparing','ready'):return False
            value=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-failed-preparation.json')).read()
            if value is None:return False
            rows=unpack(value['payload']);need(len(rows)==1 and type(rows[0]) is dict)
            if rows[0].get('phase')!='failed-ended':return False
            AvatarFailedPreparation.archive(self,value).original_result();return True

    def restore_inputs(self,call,requested_clock):
        checkpoint_ready=False
        with self.held():
            self.load();need(self.state is not None and self.state['phase'] in ('ready','cleaning'))
            current=self.phase.read();need(current['verb']=='cleanup' and current['status']['instance']==self.state['phaseInstance'])
            source=self.own_source();IOSAvatarSourceRecovery(source).recover()
            if not self.state['cleanup']:
                frame=source.read();baseline=self.state['sessions']['sources'][self.role]
                need(source.frames[baseline['index']-1] and digest(source.frames[baseline['index']-1])==baseline['sha256'])
                self.state['cleanup'].append(dict(kind='admission',ticket=current['ticket'],baseline=deepcopy(baseline),
                    source=dict(index=len(source.frames),sha256=digest(frame)),operationClock=requested_clock))
                self.state['phase']='cleaning';self.save()
            admission=self.state['cleanup'][0];need(admission['kind']=='admission' and admission['ticket']==current['ticket'])
            self.cleanup_deadline()
            self.settle_active_inputs(source)
            controls=self.runtime._avatar_cleanup_controls(self.selector,source)
            for _ in range(16):
                self.cleanup_deadline()
                steps=[row for row in self.state['cleanup'] if row['kind']=='control']
                if steps and not steps[-1]['complete']:
                    step=steps[-1]
                else:
                    IOSAvatarSourceRecovery(source).recover();source.read()
                    history=source_history(source.previous,IOSAvatarSourceRecovery(source).previous,store=source.store,root=source.root,
                        binding=source.binding,run=source.run,role=source.role,lock=source.lock)
                    directory=any(row['complete'] and row['plan']['step']=='connections' for row in steps)
                    plan=cleanup_next(history,admission['baseline']['index'],self.peer(),fixture_url=self.phase.fixture_url,expected_code=pins(),directory_verified=directory)
                    if plan is None:checkpoint_ready=True;break
                    if 'wait' in plan:raise AvatarFeaturePending('Waiting for the original cleanup effect; no completed input is repeated')
                    if steps and same(steps[-1]['plan'],plan):
                        raise AvatarFeaturePending('The completed cleanup input has not established its actual source effect; it is not sent again')
                    step=dict(kind='control',index=len(steps)+1,plan=deepcopy(plan),complete=False)
                    self.state['cleanup'].append(step);self.save()
                with self.runtime.existing_input_session(self.selector):
                    controls.run(call,index=step['index'],whole_clock=admission['operationClock'],**step['plan'])
                step['complete']=True;self.save()
            else:raise AvatarFeaturePending('Avatar cleanup input limit reached; all originals remain retained')
        return checkpoint_ready

    def cleanup_deadline(self):
        state=self.state
        if getattr(self,'final_read_clock',None) is not None:
            need(state is not None and state['phase'] in ('cleaned','terminal-ready'))
            return operation_clock.check(self.final_read_clock,self.epoch_ms(),self.monotonic())
        clock=(state['cleanup'][0]['operationClock'] if state is not None and state.get('cleanup') else self.requested_cleanup_clock)
        return operation_clock.check(clock,self.epoch_ms(),self.monotonic())

    def cleanup_checkpoint(self):
        """Both independent roles retain real bilateral absence before logout."""
        with self.held(paired=True):
            self.load();self.cleanup_deadline();current=self.phase.read()
            need(current['verb']=='cleanup' and current['ticket']==self.state['cleanup'][0]['ticket'])
            parts=self.components(self.source_parts());observer=parts['observer'];observer.recover()
            rows=[row for row in self.state['cleanup'] if row['kind']=='checkpoint']
            if not rows:
                public=observer.checkpoint(len(observer.state['rows']))
                need(same(public['state'],SCENARIOS['avatar-people']['baseline']) and public['resources'])
                event=dict(kind='checkpoint',reference=deepcopy(observer.state['rows'][-1]),published=False,publisher=None)
                self.state['cleanup'].append(event);self.save()
            else:event=rows[0]
            need(same(observer.state['rows'][event['reference']['index']-1],event['reference']))
            proof=observer.validate_original(event['reference'])
            need(proof['ticket']==current['ticket'] and same(proof['public']['state'],SCENARIOS['avatar-people']['baseline']))
            if self.role=='actor' and not event['published']:
                publisher=observer.publisher()
                if not publisher.resolve():raise AvatarFeaturePending('Original cleanup witness remains planned; it is not resent or retimed')
                publisher.publish(event['reference']);need(publisher.resolve() and publisher.state['records'])
                original=publisher.load(publisher.state['records'][-1]);need(original['mode']=='published' and same(original['intent']['original'],event['reference']))
                event.update(published=True,publisher=self.keep(publisher.previous));self.save()

    def cleanup_account(self):
        """Scheduling metadata never replaces either role's product originals."""
        with self.held():
            self.load();self.cleanup_deadline()
            original=PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-avatar-'+self.role+'-login.json')).read()
            need(original is not None)
            try:self.login_history(self.role,original)
            except AvatarFeaturePending:pass
            else:
                # Revocation follows the actual logout and preference originals.
                # Reentry must not reconstruct a ready-only live login runtime
                # or repeat the Actor's already completed live ordering read.
                self.cleanup_deadline();return
        if self.role=='primary':
            with self.held():
                self.load();need(any(row['kind']=='scene' for row in self.state['cleanup']) and any(row['kind']=='actor-scene' for row in self.state['cleanup']))
                event=next(row for row in self.state['cleanup'] if row['kind']=='actor-scene')
                self.reader_history(self.kept(event['owner']),self.scene_stage())
        else:
            self.wait_primary_logout()
        with self.held():
            self.load();self.cleanup_deadline()
            runtime=self.runtime._avatar_login(self.selector,self.authority,self.role,initial=False,lock=self.lock)
            owner=IOSAvatarLoginOwner(runtime,self.selector,self.authority,self.lock,epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
            owner.load();ticket=self.state['cleanup'][0]['ticket']
            if owner.state['phase']=='logged-in':owner.logout(ticket)
            elif owner.state['phase']=='logout-issued':owner.terminal('logout',ticket)
            elif owner.state['phase'] not in ('logged-out','restored'):
                raise AvatarFeaturePending('Original account restoration remains owned and is not repeated')
            if owner.state['phase']=='logged-out':owner.restore_preferences(ticket)
            need(owner.state['phase']=='restored')

    def wait_peer_checkpoint(self):
        """Read a token-free private handoff solely as an ordering barrier.

        No primary fact is normalized as an actor effect. Each participant has
        already independently acquired both product sources in checkpoint().
        """
        from adapters.original_frame_store import OriginalFrameStore
        other='actor' if self.role=='primary' else 'primary'
        path=self.runtime.state_path(self.selectors[other]).with_name('ios-avatar-'+other+'-feature.json')
        for _ in range(251):
            self.cleanup_deadline()
            with self.held(paired=True):
                self.load();events=[row for row in self.state['cleanup'] if row['kind']=='checkpoint-barrier']
                raw=self.kept(events[0]['owner']) if events else PrivateFeatureState(path).read()
                if raw is not None:
                    # The independent private owner is reconstructed without
                    # a runtime/client constructor or a request to either SDK.
                    template=object.__new__(IOSAvatarFeature);template.runtime=self.runtime;template.role=other
                    class Frozen(PrivateFeatureState):
                        def read(_self):return deepcopy(raw)
                        def write(_self,*_args):need(False)
                        def discard(_self,*_args):need(False)
                    template.lock=self.locks[other];template.store=Frozen(path)
                    template.run=self.run
                    template.phase=self.phase;template.selectors=self.selectors;template.selector=template.selectors[other]
                    template.root=Path(raw.get('artifactRoot',''));template.policy=raw.get('imagePolicy')
                    template.load()
                    peer=template.state
                    need(peer is not None and same(peer['bindings'],self.state['bindings'])
                        and peer['phaseInstance']==self.state['phaseInstance'] and peer['initialTicket']==self.state['initialTicket'])
                    rows=[row for row in peer['cleanup'] if row['kind']=='checkpoint']
                    if rows:
                        need(peer['cleanup'][0]['ticket']==self.state['cleanup'][0]['ticket'])
                        ref=rows[0]['reference'];originals=OriginalFrameStore(template.root,self.state['bindings'][other],self.run,other,
                            lambda:True,lambda *_:need(False),namespace='avatar-observation',schema_prefix='avatarObservation')
                        record=originals.read(originals.expand(ref['original']))
                        need(record['index']==ref['index'] and record['ticket']==ref['ticket'] and record['status']==ref['status']=='observed'
                            and record['facts']['phaseInstance']==self.state['phaseInstance'] and record['facts']['ticket']==ref['ticket'])
                        handoff=dict(kind='checkpoint-barrier',subject=other,owner=self.keep(raw),reference=deepcopy(ref),recordSha256=digest(record))
                        if events:need(same(events[0],handoff))
                        else:self.state['cleanup'].append(handoff);self.save()
                        return deepcopy(handoff)
            self.sleep(.1)
        raise AvatarFeaturePending('Waiting for the independently owned original peer checkpoint before closing either scene')

    def wait_actor_checkpoint(self):
        """Read an authenticated existing witness outside both SDK locks."""
        checker=object.__new__(PhaseWitnessPublisher);checker.run,checker.area=self.run,'avatar-people'
        for _ in range(251):
            self.cleanup_deadline();before=self.phase.read();journal=self.client.request('/runs/'+self.run);after=self.phase.read()
            checker.journal(journal)
            need(before['verb']==after['verb']=='cleanup' and before['ticket']==after['ticket']==self.state['cleanup'][0]['ticket']
                and before['status']['instance']==after['status']['instance']==self.state['phaseInstance']
                and same(before['status']['activations'],after['status']['activations']) and journal['ticket']==after['ticket']
                and before['status']['capturedEpochMs']<=journal['sampleEpochMs']<=after['status']['capturedEpochMs'])
            matches=[row for row in journal['entries'] if row['ticket']==after['ticket']
                and same(row['facts'],SCENARIOS['avatar-people']['baseline'])
                and row['capturedEpochMs']>=after['afterEpochMs']]
            if matches:return deepcopy(matches[-1])
            self.sleep(.1)
        raise AvatarFeaturePending('Independent cleanup checkpoint has not been committed')

    def wait_primary_logout(self):
        """The actor reads the genuine primary native account, never a request."""
        from ios.adapters.authentication_causality import check as account_causality,AuthenticationReadinessPending
        for _ in range(251):
            self.cleanup_deadline()
            with self.held(paired=True):
                self.load();self.actual();directory=self.root/'primary-sdk-originals'
                source_path=self.runtime.state_path(self.selectors['primary']).with_name('ios-avatar-'+self.role+'-sources.json')
                source_store=PrivateFeatureState(source_path)
                history=source_history(source_store.read(),PrivateFeatureState(source_path.with_name('ios-avatar-'+self.role+'-source-recovery.json')).read(),
                    store=source_store,root=directory,binding=self.state['bindings']['primary'],run=self.run,role=self.role,lock=self.locks['primary'])
                before=IOSAvatarObserver.reference(history,self.state['sessions']['sources']['primary'])['originals']['native']
                owner=self.runtime._avatar_account_reads(self.selectors['primary'],self.client,self.run,self.role,'primary',directory,self.locks['primary'],
                    epoch_ms=self.epoch_ms,monotonic=self.monotonic)
                row=owner.read();packet=owner.packet(row);status=self.authority.read();child=status['accounts']['primary']['runId']
                call=dict(contractVersion=CONTRACT_VERSION,runId=child,fixtureUrl=self.client.url+'/runs/'+child+'/',
                    ticket=self.state['cleanup'][0]['ticket'],verb='logout',inputs={})
                try:account_causality(call,before,packet,packet['capturedEpochMs'])
                except AuthenticationReadinessPending:pass
                else:
                    if not any(row['kind']=='primary-logout' for row in self.state['cleanup']):
                        # This actual Actor packet bridges the host ordering
                        # into the Actor's own native clock before its logout.
                        actor=self.runtime._avatar_account_reads(self.selector,self.client,self.run,self.role,'actor',self.root,self.lock,
                            epoch_ms=self.epoch_ms,monotonic=self.monotonic)
                        barrier=actor.read();actual=actor.packet(barrier)
                        principal=hashlib.sha256(('e2e-'+status['accounts']['actor']['runId']).encode()).hexdigest()
                        need(actual['account']['loggedIn'] and actual['account']['principalSha256']==principal
                            and barrier['acquisition']['hostBeforeMonotonic']>=row['acquisition']['hostAfterMonotonic']
                            and barrier['acquisition']['hostBeforeEpochMs']>=row['acquisition']['hostAfterEpochMs'])
                        self.state['cleanup'].append(dict(kind='primary-logout',source=owner.reference(row),owner=self.keep(owner.previous),
                            actorSource=actor.reference(barrier),actorOwner=self.keep(actor.previous)));self.save()
                    return
            self.sleep(.1)
        raise AvatarFeaturePending('Waiting for the original primary account logout before actor logout')

    def settle_active_inputs(self,source):
        """Settle an original return passively; never resume an old recipe."""
        own=self.runtime._avatar_actions(self.selector,source,self.peer()) if self.role=='primary' else self.runtime._avatar_consent(
            self.selector,source,self.peer()['sessionId'],'e2e-'+self.state['sessions']['authority']['accounts']['actor']['runId'])
        if own.state is None or not own.state['calls']:return
        row=own.state['calls'][-1]
        if row['phase']=='issuing':raise AvatarFeaturePending('Original UIKit input remains unresolved; cleanup cannot erase that responsibility')
        if not row['inputStarted']:return
        event=own.inputs.state['calls'][-1]['events'][-1];original=event['intent']
        if event['phase']=='issued':
            record=own.input_reads.read();own.inputs.delivered(original,own.input_reads.delivered(record,original))
        if event['phase']!='observed':own.inputs.observed(original,source.readers['ui'].capture())

    def scene_archive(self,event,subject=None,root=None):
        subject=self.role if subject is None else subject
        root=self.root if root is None else Path(root)
        path=self.runtime.state_path(self.selectors[subject]).with_name('ios-avatar-'+subject+'-scene.json')
        from ios.adapters.avatar_held_scene import scene_type
        value=self.kept(event['owner']);Scene=scene_type(value)
        return Scene.archive(value,store=Frozen(path,value),root=root,binding=self.state['bindings'][subject],
            run=self.run,role=subject,lock=self.locks[subject])

    def live_scene(self):
        source=self.own_source()
        scope=self.marker_scope()
        samples=self.runtime._avatar_samples(self.selector,scope,self.client,self.root,self.policy,self.lock)
        from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
        from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
        Scene=IOSAvatarHeldScene if type(scope) is IOSAvatarHeldMarkerScope else IOSAvatarScene
        return Scene(self.runtime,self.selector,source,scope,samples,self.state['cleanup'][0]['baseline'],
            self.state['cleanup'][0]['operationClock'],epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)

    def cleanup_native_scene(self,call):
        with self.held():
            self.load();self.cleanup_deadline();events=[row for row in self.state['cleanup'] if row['kind']=='scene']
            if events:self.scene_archive(events[0]).derive(events[0]['reference']);return
            native=[row for row in self.state['cleanup'] if row['kind']=='native-scene']
            if native:self.native_scene_original(native[0]);return
            # Checkpoint collection can leave one actual People page visible.
            # Leave that exact root with an independently owned Home input.
            source=self.own_source();IOSAvatarSourceRecovery(source).recover();frame=source.read()
            pages=[row for row in frame['ui']['controls'] if row['id'] in ('avatar.page','people.page')]
            if pages:
                need(len(pages)==1 and pages[0]['dialog']=='none');page=pages[0]
                rows=[row for row in self.state['cleanup'] if row['kind']=='control'];controls=self.runtime._avatar_cleanup_controls(self.selector,source)
                if rows and not rows[-1]['complete']:event=rows[-1]
                else:
                    event=dict(kind='control',index=len(rows)+1,plan=dict(step='close-page',inputs=dict(rootId=page['rootId'],page=page['id'].split('.')[0])),complete=False)
                    self.state['cleanup'].append(event);self.save()
                need(event['plan']['step']=='close-page')
                with self.runtime.existing_input_session(self.selector):controls.run(call,index=event['index'],whole_clock=self.state['cleanup'][0]['operationClock'],**event['plan'])
                event['complete']=True;self.save()
            scene=self.live_scene();scene.endpoints()
            value=dict(source=deepcopy(scene.sources.previous),recovery=deepcopy(IOSAvatarSourceRecovery(scene.sources).previous),scope=scene.scope.snapshot(),
                samples=deepcopy(scene.samples.previous),endpoints=deepcopy(scene.state['endpoints']),close=deepcopy(scene.state['close']))
            event=dict(kind='native-scene',owner=self.keep(value));self.native_scene_original(event)
            self.state['cleanup'].append(event);self.save()

    def native_scene_original(self,event):
        """Actual resource/camera endpoints only; no rendered retirement claim."""
        from ios.adapters.avatar_marker_history import archive as marker_archive
        from ios.adapters.avatar_marker_entities import IOSAvatarMarkerEntities
        from ios.adapters.avatar_scene_transports import IOSAvatarFileReceipts
        from ios.adapters.avatar_held_samples import history as samples_history
        from ios.adapters import avatar_cleanup_sources
        value=self.kept(event['owner']);exact(value,{'source','recovery','scope','samples','endpoints','close'})
        source_path=self.store.path.with_name('ios-avatar-'+self.role+'-sources.json')
        history=source_history(value['source'],value['recovery'],store=Frozen(source_path,value['source']),root=self.root,
            binding=self.state['bindings'][self.role],run=self.run,role=self.role,lock=self.lock)
        scope=marker_archive(value['scope'],root=self.root,binding=history.binding,run=self.run,role=self.role,lock=self.lock)
        need(scope.state['phase']=='released' and scope.state['pending'] is None and scope.state['cleanupMode']=='full')
        endpoint=value['endpoints'];exact(endpoint,{'source','entities','files','native'});frame=retained(history,endpoint['source'])
        need(same(frame['clockJoin']['nativeAfter'],endpoint['native']) and value['close']['phase']=='observed' and not frame['ui']['open'])
        baseline=self.state['cleanup'][0]['baseline']
        cleanup=avatar_cleanup_sources.restored_held if value['scope']['iosAvatarMarkerScopeVersion']==2 else avatar_cleanup_sources.restored
        closed=cleanup(history,baseline['index'],endpoint['source']['index'],
            fixture_url=self.phase.fixture_url,expected_code=pins())
        path=self.store.path.with_name('ios-avatar-'+self.role+'-marker-entities.json')
        entities=IOSAvatarMarkerEntities.archive(endpoint['entities'],store=Frozen(path,endpoint['entities']),root=self.root,binding=history.binding,
            run=self.run,role=self.role,lock=self.lock);entities.closed(scope)
        weak=avatar_cleanup_sources.wearable_lifetimes(history,baseline['index'],endpoint['source']['index'],entities.original(entities.state['records'][0])['packet'],
            entities.latest()['packet'],fixture_url=self.phase.fixture_url,expected_code=pins())
        path=self.store.path.with_name('ios-avatar-'+self.role+'-file-receipts.json')
        files=IOSAvatarFileReceipts.archive(endpoint['files'],store=Frozen(path,endpoint['files']),root=self.root,binding=history.binding,
            run=self.run,role=self.role,lock=self.lock);need(files.state['pending'] is None and files.state['records'])
        last=files.original(files.state['records'][-1]);need(last['kind']=='absent' and same(last['ownership'],scope.state['fileOwnership']))
        follow(entities.latest()['clockJoin']['nativeAfter'],last['clockJoin']['nativeBefore']);follow(last['clockJoin']['nativeAfter'],frame['clockJoin']['nativeBefore'])
        need(endpoint['native']['capturedEpochMs']>=max(closed['endpointEpochMs'],weak['endpointEpochMs']))
        samples=samples_history(value['samples'],store=Frozen(self.store.path.with_name('ios-avatar-'+self.role+'-samples.json'),value['samples']),
            root=self.root,binding=history.binding,run=self.run,role=self.role,policy=self.policy,lock=self.lock)
        need(samples.state['pending'] is None)
        for row in samples.state['rows']:
            if row['status']!='abandoned':samples.archive(row)
        baseline=scope.frames[scope.state['baseline']-1];current=scope.frames[-1]
        scope.components.view_preserved(baseline['world'],current['world']);scope.components.body_preserved(baseline['world'],current['world'])
        return dict(original=value,frame=frame)

    def wait_peer_native_scene(self):
        other='actor' if self.role=='primary' else 'primary';path=self.runtime.state_path(self.selectors[other]).with_name('ios-avatar-'+other+'-feature.json')
        for _ in range(251):
            self.cleanup_deadline()
            with self.held(paired=True):
                self.load();saved=[row for row in self.state['cleanup'] if row['kind']=='native-scene-barrier']
                raw=self.kept(saved[0]['owner']) if saved else PrivateFeatureState(path).read()
                if raw is not None:
                    peer=IOSAvatarFeature.archive(self.runtime,raw,self.client,self.locks)
                    need(same(peer.state['bindings'],self.state['bindings']) and peer.state['phaseInstance']==self.state['phaseInstance']
                        and peer.state['cleanup'][0]['ticket']==self.state['cleanup'][0]['ticket'])
                    candidates=[row for row in peer.state['cleanup'] if row['kind']=='native-scene']
                    if candidates:
                        peer.native_scene_original(candidates[0]);event=dict(kind='native-scene-barrier',subject=other,owner=self.keep(raw))
                        if saved:need(same(saved[0],event))
                        else:self.state['cleanup'].append(event);self.save()
                        return
            self.sleep(.1)
        raise AvatarFeaturePending('Both actual native camera/resource endpoints must precede cleanup pixels')

    def cleanup_scene(self,call):
        with self.held():
            self.load();self.cleanup_deadline();events=[row for row in self.state['cleanup'] if row['kind']=='scene']
            if events:self.scoped_scene(events[0]).derive(self.kept(events[0]['scoped']));return
            need(any(row['kind']=='native-scene-barrier' for row in self.state['cleanup']))
            scene=self.live_scene();observer=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-observer.json')).read()
            cursor=len(unpack(observer['payload'])[0]['rows'])
            ref=scene.capture(ticket=self.state['cleanup'][0]['ticket'],phase_instance=self.state['phaseInstance'],sequence=cursor+len(scene.state['records'])+1)
            scene.derive(ref);login=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-login.json')).read()
            event=dict(kind='scene',reference=deepcopy(ref),owner=self.keep(scene.previous),login=self.keep(login))
            scoped=self.scoped_scene(event);event['scoped']=self.keep(scoped.original(ref));scoped.derive(self.kept(event['scoped']))
            self.state['cleanup'].append(event);self.save()

    def scoped_scene(self,event):
        from ios.adapters.avatar_scoped_scene import AvatarScopedScene
        from ios.adapters.avatar_login_lifetime import AvatarLoginLifetime
        lifetime=AvatarLoginLifetime(self.kept(event['login']),binding=self.state['bindings'][self.role],run=self.run,
            child_run=self.state['sessions']['authority']['accounts'][self.role]['runId'],role=self.role,authority=self.authority)
        scene=self.scene_archive(event)
        if scene.VERSION==2:
            from ios.adapters.avatar_held_scoped_scene import AvatarHeldScopedScene
            return AvatarHeldScopedScene(scene,lifetime)
        return AvatarScopedScene(scene,lifetime)

    def wait_peer_scene(self):
        """Private actual Scene originals order publication; neither is a fact ACK."""
        other='actor' if self.role=='primary' else 'primary'
        path=self.runtime.state_path(self.selectors[other]).with_name('ios-avatar-'+other+'-feature.json')
        for _ in range(251):
            self.cleanup_deadline()
            with self.held(paired=True):
                self.load();saved=[row for row in self.state['cleanup'] if row['kind']=='scene-barrier']
                raw=self.kept(saved[0]['owner']) if saved else PrivateFeatureState(path).read()
                if raw is not None:
                    template=IOSAvatarFeature.archive(self.runtime,raw,self.client,self.locks)
                    need(same(template.state['bindings'],self.state['bindings']) and template.state['phaseInstance']==self.state['phaseInstance'])
                    rows=[row for row in template.state['cleanup'] if row['kind']=='scene']
                    if rows:
                        need(template.state['cleanup'][0]['ticket']==self.state['cleanup'][0]['ticket'])
                        scene=template.scene_archive(rows[0]);proof=template.scoped_scene(rows[0]).derive(template.kept(rows[0]['scoped']));need(proof['ticket']==self.state['cleanup'][0]['ticket'])
                        event=dict(kind='scene-barrier',subject=other,owner=self.keep(raw),reference=deepcopy(rows[0]['reference']),recordSha256=digest(scene.record(rows[0]['reference'])))
                        if saved:need(same(saved[0],event))
                        else:self.state['cleanup'].append(event);self.save()
                        return
            self.sleep(.1)
        raise AvatarFeaturePending('Waiting for both original Scene-ready owners before the once Scene publication')

    def retirement_original(self,value):
        exact(value,{'kind','reference'});need(value['kind'] in ('scene','complete'))
        if value['kind']=='scene':
            event=next(row for row in self.state['cleanup'] if row['kind']=='scene-publication')
            need(same(value['reference'],event['reference']));return self.scoped_scene(event).derive(self.kept(event['scoped']))
        event=next(row for row in self.state['cleanup'] if row['kind']=='complete-publication')
        need(same(value['reference'],event['references'][-1]));return self.final_proof(event)

    def scene_version(self,event=None):
        if event is None:event=next(row for row in self.state['cleanup'] if row['kind']=='scene')
        version=self.kept(event['owner'])['iosAvatarSceneVersion']
        need(type(version) is int and version in (1,2));return version

    def scene_stage(self,event=None):
        version=self.scene_version(event)
        if version==2:
            from feature_journeys.retirement_receipts import AVATAR_HELD_STAGE
            return AVATAR_HELD_STAGE
        need(version==1);return SCENE_STAGE

    def scene_publisher(self):
        self.lock.assert_held();need(self.role=='actor');self.phase.read()
        return PhaseRetirementPublisher(PrivateFeatureState(self.store.path.with_name('phase-retirement-avatar-people-'+self.run+'-actor.json')),
            self.state['bindings']['actor'],self.phase,self.lock,self.cleanup_deadline,self.retirement_original,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic,stage=self.scene_stage())

    def publish_scene(self):
        with self.held():
            self.load();self.cleanup_deadline();events=[row for row in self.state['cleanup'] if row['kind']=='scene-publication']
            if not events:
                scene=self.live_scene();previous=scene.derive(scene.state['records'][-1]);ref=scene.refresh(ticket=self.state['cleanup'][0]['ticket'],
                    phase_instance=self.state['phaseInstance'],sequence=previous['scene']['sequence']+1)
                admitted=next(row for row in self.state['cleanup'] if row['kind']=='scene')
                event=dict(kind='scene-publication',reference=deepcopy(ref),owner=self.keep(scene.previous),login=deepcopy(admitted['login']),published=False,publisher=None)
                event['scoped']=self.keep(self.scoped_scene(event).original(ref))
                self.state['cleanup'].append(event);self.save()
            else:event=events[0]
            publisher=self.scene_publisher();resolved=publisher.resolve()
            if not resolved:raise AvatarFeaturePending('Original Scene publication remains issued; it is never sent again')
            if not event['published']:
                publisher.publish(dict(kind='scene',reference=event['reference']))
                need(publisher.resolve() and publisher.state['records'])
                record=publisher.load(publisher.state['records'][-1]);need(record['mode']=='published' and record['entry']['stage']==self.scene_stage(event))
                event.update(published=True,publisher=self.keep(publisher.previous));self.save()

    def wait_actor_scene(self):
        need(self.role=='primary')
        for _ in range(251):
            self.cleanup_deadline()
            with self.held():
                self.load();events=[row for row in self.state['cleanup'] if row['kind']=='actor-scene']
                if events:return
                binding,admission,instance=deepcopy(self.state['bindings']['primary']),deepcopy(self.state['peerAdmission']),self.state['phaseInstance']
                stage,ticket=self.scene_stage(),self.state['cleanup'][0]['ticket']
            # No SDK source lock is held while waiting for the actor.
            self.phase.read()
            def admitted(original):return dict(runId=self.run,phaseInstance=instance,binding=peer_admission(original,binding))
            reader=PhaseRetirementReader(PrivateFeatureState(self.store.path.with_name('ios-avatar-primary-actor-scene.json')),binding,self.phase,
                self.cleanup_deadline,admission,admitted,epoch_ms=self.epoch_ms,monotonic=self.monotonic,stage=stage)
            try:reader.read()
            except PublicationPending:self.sleep(.1);continue
            with self.held():
                self.load();need(not any(row['kind']=='actor-scene' for row in self.state['cleanup']))
                need(same(binding,self.state['bindings']['primary']) and same(admission,self.state['peerAdmission'])
                    and instance==self.state['phaseInstance'] and stage==self.scene_stage()
                    and ticket==self.state['cleanup'][0]['ticket']==reader.state['records'][-1]['entry']['ticket'])
                self.state['cleanup'].append(dict(kind='actor-scene',owner=self.keep(reader.previous)));self.save();return
        raise AvatarFeaturePending('Waiting for a genuine fresh actor Scene receipt before primary logout')

    def cleanup_postlogout(self):
        """Both independent accounts must really logout before model originals."""
        from ios.adapters.authentication_causality import check as account_causality,AuthenticationReadinessPending
        for _ in range(128):
            self.cleanup_deadline();ready=False
            with self.held(paired=True):
                self.load()
                if any(row['kind']=='postlogout' for row in self.state['cleanup']):return
                status=self.authority.read();owners={};rows={};ready=True
                for subject in ROLES:
                    directory=self.root if subject==self.role else self.root/(subject+'-sdk-originals')
                    source_path=self.runtime.state_path(self.selectors[subject]).with_name('ios-avatar-'+self.role+'-sources.json')
                    raw=PrivateFeatureState(source_path).read();history=source_history(raw,
                        PrivateFeatureState(source_path.with_name('ios-avatar-'+self.role+'-source-recovery.json')).read(),store=Frozen(source_path,raw),
                        root=directory,binding=self.state['bindings'][subject],run=self.run,role=self.role,lock=self.locks[subject])
                    original=IOSAvatarObserver.reference(history,self.state['sessions']['sources'][subject]);child=status['accounts'][subject]['runId']
                    account=self.runtime._avatar_account_reads(self.selectors[subject],self.client,self.run,self.role,subject,directory,self.locks[subject],
                        epoch_ms=self.epoch_ms,monotonic=self.monotonic);sample=account.read();packet=account.packet(sample)
                    call=dict(contractVersion=CONTRACT_VERSION,runId=child,fixtureUrl=self.client.url+'/runs/'+child+'/',ticket=self.state['cleanup'][0]['ticket'],verb='logout',inputs={})
                    try:account_causality(call,original['originals']['native'],packet,packet['capturedEpochMs'])
                    except AuthenticationReadinessPending:ready=False;continue
                    post=self.runtime._avatar_postlogout_reads(self.selectors[subject],self.client,self.run,self.role,subject,directory,self.locks[subject],
                        child_run=child,ticket=self.state['cleanup'][0]['ticket'],baseline=original['originals']['state'],logout_before=original['originals']['native'],
                        epoch_ms=self.epoch_ms,monotonic=self.monotonic)
                    rows[subject]=post.capture();post.proof(rows[subject]);owners[subject]=self.keep(post.previous)
                if ready:
                    self.state['cleanup'].append(dict(kind='postlogout',owners=owners,rows=rows));self.save();return
            self.sleep(.1)
        raise AvatarFeaturePending('Both original accounts/model properties have not settled after ordinary logout')

    def account_surface_tail(self,value=None):
        from ios.adapters.avatar_held_tail import archive as tail_archive
        config=self.final_inputs()[self.role];common=dict(child_run=config['childRunId'],ticket=config['ticket'],baseline=config['baseline'],logout_before=config['logoutBefore'])
        if value is None:
            return self.runtime._avatar_postlogout_tail(self.selector,self.client,self.run,self.role,self.role,Path(config['root']),self.lock,
                epoch_ms=self.epoch_ms,monotonic=self.monotonic,held=self.scene_version()==2,**common)
        return tail_archive(value,store=PrivateFeatureState(config['paths']['tail']),root=Path(config['root']),
            binding=self.state['bindings'][self.role],run=self.run,role=self.role,subject=self.role,lock=self.lock,
            fixture_url=config['fixtureUrl'],**common)

    def cleanup_account_surface(self):
        """Close only the account tablet admitted by our restored login owner."""
        from ios.adapters.avatar_ui_inventory import absent
        with transport_scope(self.cleanup_deadline),self.held(paired=True):
            self.load();self.cleanup_deadline();need(any(row['kind']=='postlogout' for row in self.state['cleanup']))
            events=[row for row in self.state['cleanup'] if row['kind']=='account-close'];tail=self.account_surface_tail();send=False
            if not events:
                login=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-login.json')).read();state=self.login_history(self.role,login)
                tail.recover();row=tail.read();raw=tail.record(row['reference'])['widgetsReceipt']['observation'];prior=state['restoration']['receipt']['observation']
                need(raw['instance']==prior['instance'] and raw['lastSequence']==prior['lastSequence']
                    and {(item['id'],item['token']) for item in raw['controls']}=={(item['id'],item['token']) for item in prior['controls']}
                    and absent(raw) and not any(item['id'] in ('login.page','avatar.page','people.page','scripts.page') for item in raw['controls']))
                opened=raw['tabletShown'];event=dict(kind='account-close',phase='issued' if opened else 'observed',input=opened,
                    login=self.keep(login),beforeOwner=self.keep(tail.previous),before=deepcopy(row['reference']),afterOwner=None,after=None)
                if not opened:tail.proof(row);event.update(afterOwner=event['beforeOwner'],after=deepcopy(event['before']))
                self.state['cleanup'].append(event);self.save();send=opened
            else:
                event=events[0]
                # Unknown delivery is never replayed. Only independently fresh
                # native absence below can settle this admitted close.
            if send:
                actual=self.runtime._sources(self.selector);need(same(actual['binding'],self.state['bindings'][self.role]))
                def continuous():self.cleanup_deadline();need(actual['check']() is not False);self.cleanup_deadline();return True
                sdk=NativeUI(actual['client'],actual['session'],continuous,monotonic=self.monotonic,sleep=self.sleep)
                from adapters.normal_ui import Locator
                with self.runtime.existing_input_session(self.selector):sdk.click(Locator('accessibility id','OverteTabletClose'))
                event['phase']='delivered';self.save()
            if event['phase'] in ('issued','delivered'):
                tail.recover();row=tail.read();current=tail.record(row['reference']);ui=tail.geometry(current)['nativeUi']
                if current['widgetsReceipt']['observation']['tabletShown'] or ui['keyboardVisible'] or ui['imeInsetBottom']!=0:
                    raise AvatarFeaturePending('The actual account tablet or UIKit keyboard has not finished closing')
                tail.proof(row);event.update(phase='observed',afterOwner=self.keep(tail.previous),after=deepcopy(row['reference']));self.save()
            self.account_surface_original(event)

    def account_surface_original(self,event=None):
        from ios.adapters.authentication_causality import check as account_causality
        from ios.adapters.avatar_ui_inventory import absent
        if event is None:event=next(row for row in self.state['cleanup'] if row['kind']=='account-close')
        need(event['phase']=='observed');login=self.login_history(self.role,self.kept(event['login']))
        before=self.account_surface_tail(self.kept(event['beforeOwner']));after=self.account_surface_tail(self.kept(event['afterOwner']))
        original=before.record(event['before']);current=after.record(event['after']);a=original['widgetsReceipt']['observation'];b=current['widgetsReceipt']['observation']
        need(type(event['input']) is bool and event['input']==a['tabletShown'] and not b['tabletShown'] and absent(a) and absent(b))
        old=login['restoration']['receipt']['observation'];need(a['instance']==old['instance'] and a['lastSequence']==old['lastSequence']
            and {(row['id'],row['token']) for row in a['controls']}=={(row['id'],row['token']) for row in old['controls']})
        if event['input']:
            need(event['before']!=event['after']);after.widget_prefix(a,b);follow(original['clockJoin']['nativeAfter'],current['clockJoin']['nativeBefore'])
        else:need(same(event['before'],event['after']) and same(event['beforeOwner'],event['afterOwner']))
        follow(login['samples'][-1],original['clockJoin']['nativeBefore'])
        row=next(row for row in after.state['rows'] if row['reference']==event['after']);after.proof(row)
        config=self.final_inputs()[self.role];call=dict(contractVersion=CONTRACT_VERSION,runId=config['childRunId'],fixtureUrl=config['fixtureUrl'],ticket=config['ticket'],verb='logout',inputs={})
        for packet in (original['clockJoin']['nativeBefore'],original['clockJoin']['nativeAfter']):
            account_causality(call,config['logoutBefore'],packet,packet['capturedEpochMs'])
        return current

    def cleanup_authority(self):
        """Revoke actual grants only after both native logout/property originals.

        Final DELETE of the fixture remains with its existing run owner. The
        disabled, drained controlled account records are no native session.
        """
        with self.held():
            self.load();self.cleanup_deadline();need(any(row['kind']=='postlogout' for row in self.state['cleanup']))
            events=[row for row in self.state['cleanup'] if row['kind']=='accounts-retired']
            if self.role=='primary':
                if not events:
                    before=self.authority.read();self.state['cleanup'].append(dict(kind='accounts-retired',before=self.keep(before),phase='issued',after=None));self.save()
                    self.client.request('/runs/'+self.run+'/avatar/control',dict(operation='revoke'),method='POST')
                event=next(row for row in self.state['cleanup'] if row['kind']=='accounts-retired')
            else:event=None
            status=self.authority.read()
            if status['phase']!='revoking':raise AvatarFeaturePending('Original authority revoke is unresolved; it is never sent again')
            need(all(not row['grantsEnabled'] and not row['armedHold'] and all(row[key]==0 for key in
                ('heldRequests','inflightRequests','accessTokens','refreshTokens')) for row in status['accounts'].values()))
            if event is not None:event.update(phase='retired',after=self.keep(status));self.save()
            return status

    def final_inputs(self,*,version=1):
        """Use our immutable checkpoint sources, never current fixed metadata.

        The independent role may already have archived its own fixed channel.
        The source DTO and original files remain unchanged and are revalidated
        here; the full checkpoint fact join is repeated by final_proof().
        """
        need(type(version) is int and version in (1,2));record=self.checkpoint_record();result={}
        for subject in ROLES:
            directory=self.root if subject==self.role else self.root/(subject+'-sdk-originals')
            base=self.runtime.state_path(self.selectors[subject]);value=record['components']['sources'][subject]
            source_path=base.with_name('ios-avatar-'+self.role+'-sources.json')
            history=source_history(value['owner'],value['recovery'],store=Frozen(source_path,value['owner']),root=directory,
                binding=self.state['bindings'][subject],run=self.run,role=self.role,lock=self.locks[subject])
            initial=IOSAvatarObserver.reference(history,self.state['sessions']['sources'][subject])
            child=self.state['sessions']['authority']['accounts'][subject]['runId']
            result[subject]=dict(root=str(directory),paths=dict(post=str(base.with_name('ios-avatar-'+self.role+'-'+subject+'-postlogout.json')),
                tail=str(base.with_name('ios-avatar-'+self.role+'-'+subject+'-postlogout-tail.json')),pointers=str(base.with_name('ios-avatar-'+self.role+'-pointers.json'))),
                childRunId=child,fixtureUrl=self.client.url+'/runs/'+child+'/',ticket=self.state['cleanup'][0]['ticket'],
                baseline={key:deepcopy(initial['originals'][key]) for key in ('state','scripts','http')},logoutBefore=deepcopy(initial['originals']['native']))
            if version==2:
                result[subject]['markerFixtureUrl']=self.phase.fixture_url
                result[subject]['paths']['web']=str(base.with_name('ios-avatar-'+self.role+'-marker-web.json'))
        return result

    def final_owner(self,*,value=None):
        from ios.adapters.avatar_held_final import final_type,IOSAvatarHeldFinal
        store=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-final.json'))
        original=value if value is not None else store.read();mode=self.scene_version()
        Final=(IOSAvatarHeldFinal if mode==2 else IOSAvatarFinal) if original is None else final_type(original)
        version=Final.VERSION;need(version==mode);inputs=self.final_inputs(version=version)
        if value is not None:return Final.archive(value,store=store,root=self.root,bindings=self.state['bindings'],run=self.run,role=self.role,
            locks=self.locks,authority=self.authority,inputs=inputs)
        def factory(subject):
            config=inputs[subject];selector=self.selectors[subject];lock=self.locks[subject]
            common=dict(child_run=config['childRunId'],ticket=config['ticket'],logout_before=config['logoutBefore'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            post=self.runtime._avatar_postlogout_reads(selector,self.client,self.run,self.role,subject,Path(config['root']),lock,baseline=config['baseline']['state'],**common)
            tail=self.runtime._avatar_postlogout_tail(selector,self.client,self.run,self.role,subject,Path(config['root']),lock,baseline=config['baseline'],held=version==2,**common)
            actual=self.runtime._sources(selector);need(same(actual['binding'],self.state['bindings'][subject]));clock=actual['clock_source']
            pointer=IOSAvatarPointers(PrivateFeatureState(config['paths']['pointers']),Path(config['root']),self.state['bindings'][subject],self.run,self.role,lock,
                actual['check'],native=clock,pointer=actual['observer'].pointer_state(clock),epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            result=dict(post=post,tail=tail,pointers=pointer)
            if version==2:
                result['web']=self.runtime._avatar_marker_web_receipts(selector,self.client,self.run,self.role,Path(config['root']),lock,
                    fixture_url=config['markerFixtureUrl'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            return result
        return Final(store,self.root,self.state['bindings'],self.run,self.role,self.locks,self.cleanup_deadline,factory,self.authority,inputs,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)

    def final_sequence(self,owner):
        scenes=[row for row in self.state['cleanup'] if row['kind'] in ('scene','scene-publication')];need(scenes)
        last=max(self.scene_archive(row).derive(row['reference'])['scene']['sequence'] for row in scenes)
        return last+len(owner.state['rows'])+1

    def cleanup_final(self):
        for _ in range(40):
            if self.cleanup_final_round():return
            self.sleep(.2)
        raise AvatarFeaturePending('The two original account/UI/model/pointer sources have not established final quiet')

    def cleanup_final_round(self):
        """One owned passive round; the original cleanup deadline never renews."""
        with self.held(paired=True):
            self.load();self.cleanup_deadline()
            ready=[row for row in self.state['cleanup'] if row['kind']=='final-ready']
            if ready:self.terminal_live_proof(ready[0]);return True
            owner=self.final_owner();owner.recover();ref=owner.capture(ticket=self.state['cleanup'][0]['ticket'],phase_instance=self.state['phaseInstance'],
                sequence=self.final_sequence(owner));refs=[row['reference'] for row in owner.state['rows'] if row['reference'] is not None]
            if len(refs)>=3:
                # Too short a real window is the only retry condition. All
                # source/ownership failures remain failed, retained reads.
                first,last=owner.record(refs[0]),owner.record(refs[-1]);duration=last['acquisition']['hostBeforeMonotonic']-first['acquisition']['hostAfterMonotonic']
                if duration>=3:
                    event=dict(kind='final-ready',owner=self.keep(owner.previous),references=deepcopy(refs),inputs=self.keep(self.final_ownership()))
                    self.terminal_live_proof(event);self.state['cleanup'].append(event);self.save();owner.fresh(last);return True
            return False

    def final_ownership(self):
        """Immutable token-free snapshots; no client or runtime call is made."""
        result={}
        for subject in ROLES:
            path=self.runtime.state_path(self.selectors[subject])
            result[subject]=dict(login=PrivateFeatureState(path.with_name('ios-avatar-'+subject+'-login.json')).read())
        own=self.runtime.state_path(self.selector)
        result[self.role].update(active=PrivateFeatureState(own.with_name('ios-avatar-'+self.role+('-actions' if self.role=='primary' else '-consent')+'.json')).read(),
            inputs=PrivateFeatureState(own.with_name('ios-avatar-'+self.role+'-inputs.json')).read(),
            controls=PrivateFeatureState(own.with_name('ios-avatar-'+self.role+'-cleanup-controls.json')).read(),
            cleanupInputs=PrivateFeatureState(own.with_name('ios-avatar-'+self.role+'-cleanup-inputs.json')).read(),
            inputReads=PrivateFeatureState(own.with_name('ios-avatar-'+self.role+'-input-reads.json')).read(),
            surfaces={subject:PrivateFeatureState(self.runtime.state_path(self.selectors[subject]).with_name(
                'ios-avatar-'+self.role+'-'+subject+'-surface.json')).read() for subject in ROLES})
        return result

    def login_history(self,subject,value):
        from ios.adapters.authentication_origin import origin
        from ios.adapters.account_preferences import validate_basis
        child=self.state['sessions']['authority']['accounts'][subject]['runId'];endpoint=origin(self.client.url)
        owner=object.__new__(IOSAvatarLoginOwner);owner.run,owner.child,owner.role=self.run,child,subject
        owner.authority=self.authority;owner.runtime=SimpleNamespace(origin=endpoint);owner.principal=hashlib.sha256(('e2e-'+child).encode()).hexdigest()
        owner.endpoints={hashlib.sha256(v.encode()).hexdigest() for v in (endpoint,endpoint+'/')}
        state=owner.decode(value)
        if state['phase']!='restored':raise AvatarFeaturePending('The actual controlled account preference restoration is not complete')
        need(same(state['binding'],self.state['bindings'][subject]) and state['samples'][0]['account']['loggedIn'] is False
            and all(row['phase']=='complete' for row in state['protected']))
        validate_basis(state['preferences'],endpoint);return state

    def input_history(self,event,scene):
        from ios.adapters.avatar_actions import IOSAvatarActions
        from ios.adapters.avatar_consent import IOSAvatarConsent
        from ios.adapters.avatar_cleanup_controls import IOSAvatarCleanupControls
        from ios.adapters.avatar_cleanup_inputs import AvatarCleanupInputOwner
        from ios.adapters.avatar_input_owner import AvatarInputOwner
        from ios.adapters.avatar_input_reads import IOSAvatarInputReads
        history=scene.sources;need(history.historical);original=self.kept(event['inputs'])[self.role];other='actor' if self.role=='primary' else 'primary'
        peer=dict(sessionId=self.state['sessions']['input']['sessions'][other],username='e2e-'+self.state['sessions']['authority']['accounts'][other]['runId'])
        inputs=AvatarInputOwner(Frozen(self.store.path.with_name('ios-avatar-'+self.role+'-inputs.json'),original['inputs']),self.lock,
            self.state['bindings'][self.role],self.run,self.role,self.phase.fixture_url,lambda:True);inputs.load()
        if original['active'] is not None:
            if self.role=='primary':active=IOSAvatarActions.history(original['active'],original['inputs'],history,fixture_url=self.phase.fixture_url,peer=peer,expected_code=pins())
            else:
                active=object.__new__(IOSAvatarConsent);active.sources=copy(history);active.sources.phase=SimpleNamespace(fixture_url=self.phase.fixture_url)
                active.peer,active.username,active.origin=peer['sessionId'],'e2e-'+self.state['sessions']['authority']['accounts']['actor']['runId'],self.client.url.split('/feature-fixture/')[0]
                active.state=active.decode(original['active']);owned=[row for row in active.state['calls'] if row['inputStarted']]
                need(len(owned)==len(inputs.state['calls']))
                for call,actual in zip(owned,inputs.state['calls']):
                    need(same(call['query'],actual['arguments']))
                    for row in actual['events']:
                        if row['intent']['controlId'] in ('people.accept','people.decline'):active.invitation_reference(call,row['intent']['reference'],row['intent']['controlId'])
                        elif row['intent']['controlId']=='people.cancel':active.terminal_reference(call,row['intent']['reference'])
            need(all(row['phase']!='issuing' and all(item['after'] is not None for item in row['sdk']) for row in active.state['calls']))
        else:need(not inputs.state['calls'])
        cleanup=AvatarCleanupInputOwner(Frozen(self.store.path.with_name('ios-avatar-'+self.role+'-cleanup-inputs.json'),original['cleanupInputs']),self.lock,
            self.state['bindings'][self.role],self.run,self.role,self.phase.fixture_url,lambda:True);cleanup.load()
        if original['controls'] is not None:
            owner=object.__new__(IOSAvatarCleanupControls);owner.sources=copy(history);owner.sources.phase=SimpleNamespace(fixture_url=self.phase.fixture_url)
            state=owner.decode(original['controls']);need(all(row['phase']=='acknowledged' for row in state['calls'])
                and len(cleanup.state['calls'])==sum(row['inputStarted'] for row in state['calls']))
            for whole,actual in zip((row for row in state['calls'] if row['inputStarted']),cleanup.state['calls']):need(same(whole['query'],actual['arguments']) and actual['phase']=='acknowledged')
        else:need(not cleanup.state['calls'])
        roots=set()
        for ledger in (inputs,cleanup):
            for call in ledger.state['calls']:
                for row in call['events']:
                    need(row['phase']=='observed')
                    pages=[control for control in row['intent']['reference']['controls'] if control['id'] in ('avatar.page','people.page')]
                    for page in pages:roots.add(page['rootId'])
                    if row['intent']['controlId'] in ('avatar.entry','people.entry'):
                        kind=row['intent']['controlId'].split('.')[0]
                        admitted=[frame for frame in history.frames if frame['ui']['scope']['capturedEpochMs']>=row['delivery']['originalReceipt']['status']['sampleEpochMs']
                            and any(control['id']==kind+'.page' for control in frame['ui']['controls'])]
                        need(admitted)
                        for frame in admitted:
                            for control in frame['ui']['controls']:
                                if control['id']==kind+'.page':roots.add(control['rootId'])
        # Observer navigation and the Actor's exact cancelled-terminal close
        # have independent durable ownership. They cannot disappear merely
        # because active action and cleanup input ledgers are complete.
        exact(original['surfaces'],set(ROLES));checkpoint=self.checkpoint_record()
        for subject,value in original['surfaces'].items():
            component=checkpoint['components']['sources'][subject]
            directory=self.root if subject==self.role else self.root/(subject+'-sdk-originals')
            source=history if subject==self.role else source_history(component['owner'],component['recovery'],
                store=PrivateFeatureState(self.runtime.state_path(self.selectors[subject]).with_name('ios-avatar-'+self.role+'-sources.json')),
                root=directory,binding=self.state['bindings'][subject],run=self.run,role=self.role,lock=self.locks[subject])
            need(value is not None);surface=object.__new__(IOSAvatarSurface)
            surface.sources,surface.observer_role,surface.subject_role=source,self.role,subject
            state=surface.decode(value);need(all(call['phase']=='ready' and all(event['after'] is not None for event in call['sdk'])
                and all(event['observed'] is not None for event in call['events']) for call in state['calls']))
            admitted_roots=set()
            for call in state['calls']:
                for item in call['events']:
                    before=item['intent']['reference'];admitted_roots.update(row['rootId'] for row in before['controls'] if row['id'] in ('avatar.page','people.page'))
                    if item['intent']['controlId']=='people.entry':
                        after=item['observed'];page=next((row for row in after['controls'] if row['id']=='people.page'),None)
                        need(page is not None);admitted_roots.add(page['rootId'])
            observed_roots={root['rootId'] for frame in source.frames for root in frame['originals']['widgets'].get('avatarInventory',{}).get('roots',[])}
            need(admitted_roots<=observed_roots)
            if subject==self.role:roots.update(admitted_roots)
        seen={root['rootId'] for frame in history.frames for root in frame['originals']['widgets'].get('avatarInventory',{}).get('roots',[])}
        need(roots<=seen)
        if original['inputReads'] is not None:
            reads=IOSAvatarInputReads(Frozen(self.store.path.with_name('ios-avatar-'+self.role+'-input-reads.json'),original['inputReads']),self.root,
                self.state['bindings'][self.role],self.run,self.role,self.lock,lambda:True,historical=True);need(reads.state['pending'] is None)
            need(all(row['original'] is None or row['original']['phase']=='saved' for row in reads.state['rows']))
        return roots

    def checkpoint_record(self):
        from adapters.original_frame_store import OriginalFrameStore
        for lock in self.locks.values():lock.assert_held()
        event=next(row for row in self.state['cleanup'] if row['kind']=='checkpoint');ref=event['reference']
        observer=object.__new__(WholeAvatarObserver)
        observer.root,observer.binding,observer.run,observer.role,observer.lock=self.root,self.state['bindings'][self.role],self.run,self.role,self.lock
        observer.originals=OriginalFrameStore(self.root,self.state['bindings'][self.role],self.run,self.role,lambda:True,lambda *_:need(False),
            namespace='avatar-observation',schema_prefix='avatarObservation')
        record=observer.read_record(ref);need(record['status']=='observed' and record['ticket']==self.state['cleanup'][0]['ticket'])
        return record

    def checkpoint_observer(self):
        """Re-derive our own nine-fact checkpoint from original private files.

        The peer checkpoint barrier only orders closure. It cannot replace
        either participant's independently captured bilateral effects.
        """
        from adapters.original_frame_store import OriginalFrameStore
        from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
        for lock in self.locks.values():lock.assert_held()
        event=next(row for row in self.state['cleanup'] if row['kind']=='checkpoint');ref=event['reference']
        observer=object.__new__(WholeAvatarObserver)
        observer.root,observer.binding,observer.run,observer.role,observer.lock=self.root,self.state['bindings'][self.role],self.run,self.role,self.lock
        observer.authority,observer.expected_code=self.authority,pins()
        observer.originals=OriginalFrameStore(self.root,observer.binding,self.run,self.role,lambda:True,lambda *_:need(False),
            namespace='avatar-observation',schema_prefix='avatarObservation')
        record=observer.read_record(ref);need(record['status']=='observed')
        observer.sources,observer.peers={},{}
        for subject in ROLES:
            directory=self.root if subject==self.role else self.root/(subject+'-sdk-originals')
            base=self.runtime.state_path(self.selectors[subject]);binding=self.state['bindings'][subject];lock=self.locks[subject]
            value=record['components']['sources'][subject]
            observer.sources[subject]=source_history(value['owner'],value['recovery'],
                store=PrivateFeatureState(base.with_name('ios-avatar-'+self.role+'-sources.json')),root=directory,
                binding=binding,run=self.run,role=self.role,lock=lock)
            value=record['components']['peers'][subject]
            observer.peers[subject]=IOSAvatarPeerSources(Frozen(base.with_name('ios-avatar-'+self.role+'-peer-sources.json'),value['owner']),
                directory,binding,self.run,None,lock,lambda:True,historical=True,role=self.role)
        observer.samples=SimpleNamespace(store=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-samples.json')),policy=self.policy)
        return observer,ref,record

    def checkpoint_original(self):
        observer,ref,record=self.checkpoint_observer();proof=observer.validate_original(ref)
        need(proof['ticket']==self.state['cleanup'][0]['ticket'] and same(proof['public']['state'],SCENARIOS['avatar-people']['baseline'])
            and proof['public']['resources'] and record['facts']['phaseInstance']==self.state['phaseInstance'])
        return record,proof

    def reader_history(self,value,stage):
        """Strict staged receipt reconstruction without a phase/SDK request."""
        binding=self.state['bindings']['primary'];checker=object.__new__(PhaseRetirementReader)
        checker.binding,checker.run,checker.area=binding,self.run,'avatar-people';checker.url=self.client.url;checker.instance=self.state['phaseInstance']
        checker.stage=stage;checker.admitted_original=self.state['peerAdmission'];checker.validate_admission=lambda original:dict(runId=self.run,
            phaseInstance=self.state['phaseInstance'],binding=peer_admission(original,binding));checker.actor=checker.admission()
        state=checker.decode(value);need(state['records'] and state['records'][-1]['entry']['ticket']==self.state['cleanup'][0]['ticket'])
        return state

    @final_checked
    def final_proof(self,event,*,terminal=False):
        return self._final_join(event,terminal=terminal)[0]

    def _final_join(self,event,*,terminal):
        """Return this traversal's proof and already joined Login lifetimes."""
        from ios.adapters.account_preferences import validate_basis
        from ios.adapters.authentication_origin import origin
        preparation=self.preparation_closed_original();initial=self.initial_original()
        follow(preparation['clockJoin']['nativeAfter'],initial['clockJoin']['nativeBefore'])
        owner=self.final_owner(value=self.kept(event['owner']));refs=event['references'];last=owner.record(refs[-1]);proof=owner.quiet(refs,sequence=last['sequence'])
        need(proof['ticket']==self.state['cleanup'][0]['ticket'] and last['phaseInstance']==self.state['phaseInstance'])
        scene_event=next(row for row in self.state['cleanup'] if row['kind']=='scene');scene=self.scene_archive(scene_event);scene_proof,scene_parts=scene.joined(scene_event['reference'])
        self.paired_image_order(scene,scene_event)
        if owner.VERSION==2:
            from ios.adapters.avatar_final_pure_round import scope
            with scope(owner,event,guard=self.final_source_guard(event,owner)):
                lifetimes=self.final_source_lifetimes(event,owner,refs,last,scene,scene_event,validate_basis,origin)
        else:lifetimes=self.final_source_lifetimes(event,owner,refs,last,scene,scene_event,validate_basis,origin)
        markers=self.final_marker_lifetimes(event,owner,scene_event,scene_parts) if owner.VERSION==2 else {subject:[] for subject in ROLES}
        resources=self.lifetime_resources(lifetimes,markers);held=resources[self.role]
        # The legacy complete qualification may not silently discharge an
        # actual cached Login operand. Only the explicit process-end path can
        # carry it forward as retained responsibility.
        need(type(terminal) is bool and (terminal or not any(resources.values())))
        public=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=proof['sequence'],capturedEpochMs=proof['capturedEpochMs'],
            state=deepcopy(SCENARIOS['avatar-people']['baseline']),artifacts=[],resources=[row['resource'] for row in held],lifecycle=deepcopy(proof['lifecycle']))
        result=dict(ticket=proof['ticket'],public=public,acquisition=deepcopy(proof['acquisition']),retirement=dict(originalSha256=proof['originalSha256'],
            quiet=deepcopy(proof['bilateralQuiet'][self.role]),provenance=deepcopy(proof['provenance'])))
        return result,lifetimes,markers

    def final_source_guard(self,event,owner):
        """Exact caller identity for the existing read-only Final2 boundary."""
        need(type(self) is IOSAvatarFeature and type(event) is dict and owner.VERSION==2
            and owner.run==self.run and owner.role==self.role and owner.root==self.root
            and same(owner.bindings,self.state['bindings'])
            and all(owner.locks[role] is self.locks[role] for role in ROLES))
        def callable_identity(value):
            return (id(getattr(value,'__self__',None)),id(getattr(value,'__func__',value)))
        def identity():
            return (type(self),type(self.runtime),id(self.runtime),id(self.runtime.adapter),
                callable_identity(self.runtime.state_path),callable_identity(self.runtime.adapter.state_path),
                type(self.store),id(self.store),str(self.store.path),type(self.client),id(self.client),self.client.url,
                id(self.authority),type(self.authority),id(self.authority.client),self.authority.client.url,self.authority.run,
                tuple((role,id(self.locks[role]),str(self.locks[role].path)) for role in ROLES),
                digest(dict(root=str(self.root),runId=self.run,role=self.role,selector=self.selector,selectors=self.selectors,
                    policy=self.policy,fixtureUrl=self.phase.fixture_url,previous=self.previous,state=self.state,event=event)))
        original=identity()
        def unchanged():
            need(type(self) is IOSAvatarFeature and identity()==original)
            for lock in self.locks.values():lock.assert_held()
            return True
        return unchanged

    def final_source_lifetimes(self,event,owner,refs,last,scene,scene_event,validate_basis,origin):
        """Unchanged original reads and derivations, before peer Scene roots."""
        checkpoint,checkpoint_proof=self.checkpoint_original()
        account_surface=self.account_surface_original()
        for subject in ROLES:
            component=checkpoint['components']['sources'][subject]
            directory=self.root if subject==self.role else self.root/(subject+'-sdk-originals')
            source=source_history(component['owner'],component['recovery'],store=PrivateFeatureState(self.runtime.state_path(self.selectors[subject]).with_name(
                'ios-avatar-'+self.role+'-sources.json')),root=directory,binding=self.state['bindings'][subject],run=self.run,role=self.role,lock=self.locks[subject])
            actual=retained(source,checkpoint['facts']['current'][subject])
            current=owner.group(owner.record(refs[0]))[subject]
            need(current['proof']['iosAvatarPostLogoutTailProofVersion']==(4 if owner.VERSION==2 else 3))
            widgets=current['ui']['widgetsReceipt']['observation'];prior=actual['originals']['widgets']
            need(widgets['instance']==prior['instance'] and widgets['avatarGeneration']==prior['avatarGeneration']
                and widgets['avatarSourceSequence']>prior['avatarSourceSequence'] and widgets['lastSequence']>=prior['lastSequence'])
            follow(actual['originals']['native'],current['left']['clockJoin']['nativeBefore'])
        scene_native=scene.record(scene_event['reference'])['endpoints']['native'];first=owner.group(owner.record(refs[0]));follow(scene_native,first[self.role]['left']['clockJoin']['nativeBefore'])
        follow(account_surface['clockJoin']['nativeAfter'],first[self.role]['left']['clockJoin']['nativeBefore'])
        self.input_history(event,scene)
        for subject in ROLES:
            login=self.login_history(subject,self.kept(event['inputs'])[subject]['login']);actual=owner.group(last)[subject]
            follow(login['samples'][-1],first[subject]['left']['clockJoin']['nativeBefore'])
            widget=actual['ui']['widgetsReceipt'];preferences=widget['observation'].get('accountPreferences')
            basis=validate_basis(dict(binding=self.state['bindings'][subject],receipt=widget,preferences=preferences),origin(self.client.url))
            need(same(basis['preferences'],login['preferences']['preferences']))
        if self.role=='actor':self.actor_logout_order(self.kept(event['inputs'])['actor']['login'])
        return self.final_login_lifetimes(event,owner)

    def final_login_lifetimes(self,event,owner):
        from ios.adapters.avatar_login_lifetime import AvatarLoginLifetime
        from ios.adapters.login_root_ownership import validate
        inputs=self.kept(event['inputs']);result={subject:[] for subject in ROLES}
        for subject in ROLES:
            lifetime=AvatarLoginLifetime(inputs[subject]['login'],binding=self.state['bindings'][subject],run=self.run,
                child_run=self.state['sessions']['authority']['accounts'][subject]['runId'],role=subject,authority=self.authority)
            for reference in event['references']:
                original=owner.record(reference);parts=owner.group(original)[subject];tail=parts['tail']
                index=original['subjects'][subject]['rows']['tail'];ref=tail.state['rows'][index-1]['reference']
                actual=lifetime.tail(tail,ref);need(not actual['ownership']['controls'])
                if result[subject]:
                    previous=result[subject][-1]
                    validate(actual['ownership'],pid=int(lifetime.binding['processIdentity']),previous=previous['ownership'])
                    need(same(actual['heldResources'],previous['heldResources']))
                result[subject].append(actual)
        return result

    @staticmethod
    def lifetime_resources(login,markers):
        from feature_journeys.terminal import held
        result={}
        for subject in ROLES:
            rows=deepcopy(login[subject][-1]['heldResources'])
            if markers[subject]:rows+=deepcopy(markers[subject][-1]['heldResources'])
            rows.sort(key=lambda row:row['resource']);held(rows);result[subject]=rows
        return result

    def final_marker_lifetimes(self,event,owner,scene_event,scene_parts):
        from ios.adapters.avatar_marker_lifetime import AvatarMarkerLifetime
        from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
        need(owner.VERSION==2)
        other='actor' if self.role=='primary' else 'primary';barrier=next(row for row in self.state['cleanup'] if row['kind']=='scene-barrier')
        peer=IOSAvatarFeature.archive(self.runtime,self.kept(barrier['owner']),self.client,self.locks)
        need(peer.role==other and same(peer.state['bindings'],self.state['bindings']) and peer.state['phaseInstance']==self.state['phaseInstance'])
        peer_event=next(row for row in peer.state['cleanup'] if row['kind']=='scene');peer_scene=peer.scene_archive(peer_event)
        need(type(peer_scene) is IOSAvatarHeldScene);_peer_proof,peer_parts=peer_scene.joined(peer_event['reference'])
        contexts={self.role:(scene_event,scene_parts),other:(peer_event,peer_parts)};result={subject:[] for subject in ROLES}
        for subject,(admitted,parts) in contexts.items():
            scope=parts['scope'];need(type(scope) is IOSAvatarHeldScene.Marker)
            frame=scope.frames[parts['original']['quiet'][-1]['scope']-1]
            lifetime=AvatarMarkerLifetime(scope,frame,scene_reference=admitted['reference'],binding=self.state['bindings'][subject],run=self.run)
            for reference in event['references']:
                actual=lifetime.at(owner.group(owner.record(reference))[subject])
                if result[subject]:need(same(actual['heldResources'],result[subject][-1]['heldResources']))
                result[subject].append(actual)
        return result

    @final_checked
    def terminal_live_proof(self,event):
        """Fresh restored facts with actual Login holds, never Complete."""
        proof,lifetimes,markers=self._final_join(event,terminal=True);version=2 if any(markers.values()) else 1
        original=dict(iosAvatarTerminalLiveOriginalVersion=version,runId=self.run,role=self.role,
            bindings=deepcopy(self.state['bindings']),event=deepcopy(event))
        result=dict(iosAvatarTerminalLiveProofVersion=version,original=original,originalSha256=digest(original),
            ticket=proof['ticket'],public=proof['public'],acquisition=proof['acquisition'],loginLifetimes=lifetimes,
            heldResources=self.lifetime_resources(lifetimes,markers))
        if version==2:result['markerLifetimes']=markers
        return result

    def paired_image_order(self,scene,scene_event):
        """Source-bound scheduling across SDK clocks, never peer feature facts."""
        from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
        initial=self.initial_original();barrier=self.state['initialBarrier'];need(barrier is not None)
        peer=IOSAvatarFeature.archive(self.runtime,self.kept(barrier['owner']),self.client,self.locks)
        need(peer.role!=self.role and same(peer.state['bindings'],self.state['bindings']) and peer.state['phaseInstance']==self.state['phaseInstance']
            and same(peer.state['initial']['reference'],barrier['reference']))
        peer_initial=peer.initial_original();scope_before=scene.scope.frames[scene.scope.state['baseline']-1]['clockJoin']
        for frame in (initial,peer_initial):
            need(frame['clockJoin']['hostAfterMonotonic']<=scope_before['hostBeforeMonotonic']
                and frame['clockJoin']['hostAfterEpochMs']<=scope_before['hostBeforeEpochMs'])
        endpoint_barrier=next(row for row in self.state['cleanup'] if row['kind']=='native-scene-barrier')
        other=IOSAvatarFeature.archive(self.runtime,self.kept(endpoint_barrier['owner']),self.client,self.locks)
        need(other.role==peer.role and same(other.state['bindings'],self.state['bindings']) and other.state['phaseInstance']==self.state['phaseInstance'])
        native=other.native_scene_original(next(row for row in other.state['cleanup'] if row['kind']=='native-scene'))
        own_record=scene.record(scene_event['reference']);image=own_record['image']
        frames=IOSAvatarRestorationFrames.archive(image['owner'],store=Frozen(scene.paths['restoration'],image['owner']),root=self.root,
            binding=self.state['bindings'][self.role],run=self.run,role=self.role,lock=self.lock)
        current=frames.frame(image['current'])[0]
        need(native['frame']['clockJoin']['hostAfterMonotonic']<=current['clockJoin']['hostBeforeMonotonic']
            and native['frame']['clockJoin']['hostAfterEpochMs']<=current['clockJoin']['hostBeforeEpochMs'])

    def actor_logout_order(self,login_original):
        from ios.adapters.avatar_account_reads import IOSAvatarAccountReads
        from ios.adapters.authentication_causality import check as account_causality
        event=next(row for row in self.state['cleanup'] if row['kind']=='primary-logout');owners={};rows={}
        for subject,key in (('primary','owner'),('actor','actorOwner')):
            value=self.kept(event[key]);base=self.runtime.state_path(self.selectors[subject]);directory=self.root if subject=='actor' else self.root/'primary-sdk-originals'
            store=Frozen(base.with_name('ios-avatar-actor-'+subject+'-account-reads.json'),value)
            owner=IOSAvatarAccountReads.archive(value,store,directory,self.state['bindings'][subject],self.run,'actor',subject,self.locks[subject])
            ref=event['source' if subject=='primary' else 'actorSource'];row=owner.state['rows'][ref['index']-1]
            need(same(owner.reference(row),ref));owners[subject]=owner;rows[subject]=row
        need(rows['primary']['acquisition']['hostAfterMonotonic']<=rows['actor']['acquisition']['hostBeforeMonotonic']
            and rows['primary']['acquisition']['hostAfterEpochMs']<=rows['actor']['acquisition']['hostBeforeEpochMs'])
        initial=self.final_inputs()['primary']['logoutBefore'];packet=owners['primary'].packet(rows['primary'])
        child=self.state['sessions']['authority']['accounts']['primary']['runId']
        account_causality(dict(contractVersion=CONTRACT_VERSION,runId=child,fixtureUrl=self.client.url+'/runs/'+child+'/',
            ticket=self.state['cleanup'][0]['ticket'],verb='logout',inputs={}),initial,packet,packet['capturedEpochMs'])
        login=self.login_history('actor',login_original);action=next(row for row in login['actions'] if row['verb']=='logout')
        barrier=owners['actor'].packet(rows['actor']);principal=hashlib.sha256(('e2e-'+self.state['sessions']['authority']['accounts']['actor']['runId']).encode()).hexdigest()
        need(barrier['account']['loggedIn'] and barrier['account']['principalSha256']==principal
            and barrier['account']['observation']['tokenPresent'] and barrier['account']['observation']['tokenValid'])
        follow(barrier,login['samples'][action['before']])

    def wait_peer_final(self):
        """Ordering only; the actor's independent SDK originals stay required."""
        other='actor' if self.role=='primary' else 'primary';path=self.runtime.state_path(self.selectors[other]).with_name('ios-avatar-'+other+'-feature.json')
        for _ in range(251):
            self.cleanup_deadline()
            with self.held(paired=True):
                self.load();saved=[row for row in self.state['cleanup'] if row['kind']=='final-barrier'];raw=self.kept(saved[0]['owner']) if saved else PrivateFeatureState(path).read()
                if raw is not None:
                    template=object.__new__(IOSAvatarFeature);template.runtime=self.runtime;template.role=other
                    template.lock=self.locks[other];template.locks=self.locks;template.store=Frozen(path,raw);template.run=self.run;template.phase=self.phase
                    template.client=self.client;template.authority=self.authority;template.selectors=self.selectors;template.selector=template.selectors[other]
                    template.root=Path(raw['artifactRoot']);template.policy=raw['imagePolicy'];template.load()
                    need(same(template.state['bindings'],self.state['bindings']) and template.state['phaseInstance']==self.state['phaseInstance'])
                    rows=[row for row in template.state['cleanup'] if row['kind']=='final-ready']
                    if rows:
                        proof=template.terminal_live_proof(rows[0]);need(proof['ticket']==self.state['cleanup'][0]['ticket']);owner=template.final_owner(value=template.kept(rows[0]['owner']))
                        event=dict(kind='final-barrier',subject=other,owner=self.keep(raw),references=deepcopy(rows[0]['references']),lastSha256=digest(owner.record(rows[0]['references'][-1])))
                        if saved:need(same(saved[0],event))
                        else:self.state['cleanup'].append(event);self.save()
                        return
            self.sleep(.1)
        raise AvatarFeaturePending('Waiting for both independently qualified final owners before the once Complete publication')

    def publish_complete(self):
        with self.held(paired=True):
            self.load();self.cleanup_deadline();events=[row for row in self.state['cleanup'] if row['kind']=='complete-publication']
            if not events:
                owner=self.final_owner();ref=owner.capture(ticket=self.state['cleanup'][0]['ticket'],phase_instance=self.state['phaseInstance'],sequence=self.final_sequence(owner))
                ready=next(row for row in self.state['cleanup'] if row['kind']=='final-ready');event=dict(kind='complete-publication',owner=self.keep(owner.previous),
                    references=[*deepcopy(ready['references']),ref],inputs=self.keep(self.final_ownership()),published=False,publisher=None)
                self.final_proof(event);self.state['cleanup'].append(event);self.save();owner.fresh(owner.record(ref))
            else:event=events[0]
            publisher=self.scene_publisher()
            if not publisher.resolve():raise AvatarFeaturePending('Original Complete publication remains issued; no second POST is allowed')
            if not event['published']:
                publisher.publish(dict(kind='complete',reference=event['references'][-1]));need(publisher.resolve() and publisher.state['records'])
                record=publisher.load(publisher.state['records'][-1]);need(record['mode']=='published' and record['entry']['stage']=='complete')
                event.update(published=True,publisher=self.keep(publisher.previous));self.save()

    def complete_reader(self,value=None):
        self.phase.read();binding=self.state['bindings']['primary'];instance=self.state['phaseInstance']
        def admitted(original):return dict(runId=self.run,phaseInstance=instance,binding=peer_admission(original,binding))
        path=self.store.path.with_name('ios-avatar-primary-actor-complete.json');store=PrivateFeatureState(path) if value is None else Frozen(path,value)
        return PhaseRetirementReader(store,binding,self.phase,self.cleanup_deadline,self.state['peerAdmission'],admitted,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def wait_actor_complete(self):
        need(self.role=='primary')
        for _ in range(251):
            self.cleanup_deadline()
            with self.held():
                self.load();events=[row for row in self.state['cleanup'] if row['kind']=='actor-complete']
                if events:return
            reader=self.complete_reader()
            try:reader.read()
            except PublicationPending:self.sleep(.1);continue
            with self.held():
                self.load();self.state['cleanup'].append(dict(kind='actor-complete',owner=self.keep(reader.previous)));self.save();return
        raise AvatarFeaturePending('Waiting for a genuine actor Complete retirement receipt')

    def completed_original(self):
        self.lock.assert_held();ready=next(row for row in self.state['cleanup'] if row['kind']=='final-ready')
        if self.role=='actor':
            event=next(row for row in self.state['cleanup'] if row['kind']=='complete-publication');need(event['published']);proof=self.final_proof(event)
            publisher=PhaseRetirementPublisher.archive(self.kept(event['publisher']),store=PrivateFeatureState(self.store.path.with_name('phase-retirement-avatar-people-'+self.run+'-actor.json')),
                binding=self.state['bindings']['actor'],run=self.run,area='avatar-people',fixture_url=self.client.url,
                phase_instance=self.state['phaseInstance'],validate_original=self.retirement_original)
            need(publisher['pending'] is None)
            checkpoint=next(row for row in self.state['cleanup'] if row['kind']=='checkpoint');need(checkpoint['published'])
            observer,reference,_record=self.checkpoint_observer()
            value=self.kept(checkpoint['publisher']);store=PrivateFeatureState(self.store.path.with_name('phase-publication-avatar-people-'+self.run+'-actor.json'))
            witness=PhaseWitnessPublisher.archive(value,store=store,binding=self.state['bindings']['actor'],run=self.run,area='avatar-people',
                fixture_url=self.client.url,phase_instance=self.state['phaseInstance'],validate_original=observer.validate_original)
            need(witness['pending'] is None and witness['records'])
            retained=object.__new__(PhaseWitnessPublisher);retained.store=store;retained.binding=self.state['bindings']['actor'];retained.run,retained.area=self.run,'avatar-people'
            retained.url,retained.instance,retained.validate_original=self.client.url,self.state['phaseInstance'],observer.validate_original
            last=retained.load(witness['records'][-1]);need(last['mode']=='published' and same(last['intent']['original'],reference))
        else:
            proof=self.final_proof(ready);event=next(row for row in self.state['cleanup'] if row['kind']=='actor-complete')
            state=self.reader_history(self.kept(event['owner']),'complete')
            scene_event=next(row for row in self.state['cleanup'] if row['kind']=='actor-scene')
            scene=self.reader_history(self.kept(scene_event['owner']),self.scene_stage())['records'][-1]
            complete=state['records'][-1]
            need(scene['entry'] in complete['journal']['entries'] and scene['entry']['actorSequence']<complete['entry']['actorSequence'])
        return proof

    def observe_cleaned(self,after_sequence):
        """A new passive acquisition, preserving historical completion clocks.

        The old cleanup recipe deadline is never renewed. Only this closed
        postlogout observer receives a fresh read deadline; it has no ordinary
        input, World, login, marker or GPU creation path.
        """
        need(integer(after_sequence,0));old=getattr(self,'final_read_clock',None)
        self.final_read_clock=operation_clock.begin(self.epoch_ms(),self.monotonic())
        try:
            with transport_scope(self.cleanup_deadline),self.held(paired=True):
                self.load();need(self.state['phase']=='cleaned');self.completed_original();owner=self.final_owner()
                reference=owner.capture(ticket=self.state['cleanup'][0]['ticket'],phase_instance=self.state['phaseInstance'],sequence=self.final_sequence(owner))
                ready=next(row for row in self.state['cleanup'] if row['kind']=='final-ready')
                event=dict(kind='final-observation',owner=self.keep(owner.previous),references=[*deepcopy(ready['references']),reference],inputs=self.keep(self.final_ownership()))
                proof=self.final_proof(event);need(proof['public']['sequence']>after_sequence)
                self.state['cleanup'].append(event);self.save();owner.fresh(owner.record(reference));self.cleanup_deadline()
                return deepcopy(proof['public'])
        finally:self.final_read_clock=old

    def terminal_witness_original(self,original):
        """Canonical Actor facts journal, with distinct closed terminal refs."""
        if type(original) is dict and 'iosAvatarTerminalObservationReferenceVersion' in original:
            exact(original,{'iosAvatarTerminalObservationReferenceVersion','reference'})
            need(type(original['iosAvatarTerminalObservationReferenceVersion']) is int
                and original['iosAvatarTerminalObservationReferenceVersion']==1)
            event=self.kept(original['reference']);need(event in self.state['cleanup'] and event['kind']=='final-observation')
            proof=self.terminal_live_proof(event)
            return {key:deepcopy(proof[key]) for key in ('ticket','public','acquisition')}
        observer,_reference,_record=self.checkpoint_observer()
        return observer.validate_original(original)

    def terminal_witness_publisher(self):
        need(self.role=='actor');self.phase.read()
        return AvatarWitnessPublisher(PrivateFeatureState(self.store.path.with_name('phase-publication-avatar-people-'+self.run+'-actor.json')),
            self.state['bindings']['actor'],self.phase,self.lock,self.cleanup_deadline,self.terminal_witness_original,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def publish_terminal_witness(self,publisher,original):
        """Reuse this held Actor publisher; every live delivery guard remains."""
        need(self.role=='actor' and type(publisher) is AvatarWitnessPublisher)
        # Keep the same fresh phase read as the previous second factory call.
        self.phase.read()
        def current(method,actual):
            return (getattr(method,'__self__',None) is self
                and getattr(actual,'__self__',None) is self
                and getattr(method,'__func__',None) is getattr(actual,'__func__',None))
        need(publisher.phase is self.phase and publisher.lock is self.lock
            and publisher.run==self.run and publisher.area=='avatar-people'
            and same(publisher.binding,self.state['bindings']['actor'])
            and publisher.store.path==self.store.path.with_name('phase-publication-avatar-people-'+self.run+'-actor.json')
            and publisher.epoch_ms is self.epoch_ms and publisher.monotonic is self.monotonic
            and current(publisher.validate_original,self.terminal_witness_original)
            and current(publisher.guard,self.cleanup_deadline))
        return publisher.publish(original)

    def observe_terminal(self,after_sequence):
        """A fresh original observation retaining cached native resources."""
        need(integer(after_sequence,0));old=getattr(self,'final_read_clock',None)
        self.final_read_clock=operation_clock.begin(self.epoch_ms(),self.monotonic())
        try:
            with transport_scope(self.cleanup_deadline),self.held(paired=True):
                self.load();need(self.state['phase']=='terminal-ready')
                if self.role=='actor':
                    if self.terminal_actor_sealed_locked():
                        raise AvatarFeaturePending('Actual terminal seal retains the actor SDK without another source capture')
                    publisher=self.terminal_witness_publisher()
                    if not publisher.resolve():raise AvatarFeaturePending('Original terminal witness remains issued and is not sent again')
                owner=self.final_owner();reference=owner.capture(ticket=self.state['cleanup'][0]['ticket'],
                    phase_instance=self.state['phaseInstance'],sequence=self.final_sequence(owner))
                ready=next(row for row in self.state['cleanup'] if row['kind']=='final-ready')
                event=dict(kind='final-observation',owner=self.keep(owner.previous),references=[*deepcopy(ready['references']),reference],inputs=self.keep(self.final_ownership()))
                proof=self.terminal_live_proof(event);need(proof['public']['sequence']>after_sequence)
                self.state['cleanup'].append(event);self.save()
                if self.role=='actor':
                    original=dict(iosAvatarTerminalObservationReferenceVersion=1,reference=self.keep(event))
                    self.publish_terminal_witness(publisher,original)
                owner.fresh(owner.record(reference));self.cleanup_deadline();return deepcopy(proof['public'])
        finally:self.final_read_clock=old

    def terminal_actor_sealed_locked(self):
        """A private genuine seal is an ordering barrier, never actor facts."""
        from ios.adapters.avatar_terminal import AvatarTerminal
        need(self.role=='actor' and self.state['phase']=='terminal-ready')
        for lock in self.locks.values():lock.assert_held()
        path=self.runtime.state_path(self.selectors['primary']).with_name('ios-avatar-primary-feature.json')
        raw=PrivateFeatureState(path).read()
        if raw is None:return False
        primary=IOSAvatarFeature.archive(self.runtime,raw,self.client,self.locks)
        value=PrivateFeatureState(path.with_name('ios-avatar-primary-'+self.run+'-terminal.json')).read()
        if value is None:return False
        owner=AvatarTerminal.archive(primary,value)
        if owner.state['seal'] is None:return False
        owner.verify_seal();_actor,original=owner.roles(owner.state['sealedRoles'])['actor']
        need(same(self.previous,original));return True

    @api_operation
    def terminal(self,call):
        from feature_journeys import terminal
        from ios.adapters.avatar_terminal import AvatarTerminal
        call=terminal.arguments('avatar-people',call);need(call['runId']==self.run and self.role=='primary')
        with self.held(paired=True):
            self.load();need(self.state is not None and self.state['phase']=='terminal-ready');owner=AvatarTerminal(self)
            if call['stage']=='inspect':value=dict(stage='inspect',description=owner.inspect())
            elif call['stage']=='seal':value=dict(stage='seal',seal=owner.seal(call['description'],call['samples']))
            else:value=dict(stage='finish',end=owner.finish(call['seal']))
            terminal.result('avatar-people',value);return value

    def terminal_actor_ended(self):
        """Read the actual paired terminal end after fixture retirement."""
        from ios.adapters.avatar_terminal import AvatarTerminal
        with self.held(paired=True):
            self.load();need(self.role=='actor' and self.state['phase']=='terminal-ready')
            base=self.runtime.state_path(self.selectors['primary'])
            raw=PrivateFeatureState(base.with_name('ios-avatar-primary-feature.json')).read()
            if raw is None:return False
            primary=IOSAvatarFeature.archive(self.runtime,raw,self.client,self.locks)
            path=base.with_name('ios-avatar-primary-'+self.run+'-terminal.json');value=PrivateFeatureState(path).read()
            if value is None:return False
            owner=AvatarTerminal.archive(primary,value)
            if owner.state['end'] is None:return False
            from ios.adapters.avatar_ended_archive import verify
            binding=verify(self.runtime.adapter,self.selector,raw,value,held_locks=self.locks)
            need(same(binding,self.state['bindings'][self.role]));return True

    def verify_terminal_result(self,call,result):
        """Canonical post-call check after the sealed SDKs have actually ended.

        This accepts only the completed finish result. Every other operation
        still requires the installed adapter's ordinary live binding probe.
        """
        from ios.adapters.avatar_canonical_end import verify
        need(same(verify(self,call,result),result));return True

    def finalize(self):
        """Private own-SDK archival after the actual fixture input has retired."""
        from ios.adapters.avatar_finalization import AvatarFinalization
        return AvatarFinalization(self).finish()
