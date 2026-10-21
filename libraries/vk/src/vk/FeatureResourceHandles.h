// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include <shared/IOSFeatureImageTrace.h>
#include <map>
#include <utility>

namespace vks {
// The caller holds the existing recycler mutex. No native object is retained.
// Its original successful creation and actual destroy/free own these leases.
template<typename Handle> class FeatureResourceHandles final {
public:
    ~FeatureResourceHandles() {
        for (const auto& [handle, row] : _live) { invalid(row.scopes); }
    }
    void created(Handle handle, const overte::ios::feature_images::Scopes& scopes, const QString& kind) {
        if (scopes.empty()) { return; }
        if (!handle || _live.size() >= 4096) { invalid(scopes); return; }
        const auto found = _live.find(handle);
        if (found != _live.end()) { invalid(found->second.scopes); invalid(scopes); return; }
        auto leases = overte::ios::feature_images::retain(scopes, kind);
        if (leases.size() != scopes.size()) { invalid(scopes); return; }
        _live.emplace(handle, Row { scopes, std::move(leases) });
    }
    void retired(Handle handle) { _live.erase(handle); }
private:
    using Scopes = overte::ios::feature_images::Scopes;
    struct Row { Scopes scopes; overte::ios::feature_images::Leases leases; };
    static void invalid(const Scopes& scopes) { for (const auto& scope : scopes) { scope.invalidate(); } }
    std::map<Handle, Row> _live;
};
} // namespace vks
#endif
