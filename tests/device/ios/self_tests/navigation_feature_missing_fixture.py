"""Actual missing HTTP and normal OK/Cancel, modeled native Qt producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import normal_input
from ios.adapters.navigation_address_inputs import NavigationAddressInputs
from ios.adapters.navigation_address_dismiss import NavigationAddressDismiss
from ios.adapters.navigation_missing_actions import NavigationMissingActions
from feature_journeys.fixtures import context


class MissingWidget:
    def __init__(self,h,test):
        self.h=h;self.ignore=False;self.ignore_ok=False;self.partial_destroy=False;self.pending_response=None
        f=h.flow_fixture;b=f.b;original=b.call;observed=b.observed;post=normal_input.urlopen
        h.dialogs.run=h.run
        def w3c(method,path,body=None):
            name=b.by_reference.get(path.split('/element/',1)[-1].split('/')[0])
            if method=='POST' and path.endswith('/click') and name=='PhoneAddressGoButton' and b.field.startswith('hifi://'):
                old=b.mutation;b.mutation='goto-ignored'
                try:value=original(method,path,body)
                finally:b.mutation=old
                if not self.ignore:
                    status,_raw,response=h.harness.get('/api/v1/places/'+context(h.run)['hidden'])
                    if status!=404:raise AssertionError('Original missing lookup did not return 404')
                    self.pending_response=response
                return value
            return original(method,path,body)
        def ui():
            value=observed()
            if h.dialogs.rows and h.dialogs.rows[0]['dialog'] is not None:
                value['controls'].extend(dict(row,frame=dict(x=1,y=1,width=200,height=40)) for row in h.dialogs.controls()['controls'])
            return value
        def native(request,timeout):
            query=json.loads(request.data);ok=False
            if query['operation']=='edit':
                ok=any(row['id']=='navigation.error.ok' and row['token']==query['input']['fieldToken'] for row in ui()['controls'])
            old_field=b.field;value=post(request,timeout)
            if ok:
                b.field=old_field
                if not self.ignore_ok:
                    h.dialogs.respond();h.dialogs.destroy(listener=not self.partial_destroy)
            return value
        b.call=w3c;b.observed=ui
        send=h.dialogs.send
        def callback(query):
            # The real response is retained first; the native event loop
            # delivers its callback after the ordinary Go dialog closed.
            if self.pending_response is not None:
                h.dialogs.create(self.pending_response,origin=h.harness.origin)
                self.pending_response=None;b.address_open=True
            return send(query)
        h.dialogs.send=callback
        h.sources['dialogs']=h.dialogs.reader()
        boundary=patch.object(normal_input,'urlopen',native);boundary.start();test.addCleanup(boundary.stop)
        # The same physical source readers advance from the immutable static
        # admission. Earlier packets remain unchanged in their original file.
        f.f.admission.native=h.native
        f.f.admission.sources.update(dialogs=h.sources['dialogs'],replies=h.sources['replies'],ui=h.sources['ui'])
        def missing(_selector,admission):
            return NavigationMissingActions(PrivateFeatureState(h.root/'ios-navigation-missing-actions.json'),
                admission,b.ui,h.sources['ui'],epoch_ms=h.now,monotonic=h.mono)
        def address(_selector,admission):
            inputs=NavigationAddressInputs(PrivateFeatureState(h.root/'ios-navigation-address-42-inputs.json'),
                admission.binding,h.run,admission.lock,admission.bound,b.ui,h.sources['ui'],epoch_ms=h.now,monotonic=h.mono)
            return NavigationAddressDismiss(PrivateFeatureState(h.root/'ios-navigation-address-dismiss-42.json'),inputs,
                epoch_ms=h.now,monotonic=h.mono)
        f.runtime._navigation_missing_actions=missing;f.runtime._navigation_address_dismiss=address
