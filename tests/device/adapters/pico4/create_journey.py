"""Pico Create v16 coordination over the original normal input owners.

The run coordinator retains every component's original ownership. It cannot
turn a consumed input, fixture stimulus or requested state into an effect.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import os
import math
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.create_models import PicoCreateModels,input_original,source_pin,selected,idle,WorkJournal
from adapters.native_script_work import scope as work_scope
from adapters.pico4.create_picker_owner import OriginalReader
from adapters.pico4.create_entities import retired as entities_retired
from adapters.pico4.create_callbacks import active as active_callbacks
from adapters.pico4.create_dialogs import active as active_dialogs
from adapters.pico4.create_model_resources import retired as resources_retired
from adapters.pico4.navigation import validate_snapshot
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import scope,nonce
from adapters.pico4.create_picker_owner import PicoCreatePicker
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier,typed_equal
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import VERSION as CONTRACT

VERSION=2
MEMBERS={'models':PicoCreateModels,'picker':PicoCreatePicker}
ROLES=('owner','entities','callbacks','dialogs','resources','work','lifecycle','completion')


from adapters.pico4.create_primitives import CreatePrimitives,validate_steps


class PicoCreateJourney(CreatePrimitives):
    """One candidate/run and real source lock shared by its normal owners."""
    def __init__(self,adapter,target,run,source):
        identifier(run);need(isinstance(source,PhaseFixtureReader) and source.area=='create' and source.run==run
            and adapter.pico_configuration is not None)
        from adapters.pico4.create_management import configuration
        need(configuration(os.environ) is not None)
        self.adapter,self.target,self.run,self.source=adapter,target,run,source
        self.dispatch_admission=self.before_send
        self.parent=adapter.pico_configuration[1];self.key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
        self.lock=ScriptSourceLock(self.parent/('normal-create-sources-'+self.key+'.lock'))
        self.store=PrivateFeatureState(self.parent/('create-feature-owner-'+self.key+'-'+run+'.json'))
        self.readers={};self.lifecycle=None;self.lifecycle_previous=None
        self.completion_store=self.source_store('completion');self.completion_previous=self.completion_store.read()
        self.previous=self.store.read()
        if self.previous is not None:self.validate(self.previous)
        if self.completion_previous is not None:self.validate_completion(self.completion_previous)
    def validate(self,value):
        version=value.get('createFeatureVersion');extra={'primitives','baselineExtra','extraLast'} if version==2 else set()
        exact(value,{'createFeatureVersion','binding','runId','fixtureUrl','phase','calls','pending','members','subject','lastInput','inputCount','baselineUi','baselineEntities','sourcePin','manager','compilation','cleanupStarted','cleanupAttempted','baselineLifecycle','editorIds'}|extra)
        need(type(value['createFeatureVersion']) is int and value['createFeatureVersion'] in (1,VERSION)
            and value['runId']==self.run and value['fixtureUrl']==self.source.fixture_url
            and value['members']==sorted(set(value['members'])) and set(value['members'])<={'models','picker'}
            and type(value['calls']) is list and len(value['calls'])<=32 and integer(value['inputCount'],0,4096)
            and value['subject'] in (None,'models','picker','primitive') and (value['lastInput'] is None)==(value['inputCount']==0))
        context(value['binding']);tickets=[]
        need(type(value['cleanupStarted']) is bool and type(value['cleanupAttempted']) is list
            and value['cleanupAttempted']==list(dict.fromkeys(value['cleanupAttempted']))
            and set(value['cleanupAttempted'])<={'editor-close','tablet-close'} and value['sourcePin']==source_pin())
        for call in value['calls']:
            arguments('feature.create.act',call);need(call['runId']==self.run and call['fixtureUrl']==self.source.fixture_url);tickets.append(call['ticket'])
        need(len(tickets)==len(set(tickets)) and (value['pending'] is None or value['calls'] and value['pending']==value['calls'][-1]['ticket']))
        from feature_journeys.phase_fixture import validate
        phase=value['phase'];validate(phase,run=self.run,area='create',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        self.validate_navigation(value['baselineUi'],value['binding'])
        from adapters.pico4.create_entities import validate as validate_entities
        baseline=value['baselineEntities'];validate_entities(baseline,baseline['requestId'],int(value['binding']['processIdentity'].split(':')[0]),baseline['capturedEpochMs'],self.run)
        need(entities_retired(baseline['source']) and baseline['source']['domainConnected']
            and (baseline['source']['canRez'] or baseline['source']['canRezTmp']))
        positions=[]
        for call in value['calls']:
            rows=[(i,r) for i,r in enumerate(phase['activations']) if r['ticket']==call['ticket']]
            need(len(rows)==1 and rows[0][1]['stimulus']['verb']==call['verb'] and typed_equal(rows[0][1]['stimulus']['inputs'],call['inputs']))
            positions.append(rows[0][0])
        need(positions==sorted(set(positions)) and (value['subject'] in (None,'primitive') or value['subject'] in value['members']))
        from adapters.pico4.lifecycle_source import validate as life_validate
        baseline_life=value['baselineLifecycle'];life_validate(baseline_life,dict(commandId=baseline_life['commandId'],runId=self.run),
            int(value['binding']['processIdentity'].split(':')[0]),baseline_life['capturedEpochMs'])
        need(type(value['editorIds']) is list and value['editorIds']==sorted(set(value['editorIds'])) and all(nonce(x) for x in value['editorIds']))
        if version==2:
            from adapters.pico4.create_extra_ui import inventory
            validate_steps(value['primitives'])
            for step in value['primitives']:
                need(step['before']['instance']==value['baselineEntities']['instance'] and step['before']['processId']==int(value['binding']['processIdentity'].split(':')[0])
                    and step['before']['source']['runId']==self.run and step['before']['source']['domainSession']==value['baselineEntities']['source']['domainSession'])
                if step['createOriginal'] is not None:self.validate_input(dict(kind='primitive',original=step['createOriginal']),value['binding'])
            need((value['baselineExtra'] is None)==(value['extraLast'] is None))
            if value['baselineExtra'] is not None:
                inventory(value['baselineExtra']);inventory(value['extraLast'])
                need(value['baselineExtra']['instance']==value['extraLast']['instance']
                    and value['extraLast']['sourceSequence']>=value['baselineExtra']['sourceSequence'])
            need(value['subject']!='primitive' or bool(value['primitives']))
        else:need(value['subject']!='primitive')
        if value['lastInput'] is not None:self.validate_input(value['lastInput'],value['binding'])
    @staticmethod
    def validate_navigation(original,binding):
        validate_snapshot(original,int(binding['processIdentity'].split(':')[0]),original['updatedEpochMs'])
        need(original['bridgeId']==binding['sessionId'])
    @classmethod
    def validate_input(cls,value,binding):
        exact(value,{'kind','original'});original=value['original']
        if value['kind']=='primitive':
            from adapters.pico4.create_extra_ui import IDS
            exact(original,{'createExtraInputVersion','action','controlId','controlToken','scope'});scope(original['scope'])
            need(type(original['createExtraInputVersion']) is int and original['createExtraInputVersion']==1
                and original['action'] in ('activate','replace','select-index') and original['controlId'] in IDS-{'create-extra.polyvox.page'}
                and nonce(original['controlToken']) and original['scope']['instance']==binding['sessionId']
                and original['scope']['processId']==int(binding['processIdentity'].split(':')[0]))
        elif value['kind'] in ('create','models','picker'):
            if 'createInputVersion' in original:input_original(original,binding)
            else:
                from adapters.pico4.create_file_ui import IDS,metadata
                exact(original,{'createFileInputVersion','action','controlId','controlToken','scope','rootId','role','page'})
                scope(original['scope']);metadata(original['page'])
                need(value['kind']=='picker' and type(original['createFileInputVersion']) is int and original['createFileInputVersion']==1
                    and original['action'] in ('activate','replace','submit') and original['controlId'] in IDS-{'create-file.page'}
                    and nonce(original['controlToken']) and original['role'] in ('import','export') and nonce(original['rootId'])
                    and original['page']['rootId']==original['rootId'] and original['page']['role']==original['role']
                    and original['scope']['instance']==binding['sessionId'] and original['scope']['processId']==int(binding['processIdentity'].split(':')[0]))
        elif value['kind'] in ('tablet-open','tablet-close'):
            cls.validate_navigation(original,binding);need(original['open']==(value['kind']=='tablet-close'))
        else:
            from adapters.pico4.tablet_home import validate_input
            need(value['kind']=='home');validate_input(original,int(binding['processIdentity'].split(':')[0]),original['capturedEpochMs'],'tablet.home-ray')
    @staticmethod
    def owned_target(adapter,target):
        if adapter.pico_configuration is None:return False
        key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32];parent=adapter.pico_configuration[1];found=False
        PrivateFeatureState(parent/'create-feature-parent-check.json')._parent()
        for path in parent.glob('create-feature-*-'+key+'-*.json'):
            need(re.fullmatch(r'create-feature-(?:owner|entities|callbacks|dialogs|resources|work|lifecycle|completion)-'+key+r'-[0-9a-f]{32}\.json',path.name))
            found=PrivateFeatureState(path).read() is not None or found
        return found
    def source_store(self,role):
        need(role in ROLES and role!='owner');return PrivateFeatureState(self.parent/('create-feature-'+role+'-'+self.key+'-'+self.run+'.json'))
    def originals(self,binding):
        if not self.readers:
            for role,factory in (('entities',lambda:self.adapter._create_entity_observer(self.target,self.run)),
                    ('callbacks',lambda:self.adapter._create_callback_observer(self.target)),('dialogs',lambda:self.adapter._create_dialog_observer(self.target)),
                    ('resources',lambda:self.adapter._create_model_resources_observer(self.target,self.run))):
                self.readers[role]=OriginalReader(factory(),self.source_store(role),binding)
            self.readers['work']=WorkJournal(self.adapter._script_work(self.target),self.source_store('work'),binding)
        return self.readers
    def lifecycle_packet(self,binding):
        from adapters.pico4.lifecycle_source import validate,summary
        from adapters.native_feature_observation import decode
        store=self.source_store('lifecycle')
        if self.lifecycle is None:
            self.lifecycle=self.adapter._lifecycle_ui_source(self.target);self.lifecycle_previous=store.read()
            if self.lifecycle_previous is not None:
                old=self.lifecycle_previous;exact(old,{'schemaVersion','binding','raw','sha256'})
                need(type(old['schemaVersion']) is int and old['schemaVersion']==1 and context(old['binding'])==context(binding)
                    and type(old['raw']) is str and hashlib.sha256(old['raw'].encode()).hexdigest()==old['sha256'])
                packet=decode(old['raw']);validate(packet,dict(commandId=packet['commandId'],runId=self.run),
                    int(binding['processIdentity'].split(':')[0]),packet['capturedEpochMs']);self.lifecycle.restore(summary(packet))
        packet=self.lifecycle.capture(self.run);raw=self.lifecycle.last_raw
        need(type(raw) is str and decode(raw)==packet and hashlib.sha256(raw.encode()).hexdigest()==self.lifecycle.last_sha256)
        current=dict(schemaVersion=1,binding=deepcopy(context(binding)),raw=raw,sha256=self.lifecycle.last_sha256)
        store.write(current,self.lifecycle_previous);self.lifecycle_previous=current;return packet
    def editor_sample(self,packet,ui):
        from adapters.pico4.lifecycle_source import measured_keyboard
        value=self.state();baseline=value['baselineLifecycle'];rows={r['id']:r for r in packet['source']['editors']}
        need(set(value['editorIds'])<=set(rows))
        page=next((r for r in ui['controls'] if r['id']=='create.page'),None)
        if page is not None:
            current=packet['source']['current'];need(current in rows and rows[current]['kind']=='create')
            if current not in value['editorIds']:
                before={r['id'] for r in baseline['source']['editors']}
                need(current in before or rows[current]['firstObservedEpochMs']>=baseline['capturedEpochMs'])
                self.mark(editorIds=sorted(value['editorIds']+[current]))
        return packet
    def editors_retired(self,packet):
        from adapters.pico4.lifecycle_source import LIVENESS,measured_keyboard
        value=self.state();rows={r['id']:r for r in packet['source']['editors']}
        baseline={r['id']:r for r in value['baselineLifecycle']['source']['editors']}
        if measured_keyboard(packet['source']['keyboard']) or any(r['pressed'] for r in packet['source']['keyboard']['keys']):return False
        for identifier in value['editorIds']:
            need(identifier in rows);row=rows[identifier]
            if identifier in baseline:
                if any(row[k]!=baseline[identifier][k] for k in LIVENESS+('attached','visible','focused','current')):return False
            elif row['fieldAlive'] or row['pageAlive'] or row['contextAlive']:return False
        # An additional non-baseline Create original cannot hide outside the
        # selected editor list, including a page replaced between observations.
        return all(r['id'] in baseline or r['kind']!='create' or not r['alive'] for r in rows.values())

    def extra_retired(self):
        value=self.state()
        if value['createFeatureVersion']==1:return True
        baseline=value['baselineExtra'];current=value['extraLast']
        if baseline is None:return not value['primitives']
        original={r['id']:r for r in baseline['pages']}
        for row in current['pages']:
            if row['id'] in original:
                if row!=original[row['id']]:return False
            elif row['pageAlive'] or row['contextAlive']:return False
        return True

    def sample(self):
        started=self.source.monotonic();native=self.adapter._native_feature_observer(self.target);epoch=native.clock_ms()
        need(number(started,0,1e15) and integer(epoch,1))
        ui,binding=self.runtime();readers=self.originals(binding);callback=readers['callbacks'].read()
        manager,compilation=selected(callback,source_pin());work=readers['work'].read(manager['instance'])
        result=dict(callbacks=callback,manager=manager,compilation=compilation,work=work,scope=work_scope(work,compilation),ui=ui.capture(),
            sampleAnchor=dict(hostStarted=started,nativeEpochMs=epoch))
        self.validate_navigation(result['ui'],binding)
        for role in ('entities','dialogs','resources'):result[role]=readers[role].read()
        need(len({result[k]['instance'] for k in ('callbacks','entities','dialogs','resources','work')})==1
            and all(result[k]['processId']==int(binding['processIdentity'].split(':')[0]) for k in ('callbacks','entities','dialogs','resources','work')))
        need(result['resources']['source']['domainSession']==result['entities']['source']['domainSession'])
        result['lifecycle']=self.lifecycle_packet(binding)
        if self.previous is not None:
            value=self.state();need(value['manager']==manager and value['compilation']==compilation)
            from adapters.pico4.create_picker_owner import OwnedCreatePicker
            OwnedCreatePicker.same_scene(value['baselineEntities'],result['entities']);self.editor_sample(result['lifecycle'],result['ui'])
            if value['createFeatureVersion']==2 and result['ui'].get('createExtraControlsVersion')==1:
                from adapters.pico4.create_extra_ui import inventory_continuity
                current=result['ui']['createExtraUiInventory']
                if value['extraLast'] is not None:inventory_continuity(value['extraLast'],current)
                self.mark(extraLast=deepcopy(current),baselineExtra=deepcopy(current if value['baselineExtra'] is None else value['baselineExtra']))
        return result
    def state(self):
        value=self.store.read();need(value is not None and value==self.previous);self.validate(value);return value
    def write(self,value):
        self.lock.assert_held();self.validate(value);self.store.write(value,self.previous);self.previous=deepcopy(value)
    def mark(self,**changes):self.write(self.state()|deepcopy(changes))
    def runtime(self):
        self.lock.assert_held();ui,_observer,binding=self.adapter._script_runtime(self.target)
        if self.previous is not None:
            need(context(binding)==context(self.state()['binding']));self.check_children(self.state())
        for path in self.parent.glob('create-feature-*-'+self.key+'-*.json'):
            need(re.fullmatch(r'create-feature-(?:owner|entities|callbacks|dialogs|resources|work|lifecycle|completion)-'+self.key+'-'+self.run+r'\.json',path.name))
            journal=PrivateFeatureState(path).read()
            if journal is not None:need(context(journal.get('binding'))==context(binding))
        return ui,binding
    def authorize(self,member,adapter,target,run,binding=None):
        self.lock.assert_held();value=self.state()
        need(adapter is self.adapter and target==self.target and run==self.run and member in value['members'])
        if binding is not None:need(context(binding)==context(value['binding']))
        self.check_children(value)
    def check_children(self,value):
        # Coexistence never adopts another run or an unknown source/file owner.
        patterns={
            'models':r'create-models-(?:owner|callbacks|entities|work|resources|resource-join)-'+self.key+r'-([0-9a-f]{32})\.json',
            'picker':r'create-picker-(?:owner|callbacks|dialogs|entities|setting|files)-'+self.key+r'-([0-9a-f]{32})(?:-[0-9a-f]{32})?\.json'}
        for kind,pattern in patterns.items():
            prefix='create-models-' if kind=='models' else 'create-picker-'
            for path in self.parent.glob(prefix+'*-'+self.key+'-*.json'):
                match=re.fullmatch(pattern,path.name);need(match is not None and match[1]==self.run and kind in value['members'])
                journal=PrivateFeatureState(path).read()
                if journal is not None:need(context(journal.get('binding'))==context(value['binding']))
    def component(self,member):
        value=self.state();need(member in ('models','picker'))
        if member not in value['members']:self.mark(members=sorted(value['members']+[member]))
        # Fully reconstruct every registered peer's originals before granting
        # the next owner; a private filename is not a validated source history.
        for peer in self.state()['members']:
            if peer!=member:MEMBERS[peer](self.adapter,self.target,self.run,coordinator=self).flow()
        return MEMBERS[member](self.adapter,self.target,self.run,coordinator=self).flow()
    def wrap_intent(self,member,intent):
        need(member in MEMBERS and callable(intent))
        def record(original):
            self.record_input(member,original);intent(original)
        return record
    def controls(self,intent=None):
        return self.adapter._create_controls(self.target,self.input if intent is None else intent,before_send=self.dispatch_admission)
    def before_send(self,command,navigation):
        """Final actual NativeNavigationIO guard-to-writer admission."""
        self.lock.assert_held();started=self.source.monotonic()
        clock=lambda:navigation.io.adapter.adb.epoch_milliseconds(navigation.io.target)
        initial=clock();need(number(started,0,1e15) and integer(initial,1))
        current=navigation.snapshot();navigation.io.guard()
        value=self.state();item=value['lastInput'];need(item is not None and item['kind'] in ('create','models','picker','primitive'))
        need(all(navigation.context[k]==value['binding'][k] for k in ('sourceRevision','artifactSha256','processIdentity')))
        original=item['original'];scope(original['scope']);s=original['scope']
        need(all(command.get(k)==original[k] for k in ('controlId','controlToken','action'))
            and command.get('bridgeId')==s['instance'] and command.get('generation')==s['generation']
            and command.get('sequence')==s['sequence']+1 and command.get('observedElapsedMs')==s['elapsedMs'])
        self.validate_navigation(current,value['binding'])
        row=navigation.control(current,command['controlId'])
        need(current['ready'] and row is not None and row.get('inputReady') is True and row['token']==original['controlToken']
            and current['bridgeId']==s['instance'] and current['generation']==s['generation']
            and current['lastCommandSequence']==s['sequence'] and 0<=current['elapsedMs']-s['elapsedMs']<=5000)
        # Candidate and native UI work precede this final original phase read.
        # A phase advanced by the actual last guard can never reach the writer.
        phase=self.phase_fence();need(self.state()==value)
        native=clock();now=self.source.monotonic();need(integer(native,initial) and number(now,started,1e15))
        effective=max(native,initial+math.ceil((now-started)*1000))
        fresh(current['updatedEpochMs'],effective);fresh(phase['capturedEpochMs'],effective)
    def phase_fence(self):
        """Fresh original activation admission, including cleanup ownership."""
        value=self.state();active=self.source.read(value['phase'])
        need(typed_equal(active['status']['activations'],value['phase']['activations']))
        if value['cleanupStarted']:
            original=value['phase']['activations'][-1]
            need(active['ticket']==original['ticket'] and active['verb']=='cleanup' and active['inputs']=={})
        else:
            ticket=value['pending']
            if ticket is None and self.completion_previous is not None:ticket=self.completion_previous['call']['ticket']
            need(ticket is not None);call=value['calls'][-1]
            need(active['ticket']==ticket==call['ticket'] and active['verb']==call['verb']
                and typed_equal(active['inputs'],call['inputs']))
        return active['status']
    def fresh_sample(self,actual):
        anchor=actual['sampleAnchor'];exact(anchor,{'hostStarted','nativeEpochMs'})
        native=self.readers['entities'].reader.clock_ms();now=self.source.monotonic()
        need(number(now,anchor['hostStarted'],1e15) and integer(native,anchor['nativeEpochMs']))
        # This is an admission bound only. Preserve every original source clock.
        epoch=max(native,anchor['nativeEpochMs']+math.ceil((now-anchor['hostStarted'])*1000))
        for role in ('callbacks','entities','dialogs','resources','work','lifecycle'):fresh(actual[role]['capturedEpochMs'],epoch)
        fresh(actual['ui']['updatedEpochMs'],epoch)
    def validate_completion(self,value):
        exact(value,{'schemaVersion','binding','runId','call'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.run)
        arguments('feature.create.act',value['call']);state=self.state()
        need(bool(state['calls']) and context(value['binding'])==context(state['binding']) and value['call']==state['calls'][-1]
            and state['pending'] in (None,value['call']['ticket']))
    def completion(self):
        value=self.completion_store.read();need(value==self.completion_previous)
        if value is not None:self.validate_completion(value)
        return value
    def resume_completion(self):
        self.lock.assert_held();value=self.completion()
        if value is not None:
            self.runtime() # Candidate/process guard before any recovery write.
            if self.state()['pending'] is None:self.mark(pending=value['call']['ticket'])
    def complete_call(self):
        actual=self.sample();self.primitive_final(actual);phase=self.phase_fence();self.fresh_sample(actual);original=self.state()
        transition=dict(schemaVersion=1,binding=deepcopy(original['binding']),runId=self.run,call=deepcopy(original['calls'][-1]))
        self.validate_completion(transition);previous=self.completion()
        need(previous is None or previous==transition)
        self.completion_store.write(transition,previous);self.completion_previous=transition
        try:
            # Keep the exact original ticket through the retained copy/CAS and
            # actual candidate guard. A slow writer cannot hide behind a frozen
            # native clock. The final pending-clear CAS is checked once again.
            self.mark(phase=phase);self.runtime();self.fresh_sample(actual)
            self.mark(pending=None);self.runtime();self.phase_fence();self.fresh_sample(actual)
            self.completion_store.discard(transition);self.completion_previous=None
        except Exception:
            # If this restoration itself fails, the durable transition still
            # blocks every next act and restores the original on reconstruction.
            if self.state()['pending'] is None:self.mark(pending=transition['call']['ticket'])
            raise
        return {'performed':True}

    def record_input(self,kind,original):
        value=self.state();need(value['pending'] is not None or value['cleanupStarted'])
        item=dict(kind=kind,original=deepcopy(original));self.validate_input(item,value['binding'])
        phase=self.phase_fence()
        changes=dict(phase=phase,lastInput=item,inputCount=value['inputCount']+1)
        if kind=='primitive' and original['controlId']=='create-extra.polyvox.add':
            steps=deepcopy(value['primitives']);need(bool(steps) and steps[-1]['createOriginal'] is None)
            steps[-1]['createOriginal']=deepcopy(original);changes['primitives']=steps
        self.mark(**changes)
    def export_subject(self,actual):
        need('models' in self.state()['members'] and self.state()['subject']=='models')
        model=self.component('models');value=model.state();step=value['steps'][-1]
        need(value['pending'] is None and step['texture'] is not None and step['texture']['applied']
            and step['outcome']=='texture-property-applied')
        measured=model.quiet('texture');row=model.actual_entity(measured)
        need(actual['entities']['source']['domainSession']==measured['entities']['source']['domainSession']
            and actual['entities']['source']['entities']==[row])
        return deepcopy(row)
    def join_model_deletion(self,model):
        """Retain Save bytes while independently retiring its exported subject."""
        state=model.state();need(state['pending'] is None and state['steps'][-1]['outcome']=='deleted')
        if 'picker' not in self.state()['members']:return
        picker=self.component('picker')
        if picker.previous is None:return
        value=picker.state();step=value['steps'][-1]
        if step['role']=='export' and step['entityId']==state['steps'][-1]['entityId']:
            need(value['pending'] is None and step['outcome'] in ('exported','deleted'))
            # This only reads original domain/callback/weak lifetime sources.
            # It neither performs nor attributes another ordinary Delete.
            picker.settle('delete')

    def prepare(self):
        self.lock.assert_held();need(self.previous is None)
        active=self.source.read();need(active['verb']=='baseline' and active['inputs']=={})
        ui,binding=self.runtime();before=ui.capture();self.validate_navigation(before,binding)
        need(not any(r['id'] in ('create.page','create-extra.polyvox.page') for r in before['controls']))
        need(not self.adapter._create_models_owned(self.target) and not self.adapter._create_picker_owned(self.target)
            and not self.adapter._create_management(self.target).owned())
        original=self.sample();need(entities_retired(original['entities']['source']) and idle(original['scope'])
            and not active_callbacks(original['callbacks']) and not active_dialogs(original['dialogs'])
            and resources_retired(original['resources']['source']))
        from adapters.pico4.lifecycle_source import measured_keyboard
        need(not original['lifecycle']['source']['current'] and not measured_keyboard(original['lifecycle']['source']['keyboard']))
        current=self.source.read(active['status'])
        need(current['ticket']==active['ticket'] and current['verb']=='baseline' and current['inputs']=={}
            and typed_equal(current['status']['activations'],active['status']['activations']))
        self.fresh_sample(original);active=current
        value=dict(createFeatureVersion=VERSION,binding=deepcopy(context(binding)),runId=self.run,fixtureUrl=self.source.fixture_url,
            phase=active['status'],calls=[],pending=None,members=[],subject=None,lastInput=None,inputCount=0,baselineUi=before,baselineEntities=original['entities'],sourcePin=source_pin(),manager=original['manager'],
            compilation=original['compilation'],cleanupStarted=False,cleanupAttempted=[],baselineLifecycle=original['lifecycle'],editorIds=[],primitives=[],baselineExtra=deepcopy(original['ui'].get('createExtraUiInventory')),extraLast=deepcopy(original['ui'].get('createExtraUiInventory')))
        self.write(value);return value
    def input(self,original):
        self.record_input('create',original)
    def navigation_input(self,stage,original,control):
        need(stage==control=='tablet-open');self.record_input('tablet-open',original)
    def home_input(self,stage,original,control):
        from adapters.pico4.tablet_home import validate_input
        need(stage=='tablet-home-ray' and control=='tablet.home-ray');self.record_input('home',original)
    def open_editor(self):
        ui,_binding=self.runtime();before=ui.capture()
        if not before['open']:
            self.navigation_input('tablet-open',before,'tablet-open');ui.open_tablet()
        from adapters.pico4.tablet_home import bind_home
        home=bind_home(self.adapter,self.target,self.adapter._native_feature_observer(self.target));home.ensure(self.home_input)
        controls=self.controls();controls.open_create();controls.wait_create()
    def close_editor(self):
        from adapters.pico4.tablet_home import bind_home
        home=bind_home(self.adapter,self.target,self.adapter._native_feature_observer(self.target))
        home.ensure(self.home_input)
        controls=self.controls()
        need(controls.row(controls.capture(),'create.page',enabled=False) is None)
    def act(self,values):
        arguments('feature.create.act',values)
        with self.lock.held():
            self.resume_completion()
            value=self.state();need(value['pending'] is None and not value['cleanupStarted'] and values['runId']==self.run and values['fixtureUrl']==self.source.fixture_url
                and values['ticket'] not in [r['ticket'] for r in value['calls']])
            need(values['verb'] in ('open','close','import-picker-open','import-picker-cancel','import-picker-accept','model-create','apply-texture','export-selection','delete-owned','voxel-create'))
            if value['createFeatureVersion']==1:
                self.runtime();self.mark(createFeatureVersion=2,primitives=[],baselineExtra=None,extraLast=None);value=self.state()
            if values['verb']=='voxel-create':need(self.sample()['entities']['source']['createEntitySourceVersion']==4)
            self.sample();value=self.state()
            active=self.source.read(value['phase']);need(active['ticket']==values['ticket'] and active['verb']==values['verb'] and typed_equal(active['inputs'],values['inputs']))
            value['calls'].append(deepcopy(values));value.update(pending=values['ticket'],phase=active['status']);self.write(value)
            verb=values['verb']
            if verb=='open':self.open_editor()
            elif verb=='close':self.close_editor()
            elif verb=='import-picker-open':self.component('picker').open(self.run,values['ticket'],values['fixtureUrl'])
            elif verb=='import-picker-cancel':self.component('picker').finish_choice('cancel')
            elif verb=='import-picker-accept':
                self.component('picker').import_file();self.mark(subject='picker')
            elif verb=='model-create':
                self.component('models').create(self.run,values['ticket'],values['fixtureUrl'],values['inputs']['resource']);self.mark(subject='models')
            elif verb=='apply-texture':
                need(value['subject']=='models');self.component('models').apply_texture(self.run,values['ticket'],values['fixtureUrl'],values['inputs']['resource'])
            elif verb=='export-selection':
                picker=self.component('picker');picker.open_export(self.run,values['ticket'],values['fixtureUrl']);picker.export_file()
            elif verb=='voxel-create':self.primitive_create()
            elif verb=='delete-owned' and value['subject']=='primitive':self.primitive_delete()
            elif verb=='delete-owned':
                need(value['subject'] in ('models','picker'));member=self.component(value['subject'])
                (member.delete if value['subject']=='models' else member.delete_import)()
                if value['subject']=='models':self.join_model_deletion(member)
                self.mark(subject=None)
            else:need(False)
            return self.complete_call()

    def reconcile(self):
        """Read-only completion after a lost reply; never resumes input stages."""
        self.lock.assert_held();self.resume_completion();value=self.state();need(value['pending'] is not None and not value['cleanupStarted']);self.phase_fence()
        verb=value['calls'][-1]['verb'];subject=value['subject']
        if verb=='voxel-create' or verb=='delete-owned' and (subject=='primitive' or value.get('primitives') and value['primitives'][-1]['deleteTicket']==value['pending']):
            self.primitive_reconcile('create' if verb=='voxel-create' else 'delete')
        elif verb in ('open','close'):
            ui=self.controls();page=ui.row(ui.capture(),'create.page',enabled=False)
            need((page is not None)==(verb=='open') and value['lastInput'] is not None)
        elif verb in ('model-create','apply-texture') or verb=='delete-owned' and subject=='models':
            model=self.component('models');state=model.state()
            operation={'model-create':'create','apply-texture':'texture','delete-owned':'delete'}[verb]
            if state['pending'] is not None:
                need(state['pending']['operation']==operation);model.reconcile()
            else:
                need(state['steps'][-1]['outcome']=={'create':'created','texture':'texture-property-applied','delete':'deleted'}[operation])
                model.quiet(operation,created=operation=='create')
            if verb=='model-create':self.mark(subject='models')
            elif verb=='delete-owned':self.join_model_deletion(model);self.mark(subject=None)
        else:
            picker=self.component('picker');state=picker.state()
            if verb=='import-picker-open':
                need(state['pending'] is None and state['steps'][-1]['outcome']=='open' or state['pending'] is not None and state['pending']['operation']=='open')
                picker.join_open();picker.finish('open')
            else:
                operation={'import-picker-cancel':'cancel','import-picker-accept':'import','export-selection':'export','delete-owned':'delete'}[verb]
                if state['pending'] is not None:
                    need(state['pending']['operation']==operation);picker.reconcile()
                else:picker.settle_completed(operation)
                if verb=='import-picker-accept':self.mark(subject='picker')
                elif verb=='delete-owned':self.mark(subject=None)
        return self.complete_call()

    def cleanup(self):
        """A distinct ordinary Cancel/Delete, then original joint retirement.

        Cleanup cannot call act/replay its uncertain call. All child attempts,
        files and original Qt/resource identities remain owned on refusal.
        """
        self.lock.assert_held();self.resume_completion();value=self.state()
        if not value['cleanupStarted']:
            active=self.source.read(value['phase']);need(active['verb']=='cleanup' and active['inputs']=={})
            self.mark(cleanupStarted=True,phase=active['status'])
        self.phase_fence()
        # Settle or cancel actual open file input before changing selection.
        if 'picker' in self.state()['members']:
            picker=self.component('picker')
            if picker.previous is not None:
                state=picker.state();step=state['steps'][-1]
                if state['pending'] is not None:
                    if state['pending']['operation']=='cancel':picker.reconcile()
                    elif state['pending']['operation']=='open':
                        picker.join_open();picker.finish_choice('cancel')
                    elif state['pending']['operation'] in ('import','export'):
                        # A consumed choice may have returned despite lost reply.
                        # Read first. Do not send Cancel if the native callback
                        # has already returned or the ordinary window is gone.
                        actual=picker.actual()
                        from adapters.pico4.create_dialogs import joined
                        current=joined(step['dialogBinding'],actual['dialogs'])
                        if current['pending']:picker.finish_choice('cancel')
                        else:picker.reconcile()
                    else:picker.reconcile()
                elif step['outcome']=='open':picker.finish_choice('cancel')
        # Actual member sources decide which object exists. Subject metadata
        # cannot hide a consumed create/import whose root reply was lost.
        actual=self.sample();rows=actual['entities']['source']['entities']
        if self.state().get('primitives') and self.primitive_step()['outcome']!='deleted':
            self.primitive_delete();actual=self.sample();rows=actual['entities']['source']['entities']
        if rows:
            need(len(rows)==1);identifier=rows[0]['id'];owners=[]
            for member in self.state()['members']:
                child=self.component(member)
                if child.previous is None:continue
                step=child.state()['steps'][-1]
                if member=='models' and (step['entityId']==identifier or step['entityId'] is None and rows[0]['modelUrl']==step['url']):
                    model=child.actual_entity(child.capture(),allow_absent=True)
                    if model is not None and model['id']==identifier:owners.append((member,child))
                elif member=='picker' and step['role']=='import' and step['entityId']==identifier:owners.append((member,child))
            need(len(owners)==1);member,child=owners[0]
            (child.delete if member=='models' else child.delete_import)()
            if member=='models':self.join_model_deletion(child)
        for member in self.state()['members']:
            factory=MEMBERS[member](self.adapter,self.target,self.run,coordinator=self)
            if not factory.owned():
                need(not factory.owned_target(self.adapter,self.target));continue
            self.phase_fence();child=self.component(member)
            if child.previous is None:child.release_observations()
            else:child.release()
        # Every child retirement may fail independently. The root sources and
        # original pending call survive until a fresh common quiet window.
        need(not self.adapter._create_models_owned(self.target) and not self.adapter._create_picker_owned(self.target))
        self.mark(subject=None)
        ui,_binding=self.runtime();controls=self.controls()
        if controls.row(controls.capture(),'create.page',enabled=False) is not None:
            value=self.state();need('editor-close' not in value['cleanupAttempted'])
            self.mark(cleanupAttempted=value['cleanupAttempted']+['editor-close']);self.close_editor()
        if not self.state()['baselineUi']['open'] and ui.capture()['open']:
            value=self.state();need('tablet-close' not in value['cleanupAttempted'])
            self.mark(cleanupAttempted=value['cleanupAttempted']+['tablet-close'])
            self.record_input('tablet-close',ui.capture());ui.close_tablet();ui.wait_tablet_absent()
        started=ui.monotonic();quiet=None;clocks=None;stable=None
        for attempt in range(67):
            actual=self.sample();packet=actual['entities'];current=ui.monotonic()
            controls=self.controls();page=controls.row(controls.capture(),'create.page',enabled=False)
            if not self.extra_retired():raise NativeUIError('Original Create PolyVox page or Qt context remains retained')
            if not self.editors_retired(actual['lifecycle']):
                raise NativeUIError('Original Create editor or Qt context remains retained')
            ready=(entities_retired(packet['source']) and idle(actual['scope']) and not active_callbacks(actual['callbacks'])
                and not active_dialogs(actual['dialogs']) and resources_retired(actual['resources']['source']) and page is None
                and actual['ui']['open']==self.state()['baselineUi']['open'] and self.editors_retired(actual['lifecycle']) and self.extra_retired())
            epoch=(packet['capturedEpochMs'],actual['dialogs']['source']['elapsedMs'],actual['resources']['capturedEpochMs'],
                actual['work']['source']['work']['capturedEpochMs'],actual['ui']['elapsedMs'],actual['lifecycle']['capturedEpochMs'])+((self.state()['extraLast']['elapsedMs'],) if self.state().get('extraLast') is not None else ())
            signature=(actual['entities']['source'],actual['resources']['source'],actual['lifecycle']['source']['editors'],actual['scope']['timerRegistrations'],actual['scope']['timerInvocations'],deepcopy(self.state().get('extraLast',{}).get('pages',[]) if self.state().get('extraLast') else []))
            if ready and (stable is None or signature==stable):
                quiet=current if quiet is None else quiet;clocks=epoch if clocks is None else clocks;stable=deepcopy(signature)
                if current-quiet>=3 and all(b-a>=3000 for a,b in zip(clocks,epoch)):
                    phase=self.phase_fence();self.fresh_sample(actual);self.mark(phase=phase);self.runtime();self.fresh_sample(actual)
                    if self.completion() is not None:
                        self.completion_store.discard(self.completion_previous);self.completion_previous=None
                    for reader in self.readers.values():reader.retire()
                    self.source_store('lifecycle').discard(self.lifecycle_previous);self.lifecycle_previous=None
                    self.store.discard(self.state());self.previous=None;return {'performed':True}
            else:quiet=None;clocks=None;stable=None
            need(current-started<13 and attempt<66);ui.sleep(.2)
        need(False)

    def invoke(self,operation,values=None):
        need(operation in ('prepare','act','sample','reconcile','cleanup'))
        if operation=='act':return self.act(values)
        need(values is None)
        if operation=='cleanup' and self.previous is None:
            need(not self.owned_target(self.adapter,self.target) and not self.adapter._create_models_owned(self.target)
                and not self.adapter._create_picker_owned(self.target))
            return {'performed':True}
        with self.lock.held():return getattr(self,operation)()
