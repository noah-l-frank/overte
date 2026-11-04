// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QImage>
#include <QVariantMap>
#include <QtGlobal>

namespace gpu {
// Observation only. The ordinary OpenGL consumer owns this exact frame and
// invokes the ordinary callback once; no other screenshot can create a scope.
// Definitions live in Frame.cpp, so all consumers use one TLS implementation.
class FeatureSnapshotProvenance {
public:
    static bool enabled();
    static bool sceneEnabled();
    // Separate default-off observation of THIS held Actor frame, never a
    // Primary capture or WDA screen. Callback QImage dies before commit.
    static bool actorPixelsEnabled();
    static bool beginActorPixelReadback(const QVariantMap& frame,quint32 index,bool mono);
    static QVariantMap actorPixelReadback(const QImage& callbackImage);
    static void commitActorPixelReadback(const QVariantMap& record);
    static QVariantMap actorPixelOriginal();
    // The same recorded frame carries these observed render-entry inputs.
    static void entityInput(QVariantMap& frame,const QVariantMap& actual,bool returned);
    static void consumedScene(const QVariantMap& frame,quint32 index,bool mono);
    static QVariantMap sceneOriginal();
    class Scope {
    public:
        Scope(const QVariantMap& frame,quint32 index,bool mono);
        ~Scope();
        Scope(const Scope&)=delete;
        Scope& operator=(const Scope&)=delete;
    private:
        friend class FeatureSnapshotProvenance;
        Scope* _previous {nullptr};
        QVariantMap _frame;
        bool _read {false},_valid {false};
    };
    static void readback(int sourceWidth,int sourceHeight,int x,int y,int width,int height,const QImage& bottomUp);
    static QVariantMap original(const QImage& callbackImage);
private:
    static Scope*& current();
    static QByteArray pixelHash(const QImage& image);
};
} // namespace gpu
#endif
