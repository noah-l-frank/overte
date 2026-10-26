"""One real Node child/production Chat engine; modeled native/QML boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import select
import subprocess
from ios.self_tests.test_ios_chat_draft_owner import DraftModel


class ScriptMessageModel(DraftModel):
    def __init__(self,case):
        super().__init__();root=Path(__file__).resolve().parents[4]
        self.child=subprocess.Popen(['node',str(Path(__file__).with_suffix('.js')),str(root)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        case.addCleanup(self.close);self.source=None;self.command('read')
    def command(self,action,*,apply=False,**values):
        assert self.child.poll() is None,'Declared original Chat child is unavailable'
        self.child.stdin.write(json.dumps(dict(action=action,epoch=self.native_epoch(),**values))+'\n');self.child.stdin.flush()
        assert select.select([self.child.stdout],[],[],5)[0],'Original Chat child response expired'
        response=json.loads(self.child.stdout.readline());assert response==dict(ok=True,source=response.get('source'))
        self.source=response['source']
        if apply:
            self.widgets.local=list(self.source['local']);self.widgets.domain=list(self.source['domain'])
            rows=self.source['history'];kind='unset' if not self.source['historyPresent'] else 'null' if rows is None else 'array'
            self.storage.update(kind=kind,count=len(rows or []),unowned=0,events=[dict(channel=row['channel'],text=row['message'],timestamp=row['timestamp']) for row in rows or []])
        return self.source
    def query(self,command):
        super().query(command)
        # Query WAL precedes each separate source read. Input return values do
        # not populate native model/Settings observations.
        if command['action'] in ('normal-ui-input','feature-chat-view-observe'):self.command('read',apply=True)
    def chat_input(self,identifier,action,*,reference,value=None):
        sent=len(self.widgets.sent);super().chat_input(identifier,action,reference=reference,value=value)
        if identifier=='chat.entry':self.command('open')
        elif identifier=='chat.close':self.command('close')
        elif action=='replace':self.command('typing',nonempty=bool(value))
        if len(self.widgets.sent)>sent:
            channel,text=self.widgets.sent[-1];self.command('send',channel=channel,text=text)
            self.command('typing',nonempty=False) # QML's actual empty-text branch.
    def close(self):
        try:
            if self.child.poll() is None:
                source=self.command('end');assert source['subscriptions']==0
                self.child.stdin.close();assert self.child.wait(timeout=3)==0,'Original Chat child failed on exit'
        finally:
            if self.child.poll() is None:self.child.kill();self.child.wait(timeout=3)
            for stream in (self.child.stdin,self.child.stdout,self.child.stderr):
                if not stream.closed:stream.close()
