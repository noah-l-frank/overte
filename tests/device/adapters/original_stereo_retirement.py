"""Shared original stereo memory/file retirement; uncertain mutations stay owned."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.graphics_journey.samples import retirement


class OriginalStereoRetirement:
    def retire(self,owned):
        self.now();owner=owned.owner.owned();need(owner['capture']==self.state['captureIntent'])
        # Bind recreated storage to the original native issuer before any read
        # or retirement. A new renderer/source cannot report an old one absent.
        owned.storage.bind(self.state['frame']['capture'])
        resumed=self.state['phase']=='retiring'
        if resumed:
            # Do not repeat an uncertain release/remove mutation. Known original
            # successful headers can finish through a fresh read-only inventory;
            # a lost mutation header retains ownership for failure cleanup.
            need(self.state['memory'] is not None and self.state['owner']==owner
                 and type(self.state['files']) is dict and 'remove' in self.state['files'])
            memory=deepcopy(self.state['memory']);removed=deepcopy(self.state['files']['remove'])
            absent=owned.receipts.cleanup.request('inspect');self.now()
            current=deepcopy(self.state);current['files']['inspect']=absent;self.save(current)
            files=dict(removed=removed,absent=absent)
        else:
            current=deepcopy(self.state);current['phase']='retiring';self.save(current)
            memory=owned.storage.release(owner['capture']['commandId']);self.now()
            current=deepcopy(self.state);current['memory']=memory;current['owner']=owned.owner.owned();self.save(current)
            original=owned.receipts.cleanup.request
            def remember(operation):
                packet=original(operation);self.now();current=deepcopy(self.state)
                current['files']=dict(current['files'] or {});current['files'][operation]=packet;self.save(current);return packet
            owned.receipts.cleanup.request=remember
            files=owned.receipts.retire();self.now();owner=owned.owner.owned()
        proof=dict(memory=memory,files=files,owner=owner)
        retirement(proof,owner,int(self.binding['processIdentity'].split(':',1)[0]),self.binding,self.role)
        current=deepcopy(self.state);current['proof']=proof;self.save(current)
        need(owned.owner.owned()==owner);owned.owner.store.discard(owner);need(owned.owner.store.read() is None);self.now()
        return proof
