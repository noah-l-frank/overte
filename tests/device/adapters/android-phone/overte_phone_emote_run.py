"""Durable Emote setup/input coordination over existing Phone components.

This internal run owner supplies no public feature triple. Original source
admission, role/image publication and whole-run retirement must be composed
before a complete capability can be registered.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_phone_emote_fixture import input_command
from adapters.emote_admission import policy as admission_policy
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhaseFixtureReader
from overte_phone_emote_background import PhoneEmoteBackground
from overte_phone_emote_admission import PhoneEmoteAdmission
from overte_phone_emote_cleanup import PhoneEmoteCleanup
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_lifetime import PhoneEmoteLifetime
from overte_phone_emote_namespaces import PhoneEmoteNamespaces
from overte_phone_emote_scene import PhoneEmoteScene
from overte_phone_emote_sources import PhoneEmoteSources,MAX_SEGMENTS
from overte_phone_emote_view import PhoneEmoteView
from overte_phone_script_history import pack,unpack,same,canonical
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=3


class PhoneEmoteRun:
    def __init__(self,adapter,selector,phase,artifact_root,image_extent,marker_roi,*,admission=None,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.phase=adapter,selector,phase
        self.run,self.fixture_url=phase.run,phase.fixture_url
        self.root,self.extent,self.marker=Path(artifact_root),deepcopy(image_extent),deepcopy(marker_roi)
        self.policy=None if admission is None else admission_policy(admission)
        PrivateFeatureState(self.root/'emote-run-boundary.json')._parent()
        input_command(dict(schemaVersion=1,commandId='a'*32,action='phone-emote-fixture-input',operation='prepare',
            runId=self.run,fixtureUrl=self.fixture_url,ticket='a'*32,imageExtent=self.extent,markerRoi=self.marker))
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-emote-run.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.previous=self.state=None;self.failed=False

    def load(self):
        self.lock.assert_held();need(not self.failed)
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
        return self.state

    def decode(self,value):
        version=value.get('emoteRunVersion') if type(value) is dict else None
        exact(value,{'emoteRunVersion','runId','fixtureUrl','artifactRoot','imageExtent','markerRoi','payload'}
            |({'admissionPolicy'} if version==VERSION else set()))
        need(type(version) is int and version in (1,2,VERSION)
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.root)
            and same(value['imageExtent'],self.extent) and same(value['markerRoi'],self.marker))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','binding','segment','baseline','call','cleanupTicket'}|({'admissionSha256'} if version==VERSION else set()))
        state=deepcopy(state)
        if version==VERSION:need(same(value['admissionPolicy'],self.policy))
        else:state['admissionSha256']=None
        context(state['binding']);need(integer(state['segment'],0,MAX_SEGMENTS-1)
            and state['phase'] in ('preparing','prepared','acting','active','switching','cleaning-inputs','inputs-restored',
                'restoring-resources','resources-restored'))
        if value['emoteRunVersion']==1:need(state['phase'] not in ('restoring-resources','resources-restored'))
        if state['admissionSha256'] is not None:
            need(self.policy is not None and type(state['admissionSha256']) is str
                and len(state['admissionSha256'])==64 and all(ch in '0123456789abcdef' for ch in state['admissionSha256']))
        if version==VERSION and state['phase'] in ('prepared','acting','active','switching'):need(state['admissionSha256'] is not None)
        if state['baseline'] is not None:
            exact(state['baseline'],{'revision','sha256'});need(integer(state['baseline']['revision'],1,1024)
                and type(state['baseline']['sha256']) is str and len(state['baseline']['sha256'])==64
                and all(ch in '0123456789abcdef' for ch in state['baseline']['sha256']))
        if state['phase'] in ('prepared','acting','active','switching'):need(state['baseline'] is not None)
        if state['call'] is not None:
            call=arguments('feature.emotes.act',state['call'])
            need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        if state['phase'] in ('acting','active','switching'):need(state['call'] is not None)
        if state['phase']=='switching':need(state['call']['verb'] in ('play','sit'))
        if state['cleanupTicket'] is not None:
            need(type(state['cleanupTicket']) is str and len(state['cleanupTicket'])==32
                and all(ch in '0123456789abcdef' for ch in state['cleanupTicket']))
        need((state['cleanupTicket'] is not None)==(state['phase'] in ('cleaning-inputs','inputs-restored','restoring-resources','resources-restored')))
        return deepcopy(state)

    def save(self):
        self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous))
        value=dict(emoteRunVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,artifactRoot=str(self.root),
            imageExtent=self.extent,markerRoi=self.marker,admissionPolicy=deepcopy(self.policy),payload=pack([self.state]))
        try:
            self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def source(self,role='primary',*,segment=None):
        need(self.state is not None)
        source=PhoneEmoteSources(self.adapter,self.selector,self.phase,role,self.lock,artifact_root=self.root,
            monotonic=self.monotonic,segment=self.state['segment'] if segment is None else segment,
            admission=self.policy if self.state['phase']=='preparing' or self.state['admissionSha256'] is not None else None)
        need(same(source.binding,self.state['binding']))
        return source

    def view(self):
        value=PhoneEmoteView(self.adapter,self.selector,self.phase,self.lock,monotonic=self.monotonic,sleep=self.sleep)
        need(same(value.binding,self.state['binding']));return value

    def scene(self,view):
        return PhoneEmoteScene(view,self.root,self.extent,self.marker,monotonic=self.monotonic,sleep=self.sleep)

    def background(self):
        return PhoneEmoteBackground(self.adapter,self.selector,self.phase,self.lock,artifact_root=self.root,
            monotonic=self.monotonic,sleep=self.sleep,segment=self.state['segment'])

    def admitted(self,*,recovering_background=False):
        """Reopen original approved admission; background recovery uses its pin.

        The recovery exception permits only an already owned OS cycle to reach
        foreground. Fresh original validation follows before action completion.
        It never permits a new Home or native getter in an unknown background.
        """
        need(self.policy is not None and self.state['admissionSha256'] is not None)
        header=PrivateFeatureState(self.store.path.with_name('phone-emote-primary-admission.json')).read()
        need(header is not None and hashlib.sha256(canonical(header)).hexdigest()==self.state['admissionSha256'])
        if recovering_background:return
        admission=PhoneEmoteAdmission(self.source(segment=0),self.policy)
        need(admission.state['phase']=='admitted' and same(admission.previous,header))

    def active(self,verb=None,call=None):
        status=self.phase.status();need(status['active'] and status['activations']);row=status['activations'][-1]
        if verb is not None:need(row['stimulus']==dict(verb=verb,inputs={}))
        if verb=='baseline':need(len(status['activations'])==1)
        if call is not None:
            need(row['ticket']==call['ticket'] and same(row['stimulus'],dict(verb=call['verb'],inputs=call['inputs'])))
        return row

    def prepare(self):
        with self.lock.held():
            self.load()
            if self.state is None:
                need(self.policy is not None)
                self.active('baseline')
                # No orphaned ownership is adopted by a new run. Existing
                # diagnostic transport files have different native filenames.
                need(not list(self.store.path.parent.glob('phone-emote-*.json')))
                _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
                need(guard() is not False)
                self.state=dict(phase='preparing',binding=deepcopy(context(binding)),segment=0,baseline=None,call=None,cleanupTicket=None,admissionSha256=None)
                self.save() # Parent ownership precedes every child request/input.
            if self.state['phase']!='preparing':
                need(self.state['phase'] in ('prepared','acting','active','switching'));self.admitted();return deepcopy(self.state)
            baseline_ticket=self.active('baseline')['ticket'];source=self.source();owner=PhoneEmoteInputs(source)
            if self.state['baseline'] is None:
                frame=source.read();need(frame['group']['native']['animation']['overrideActive'] is False
                    and frame['ui']['open'] is False and not frame['ui']['controls'])
                self.state['baseline']=owner.reference();self.save()
            else:
                frame=owner.original(self.state['baseline']);need(frame['phaseAfter']['activations'][-1]['stimulus']==dict(verb='baseline',inputs={}))
            need(all(frame[key]['activations'][-1]['ticket']==baseline_ticket for key in ('phaseBefore','phaseAfter')))
            if self.state['admissionSha256'] is None:
                need(self.policy is not None);admission=PhoneEmoteAdmission(source,self.policy)
                header=admission.wait(sleep=self.sleep);need(admission.state['phase']=='admitted')
                self.state['admissionSha256']=hashlib.sha256(canonical(header)).hexdigest();self.save()
            else:self.admitted()
            view=self.view();view.prepare();need(view.state['phase']=='active')
            need(self.active('baseline')['ticket']==baseline_ticket)
            scene=self.scene(view);scene.prepare();need(scene.state['phase']=='active')
            need(self.active('baseline')['ticket']==baseline_ticket and source.guard() is not False)
            self.state['phase']='prepared';self.save();return deepcopy(self.state)

    def act(self,call):
        """Input ownership only; no requested values become feature effects."""
        call=deepcopy(arguments('feature.emotes.act',call));need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase'] in ('prepared','acting','active'))
            self.active(call=call)
            recovering=(call['verb']=='background-resume' and PrivateFeatureState(self.store.path.with_name('phone-emote-background.json')).read() is not None)
            self.admitted(recovering_background=recovering)
            if self.state['phase']=='acting':need(same(self.state['call'],call))
            else:self.state.update(phase='acting',call=call);self.save()
            if call['verb']=='background-resume':
                # Construct/recover the OS owner before any foreground-only
                # source. The same actual background action is never resent.
                background=self.background()
                if background.state is not None:need(same(background.state['binding'],self.state['binding']) and same(background.state['call'],call))
                value=background.act(call)
                self.admitted()
            else:
                source=self.source();PhoneEmoteNamespaces(source).assert_acquiring();value=PhoneEmoteInputs(source).act(call)
            need(value=={'performed':True});self.active(call=call)
            self.state['phase']='active';self.save();return value

    def acquire(self,role):
        """Obtain this role's actual new original; never forward primary facts."""
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']!='preparing')
            source=self.source(role);PhoneEmoteNamespaces(source).assert_acquiring();return source.read()

    def request_switch(self,call):
        call=deepcopy(arguments('feature.emotes.act',call));need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url
            and call['verb'] in ('play','sit'))
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase'] in ('prepared','active','switching'));self.active(call=call)
            if self.state['phase']=='switching':need(same(self.state['call'],call))
            else:self.state.update(phase='switching',call=call);self.save()
            source=self.source();lease=PhoneEmoteNamespaces(source)
            if lease.state['pending'] is None:
                lease.assert_acquiring();source.read();lease=PhoneEmoteNamespaces(source)
            lease.request(call)

    def acknowledge_switch(self,role):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='switching');self.active(call=self.state['call'])
            source=self.source(role);lease=PhoneEmoteNamespaces(source)
            # A role which already froze does not acquire or republish again.
            if lease.state['pending'] is not None and lease.state['pending']['roles'][role] is not None:return lease.acknowledge()
            lease.assert_acquiring();source.read();return PhoneEmoteNamespaces(source).acknowledge()

    def advance_switch(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='switching');self.active(call=self.state['call'])
            source=self.source();lease=PhoneEmoteNamespaces(source);current=self.state['segment']
            if lease.state['current']==current:need(lease.advance()==current+1)
            else:need(lease.state['current']==current+1 and lease.state['closed'][-1]['segment']==current
                and same(lease.state['closed'][-1]['call'],self.state['call']))
            # Recovery reads the committed child lease; it never advances twice.
            self.state.update(segment=current+1,phase='acting');self.save();return current+1

    def cleanup_inputs(self,call):
        """Recover OS, release a freeze and restore owned native/UI inputs.

        This is explicitly not whole feature cleanup. Scene/view/timer/image/
        actor/file ownership remains until the enclosing complete retirement.
        """
        call=deepcopy(arguments('feature.emotes.cleanup',call));need(call['runId']==self.run)
        with self.lock.held():
            self.load();need(self.state is not None);phase=self.active('cleanup')
            if self.state['cleanupTicket'] is not None:need(self.state['cleanupTicket']==phase['ticket'])
            self.state.update(phase='cleaning-inputs',cleanupTicket=phase['ticket']);self.save()
            background=self.background()
            if background.state is not None:
                need(same(background.state['binding'],self.state['binding']));background.recover_foreground(call)
            source=self.source();lease=PhoneEmoteNamespaces(source)
            if lease.state['current']!=self.state['segment']:
                need(lease.state['current']==self.state['segment']+1 and lease.state['closed']
                    and lease.state['closed'][-1]['segment']==self.state['segment']
                    and same(lease.state['closed'][-1]['call'],self.state['call']))
                self.state['segment']+=1;self.save();source=self.source();lease=PhoneEmoteNamespaces(source)
            from overte_phone_emote_failures import PhoneEmoteFailures
            failures=PhoneEmoteFailures(self);failures.collect_sources();failures.collect_roles();failures.collect_admissions()
            source=self.source();lease=PhoneEmoteNamespaces(source)
            lease.begin_cleanup();lease.assert_acquiring()
            owner=PhoneEmoteInputs(source);clean=PhoneEmoteCleanup(owner);clean.cleanup(call,sleep=self.sleep)
            self.state['phase']='inputs-restored';self.save();return deepcopy(clean.previous)

    def cleanup_resources(self,call):
        """Restore real Scene/View resources after owned input restoration.

        This retains every child journal. No public cleanup, native timer or
        host-file retirement result is inferred from these input/resource ACKs.
        """
        call=deepcopy(arguments('feature.emotes.cleanup',call));need(call['runId']==self.run)
        self.cleanup_inputs(call)
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='inputs-restored')
            need(self.active('cleanup')['ticket']==self.state['cleanupTicket'])
            self.state['phase']='restoring-resources';self.save()
            view=self.view();scene=self.scene(view)
            scene.cleanup();need(scene.state['phase']=='released')
            need(self.active('cleanup')['ticket']==self.state['cleanupTicket'])
            view.cleanup();need(view.state['phase']=='restored')
            need(self.active('cleanup')['ticket']==self.state['cleanupTicket'])
            self.state['phase']='resources-restored';self.save()
            return dict(scene=deepcopy(scene.previous),view=deepcopy(view.previous))

    def cleanup_quiet(self,role):
        """This role independently reads the original three-second quiet window.

        Whole retirement must retain these exact records before removing their
        metadata. Independent publishing still needs its authenticated client.
        """
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='resources-restored')
            need(self.active('cleanup')['ticket']==self.state['cleanupTicket'])
            source=self.source(role);PhoneEmoteNamespaces(source).assert_acquiring()
            life=PhoneEmoteLifetime(source);life.wait(sleep=self.sleep);need(life.state['phase']=='complete')
            need(self.active('cleanup')['ticket']==self.state['cleanupTicket'])
            value=deepcopy(life.previous);last=life.state['records'][-1];frame=life.original(last['source'])
            native=self.adapter._native_feature_observer(self.selector,read_only=True)
            need(native.pid==source.pid and native.ios is False and native.guard() is not False and source.guard() is not False)
            epoch,host,end=native.clock_ms(),self.phase.epoch_ms(),self.monotonic()
            floor=frame['group']['rootsBefore']['requestedEpochMs'];provider=frame['phaseBefore']['capturedEpochMs']
            fresh(floor,epoch);need(number(host,1,1e15) and number(end,last['monotonicMs']/1000,1e15))
            elapsed=end*1000-last['monotonicMs']
            need(-250<=host-provider<=1500 and max(epoch-floor,last['epochMs']-floor+elapsed)<=1500
                and last['hostEpochMs']-provider+elapsed<=1500)
            source.lock.assert_held();return value
