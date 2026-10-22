"""Historical recipe program counter followed by fresh ordinary input.

The historical prefix only interprets unchanged original control/command
records. It never invokes an SDK or reissues a recorded command. Every step
after that prefix uses the ordinary AvatarUI transport and new durable intent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.avatar_controls import AvatarUI
from ios.adapters.avatar_input_owner import intent,delivery,observed as original_observed


class AvatarRecipeUI(AvatarUI):
    def __init__(self,io,own_intent,events,*,deadline,delivered=None,observed=None,monotonic,sleep):
        need(type(events) is list and len(events)<=64 and callable(deadline))
        super().__init__(io,own_intent,delivered=delivered,observed=observed,monotonic=monotonic,sleep=sleep)
        self.prefix=deepcopy(events);self.cursor=0;self.deadline=deadline;self.joined=not events
        for event in events:
            need(event['phase']=='observed');pid=event['intent']['reference']['scope']['processId']
            intent(event['intent'],pid);delivery(event['delivery'],event['intent'],pid)
            original_observed(event['observed'],event['intent'],event['delivery'],pid)

    def capture(self):
        need(self.deadline() is not False)
        if self.cursor<len(self.prefix):
            return deepcopy(self.prefix[self.cursor]['intent']['reference'])
        if not self.joined:
            self.last=deepcopy(self.prefix[-1]['observed']);self.joined=True
            current=super().capture();previous=self.prefix[-1]
            def pages(value):return {row['id']:(row['rootId'],row['qmlSource']) for row in value['controls'] if row['id'] in ('avatar.page','people.page')}
            old,new=pages(previous['observed']),pages(current)
            navigation=previous['intent']['controlId'] in ('tablet.home','avatar.entry','people.entry') or previous['intent']['controlId'].startswith('tablet.page.')
            if not navigation:need(old==new)
            else:
                for page in old.keys()&new.keys():need(old[page]==new[page])
            return current
        return super().capture()

    def now(self):
        need(self.deadline() is not False);return super().now()

    def before_deliver(self):
        need(self.deadline() is not False);return True

    def input(self,identifier,action='activate',value=None):
        need(self.deadline() is not False)
        if self.cursor<len(self.prefix):
            event=self.prefix[self.cursor];original=event['intent']
            need(original['controlId']==identifier and original['action']==action and same(original.get('value'),value)
                and ('value' in original)==(value is not None))
            self.cursor+=1
            return deepcopy(original['reference']),deepcopy(event['observed'])
        return super().input(identifier,action,value)

    def complete(self):
        need(self.deadline() is not False);need(self.cursor==len(self.prefix))
        # Even a recipe whose final event is entirely historical must join an
        # actual current control source before its caller can examine effects.
        if not self.joined:self.capture()
