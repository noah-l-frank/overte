"""Genuine Scene1/ordered3 owners with declared native/HTTP lower models.

The unchanged native/SDK/Qt/WDA/PNG producers remain explicit host models.
The canonical Journal, its phase/sequence/receipt logic, real typed owners,
PFS/OFS, locks and normal capture path are genuine. HTTP dispatch/auth below
are declared transport models, not real server or independent-process proof.
"""
from copy import deepcopy
from unittest.mock import patch
from adapters.native_feature_observation import need
from feature_journeys.witness import Client,Journal
from ios.adapters.snapshot_scene_canonical_runtime import IOSSnapshotSceneCanonicalRuntime
from ios.self_tests.snapshot_scene_order_domain import OrderedSceneDomain,RUN,TICKET


class CanonicalSceneDomain(OrderedSceneDomain):
    def __init__(self,case,*,enabled=True):
        super().__init__(case)
        self.journal=Journal(clock=self.primary.capture.epoch,snapshot_scene_samples=enabled)
        # Only the input run allocator is modeled, before any operation/source
        # original exists. No returned native/frame/phase original is edited.
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):
            need(self.journal.register('snapshots')==RUN)
        self.journal.activate(RUN,TICKET,'capture',dict(mode='still',format='png'))
        self.posts=[];self.drop_post=False;self.lose_post=False
        domain=self
        class Transport(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                if path=='/runs/'+RUN+'/phase':
                    need(value is None and phase_nonce is not None);return domain.journal.phase(RUN,phase_nonce)
                if path=='/runs/'+RUN:
                    need(value is None);return domain.journal.snapshot(RUN)
                need(path=='/runs/'+RUN+'/samples'and self.token=='a'*64 and type(value)is dict)
                domain.posts.append(deepcopy(value))
                if not domain.drop_post:domain.journal.publish(RUN,value)
                if domain.lose_post:
                    domain.lose_post=False;raise OSError('Real Journal accepted sample; modeled transport return lost')
                return {}
        def client(actor=False):
            return Transport('https://controlled.invalid/feature-fixture/v1',('a'if actor else'r')*64,
                monotonic=self.primary.capture.mono,sleep=self.primary.capture.sleep)
        self.client=client;self.actor_client=client(True)
        self.primary.capture.client=lambda:client(False)
        base=type(self.primary.runtime)
        class Primary(IOSSnapshotSceneCanonicalRuntime,base):pass
        self.primary.runtime=Primary(self.primary.runtime.adapter)
        base_actor=type(self.actor_runtime)
        class Actor(IOSSnapshotSceneCanonicalRuntime,base_actor):pass
        self.actor_runtime=Actor(self.actor_runtime.adapter)

    def owner(self):
        d=self.primary
        return d.runtime.published_scene_capture_order('primary',self.actor_runtime,'actor',RUN,self.client(),self.actor_client,
            epoch_ms=d.capture.epoch,monotonic=d.capture.mono,sleep=d.capture.sleep)

    def independent(self):
        return self.actor_runtime.scene_actor_publications('actor',RUN,self.actor_client,
            epoch_ms=self.primary.capture.epoch,monotonic=self.primary.capture.mono)
