//
//  Created by Bradley Austin Davis on 2017-01-11
//  Copyright 2013-2017 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//
#pragma once
#ifndef hifi_OffscreenQmlSurfaceCache_h
#define hifi_OffscreenQmlSurfaceCahce_h

#include "DependencyManager.h"

#include <QtCore/QSharedPointer>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include "IOSWebSurfaceOwnership.h"
#endif

class QQmlContext;
class OffscreenQmlSurface;

class OffscreenQmlSurfaceCache : public Dependency {
    SINGLETON_DEPENDENCY

public:
    OffscreenQmlSurfaceCache();
    virtual ~OffscreenQmlSurfaceCache();

    QSharedPointer<OffscreenQmlSurface> acquire(const QString& rootSource);
    void release(const QString& rootSource, const QSharedPointer<OffscreenQmlSurface>& surface);
    void reserve(const QString& rootSource, int count = 1);
    void setOnRootContextCreated(const std::function<void(const QString& rootSource, QQmlContext* rootContext)> & onRootContextCreated);

#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
    // Passive source only; no dependency/session/cache allocation is performed.
    QVariantMap featureWebSurfaceOwnership() const { return _featureWebSurfaces.read(); }
    void featureWebRendererLease(const QSharedPointer<OffscreenQmlSurface>& surface,const QSharedPointer<int>& lease,
        const QString& entity,const QString& source) { _featureWebSurfaces.rendererLease(surface,lease,entity,source); }
#endif

private:
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
    overte::ios::IOSWebSurfaceOwnership _featureWebSurfaces;
#endif
    QSharedPointer<OffscreenQmlSurface> buildSurface(const QString& rootSource);
    QHash<QString, QList<QSharedPointer<OffscreenQmlSurface>>> _cache;
    std::function<void(const QString& rootSource, QQmlContext* rootContext)> _onRootContextCreated;
};

#endif
