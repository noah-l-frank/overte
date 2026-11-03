"""Two actual Chat Scripts and independent selected IPA/loaded-root host models.

Qt, loader, native UI, mixer bus and SDK remain explicit producers. Real Node,
original files, zeroing weak roots, typed runtime and IPA decoders execute only
when Root runs this fixture. No build/device/source-authority claim follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from types import SimpleNamespace
import hashlib,json
from adapters.script_feature.history import same
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters import qt_image_bytes
from ios.self_tests.chat_loaded_identity_owner_fixture import LoadedIdentityModel
from ios.self_tests.chat_peer_receipt_fixture import SharedPhaseModel
from ios.self_tests.chat_peer_send_fixture import PeerSendFixture,HostClock
from ios.self_tests.chat_roots_fixture import ChatRoots,Page
from ios.self_tests.chat_qml_cache_source_fixture import cache_packet
from ios.self_tests.test_ios_chat_receive_runtime import IOSChatReceiveRuntimeTests
from ios.self_tests.test_ios_peer_admission import PeerAdmissionTests
from ios.self_tests.test_ios_qt_image_bytes import QtImageBytesTests
from ios.self_tests.test_ios_installed_code import InstalledCodeTests

class LoadedIPAAdmission(PeerAdmissionTests):
    def setUp(self):
        images=QtImageBytesTests();self.addCleanup(images.doCleanups)
        self.archive,self.fixture,sha,self.image=images.prepare();self.artifact=(self.archive.path,sha)
        self.primary=dict(self.fixture.scope,processIdentity='42',sessionId='separate-primary-session',targetFingerprint='b'*64)
        self.primary_installed=InstalledCodeTests();self.primary_installed.setUp();self.addCleanup(self.primary_installed.doCleanups)
        self.primary_installed.scope={key:value for key,value in self.primary.items() if key!='processIdentity'}
        self.primary_installed.native.bundle=deepcopy(self.fixture.native.bundle)
        self.primary_installed.binding=self.primary_installed.make();self.primary_installed.active()
        self.runtime=object.__new__(IOSScriptRuntime);self.gets=[];self.runtime._existing=self.existing
        self.runtime.adapter=SimpleNamespace(_binding=lambda *_args:self.fixture.make())

class LoadedPairRuntime(IOSChatReceiveRuntimeTests):
    admission_fixture_type=LoadedIPAAdmission

class LoadedPairModel(SharedPhaseModel):
    # These producer methods contain no superclass calls. Current clocks,
    # original loader data and native weak-root reads stay per-model.
    qml_clock=LoadedIdentityModel.qml_clock
    identity=LoadedIdentityModel.identity
    send_qml=LoadedIdentityModel.send_qml
    qml_reader=LoadedIdentityModel.qml_reader
    view_reader=LoadedIdentityModel.view_reader
    def __init__(self,case,clock,role,*,image):
        super().__init__(case,clock,role)
        self.roots=ChatRoots(pid=42,epoch=self.native_epoch,monotonic=lambda:self.widgets.clock)
        self.cached_page=None;self.qml_epoch=self.native_epoch()-5000;self.qml_base=cache_packet(self.qml_epoch)
        self.image=deepcopy(image);self.qml_sequence=0;self.qml_queries=[];self.qml_raw=''
        self.qml_fault=None;self.cut_fault=None;self.lose_qml_return=False;self.lose_send=False
    def chat_input(self,identifier,action,*,reference,value=None):
        before=len(self.widgets.sent);super().chat_input(identifier,action,reference=reference,value=value)
        if identifier=='chat.entry':
            if self.cached_page is None:self.cached_page=Page()
            self.cached_page.in_tree=self.cached_page.visible=True
        elif identifier=='chat.close' and self.cached_page is not None:
            self.cached_page.in_tree=self.cached_page.visible=False
        if self.lose_send and len(self.widgets.sent)>before:raise OSError('Declared lost normal Send return after original Script delivery')
    def send_view(self,query):
        super().send_view(query);value=self.view_value;value['chatViewVersion']=4
        storage=value['source']['storage'];storage['valueSha256']=hashlib.sha256(json.dumps(storage,sort_keys=True).encode()).hexdigest()
        pages=[] if self.cached_page is None else [self.cached_page]
        if self.cached_page is not None:self.cached_page.model=self.cached_page.local if self.widgets.channel=='local' else self.cached_page.domain
        ownership=self.roots.capture(pages);value['source']['rootOwnership']=ownership
        if value['source']['ui']['present']:value['source']['ui']['rootIdentity']=self.roots.observe(self.cached_page)
        links=[dict(rootIdentity=page['page'],atWalk=self.identity(),atRead=self.identity()) for page in ownership['pages']]
        value['loadedObjectIdentity']=dict(chatViewLoadedObjectIdentityCutVersion=1,
            objectLinks=dict(chatRootLoadedObjectLinksVersion=1,census=str(ownership['sequence']),
                rootSourceInstance=ownership['instance'],rootObservationSequence=ownership['sequence'],links=links),
            cutCompletedEpochMs=self.native_epoch())
        if self.cut_fault:self.cut_fault(value)

class LoadedPairedFixture:
    def __init__(self,case):
        pair=LoadedPairRuntime();clock=HostClock();clock.activations=[];clock.phase_sequence=0
        def model(case,clock,role):return LoadedPairModel(case,clock,role,image=pair.f.image)
        self.f=PeerSendFixture(case,clock=clock,model_class=model,pair_factory=lambda:pair)
        self.artifacts={role:pair.f.artifact for role in ('primary','peer')}
        self.contexts=pair.runtime._chat_receipt_contexts('primary','peer',self.f.receive.run,
            self.f.drafts['primary'].m.client(),self.f.receive,qml_artifacts=self.artifacts)
        self.installed={'primary':pair.f.primary_installed,'peer':pair.f.fixture}
        for role,draft in self.f.drafts.items():
            def images(value,role=role):
                gate=self.installed[role].binding;original=deepcopy(gate.record())
                bound=qt_image_bytes.bind_many(gate,[value['qtEntryImage'],value['qtDependencyEntryImage']],*self.artifacts[role])
                case.assertTrue(same(original,gate.record()));return dict(bindingOriginal=original,entryBindings=bound)
            draft.owner=partial(draft.owner,peer_receipts=self.contexts[role],qml_bound=True,
                qml_artifact=self.artifacts[role],qml_images=images)
