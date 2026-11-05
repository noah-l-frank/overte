"""Cold authenticated real loopback roles with existing normal Audio fixture."""
from copy import deepcopy
import time
from unittest.mock import patch
from adapters.host_process_identity import host_identity
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1
from self_tests import test_pico_audio_bundle_acquisition as bundle_fixture
from self_tests import test_pico_audio_pc_start as pc_fixture
from self_tests.pico_audio_authenticated_recipe_fixture import AuthenticatedAudioRecipeFixture
OriginalPC=pc_fixture.AudioPCStartTests
class ColdPC(OriginalPC):
    recipe_fixture=AuthenticatedAudioRecipeFixture
    def create_cleanup_budget(self):
        started=time.monotonic()
        self.budget=AudioCleanupBudget1(dict(picoAudioCleanupProfileVersion=3,quietPollingProfile='work-inclusive-450ms',
            cleanupWorkspacePolicy='book-before-cleanup-constructor',
            runId=self.f.run,binding=deepcopy(self.f.native.binding),hostProcessIdentity=host_identity(),
            startedMonotonic=started,deadlineMonotonic=started+120),self.f.native.lock)
        return self.budget
# Existing fixture's only transport model change is its Actor Client. A real
# Client is selected before original Actor/Source construction, never rebound.
class AuthBundleFixture(bundle_fixture.AudioBundleAcquisitionTests):
    def setUp(self):
        from feature_journeys.witness import Client
        from feature_journeys.phase_fixture import PhaseFixtureReader
        original_actor=bundle_fixture.PicoAudioPCActor
        def cold_actor(recipe,source,*args,**kwargs):
            clock=self.fixture.f.native.phase_clock
            real_source=PhaseFixtureReader(Client(source.client.url,source.client.token),source.run,'audio',
                monotonic=clock.monotonic,epoch_ms=clock.epoch)
            return original_actor(recipe,real_source,*args,**kwargs)
        with patch.object(pc_fixture,'AudioPCStartTests',ColdPC),patch.object(bundle_fixture,'PicoAudioPCActor',side_effect=cold_actor):
            super().setUp()
