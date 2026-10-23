"""Original raw settings after normal checked-control restoration and Close.

This read-only checkpoint never supplies a setting, a new input or a baseline.
Its closed bookends are independent of the later continuous Close quiet proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.snapshot_settings_baseline import PicoSnapshotSettingsBaseline
from adapters.pico4.snapshot_upload_owner import sha
from adapters.script_journey.history import pack,unpack,canonical
from feature_journeys.contract import typed_equal,json_document

VERSION=1


class PicoSnapshotSettingsClose:
    def __init__(self,parent,path):
        from adapters.pico4.snapshot_close_owner import PicoSnapshotCloseOwner
        need(isinstance(parent,PicoSnapshotCloseOwner))
        self.parent,self.run,self.binding,self.lock=parent,parent.run,deepcopy(parent.binding),parent.lock
        self.baseline=getattr(parent.base,'settings_baseline',None)
        need(isinstance(self.baseline,PicoSnapshotSettingsBaseline) and self.baseline.parent is parent.base
            and self.baseline.lock is self.lock and self.baseline.run==self.run and typed_equal(self.baseline.binding,self.binding))
        self.store=PrivateFeatureState(path);need(self.store.path==self.lock.path.with_name('snapshot-settings-close.json'))
        self.disk=self.state=self.state_sha=None
        with self.lock.held():
            parent.load();need(parent.encoding_version==2 and parent.state['stage'] in ('closed','quiet-issued','partial-closed'))
            self.baseline.load();need(self.baseline.state['stage']=='enveloped')
            self.identity=self.baseline.identity();self.phase=deepcopy(parent.state['source'])
            need(parent.base.encoding_version==3 and parent.base.disk['settingsBaselineOriginalSha256']==self.identity)
            self.controller=deepcopy(parent.state['controller']['envelope']);self.generation=parent.state['closedGeneration']
            self.load()

    def bound(self):
        self.lock.assert_held();self.parent.bound();self.baseline.bound()
        need(self.parent.encoding_version==2 and self.parent.state['stage'] in ('closed','quiet-issued','partial-closed')
            and self.parent.base.settings_baseline is self.baseline and self.baseline.parent is self.parent.base and self.baseline.lock is self.lock
            and typed_equal(self.parent.state['source'],self.phase) and typed_equal(self.parent.state['controller']['envelope'],self.controller)
            and self.parent.state['closedGeneration']==self.generation and self.baseline.identity()==self.identity
            and self.parent.base.encoding_version==3 and self.parent.base.disk['settingsBaselineOriginalSha256']==self.identity)
        if self.disk is not None:need(typed_equal(self.store.read(),self.disk) and sha(self.state)==self.state_sha
            and typed_equal(self.state,json_document(canonical(self.state))))
        return self.parent.native.monotonic()

    def frame(self,reference):
        exact(reference,{'index','sha256'});index=reference['index'];need(integer(index,0,len(self.parent.state['frames'])-1))
        row=self.parent.state['frames'][index];need(reference['sha256']==sha(row) and not row['base']['ui']['open']
            and row['base']['ui']['generation']==self.generation and index>self.parent.state['controller']['before'])
        actual=[sample['value'] for sample in self.parent.state['neutrals'] if sample['frame']==index];need(len(actual)==1)
        self.parent.neutral(actual[0],row,self.parent.state);return row

    def reference(self):
        index=len(self.parent.state['frames'])-1;return dict(index=index,sha256=sha(self.parent.state['frames'][index]))

    def validate(self,state):
        exact(state,{'stage','before','baselineIndex','settings','after'})
        need(state['stage'] in ('read-issued','captured','observed') and integer(state['baselineIndex'],0,31))
        before=self.frame(state['before']);observations=self.baseline.state['observations'];index=state['baselineIndex']
        if state['settings'] is None:
            # A crash after the child's original CAS may leave exactly one
            # already committed answer. Recovery adopts that answer, never a
            # later unrelated source read or a reconstructed baseline.
            need(state['stage']=='read-issued' and state['after'] is None and len(observations) in (index,index+1));return
        need(len(observations)>index and typed_equal(observations[index],state['settings']))
        packet=self.baseline.packet(state['settings']);original=self.baseline.originals.get('settings',state['settings'])
        before_epoch=decode(before['base']['native']['raw'])['capturedEpochMs']
        need(packet['source']['entriesEpochMs']>=before_epoch and original['anchor']['hostMonotonic']>=before['hostMonotonic'])
        if state['after'] is None:need(state['stage']=='captured');return
        need(state['stage']=='observed' and state['after']['index']>state['before']['index']);after=self.frame(state['after'])
        need(decode(after['base']['native']['raw'])['capturedEpochMs']>=packet['capturedEpochMs']
            and after['hostMonotonic']>=original['anchor']['hostMonotonic'])

    def load(self):
        self.bound();disk=self.store.read();need(self.disk is None or typed_equal(self.disk,disk))
        if disk is None:need(self.state is None);return
        exact(disk,{'snapshotSettingsCloseVersion','runId','binding','fixtureUrl','baselineSha256','phase','controller','closedGeneration','payload'})
        need(type(disk['snapshotSettingsCloseVersion']) is int and disk['snapshotSettingsCloseVersion']==VERSION and disk['runId']==self.run
            and typed_equal(disk['binding'],self.binding) and disk['fixtureUrl']==self.parent.source.fixture_url and disk['baselineSha256']==self.identity
            and typed_equal(disk['phase'],self.phase) and typed_equal(disk['controller'],self.controller) and disk['closedGeneration']==self.generation)
        rows=unpack(disk['payload']);need(len(rows)==1);state=rows[0];self.validate(state)
        self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def save(self,state):
        self.bound();self.validate(state)
        disk=dict(snapshotSettingsCloseVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.parent.source.fixture_url,
            baselineSha256=self.identity,phase=self.phase,controller=self.controller,closedGeneration=self.generation,payload=pack([state]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def seal(self):
        # The last exact Close phase/guard is after report construction and all
        # checkpoint CAS work. Only clock/host validation follows it.
        self.parent.fence();packet=self.baseline.packet(self.state['settings'])
        original=self.baseline.originals.get('settings',self.state['settings']);anchor=original['anchor']
        epoch=self.parent.native.clock_ms();completed=self.bound();oldest=min(packet['capturedEpochMs'],packet['source']['entriesEpochMs'])
        need(number(epoch,1,1e15) and number(completed,anchor['hostMonotonic'],1e15) and -250<=epoch-oldest
            and max(epoch-oldest,anchor['nativeEpochMs']-oldest+(completed-anchor['hostMonotonic'])*1000)<=1500)

    def observe(self):
        with self.lock.held():
            self.load()
            if self.state is None:
                self.parent.observe();before=self.reference()
                self.save(dict(stage='read-issued',before=before,baselineIndex=len(self.baseline.state['observations']),settings=None,after=None))
            if self.state['stage']=='read-issued':
                index=self.state['baselineIndex'];observations=self.baseline.state['observations']
                if len(observations)==index:
                    if self.parent.anchor is None:self.parent.observe()
                    self.parent.fence();self.baseline.observe()
                need(len(self.baseline.state['observations'])==index+1)
                state=deepcopy(self.state);state.update(stage='captured',settings=deepcopy(self.baseline.state['observations'][index]));self.save(state)
            if self.state['stage']=='captured':
                self.parent.observe();state=deepcopy(self.state);state.update(stage='observed',after=self.reference());self.save(state)
            result=self.report();self.seal();return result

    def report(self):
        self.bound();need(self.state is not None and self.state['stage']=='observed');self.validate(self.state)
        before=self.baseline.packet(self.baseline.state['original'])['source'];after=self.baseline.packet(self.state['settings'])['source']
        return dict(qualification='PICO_SNAPSHOT_CLOSED_RAW_SETTINGS_OBSERVATION_ONLY',originalPreinputBaseline=True,
            originalClosedBookends=True,typedSettingsMatchOriginal=before['typedSha256']==after['typedSha256']
                and typed_equal(before['entries'],after['entries']) and typed_equal(before['formatCache'],after['formatCache']),
            entryProjectionDifferences=[key for key in sorted(before['entries']) if not typed_equal(before['entries'][key],after['entries'][key])],
            formatCacheProjectionChanged=not typed_equal(before['formatCache'],after['formatCache']),
            settingsRestored=False,continuousQuiet=False,fullSnapshotRecipe=False,deviceAcceptance=False,journalRetained=True)
