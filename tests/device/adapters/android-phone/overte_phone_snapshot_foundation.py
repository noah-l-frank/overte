"""Bind the existing five-output SNAP foundation to original cleanup owners.

This layer owns no feature verdict. The unchanged snapshot_journey decodes the
actual outputs. A separate explicit scope owns native files/settings; it can
never be adopted as a subsequent extended feature run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
import uuid
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_snapshot_settings import validate as settings_source
from overte_phone_snapshot_capture_source import prefix,nonce

VERSION=1


class PhoneSnapshotFoundation:
    def __init__(self,adapter,selector,root,binding,guard,*,monotonic=time.monotonic,sleep=time.sleep):
        context(binding);need(all(callable(fn) for fn in (guard,monotonic,sleep)))
        self.adapter,self.selector,self.root,self.context=adapter,selector,Path(root),deepcopy(binding)
        self.guard,self.monotonic,self.sleep=guard,monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-snapshot-foundation.json'))
        self.store._parent();PrivateFeatureState(self.root/'snapshot-foundation-boundary.json')._parent()
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.state=self.previous=self.flow=None;self.file_owner=None

    def checked(self):need(self.guard() is not False)

    def load(self):
        self.checked();self.previous=self.store.read();self.state=deepcopy(self.previous)
        if self.state is None:return
        value=self.state
        exact(value,{'snapshotFoundationVersion','binding','artifactRoot','scope','phase','prefixes','settings','original','restoreId','expectedSha256','quiet','filesBinding'})
        need(type(value['snapshotFoundationVersion']) is int and value['snapshotFoundationVersion']==VERSION
            and context(value['binding'])==self.context and value['artifactRoot']==str(self.root) and nonce(value['scope'])
            and value['phase'] in ('preparing','active','closing','restoring','settings-restored','retired','archiving')
            and type(value['prefixes']) is list and len(value['prefixes'])<=5 and value['prefixes']==sorted(set(value['prefixes']))
            and all(prefix(name) and name.startswith('parity-') for name in value['prefixes']))
        if value['settings'] is not None:
            source=self.settings_value();request=dict(schemaVersion=1,action='phone-snapshot-settings',
                **{k:source[k] for k in ('commandId','runId','operation')})
            if source['operation']=='restore':request.update({k:source['source'][k] for k in ('restoreId','expectedSha256')})
            settings_source(source,request,self.pid,source['capturedEpochMs']);need(source['runId']==value['scope'])
            exact(value['original'],{'instance','openedEpochMs','sha256'})
            need(source['instance']==value['original']['instance'] and source['source']['openedEpochMs']==value['original']['openedEpochMs']
                and source['source']['originalSha256']==value['original']['sha256'])
        else:need(value['phase']=='preparing' and value['original'] is None)
        need((value['restoreId']==value['expectedSha256']=='') or (nonce(value['restoreId'])
            and type(value['expectedSha256']) is str and len(value['expectedSha256'])==64))
        need(type(value['quiet']) is list and len(value['quiet'])<=2)

    @property
    def pid(self):
        value=self.context['processIdentity'].split(':')[0];need(value.isdigit() and int(value)>0);return int(value)

    def save(self):
        self.checked();need(same(self.store.read(),self.previous));self.store.write(self.state,self.previous)
        need(same(self.store.read(),self.state));self.previous=deepcopy(self.state)

    def settings_value(self):
        rows=unpack(self.state['settings']);need(len(rows)==1);return rows[0]

    def settings(self):
        reader=self.adapter._snapshot_settings(self.selector,read_only=False)
        if self.state['settings'] is not None:reader.restore_source(self.settings_value())
        return reader

    def retain(self,value):
        self.state['settings']=pack([value]);self.save();return value

    def files_owner(self):
        if self.file_owner is None:
            self.file_owner=self.adapter._snapshot_capture_files(self.selector,self.root,
                self.store.path.with_name('phone-snapshot-foundation-'+self.state['scope']+'-files.json'),read_only=False)
        return self.file_owner

    def prepare(self):
        self.checked()
        if self.state is None:
            self.state=dict(snapshotFoundationVersion=VERSION,binding=deepcopy(self.context),artifactRoot=str(self.root),scope=uuid.uuid4().hex,
                phase='preparing',prefixes=[],settings=None,original=None,restoreId='',expectedSha256='',quiet=[],filesBinding=None);self.save()
        need(self.state['phase'] in ('preparing','active'))
        if self.state['settings'] is None:
            actual=self.settings().request(self.state['scope'],'capture');row=actual['source']
            self.state['original']=dict(instance=actual['instance'],openedEpochMs=row['openedEpochMs'],sha256=row['originalSha256'])
            self.retain(actual)

    def files(self,name):
        # Called by the existing PhoneSnapshot flow under this same source lock.
        self.lock.assert_held();self.checked()
        need(self.state is not None and self.state['phase']=='active' and self.flow is not None and prefix(name) and name.startswith('parity-'))
        owner=self.files_owner()
        if name not in self.state['prefixes']:
            need(len(self.state['prefixes'])<5)
            self.state['prefixes']=sorted([*self.state['prefixes'],name]);self.save()
        owner.plan(self.state['scope'],name)
        if not self.flow.state['capturePending']:
            # A preflight never hides an actual unfinished or foreign file.
            inventory=owner.inventory();need(not any(row['basename'].startswith(name+'-') for row in inventory['files']))
        return owner.files(name,allow_pending=self.flow.state['capturePending'])

    @staticmethod
    def idle(value):
        source=value['source'];latest={}
        for event in source['scriptHistory']['events']:latest[event['id']]=event['kind']
        return (not source['review']['present'] and not source['captures'] and not source['uploads']
            and not any(phase in ('pending','processing') for phase in latest.values()))

    def quiet(self):
        reader=self.adapter._snapshot_source(self.selector);start=prior=self.monotonic();need(number(start,0,1e15))
        first=None;history=None;samples=0
        for attempt in range(101):
            self.checked();value=reader.read(self.state['scope']);need(self.idle(value))
            source=value['source'];current=(source['history'],source['scriptHistory'])
            if history is None:history=deepcopy(current)
            else:need(same(current,history)) # No late allocation, timer or terminal activity.
            now=self.monotonic();need(number(now,prior,1e15) and now-start<20);prior=now
            if first is None:first=now
            samples+=1
            if now-first>=3 and samples>=2:
                return dict(startMonotonic=first,endMonotonic=now,samples=samples,sourceInstance=value['instance'],
                    capturedEpochMs=value['capturedEpochMs'])
            self.sleep(.1)
        raise NativeUIError('Original Snapshot foundation never reached its independent quiet window')

    def close(self):
        if self.state is None:return
        if self.state['phase']=='archiving':self.finalize();return
        if self.state['phase']=='retired':self.require_retired();return
        if self.state['settings'] is None:self.prepare() # Recover an uncertain original capture before any UI input.
        if self.state['phase'] not in ('restoring','settings-restored'):
            self.state['phase']='closing';self.save();self.state['quiet']=[self.quiet()];self.save()
            if self.state['prefixes']:
                self.files_owner().retire();self.files_owner().require_retired()
                self.state['filesBinding']=self.files_owner().binding();self.save()
            reader=self.settings();observed=reader.request(self.state['scope'],'observe');self.retain(observed)
            self.state.update(restoreId=uuid.uuid4().hex,expectedSha256=observed['source']['currentSha256'],phase='restoring');self.save()
        if self.state['phase']=='restoring':
            reader=self.settings();actual=reader.request(self.state['scope'],'restore',restore_id=self.state['restoreId'],expected_sha256=self.state['expectedSha256'])
            self.retain(actual);self.state['phase']='settings-restored';self.save()
        reader=self.settings();self.retain(reader.request(self.state['scope'],'retire'))
        self.state['quiet']=[self.state['quiet'][0],self.quiet()];self.state['phase']='retired';self.save()
        self.require_retired()

    def require_retired(self):
        need(self.state is not None and self.state['phase'] in ('retired','archiving') and len(self.state['quiet'])==2)
        reader=self.settings();actual=reader.request(self.state['scope'],'observe');need(actual['source']['retired'] and self.idle(self.adapter._snapshot_source(self.selector).read(self.state['scope'])))
        if self.state['prefixes']:
            owner=self.files_owner()
            if owner.store.read() is not None:owner.require_retired()
            else:
                need(self.state['phase']=='archiving');binding=self.state['filesBinding'];need(binding is not None)
                packet=self.adapter._snapshot_capture_file_source(self.selector,read_only=True).request(self.state['scope'])
                need(packet['instance']==binding['native']['instance'] and packet['source']['instance']==binding['native']['sourceInstance'])
                plans={row['prefix']:row for row in packet['source']['plans'] if row['runId']==self.state['scope']}
                need(same(plans,binding['plans']) and all(row['sealed'] for row in plans.values()))
                for name,row in plans.items():
                    scan=owner.transport.scan(name);owner.root(row,scan);need(not scan['files'])
                for row in packet['source']['rows']:
                    if row['runId']==self.state['scope']:need(row['closed'] and row['absent'] and nonce(row['retireId']))
                need(not any(self.root.glob('snapshot-owned-'+self.state['scope']+'-*')))
        self.retain(actual);return True

    def finalize(self):
        """After normal closure, retire both host journals with resumable intent."""
        try:
            with self.lock.held():
                self.load()
                if self.state is None:return True
                self.require_retired();self.state['phase']='archiving';self.save()
                if self.state['prefixes']:
                    owner=self.files_owner()
                    with owner.held():
                        if owner.state is not None:
                            owner.require_retired();need(owner.state['retired']);owner.store.discard(owner.state)
                self.require_retired();self.store.discard(self.previous);need(self.store.read() is None);self.checked();return True
        except Exception:raise NativeUIError('Original Snapshot foundation journal retirement failed') from None

    def invoke(self,flow,operation,arguments):
        try:
            with self.lock.held():
                self.load();self.flow=flow
                if operation=='snapshot.open':self.prepare()
                elif operation!='snapshot.close':need(self.state is not None and self.state['phase']=='active')
                answer=flow.invoke(operation,arguments)
                if operation=='snapshot.open':self.state['phase']='active';self.save()
                if operation=='snapshot.close':self.close();self.finalize()
                self.checked();return answer
        except Exception:raise NativeUIError('Original Snapshot foundation input or complete handback failed') from None
