"""Real host weak roots/IPA/WAL and production Node Chat; Qt/native are models.

One actual Python page is deliberately retained by the declared cached-page
model. The root census holds zeroing weak references. A normal reopen reuses
that cached page; it never invents a second native loader birth from its URL.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from adapters.native_chat_view import NativeChatView
from ios.adapters.chat_qml_sources import IOSChatQmlSources
from ios.self_tests.chat_source_bound_fixture import SourceObservationModel
from ios.self_tests.chat_message_script_domain import ScriptMessageModel
from ios.self_tests.chat_roots_fixture import ChatRoots, Page
from ios.self_tests.chat_qml_cache_source_fixture import cache_packet
from ios.self_tests.test_ios_chat_qml_dependency_transport import packet as dependency_packet


class LoadedIdentityModel(SourceObservationModel, ScriptMessageModel):
    def __init__(self, case, image):
        super().__init__(case)
        self.roots = ChatRoots(pid=42, epoch=self.native_epoch, monotonic=lambda: self.widgets.clock)
        self.cached_page = None; self.qml_epoch = self.native_epoch() - 5000
        self.qml_base = cache_packet(self.qml_epoch); self.image = deepcopy(image)
        self.qml_sequence = 0; self.qml_queries = []; self.qml_raw = ''
        self.qml_fault = None; self.cut_fault = None; self.lose_qml_return = False; self.lose_send = False

    def qml_clock(self):
        return dict(epochMs=self.native_epoch(), monotonicMs=self.native_epoch() - self.qml_epoch)

    def identity(self):
        loaded = self.qml_base['source']
        return dict(qmlObservedLoadObjectIdentityVersion=1, observerInstance=loaded['instance'],
            **{key: loaded[key] for key in ('loadSequence', 'loadId', 'objectId', 'processId', 'clockDomain')},
            readBefore=self.qml_clock(), readAfter=self.qml_clock())

    def chat_input(self, identifier, action, *, reference, value=None):
        sent = len(self.widgets.sent)
        super().chat_input(identifier, action, reference=reference, value=value)
        if identifier == 'chat.entry':
            if self.cached_page is None: self.cached_page = Page()
            self.cached_page.in_tree = self.cached_page.visible = True
        elif identifier == 'chat.close' and self.cached_page is not None:
            self.cached_page.in_tree = self.cached_page.visible = False
        if self.lose_send and len(self.widgets.sent) > sent:
            from adapters.normal_ui import NativeUIError
            raise NativeUIError('Declared lost normal Send return after actual production JS delivery')

    def send_view(self, query):
        super().send_view(query)
        value = self.view_value; value['chatViewVersion'] = 4
        storage = value['source']['storage']
        storage['valueSha256'] = hashlib.sha256(json.dumps(storage, sort_keys=True).encode()).hexdigest()
        pages = [] if self.cached_page is None else [self.cached_page]
        if self.cached_page is not None:
            self.cached_page.model = self.cached_page.local if self.widgets.channel == 'local' else self.cached_page.domain
        ownership = self.roots.capture(pages); value['source']['rootOwnership'] = ownership
        if value['source']['ui']['present']:
            value['source']['ui']['rootIdentity'] = self.roots.observe(self.cached_page)
        links = [dict(rootIdentity=page['page'], atWalk=self.identity(), atRead=self.identity()) for page in ownership['pages']]
        value['loadedObjectIdentity'] = dict(chatViewLoadedObjectIdentityCutVersion=1,
            objectLinks=dict(chatRootLoadedObjectLinksVersion=1, census=str(ownership['sequence']),
                rootSourceInstance=ownership['instance'], rootObservationSequence=ownership['sequence'], links=links),
            cutCompletedEpochMs=self.native_epoch())
        if self.cut_fault: self.cut_fault(value)

    def view_reader(self):
        return NativeChatView(self.send_view, lambda: json.dumps(self.view_value), self.native_epoch, self.guard, 42,
            ios=True, loaded_object_identity=True, monotonic=lambda: self.widgets.clock, sleep=self.sleep)

    def send_qml(self, query):
        self.query(query); self.qml_queries.append(deepcopy(query)); self.tick(); self.qml_sequence += 1
        value = deepcopy(self.qml_base)
        value.update(requestId=query['commandId'], runId=query['runId'], sequence=self.qml_sequence, clockBefore=self.qml_clock())
        self.tick(); value['clockAfter'] = self.qml_clock()
        value['source']['cacheAtRead']['unit'].update(unitReadBefore=deepcopy(value['clockBefore']), unitReadAfter=deepcopy(value['clockAfter']))
        value = dependency_packet(value, self.image, 2 * self.qml_sequence - 1)
        if self.qml_fault: self.qml_fault(value)
        self.qml_raw = json.dumps(value)
        if self.lose_qml_return: raise OSError('Declared lost same-object QML read return')

    def qml_reader(self):
        return IOSChatQmlSources(self.send_qml, lambda: self.qml_raw, self.native_epoch, self.guard, 42,
            monotonic=lambda: self.widgets.clock, sleep=self.sleep)
