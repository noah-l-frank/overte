"""Normal Chat model with separately acquired original Script-root/code data."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from adapters.native_script_roots import NativeScriptRoots
from ios.adapters.chat_script_sources import IOSChatScriptSources
from ios.self_tests.chat_script_source_fixture import packet,URL
from ios.self_tests.test_ios_chat_message_owner import MessageModel
from ios.self_tests.chat_message_script_domain import ScriptMessageModel


class SourceObservationModel:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.code_value=packet(self.native_epoch());self.code_sequence=self.roots_sequence=0
        self.code_queries=[];self.root_queries=[];self.code_raw=self.roots_raw='';self.root_url=URL
        self.wrong_code=False;self.lose_code_return=False;self.replaced_manager=False
    def send_roots(self,query):
        self.query(query);self.root_queries.append(deepcopy(query));self.tick();self.roots_sequence+=1
        self.roots_raw=json.dumps(dict(scriptRootsVersion=1,commandId=query['commandId'],instance='8'*32,sequence=self.roots_sequence,
            processId=42,requestedEpochMs=self.native_epoch(),capturedEpochMs=self.native_epoch(),source=dict(defaultScriptsUrl=self.root_url)))
    def send_code(self,query):
        self.query(query);self.code_queries.append(deepcopy(query));self.tick();self.code_sequence+=1;value=deepcopy(self.code_value)
        value.update(requestId=query['commandId'],runId=query['runId'],sequence=self.code_sequence,
            clockBefore=dict(epochMs=self.native_epoch(),monotonicMs=self.widgets.elapsed))
        if self.wrong_code:
            row=value['source']['workers'][0];row['code']['sha256']=row['codeSources']['evaluations'][0]['sha256']='0'*64
        if self.replaced_manager:
            old=value['source']['workers'][0];old.update(running=False,finished=True,done=True)
            newer=deepcopy(old);newer.update(running=True,finished=False,done=False)
            newer['membership'].update(instance='c'*32,assignedEpochMs=self.native_epoch()-2)
            newer['code']['submittedEpochMs']=self.native_epoch()-1
            newer['codeSources']['evaluations'][0]['submittedEpochMs']=self.native_epoch()
            value['source'].update(revision=2,workers=[old,newer])
        self.tick();value['clockAfter']=dict(epochMs=self.native_epoch(),monotonicMs=self.widgets.elapsed);self.code_raw=json.dumps(value)
        if self.lose_code_return:raise OSError('Declared lost passive code-query return')
    def code_readers(self):
        shared=dict(monotonic=lambda:self.widgets.clock,sleep=self.sleep)
        roots=NativeScriptRoots(self.send_roots,lambda:self.roots_raw,self.native_epoch,self.guard,42,ios=True,**shared)
        code=IOSChatScriptSources(self.send_code,lambda:self.code_raw,self.native_epoch,self.guard,42,**shared)
        return roots,code


class SourceBoundMessageModel(SourceObservationModel,MessageModel):pass
class SourceBoundScriptMessageModel(SourceObservationModel,ScriptMessageModel):pass
