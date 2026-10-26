"""Normal editor input composed with independent original editor history.

This owns only the editor portion. World gestures, background/resume, native
held-event retirement, Actor/images and final cleanup remain separate owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters import lifecycle_fields as fields,lifecycle_originals as originals,tablet_launcher_controls as launcher
from ios.adapters import lifecycle_navigation_controls as navigation,lifecycle_input_owner as field_inputs
from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
from ios.adapters.lifecycle_navigation_owner import LifecycleNavigationOwner
from ios.adapters.lifecycle_input_owner import LifecycleInputOwner

EDITORS=('create','chat','scripts')
ENTRY={'create':'create.entry','chat':'chat.entry','scripts':'scripts.entry'}
FIELD={'create':'lifecycle.create.text','chat':'chat.input','scripts':'lifecycle.scripts.filter'}


class LifecycleEditors:
    def __init__(self,store,history,sources,navigation_owner,navigation_reader,field_owner,field_reader,*,epoch_ms=lambda:time.time()*1000):
        need(isinstance(store,PrivateFeatureState) and isinstance(history,LifecycleEditorHistory)
             and isinstance(navigation_owner,LifecycleNavigationOwner) and isinstance(field_owner,LifecycleInputOwner))
        self.store,self.history,self.sources=store,history,sources
        self.owners={'navigation':navigation_owner,'field':field_owner};self.readers={'navigation':navigation_reader,'field':field_reader}
        self.binding,self.run,self.lock=history.binding,history.run,history.lock;self.epoch_ms=epoch_ms
        need(store.path==history.store.path.with_name('ios-lifecycle-editors-owner.json')
             and same(sources.binding,self.binding) and sources.run==self.run)
        for owner in self.owners.values():
            need(owner.lock is self.lock and same(owner.binding,self.binding) and owner.run==self.run and owner.role=='primary')
        self.previous=store.read();self.state=dict(initial=None,actions=[]) if self.previous is None else self.decode(self.previous)

    def envelope(self,state=None):
        return dict(iosLifecycleEditorsVersion=1,binding=self.binding,runId=self.run,state=deepcopy(self.state if state is None else state))

    def bound(self):
        self.history.check();need(same(self.store.read(),self.previous))
        for owner in self.owners.values():owner.bound()

    def decode(self,value):
        exact(value,{'iosLifecycleEditorsVersion','binding','runId','state'});state=value['state']
        need(type(value['iosLifecycleEditorsVersion']) is int and value['iosLifecycleEditorsVersion']==1 and same(value,self.envelope(state)))
        exact(state,{'initial','actions'});need(type(state['actions']) is list and len(state['actions'])<=96)
        if state['initial'] is not None:
            need(type(state['initial']) is int and state['initial']==1 and self.history.state['baseline']==1)
            initial=self.history.read(1);self.history.baseline_proof(initial);need(not initial['originals']['ui']['tabletShown'])
        seen=set();slots={'navigation':0,'field':0}
        for index,action in enumerate(state['actions']):
            exact(action,{'label','kind','control','operation','text','before','reference','childBefore','childIndex','observationStart','after'})
            need(type(action['label']) is str and re.fullmatch(r'(?:create|chat|scripts)-(?:tablet|home|page-(?:[1-9]|[12][0-9]|3[0-2])|entry|menu|menu-edit|menu-running|focus|type|back-[1-4])',action['label']) is not None
                 and action['label'] not in seen and action['kind'] in self.owners);seen.add(action['label'])
            self.spec(action)
            owner=self.owners[action['kind']];owner._reference(action['reference'],action['control'])
            need(action['operation'] in ('activate','replace') and (action['operation']=='replace' or action['text'] is None)
                 and integer(action['before'],1,len(self.history.state['frames'])) and type(action['childBefore']) is int
                 and action['childBefore']==slots[action['kind']])
            self.reference(action,self.history.read(action['before']))
            if action['childIndex'] is not None:
                need(type(action['childIndex']) is int and action['childIndex']==action['childBefore']+1
                     and action['childIndex']<=len(owner.state['events']))
                self.child(action);slots[action['kind']]=action['childIndex']
            if action['observationStart'] is not None:need(integer(action['observationStart'],action['before'],len(self.history.state['frames'])) and action['childIndex'] is not None)
            if action['after'] is not None:
                need(type(action['after']) is int and action['after']==action['observationStart']+1
                     and action['after']<=len(self.history.state['frames']));self.effect(action)
            else:need(index==len(state['actions'])-1)
        return deepcopy(state)

    def spec(self,action):
        editor,suffix=action['label'].split('-',1);kind='navigation';operation='activate'
        if suffix=='tablet':allowed={'hud.tablet'}
        elif suffix=='home':allowed={'tablet.home'}
        elif suffix.startswith('page-'):allowed={'tablet.page.'+suffix[5:]}
        elif suffix=='entry':allowed={ENTRY[editor]}|({'scripts.menu-running'} if editor=='scripts' else set())
        elif suffix in ('menu','menu-edit','menu-running'):need(editor=='scripts');allowed={'scripts.'+suffix}
        elif suffix=='focus':kind='field';allowed={FIELD[editor]}
        elif suffix=='type':
            kind='field';operation='replace';allowed={FIELD[editor]}
            need(fields.owned_text(action['text'],editor) and action['text'].endswith(self.run))
        else:kind='field';allowed={'tablet.back'};need(suffix.startswith('back-'))
        need(action['kind']==kind and action['control'] in allowed and action['operation']==operation
             and (operation=='replace' or action['text'] is None))

    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)

    def sample(self):
        if self.history.state['original'] is not None:return self.history.recover_original()
        return self.history.append(self.sources.sample(self.epoch_ms()))

    def start(self):
        self.bound()
        if self.state['initial'] is None:
            if not self.history.state['frames']:self.sample()
            need(len(self.history.state['frames'])==1);frame=self.history.read(1)
            self.history.baseline_proof(frame);need(not frame['originals']['ui']['tabletShown'])
            if self.history.state['baseline'] is None:self.history.baseline()
            self.state['initial']=1;self.save()
        return self.state['initial']

    def reference(self,action,frame):
        ui=frame['originals']['ui'];project=navigation.project if action['kind']=='navigation' else field_inputs.project
        need(same(project(ui,action['control']),action['reference']))

    def child(self,action):
        owner=self.owners[action['kind']];event=owner.state['events'][action['childIndex']-1]
        need(event['controlId']==action['control'] and same(event['reference'],action['reference'])
             and event['command']['operation']==action['operation'] and event['command'].get('text')==action['text'])
        return event

    def effect(self,action):
        owner=self.owners[action['kind']];event=self.child(action);owner.validate_original(action['childIndex'])
        before=self.history.read(action['before']);after=self.history.read(action['after']);self.history.follows(before,after)
        a=originals.validate(before,self.binding,self.run);b=originals.validate(after,self.binding,self.run)
        command=event['command'];receipt=event['receipt']['status'];ui=after['originals']['ui'];control=action['control']
        need(before['clockJoin']['nativeAfter']['capturedEpochMs']<=receipt['sampleEpochMs']<=after['clockJoin']['nativeBefore']['capturedEpochMs']
             and ui['lastSequence']==command['sequence']
             and same(before['clockJoin']['nativeAfter']['lifecycle'],after['clockJoin']['nativeBefore']['lifecycle']))
        if action['kind']=='navigation':
            need(ui['tabletShown'] and navigation.membership(ui)['complete'])
            if control in ENTRY.values() or control=='scripts.menu-running':
                editor='scripts' if control=='scripts.menu-running' else next(key for key,value in ENTRY.items() if value==control)
                fields.alias_transition(before['originals']['ui']['lifecycleFieldInventory'],ui['lifecycleFieldInventory'],editor,EDITORS.index(editor)+1)
            elif control in ('scripts.menu','scripts.menu-edit'):
                target='scripts.menu-edit' if control=='scripts.menu' else 'scripts.menu-running'
                need(any(row['controlId']==target and row['inputReady'] for row in ui['lifecycleNavigation']['controls']) and b['field'] is None)
            else:
                need(b['field'] is None and not b['keyboard']['keyboard']);selected=launcher.selection(ui)
                if control=='hud.tablet':need(not before['originals']['ui']['tabletShown'])
                elif control.startswith('tablet.page.'):
                    original=launcher.selection(before['originals']['ui']);row=next(row for row in before['originals']['ui']['controls'] if row['id']==control)
                    launcher.metadata(row);need(selected['launcherCurrentIndex']==row['launcherControlIndex'] and all(same(selected[key],original[key]) for key in ('launcherRootId','launcherQmlSource','launcherPageCount')))
                else:need(control=='tablet.home')
        elif control=='tablet.back':
            need(a['field'] is not None and b['field'] is None and not b['keyboard']['keyboard'])
            editor,suffix=action['label'].split('-',1);prior=self.history.historical_editor(action['before'])
            need(prior['editor']==editor and prior['generation']==int(suffix.rsplit('-',1)[1]))
            previous=a['field']['identity'];rows=[row for row in ui['lifecycleFieldInventory']['fields'] if same(row['identity'],previous)]
            need(len(rows)==1 and (rows[0]['current'] is None or not rows[0]['current']['attached'] and not rows[0]['current']['focused']))
        else:
            need(a['field'] is not None and b['field'] is not None and same(a['field']['identity'],b['field']['identity'])
                 and b['field']['focused'] and b['keyboard']['keyboard'] and b['field']['textOwned'])
            need(b['field']['text']==(command['text'] if command['operation']=='replace' else a['field']['text']))
        return b

    def drive(self,label,kind,control,*,operation='activate',text=None):
        need(kind in self.owners);self.start();matches=[row for row in self.state['actions'] if row['label']==label];need(len(matches)<=1)
        if matches:
            action=matches[0];need((kind,control,operation,text)==(action['kind'],action['control'],action['operation'],action['text']))
        else:
            need(not self.state['actions'] or self.state['actions'][-1]['after'] is not None)
            before=len(self.history.state['frames']);ui=self.history.read(before)['originals']['ui']
            project=navigation.project if kind=='navigation' else field_inputs.project
            action=dict(label=label,kind=kind,control=control,operation=operation,text=text,before=before,reference=project(ui,control),
                childBefore=len(self.owners[kind].state['events']),childIndex=None,observationStart=None,after=None)
            self.spec(action)
            self.state['actions'].append(action);self.save()
        owner=self.owners[kind]
        if action['childIndex'] is None:
            if len(owner.state['events'])==action['childBefore']:owner.reserve(control,action['reference'],operation=operation,text=text)
            need(len(owner.state['events'])==action['childBefore']+1);action['childIndex']=action['childBefore']+1;self.child(action);self.save()
        event=self.child(action)
        if event['phase']=='reserved':owner.send()
        elif event['phase']=='issued':owner.recover(self.readers[kind].read(self.run))
        need(self.child(action)['phase']=='delivered')
        if action['after'] is None:
            if action['observationStart'] is None:action['observationStart']=len(self.history.state['frames']);self.save()
            elif len(self.history.state['frames'])==action['observationStart']+1:
                # An interrupted parent append may already have its original.
                # A failed effect remains retained. A later explicit recovery
                # may obtain another observation without repeating the input.
                action['after']=len(self.history.state['frames'])
                try:self.effect(action)
                except (ValueError,RuntimeError):
                    action['after']=None;action['observationStart']=len(self.history.state['frames']);self.save()
                else:self.save()
            if action['after'] is not None:self.effect(action);return deepcopy(action)
            if len(self.history.state['frames'])==action['observationStart']:self.sample()
            need(len(self.history.state['frames'])==action['observationStart']+1)
            action['after']=len(self.history.state['frames'])
            try:self.effect(action)
            except BaseException:action['after']=None;raise
            self.save()
        self.effect(action);return deepcopy(action)

    def open(self,editor):
        need(editor in EDITORS);self.start();generation=EDITORS.index(editor)+1
        need(len(self.history.state['aliases']) in (generation-1,generation))
        if self.state['actions'] and self.state['actions'][-1]['after'] is None:
            pending=self.state['actions'][-1];need(pending['label'].startswith(editor+'-'))
            self.drive(pending['label'],pending['kind'],pending['control'],operation=pending['operation'],text=pending['text'])
        entry_label=editor+'-entry'
        if not any(row['label']==entry_label for row in self.state['actions']):
            current=self.history.read(len(self.history.state['frames']))['originals']['ui']
            if not current['tabletShown']:self.drive(editor+'-tablet','navigation','hud.tablet')
            current=self.history.read(len(self.history.state['frames']))['originals']['ui']
            if fields.active(current['lifecycleFieldInventory']) is not None:self.drive(editor+'-home','navigation','tablet.home')
            if editor=='scripts' and any(row['label']=='scripts-menu' for row in self.state['actions']):
                self.drive('scripts-menu','navigation','scripts.menu');self.drive('scripts-menu-edit','navigation','scripts.menu-edit')
                self.drive(entry_label,'navigation','scripts.menu-running')
            for _ in range(33):
                if any(row['label']==entry_label for row in self.state['actions']):break
                current=self.history.read(len(self.history.state['frames']))['originals']['ui'];selection=launcher.selection(current)
                ids={row['id'] for row in current['controls']}
                if ENTRY[editor] in ids:self.drive(entry_label,'navigation',ENTRY[editor]);break
                if editor=='scripts' and 'scripts.menu' in ids:
                    self.drive(editor+'-menu','navigation','scripts.menu');self.drive(editor+'-menu-edit','navigation','scripts.menu-edit')
                    self.drive(entry_label,'navigation','scripts.menu-running');break
                visited={int(row['control'].rsplit('.',1)[1])-1 for row in self.state['actions'] if row['label'].startswith(editor+'-page-')}
                visited.add(selection['launcherCurrentIndex']);targets=set(range(selection['launcherPageCount']))-visited;need(targets)
                target=min(targets);self.drive(editor+'-page-'+str(target+1),'navigation','tablet.page.'+str(target+1))
            else:need(False)
        else:
            action=next(row for row in self.state['actions'] if row['label']==entry_label)
            self.drive(entry_label,'navigation',action['control'])
        focus=self.drive(editor+'-focus','field',FIELD[editor])
        entry=next(row for row in self.state['actions'] if row['label']==entry_label)
        if len(self.history.state['aliases'])==generation-1:self.history.qualify(entry['before'],focus['after'])
        alias=self.history.state['aliases'][generation-1];need(alias['before']==entry['before'] and alias['after']==focus['after'])
        return dict(originalEditorIndex=focus['after'],generation=generation,historical=True,wholeFeatureRequired=True)

    def type(self,editor,text):
        need(editor in EDITORS);return self.drive(editor+'-type','field',FIELD[editor],operation='replace',text=text)

    def back(self,editor):
        need(editor in EDITORS);generation=len(self.history.state['aliases']);need(generation in range(1,5))
        need(self.history.state['aliases'][-1]['identity']['editor']==editor)
        return self.drive(editor+'-back-'+str(generation),'field','tablet.back')
