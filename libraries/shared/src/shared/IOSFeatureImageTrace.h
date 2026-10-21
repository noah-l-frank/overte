// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include <QImage>
#include <QColorSpace>
#include <QString>
#include <QStringList>
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
inline bool sameMetadata(const QImage& original, const QImage& carrier) {
    return original.devicePixelRatio() == carrier.devicePixelRatio()
        && original.dotsPerMeterX() == carrier.dotsPerMeterX() && original.dotsPerMeterY() == carrier.dotsPerMeterY()
        && original.offset() == carrier.offset() && original.colorSpace() == carrier.colorSpace()
        && original.colorTable() == carrier.colorTable() && original.textKeys().isEmpty() && carrier.textKeys().isEmpty();
}
Scopes sources(const QImage& image);
Leases retain(const Scopes& scopes, const QString& kind);
QImage image(const QImage& original, const Scopes& scopes, const QString& kind);
void painted(const Scope& scope);
// Original command-buffer reference ownership. Only the existing successful
// matching submission fence can qualify completion; last ticket copies drain.
class Submission final {
public:
    Submission();
    ~Submission();
    Submission(const Submission&) = delete;
    Submission& operator=(const Submission&) = delete;
    void add(const Scopes& scopes);
    void submit(bool success);
    void finish(bool success);
private:
    struct Private;
    std::unique_ptr<Private> _private;
};
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
