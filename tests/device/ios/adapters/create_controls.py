"""Original iOS Create controls; native UI component scope only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from ios.adapters.create_controls_v2 import project


class IOSCreateIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.native.create_input(identifier,'activate',reference=reference)
    def replace(self,identifier,value,*,reference):self.original.native.create_input(identifier,'replace',reference=reference,value=value)
    def select_index(self,identifier,value,*,reference):self.original.native.create_input(identifier,'select-index',reference=reference,value=value)
    def scroll(self,identifier,value,*,reference):self.original.native.create_input(identifier,'scroll',reference=reference,value=value)
