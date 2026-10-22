"""One modeled Qt widget/file producer driven by actual normal input tokens.

Original Places JS and QML materialize directory results. No admission packet
or retained source is changed when the ordinary widget later changes state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch
from ios.adapters import normal_input
from ios.self_tests.test_ios_places_settings import row


class PlacesWidget:
    def __init__(self,whole,test):
        self.h=whole;self.f=whole.flow_fixture;self.focus='';self.ignore=False;self.rows=[];self.edits=[]
        self.bookmarks=json.loads(whole.books.path.read_text());self.raw=None
        observed=self.f.b.observed;post=normal_input.urlopen;call=self.f.b.call
        def native_original():
            value=observed()
            if self.f.b.screen=='places' and whole.model.pages:
                value['controls']=[item for item in value['controls'] if not item['id'].startswith('places.')]
                value['controls'].extend(self.controls())
            return value
        def native_post(request,timeout):
            payload=json.loads(request.data);selected=None
            if payload['operation']=='edit':
                selected=next((deepcopy(item) for item in self.rows if item['token']==payload['input']['fieldToken']),None)
            old_field=self.f.b.field
            result=post(request,timeout)
            if payload['operation']=='edit' and selected is not None:
                self.f.b.field=old_field
                self.edits.append(deepcopy(payload['input']))
                if not self.ignore and self.f.b.native_boundary.receipt['status']['performed']:
                    self.apply(selected,payload['input'])
            return result
        def w3c(method,path,body=None):
            value=call(method,path,body)
            if whole.model.pages:
                shown=self.f.b.screen=='places';whole.model.shown=shown
                page=self.page();page.update(active=shown,visible=shown,currentAddress=self.f.b.current)
                self.visibility()
            return value
        self.f.b.observed=native_original;self.f.b.call=w3c
        boundary=patch.object(normal_input,'urlopen',native_post);boundary.start();test.addCleanup(boundary.stop)
        original_sources=self.f.runtime._sources
        def sources(selector):
            value=original_sources(selector)
            value.update(native=whole.sources['ui'],clock_source=whole.native,
                observer=SimpleNamespace(places_model=lambda _clock:whole.sources['model'],
                    navigation_state=lambda _clock:whole.navigation))
            return value
        self.f.runtime._sources=sources

    def page(self):return self.h.model.pages[0]

    def materialized(self,raw,page):
        self.raw=raw;page.update(currentAddress=self.f.b.current,bookmarkAddresses=deepcopy(self.bookmarks))
        self.sync_bookmarks(write=False);self.visibility()

    def visibility(self):
        page=self.page();shown=self.h.model.shown
        for key in ('places','bookmarks','servers'):
            page['lists'][key]['visible']=shown and page['tab']=={'places':0,'bookmarks':1,'servers':2}[key]

    def sync_bookmarks(self,*,write=True):
        page=self.page();page['bookmarkAddresses']=deepcopy(self.bookmarks)
        page['lists']['bookmarks']['rows']=[dict(bookmarkName=name,bookmarkAddress=url) for name,url in sorted(self.bookmarks.items())]
        if write:
            self.h.books.loaded=deepcopy(self.bookmarks)
            self.h.books.path.write_text(json.dumps(self.bookmarks,sort_keys=True))

    def controls(self):
        page=self.page();popup=page['popup'];items=[row('places.page',popup=popup)]
        if popup=='bookmark':
            items.extend(row(key,popup=popup) for key in ('places.bookmark-name','places.bookmark-save','places.bookmark-cancel'))
            items[1]['value']=page['dialog']['name']
        else:
            items.extend(row(key) for key in ('places.tab.places','places.tab.bookmarks'))
            if page['tab']==0:
                items.append(row('places.search'));items[-1]['value']=page['search']
                for place in page['lists']['places']['rows']:
                    key=hashlib.sha256(place['placeId'].encode()).hexdigest()[:32]
                    items.append(row('places.visit.'+key,name=place['placeId'],address=place['placeAddress']))
            else:
                items.append(row('places.bookmark-add'))
                for name,url in sorted(self.bookmarks.items()):
                    key=hashlib.sha256(name.encode()).hexdigest()[:32]
                    items.extend(row('places.'+kind+'.'+key,name=name,address=url)
                        for kind in ('bookmark-visit','bookmark-rename','bookmark-delete'))
        for item in items:
            item.update(rootId=page['rootId'],qmlSource=page['qmlSource'],focused=item['id']==self.focus,
                frame=dict(x=10,y=20,width=300,height=40))
        self.rows=items;return deepcopy(items)

    def apply(self,selected,command):
        key=selected['id'];page=self.page()
        if command['operation']=='replace':
            if key=='places.search':
                page['search']=command['text']
                materialized=self.h.http.model(self.raw,origin=self.h.harness.origin,run=self.h.run,query=page['search'])['roots'][0]
                page['records']=materialized['records'];page['lists']['places']['rows']=materialized['lists']['places']['rows']
            else:page['dialog']['name']=command['text']
        elif key in ('places.search','places.bookmark-name'):self.focus=key
        elif key.startswith('places.tab.'):
            page['tab']=0 if key.endswith('.places') else 1;self.focus='';self.visibility()
        elif key=='places.bookmark-add' or key.startswith('places.bookmark-rename.'):
            name=selected['rowName'] if key!='places.bookmark-add' else ''
            page.update(popup='bookmark',dialog=dict(visible=True,originalName=name,
                address=selected['rowAddress'] if name else page['currentAddress'],name=name));self.focus=''
        elif key in ('places.bookmark-save','places.bookmark-cancel'):
            if key.endswith('-save'):
                dialog=page['dialog']
                if dialog['originalName']:del self.bookmarks[dialog['originalName']]
                self.bookmarks[dialog['name']]=dialog['address'];self.sync_bookmarks()
            page['popup']='none';page['dialog']['visible']=False;self.focus=''
        elif key.startswith('places.bookmark-delete.'):
            del self.bookmarks[selected['rowName']];self.sync_bookmarks()
        elif key.startswith(('places.bookmark-visit.','places.visit.')):
            # Same ordinary physical Go To boundary used for scene entry.
            self.f.b.current=selected['rowAddress'];self.h.sync_navigation()
