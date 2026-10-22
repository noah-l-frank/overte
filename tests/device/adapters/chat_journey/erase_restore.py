"""Normal Erase/reconstruction and actual original profile restoration.

Pre-Erase append-only transcripts stay intact. Separate independently querying
post-Erase roles preserve the actual discontinuity without resetting a source
cursor or granting a generic authority to discard earlier history.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time
import uuid
from adapters.chat_journey.samples import ChatSamples
from adapters.independent_chat_receiver import source_identity
from adapters.native_chat_profile import OwnedChatProfile
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import TokenChatUI,authorize_erase

VERSION=1


def references(roles):
    return [dict(index=len(role.frames)-1,ticket=role.frames[-1]['ticket'],
        queries=[role.frames[-1][key].get('commandId',role.frames[-1][key].get('requestId'))
            for key in ('primary','peer','view','lifecycle')],
        epochs=[role.frames[-1][key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')]) for role in roles]


class ChatEraseRestore:
    def __init__(self,profile,before,after,controls,store,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(profile,OwnedChatProfile) and type(before) is tuple and type(after) is tuple and len(before)==len(after)==2
            and callable(controls) and callable(monotonic) and callable(sleep) and store.read() is None)
        roles=before+after
        need(all(isinstance(role,ChatSamples) and role.run==profile.run and role.binding==profile.binding for role in roles)
            and all(pair[0].role=='primary' and pair[1].role=='actor' for pair in (before,after))
            and all(role.peer_binding==roles[0].peer_binding and role.vr==roles[0].vr for role in roles)
            and len({role.store.path for role in roles}|{store.path,profile.store.path})==6
            and all(not role.frames for role in after))
        self.profile,self.before,self.after,self.store=profile,before,after,store
        self.monotonic,self.sleep=monotonic,sleep;self.previous=None;self.last_clock=None
        self.ui=controls(self.intent);need(isinstance(self.ui,TokenChatUI) and self.ui.run==profile.run)
        self.reference=None;self.starts=None;self.needs_close=True;self.close_pending=False

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def write(self,phase,**changes):
        need(self.store.read()==self.previous)
        value={**self.previous,**changes,'phase':phase};self.store.write(value,self.previous)
        need(self.store.read()==value);self.previous=deepcopy(value)

    def intent(self,value):
        exact(value,{'controlId','action','instance','generation','sequence'})
        need(self.previous is not None and value['action']=='activate' and len(self.previous['inputs'])<16)
        phase=self.previous['phase'];control=value['controlId']
        need((phase=='preparing' and control=='chat.settings') or (phase=='authorized' and control=='chat.erase')
            or (phase in ('closing','final-closing','recovery-closing') and control=='chat.close')
            or (phase=='opening' and control in ('tablet.home','chat.entry')))
        self.write('erasing' if control=='chat.erase' else phase,inputs=self.previous['inputs']+[deepcopy(value)])

    def pair(self,roles,after_epoch,*,settings=False):
        started=self.now();observed=[(role.read_settings if settings else role.read)(uuid.uuid4().hex,after_epoch) for role in roles]
        if settings:
            need(all(value.get('settings') is True and 'state' not in value for value in observed))
            need(all(roles[0].frames[-1]['view']['source'][key]==roles[1].frames[-1]['view']['source'][key] for key in ('ui','storage','editorFocused','editorHasDraft','tabletShown')))
        else:need(observed[0]['state']==observed[1]['state'])
        clocks=[]
        for role in roles:
            frame=role.frames[-1]
            for reader in (role.primary,role.peer,role.view,role.lifecycle):need(reader.guard() is not False)
            for reader,oldest in ((role.primary,min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))),
                                  (role.peer,frame['peer']['capturedEpochMs'])):
                measured=self.now();epoch=reader.clock_ms();fresh(oldest,epoch);clocks.append((measured,epoch,oldest))
        finished=self.now();need(number(finished,started,started+1.5))
        need(all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))
        return observed

    def stable_sources(self,roles,initial):
        for role,old in zip(roles,initial):
            frame=role.frames[-1]
            for key in ('primary','peer'):
                need(frame[key]['source']['mixerPresent'])
                need(frame[key]['instance']==old[key]['instance'] and frame[key]['sequence']>old[key]['sequence']
                    and source_identity(frame[key])==source_identity(old[key]) and frame[key]['source']==old[key]['source'])
            need(frame['view']['instance']==old['view']['instance'] and frame['view']['sequence']>old['view']['sequence']
                and frame['view']['source']['storage']['configSha256']==self.config
                and frame['lifecycle']['instance']==old['lifecycle']['instance']
                and frame['lifecycle']['lifecycle']==old['lifecycle']['lifecycle'])

    @staticmethod
    def empty(observed,roles,*,opened,channel='none'):
        for value,role in zip(observed,roles):
            state=value['state'];need(state['open']==opened and state['channel']==channel and not state['draft']
                and not state['focused'] and not state['keyboard'] and not state['messages']
                and not state['localMessages'] and not state['domainMessages'] and state['mixerConnected'])
            storage=role.frames[-1]['view']['source']['storage'];need(storage['count']==storage['unowned']==0 and not storage['events'])

    def authorize(self,reference):
        started=self.now()
        self.pair(self.before,self.after_epoch,settings=True)
        for role in self.before:
            view=role.frames[-1]['view'];authorize_erase(self.profile.run,reference,view,self.config,role.primary.clock_ms())
            need(view['source']['storage']['count']>0)
        need(self.before[0].frames[-1]['view']['source']['storage']==self.before[1].frames[-1]['view']['source']['storage'])
        need(self.now()-started<=1.5)
        self.reference=deepcopy(reference);self.starts=[deepcopy(role.frames[-1]) for role in self.before]
        self.write('authorized',control=deepcopy(reference),before=references(self.before));return True

    def close(self,phase):
        self.write(phase);self.close_pending=True;count=len(self.previous['inputs'])
        self.ui.close();need(len(self.previous['inputs'])==count+1 and self.previous['inputs'][-1]['controlId']=='chat.close')
        self.needs_close=False;self.close_pending=False

    def quiet(self,phase):
        self.write(phase);initial=None;epochs=None;previous=None;quiet_started=None
        started=self.now()
        for _attempt in range(202):
            observed=self.pair(self.after,self.after_epoch);self.empty(observed,self.after,opened=False)
            self.stable_sources(self.after,self.starts)
            refs=references(self.after);current=[epoch for ref in refs for epoch in ref['epochs']];now=self.now()
            if initial is None:
                initial=[deepcopy(role.frames[-1]) for role in self.after];epochs=current;quiet_started=now
            else:
                need(all(new>old for new,old in zip(current,previous)))
                for role,old in zip(self.after,initial):need(role.frames[-1]['view']['source']['storage']==old['view']['source']['storage'])
            previous=current
            self.write(phase,samples=self.previous['samples']+[dict(phase=phase,roles=refs)])
            if now-quiet_started>=3 and all(end-begin>=3000 for end,begin in zip(current,epochs)):return
            need(now-started<20);self.sleep(.1)
        need(False)

    def run(self,after_epoch):
        try:
            need(self.previous is None and integer(after_epoch,1) and self.profile.reader.last is not None
                and not self.profile.reader.last['restoreAttempted'])
            self.after_epoch=after_epoch;self.config=self.profile.reader.last['original']['cache']['ArmoredChat-Config']
            self.previous=dict(chatEraseRestoreVersion=VERSION,runId=self.profile.run,binding=self.profile.binding,
                peerBinding=self.before[0].peer_binding,profileJournal=self.profile.store.path.name,
                beforeTranscripts=[role.store.path.name for role in self.before],afterTranscripts=[role.store.path.name for role in self.after],
                phase='preparing',inputs=[],control=None,before=None,erased=None,reopened=None,restored=None,samples=[])
            value=self.previous;self.previous=None;need(self.store.read() is None);self.store.write(value,None);self.previous=deepcopy(value)
            self.ui.erase_history(self.authorize);need(self.ui.erase_issued and self.reference is not None)
            consumed=self.ui.capture()['scope'];scope=self.reference['scope']
            need(consumed['instance']==scope['instance'] and consumed['processId']==scope['processId']
                and consumed['sequence']==scope['sequence']+1)
            self.pair(self.after,after_epoch,settings=True)
            for role in self.after:
                view=role.frames[-1]['view']['source'];storage=view['storage'];ui=view['ui']
                need(storage['count']==storage['unowned']==0 and not storage['events']
                    and ui['localRowCount']==ui['domainRowCount']==0 and not ui['localMessages'] and not ui['domainMessages'])
            self.stable_sources(self.after,self.starts)
            for role in self.after:need(role.frames[-1]['view']['source']['storage']['kind']=='null')
            old_generations=[role.frames[-1]['view']['source']['ui']['generation'] for role in self.after]
            self.write('erased',erased=references(self.after));self.close('closing');self.quiet('closed-quiet')
            self.write('opening');self.needs_close=True;count=len(self.previous['inputs']);self.ui.open()
            need(count<len(self.previous['inputs'])<=count+2 and self.previous['inputs'][-1]['controlId']=='chat.entry')
            observed=self.pair(self.after,after_epoch);self.empty(observed,self.after,opened=True,channel='local')
            self.stable_sources(self.after,self.starts)
            for role,generation in zip(self.after,old_generations):
                need(role.frames[-1]['view']['source']['ui']['generation']!=generation)
            self.write('reconstructed',reopened=references(self.after));self.close('final-closing')
            self.quiet('before-restore-quiet');self.write('restoring')
            restored=self.profile.perform('restore');need(restored['restored'])
            self.write('restored',restored=dict(commandId=restored['commandId'],sequence=restored['sequence']))
            self.quiet('restored-quiet');current=self.profile.perform('inspect')
            need(current['restored'] and current['settings']['mutationSequence']==restored['settings']['mutationSequence']
                and current['settings']['capturedEpochMs']-restored['settings']['capturedEpochMs']>=3000)
            self.write('complete');return deepcopy(self.previous)
        except Exception:
            # Best-effort original release, with no repeated uncertain close or
            # profile restore. Every journal stays, regardless of these effects.
            if self.previous is not None:
                if self.needs_close and not self.close_pending:
                    try:self.close('recovery-closing')
                    except Exception:pass
                if not any(row['request']['operation']=='restore' for row in self.profile.attempts):
                    try:self.write('recovery-restoring');self.profile.perform('restore')
                    except Exception:pass
            raise NativeUIError('Chat Erase/profile flow is unresolved; original journals are retained') from None
