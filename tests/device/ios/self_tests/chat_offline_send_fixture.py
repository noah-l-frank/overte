"""Actual ordinary Script wires; declared native node/callback/cache producers.

No native MessagesClient, real mixer, domain, Qt, SDK or network executes.
The lower callback model selects its node state before normal Send. It emits
only from actual production-Script wire bytes, never an expected message list.
"""
from copy import deepcopy
import json
from ios.self_tests.chat_send_receive_fixture import SendReceiveFixture
from self_tests.test_native_chat_observation import SELF


class OfflineSendFixture(SendReceiveFixture):
    def __init__(self, case):
        super().__init__(case)
        self.node_present = True
        self.node_sha = 'd' * 64
        self.ignore_native_delivery = False
        self.ignore_script_callback = False
        self.false_local_only = False
        self.unexpected_peer_delivery = False
        self.replay_on_restore = False
        self.last_wire = None
        self.lower_wires = []
        # Configure the pre-existing lower Messages callback seam before any
        # normal owner input. Actual Script handlers and query readers stay
        # unchanged. This model, rather than the old always-online shim, now
        # determines whether the actual wire receives a native callback.
        self.model.command('echo', enabled=False)
        self.model.bus = self.deliver_native
        self.observation_fault = self.native_node_original

    def native_node_original(self, role, value):
        value['source']['mixerPresent'] = self.node_present
        value['source']['mixerSha256'] = self.node_sha if self.node_present else ''

    def remove_mixer(self):
        self.node_present = False
        self.pair.primary.mixer = self.pair.peer.mixer = False

    def restore_mixer(self):
        self.node_sha = 'a' * 64
        self.node_present = True
        self.pair.primary.mixer = self.pair.peer.mixer = True
        if self.replay_on_restore and self.last_wire is not None:
            self.deliver_native(deepcopy(self.last_wire))

    def deliver_native(self, wire):
        assert wire['channel'] == 'chat' and type(wire['localOnly']) is bool
        body = json.loads(wire['message'])
        assert body['action'] == 'send_chat_message' and type(body['message']) is str
        self.last_wire = deepcopy(wire); self.lower_wires.append(deepcopy(wire))
        if self.ignore_native_delivery:
            return
        # Exact declared MessagesClient.cpp branch: explicit local delivery or
        # absence of its original node means local-only emission. Presence
        # takes the connected packet path. No process ACK supplies this state.
        local = wire['localOnly'] or not self.node_present
        if local:
            event = dict(sequence=len(self.pair.primary.events) + 1,
                         capturedEpochMs=self.epoch['primary'](), senderSha256=SELF,
                         localOnly=not self.false_local_only,
                         channel=body['channel'], text=body['message'])
            self.pair.primary.events.append(event)
            if self.unexpected_peer_delivery:
                other = dict(event, sequence=len(self.pair.peer.events) + 1,
                             capturedEpochMs=self.epoch['peer'](), localOnly=False)
                self.pair.peer.events.append(other)
        else:
            super().deliver(wire)
        if not self.ignore_script_callback:
            # This invokes the real armored_chat.js incoming callback. It
            # deliberately does NOT apply input-return snapshots to the UI or
            # Settings model; later real query intents read them independently.
            self.model.command('receive', message=wire['message'], localOnly=local)
