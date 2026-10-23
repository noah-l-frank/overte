"""Cooperative clock for two real API/worker tasks in the explicit host model.

Pure decoder CPU and a busy source-lock poll create no native event. Parallel
waits advance the existing producer clock to the earliest wake, never by their
sum. Every DTO is still first produced by its original model producer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import threading


class CleanupScheduler:
    def __init__(self,clock,advance):
        self.clock,self.advance=clock,advance;self.condition=threading.Condition()
        self.roles={role:None for role in ('primary','actor')};self.steps=[]

    def wake(self):
        if not self.roles or any(value is None for value in self.roles.values()):return
        before=self.clock[0];due=min(self.roles.values());delay=max(0,due-before)
        if delay:self.advance(delay)
        after=self.clock[0];self.steps.append(dict(before=before,after=after,due=due))
        for role,value in self.roles.items():
            if value<=after+1e-9:self.roles[role]=None
        self.condition.notify_all()

    def sleep(self,role,seconds):
        assert type(seconds) in (int,float) and seconds>=0
        with self.condition:
            assert role in self.roles and self.roles[role] is None
            self.roles[role]=self.clock[0]+seconds;self.wake()
            while role in self.roles and self.roles[role] is not None:
                self.condition.wait(.1);self.wake()

    def finish(self,role):
        with self.condition:
            assert role in self.roles;del self.roles[role];self.wake();self.condition.notify_all()
