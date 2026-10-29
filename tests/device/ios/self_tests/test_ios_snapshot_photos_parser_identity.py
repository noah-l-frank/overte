"""Exact descriptor parity and mutable parser metadata; no graph authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
import unittest
from ios.adapters.snapshot_photos_end_round import methods,_methods_original
from ios.adapters import snapshot_photos_end_round as source


class SnapshotParserIdentityMemoTests(unittest.TestCase):
    def namespace(self):
        def leaf(value=[1],*,mode={'a':1}):return value,mode
        @wraps(leaf)
        def wrapped(*args,**kwargs):return leaf(*args,**kwargs)
        def enclosing(target):
            def closure():return target()
            return closure
        class Parent:
            CONSTANT={'rows':[1,2]}
            method=leaf
            static=staticmethod(wrapped)
        class Child(Parent):
            klass=classmethod(lambda cls:cls)
        return dict(leaf=leaf,alias=leaf,wrapped=wrapped,closure=enclosing(leaf),Parent=Parent,Child=Child,ChildAlias=Child)
    def signature(self,namespace):return methods(namespace,{})
    def parity(self,namespace):
        self.assertEqual(_methods_original(namespace),methods(namespace));self.assertEqual(_methods_original(namespace),self.signature(namespace))
    def test_exact_alias_inheritance_wrapped_closure_signature_parity(self):
        self.parity(self.namespace())
        expected=tuple((name,id(module),_methods_original(vars(module)),tuple((key,source.data(value))
            for key,value in sorted(vars(module).items()) if key.isupper() and key not in ('_ORIGINAL','_BASELINES','_DEPENDENCIES')))
            for name,module in sorted(source.modules().items()))
        self.assertEqual(expected,source.parser_identity())
    def test_no_descriptor_is_borrowed_across_identity_checks(self):
        namespace=self.namespace();first=self.signature(namespace);namespace['Child'].new_method=lambda self:1
        self.parity(namespace);self.assertNotEqual(first,self.signature(namespace))
    def test_replacing_method_object_is_seen(self):
        namespace=self.namespace();first=self.signature(namespace);namespace['Parent'].method=lambda self:2
        self.parity(namespace);self.assertNotEqual(first,self.signature(namespace))
    def test_replacing_function_code_is_seen_without_replacing_function(self):
        namespace=self.namespace();first=self.signature(namespace)
        def changed(value=[1],*,mode={'a':1}):return mode,value
        namespace['leaf'].__code__=changed.__code__
        self.parity(namespace);self.assertNotEqual(first,self.signature(namespace))
    def test_mutating_positional_default_is_seen(self):
        namespace=self.namespace();first=self.signature(namespace);namespace['leaf'].__defaults__[0].append(2)
        self.parity(namespace);self.assertNotEqual(first,self.signature(namespace))
    def test_mutating_keyword_default_is_seen(self):
        namespace=self.namespace();first=self.signature(namespace);namespace['leaf'].__kwdefaults__['mode']['a']=2
        self.parity(namespace);self.assertNotEqual(first,self.signature(namespace))
    def test_mutating_inherited_class_constant_is_seen(self):
        namespace=self.namespace();first=self.signature(namespace);namespace['Parent'].CONSTANT['rows'].append(3)
        self.parity(namespace);self.assertNotEqual(first,self.signature(namespace))
    def test_rebinding_closure_function_is_seen(self):
        namespace=self.namespace();first=self.signature(namespace);namespace['closure'].__closure__[0].cell_contents=lambda:3
        self.parity(namespace);self.assertNotEqual(first,self.signature(namespace))


if __name__=='__main__':unittest.main()
