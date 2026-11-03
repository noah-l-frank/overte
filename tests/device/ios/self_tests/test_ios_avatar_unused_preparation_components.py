"""Real native-channel Runtime preparation graphs and retained current guards.

Ordinary marker inputs, current bindings and original constructors are literal.
Native/Qt/GPU producers remain host models. A declared observer-entry stop ends
before fresh observation, so this is not normal/whole/device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import sys
from types import CodeType
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import VERSION
from ios.adapters.avatar_feature import IOSAvatarFeature,WholeAvatarObserver
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_observer import IOSAvatarObserver
from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
from ios.adapters.installed_code import InstalledCodeBinding
from ios.self_tests.test_ios_avatar_bilateral_initial_barrier import AvatarBilateralInitialBarrierTests
from ios.self_tests.avatar_prepare_fixture import RUN


class ObserverEntryStopped(RuntimeError):pass


class OriginalConstructorCounts:
    """Exact original local START events only; no code/function/frame replacement."""
    def __init__(self):
        self.bindings={
            'actual':IOSAvatarFeature.actual.__code__,
            'sourceParts':IOSAvatarFeature.source_parts.__code__,
            'components':IOSAvatarFeature.components.__code__,
            'currentSources':IOSScriptRuntime._sources.__code__,
            'installedVerify':InstalledCodeBinding.verify.__code__,
            'sourceFactory':IOSAvatarRuntime._avatar_sources.__code__,
            'peerFactory':IOSAvatarRuntime._avatar_peer_sources.__code__,
            'sampleFactory':IOSAvatarRuntime._avatar_samples.__code__,
            'sourceConstructor':IOSAvatarSources.__init__.__code__,
            'sampleConstructor':IOSAvatarSamples.__init__.__code__,
            'observerConstructor':IOSAvatarObserver.__init__.__code__,
        }
        assert all(type(code) is CodeType for code in self.bindings.values())
        assert len(set(self.bindings.values()))==len(self.bindings)
        self.names={code:name for name,code in self.bindings.items()};self.counts={name:0 for name in self.bindings};self.tool=None
        self.profile,self.trace=sys.getprofile(),sys.gettrace()
    def __enter__(self):
        assert self.profile is None and self.trace is None and self.tool is None
        self.monitoring=getattr(sys,'monitoring',None);assert self.monitoring is not None
        available=[i for i in (5,4,3,1,0,2) if self.monitoring.get_tool(i) is None];assert available
        self.tool=available[0];self.name='avatar-unused-preparation-original-counters-'+str(id(self))
        self.monitoring.use_tool_id(self.tool,self.name)
        try:
            assert self.monitoring.get_events(self.tool)==0
            self.monitoring.register_callback(self.tool,self.monitoring.events.PY_START,self.start)
            for code in self.names:
                self.monitoring.set_local_events(self.tool,code,self.monitoring.events.PY_START)
                assert self.monitoring.get_local_events(self.tool,code)==self.monitoring.events.PY_START
        except BaseException:self.__exit__(None,None,None);raise
        return self
    def start(self,code,offset):
        assert code in self.names
        name=self.names[code];self.counts[name]+=1;assert sum(self.counts.values())<=10000
    def __exit__(self,*_args):
        if self.tool is None:return
        m=self.monitoring;tool=self.tool;assert m.get_tool(tool)==self.name and m.get_events(tool)==0
        for code in self.names:m.set_local_events(tool,code,0)
        m.register_callback(tool,m.events.PY_START,None)
        assert all(m.get_local_events(tool,code)==0 for code in self.names)
        m.free_tool_id(tool);assert m.get_tool(tool) is None;self.tool=None
        assert sys.getprofile() is self.profile and sys.gettrace() is self.trace


class AvatarUnusedPreparationComponentsTests(AvatarBilateralInitialBarrierTests):
    def test_default_graph_and_explicit_opt_out_keep_current_both_sdk_guards_then_observe_builds_one_fresh_graph(self):
        f,d,runtime,primary,actor,_before=self.initial_pair()
        # The initial_pair counter's explicit stops end before marker inputs.
        # Complete each real own-role marker with the production Runtime; no
        # source/archive/guard/clock or returned result is substituted.
        actor.prepare_marker();primary.prepare_marker()
        for owner in (primary,actor):
            with owner.held(paired=True):owner.load();self.assertEqual('ready',owner.state['phase'])
        inputs={role:list(native.input_log) for role,native in d.natives.items()}
        counts_store=PrivateFeatureState(f.root/'actual-unused-preparation-observed-counts.json')
        def retain_counts(stage,counter):
            previous=counts_store.read();value={} if previous is None else dict(previous)
            value[stage]=dict(counter.counts);counts_store.write(value,previous)
        # Source.__init__ is shared by genuine historical archive reconstruction
        # and live construction. Preserve its total as a diagnostic, while
        # real fresh factories and their non-historical objects prove the graph.
        with OriginalConstructorCounts() as default:
            graph=primary.prepare()
        retain_counts('default-graph',default)
        self.assertEqual({'actual','sources','peers','scope','samples','surfaces','observer'},set(graph))
        self.assertIsInstance(graph['observer'],WholeAvatarObserver)
        self.assertIsInstance(graph['samples'],IOSAvatarSamples)
        self.assertTrue(all(isinstance(source,IOSAvatarSources) and not source.historical for source in graph['sources'].values()))
        self.assertTrue(all(isinstance(peer,IOSAvatarPeerSources) and not peer.historical for peer in graph['peers'].values()))
        for name,count in dict(actual=1,sourceParts=1,components=1,sourceFactory=2,peerFactory=2,
                               sampleFactory=1,sampleConstructor=1,observerConstructor=1).items():
            self.assertEqual(count,default.counts[name],name)
        self.assertGreaterEqual(default.counts['installedVerify'],2)
        self.assertGreater(default.counts['currentSources'],2)
        with OriginalConstructorCounts() as omitted:
            self.assertIsNone(primary.prepare(components=False))
        retain_counts('explicit-omission',omitted)
        self.assertEqual(1,omitted.counts['actual']);self.assertEqual(2,omitted.counts['currentSources'])
        self.assertGreaterEqual(omitted.counts['installedVerify'],2)
        for name in ('sourceParts','components','sourceFactory','peerFactory','sampleFactory','sampleConstructor','observerConstructor'):
            self.assertEqual(0,omitted.counts[name],name)
        # A stage stop marks observer entry, after the real fresh paired graph
        # has been constructed. It grants no observation/result/clock verdict.
        stop=ObserverEntryStopped('Declared counter stop at original observer entry before fresh observation')
        with OriginalConstructorCounts() as observed,patch.object(WholeAvatarObserver,'observe',side_effect=stop),self.assertRaises(ObserverEntryStopped) as caught:
            primary.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        retain_counts('public-observe-entry',observed)
        self.assertIs(stop,caught.exception)
        for name,count in dict(actual=2,sourceParts=1,components=1,sourceFactory=2,peerFactory=2,
                               sampleFactory=1,sampleConstructor=1,observerConstructor=1).items():
            self.assertEqual(count,observed.counts[name],name)
        self.assertGreaterEqual(observed.counts['installedVerify'],4)
        self.assertEqual(inputs,{role:list(native.input_log) for role,native in d.natives.items()})
        before_commands={role:len(native.commands) for role,native in d.natives.items()}
        with self.assertRaises(NativeUIError):primary.prepare(components=1)
        self.assertEqual(before_commands,{role:len(native.commands) for role,native in d.natives.items()})
        # Genuine changed peer process/current binding must still refuse the
        # opt-out through original Installed/native admission before any input.
        native=d.natives['actor'];installed=d.installed['actor'];native.pid+=1;installed.process['pid']=native.pid
        self.assertNotEqual(native.pid,installed.store.read()['process']['pid'])
        with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_REJECTED'):
            primary.prepare(components=False)
        self.assertEqual(inputs,{role:list(value.input_log) for role,value in d.natives.items()})
        for owner in (primary,actor):
            with owner.held():owner.load();self.assertIsNotNone(owner.initial_original())
        evidence=dict(defaultGraph=default.counts,explicitOmission=omitted.counts,publicObserveToEntry=observed.counts,
            mixedHistoricalAndLiveConstructorDiagnostic='sourceConstructor is retained as an unqualified total, never interpreted as fresh-only',
            freshGraphProof='Original Runtime source/peer/sample factories and actual non-historical returned graph objects',
            stageStop='Before any fresh WholeAvatarObserver acquisition/result',originalInputsUnchanged=True,
            changedPeerProcessRefusedByOriginalInstalledBinding=True,normalQualified=False,nativeQualified=False,wholeAvatarQualified=False)
        PrivateFeatureState(f.root/'actual-unused-preparation-constructor-counts.json').write(evidence,None)
