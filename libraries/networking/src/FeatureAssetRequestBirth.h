// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
class AssetResourceRequest;
namespace overte::e2e {
// Optional weakly held passive binding. Implementations must observe actual
// originals only and must not start, finish, cancel or retain a request.
class FeatureAssetRequestBirth {
public:
    virtual ~FeatureAssetRequestBirth() = default;
    virtual void observe(AssetResourceRequest* original) = 0;
};
}
#endif
