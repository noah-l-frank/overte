// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSFeatureImageTrace.h"
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include <algorithm>
#include <atomic>
#include <map>
#include <mutex>

namespace overte::ios::feature_images {
namespace {
constexpr std::size_t MAX_IMAGES = 4096, MAX_SCOPES = 1024;
struct Row { Scopes scopes; QString kind; };
struct State { std::mutex mutex; std::map<qint64, Row> images; };
// One shared-library registry, also used by the Web and renderer libraries.
// Original carrier destruction, including process shutdown, owns its removal.
State& state() { static State* data = new State; return *data; }
thread_local Scopes* currentFrame = nullptr;
thread_local bool* currentPainted = nullptr;
void invalid(const Scopes& scopes) { for (const auto& scope : scopes) { if (scope.invalidate) { scope.invalidate(); } } }
bool merge(Scopes& output, const Scopes& input) {
    for (const auto& scope : input) {
        if (scope.id.isEmpty() || !scope.retain || !scope.invalidate) { invalid(input); return false; }
        if (std::none_of(output.begin(), output.end(), [&](const auto& old) { return old.id == scope.id; })) {
            if (output.size() >= MAX_SCOPES) { invalid(output); invalid(input); return false; }
            output.push_back(scope);
        }
    }
    return true;
}
struct Owner {
    std::shared_ptr<std::atomic<bool>> cleaned;
    Scopes scopes;
    Leases leases;
    qint64 key { 0 };
    bool registered { false };
    QImage original;
    ~Owner() {
        original = {}; // Drop the actual original implicit copy first.
        if (registered) { auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex); data.images.erase(key); }
        // Actual original reference and provenance registry retire before leases.
    }
};
}
Scopes sources(const QImage& image) {
    if (image.isNull()) { return {}; }
    auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex);
    const auto found = data.images.find(image.cacheKey());
    return found == data.images.end() ? Scopes() : found->second.scopes;
}
Leases retain(const Scopes& scopes, const QString& kind) {
    Leases result;
    for (const auto& scope : scopes) {
        auto lease = scope.retain ? scope.retain(kind) : nullptr;
        if (!lease) { invalid(scopes); return {}; }
        result.push_back(std::move(lease));
    }
    return result;
}
QImage image(const QImage& original, const Scopes& requested, const QString& kind) {
    if (original.isNull() || requested.empty()) { return original; }
    Scopes scopes = sources(original); if (!merge(scopes, requested)) { return original; }
    {
        auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex);
        const auto found = data.images.find(original.cacheKey());
        if (found != data.images.end() && found->second.kind == kind && found->second.scopes.size() == scopes.size()) { return original; }
        if (data.images.size() >= MAX_IMAGES) { invalid(scopes); return original; }
    }
    auto leases = retain(scopes, kind);
    if (leases.size() != scopes.size()) { return original; }
    const auto cleaned = std::make_shared<std::atomic<bool>>(false);
    auto* owner = new Owner { cleaned, scopes, std::move(leases), 0, false, original };
    {
        QImage carrier(original.constBits(), original.width(), original.height(), original.bytesPerLine(), original.format(),
            [](void* pointer) { auto* owner = static_cast<Owner*>(pointer); owner->cleaned->store(true); delete owner; }, owner);
        if (!carrier.isNull()) {
            owner->key = carrier.cacheKey();
            auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex);
            if (data.images.size() < MAX_IMAGES && data.images.emplace(owner->key, Row { scopes, kind }).second) {
                owner->registered = true; return carrier;
            }
            invalid(scopes);
        }
    }
    if (!cleaned->load()) { delete owner; }
    invalid(scopes); return original;
}
void painted(const Scope& scope) {
    if (currentFrame && currentPainted) { *currentPainted = true; merge(*currentFrame, Scopes { scope }); }
    else if (scope.invalidate) { scope.invalidate(); } // An untraced paint cannot become complete lifetime coverage.
}
struct Submission::Private {
    std::mutex mutex;
    Scopes scopes;
    Leases leases;
    bool submitted { false }, completed { false }, valid { true };
};
Submission::Submission() : _private(std::make_unique<Private>()) {}
Submission::~Submission() {
    // Releasing an unknown or failed ticket never restores source completeness.
    if (!_private->valid || !_private->submitted || !_private->completed) { invalid(_private->scopes); }
}
void Submission::add(const Scopes& scopes) {
    std::lock_guard<std::mutex> guard(_private->mutex);
    if (!_private->valid || _private->submitted || _private->completed) { invalid(scopes); invalid(_private->scopes); _private->valid = false; return; }
    const auto before = _private->scopes.size();
    if (!merge(_private->scopes, scopes)) { _private->valid = false; return; }
    Scopes added(_private->scopes.begin() + before, _private->scopes.end());
    auto leases = retain(added, QStringLiteral("vulkan-submission"));
    if (leases.size() != added.size()) { invalid(_private->scopes); _private->valid = false; return; }
    _private->leases.insert(_private->leases.end(), leases.begin(), leases.end());
}
void Submission::submit(bool success) {
    std::lock_guard<std::mutex> guard(_private->mutex);
    if (!_private->valid || _private->submitted || _private->completed || !success) {
        invalid(_private->scopes); _private->valid = false; return;
    }
    _private->submitted = true;
}
void Submission::finish(bool success) {
    std::lock_guard<std::mutex> guard(_private->mutex);
    if (!_private->valid || !_private->submitted || _private->completed || !success) {
        invalid(_private->scopes); _private->valid = false; return;
    }
    _private->completed = true;
    // Keep leases through actual callback/FrameData copies, after fence success.
}
struct PaintFrame::Private {
    Scopes scopes; Scopes* previous { nullptr }; bool* previousPainted { nullptr };
    bool finished { false }, painted { false };
};
PaintFrame::PaintFrame(const QImage& original) : _private(std::make_unique<Private>()) {
    _private->scopes = sources(original); _private->previous = currentFrame; _private->previousPainted = currentPainted;
    currentFrame = &_private->scopes; currentPainted = &_private->painted;
}
PaintFrame::~PaintFrame() {
    if (!_private->finished && _private->painted && !_private->scopes.empty()) { invalid(_private->scopes); }
    currentFrame = _private->previous; currentPainted = _private->previousPainted;
}
void PaintFrame::finish(QImage& original) {
    if (_private->finished || currentFrame != &_private->scopes) { invalid(_private->scopes); return; }
    _private->finished = true;
    // Preserve the union of actual painted sources until the allocation's last
    // implicit copy dies. Dirty-region rendering is not a full-clear receipt.
    original = image(original, _private->scopes, QStringLiteral("offscreen-image"));
}
} // namespace overte::ios::feature_images
#endif
