// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Original Offscreen loader/TabletProxy bodies are compiled below. GPU surface
// allocation, sound, local-script policy and the standard controller channel
// are explicit host endpoints; none can fabricate object retirement.
#include <QQmlAbstractUrlInterceptor>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QLoggingCategory>
#include <QJSValue>
#include <QFile>
#include <functional>
#include <memory>
#include "libraries/qml/src/qml/FeatureQmlLoads.h"
#define PROFILE_RANGE_EX(...)
#define PROFILE_RANGE(...)
#ifndef BLOCKING_INVOKE_METHOD
#define BLOCKING_INVOKE_METHOD(object,name,...) QMetaObject::invokeMethod(object,name,Qt::BlockingQueuedConnection,__VA_ARGS__)
#endif
Q_DECLARE_LOGGING_CATEGORY(qmlLogging)
namespace hifi::scripting {
inline bool isLocalAccessSafeThread(){return false;}
inline void setLocalAccessSafeThread(bool){}
}
struct ContextAwareProfile {static void restrictContext(QQmlContext*,bool){qFatal("Unavailable local-policy branch");}};
struct FileTypeProfile {static void registerWithContext(QQmlContext*){qFatal("Unavailable local-policy branch");}};
struct HFWebEngineProfile {static void registerWithContext(QQmlContext*){qFatal("Unavailable web-profile branch");}};
namespace hifi::qml {
using QmlContextObjectCallback=std::function<void(QQmlContext*,QQuickItem*)>;
using QmlContextCallback=std::function<void(QQmlContext*)>;
using QmlUrlValidator=std::function<bool(const QUrl&)>;
struct HostSharedObject {
    QList<QPointer<QObject>> _deletionList;
    void addToDeletionList(QObject*);
    void create(QObject*){qFatal("Root surface allocation is an unavailable host endpoint");}
    void setObjectName(const QString&){qFatal("Root surface allocation is an unavailable host endpoint");}
    void setRootItem(QQuickItem*){qFatal("Root replacement is an unavailable host endpoint");}
};
class OffscreenSurface:public QObject {
    Q_OBJECT
public:
    QQmlEngine* engine;QQuickItem* root{nullptr};HostSharedObject shared;
    HostSharedObject* _sharedObject{&shared};
    std::shared_ptr<FeatureQmlLoads> _featureQmlLoads{std::make_shared<FeatureQmlLoads>()};
    explicit OffscreenSurface(QQmlEngine* engine):engine(engine){}
    QQuickItem* getRootItem(){return root;}QQmlContext* getSurfaceContext(){return engine->rootContext();}
    void onItemCreated(QQmlContext*,QQuickItem*){} // unrelated event-bridge/audio services
    void onRootCreated(){qFatal("Root replacement is an unavailable host endpoint");}
    static QmlUrlValidator validator;
    static const QmlContextCallback DEFAULT_CONTEXT_CALLBACK;
    void loadInternal(const QUrl&,bool,QQuickItem*,const QmlContextObjectCallback&,const QmlContextCallback& = DEFAULT_CONTEXT_CALLBACK);
    void finishQmlLoad(QQmlComponent*,QQmlContext*,QQuickItem*,const QmlContextObjectCallback&);
    QQmlContext* contextForUrl(const QUrl&,QQuickItem*,bool);
signals:
    void qmlLoadFailed(QQuickItem*,int);void fromQml(QVariant);void rootItemCreated(QQuickItem*);
};
}
class HostSurfaceLoader:public hifi::qml::OffscreenSurface {
    Q_OBJECT
public:
    using hifi::qml::OffscreenSurface::OffscreenSurface;
    Q_INVOKABLE void load(const QUrl&,QQuickItem*,const QJSValue&);
};
struct HostDesktopWindow {QQuickItem* asQuickItem(){qFatal("Desktop window is an unavailable host endpoint");return nullptr;}};
class TabletProxy:public QObject {
    Q_OBJECT
    Q_PROPERTY(bool tabletShown READ shown)
public:
    enum class State {Uninitialized,Home,QML};State _state{State::QML};
    bool _toolbarMode{false};QQuickItem* _qmlTabletRoot{nullptr};HostDesktopWindow* _desktopWindow{nullptr};QVariant _currentPathLoaded;
    bool shown()const{return _qmlTabletRoot && _qmlTabletRoot->isVisible();}
    Q_INVOKABLE void gotoHomeScreen();Q_INVOKABLE bool onHomeScreen();Q_INVOKABLE void loadHomeScreen(bool);
    void loadQMLSourceImpl(const QVariant&,bool,bool);
    void stopQMLSource(){qFatal("Desktop window is an unavailable host endpoint");}
};
class HostPicoStandardChannel:public QObject {
    Q_OBJECT
public:
    QJSValue callback;int edges{0};bool held{false};
    Q_INVOKABLE void install(const QJSValue& value){if(callback.isCallable() || !value.isCallable())qFatal("Foreign controller mapping");callback=value;}
    bool publish(bool pressed){if(!callback.isCallable())return false;++edges;held=pressed;return !callback.call({QJSValue(pressed)}).isError();}
};
class HostUnrelatedQml:public QQmlAbstractUrlInterceptor {
public:
    QUrl empty;
    explicit HostUnrelatedQml(const QUrl& empty):empty(empty){}
    QUrl intercept(const QUrl& url,DataType type) override {
        if(type==QQmlAbstractUrlInterceptor::QmlFile && (url.path().endsWith("/dialogs/TabletQueryDialog.qml")
                || url.path().endsWith("/dialogs/TabletMessageBox.qml") || url.path().endsWith("/hifi/tablet/TabletHome.qml")))return empty;
        return url;
    }
};
