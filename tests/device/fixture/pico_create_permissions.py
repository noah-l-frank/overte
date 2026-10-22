"""Pico's strict admission on the fixed original Phone Settings controller.

Only the opted-in process-owned fixture calls the original Settings API. No
Interface permission setter, adapter credential or client effect is supplied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import math
from urllib.request import Request
from adapters.native_feature_observation import need,number
from fixture.create_permissions import CreatePermissions,standard,canonical

# Complete original NodePermissions::toVariant rows; unknown fields cannot be
# preserved by that product serializer and therefore cannot be our baseline.
FIELDS={'permissions_id','id_can_connect','id_can_rez_avatar_entities','id_can_adjust_locks',
    'id_can_rez','id_can_rez_tmp','id_can_write_to_asset_server','id_can_connect_past_max_capacity',
    'id_can_kick','id_can_replace_content','id_can_get_and_set_private_user_data','id_can_view_asset_urls'}


def rows(value):
    result=standard(value)
    need(all(set(row)==FIELDS and all(type(v) is bool for k,v in row.items() if k!='permissions_id') for row in result))
    return result


class PicoCreatePermissions(CreatePermissions):
    validate_rows=staticmethod(rows)
    def __init__(self,*args,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000)):
        need(callable(monotonic) and callable(epoch_ms));self.monotonic,self.epoch_ms=monotonic,epoch_ms
        super().__init__(*args)
    def http(self,path,payload=None):
        try:
            if payload is None:return super().http(path)
            # Original normal Settings POST, with a fresh comparison AFTER the
            # durable once-only intent. A delayed CAS cannot overwrite a newly
            # observed foreign standard row. No failed input is ever retried.
            need(path=='/settings.json' and self.state['pending'] is not None
                and payload=={'security':{'standard_permissions':self.state['pending']}})
            actual,outside=self.original()
            need(actual==self.state['last'] and outside==self.state['outsideSha256'])
            request=Request(self.url+path,data=canonical(payload),method='POST',headers={
                'Content-Type':'application/json','Cache-Control':'no-store'})
            self.guard()
            now=self.monotonic();epoch=self.epoch_ms()
            need(number(now,self.original_host,1e15) and number(epoch,self.original_epoch,1e15)
                and max(epoch-self.original_epoch,(now-self.original_host)*1000)<=1500)
            with self.opener.open(request,timeout=2) as response:
                need(response.status==200 and response.geturl()==self.url+path)
                result=response.read(1048577);need(len(result)<=1048576)
            self.guard();return result
        except Exception as error:
            if callable(getattr(error,"close",None)):error.close()
            raise
    def original(self):
        started=self.monotonic();epoch=self.epoch_ms();need(number(started,0,1e15) and number(epoch,1,1e15))
        actual=super().original();now=self.monotonic();current=self.epoch_ms()
        need(number(now,started,1e15) and number(current,epoch,1e15)
            and max(current-epoch,(now-started)*1000)<=1500)
        self.original_epoch=epoch;self.original_host=started
        return actual
    def observe(self):
        need(self.state is not None)
        actual,outside=self.original();need(outside==self.state['outsideSha256'])
        if self.state['pending'] is not None:
            # The original state cannot tell whether an uncertain old POST is
            # still queued. Keep its exact ownership and never resend it.
            need(actual==self.state['pending'])
            self.save(phase='ready',last=actual,pending=None)
        else:need(actual==self.state['last'])
        self.sequence+=1
        return {self.VERSION_FIELD:1,'domainId':self.domain,'sequence':self.sequence,
            'capturedEpochMs':self.original_epoch,'restored':self.state['phase']=='restored','standard':deepcopy(actual)}
