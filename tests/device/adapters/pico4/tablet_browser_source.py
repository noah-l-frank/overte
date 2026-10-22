"""Closed Pico tablet-source additions: original held callbacks and leases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need
from feature_journeys.contract import identifier
from adapters.pico4.browser_source import PicoBrowserIO,identity,geometry_original,CONTROLS
from adapters.normal_ui import NativeUIError

HELD={'handle','creation','grant','page','url','token','revision','bodySha256','sourceSha256','payloadSha256','capturedEpochMs','origin','mainFrame','payloadBytes'}


def held(value,epoch):
    exact(value,HELD);identity(value);identifier(value['token'])
    origin=urlsplit(value['origin']);origin.port
    need(value['mainFrame'] is True and integer(value['payloadBytes'],1,65536) and origin.scheme=='http'
        and origin.hostname==value['token']+'.overte-inline.invalid' and origin.path in ('','/')
        and origin.username is None and origin.password is None and not origin.query and not origin.fragment)
    need(integer(value['revision'],1) and integer(value['capturedEpochMs'],1,epoch)
        and value['url']=='http://'+value['token']+'.overte-inline.invalid/index.html'
        and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]) for key in ('bodySha256','sourceSha256','payloadSha256')))


def deferred(value,epoch):
    exact(value,{'armed','pending','held','deliveries'})
    need(type(value['armed']) is bool and type(value['pending']) is bool and type(value['deliveries']) is list and len(value['deliveries'])<=16
        and not (value['armed'] and value['pending']))
    if value['held'] is not None:held(value['held'],epoch)
    need(not value['pending'] or value['held'] is not None)
    for row in value['deliveries']:
        exact(row,HELD|{'deliveredEpochMs','leaseCurrent','ownerAlive','accepted'})
        held({key:row[key] for key in HELD},epoch)
        need(integer(row['deliveredEpochMs'],row['capturedEpochMs'],epoch)
            and all(type(row[key]) is bool for key in ('leaseCurrent','ownerAlive','accepted')))


class PicoTabletBrowserIO(PicoBrowserIO):
    action='pico-tablet-web'

    def measure(self,run,url,owner,view,control):
        need(control in CONTROLS);identity(view)
        packet=self.request(run,url,owner,'measure',control=control,
            **{key:view[key] for key in ('handle','creation','grant','page')})
        need(packet['source']['nativeView']==view)
        return packet

    @staticmethod
    def geometry(packet,run,control):
        return geometry_original(packet['source']['geometryRaw'],
            dict(commandId=packet['commandId'],runId=run,control=control),
            packet['source']['nativeView']['url'],packet['capturedEpochMs'],visible=False)

    def reveal(self,run,url,owner,view,control,*,intent):
        """Read actual control bounds, issue normal wheels, remeasure movement.

        Each input is journaled before publication. A wheel ACK only permits
        passive reads; it never supplies the measured scroll/control effect.
        """
        need(control in CONTROLS-{'scroll-up','scroll-down'} and callable(intent))
        start=self.monotonic();previous=start;original=None
        for attempt in range(17):
            packet=self.measure(run,url,owner,view,control);actual=self.geometry(packet,run,control)
            need(actual['connected'] and actual['enabled'])
            if original is not None:
                need(actual['instance']==original['instance'] and actual['sequence']>original['sequence']
                    and actual['capturedEpochMs']>=original['capturedEpochMs'])
            center,viewport=actual['center'],actual['viewport']
            need(0<=center['x']<viewport['width'])
            if 0<=center['y']<viewport['height']:
                need(actual['hit']);return packet
            now=self.monotonic();need(previous<=now and now-start<10 and attempt<16 and not self.read_only);previous=now
            direction='scroll-up' if center['y']<0 else 'scroll-down'
            intent(dict(operation='wheel',control=direction,reference=packet))
            self.request(run,url,owner,'input',control=direction,text='',
                **{key:view[key] for key in ('handle','creation','grant','page')})
            # Observe movement after this exact delivery. No second wheel may be
            # issued just because the previous one was ignored or its result lost.
            deadline=self.monotonic()+1;original=actual;changed=False
            for read in range(12):
                current=self.measure(run,url,owner,view,control);after=self.geometry(current,run,control)
                now=self.monotonic();need(previous<=now and now-start<10);previous=now
                need(after['instance']==actual['instance'] and after['sequence']>actual['sequence']
                    and after['capturedEpochMs']>=actual['capturedEpochMs'] and after['connected'] and after['enabled'])
                movement=after['center']['y']-center['y']
                if (direction=='scroll-up' and movement>0.001) or (direction=='scroll-down' and movement<-0.001):
                    original=after;changed=True;break
                if now>=deadline or read==11:break
                self.sleep(.1)
            if not changed:raise NativeUIError('Normal Pico browser wheel produced no measured control movement')
        raise NativeUIError('Normal Pico browser control did not enter the viewport')

    def input_visible(self,run,url,owner,view,control,text='',*,intent):
        need(control in CONTROLS-{'scroll-up','scroll-down'} and not self.read_only)
        reference=self.reveal(run,url,owner,view,control,intent=intent)
        intent(dict(operation='input',control=control,reference=reference))
        return self.request(run,url,owner,'input',control=control,text=text,
            **{key:view[key] for key in ('handle','creation','grant','page')})
