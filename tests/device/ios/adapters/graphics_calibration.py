"""Durable ordinary-input calibration with separate role-owned off originals.

No fixture phase, public baseline, product observation or actor input is forged.
The whole owner must exclude public observation and unrelated input until this
private round completes. Calls return between roles; no source lock is slept on.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets

from adapters.native_feature_observation import exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.token_graphics_ui import TokenGraphicsUI
from feature_journeys.contract import arguments,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_fixture import GraphicsFixtureReader
from ios.adapters.graphics_history import follow_native
from ios.adapters.graphics_observer import IOSGraphicsObserver
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.adapters.graphics_source import validate as graphics_packet

VERSION=2
READS=(1,2)
FIELDS={'haze':'hazeSetting','mirror':'mirrorsSetting'}
VERBS={'haze':'set-haze','mirror':'set-mirrors'}


class IOSGraphicsCalibration:
    def __init__(self,preferences,source):
        need(isinstance(preferences,IOSGraphicsPreferences) and isinstance(source,GraphicsFixtureReader)
             and source.run==preferences.run and source.fixture_url==preferences.fixture_url)
        self.preferences,self.source,self.scene=preferences,source,preferences.scene
        self.lock,self.run,self.binding=preferences.lock,preferences.run,deepcopy(preferences.scene.binding)
        self.store=PrivateFeatureState(preferences.store.path.with_name('ios-graphics-calibration.json'))
        self.lock.assert_held();self.previous=self.store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    @classmethod
    def archive(cls,value,*,scene,source):
        """Original decoding only; no source factory, input or clock exists."""
        scope=object.__new__(cls);scope.scene,scope.source=scene,source
        scope.run,scope.binding=scene.run,deepcopy(scene.binding)
        return deepcopy(scope.decode(value))

    def decode(self,value):
        exact(value,{'iosGraphicsCalibrationVersion','runId','fixtureUrl','providerInstance','payload'})
        need(type(value['iosGraphicsCalibrationVersion']) is int and value['iosGraphicsCalibrationVersion'] in READS
             and value['runId']==self.run and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'rounds'});need(type(state['rounds']) is list and 1<=len(state['rounds'])<=8)
        handoff=self.scene.state['handoff'];receipt=None
        if handoff is not None:
            from ios.adapters.graphics_restart_proof import validate as restart_packet
            receipt=restart_packet(handoff['receipt']);need(same(receipt['input']['newBinding'],self.binding))
        for ordinal,row in enumerate(state['rounds'],1):
            exact(row,{'ordinal','stage','binding','phase','active','native','graphics','shown','features','offCalls','restoreCalls','offNative','restoredNative','restoredGraphics','roles'}|({'captureFeatures'} if 'captureFeatures' in row else set()))
            if value['iosGraphicsCalibrationVersion']==1:need('captureFeatures' not in row)
            if 'captureFeatures' in row:need(row['captureFeatures']==list(FIELDS))
            need(type(row['ordinal']) is int and row['ordinal']==ordinal and integer(row['stage'],0,1)
                 and row['phase'] in ('turning-off','off','restoring','complete') and (ordinal==len(state['rounds']) or row['phase']=='complete'))
            binding=context(row['binding']);pid=int(binding['processIdentity'])
            expected=self.binding if receipt is None else receipt['input']['oldBinding' if row['stage']==0 else 'newBinding']
            need(same(binding,expected) and (receipt is not None or row['stage']==0))
            native=row['native'];native_packet(native,native['requestId'],pid,native['capturedEpochMs'])
            if ordinal>1:
                previous=state['rounds'][ordinal-2];need(row['stage']>=previous['stage'])
                if same(previous['binding'],binding):follow_native(previous['restoredNative'],native)
                else:
                    need(receipt is not None and previous['stage']==0 and row['stage']==1
                         and previous['restoredNative']['instance']==receipt['oldNative']['instance']
                         and previous['restoredNative']['sequence']<receipt['oldNative']['sequence']
                         and native['instance']==receipt['native']['instance']
                         and native['requestedEpochMs']>=receipt['native']['capturedEpochMs'])
            ui=row['graphics'];graphics_packet(ui,ui['commandId'],pid,ui['capturedEpochMs'])
            need(ui['capturedEpochMs']<=native['requestedEpochMs']
                 and type(row['shown']) is bool and row['shown']==(TokenGraphicsUI.row(ui,'graphics.page') is not None))
            need(row['features']==[f for f,k in FIELDS.items() if native['graphics'][k]] and (bool(row['features']) or 'captureFeatures' in row))
            active=row['active'];exact(active,{'ticket','verb','inputs','afterEpochMs','status'})
            self.source.active(dict(schemaVersion=1,runId=self.run,area='graphics',ticket=active['ticket'],stimulus=dict(verb=active['verb'],inputs=active['inputs'])))
            status=active['status'];validate_status(status,instance=self.source.instance,run=self.run,url=self.source.client.url,request=status['requestId'])
            need(status['active'] and status['ticket']==active['ticket'] and integer(active['afterEpochMs'],1))
            off=[('open',{})] if row['features'] and not row['shown'] else []
            off += [(VERBS[f],dict(enabled=False)) for f in row['features']]
            restore=[(VERBS[f],dict(enabled=native['graphics'][FIELDS[f]])) for f in row['features']]
            if row['features'] and not row['shown']:restore.append(('close',{}))
            seen=set()
            for key,plan in (('offCalls',off),('restoreCalls',restore)):
                need(type(row[key]) is list and len(row[key])==len(plan))
                for step,(verb,inputs) in zip(row[key],plan):
                    exact(step,{'call','phase'});call=arguments('feature.graphics.act',step['call'])
                    need(call['runId']==self.run and call['fixtureUrl']==self.source.fixture_url and call['verb']==verb
                         and same(call['inputs'],inputs) and call['ticket']!=active['ticket'] and call['ticket'] not in seen
                         and step['phase'] in ('planned','issued','observed'));seen.add(call['ticket'])
            if row['offNative'] is not None:
                packet=row['offNative'];follow_native(native,packet)
                need(all(not packet['graphics'][FIELDS[f]] for f in row['features'])
                     and all(same(v,packet['graphics'][k]) for k,v in native['graphics'].items() if k not in [FIELDS[f] for f in row['features']]))
            if row['phase']!='turning-off':need(row['offNative'] is not None and all(s['phase']=='observed' for s in row['offCalls']))
            exact(row['roles'],{'primary','actor'})
            for role,item in row['roles'].items():
                if item is None:continue
                exact(item,{'phase','before','refs'});need(item['phase'] in ('capturing','observed') and type(item['before']) is dict)
                need(item['before']['role']==role and item['before']['runId']==self.run)
                if item['phase']=='capturing':need(item['refs'] is None)
                else:
                    exact(item['refs'],set(self.capture_features(row)))
                    for ref in item['refs'].values():
                        exact(ref,{'iosGraphicsObserverFrameRefVersion','stage','requestId','sha256'})
                        need(ref['stage']==row['stage'] and ref['iosGraphicsObserverFrameRefVersion']==1)
            if row['phase'] in ('restoring','complete'):need(all(i is not None and i['phase']=='observed' for i in row['roles'].values()))
            if row['phase']=='complete':
                need(all(s['phase']=='observed' for s in row['restoreCalls']) and row['restoredNative'] is not None)
                follow_native(row['offNative'],row['restoredNative']);need(same(row['restoredNative']['graphics'],native['graphics']))
                ui=row['restoredGraphics'];graphics_packet(ui,ui['commandId'],pid,ui['capturedEpochMs'])
                need(ui['instance']==row['graphics']['instance'] and ui['sourceSequence']>row['graphics']['sourceSequence']
                     and row['offNative']['capturedEpochMs']<=ui['capturedEpochMs']<=row['restoredNative']['requestedEpochMs']
                     and row['shown']==(TokenGraphicsUI.row(ui,'graphics.page') is not None)
                     and ui['originalReceipt']['observation']['tabletShown']==row['shown'])
            else:need(row['restoredNative'] is None and row['restoredGraphics'] is None)
        last=state['rounds'][-1]
        if not same(last['binding'],self.binding):
            need(receipt is not None and last['phase']=='complete' and last['stage']==0)
            need(same(receipt['input']['oldBinding'],last['binding']) and same(receipt['input']['newBinding'],self.binding))
        return state

    def save(self):
        self.lock.assert_held();need(self.scene.guard() is not False and same(self.store.read(),self.previous))
        value=dict(iosGraphicsCalibrationVersion=VERSION,runId=self.run,fixtureUrl=self.source.client.url,
                   providerInstance=self.source.instance,payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def phase(self,row):
        active=self.source.read(row['active']['status'])
        need(active['ticket']==row['active']['ticket'] and active['verb']==row['active']['verb'] and same(active['inputs'],row['active']['inputs']))
        return active

    def begin(self,stage):
        """Primary only: measure current preferences and reserve all normal calls."""
        self.lock.assert_held();need(type(stage) is int and stage in (0,1)
             and (self.state is None or self.state['rounds'][-1]['phase']=='complete')
             and (self.state is None or len(self.state['rounds'])<8))
        active=self.source.read();_surface,ui,shown=self.preferences.status();native=self.preferences.source()
        page=TokenGraphicsUI.row(ui,'graphics.page');need(shown==(page is not None))
        features=[f for f,k in FIELDS.items() if native['graphics'][k]]
        off=([('open',{})] if features and not shown else [])+[(VERBS[f],dict(enabled=False)) for f in features]
        restore=[(VERBS[f],dict(enabled=native['graphics'][FIELDS[f]])) for f in features]+([('close',{})] if features and not shown else [])
        def calls(plan):
            return [dict(call=dict(contractVersion=CONTRACT_VERSION,runId=self.run,fixtureUrl=self.source.fixture_url,
                         ticket=secrets.token_hex(16),verb=verb,inputs=inputs),phase='planned') for verb,inputs in plan]
        rounds=[] if self.state is None else self.state['rounds']
        rounds.append(dict(ordinal=len(rounds)+1,stage=stage,binding=self.binding,phase='turning-off',active=active,native=native,
            graphics=ui,shown=shown,features=features,captureFeatures=list(FIELDS),offCalls=calls(off),restoreCalls=calls(restore),offNative=None,
            restoredNative=None,restoredGraphics=None,roles=dict(primary=None,actor=None)))
        self.state=dict(rounds=rounds);self.save();return deepcopy(rounds[-1])

    def steps(self,row,key):
        for step in row[key]:
            self.phase(row)
            if step['phase']=='observed':continue
            if step['phase']=='planned':step['phase']='issued';self.save()
            # Preferences persist the lower-level one-send intent. Repetition
            # after a lost return reads that same call; it cannot resend input.
            self.preferences.act(step['call']);step['phase']='observed';self.save()

    def advance_primary(self):
        """Whole owner calls with ordinary-input authority; never an actor API."""
        self.lock.assert_held();need(self.state is not None);row=self.state['rounds'][-1];self.phase(row)
        if row['phase']=='turning-off':
            self.steps(row,'offCalls');row['offNative']=deepcopy(self.preferences.source());row['phase']='off';self.save()
        if row['phase']=='off':
            if any(i is None or i['phase']!='observed' for i in row['roles'].values()):return False
            row['phase']='restoring';self.save()
        if row['phase']=='restoring':
            self.steps(row,'restoreCalls');_surface,ui,shown=self.preferences.status();packet=self.preferences.source()
            need(shown==row['shown'] and shown==(TokenGraphicsUI.row(ui,'graphics.page') is not None)
                 and same(packet['graphics'],row['native']['graphics']))
            row.update(phase='complete',restoredNative=deepcopy(packet),restoredGraphics=deepcopy(ui));self.save()
        need(row['phase']=='complete');return True

    @staticmethod
    def capture_features(row):return row.get('captureFeatures',row['features'])

    def verify_refs(self,row,observer,refs):
        exact(refs,set(self.capture_features(row)))
        for feature,ref in refs.items():
            need(ref['stage']==row['stage']);frame,_raw,actual,_name=observer.frame(ref,row['binding'])
            need(frame['provider']['ticket']==row['active']['ticket'] and not actual['state'][feature]
                 and not actual['state'][feature+'Pass'])
            follow_native(row['offNative'],frame['clockJoin']['nativeBefore'])
        return deepcopy(refs)

    def capture(self,observer):
        """Each credentialed role supplies its own observer, never copied facts."""
        self.lock.assert_held();need(isinstance(observer,IOSGraphicsObserver) and observer.run==self.run
             and observer.source.client is self.source.client and observer.lock is self.lock and self.state is not None)
        row=self.state['rounds'][-1];need(row['phase']=='off' and observer.state['stage']==row['stage']
             and same(observer.current_binding,row['binding']));self.phase(row);role=observer.role;item=row['roles'][role]
        if item is None:
            item=dict(phase='capturing',before=deepcopy(observer.previous),refs=None);row['roles'][role]=item;self.save()
        observer.decode(item['before'])
        if item['phase']=='observed':return self.verify_refs(row,observer,item['refs'])
        if same(observer.previous,item['before']):refs=observer.seed_off(self.capture_features(row),row['stage'])
        else:
            # A committed seed whose return was lost is adopted by immutable
            # reference and original input barrier, with no second GPU request.
            need(observer.state['phase']=='ready')
            refs={f:deepcopy(observer.state['offFrames'][f]) for f in self.capture_features(row)};need(all(refs.values()))
        item.update(phase='observed',refs=self.verify_refs(row,observer,refs));self.save();return deepcopy(item['refs'])
