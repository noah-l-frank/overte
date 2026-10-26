"""Ordinary UIKit W3C touch/text inputs bound to original visible Tablet DOM.

Each mutation is announced durably before delivery. Returned requests are input
ACK metadata only; actual trusted DOM/UIKit events remain independent sources.
No JavaScript mutation, hidden field selection or Script/native setter is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import uuid
from adapters.native_feature_observation import exact,fresh,need,number
from adapters.normal_ui import NativeUI,NativeUIError,WEBDRIVER_KEYS
from adapters.normal_feature_state import context
from ios.adapters import tablet_web_dom as dom,tablet_web_presentation as presentation


def input_text(field,text):
    need(field in ('text','foreign') and type(text) is str)
    try:
        text.encode('utf-8');units=len(text.encode('utf-16-le'))//2
    except UnicodeError:raise NativeUIError('Controlled Tablet text encoding is invalid') from None
    need(units<=(512 if field=='text' else 8192)
        and not any(ord(char)<32 or ord(char)==127 or ord(char) in WEBDRIVER_KEYS for char in text))
    return text


class TabletWebNativeInput:
    def __init__(self,client,binding,clock_ms,guard,intent):
        self.binding=deepcopy(context(binding));need(all(callable(value) for value in (clock_ms,guard,intent)))
        self.clock_ms=clock_ms
        self.ui=NativeUI(client,self.binding['sessionId'],guard);self.intent=intent

    def owned(self,document,element):
        dom.original(document);need(document['status']=='ready' and self.binding['processIdentity']==str(document['processId']))
        fresh(document['clockAfter']['epochMs'],self.clock_ms())
        source=document['source'];presentation.current(source['presentationAfter'])
        need(source['presentationBefore']==source['presentationAfter'])
        rows=[row for row in source['dom']['elements'] if row['id']==element];need(len(rows)==1)
        row=rows[0];need(row['visible'] and row['enabled']);point=presentation.point(source['presentationAfter'],source['dom']['document'],row)
        return source,row,point

    @staticmethod
    def screen_rect(source,row):
        viewport=source['dom']['document']['visualViewport'];frame=source['presentationAfter']['screenFrame']
        scale=frame[2]/viewport['width'];left,top,right,bottom=row['rect']
        return dict(x=frame[0]+(left-viewport['offsetLeft'])*scale,y=frame[1]+(top-viewport['offsetTop'])*scale,
            width=(right-left)*scale,height=(bottom-top)*scale)

    def _mutation(self,kind,path,body,ownership,will_send=None,*,transport=None,intent=None):
        need(kind in ('touch','release','clear','text'))
        need(path=='/actions' if kind in ('touch','release') else type(path) is str
            and re.fullmatch(r'/element/[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}/'+('clear' if kind=='clear' else 'value'),path))
        ui=self.ui;callback=self.intent if intent is None else intent
        send=ui._request if transport is None else transport
        if kind!='release':ui._check()
        record=dict(tabletWebNativeInputVersion=1,id=uuid.uuid4().hex,kind=kind,path=path,body=deepcopy(body),ownership=deepcopy(ownership))
        need(callback('issued',deepcopy(record)) is not False)
        if kind!='release':ui._check();fresh(ownership['nativeCapturedEpochMs'],self.clock_ms())
        if will_send is not None:will_send()
        result=send('DELETE' if kind=='release' else 'POST',path,body)
        need(callback('returned',deepcopy(record)) is not False)
        if kind!='release':ui._check()
        return result

    def tap(self,document,element):
        source,row,point=self.owned(document,element);point=[round(value) for value in point]
        rect=self.screen_rect(source,row);need(rect['x']<=point[0]<rect['x']+rect['width'] and rect['y']<=point[1]<rect['y']+rect['height'])
        owner=dict(nativeView=deepcopy(source['nativeView']),domInstance=source['dom']['instance'],nativeCapturedEpochMs=document['clockAfter']['epochMs'],
            requestId=document['commandId'],element=element,birth=row['birth'],point=point)
        body={'actions':[{'type':'pointer','id':'tablet-web-'+uuid.uuid4().hex,'parameters':{'pointerType':'touch'},'actions':[
            {'type':'pointerMove','duration':0,'origin':'viewport','x':point[0],'y':point[1]},
            {'type':'pointerDown','button':0},{'type':'pause','duration':80},{'type':'pointerUp','button':0}]}]}
        attempted=[False];ui=self.ui;client=ui.client;call=client.call;base=ui.base;intent=self.intent
        server=getattr(client,'server_url',None)
        def release_send(method,path,value):
            need(method=='DELETE' and path=='/actions' and value is None and getattr(client,'server_url',None)==server)
            try:return call(method,base+path,value)
            except Exception:raise NativeUIError('Normal native UI transport failed') from None
        def sent():attempted[0]=True
        try:self._mutation('touch','/actions',body,owner,sent,intent=intent)
        finally:
            if attempted[0]:self._mutation('release','/actions',None,owner,transport=release_send,intent=intent)
        return deepcopy(owner)

    def active_field(self,source,row,expected_value,*,expected_element=None):
        """Read the current actual UIKit field; no clear ACK supplies value."""
        ui=self.ui;ui._check();reference=ui._request('GET','/element/active');element=ui._element(reference);ui._check()
        if expected_element is not None:need(element==expected_element)
        kind=ui._request('GET',element+'/attribute/type');rect=ui._request('GET',element+'/rect')
        label=ui._request('GET',element+'/attribute/label')
        visible=ui._request('GET',element+'/displayed');enabled=ui._request('GET',element+'/enabled');ui._check()
        need(kind=='XCUIElementTypeTextField' and visible is enabled is True and type(row['accessibilityLabel']) is str
            and row['accessibilityLabel'] and label==row['accessibilityLabel']);exact(rect,{'x','y','width','height'})
        need(all(number(rect[key],-1e6,1e6) for key in rect) and rect['width']>0 and rect['height']>0)
        expected=self.screen_rect(source,row)
        need(all(abs(rect[key]-expected[key])<=2. for key in rect))
        value=ui._request('GET',element+'/attribute/value');ui._check();need(type(value) is str and value==expected_value)
        return reference,element,kind,rect,label,value

    def replace(self,document,field,text):
        input_text(field,text)
        source,row,point=self.owned(document,field);need(row['focused'] and source['presentationAfter']['responders'])
        reference,element,kind,rect,label,value=self.active_field(source,row,row['value'])
        owner=dict(nativeView=deepcopy(source['nativeView']),domInstance=source['dom']['instance'],requestId=document['commandId'],
            nativeCapturedEpochMs=document['clockAfter']['epochMs'],field=field,birth=row['birth'],elementReference=deepcopy(reference),type=kind,accessibilityLabel=label,rect=deepcopy(rect),
            beforeTextSha256=hashlib.sha256(value.encode()).hexdigest(),point=point)
        if value:self._mutation('clear',element+'/clear',{},owner)
        if text:
            # A successful clear can synchronously move focus or leave text
            # unchanged. Reacquire current UIKit identity/state before the
            # remaining, still-unissued text request; never repeat the clear.
            if value:self.active_field(source,row,'',expected_element=element)
            self._mutation('text',element+'/value',{'text':text,'value':list(text)},owner)
        return deepcopy(owner)
