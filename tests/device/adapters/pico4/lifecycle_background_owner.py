"""One-send ordinary HOME/return joined to original Lifecycle Chat sources.

Cold recovery reads only private archives and original OS process/foreground
status until the existing process is actually foreground again. No native
foreground guard is weakened and no uncertain input is delivered twice.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.pico4.lifecycle_background_state5 import helper_method
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_background as proof,lifecycle_background_source as source,lifecycle_source as ui,lifecycle_drive as drive,lifecycle_gesture as gesture
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft
from adapters.pico4.lifecycle_background_originals import LifecycleBackgroundOriginals
from adapters.pico4.lifecycle_world import PicoLifecycleWorld,neutral
from adapters.script_journey.history import canonical,pack,unpack
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
PHASES=('prepared','arm-issued','armed','home-issued','background-observed','resume-issued','returned','quiet','release-issued','released')
ARCHIVES=('lifecycle-chat-owner.json','lifecycle-editor-owner.json','lifecycle-x-join.json','lifecycle-x-back-owner.json')


class PicoLifecycleBackground:
    def __init__(self,path,run,binding,source_lock,os_status,os_input,runtime,*,monotonic=time.monotonic,sleep=time.sleep,raw_layout=None,state_layout=None):
        need(ui.nonce(run) and isinstance(source_lock,ScriptSourceLock)
            and all(callable(f) for f in (os_status,os_input,runtime,monotonic,sleep)))
        self.store,self.run,self.binding=PrivateFeatureState(path),run,deepcopy(context(binding));self.pid,_start=proof.identity(binding)
        self.lock=source_lock;need(self.store.path.name=='lifecycle-background-owner.json' and self.lock.path==self.store.path.with_name('script-sources.lock'))
        self.os_status,self.os_input,self.runtime_factory=os_status,os_input,runtime
        self.monotonic,self.sleep=monotonic,sleep;self.runtime=None;self.disk=self.state=self.last_clock=self.fresh_anchor=None
        need(state_layout is None or type(state_layout) is int and state_layout==5)
        self.state5=self._state5=None;self._plain5=False
        self._state_choice=self._original_state_choice=(state_layout,)
        self.version=VERSION
        with self.lock.held():
            self.disk=self.store.read()
            if raw_layout is None:
                raw_path=self.store.path.with_name('lifecycle-background-raw.json')
                need(not raw_path.exists() and not list(raw_path.parent.glob(raw_path.name+'.*')))
                self.originals=LifecycleBackgroundOriginals(self.store.path.with_name('lifecycle-background-originals.json'),run,binding)
            else:
                from adapters.pico4.lifecycle_background_raw import LifecycleBackgroundRaw3
                from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
                need(type(raw_layout) in (LifecycleBackgroundRaw3,LifecycleSourceRaw4) and raw_layout.run==run
                    and raw_layout.binding==self.binding and raw_layout.lock is self.lock
                    and raw_layout.path==self.store.path.with_name('lifecycle-background-raw.json')
                    and type(raw_layout.version) is int and raw_layout.version==(3 if type(raw_layout) is LifecycleBackgroundRaw3 else 4))
                if type(raw_layout) is LifecycleSourceRaw4:need(self.disk is None)
                self.originals=raw_layout;self.version=raw_layout.version
                if state_layout is not None:
                    need(type(raw_layout) is LifecycleSourceRaw4 and self.disk is None
                        and raw_layout.archive.state['reads']==0)
                    self.version=5
                    from adapters.pico4.lifecycle_background_state5 import LifecycleBackgroundState5
                    helper=LifecycleBackgroundState5.__new__(LifecycleBackgroundState5)
                    self.state5=self._state5=helper
                    raw_layout.bind_background_state5(self,helper)
                    try:LifecycleBackgroundState5.__init__(helper,self,raw_layout)
                    except BaseException:
                        raw_layout.failed=True
                        from adapters.pico4.lifecycle_background_raw_state import close_or_retain
                        close_or_retain(path.parent,helper,raw_layout);raise
            need(state_layout is None or self.version==5)
            need(self.disk is not None or self.originals.disk is None);self.load()

    def bound(self):
        # Host-only: this also runs during normal background and immediately
        # before native/OS input, including inside the source intent callback.
        self.lock.assert_held();now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and self.store.read()==self.disk);self.last_clock=now
        self.originals.verify()
        need((self.disk is not None and self.disk['originalChunks']==self.originals.manifest)
            or (self.disk is None and self.originals.disk is None))
        if self.state is not None:
            for name,digest in self.state['archives'].items():
                disk=PrivateFeatureState(self.store.path.with_name(name)).read()
                need(disk is not None and hashlib.sha256(canonical(disk)).hexdigest()==digest)
        return now

    def packet(self,row):
        if self.version==5 and not self._plain5:return helper_method(self.state5,'call')(row,'packet')
        return self._packet_plain(row)

    def _packet_plain(self,row):
        exact(row,{'sourceIndex','world','native','hostMonotonic'});need(integer(row['sourceIndex'],0,len(self.state['sources'])-1)
            and number(row['hostMonotonic'],0,1e15))
        world=row['world'];exact(world,{'ui','gesture','drive','hostMonotonic'});need(number(world['hostMonotonic'],0,1e15))
        packets={name:proof.original(world[name],validator,self.pid,self.run) for name,validator in
            (('ui',ui.validate),('gesture',gesture.validate),('drive',drive.validate))}
        proof.feature_original(row['native'],self.pid);return packets

    def bind_phase_fence(self,fence):
        from adapters.pico4.lifecycle_operations import phase
        need(getattr(self,'phase_fence',None) is None)
        self.phase_fence=fence;phase(self)
        if self.version in (3,4,5):self.originals.bind_phase(fence)

    def close_storage_host(self):
        # Host descriptor retirement alone never performs product cleanup or
        # claims native release. Failed/foreign OFDs remain unresolved.
        need(self.version in (3,4,5))
        from adapters.pico4.lifecycle_background_raw_state import close_or_retain
        namespace=getattr(self,'raw_namespace',None)
        return close_or_retain(self.store.path.parent,self.originals,namespace)

    def evidence(self,row):
        need(self.version!=5 or self._plain5)
        return dict(beforeUi=self.state['beforeUi'],beforeNative=self.state['beforeNative'],arm=self.state['inputs'][0],
            home=self.state['sources'][self.state['home']],background=self.state['background'],foreground=self.state['foreground'],
            returned=self.state['sources'][row['sourceIndex']],afterUi=row['world']['ui'],afterNative=row['native'])

    def validate(self,state):
        if self.version==5 and not self._plain5:return helper_method(self.state5,'call')(state,'validate')
        return self._validate_plain(state)

    def _validate_plain(self,state):
        exact(state,{'phase','archives','beforeUi','beforeNative','sources','inputs','home','background','foreground','quiet','finalQuiet','final'})
        need(state['phase'] in PHASES and set(state['archives'])==set(ARCHIVES)
            and all(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value) for value in state['archives'].values())
            and type(state['sources']) is list and 1<=len(state['sources'])<=64
            and type(state['inputs']) is list and len(state['inputs'])<=2
            and type(state['quiet']) is list and len(state['quiet'])<=25
            and type(state['finalQuiet']) is list and len(state['finalQuiet'])<=25)
        before=proof.original(state['beforeUi'],ui.validate,self.pid,self.run);proof.chat_current(before,self.run,quiet=False)
        proof.feature_original(state['beforeNative'],self.pid);previous=None
        for row in state['sources']:
            packet=proof.source_original(row,self.pid,self.run);source.accept(previous,packet);previous=packet
        need(proof.source_original(state['sources'][0],self.pid,self.run)['ownerRunId']=='')
        for index,request in enumerate(state['inputs']):
            source.command(request);need(request['runId']==self.run and request['operation']==('arm' if index==0 else 'release')
                and request['ownerInstance']==previous['instance'] and request['intentSequence']==index+1)
        rank=PHASES.index(state['phase'])
        if rank>=2:
            need(state['inputs'] and previous['armCommandId']==state['inputs'][0]['commandId'] and previous['ownerRunId']==self.run)
        if state['home'] is not None:
            need(integer(state['home'],1,len(state['sources'])-1))
            home=proof.source_original(state['sources'][state['home']],self.pid,self.run)
            need(home['active'] and home['available'] and not home['released'])
        need(rank<3 or state['home'] is not None)
        if state['background'] is not None:proof.status(state['background'],self.binding,False)
        if state['foreground'] is not None:proof.status(state['foreground'],self.binding,True)
        need(rank<4 or state['background'] is not None);need(rank<6 or state['foreground'] is not None and state['quiet'])
        old=self.state;self.state=state
        try:
            anchor=None;window=None;previous_host=None;prior_gesture=None;prior_native=None
            for row in state['quiet']:
                packets=self.packet(row);proof.validate_return(self.evidence(row),self.run,self.binding)
                observed=proof.source_original(state['sources'][row['sourceIndex']],self.pid,self.run)
                after_home=observed['frames'][len(proof.source_original(state['sources'][state['home']],self.pid,self.run)['frames']):]
                hidden=[item for item in after_home if item['applicationState'] in ('hidden','suspended')]
                need(hidden and any(item['cause']=='timer' and item['capturedEpochMs']-hidden[0]['capturedEpochMs']>=250
                    and item['elapsedMs']-hidden[0]['elapsedMs']>=250 for item in hidden))
                first=after_home.index(hidden[0]);returned=next(index for index,item in enumerate(after_home) if index>first and item['applicationState']=='active')
                for a,b in zip(after_home[first:returned],after_home[first+1:returned+1]):
                    need(0<=b['capturedEpochMs']-a['capturedEpochMs']<=500 and 0<=b['elapsedMs']-a['elapsedMs']<=500)
                if anchor is None:anchor=drive.AvatarDisplacement(packets['drive']);window=drive.AvatarReleaseWindow(anchor)
                need(previous_host is None or row['hostMonotonic']>=previous_host);previous_host=row['hostMonotonic']
                if prior_gesture is not None:need(packets['gesture']['source']['events']==prior_gesture['source']['events'])
                prior_gesture=gesture.accept(prior_gesture,packets['gesture'])
                sample=proof.feature_original(row['native'],self.pid)
                if prior_native is not None:need(sample['instance']==prior_native['instance'] and sample['sequence']>prior_native['sequence']
                    and sample['lifecycle']==prior_native['lifecycle'])
                prior_native=sample
                neutral(packets['gesture']);need(not anchor.measure(packets['drive'])['heldInputs'])
                complete=window.observe(packets['drive'],row['hostMonotonic'])
            need(rank<7 or complete)
            final_window=None;final_complete=False
            for row in state['finalQuiet']:
                packets=self.packet(row);last=proof.source_original(state['sources'][row['sourceIndex']],self.pid,self.run)
                need(len(state['inputs'])==2 and last['released'] and not last['active'] and not last['timerActive'] and last['available']
                    and last['releaseCommandId']==state['inputs'][1]['commandId'] and last['lastIntentSequence']==state['inputs'][1]['intentSequence'])
                current=proof.chat_current(packets['ui'],self.run,quiet=True);proof.same_editor(ui.current_editor(before),current)
                final=last['frames'][-1];need(packets['ui']['sequence']>final['uiSequence']
                    and packets['ui']['source']['keyboard']['sequence']>final['keyboard']['sequence'])
                sample=proof.feature_original(row['native'],self.pid);proof.advanced(proof.feature_original(state['beforeNative'],self.pid),sample)
                need(sample['instance']==prior_native['instance'] and sample['sequence']>prior_native['sequence'] and sample['lifecycle']==prior_native['lifecycle']);prior_native=sample
                need(packets['gesture']['source']['events']==prior_gesture['source']['events'])
                prior_gesture=gesture.accept(prior_gesture,packets['gesture']);neutral(packets['gesture']);need(not anchor.measure(packets['drive'])['heldInputs'])
                if final_window is None:final_window=drive.AvatarReleaseWindow(anchor)
                final_complete=final_window.observe(packets['drive'],row['hostMonotonic'])
            need(state['final']==(state['finalQuiet'][-1] if state['finalQuiet'] else None))
            need(rank<9 or final_complete)
        finally:self.state=old

    def load(self):
        if self.version in (3,4,5):self.originals.preflight_batch()
        self.bound();disk=self.store.read()
        if disk is None:need(self.state is None);return
        exact(disk,{'lifecycleBackgroundOwnerVersion','runId','binding','originalChunks','payload'})
        need(type(disk['lifecycleBackgroundOwnerVersion']) is int and disk['lifecycleBackgroundOwnerVersion']==self.version
            and disk['runId']==self.run and disk['binding']==self.binding and disk['originalChunks']==self.originals.manifest)
        rows=(unpack(disk['payload']) if self.version==5 else self.originals.decode(unpack(disk['payload'])));need(len(rows)==1);self.validate(rows[0]);self.disk,self.state=deepcopy(disk),deepcopy(rows[0]);self.bound()

    def save(self,state):
        if self.version==5:return helper_method(self.state5,'save')(state)
        return self._save_plain(state)

    def _save_plain(self,state):
        if self.version in (3,4,5):self.originals.preflight_batch()
        self.bound();self.validate(state)
        if self.version in (4,5):
            self.originals.save_background(self,state);self.bound();return
        encoded=self.originals.encode([state])
        disk=dict(lifecycleBackgroundOwnerVersion=self.version,runId=self.run,binding=deepcopy(self.binding),originalChunks=self.originals.manifest,payload=pack(encoded))
        self.store.write(disk,self.disk);need(self.store.read()==disk)
        if self.version in (3,4,5):self.originals.namespace.owner_cas(self.store,disk)
        self.disk,self.state=deepcopy(disk),deepcopy(state);self.bound()

    def status(self):
        self.bound();value=self.os_status(deepcopy(self.binding));need(type(value.get('foreground')) is bool)
        proof.status(value,self.binding,value['foreground']);self.bound();return deepcopy(value)

    def wait_status(self,foreground):
        start=self.bound()
        for attempt in range(51):
            packet=self.status()
            if packet['foreground'] is foreground:return packet
            need(self.bound()-start<5 and attempt<50);self.sleep(.1)
        need(False)

    def live(self):
        need(self.status()['foreground'])
        if self.runtime is None:
            world,observer,native=self.runtime_factory(self.intent)
            need(isinstance(world,PicoLifecycleWorld) and isinstance(observer,source.NativeLifecycleBackground)
                and isinstance(native,NativeFeatureObservation) and world.run==self.run and world.binding==self.binding
                and world.lock is self.lock and observer.source_lock is self.lock and observer.pid==native.pid==self.pid)
            if self.version in (3,4,5):
                self.originals.bind_world(world)
                for reader,role in ((world.source,'ui'),(world.axes,'gesture'),(world.avatar,'drive'),
                        (observer,'background'),(native,'feature')):
                    self.originals.hook(reader,role)
            observer.intent=self.intent
            fence=getattr(self,'phase_fence',None)
            if fence is not None:
                need(getattr(observer,'phase_fence',None) is None or observer.phase_fence is fence)
                observer.phase_fence=fence
            if self.state is not None:
                need(self.version!=5) # No new runtime/cold reader adopts a layout5 state.
                observer.restore(self.state['sources'][-1]['raw'])
                baseline=proof.feature_original((self.state['quiet'][-1]['native'] if self.state['quiet'] else self.state['beforeNative']),self.pid)
                native.instance,native.sequence,native.lifecycle=baseline['instance'],baseline['sequence'],deepcopy(baseline['lifecycle'])
            self.runtime=world,observer,native
        return self.runtime

    def intent(self,request):
        self.bound();need(self.state is not None and self.state['phase']==('arm-issued' if request['operation']=='arm' else 'release-issued'))
        from adapters.pico4.lifecycle_operations import phase
        if phase(self) is not None:phase(self).mark()
        state=deepcopy(self.state);state['inputs'].append(deepcopy(request));self.save(state)

    def remember(self,observer):
        state=deepcopy(self.state);state['sources'].append(frame(observer.last_raw));self.save(state)

    def fresh(self):
        world,_observer,native=self.runtime;self.bound();need(native.guard() is not False);epoch=native.clock_ms();now=self.monotonic()
        start,requested,stamp=self.fresh_anchor
        need(integer(epoch,1) and number(now,0,1e15) and now>=self.last_clock and -250<=epoch-stamp
            and max(epoch-stamp,requested-stamp+(now-start)*1000)<=1500);self.last_clock=now

    def capture(self):
        world,observer,native=self.live();start=self.bound();requested=native.clock_ms()
        if self.version in (3,4,5):self.originals.begin_outer(start,requested)
        try:
            observer.read(self.run);self.remember(observer)
            packets=world.current();need(len(world.state['attempts'])==1 and world.state['attempts'][0]['phase']=='quiet'
                and len(world.attempts(world.state,packets['gesture']))==1)
            neutral(packets['gesture']);actual=world.anchor.measure(packets['drive']);need(not actual['heldInputs'] and actual['worldDisplacement']<=.025)
            if self.version==5:value,original=helper_method(self.state5,'read_feature_original')(native)
            else:value=native.read(native.sequence);original=native.original()
            raw=frame(original);need(proof.bytes_packet(raw)==value)
            row=dict(sourceIndex=len(self.state['sources'])-1,world=deepcopy(world.state['frames'][-1]),native=raw,hostMonotonic=self.bound())
            stamps=[observer.last['capturedEpochMs'],value['capturedEpochMs'],*(packet['capturedEpochMs'] for packet in packets.values()),packets['gesture']['source']['frameEpochMs']]
            self.fresh_anchor=start,requested,min(stamps);self.fresh();return row
        finally:
            if self.version in (3,4,5):self.originals.end_outer(start,requested)

    def prepare(self,chat):
        with self.lock.held():
            self.load();need(self.state is None and isinstance(chat,PicoLifecycleChatDraft) and chat.run==self.run
                and chat.binding==self.binding and chat.lock is self.lock and chat.state['phase']=='typed')
            if self.version in (3,4,5):self.originals.install_writer(chat,'chat')
            chat.observe()
            if self.version in (3,4,5):self.originals.preflight_batch()
            world,observer,native=self.live();need(world is chat.joined.world)
            start=self.bound();requested=native.clock_ms()
            if self.version in (3,4,5):self.originals.begin_outer(start,requested)
            try:
                packets=world.current();before=proof.chat_current(packets['ui'],self.run,quiet=False)
                need(before['id']==chat.state['originalId'] and before['focused'] and len(world.state['attempts'])==1
                    and world.state['attempts'][0]['phase']=='quiet' and len(world.attempts(world.state,packets['gesture']))==1)
                neutral(packets['gesture']);actual=world.anchor.measure(packets['drive']);need(not actual['heldInputs'] and actual['worldDisplacement']<=.025)
                if self.version==5:value,original=helper_method(self.state5,'read_feature_original')(native)
                else:value=native.read(native.sequence);original=native.original()
                raw=frame(original);need(proof.bytes_packet(raw)==value)
                observer.read(self.run);need(observer.last['available'] and observer.last['ownerRunId']=='' and observer.last['lastIntentSequence']==0)
                archives={}
                for name in ARCHIVES:
                    disk=PrivateFeatureState(self.store.path.with_name(name)).read();need(disk is not None);archives[name]=hashlib.sha256(canonical(disk)).hexdigest()
                self.save(dict(phase='prepared',archives=archives,beforeUi=deepcopy(world.state['frames'][-1]['ui']),beforeNative=raw,
                    sources=[frame(observer.last_raw)],inputs=[],home=None,background=None,foreground=None,quiet=[],finalQuiet=[],final=None))
                self.fresh_anchor=start,requested,min(observer.last['capturedEpochMs'],value['capturedEpochMs'],*(packet['capturedEpochMs'] for packet in packets.values()))
                self.fresh()
            finally:
                if self.version in (3,4,5):self.originals.end_outer(start,requested)

    def phase(self,value):
        state=deepcopy(self.state);state['phase']=value;self.save(state)

    def poll_delay(self,capture_start):
        if self.version not in (4,5):
            self.sleep(.25);return
        # This is only polling cadence. The SAME already captured original
        # source/quiet/deadline clocks remain authoritative, with all actual
        # archival/CAS work included before deciding any remaining delay.
        now=self.monotonic()
        need(number(capture_start,0,1e15) and number(now,capture_start,1e15)
            and (self.last_clock is None or now>=self.last_clock) and self.fresh_anchor[0]==capture_start)
        remaining=.25-(now-capture_start)
        if remaining>0:self.sleep(remaining)

    def run_owned(self):
        try:
            with self.lock.held():
                self.load();need(self.state is not None);returned_seed=None
                quiet_invocation=helper_method(self.state5,'begin_quiet_invocation')() if self.version==5 else None
                if self.state['phase']=='prepared':
                    _world,observer,_native=self.live();self.phase('arm-issued');observer.arm(self.run);self.remember(observer)
                if self.state['phase']=='arm-issued':
                    _world,observer,_native=self.live();observer.read(self.run);self.remember(observer)
                    need(len(self.state['inputs'])==1 and observer.last['armCommandId']==self.state['inputs'][0]['commandId']
                        and observer.last['lastIntentSequence']==self.state['inputs'][0]['intentSequence'] and observer.last['available'] and observer.last['active'])
                    self.phase('armed')
                if self.state['phase']=='armed':
                    need(self.status()['foreground']);_world,observer,native=self.live();started=self.bound();requested=native.clock_ms()
                    observer.read(self.run);self.remember(observer)
                    last=observer.last;before=self.before_ui();original=ui.current_editor(before)
                    need(last['available'] and last['active'] and last['originalId']==original['id'])
                    current=last['frames'][-1];proof.same_editor(original,current['editor'])
                    need(current['applicationState']=='active' and current['editor']['current'] and current['editor']['text']==original['text'])
                    from adapters.pico4.lifecycle_operations import phase
                    if phase(self) is not None:phase(self).mark()
                    state=deepcopy(self.state);state.update(phase='home-issued',home=len(state['sources'])-1);self.save(state)
                    self.fresh_anchor=started,requested,min(last['capturedEpochMs'],current['uiCapturedEpochMs']);self.fresh()
                    if phase(self) is not None:phase(self).check()
                    self.os_input('lifecycle.background',deepcopy(self.binding));self.bound()
                if self.state['phase']=='home-issued':
                    background=self.wait_status(False);proof.status(background,self.binding,False)
                    state=deepcopy(self.state);state.update(phase='background-observed',background=background);self.save(state)
                if self.state['phase']=='background-observed':
                    proof.status(self.status(),self.binding,False)
                    # Give the original autonomous 250 ms native timer an
                    # actual background checkpoint. Its eventual original
                    # frame, rather than this sleep, must prove absence.
                    self.sleep(.35);proof.status(self.status(),self.binding,False)
                    from adapters.pico4.lifecycle_operations import phase
                    if phase(self) is not None:phase(self).mark()
                    self.phase('resume-issued')
                    if phase(self) is not None:phase(self).check()
                    self.os_input('app.launch',deepcopy(self.binding));self.bound()
                if self.state['phase']=='resume-issued':
                    foreground=self.wait_status(True);proof.status(foreground,self.binding,True)
                    state=deepcopy(self.state);state['foreground']=foreground;self.save(state)
                    row=self.capture();state=deepcopy(self.state);state.update(phase='returned',quiet=[row]);self.save(state);self.fresh()
                    if self.version==5:returned_seed=(row,self.fresh_anchor)
                if self.state['phase']=='returned':
                    # A fresh quiet window is required on recovery; historic
                    # host monotonic values cannot bridge a new acquisition.
                    rows=[];window=None
                    for index in range(25):
                        if returned_seed is None:row=self.capture()
                        else:
                            # Only this invocation's actual returned capture;
                            # recovery begins with no seed or historic window.
                            row,anchor=returned_seed;returned_seed=None
                            need(self.version==5 and self.fresh_anchor is anchor)
                        capture_start=self.fresh_anchor[0] if self.version in (4,5) else None
                        if self.version==5:complete,window=helper_method(self.state5,'quiet_step')(row,window,quiet_invocation,'quiet')
                        else:
                            packets=self.packet(row)
                            if window is None:window=drive.AvatarReleaseWindow(drive.AvatarDisplacement(packets['drive']))
                            complete=window.observe(packets['drive'],row['hostMonotonic'])
                        rows.append(row)
                        state=deepcopy(self.state);state.update(phase='quiet' if complete else 'returned',quiet=deepcopy(rows));self.save(state);self.fresh()
                        if complete:break
                        need(index<24);self.poll_delay(capture_start)
                if self.state['phase']=='quiet':
                    _world,observer,_native=self.live();self.phase('release-issued')
                    observer.release_owned(self.run,self.state['inputs'][0]);self.remember(observer)
                if self.state['phase'] in ('release-issued','released'):
                    self.phase('release-issued');rows=[];window=None
                    for index in range(25):
                        row=self.capture();capture_start=self.fresh_anchor[0] if self.version in (4,5) else None
                        if self.version==5:complete,window=helper_method(self.state5,'quiet_step')(row,window,quiet_invocation,'finalQuiet')
                        else:
                            packets=self.packet(row)
                            if window is None:window=drive.AvatarReleaseWindow(drive.AvatarDisplacement(packets['drive']))
                            complete=window.observe(packets['drive'],row['hostMonotonic'])
                        rows.append(row)
                        state=deepcopy(self.state);state.update(phase='released' if complete else 'release-issued',finalQuiet=deepcopy(rows),final=row)
                        self.save(state);self.fresh()
                        if complete:break
                        need(index<24);self.poll_delay(capture_start)
                need(self.state['phase']=='released')
                result=self.report()
                self.fresh();return result
        except Exception:raise NativeUIError('Lifecycle background unresolved; original intents/history retained, none repeated') from None

    def before_ui(self):
        if self.version==5 and not self._plain5:return helper_method(self.state5,'call')(self.state['beforeUi'],'ui')
        return self._before_ui_plain(self.state['beforeUi'])

    def _before_ui_plain(self,value):
        return proof.original(value,ui.validate,self.pid,self.run)

    def report(self):
        if self.version==5 and not self._plain5:return helper_method(self.state5,'call')(self.state,'report')
        return self._report_plain()

    def _report_plain(self):
        result=proof.validate_return(self.evidence(self.state['quiet'][-1]),self.run,self.binding)
        first,last=self.state['finalQuiet'][0],self.state['finalQuiet'][-1]
        a,b=self.packet(first)['drive'],self.packet(last)['drive']
        actual=proof.source_original(self.state['sources'][self.state['final']['sourceIndex']],self.pid,self.run)
        result.update(observerTimerActive=actual['timerActive'],quietSeconds=min(last['hostMonotonic']-first['hostMonotonic'],
            (b['capturedEpochMs']-a['capturedEpochMs'])/1000),journalRetained=True,processOwnedSourcesRetained=True)
        return result
