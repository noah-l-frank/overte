"""Pure pair copying and actual Source fallback order over declared host models.

Metadata tests count genuine codec calls without modifying a second epoch
function. Source tests use the existing real-file/typed-reader fixture and call
its genuine validator; no current effect or Native/device qualification follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from ios.adapters import world_web_json_pair as pair_module
from ios.adapters import world_web_sources as sources
from ios.self_tests import test_ios_world_web_sources as fixture


def mutable_nodes(value):
    pending=[value];found={}
    while pending:
        item=pending.pop()
        if type(item) not in (dict,list) or id(item) in found:continue
        found[id(item)]=item;pending.extend(item.values() if type(item) is dict else item)
    return found


def independent(test,source,target):
    originals=mutable_nodes(source);forward={};reverse={};pending=[(source,target)]
    while pending:
        left,right=pending.pop();test.assertIs(type(left),type(right))
        if type(left) in (dict,list):
            if id(left) in forward:test.assertIs(forward[id(left)],right);continue
            test.assertNotIn(id(right),originals);test.assertNotIn(id(right),reverse)
            forward[id(left)]=right;reverse[id(right)]=left
            if type(left) is dict:
                test.assertEqual(list(left),list(right));pending.extend((left[key],right[key]) for key in left)
            else:test.assertEqual(len(left),len(right));pending.extend(zip(left,right))
        elif type(left) is float:test.assertEqual(struct.pack('>d',left),struct.pack('>d',right))
        else:test.assertEqual(left,right)


def observed(operation):
    counts=dict(dumps=0,loads=0);old=sys.getprofile()
    def profile(frame,event,arg):
        if event=='c_call':
            if arg is pair_module._DUMPS:counts['dumps']+=1
            elif arg is pair_module._LOADS:counts['loads']+=1
    try:sys.setprofile(profile);result=operation()
    finally:sys.setprofile(old)
    return result,counts


class WorldWebJSONPairTests(unittest.TestCase):
    def test_actual_fast_pair_preserves_types_floatbits_unicode_and_disjoint_graphs(self):
        if not pair_module._same_copy(copy.deepcopy):self.skipTest('Supported unchanged CPython only')
        value={'none':None,'bool':True,'int':2**4096,'float':1.25,'negativezero':-0.0,
            'strings':['ascii',chr(0x1f642),chr(0xd83d)+chr(0xde42),chr(0xd800),'Überte'],'rows':[{'a':1},[],{}]}
        pair,counts=observed(lambda:pair_module.clone_pair(value,copy.deepcopy))
        self.assertEqual(dict(dumps=1,loads=2),counts);self.assertIsNotNone(pair)
        independent(self,value,pair[0]);independent(self,value,pair[1]);independent(self,pair[0],pair[1])
        pair[1]['rows'][0]['a']=9;self.assertEqual(1,pair[0]['rows'][0]['a']);self.assertEqual(1,value['rows'][0]['a'])
    def test_actual_alias_and_cycle_graphs_are_preserved_in_both_independent_results(self):
        if not pair_module._same_copy(copy.deepcopy):self.skipTest('Supported unchanged CPython only')
        shared=[];value={'first':shared,'second':shared,'distinct':[]};shared.append(value)
        pair,counts=observed(lambda:pair_module.clone_pair(value,copy.deepcopy));self.assertEqual(dict(dumps=1,loads=2),counts)
        independent(self,value,pair[0]);independent(self,value,pair[1]);independent(self,pair[0],pair[1])
        self.assertIs(pair[0]['first'],pair[0]['second']);self.assertIs(pair[1],pair[1]['first'][0])
    def test_opaque_subclass_buffer_and_metaclass_hooks_are_not_invoked(self):
        effects=[]
        class Rows(list):
            def __iter__(self):effects.append('iter');raise AssertionError('Subclass iterated')
            def __deepcopy__(self,memo):effects.append('deepcopy');return ['literal']
        class Hostile(type):
            def __eq__(cls,other):effects.append('eq');raise AssertionError('Foreign type compared')
            def __hash__(cls):effects.append('hash');return 1
        class Opaque(metaclass=Hostile):
            def __buffer__(self,flags):effects.append('buffer');raise AssertionError('Opaque buffered')
            def __deepcopy__(self,memo):effects.append('deepcopy');return {'literal':True}
        for value in (Rows([1]),Opaque(),{'nested':Rows([1])}):
            result,counts=observed(lambda:pair_module.clone_pair(value,copy.deepcopy))
            self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts);self.assertEqual([],effects)
    def test_tuple_bytes_code_nonstring_key_and_nonfinite_refuse_without_copying(self):
        code=(lambda:None).__code__
        for value in (([1],),b'bytes',code,{1:'key'},float('nan'),float('inf'),-float('inf')):
            with self.subTest(kind=type(value).__name__):
                result,counts=observed(lambda:pair_module.clone_pair(value,copy.deepcopy))
                self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts)
    def test_changed_caller_alias_is_never_called_by_pair_helper(self):
        calls=[]
        def custom(value):calls.append(value);return {'literal':value}
        result,counts=observed(lambda:pair_module.clone_pair({'owned':[]},custom))
        self.assertIsNone(result);self.assertEqual([],calls);self.assertEqual(dict(dumps=0,loads=0),counts)
    def test_changed_deepcopy_code_is_the_only_fault_and_pair_refuses(self):
        original=copy.deepcopy.__code__
        def changed(value,memo=None,_nil=[]):return {'literalChanged':value}
        try:
            copy.deepcopy.__code__=changed.__code__
            value={'input':1};result,counts=observed(lambda:pair_module.clone_pair(value,copy.deepcopy))
            self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts)
            self.assertIs(value,copy.deepcopy(value)['literalChanged'])
        finally:copy.deepcopy.__code__=original
    def test_changed_list_dispatch_or_recursive_default_is_not_masked_by_other_changes(self):
        original=copy._deepcopy_dispatch[list];calls=[]
        def changed(value,memo):calls.append(True);return ['literal-dispatch']
        try:
            copy._deepcopy_dispatch[list]=changed
            result,counts=observed(lambda:pair_module.clone_pair([1],copy.deepcopy))
            self.assertIsNone(result);self.assertEqual([],calls);self.assertEqual(dict(dumps=0,loads=0),counts)
        finally:copy._deepcopy_dispatch[list]=original
        defaults=copy._deepcopy_list.__defaults__
        try:
            copy._deepcopy_list.__defaults__=(lambda value,memo:('literal-default',value),)
            result,counts=observed(lambda:pair_module.clone_pair([1],copy.deepcopy))
            self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts)
        finally:copy._deepcopy_list.__defaults__=defaults
    def test_changed_atomic_membership_or_nil_default_is_detected_alone(self):
        atomics=getattr(copy,'_atomic_types',None)
        if type(atomics) is set:
            atomics.add(dict)
            try:
                result,counts=observed(lambda:pair_module.clone_pair({'owned':1},copy.deepcopy))
                self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts)
            finally:atomics.remove(dict)
        nil=copy.deepcopy.__defaults__[1];nil.append('changed')
        try:
            result,counts=observed(lambda:pair_module.clone_pair({'owned':1},copy.deepcopy))
            self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts)
        finally:nil.pop()
    def test_changed_helper_functions_or_budgets_refuse_without_running_them(self):
        value={'owned':[1]}
        for name in ('_scan_json_graph','_roundtrip','_same_copy','_finite','_helper_epoch'):
            with self.subTest(function=name),patch.object(pair_module,name,side_effect=AssertionError('Changed helper executed')) as changed:
                result=pair_module.clone_pair(value,copy.deepcopy);self.assertIsNone(result);changed.assert_not_called()
        for name,value in (('_MAX_NODES',1),('_MAX_DEPTH',0),('_MAX_BYTES',1),('_SUPPORTED',False),('_JSON',())):
            with self.subTest(global_name=name),patch.object(pair_module,name,value):self.assertIsNone(pair_module.clone_pair({'owned':1},copy.deepcopy))
    def test_changed_marshal_api_is_not_invoked(self):
        for name in ('dumps','loads'):
            with self.subTest(api=name),patch.object(pair_module._marshal,name,side_effect=AssertionError('Changed marshal called')) as changed:
                self.assertIsNone(pair_module.clone_pair({'owned':1},copy.deepcopy));changed.assert_not_called()
    def test_actual_marshal_policy_exceptions_return_none_but_user_cancellation_propagates(self):
        if not pair_module._same_copy(copy.deepcopy):self.skipTest('Supported unchanged CPython only')
        active=[None]
        def audit(event,args):
            if event=='marshal.dumps' and active[0] is not None:raise active[0]
        sys.addaudithook(audit)
        for error in (RuntimeError('policy'),OSError('policy'),AssertionError('policy')):
            try:
                active[0]=error;result,counts=observed(lambda:pair_module.clone_pair({'owned':1},copy.deepcopy))
            finally:active[0]=None
            self.assertIsNone(result);self.assertEqual(dict(dumps=1,loads=0),counts)
        for error in (KeyboardInterrupt(),SystemExit()):
            try:
                active[0]=error
                with self.assertRaises(type(error)):pair_module.clone_pair({'owned':1},copy.deepcopy)
            finally:active[0]=None
    def test_deep_recursion_and_node_budget_refuse_instead_of_copying_inside_helper(self):
        value=[]
        for _ in range(pair_module._MAX_DEPTH+1):value=[value]
        result,counts=observed(lambda:pair_module.clone_pair(value,copy.deepcopy))
        self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts)
        value=[None]*(pair_module._MAX_NODES+1)
        result,counts=observed(lambda:pair_module.clone_pair(value,copy.deepcopy))
        self.assertIsNone(result);self.assertEqual(dict(dumps=0,loads=0),counts)


class RetainedDirectory:
    def __init__(self):self.name=tempfile.mkdtemp(prefix='world-json-pair-source-')
    def cleanup(self):pass


class WorldWebSourcePairTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebSourcesTests()
        with patch.object(fixture,'tempfile',SimpleNamespace(TemporaryDirectory=RetainedDirectory)):self.f.setUp()
        self.addCleanup(self.f.doCleanups)
    def test_real_source_default_pair_cache_outward_and_public_previous_stay_independent(self):
        f=self.f;literal=sources.WorldWebSources.validate_frame;mutated=[]
        def validating(owner,frame,previous=None):
            result=literal(owner,frame,previous)
            if previous is not None:
                cached=next(value for key,value in owner._cache.items() if key[0]==1)
                independent(self,cached,previous)
                previous['label']='literal-public-predecessor';mutated.append(previous)
            return result
        with f.held():
            current=f.sdk.owner(f.store,f.lock);reference=current.capture('baseline');current.capture('second')
            before=copy.deepcopy(f.store.read())
            with patch.object(sources.WorldWebSources,'validate_frame',validating):
                source,counts=observed(lambda:f.sdk.owner(f.store,f.lock,historical=True))
            if pair_module._same_copy(copy.deepcopy):self.assertEqual(dict(dumps=2,loads=4),counts)
            self.assertEqual(1,len(mutated));self.assertIs(mutated[0],source.frames[0])
            cache=next(value for key,value in source._cache.items() if key[0]==1)
            self.assertEqual('literal-public-predecessor',source.frames[0]['label']);self.assertEqual('baseline',cache['label'])
            self.assertTrue(set(mutable_nodes(cache)).isdisjoint(mutable_nodes(source.frames[0])))
            second=next(value for key,value in source._cache.items() if key[0]==2);independent(self,second,source.frames[1])
            source.frames[0]['label']='public-copy-mutated'
            self.assertEqual('baseline',source.frame(reference)['label'])
            self.assertEqual(before,source.previous);self.assertEqual(before,f.store.read())
    def fallback(self,mode):
        f=self.f;literal=sources.WorldWebSources.validate_frame;original=sources.clone_pair;code=original.__code__;defaults=original.__defaults__
        admitted=[];copied=[];did=[];copy_code=copy.deepcopy.__code__
        class Cache(dict):pass
        class OtherSource(sources.WorldWebSources):pass
        def forbidden(value,copier,*args):raise AssertionError('Changed pair implementation invoked')
        def validating(owner,frame,previous=None):
            result=literal(owner,frame,previous);admitted.append(frame)
            if not did:
                if mode=='alias':sources.clone_pair=forbidden
                elif mode=='code':original.__code__=forbidden.__code__
                elif mode=='defaults':original.__defaults__=(None,)
                elif mode=='cache-subtype':owner._cache=Cache(owner._cache)
                elif mode=='cache-identity':owner._cache={}
                elif mode=='owner-subtype':owner.__class__=OtherSource
                did.append(True)
            return result
        def profile(frame,event,arg):
            if event=='call' and frame.f_code is copy_code:
                item=frame.f_locals.get('x')
                if any(item is actual for actual in admitted):copied.append(item)
        with f.held():
            initial=f.sdk.owner(f.store,f.lock);reference=initial.capture('baseline');before=copy.deepcopy(f.store.read());old=sys.getprofile()
            try:
                with patch.object(sources.WorldWebSources,'validate_frame',validating):
                    sys.setprofile(profile);source=f.sdk.owner(f.store,f.lock,historical=True)
            finally:
                sys.setprofile(old);sources.clone_pair=original;original.__code__=code;original.__defaults__=defaults
            self.assertEqual(1,len(admitted));self.assertTrue(any(item is admitted[0] for item in copied))
            cache=next(iter(source._cache.values()));independent(self,cache,source.frames[0])
            self.assertEqual(before,source.previous);self.assertEqual(before,f.store.read())
            source.frames[0]['label']='public-copy-mutated';self.assertEqual('baseline',cache['label'])
    def test_validator_rebinding_pair_alias_runs_actual_literal_copy(self):self.fallback('alias')
    def test_validator_changing_pair_code_in_place_runs_actual_literal_copy(self):self.fallback('code')
    def test_validator_changing_pair_defaults_runs_actual_literal_copy(self):self.fallback('defaults')
    def test_validator_cache_subtype_runs_actual_literal_copy(self):self.fallback('cache-subtype')
    def test_validator_cache_identity_change_runs_actual_literal_copy(self):self.fallback('cache-identity')
    def test_validator_owner_subtype_runs_actual_literal_copy(self):self.fallback('owner-subtype')
    def test_current_copier_rebinding_occurs_after_cache_assignment_and_before_second_copy(self):
        f=self.f;literal=sources.WorldWebSources.validate_frame;original=sources.deepcopy;events=[];owner_box=[];admitted=[]
        def second(value):
            if type(value) is dict and value.get('index')==1 and 'originals' in value:
                self.assertTrue(any(value is item for item in owner_box[0]._cache.values()));events.append('second-after-cache')
            return original(value)
        def first(value):
            if any(value is item for item in admitted):events.append('first-before-cache');sources.deepcopy=second
            return original(value)
        def validating(owner,frame,previous=None):
            result=literal(owner,frame,previous);owner_box.append(owner);admitted.append(frame);sources.deepcopy=first;return result
        with f.held():
            initial=f.sdk.owner(f.store,f.lock);initial.capture('baseline');before=copy.deepcopy(f.store.read())
            try:
                with patch.object(sources.WorldWebSources,'validate_frame',validating):source=f.sdk.owner(f.store,f.lock,historical=True)
            finally:sources.deepcopy=original
            self.assertEqual(['first-before-cache','second-after-cache'],events)
            self.assertEqual(before,source.previous);self.assertEqual(before,f.store.read())
            independent(self,next(iter(source._cache.values())),source.frames[0])


class WorldWebPairCacheGateTests(unittest.TestCase):
    def test_foreign_collision_key_and_cache_subtype_never_invoke_unknown_callbacks(self):
        owner=object.__new__(sources.WorldWebSources);key=(1,'a'*64,None,'b'*64);events=[]
        class Collision:
            def __hash__(self):return hash(key)
            def __eq__(self,other):events.append('eq');raise AssertionError('Foreign key compared')
        owner._cache={Collision():None}
        self.assertIsNone(sources._pair_cache_ready(owner,key,owner._cache));self.assertEqual([],events)
        class Cache(dict):
            def __contains__(self,key):events.append('contains');raise AssertionError('Foreign cache queried')
        owner._cache=Cache();self.assertIsNone(sources._pair_cache_ready(owner,key,owner._cache));self.assertEqual([],events)


if __name__=='__main__':unittest.main()
