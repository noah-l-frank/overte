// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Native graphics/setting endpoints are fixtures; the full page and its controls
// execute unchanged. The actual native capability getter is tested separately.
#include <QtQuickTest/quicktest.h>
#include <QQmlEngine>
#include <QQmlContext>
#include <QQmlPropertyMap>
class RenderBoundary : public QQmlPropertyMap {
    Q_OBJECT
public:
    RenderBoundary() : QQmlPropertyMap(this, nullptr) {
        for(const auto& name:{"deferredRenderingAvailable","shadowsEnabled","hazeEnabled","bloomEnabled","ambientOcclusionEnabled","localLightingEnabled","proceduralMaterialsEnabled","mirrorsEnabled"})insert(name,true);
        insert("renderMethod",1);insert("antialiasingMode",0);insert("viewportResolutionScale",1.0);insert("verticalFieldOfView",60.0);insert("cameraClippingEnabled",false);
    }
    Q_INVOKABLE QStringList getScreens(){return {"Screen"};}
    Q_INVOKABLE QString getFullScreenScreen(){return "Screen";}
    Q_INVOKABLE void setFullScreenScreen(const QString&){}
    Q_INVOKABLE void useDeferred(bool available){insert("deferredRenderingAvailable",available);}
};
class PerformanceBoundary : public QObject {
    Q_OBJECT
public:
    Q_INVOKABLE int getPerformancePreset(){return 5;}
    Q_INVOKABLE void setPerformancePreset(int){}
    Q_INVOKABLE int getRefreshRateProfile(){return 0;}
    Q_INVOKABLE void setRefreshRateProfile(int){}
    Q_INVOKABLE int getCustomRefreshRate(int){return 60;}
    Q_INVOKABLE void setCustomRefreshRate(int,int){}
};
class SettingsBoundary : public QObject {
    Q_OBJECT
public:
    Q_INVOKABLE QVariant getValue(const QString&,const QVariant& fallback){return fallback;}
};
class Setup : public QObject {
    Q_OBJECT
    RenderBoundary render;
    PerformanceBoundary performance;
    SettingsBoundary settings;
    QQmlPropertyMap lod,header;
public slots:
    void qmlEngineAvailable(QQmlEngine* engine){
        lod.insert("worldDetailQuality",1);header.insert("height",0);
        auto* c=engine->rootContext();
        c->setContextProperty("Render",&render);c->setContextProperty("Performance",&performance);
        c->setContextProperty("Settings",&settings);c->setContextProperty("LODManager",&lod);
        c->setContextProperty("header",&header);c->setContextProperty("currentPage","Graphics");
    }
};
QUICK_TEST_MAIN_WITH_SETUP(GraphicsSettings, Setup)
#include "graphics-settings-services.moc"
