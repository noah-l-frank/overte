"""Original immediate Graphics inputs; no render/pass or persistence verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import time
from adapters.normal_feature_state import need
from adapters.normal_ui import NativeUIError

IDS=frozenset({'graphics.page','graphics.settings-entry','settings.entry','graphics.resolution',
               'graphics.haze','graphics.mirrors','graphics.scrollbar'})
PROFILES=frozenset({'phone-immediate-v1','generic-immediate-v1'})


def graphics_control(identifier): return type(identifier) is str and identifier in IDS


def metadata_fields(identifier):
    need(graphics_control(identifier))
    return {'inputReady','viewport'} | {'graphics.page':{'profile'},
        'graphics.resolution':{'value','nativeValue','minimum','maximum','step'},
        'graphics.haze':{'checked','nativeChecked'},'graphics.mirrors':{'checked','nativeChecked'},
        'graphics.scrollbar':{'position','size'}}.get(identifier,set())


def finite(value,low,high):return type(value) in (int,float) and math.isfinite(value) and low<=value<=high


def on_grid(value,row):
    if not finite(value,row['minimum']-1e-6,row['maximum']+1e-6):return False
    units=(value-row['minimum'])/row['step']
    return abs(units-round(units))<1e-4


def validate_metadata(row):
    need(metadata_fields(row['id'])<=set(row) and type(row['inputReady']) is bool
         and type(row['viewport']) is str and row['viewport'] in ('visible','above','below','outside'))
    if row['inputReady']:need(row['viewport']=='visible')
    if row['id']=='graphics.page':need(row['inputReady'] is False and type(row['profile']) is str and row['profile'] in PROFILES)
    elif row['id']=='graphics.resolution':
        need(finite(row['minimum'],0.1-1e-6,2) and finite(row['maximum'],0.1,2+1e-6)
             and row['maximum']>row['minimum'] and finite(row['step'],1e-6,row['maximum']-row['minimum'])
             and finite(row['value'],row['minimum']-1e-6,row['maximum']+1e-6) and finite(row['nativeValue'],0.1,2))
        if row['inputReady']:need(abs(row['value']-row['nativeValue'])<1e-4 and on_grid(row['nativeValue'],row))
    elif row['id'] in ('graphics.haze','graphics.mirrors'):
        need(type(row['checked']) is bool and type(row['nativeChecked']) is bool)
        if row['inputReady']:need(row['checked']==row['nativeChecked'])
    elif row['id']=='graphics.scrollbar':
        need(finite(row['size'],1e-6,1) and finite(row['position'],0,1-row['size']+1e-6))


class TokenGraphicsUI:
    def __init__(self,io,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (intent,monotonic,sleep)))
        self.io,self.intent,self.monotonic,self.sleep=io,intent,monotonic,sleep
        self.identity=self.profile=self.last_clock=None

    def now(self):
        value=self.monotonic();need(finite(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    @staticmethod
    def row(value,identifier):
        rows=[row for row in value['controls'] if row['id']==identifier];need(len(rows)<=1)
        return rows[0] if rows else None

    def capture(self):
        value=self.io.capture()
        need(type(value) is dict and type(value.get('graphicsControlsVersion')) is int
             and value['graphicsControlsVersion']==1 and value.get('ready') is True
             and type(value.get('controls')) is list and len(value['controls'])<=384)
        identity=(value.get('instance',value.get('bridgeId')),value.get('generation'))
        need(type(identity[0]) is str and bool(identity[0])
             and (identity[1] is None or type(identity[1]) is str and bool(identity[1]))
             and self.identity in (None,identity));self.identity=identity
        seen=set()
        for row in value['controls']:
            need(type(row) is dict and type(row.get('id')) is str and row['id'] not in seen);seen.add(row['id'])
            if graphics_control(row['id']):
                need(type(row.get('enabled')) is bool and type(row.get('token')) is str and bool(row['token']))
                validate_metadata(row)
        page=self.row(value,'graphics.page')
        if page:
            need(self.profile in (None,page['profile']));self.profile=page['profile']
        else:need(not any(row['id'] in ('graphics.resolution','graphics.haze','graphics.mirrors') for row in value['controls']))
        return value

    def wait(self,predicate):
        started=self.now()
        for _attempt in range(101):
            value=self.capture();now=self.now()
            if now-started>10:break
            if predicate(value):return value
            if now-started>=10:break
            self.sleep(0.1)
        raise NativeUIError('Original Graphics UI did not reach its observed state')

    def visible(self,identifier):
        need(identifier in ('graphics.resolution','graphics.haze','graphics.mirrors'))
        for _attempt in range(8):
            value=self.capture();row=self.row(value,identifier);need(row is not None)
            if row['viewport']=='visible':
                if row['enabled'] and row['inputReady']:return row
                observed=self.wait(lambda v:(self.row(v,identifier) or {}).get('inputReady') is True)
                ready=self.row(observed,identifier);need(ready['enabled']);return ready
            need(row['viewport'] in ('above','below'))
            bar=self.row(value,'graphics.scrollbar');need(bar is not None and bar['enabled'] and bar['inputReady'])
            direction='up' if row['viewport']=='above' else 'down';before=bar['position']
            need(before>0 if direction=='up' else before<1-bar['size']-1e-6)
            self.intent('scroll-'+direction,value,'graphics.scrollbar')
            self.io.scroll('graphics.scrollbar',direction,token=bar['token'])
            def progressed(current):
                position=(self.row(current,'graphics.scrollbar') or {}).get('position');need(position is not None)
                return position<before-1e-6 if direction=='up' else position>before+1e-6
            self.wait(progressed)
        raise NativeUIError('Original Graphics control remains outside its viewport')

    def set_resolution(self,value):
        initial=self.row(self.capture(),'graphics.resolution');need(initial is not None and on_grid(value,initial))
        row=self.visible('graphics.resolution');need(on_grid(value,row))
        if abs(row['nativeValue']-value)>=1e-4:
            current=self.capture();original=self.row(current,'graphics.resolution')
            need(original is not None and original['enabled'] and original['inputReady'] and original['token']==row['token'])
            self.intent('set-resolution',current,'graphics.resolution')
            self.io.set_value('graphics.resolution',value,token=row['token'])
        observed=self.wait(lambda v:self.row(v,'graphics.resolution') is not None
            and self.row(v,'graphics.resolution')['inputReady']
            and abs(self.row(v,'graphics.resolution')['nativeValue']-value)<1e-4)
        return self.row(observed,'graphics.resolution')

    def toggle(self,identifier,enabled):
        need(identifier in ('graphics.haze','graphics.mirrors') and type(enabled) is bool)
        row=self.visible(identifier)
        if row['nativeChecked']!=enabled:
            current=self.capture();original=self.row(current,identifier)
            need(original is not None and original['enabled'] and original['inputReady'] and original['token']==row['token'])
            self.intent('set-'+identifier.rsplit('.',1)[1],current,identifier)
            self.io.activate(identifier,token=row['token'])
        observed=self.wait(lambda v:(self.row(v,identifier) or {}).get('nativeChecked') is enabled
            and (self.row(v,identifier) or {}).get('inputReady') is True)
        return self.row(observed,identifier)
