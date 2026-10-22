"""Independent Emote publication and owned observer retirement, not a facade."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier
from feature_journeys.evidence import rectangle
from feature_journeys.witness import Client,projection,WITNESS_KEYS
from feature_journeys.phase_fixture import PhaseRetired,validate as phase_packet
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_emote_lifetime import PhoneEmoteLifetime
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_emote_run import PhoneEmoteRun
from overte_phone_script_history import pack,unpack,same

VERSION=3
LIMIT=1024


def image_policy(value):
    exact(value,{'source','marker','subject'});need(value['source']=='world-render-target')
    rectangle(value['marker'],(16384,16384));rectangle(value['subject'],(16384,16384))
    return deepcopy(value)


class PhoneEmoteActor:
    def __init__(self,run,policy):
        need(isinstance(run,PhoneEmoteRun) and isinstance(run.phase.client,Client))
        self.run,self.policy,self.client=run,image_policy(policy),run.phase.client
        for key in ('marker','subject'):rectangle(self.policy[key],tuple(run.extent))
        self.store=PrivateFeatureState(run.store.path.with_name('phone-emote-actor-lifecycle.json'))
        self.previous=self.state=None;self.failed=False

    def sample(self,value):
        exact(value,{'ticket','actor','actorSequence','capturedEpochMs','facts'})
        identifier(value['ticket']);need(value['actor']=='owned-observer' and integer(value['actorSequence'],1,LIMIT)
            and number(value['capturedEpochMs'],1,1e15))
        exact(value['facts'],set(WITNESS_KEYS['emotes']))
        need(type(value['facts']['animation']) is str and type(value['facts']['sit']) is str
            and number(value['facts']['poseProgress'],0,1)
            and all(type(value['facts'][key]) is bool for key in ('override','restoredBeforeNominalEnd')))
        return value

    def load(self):
        self.run.lock.assert_held();need(not self.failed and self.run.state is not None)
        self.previous=self.store.read()
        self.state=dict(phase='watching',binding=deepcopy(context(self.run.state['binding'])),pending=None,last=None,quiet=None,dropped=[],providerRetirement=None)
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def decode(self,value):
        exact(value,{'emoteActorVersion','runId','fixtureUrl','artifactRoot','imagePolicy','payload'})
        need(type(value['emoteActorVersion']) is int and value['emoteActorVersion'] in (1,2,VERSION)
            and value['runId']==self.run.run and value['fixtureUrl']==self.run.fixture_url
            and value['artifactRoot']==str(self.run.root) and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','binding','pending','last','quiet','dropped'}|({'providerRetirement'} if value['emoteActorVersion']>=2 else set()))
        if value['emoteActorVersion']==1:
            need(state['phase'] in ('watching','publishing','quiet','retired'))
            state=deepcopy(state);state['providerRetirement']=None
            if state['phase']=='retired':state['phase']='drained'
        need(same(context(state['binding']),self.run.state['binding']) and state['phase'] in ('watching','publishing','quiet','drained','retired','unadmitted')
            and (state['phase']!='unadmitted' or value['emoteActorVersion']==3)
            and type(state['dropped']) is list and len(state['dropped'])<=LIMIT)
        cursor=0
        for row in state['dropped']:
            exact(row,{'sequence','ticket','reason'});identifier(row['ticket'])
            need(integer(row['sequence'],cursor+1,LIMIT) and row['reason'] in ('phase-changed','expired-before-send','fixture-retired'));cursor=row['sequence']
        if state['pending'] is not None:
            pending=state['pending'];exact(pending,{'sample','startedMonotonicMs','hostEpochMs','provider','issued'})
            self.sample(pending['sample']);need(type(pending['issued']) is bool and number(pending['startedMonotonicMs'],0,1e15)
                and number(pending['hostEpochMs'],1,1e15) and type(pending['provider']) is dict)
        need((state['phase']=='publishing')==(state['pending'] is not None))
        if state['last'] is not None:
            exact(state['last'],{'sample','receipt'});self.sample(state['last']['sample'])
            receipt=state['last']['receipt'];exact(receipt,{'kind','receivedEpochMs','body'})
            need(receipt['kind']=='journal' and number(receipt['receivedEpochMs'],1,1e15))
            row=receipt['body'];exact(row,set(state['last']['sample'])|{'sequence','receivedEpochMs'})
            need(same({key:row[key] for key in state['last']['sample']},state['last']['sample'])
                and integer(row['sequence'],1) and number(row['receivedEpochMs'],1,1e15))
            if state['pending'] is not None:need(state['pending']['sample']['actorSequence']>state['last']['sample']['actorSequence'])
        if state['quiet'] is not None:need(type(state['quiet']) is dict
            and type(state['quiet'].get('emoteLifetimeRetirementVersion')) is int and state['quiet']['emoteLifetimeRetirementVersion']==1)
        if state['phase'] in ('drained','retired'):need(state['quiet'] is not None and state['last'] is not None)
        need((state['providerRetirement'] is not None)==(state['phase'] in ('retired','unadmitted')))
        if state['phase']=='unadmitted':need(state['pending'] is state['last'] is state['quiet'] is None and not state['dropped'])
        if state['providerRetirement'] is not None:
            status=state['providerRetirement'];phase_packet(status,run=self.run.run,area='emotes',request=status.get('requestId'),epoch=status.get('capturedEpochMs'))
            ticket=self.run.state['cleanupTicket'] if state['phase']=='unadmitted' else state['last']['sample']['ticket']
            need(status['active'] is False and status['activations'][-1]['ticket']==ticket
                and status['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        return deepcopy(state)

    def bound(self):
        self.run.lock.assert_held();need(not self.failed and not self.run.failed
            and same(self.store.read(),self.previous) and same(self.run.store.read(),self.run.previous)
            and same(self.state['binding'],self.run.state['binding']))

    def save(self):
        self.bound()
        value=dict(emoteActorVersion=VERSION,runId=self.run.run,fixtureUrl=self.run.fixture_url,artifactRoot=str(self.run.root),
            imagePolicy=deepcopy(self.policy),payload=pack([self.state]))
        try:
            self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def original(self,sample):
        role=PhoneEmoteRole(self.run,'actor',self.policy);row=role.stored(sample['actorSequence'])
        expected=dict(ticket=row['ticket'],actor='owned-observer',actorSequence=row['sequence'],
            capturedEpochMs=row['public']['capturedEpochMs'],facts=projection('emotes',row['public']['state']))
        need(same(expected,sample));return role,row

    def current(self,previous=None):
        status=self.run.phase.status(previous);need(status['activations'])
        if not status['active']:raise PhaseRetired(status)
        return status,status['activations'][-1]

    def fresh(self,pending):
        now=self.run.monotonic();epoch=self.run.phase.epoch_ms();sample=pending['sample']
        need(number(now,pending['startedMonotonicMs']/1000,1e15) and number(epoch,1,1e15))
        return -250<=epoch-sample['capturedEpochMs']<=1500 and max(epoch-sample['capturedEpochMs'],
            pending['hostEpochMs']-sample['capturedEpochMs']+now*1000-pending['startedMonotonicMs'])<=1500

    def dropped(self,pending,reason):
        self.bound();need(same(self.state['pending'],pending) and len(self.state['dropped'])<LIMIT)
        self.state['dropped'].append(dict(sequence=pending['sample']['actorSequence'],ticket=pending['sample']['ticket'],reason=reason))
        self.state.update(phase='watching',pending=None);self.save();return False

    def retired_role(self,sample):
        quiet=self.state['quiet'];need(quiet is not None and self.run.state['phase']=='resources-restored'
            and sample['ticket']==self.run.state['cleanupTicket']==quiet['cleanup']['activations'][-1]['ticket'])
        role,row=self.original(sample)
        need(row['public']['resources']==[] and row['public']['state']['panel'] is False
            and row['public']['state']['animation']=='idle' and row['public']['state']['override'] is False)
        need(role.state['phase']=='ready' and role.source.state['phase']=='ready' and role.source.state['pending'] is None)
        PhoneEmoteLifetime.retirement_archive(quiet,role.source)
        from overte_phone_emote_namespaces import PhoneEmoteNamespaces
        PhoneEmoteNamespaces(role.source).no_scopes('actor')
        from adapters.owned_world_render import OwnedWorldRenderCapture
        owned=self.run.adapter._world_render_capture(self.run.selector,read_only=True,role='actor',require_frame_view=True)
        need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,self.state['binding'])
            and owned.owner.role=='actor' and owned.owner.store.read() is None)
        return role

    def accept(self,pending,receipt):
        with self.run.lock.held():
            self.run.load();self.load();need(same(self.state['pending'],pending))
            if self.run.state['phase'] not in ('prepared','active','switching','resources-restored'):return False
            status=self.run.phase.status()
            if not status['active']:return self.finish(status)
            self.original(pending['sample'])
            self.state.update(phase='watching',pending=None,last=dict(sample=deepcopy(pending['sample']),receipt=deepcopy(receipt)))
            quiet=self.state['quiet']
            if quiet is not None and self.fresh(pending):
                self.retired_role(pending['sample']);self.state['phase']='drained'
            self.save()
            if self.state['phase']=='drained' and not self.fresh(pending):self.state['phase']='watching';self.save()
            return False # Cleanup observations continue until actual fixture retirement.

    def receipt(self,pending):
        started=self.run.monotonic();host=self.run.phase.epoch_ms()
        value=self.client.request('/runs/'+self.run.run)
        exact(value,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.run.run
            and value['area']=='emotes' and type(value['entries']) is list and len(value['entries'])<=512)
        identifier(value['ticket']);epoch=self.run.phase.epoch_ms();end=self.run.monotonic()
        need(number(end,started,1e15) and end-started<5 and number(value['sampleEpochMs'],1,1e15)
            and -250<=epoch-value['sampleEpochMs']<=1500
            and host-value['sampleEpochMs']+(end-started)*1000<=1500)
        matches=[]
        for row in value['entries']:
            exact(row,set(pending['sample'])|{'sequence','receivedEpochMs'})
            if row['actorSequence']==pending['sample']['actorSequence']:
                need(same({key:row[key] for key in pending['sample']},pending['sample'])
                    and integer(row['sequence'],1) and number(row['receivedEpochMs'],1,1e15))
                matches.append(row)
        need(len(matches)<=1)
        return None if not matches else dict(kind='journal',receivedEpochMs=epoch,body=deepcopy(matches[0]))

    def unadmitted(self):
        """Actual host ownership absence, never native/peer/quiet evidence."""
        self.bound()
        setup=self.run.state['setup']
        if self.run.state['call'] is not None or any(value not in ('unissued','issued') for value in setup.values()):return False
        if self.run.state.get('prepared') is not False and self.run.state['baseline'] is not None and self.run.state['admissionSha256'] is not None and setup==dict(view='issued',scene='issued'):return False
        if self.state['pending'] is not None or self.state['last'] is not None or self.state['quiet'] is not None or self.state['dropped']:return False
        from overte_phone_emote_sources import source_name,MAX_SEGMENTS
        from adapters.owned_world_render import OwnedWorldRenderCapture
        root=self.store.path.parent
        names=['phone-emote-actor-'+kind+'.json' for kind in ('role','lifetime','admission')]
        names.extend(source_name('actor',segment) for segment in range(MAX_SEGMENTS))
        if any(PrivateFeatureState(root/name).read() is not None for name in names):return False
        if any(path.name!=self.store.path.name for path in root.glob('phone-emote-actor-*.json')):return False
        if list(root.glob('phone-emote-actor-capture-*.json')) or list(root.glob('phone-emote-actor-observation-*.json')):return False
        _ui,_native,binding,guard,_installed=self.run.adapter.normal_feature_runtime(self.run.selector,read_only=True)
        need(same(context(binding),self.state['binding']) and guard() is not False)
        owned=self.run.adapter._world_render_capture(self.run.selector,read_only=True,role='actor',require_frame_view=True)
        need(isinstance(owned,OwnedWorldRenderCapture) and same(owned.owner.binding,self.state['binding']) and owned.owner.role=='actor')
        result=owned.owner.store.read() is None;need(guard() is not False);self.bound();return result

    def finish(self,status):
        """Retain closed input authority; never acquire a new product sample."""
        self.bound();need(self.run.state['phase']=='resources-restored' and status['active'] is False)
        phase_packet(status,run=self.run.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs'])
        need(status['activations'] and status['activations'][-1]['ticket']==self.run.state['cleanupTicket']
            and status['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        if self.unadmitted():
            if self.state['phase']=='unadmitted':
                phase_packet(status,run=self.run.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs'],previous=self.state['providerRetirement'])
            else:self.state.update(phase='unadmitted',providerRetirement=deepcopy(status));self.save()
            return True
        need(self.state['phase']!='unadmitted' and self.state['quiet'] is not None and self.state['last'] is not None)
        sample=self.state['last']['sample'];need(sample['ticket']==self.run.state['cleanupTicket'])
        if self.state['phase']=='retired':
            phase_packet(status,run=self.run.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs'],previous=self.state['providerRetirement'])
            self.retired_role(sample);return True
        failure=PhoneEmoteFailures(self.run);failure.collect_sources();failure.collect_roles()
        role=self.retired_role(sample);row=role.stored(sample['actorSequence'])
        previous=role.effects.current_original(row['frame'])['phaseAfter']
        phase_packet(status,run=self.run.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs'],previous=previous)
        if self.state['pending'] is not None:
            self.dropped(deepcopy(self.state['pending']),'fixture-retired')
        self.state.update(phase='retired',providerRetirement=deepcopy(status));self.save();return True

    def deliver(self):
        try:return self._deliver()
        except (ValueError,PhaseRetired):
            with self.run.lock.held():
                self.run.load();self.load();status=self.run.phase.status()
                if not status['active']:return self.finish(status)
            raise

    def _deliver(self):
        # Every transport operation below is outside the native source lock.
        with self.run.lock.held():
            self.run.load();self.load();pending=deepcopy(self.state['pending']);need(pending is not None)
            if self.run.state['phase'] not in ('prepared','active','switching','resources-restored'):return False
            status=self.run.phase.status()
            if not status['active']:return self.finish(status)
            self.original(pending['sample'])
        if pending['issued']:
            receipt=self.receipt(pending)
            if receipt is not None:return self.accept(pending,receipt)
        status,current=self.current(pending['provider'])
        if current['ticket']!=pending['sample']['ticket']:
            with self.run.lock.held():self.run.load();self.load();return self.dropped(pending,'phase-changed')
        need(not pending['issued']) # Missing/unknown delivery cannot replay a POST.
        if not self.fresh(pending):
            with self.run.lock.held():self.run.load();self.load();return self.dropped(pending,'expired-before-send')
        with self.run.lock.held():
            self.run.load();self.load();need(same(self.state['pending'],pending))
            self.state['pending']['issued']=True;self.save();pending=deepcopy(self.state['pending'])
        need(self.fresh(pending))
        try:
            reply=self.client.request('/runs/'+self.run.run+'/samples',pending['sample']);need(reply=={})
            receipt=self.receipt(pending);need(receipt is not None)
        except ValueError:
            receipt=self.receipt(pending)
            if receipt is None:
                _status,current=self.current(pending['provider'])
                if current['ticket']!=pending['sample']['ticket']:
                    with self.run.lock.held():self.run.load();self.load();return self.dropped(pending,'phase-changed')
                raise
        return self.accept(pending,receipt)

    def cleanup_quiet(self):
        need(self.run.state['phase']=='resources-restored')
        self.state['phase']='quiet';self.save()
        if self.state['quiet'] is None:self.run.cleanup_quiet('actor')
        source=self.run.source('actor');life=PhoneEmoteLifetime(source)
        def retain(proof):
            if self.state['quiet'] is None:self.state['quiet']=deepcopy(proof);self.save()
            else:need(same(self.state['quiet'],proof))
        life.retire(retain,retained=self.state['quiet'])
        self.state['phase']='watching';self.save()

    def step(self):
        ready=False
        with self.run.lock.held():
            self.run.load();need(self.run.state is not None);self.load()
            parent=self.run.state['phase']
            # No foreground-only factory while setup/input/OS recovery is pending.
            if parent not in ('prepared','active','switching','resources-restored'):return False
            status=self.run.phase.status(self.state['providerRetirement'])
            if not status['active']:return self.finish(status)
            need(self.state['phase']!='retired')
            if self.state['pending'] is not None:ready=True
            else:
                need(status['activations']);current=status['activations'][-1]
                if parent=='switching':
                    role_path=PrivateFeatureState(self.store.path.with_name('phone-emote-actor-role.json')).read()
                    if role_path is not None:
                        role=PhoneEmoteRole(self.run,'actor',self.policy)
                        if role.state['phase']!='ready':PhoneEmoteFailures(self.run).collect_phase()
                    self.run.acknowledge_switch('actor');return False
                if current['stimulus']['verb']=='baseline':
                    if parent!='prepared':return False
                elif current['stimulus']['verb']=='cleanup':
                    if parent!='resources-restored' or current['ticket']!=self.run.state['cleanupTicket']:return False
                    if self.unadmitted():return False # No observation was admitted; closure owns only this watcher.
                elif parent!='active' or self.run.state['call'] is None or not same(
                        dict(ticket=current['ticket'],verb=current['stimulus']['verb'],inputs=current['stimulus']['inputs']),
                        {key:self.run.state['call'][key] for key in ('ticket','verb','inputs')}):return False
                role=PhoneEmoteRole(self.run,'actor',self.policy)
                if role.state['phase']!='ready':
                    if role.state['pending']['ticket']!=current['ticket']:PhoneEmoteFailures(self.run).collect_phase();return False
                    role.recover();return False
                if current['stimulus']['verb']=='cleanup' and self.state['quiet'] is None:self.cleanup_quiet();role=PhoneEmoteRole(self.run,'actor',self.policy)
                # An already-retained quiet proof may be awaiting child deletion.
                elif self.state['phase']=='quiet':self.cleanup_quiet();role=PhoneEmoteRole(self.run,'actor',self.policy)
                started,host=self.run.monotonic(),self.run.phase.epoch_ms()
                try:sample=role.publication()
                except (NativeUIError,PhaseRetired):
                    _status=self.run.phase.status(status)
                    if not _status['active']:return self.finish(_status)
                    latest=_status['activations'][-1]
                    if latest['ticket']==current['ticket']:raise
                    if role.state['phase']!='ready':PhoneEmoteFailures(self.run).collect_phase()
                    return False
                row=role.stored(sample['actorSequence']);provider=role.effects.current_original(row['frame'])['phaseAfter']
                self.state.update(phase='publishing',pending=dict(sample=sample,startedMonotonicMs=started*1000,
                    hostEpochMs=host,provider=deepcopy(provider),issued=False));self.save();ready=True
        return self.deliver() if ready else False
