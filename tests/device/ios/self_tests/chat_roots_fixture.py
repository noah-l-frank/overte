"""Real host weak references; declared Qt aliases, native clocks and transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from ios.self_tests.world_web_ui_roots_fixture import RootCensus
from ios.self_tests.test_ios_chat_history_cleanup import RestoreModel

SOURCE='qrc:/scripts/communityScripts/armored-chat/armored_chat.qml'


class Operand:
    def __init__(self,kind):self.kind,self.source=kind,SOURCE


class Page(Operand):
    def __init__(self):
        super().__init__('page');self.editor=Operand('editor');self.local=Operand('local-model')
        self.domain=Operand('domain-model');self.list=Operand('list');self.model=self.local
        self.visible=True;self.in_tree=True


class ChatRoots(RootCensus):
    def __init__(self,*,pid=31,epoch=None,monotonic=None):
        super().__init__();self.pid,self.epoch_fn,self.mono_fn=pid,epoch,monotonic
    def tick(self):
        if self.epoch_fn is None:return super().tick()
        self.elapsed=int(self.mono_fn()*1000);return self.epoch_fn()
    def capture(self,pages,*,ready=True):
        members=[]
        for page in pages:
            if not page.in_tree:continue
            members.append(dict(page=self.observe(page),editor=self.observe(page.editor),localModel=self.observe(page.local),
                domainModel=self.observe(page.domain),list=self.observe(page.list),listModel=self.observe(page.model),visible=page.visible))
        self.sequence+=1
        for row,reference in self.rows:
            if reference() is None and row['weakAlive']:
                row.update(weakAlive=False,weakExpiredObservedEpochMs=self.tick(),weakExpiredObservedMonotonicMs=self.elapsed)
        return dict(iosChatRootOwnershipVersion=1,available=True,instance=self.instance,sequence=self.sequence,processId=self.pid,
            capturedEpochMs=self.tick(),monotonicMs=self.elapsed,clockDomain='native-main-ios-chat-roots',complete=self.complete,
            wholeTreeReady=ready,observationSequence=len(self.rows),roots=[deepcopy(row) for row,_reference in self.rows],pages=members)


class RootRestoreModel(RestoreModel):
    def __init__(self):
        super().__init__();self.qt_pages=[];self.roots=ChatRoots(pid=42,epoch=self.native_epoch,monotonic=lambda:self.widgets.clock)
    def chat_input(self,identifier,action,*,reference,value=None):
        old=self.widgets.page_life
        try:return super().chat_input(identifier,action,reference=reference,value=value)
        finally:
            if self.widgets.page_life!=old:
                if self.widgets.panel:self.qt_pages.append(Page())
                else:
                    for page in self.qt_pages:page.visible=False;page.in_tree=False
            for page in self.qt_pages:
                if page.visible:page.model=page.local if self.widgets.channel=='local' else page.domain
    def send_view(self,command):
        super().send_view(command);self.view_value['chatViewVersion']=3
        roots=self.roots.capture(self.qt_pages);self.view_value['source']['rootOwnership']=roots
        if self.view_value['source']['ui']['present']:
            current=[page for page in self.qt_pages if page.visible];assert len(current)==1
            self.view_value['source']['ui']['rootIdentity']=self.roots.observe(current[0])


from ios.self_tests.test_ios_chat_history_value import TypedBoundary


class RootBoundary(TypedBoundary):
    def __init__(self):
        super().__init__();self.roots=ChatRoots(pid=123);self.qt_pages=[Page()]
        self.qt_pages[0].visible=False;self.final_mutate=None
    def send(self,request):
        super().send(request)
        if self.value is not None:
            self.value['chatViewVersion']=3;roots=self.roots.capture(self.qt_pages)
            self.value['capturedEpochMs']=roots['capturedEpochMs'];self.value['source']['rootOwnership']=roots
            if self.value['source']['ui']['present']:
                self.value['source']['ui']['rootIdentity']=self.roots.observe(self.qt_pages[0])
            if self.final_mutate:self.final_mutate(self.value)
