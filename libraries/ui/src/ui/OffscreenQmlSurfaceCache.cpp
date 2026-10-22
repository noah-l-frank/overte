//
//  Created by Bradley Austin Davis on 2017-01-11
//  Copyright 2013-2017 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//
#include "OffscreenQmlSurfaceCache.h"

#include <QtGui/QOpenGLContext>
#include <QtQml/QQmlContext>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include <QtQuick/QQuickItem>
#endif

#include <PathUtils.h>
#include "OffscreenQmlSurface.h"
#include "Profile.h"

OffscreenQmlSurfaceCache::OffscreenQmlSurfaceCache() {
}

OffscreenQmlSurfaceCache::~OffscreenQmlSurfaceCache() {
    _cache.clear();
}

QSharedPointer<OffscreenQmlSurface> OffscreenQmlSurfaceCache::acquire(const QString& rootSource) {
    auto& list = _cache[rootSource];
    if (list.empty()) {
        list.push_back(buildSurface(rootSource));
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
        _featureWebSurfaces.cached(list.back(),"reserved");
#endif
    }
    auto result = list.front();
    list.pop_front();
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
    _featureWebSurfaces.acquired(result);
#endif
    return result;
}

void OffscreenQmlSurfaceCache::reserve(const QString& rootSource, int count) {
    auto& list = _cache[rootSource];
    while (list.size() < count) {
        list.push_back(buildSurface(rootSource));
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
        _featureWebSurfaces.cached(list.back(),"reserved");
#endif
    }
}

void OffscreenQmlSurfaceCache::release(const QString& rootSource, const QSharedPointer<OffscreenQmlSurface>& surface) {
    PROFILE_RANGE(app, "buildSurface");
    surface->pause();
    _cache[rootSource].push_back(surface);
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
    _featureWebSurfaces.cached(surface,"released");
#endif
}

QSharedPointer<OffscreenQmlSurface> OffscreenQmlSurfaceCache::buildSurface(const QString& rootSource) {
    auto surface = QSharedPointer<OffscreenQmlSurface>::create();
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
    _featureWebSurfaces.built(rootSource,surface);
    const auto featureRoot = _featureWebSurfaces.rootCallback(surface);
    if (featureRoot) {
        QObject::connect(surface.data(), &hifi::qml::OffscreenSurface::rootItemCreated, QCoreApplication::instance(),
            [featureRoot](QQuickItem* root) { featureRoot(root); }, Qt::DirectConnection);
    }
#endif

    QObject::connect(surface.data(), &hifi::qml::OffscreenSurface::rootContextCreated, [this, rootSource](QQmlContext* surfaceContext) {
        if (_onRootContextCreated) {
            _onRootContextCreated(rootSource, surfaceContext);
        }
    });

    surface->load(rootSource);
    surface->resize(QSize(100, 100));
    return surface;
}

void OffscreenQmlSurfaceCache::setOnRootContextCreated(const std::function<void(const QString& rootSource, QQmlContext* rootContext)>& onRootContextCreated) {
    _onRootContextCreated = onRootContextCreated;
}