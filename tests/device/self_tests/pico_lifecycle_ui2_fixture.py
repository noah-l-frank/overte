"""Explicit weak-object GUI model for the EXISTING normal Lifecycle owners.

This does not execute Qt. Existing normal inputs still mutate the original
fixture's widget objects; one shared weak registry supplies both consumers.
UI1 background-history requests keep the original row grammar. UI2 is chosen
at each actual source constructor, before its first observation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import patch

from adapters.native_feature_observation import need
from adapters.pico4.lifecycle_source import PicoLifecycleSource
from self_tests.test_pico_lifecycle_source import Boundary
from self_tests.test_pico_lifecycle_field_binding import Object,Field,WeakTripleModel
from self_tests import test_pico_lifecycle_world as world_fixture


@dataclass(eq=False)
class WidgetObjects:
    row:object
    field:object
    context:object
    token:str=''


class SharedWeakUi2(Boundary):
    def __init__(self):
        super().__init__();self.registry=WeakTripleModel();self.window=Object();self.objects=[]

    def widget(self,row):
        # The original fixture keeps actual mutable widget-row objects. Their
        # Python object identity selects a model lifetime; selector/text/opaque
        # DTO IDs never select or create a matching Pending token.
        record=next((item for item in self.objects if item.row is row),None)
        if record is None:
            record=WidgetObjects(row,Field(self.window) if row['fieldAlive'] else None,
                Object() if row['contextAlive'] else None);self.objects.append(record)
        if not row['fieldAlive']:record.field=None
        if not row['contextAlive']:record.context=None
        return record

    def token(self,row):
        record=self.widget(row)
        if record.field is None or record.context is None or not row['windowAlive']:return record.token
        token=self.registry.identity(record.field,self.window,record.context)
        need(token and (not record.token or record.token==token));record.token=token
        return token

    def send(self,request):
        super().send(request)
        if self.value is None or request.get('schemaVersion',1)!=2:return
        self.value['lifecycleUiVersion']=2
        need(len(self.value['source']['editors'])==len(self.rows))
        for row,observed in zip(self.rows,self.value['source']['editors']):
            token=self.token(row);live=all(row[name] for name in ('fieldAlive','windowAlive','contextAlive'))
            observed['fieldBinding']=dict(lifecycleFieldBindingVersion=1,uiFieldId=observed['fieldId'],
                pendingFieldToken=token,weakBirth=token,status='linked' if live else 'retired' if token else 'unobserved')

    def source(self):
        return PicoLifecycleSource(self.send,self.read,lambda:20000,lambda:self.alive,123,
            monotonic=lambda:self.clock,sleep=self.sleep,field_bindings=True)

    def scripts_token(self):
        current=next((row for row in self.rows if row['current'] and row['kind']=='scripts'),None)
        return '' if current is None else self.token(current)


@contextmanager
def normal_ui2_sources():
    # Existing World.Native and Editor.Native use this exact constructor alias.
    # No admitted reader, phase, requested facts or product code is mutated.
    with patch.object(world_fixture,'UiBoundary',SharedWeakUi2):yield
