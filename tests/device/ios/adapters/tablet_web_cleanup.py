"""Ordinary Tablet cleanup inputs with separate durable recovery ownership.

The original action/setup journals are immutable responsibilities. A cleanup
owner never replays their unknown input. Native tails independently prove the
actual result; returned inputs alone cannot retire a resource or authorize Stop.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner

VERSION=1


def unloaded_original(current,metadata,directory,dialog_before):
    """Actual returned-null picker callbacks and complete no-worker originals.

    The dialog is independently born after the original pre-open native ledger;
    QML picker request IDs are unrelated and never used as listener IDs. This
    intentionally refuses an executed but unadmitted
    manager: that requires its own submitted-code/terminal ownership join.
    """
    from ios.adapters import script_dialogs
    from adapters.native_script_terminal import validate as terminal_original,ACTION
    from adapters.native_script_observation import validate as script_original
    from adapters.native_script_files import NativeScriptFiles
    from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles
    from ios.adapters.tablet_web_app_origin import Frozen
    from urllib.parse import urlsplit,unquote
    owned=OwnedTabletWebAppFiles(None,Frozen(metadata),current['row']['source']['observation']['binding']).owned()
    need(type(directory) is str and directory.endswith('/feature-script-'+owned['runId']))
    packets=current['packets'];dialog=packets['dialogs'];pid=int(owned['binding']['processIdentity'])
    script_dialogs.validate(dialog,dict(schemaVersion=1,commandId=dialog['requestId'],action=script_dialogs.ACTION,runId=dialog['runId']),pid)
    actual=script_dialogs.completed(dialog,dialog_before,after_epoch=dialog_before['clockAfter']['epochMs']);identity=actual['dialog']
    rows=[row for row in dialog['source']['events'] if row['dialogInstance']==identity]
    need(len(rows)==4 and {row['kind'] for row in rows}=={'listener-created','response-entered','response-returned','listener-destroyed'})
    entered=next(row for row in rows if row['kind']=='response-entered');returned=next(row for row in rows if row['kind']=='response-returned')
    selected=directory+'/script.js';local=unquote(urlsplit(selected).path)
    need(entered['response']['text'] in ('',selected,local) and returned['manager'] is None)
    scripts=packets['scripts'];script_original(scripts,scripts['requestId'],pid,scripts['capturedEpochMs'])
    source=scripts['source'];need(source.get('membershipSourceVersion')==1 and source['membership']['complete'])
    prefix=directory+'/'
    need(not any(row['url'].startswith(prefix) for row in source['membership']['managers'])
        and not any(row['url'].startswith(prefix) for row in source['engines']))
    terminal=packets['terminal'];terminal_original(terminal,dict(schemaVersion=1,commandId=terminal['commandId'],action=ACTION),pid,terminal['capturedEpochMs'])
    need(not any(row['manager']['url'].startswith(prefix) for row in terminal['source']['events']))
    file=packets['files:'+owned['runId']];NativeScriptFiles.validate_source(file['source'],'observe',owned['runId'])
    need(file['operation']=='observe' and file['runId']==owned['runId'])
    if file['source']['exists']:need(file['source']['directory']==directory)
    return dict(tabletWebUnloadedOriginalVersion=1,storageRun=owned['runId'],dialog=identity,
        dialogSha256=digest(dialog),scriptsSha256=digest(scripts),terminalSha256=digest(terminal),filesSha256=digest(file))


class TabletWebCleanupAppOwner(TabletWebAppOwner):
    """Reuse normal Script UI with an explicit independent cleanup journal.

    Only the same Primary's original input plan is adopted. Neither requested
    outputs nor copied Actor measurements can qualify a Script, file or target.
    Unknown old operations remain untouched in their original parent journal.
    """
    def __init__(self,runtime):
        base=TabletWebAppOwner(runtime);self.base=base
        self.runtime,self.root,self.binding,self.run,self.lock=runtime,base.root,base.binding,base.run,base.lock
        self.base_sha=digest(base.saved);self.store=PrivateFeatureState(self.root/('tabletweb-cleanup-app-owner-'+self.run+'.json'))
        self.saved=self.store.read()
        if self.saved is None:
            self.state=dict(generations=deepcopy(base.state['generations']),operations=[],pending=None);self.save()
        else:
            exact(self.saved,{'tabletWebCleanupAppOwnerVersion','binding','runId','baseSha256','payload'})
            need(type(self.saved['tabletWebCleanupAppOwnerVersion']) is int and self.saved['tabletWebCleanupAppOwnerVersion']==VERSION
                and same(self.saved['binding'],self.binding) and self.saved['runId']==self.run and self.saved['baseSha256']==self.base_sha)
            rows=unpack(self.saved['payload']);need(len(rows)==1);self.state=rows[0]
        self.decode()
    def bound(self):
        self.runtime.check();self.lock.assert_held()
        need(same(self.store.read(),self.saved) and digest(self.base.store.read())==self.base_sha)
    def save(self):
        self.bound();self.decode();value=dict(tabletWebCleanupAppOwnerVersion=VERSION,binding=self.binding,runId=self.run,
            baseSha256=self.base_sha,payload=pack([self.state]))
        self.store.write(value,self.saved);self.saved=deepcopy(value)
    def prepare(self,_ticket):need(False)  # Cleanup cannot stage, load or mint a new app generation.

    def close_page(self):
        """Observe actual native closure or deliver one ordinary owned Close."""
        from ios.adapters import tablet_web_state as state
        from ios.adapters.tablet_web_actions import ordinary_toolbar
        from adapters.normal_ui import NativeUI
        source=self.runtime.observer.source;packets={}
        for name in ('sources','trace','uikit','state'):packets[name]=source.children[name].capture(self.runtime.observer.readers[name])
        state.join(packets['state'],packets['sources'],packets['trace'],packets['uikit'])
        need(packets['state']['iosTabletWebStateVersion']==2 and packets['state']['otherLiveTablets']==0)
        current=[row for row in packets['state']['owners'] if row['alive'] and row['current'] is not None and row['current']['generation']]
        if not current:
            state.closed(packets['state'],packets['sources'],packets['trace'],packets['uikit'],require_observed=False);return
        generations=[row for row in self.state['generations'] if row['admission'] is not None];need(generations)
        generation=generations[-1]
        def send(method,path,body,ownership):
            request=dict(method=method,path=path,body=deepcopy(body),ownership=deepcopy(ownership));self.intent('sdk',request)
            ui=NativeUI(self.runtime.client,self.binding['sessionId'],lambda:self.runtime.process() is not None,
                monotonic=source.monotonic,sleep=self.runtime.transport.sleep)
            result=ui._request(method,path,body);self.returned('sdk',request,result);return result
        self.once(generation,'cleanup-close-native-page',lambda:ordinary_toolbar(self.runtime,'Close',send))

    def stop_apps(self):
        """Only normal per-URL Stop; no Script API/product repair is called."""
        self.bound();self.decode();need(self.state['pending'] is None)
        for generation in self.state['generations']:
            if generation['directory'] is None:
                # No UI load can precede successful stage+directory recording
                # in the original closed setup protocol. Preserve unknown stage
                # ownership for independent NativeFiles readback/retirement.
                labels=[row['label'] for row in self.base.state['operations']+
                    ([self.base.state['pending']] if self.base.state['pending'] else []) if row['generation']==generation['index']]
                need(not any(label.startswith(('open-manager-','open-picker-','load-app-')) for label in labels));continue
            manager=self.manager(generation);index=str(generation['index'])
            self.once(generation,'cleanup-close-dialog-'+index,manager.close_dialog)
            self.once(generation,'cleanup-open-manager-'+index,lambda:self.open_manager(manager))
            self.once(generation,'cleanup-stop-script-'+index,lambda manager=manager,generation=generation:
                self.stop_source(manager,generation))
            self.once(generation,'cleanup-close-manager-'+index,lambda:self.close_manager(manager,'cleanup-open-manager-'+index))

    @staticmethod
    def stop_source(manager,generation):
        manager.require_current()
        if manager.state['source'] is None:
            # A setup interrupted while its picker was open has issued no
            # load for any URL. No Stop is sent for an invented source. The
            # independent dialog/VM/terminal/file join still gates deletion.
            need(manager.state['loadAttempted'] is False);return
        manager.stop_source(generation['directory']+'/script.js')

    def open_manager(self,manager):
        """Enter a genuinely still-open owned Home without adopting its flags.

        App setup opens Home separately after the generic manager owner has
        closed its own tablet. The generic owner correctly refuses to adopt
        that open surface. Our separate input journal owns that exact open;
        current source-owned ordinary Home controls admit the next input.
        No Script/VM/effect is inferred from the old returned input.
        """
        from ios.adapters.tablet_web_owned_home import enter
        return enter(manager,self.base.state['operations'])

    def close_manager(self,manager,label):
        # The independent cleanup operation, not a changed generic ownership
        # flag, owns the ordinary manager entry above. Unknown entry/close
        # delivery remains pending and cannot reach this next operation.
        from ios.adapters.tablet_web_owned_home import leave
        return leave(manager,self.state['operations'],label)

    def release_files(self,before_reference,stop_reference,current_reference):
        """Run only after separately decoded actual VM/Ending/thread drainage.

        The caller owns that source proof. Release ACK is followed by a genuine
        NativeFiles absence read; both receipts remain in the raw query owner.
        """
        self.bound();self.decode();need(self.state['pending'] is None)
        from ios.adapters.tablet_web_tail import TabletWebTail
        from ios.adapters.tablet_web_quiet import scripts_drained
        tail=TabletWebTail(self.runtime,historical=True)
        need(tail.state['pending'] is None and current_reference==tail.state['records'][-1])
        before,stop,current=(tail.read(ref) for ref in (before_reference,stop_reference,current_reference))
        apps=self.runtime.observer.source.app_sources();scripts_drained(before,stop,current,apps)
        source=current['packets']['scripts']['source']
        for generation in self.state['generations']:
            if generation['ownership'] is None:continue
            if generation['admission'] is None:
                issued=self.base.state['operations']+([self.base.state['pending']] if self.base.state['pending'] else [])
                loads=[row for row in issued if row['generation']==generation['index'] and row['label'].startswith('load-app-')]
                if loads:
                    from ios.adapters.tablet_web_native_reads import TabletNativeReads
                    history=TabletNativeReads(self.root,self.binding,self.run,'primary','dialogs',self.lock,lambda:need(False),
                        monotonic=self.runtime.observer.source.monotonic,historical=True)
                    need(generation['dialogBefore'] is not None)
                    unloaded_original(current,generation['ownership'],generation['directory'],history.at(generation['dialogBefore']))
            metadata=deepcopy(generation['ownership'])
            packet=self.runtime.read_auxiliary('files',ownership=metadata)
            if packet['source']['exists']:
                prefix=packet['source']['directory']+'/'
                need(not any(row['url'].startswith(prefix) for row in source['membership']['managers'])
                    and not any(row['url'].startswith(prefix) for row in source['engines']))
                self.once(generation,'cleanup-release-files-'+str(generation['index']),lambda metadata=metadata:
                    self.runtime.read_auxiliary('files',ownership=metadata,operation='release'))
                packet=self.runtime.read_auxiliary('files',ownership=metadata)
            need(packet['operation']=='observe' and packet['source']==dict(exists=False,files=[]))
