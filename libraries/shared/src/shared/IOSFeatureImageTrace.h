// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include <QImage>
#include <QString>
#include <functional>
#include <memory>
#include <vector>

namespace overte::ios::feature_images {
// Opaque factories retain only original source metadata until actual ownership
// begins. The native producer remains the authority for counters and epochs.
struct Scope {
    QString id;
    std::function<std::shared_ptr<void>(const QString&)> retain;
    std::function<void()> invalidate;
};
using Scopes = std::vector<Scope>;
using Leases = std::vector<std::shared_ptr<void>>;
Scopes sources(const QImage& image);
Leases retain(const Scopes& scopes, const QString& kind);
QImage image(const QImage& original, const Scopes& scopes, const QString& kind);
void painted(const Scope& scope);
class PaintFrame final {
public:
    explicit PaintFrame(const QImage& original);
    ~PaintFrame();
    PaintFrame(const PaintFrame&) = delete;
    PaintFrame& operator=(const PaintFrame&) = delete;
    void finish(QImage& original);
private:
    struct Private;
    std::unique_ptr<Private> _private;
};
} // namespace overte::ios::feature_images
#endif
