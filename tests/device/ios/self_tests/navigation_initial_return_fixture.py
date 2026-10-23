"""Initial-process native model handles a real ordinary static-scene return.

The static-scene HTTP bytes and normal input owners are real. Qt/native/GPU
effects and native collection ticks are modeled before their first responses.
No saved source packet or acquisition clock is rewritten.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from feature_journeys.navigation_base_scene import resource_url
from ios.self_tests.navigation_feature_observer_fixture import Whole
from ios.self_tests.navigation_feature_next_ui_fixture import NextUI


class InitialReturnWorld(Whole):
    sync_navigation=NextUI.sync_navigation

    def __init__(self,test):
        super().__init__(test)
        self.static_source=deepcopy(self.sdk.navigation.source)
        self.base_url=resource_url(self.harness.inputs['sceneUrl'])
        self.collect_http=True;self.http_collection=[]
        response=self.http.response
        def completed(*args,**kwargs):
            value=response(*args,**kwargs)
            self.http_collection.append((self.http.xhr,self.http.reply,self.sdk.gpu.clock+.2));return value
        self.http.response=completed
        original=self.http.original
        def read():
            if self.collect_http:
                due=[row for row in self.http_collection if row[2]<=self.sdk.gpu.clock]
                for row in due:
                    xhr,reply,_when=row;current=self.http.xhr,self.http.reply
                    self.http.xhr,self.http.reply=xhr,reply;self.http.retire();self.http.xhr,self.http.reply=current
                    self.http_collection.remove(row)
            return original()
        self.http.original=read;self.sources['http'].original=read
