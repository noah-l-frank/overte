"""Owned passive Avatar UI/HTTP/timer originals after NodeList logout reset.

No World, renderer or nonnull Avatar-session source is requested here. Every
source and clock query is owned before send; account causality admits the closed
postlogout consumer. This component cannot establish complete paired cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters import original_marker_clock_queries as clock_queries
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import decode,exact,integer,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_key_packets import OriginalKeyPackets
from adapters.original_frame_store import MAX_FRAMES
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import avatar_scripts,avatar_social_http,people_model,avatar_ui_inventory,normal_input,world_web_keys
from ios.adapters.authentication_causality import check as account_causality
from ios.adapters.avatar_code import pins
from ios.adapters.native_geometry import OriginalGeometry,validate as geometry_receipt
from ios.adapters.avatar_ui_work import drained_since
from ios.adapters.emote_native_prefix import follow

VERSION=2
READS=(1,2)
CHANNELS=dict(scripts=avatar_scripts,http=avatar_social_http,people=people_model)
SOURCES=dict(CHANNELS,keys=world_web_keys)


class LegacyAvatarTail2:
    PROFILE='avatar'
    def __init__(self,store,root,binding,run,role,subject,lock,guard,factory,*,child_run,fixture_url,ticket,baseline,logout_before,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor') and subject in ('primary','actor')
            and all(callable(fn) for fn in (guard,factory,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.subject,self.lock=store,Path(root),context(binding),identifier(run),role,subject,lock
        need(store.path.parent==lock.path.parent and store.path.name=='ios-avatar-'+role+'-'+subject+'-postlogout-tail.json');lock.assert_held()
        self.guard,self.factory,self.epoch_ms,self.monotonic,self.historical=guard,factory,epoch_ms,monotonic,False
        self.inputs=dict(childRunId=identifier(child_run),fixtureUrl=fixture_url,ticket=identifier(ticket),baseline=deepcopy(baseline),logoutBefore=deepcopy(logout_before))
        self.key_originals=OriginalKeyPackets(root,binding,run,role,subject,guard,self.key_storage,profile='avatar',monotonic=monotonic)
        self.previous=store.read();self.state=dict(rows=[],pending=None)
        if self.previous is not None:self.state=self.parse(self.previous)

    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,subject,lock,child_run,fixture_url,ticket,baseline,logout_before):
        class Frozen(PrivateFeatureState):
            def read(_self):return deepcopy(value)
            def write(_self,*_args):need(False)
            def discard(_self,*_args):need(False)
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.subject,result.lock=Frozen(store.path),Path(root),context(binding),identifier(run),role,subject,lock
        lock.assert_held();need(role in ('primary','actor') and subject in ('primary','actor'))
        result.inputs=dict(childRunId=identifier(child_run),fixtureUrl=fixture_url,ticket=identifier(ticket),baseline=deepcopy(baseline),logoutBefore=deepcopy(logout_before))
        result.historical=True;result.key_originals=OriginalKeyPackets(root,binding,run,role,subject,lambda:True,lambda *_:need(False),profile='avatar')
        result.previous=deepcopy(value);result.state=result.parse(value);return result

    def envelope(self,state,version=VERSION):return dict(iosAvatarPostLogoutTailVersion=version,runId=self.run,role=self.role,subject=self.subject,binding=self.binding,
        artifactRoot=str(self.root),inputs=deepcopy(self.inputs),payload=pack([state]))
    def file(self,index):
        need(integer(index,1,128));return PrivateFeatureState(self.root/('avatar-'+self.subject+'-postlogout-tail-'+self.run+'-'+self.role+'-'+str(index)+'.json'))
    def bound(self):self.lock.assert_held();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.parse(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def partial(self,p):
        exact(p,{'index','nativeQueries','queries','raws','widgetsQuery','widgetsReceipt','join','record'}|({'keyRaws','geometryQuery','geometryRaws'} if 'keyRaws' in p else set()))
        need(integer(p['index'],1,128));clock_queries.queries(p['nativeQueries'],int(self.binding['processIdentity']),strict=False)
        need(type(p['queries']) is dict and set(p['queries'])<=set(SOURCES) and type(p['raws']) is dict and set(p['raws'])<=set(CHANNELS))
        for name,query in p['queries'].items():SOURCES[name].command(query);need(query['runId']==self.run)
        for name,rows in p['raws'].items():
            need(name in p['queries'] and type(rows) is list and len(rows)<=51 and all(type(raw) is str and len(raw.encode())<=CHANNELS[name].LIMIT for raw in rows))
        if 'keyRaws' in p:
            need(type(p['keyRaws']) is list and len(p['keyRaws'])<=61)
            for index,original in enumerate(p['keyRaws']):
                self.key_originals.original(original)
                if index:need(original['index']==p['keyRaws'][index-1]['index']+1)
                if original['phase']=='saved':self.key_raw(original)
                else:need(index==len(p['keyRaws'])-1)
            need(type(p['geometryRaws']) is list and len(p['geometryRaws'])<=61 and all(type(raw) is str and len(raw.encode())<=65536 for raw in p['geometryRaws']))
            if p['geometryQuery'] is not None:self.geometry_query(p['geometryQuery'])
            else:need(not p['geometryRaws'])
        else:need('keys' not in p['queries'])
        if p['widgetsQuery'] is not None:
            q=p['widgetsQuery'];exact(q,{'schemaVersion','commandId','action','operation'})
            need(type(q['schemaVersion']) is int and q['schemaVersion']==1 and q['action']=='normal-ui-input' and q['operation']=='observe')
            identifier(q['commandId'][4:]);need(q['commandId'].startswith('ios-'))
        if p['widgetsReceipt'] is not None:need(p['widgetsQuery'] is not None and type(p['widgetsReceipt']) is dict)
        if p['join'] is not None:need(type(p['join']) is dict)
        if p['record'] is not None:need(type(p['record']) is dict)

    def parse(self,value):
        exact(value,{'iosAvatarPostLogoutTailVersion','runId','role','subject','binding','artifactRoot','inputs','payload'})
        version=value['iosAvatarPostLogoutTailVersion'];need(type(version) is int and version in READS)
        states=unpack(value['payload']);need(len(states)==1 and same(value,self.envelope(states[0],version)));state=states[0];exact(state,{'rows','pending'})
        need(type(state['rows']) is list and len(state['rows'])<=128);previous=None;partials=[];key_index=0
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','status','partial','reference'});need(integer(row['index'],1,128) and row['index']==index and row['partial']['index']==index and row['status'] in ('observed','abandoned'))
            self.partial(row['partial'])
            if version==1:need('keyRaws' not in row['partial'])
            for raw in row['partial'].get('keyRaws',[]):key_index+=1;need(raw['index']==key_index)
            if row['status']=='observed':
                current=self.record(row['reference']);self.validate(current,previous);need(current['index']==index==row['reference']['index']
                    and (same(row['reference'],row['partial']['record']) if 'keyRaws' in row['partial'] else same(self.file(index).read(),row['partial']['record']))
                    and all(same(current[key],row['partial'][key]) for key in ('nativeQueries','queries','widgetsQuery','widgetsReceipt'))
                    and same(current['clockJoin'],row['partial']['join']))
                for name,packet in current['packets'].items():
                    matched=False
                    for raw in row['partial']['raws'][name]:
                        try:original=decode(raw)
                        except ValueError:continue
                        if same(original,packet):matched=True
                    need(matched)
                need(('keys' in current)==('keyRaws' in row['partial']))
                if 'keys' in current:
                    need(current['keys']==row['partial']['keyRaws'][-1]);self.key_floors(row['partial']['keyRaws'][:-1],current)
                if 'keys' in current:
                    need(same(current['geometryQuery'],row['partial']['geometryQuery']));matched=False
                    for raw in row['partial']['geometryRaws']:
                        try:receipt=decode(raw)
                        except (ValueError,UnicodeError):continue
                        if same(receipt,current['geometry']):matched=True
                    need(matched)
                for old in partials:self.floors(old,current)
                previous=current
            else:need(row['reference'] is None and row['partial']['record'] is None);partials.append(row['partial'])
        if state['pending'] is not None:
            self.partial(state['pending']);need(state['pending']['index']==len(state['rows'])+1)
            if version==1:need('keyRaws' not in state['pending'])
            for raw in state['pending'].get('keyRaws',[]):key_index+=1;need(raw['index']==key_index)
        elif len(state['rows'])<128 and not self.historical:need(self.file(len(state['rows'])+1).read() is None)
        return deepcopy(state)

    def record(self,reference):
        exact(reference,{'index','sha256'});value=self.file(reference['index']).read();need(value is not None and digest(value)==reference['sha256'])
        exact(value,{'iosAvatarPostLogoutTailOriginalVersion','runId','role','subject','binding','payload'})
        need(type(value['iosAvatarPostLogoutTailOriginalVersion']) is int and value['iosAvatarPostLogoutTailOriginalVersion'] in READS and value['runId']==self.run
            and value['role']==self.role and value['subject']==self.subject and same(value['binding'],self.binding))
        rows=unpack(value['payload']);need(len(rows)==1 and ('keys' in rows[0])==(value['iosAvatarPostLogoutTailOriginalVersion']==2));return rows[0]

    def validate(self,value,previous=None):
        exact(value,{'index','nativeQueries','queries','packets','widgetsQuery','widgetsReceipt','clockJoin'}|({'keys','geometryQuery','geometry'} if 'keys' in value else set()))
        need(integer(value['index'],1,128));pid=int(self.binding['processIdentity']);clock_queries.bracket('avatar',value,pid)
        exact(value['queries'],set(SOURCES) if 'keys' in value else set(CHANNELS));exact(value['packets'],set(CHANNELS))
        originals=deepcopy(value['packets']);originals['widgets']=value['widgetsReceipt']['observation']
        for name,module in CHANNELS.items():
            module.validate(value['packets'][name],value['queries'][name],pid,previous=None if previous is None else previous['packets'][name])
            p=value['packets'][name];need(p['runId']==self.run);originals[name+'Clock']=dict(capturedEpochMs=p['clockAfter']['epochMs'])
        if 'keys' in value:
            keys=self.keys(value);prior=self.keys(previous) if previous is not None and 'keys' in previous else None
            world_web_keys.validate(keys,value['queries']['keys'],pid,previous=prior)
            originals['keys']=keys;originals['keysClock']=dict(capturedEpochMs=keys['clockAfter']['epochMs'])
            self.geometry(value,previous);originals['geometry']=value['geometry'];originals['geometryClock']=dict(sampleEpochMs=value['geometry']['observation']['sampleEpochMs'])
        q,receipt=value['widgetsQuery'],value['widgetsReceipt'];exact(q,{'schemaVersion','commandId','action','operation'})
        need(q['action']=='normal-ui-input' and q['operation']=='observe' and type(q['schemaVersion']) is int and q['schemaVersion']==1)
        import re
        need(type(q['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',q['commandId']) is not None)
        exact(receipt,{'schemaVersion','commandId','observation'});need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and receipt['commandId']==q['commandId'])
        join=validate_join(value['clockJoin'],originals);before,after=join['nativeBefore'],join['nativeAfter'];follow(before,after)
        for native in (before,after):native_packet(native,native['requestId'],pid,native['capturedEpochMs'],require_account=True)
        normal_input.observation(originals['widgets'],pid,after['capturedEpochMs'])
        need(before['capturedEpochMs']<=originals['widgets']['sampleEpochMs']<=after['capturedEpochMs'])
        if 'keys' in value:need(before['capturedEpochMs']<=value['geometry']['observation']['sampleEpochMs']<=after['capturedEpochMs'])
        for name in SOURCES if 'keys' in value else CHANNELS:
            packet=self.keys(value) if name=='keys' else value['packets'][name]
            need(before['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=after['capturedEpochMs'])
        if previous is not None:
            follow(previous['clockJoin']['nativeAfter'],before)
            need(join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
            self.widget_prefix(previous['widgetsReceipt']['observation'],originals['widgets'])
        return value

    def widget_prefix(self,before,after):
        for value in (before,after):normal_input.observation(value,int(self.binding['processIdentity']),value['sampleEpochMs'])
        need(before['instance']==after['instance'] and all(after[k]>=before[k] for k in ('sampleEpochMs','elapsedMs','lastSequence')))
        for key in ('avatarSourceSequence','emoteSourceSequence','placesSourceSequence','navigationDialogSourceSequence'):
            if key in before:need(key in after and after[key]>before[key])

    @staticmethod
    def geometry_query(value):
        exact(value,{'schemaVersion','commandId','action'})
        import re
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='native-geometry-snapshot'
            and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']) is not None)

    def geometry(self,value,previous=None):
        self.geometry_query(value['geometryQuery']);document,_rect=geometry_receipt(value['geometry'],value['geometryQuery']['commandId'],
            native_epoch_ms=value['geometry']['observation']['sampleEpochMs'])
        need(type(document['schemaVersion']) is int and document['schemaVersion']==1 and integer(document['sampleEpochMs'],1))
        if previous is not None and 'geometry' in previous:
            before=self.geometry(previous);need(document['sampleSequence']>before['sampleSequence'] and document['sampleEpochMs']>=before['sampleEpochMs'])
        return document

    def key_raw(self,original):
        return self.key_originals.read(original)

    def keys(self,record):
        need(type(record) is dict and 'keys' in record);value=self.key_raw(record['keys'])
        need(same(value['query'],record['queries']['keys']));return decode(value['raw'],limit=world_web_keys.LIMIT)

    def next_key_index(self):
        rows=[ref['index'] for row in self.state['rows'] for ref in row['partial'].get('keyRaws',[])]
        if self.state['pending'] is not None:rows += [ref['index'] for ref in self.state['pending'].get('keyRaws',[])]
        return max([0,*rows])+1

    def key_storage(self,kind,original):
        self.bound();p=self.state['pending'];need(kind=='original' and p is not None and 'keyRaws' in p)
        self.key_originals.original(original);index=self.next_key_index()
        if original['phase']=='planned':need(original['index']==index);p['keyRaws'].append(deepcopy(original))
        else:
            old=p['keyRaws'][-1];need(original['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(original[k],old[k]) for k in original if k not in ('phase','file')) and (old['phase']=='planned' or same(original['file'],old['file'])))
            p['keyRaws'][-1]=deepcopy(original)
        self.save()

    def key_floors(self,originals,current):
        for original in originals:
            need(original['phase']=='saved')
            raw=self.key_raw(original)
            try:value=decode(raw['raw'],limit=world_web_keys.LIMIT)
            except (ValueError,UnicodeError):continue
            if type(value) is dict and value.get('requestId')==raw['query']['commandId']:
                world_web_keys.validate(value,raw['query'],int(self.binding['processIdentity']))
                actual=self.keys(current)
                if not same(actual,value):world_web_keys.validate(actual,current['queries']['keys'],int(self.binding['processIdentity']),previous=value)

    def floors(self,partial,current):
        clock_queries.floor('avatar',partial,current,int(self.binding['processIdentity']))
        retained=partial['widgetsReceipt']
        if retained is not None:
            exact(retained,{'schemaVersion','commandId','observation'})
            need(type(retained['schemaVersion']) is int and retained['schemaVersion']==1
                and retained['commandId']==partial['widgetsQuery']['commandId'])
            self.widget_prefix(retained['observation'],current['widgetsReceipt']['observation'])
        if partial.get('geometryQuery') is not None:
            for raw in partial['geometryRaws']:
                try:receipt=decode(raw)
                except (ValueError,UnicodeError):continue
                if type(receipt) is dict and receipt.get('commandId')==partial['geometryQuery']['commandId']:
                    self.geometry(current,dict(geometryQuery=partial['geometryQuery'],geometry=receipt))
        self.key_floors(partial.get('keyRaws',[]),current)
        for name,rows in partial['raws'].items():
            for raw in rows:
                try:value=decode(raw)
                except ValueError:continue
                if type(value) is dict and value.get('requestId')==partial['queries'][name]['commandId']:
                    CHANNELS[name].validate(value,partial['queries'][name],int(self.binding['processIdentity']))
                    CHANNELS[name].validate(current['packets'][name],current['queries'][name],int(self.binding['processIdentity']),previous=value)

    def recover(self):
        self.bound();p=self.state['pending']
        if p is None:return None
        need(all(original['phase']=='saved' for original in p.get('keyRaws',[])))
        if p['record'] is None:row=dict(index=p['index'],status='abandoned',partial=deepcopy(p),reference=None)
        else:
            store=self.file(p['index']);old=store.read()
            if old is None:store.write(p['record'],None)
            else:need(same(old,p['record']))
            ref=dict(index=p['index'],sha256=digest(p['record']));self.validate(self.record(ref));row=dict(index=p['index'],status='observed',partial=deepcopy(p),reference=ref)
            if 'keyRaws' in p:row['partial']['record']=deepcopy(ref)
        self.state['rows'].append(row);self.state['pending']=None;self.save();return deepcopy(row)

    def capture(self):
        self.bound();self.recover();need(len(self.state['rows'])<128 and self.next_key_index()+60<=MAX_FRAMES)
        actual=self.factory();need(same(actual['binding'],self.binding));self.native=actual['clock_source'];need(not self.native.native_clock_bound)
        readers={name:getattr(actual['observer'],{'scripts':'avatar_scripts','http':'avatar_social_http','people':'people_model','keys':'world_web_keys'}[name])(self.native) for name in SOURCES}
        last=next((self.record(row['reference']) for row in reversed(self.state['rows']) if row['status']=='observed'),None)
        if last is not None:
            from adapters.native_clock_source_history import restore
            restore(self.native,last['clockJoin']['nativeAfter'])
            for name,reader in readers.items():reader.last=deepcopy(self.keys(last) if name=='keys' and 'keys' in last else last['packets'].get(name))
        p=dict(index=len(self.state['rows'])+1,nativeQueries=[],queries={},raws={},widgetsQuery=None,widgetsReceipt=None,join=None,record=None,keyRaws=[],geometryQuery=None,geometryRaws=[])
        self.state['pending']=p;self.save();packets={};key_packet=None
        with clock_queries.owned(self):
            window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(self.epoch_ms())
            account_causality(dict(contractVersion=16,runId=self.inputs['childRunId'],fixtureUrl=self.inputs['fixtureUrl'],
                ticket=self.inputs['ticket'],verb='logout',inputs={}),self.inputs['logoutBefore'],window.started['nativeBefore'],window.started['nativeBefore']['capturedEpochMs'])
            for name,reader in readers.items():
                send,read=reader.send,reader.original
                def sending(query,name=name,send=send):
                    p['queries'][name]=deepcopy(query)
                    if name!='keys':p['raws'][name]=[]
                    self.save();return send(query)
                def reading(name=name,read=read):
                    raw=read()
                    if name=='keys':
                        need(type(raw) is str and len(raw.encode())<=world_web_keys.LIMIT)
                        self.key_originals.write(self.next_key_index(),p['queries']['keys'],raw)
                    else:
                        rows=p['raws'][name]
                        if not rows or rows[-1]!=raw:rows.append(raw);self.save()
                    return raw
                reader.send,reader.original=sending,reading
                try:
                    if name=='keys':key_packet=reader.read(self.run)
                    else:packets[name]=reader.read(self.run)
                finally:reader.send,reader.original=send,read
            geometry=actual['observer'].geometry();need(isinstance(geometry,OriginalGeometry))
            geometry.sequence=0 if last is None or 'geometry' not in last else last['geometry']['observation']['sampleSequence']
            geometry.epoch=0 if last is None or 'geometry' not in last else last['geometry']['observation']['sampleEpochMs']
            geometry.clock_ms=lambda:self.native.read(self.native.sequence)['capturedEpochMs']
            send,read=geometry.send,geometry.original
            def sending_geometry(query):need(p['geometryQuery'] is None);self.geometry_query(query);p['geometryQuery']=deepcopy(query);self.save();return send(query)
            def reading_geometry():
                raw=read()
                if not p['geometryRaws'] or p['geometryRaws'][-1]!=raw:p['geometryRaws'].append(raw);self.save()
                return raw
            geometry.send,geometry.original=sending_geometry,reading_geometry
            try:geometry_value=geometry.capture()
            finally:geometry.send,geometry.original=send,read
            widgets=actual['native'];intent=getattr(widgets,'observe_intent',None)
            def own(query):need(p['widgetsQuery'] is None);p['widgetsQuery']=deepcopy(query);self.save()
            widgets.observe_intent=own
            try:observed=widgets.capture()
            finally:
                if widgets.last_receipt is not None:p['widgetsReceipt']=deepcopy(widgets.last_receipt);self.save()
                widgets.observe_intent=intent
            originals=deepcopy(packets);originals['widgets']=observed;fields=[]
            need(key_packet is not None and p['keyRaws'] and p['keyRaws'][-1]['phase']=='saved')
            originals['keys']=key_packet;originals['keysClock']=dict(capturedEpochMs=key_packet['clockAfter']['epochMs']);fields.append(('keysClock','capturedEpochMs'))
            originals['geometry']=geometry_value;originals['geometryClock']=dict(sampleEpochMs=geometry_value['observation']['sampleEpochMs']);fields.append(('geometryClock','sampleEpochMs'))
            for name,packet in packets.items():originals[name+'Clock']=dict(capturedEpochMs=packet['clockAfter']['epochMs']);fields.append((name+'Clock','capturedEpochMs'))
            fields.append(('widgets','sampleEpochMs'))
            join=window.finish(originals,fields);p['join']=join;self.save()
        value=dict(index=p['index'],nativeQueries=deepcopy(p['nativeQueries']),queries=deepcopy(p['queries']),packets=packets,
            widgetsQuery=deepcopy(p['widgetsQuery']),widgetsReceipt=deepcopy(p['widgetsReceipt']),clockJoin=join,keys=deepcopy(p['keyRaws'][-1]),geometryQuery=deepcopy(p['geometryQuery']),geometry=deepcopy(geometry_value))
        self.validate(value,last)
        for row in self.state['rows']:
            if row['status']=='abandoned':self.floors(row['partial'],value)
        p['record']=dict(iosAvatarPostLogoutTailOriginalVersion=VERSION,runId=self.run,role=self.role,subject=self.subject,binding=self.binding,payload=pack([value]));self.save()
        row=self.recover();self.proof(row);a=join;now,mono=self.epoch_ms(),self.monotonic()
        need(a['hostAfterEpochMs']<=now<a['hostBeforeEpochMs']+1500 and a['hostAfterMonotonic']<=mono<a['hostBeforeMonotonic']+1.5
            and abs(now-a['hostBeforeEpochMs']-(mono-a['hostBeforeMonotonic'])*1000)<=250);return row

    def proof(self,row):
        need(row in self.state['rows'] and row['status']=='observed');value=self.validate(self.record(row['reference']));join=value['clockJoin']
        call=dict(contractVersion=16,runId=self.inputs['childRunId'],fixtureUrl=self.inputs['fixtureUrl'],ticket=self.inputs['ticket'],verb='logout',inputs={})
        for packet in (join['nativeBefore'],join['nativeAfter']):account_causality(call,self.inputs['logoutBefore'],packet,packet['capturedEpochMs'])
        baseline=self.inputs['baseline'];scripts=value['packets']['scripts'];managers={worker['membership']['instance'] for worker in baseline['scripts']['source']['workers'] if worker['avatar']['code']}
        work=drained_since(baseline['scripts'],scripts,managers,pins());need(avatar_scripts.drained(scripts,managers))
        need(all('uiWork' in worker for worker in scripts['source']['workers'] if worker['avatar']['code']))
        need(all(timer['depth']==timer['pendingDispatch']==0 for worker in scripts['source']['workers'] if 'uiWork' in worker for timer in worker['uiWork']['timers']))
        need(people_model.drained(value['packets']['people']) and avatar_ui_inventory.absent(value['widgetsReceipt']['observation'])
            and not value['widgetsReceipt']['observation']['tabletShown'])
        keyboard=None
        if 'keys' in value:
            world_web_keys.privacy_qualified(self.keys(value))
            keyboard=world_web_keys.drained(self.keys(value));ui=self.geometry(value)['nativeUi']
            need(ui.get('keyboardVisible') is False and type(ui.get('keyboardVisible')) is bool and number(ui.get('imeInsetBottom'),0,10000) and ui['imeInsetBottom']==0)
        old=avatar_social_http.events(baseline['http']);now=avatar_social_http.events(value['packets']['http']);owned=set(now)-set(old)
        if owned:need(avatar_social_http.drained(value['packets']['http'],sorted(owned)))
        proof=dict(iosAvatarPostLogoutTailProofVersion=2 if 'keys' in value else 1,originalSha256=row['reference']['sha256'],ownedHttp=sorted(owned),timers=work,
            endpointEpochMs=max([work['endpointEpochMs'],*[event['clock']['epochMs'] for event in value['packets']['http']['events'] if event['xhrId'] in owned]]))
        if keyboard is not None:
            proof['keys']=keyboard
            proof['endpointEpochMs']=max([proof['endpointEpochMs'],*[event['epochMs'] for event in keyboard['events']]])
        return proof
