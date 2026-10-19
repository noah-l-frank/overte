"""Durable acquisition/receipt ownership; cleanup never trusts a release ACK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.normal_feature_state import context,need
from adapters.world_render_storage import command as storage_command,receipt_file


class WorldRenderOwner:
    def __init__(self,store,binding,guard,*,component_only=False):
        need(callable(guard))
        self.store,self.guard,self.component_only=store,guard,component_only
        self.binding=deepcopy(context(binding,component_only=component_only))

    @staticmethod
    def acquisition(command):
        need(type(command) is dict and set(command)=={'schemaVersion','commandId','action'}
             and type(command['schemaVersion']) is int and command['schemaVersion']==1
             and command['action']=='feature-world-render-observe' and type(command['commandId']) is str
             and re.fullmatch('(?:ios-)?[0-9a-f]{32}',command['commandId']))
        return command

    def owned(self):
        need(self.guard() is not False)
        value=self.store.read()
        need(type(value) is dict and set(value)=={'ownershipVersion','binding','capture','receipts'}
             and type(value['ownershipVersion']) is int and value['ownershipVersion']==1
             and context(value['binding'],component_only=self.component_only)==self.binding
             and self.acquisition(value['capture']) and type(value['receipts']) is list and len(value['receipts'])<=1024)
        need(all(type(n) is str and re.fullmatch('(?:ios-)?[0-9a-f]{32}',n) for n in value['receipts'])
             and len(set(value['receipts']))==len(value['receipts'])
             and all(n.startswith('ios-')==value['capture']['commandId'].startswith('ios-') for n in value['receipts']))
        return value

    def intent(self,command):
        need(self.guard() is not False and self.store.read() is None)
        self.acquisition(command)
        value=dict(ownershipVersion=1,binding=self.binding,capture=deepcopy(command),receipts=[])
        self.store.write(value,None)

    def receipt_intent(self,command):
        before=self.owned();storage_command(command)
        need(command['requestId']==before['capture']['commandId'] and command['commandId'] not in before['receipts']
             and len(before['receipts'])<1024
             and command['commandId'].startswith('ios-')==command['requestId'].startswith('ios-'))
        value=deepcopy(before);value['receipts'].append(command['commandId'])
        self.store.write(value,before)


class OwnedWorldRenderCapture:
    def __init__(self,capture,storage,owner,receipts):
        need(capture.files is storage and capture.intent==owner.intent and storage.receipt_intent==owner.receipt_intent
             and all(callable(getattr(receipts,n,None)) for n in ('remove','absent')))
        self.capture,self.storage,self.owner,self.receipts=capture,storage,owner,receipts

    def read(self,after_sequence):
        need(self.owner.store.read() is None)
        return self.capture.read(after_sequence)

    def release(self):
        value=self.owner.owned();request=value['capture']['commandId']
        sample=self.storage.release(request) # Retire late requests; independently observe drained buffers.
        value=self.owner.owned() # Includes the newly issued release/inspect receipt intents.
        for nonce in value['receipts']:
            need(self.owner.guard() is not False)
            name=receipt_file(nonce)
            self.receipts.remove(name) # An ACK cannot discard the ownership journal.
            need(self.owner.guard() is not False and self.receipts.absent(name) is True
                 and self.owner.guard() is not False)
        self.owner.store.discard(value)
        return sample # Memory absence only; original metadata is retained as run evidence.
