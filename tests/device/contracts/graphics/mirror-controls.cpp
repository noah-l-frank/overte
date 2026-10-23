// Copyright 2026 Overte e.V.
// SPDX-License-Identifier: Apache-2.0
// @...@ sections are unchanged production code, filled by the focused driver.
#include <QGuiApplication>
#include <QQuickItem>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlFileSelector>
#include <QFileSelector>
#include <QSettings>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QRegularExpression>
#include <QStringList>
#include <algorithm>
#include <chrono>
#include <list>
#include <memory>
#include <iostream>
#include <cassert>
#ifdef HOST_ANDROID
#define Q_OS_ANDROID
#endif
QSettings* store;
namespace Setting {
template<class T> struct Handle {
    QString key; T fallback;
    Handle(QString name, T value):key(name),fallback(value) {}
    T get() const { return store->value(key,QVariant::fromValue(fallback)).template value<T>(); }
    void set(T value) { store->setValue(key,QVariant::fromValue(value)); }
};
}
// JSON serialization and GPU job refresh are not part of mirror control lookup.
QJsonValue toJsonValue(const QObject&) { return {}; }
void qObjectFromJsonValue(const QJsonValue&,QObject&) {}
namespace task {
class JobConcept;
template<class C> class PersistentConfig;
class JobConfig;
struct TConfigProxy { using Config=JobConfig; };
@JOB_CLASS@
JobConfig::~JobConfig()=default;
void JobConfig::refresh() {}
void JobConfig::setPresetList(const QJsonObject&) {}
void JobConfig::connectChildConfig(std::shared_ptr<JobConfig>,const std::string&) {}
void JobConfig::transferChildrenConfigs(std::shared_ptr<JobConfig>) {}
void JobConfig::setBranch(uint8_t b) { _branch=b; }
@JOB_METHODS@
}
struct Lock {
    template<class F> void withReadLock(F f) { f(); }
    template<class F> void withWriteLock(F f) { f(); }
};
struct AntialiasingSetupConfig { enum Mode { NONE }; };
namespace render { struct Args { enum RenderMethod { DEFERRED,FORWARD }; }; }
constexpr bool RENDER_FORWARD=false;
struct RenderMirrorTask { static constexpr size_t MAX_MIRRORS_PER_LEVEL=@MIRROR_COUNT@; };
struct RenderConfig : task::JobConfig {
    QObject* getConfig(const QString& name) { return getJobConfig(name.toStdString()); }
};
struct Engine { RenderConfig* configuration{}; RenderConfig* getConfiguration() { return configuration; } };
struct App { Engine engine;Engine* getRenderEngine() { return &engine; } };
#undef qApp
App* qApp;
class RenderScriptingInterface : public QObject {
    Q_OBJECT
@PROPERTY@
@CAPABILITY_PROPERTY@
    // Remaining behaviors are explicit UI boundaries. Their shared notification
    // signal matches the production properties so live QML bindings stay valid.
    Q_PROPERTY(bool localLightingEnabled MEMBER _localLightingEnabled NOTIFY settingsChanged)
    Q_PROPERTY(bool proceduralMaterialsEnabled MEMBER _proceduralMaterialsEnabled NOTIFY settingsChanged)
    Q_PROPERTY(bool bloomEnabled MEMBER _bloomEnabled NOTIFY settingsChanged)
    Q_PROPERTY(bool shadowsEnabled MEMBER _shadowsEnabled NOTIFY settingsChanged)
    Q_PROPERTY(bool ambientOcclusionEnabled MEMBER _ambientOcclusionEnabled NOTIFY settingsChanged)
    Q_PROPERTY(bool hazeEnabled MEMBER _hazeEnabled NOTIFY settingsChanged)
    Q_PROPERTY(int renderMethod MEMBER _renderMethod NOTIFY settingsChanged)
    Q_PROPERTY(int antialiasingMode MEMBER _antialiasingMode NOTIFY settingsChanged)
    Q_PROPERTY(float viewportResolutionScale MEMBER _viewportResolutionScale NOTIFY settingsChanged)
    Q_PROPERTY(float verticalFieldOfView MEMBER fieldOfView NOTIFY settingsChanged)
    Q_PROPERTY(bool cameraClippingEnabled MEMBER cameraClipping NOTIFY settingsChanged)
public:
    Lock _renderSettingLock;
    int _renderMethod{0};bool _localLightingEnabled{true},_proceduralMaterialsEnabled{true};
    bool _bloomEnabled{},_shadowsEnabled{},_ambientOcclusionEnabled{},_hazeEnabled{true};
    int _antialiasingMode{0};float _viewportResolutionScale{0.8f},fieldOfView{60};bool cameraClipping{true};QString _fullScreenScreen;
@RUNTIME@
@PERSISTENCE_MEMBER@
@SETTINGS@
    void loadSettings();bool getMirrorsEnabled() const;void setMirrorsEnabled(bool);void forceMirrorsEnabled(bool);
    bool isDeferredRenderingAvailable() const;
    enum RenderMethod { DEFERRED,FORWARD };
    QStringList getScreens() const { return {"Default"}; }
    void setFullScreenScreen(const QString& value) { _fullScreenScreen=value; }
    Q_INVOKABLE QString getFullScreenScreen() const { return "Default"; }
    Q_INVOKABLE void setFullScreenScreen(const QVariant&) {}
    Q_INVOKABLE QVariantList getScreens() { return {"Default"}; }
    void forceRenderMethod(RenderMethod) {}void forceShadowsEnabled(bool) {}void forceHazeEnabled(bool) {}
    void forceBloomEnabled(bool) {}void forceAmbientOcclusionEnabled(bool) {}void forceLocalLightingEnabled(bool) {}
    void forceProceduralMaterialsEnabled(bool) {}void forceAntialiasingMode(int) {}void forceViewportResolutionScale(float) {}
signals:
    void settingsChanged();
};
@METHODS@
// Production render graph registration names/branches are checked by the driver.
// Use real JobConfig/QObject hierarchy and unchanged production path lookup.
task::JobConfig* add(task::JobConfig* root,const QString& path) {
    auto segments=path.split('.');task::JobConfig* current=root;
    for(const auto& name:segments) {
        auto next=current->findChild<task::JobConfig*>(name,Qt::FindDirectChildrenOnly);
        if(!next) { next=new task::JobConfig(true);next->setParent(current);next->setObjectName(name); }
        current=next;
    }
    return current;
}
void graph(RenderConfig& root) {
    for(const auto& view:QStringList{"RenderMainView","RenderSecondView"}) {
#ifdef Q_OS_ANDROID
        const QStringList paths{".RenderForwardTask"};
#else
        const QStringList paths{".DeferredForwardSwitch.RenderShadowsAndDeferredTask.RenderDeferredTask",".DeferredForwardSwitch.RenderForwardTask"};
#endif
        add(&root,view+".UnrelatedPass");
#if HOST_HAS_MIRRORS
        for(const auto& path:paths) for(size_t i=0;i<RenderMirrorTask::MAX_MIRRORS_PER_LEVEL;++i) {
            auto base=view+path+".RenderMirrorTask"+QString::number(i)+"Depth0";
            add(&root,base+".RenderMirrorView"+QString::number(i)+"Depth0");
        }
#endif
    }
}
bool allMatch(RenderConfig& root,bool enabled) {
    for(auto job:root.findChildren<task::JobConfig*>()) if(job->objectName().startsWith("RenderMirror") && job->isEnabled()!=enabled) return false;
    return true;
}
QObject* api(QQmlEngine& engine,const QByteArray& source) {
    QQmlComponent c(&engine);c.setData(source,QUrl());auto object=c.create();assert(object);return object;
}
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);assert(argc==4);QSettings settings(argv[1],QSettings::IniFormat);store=&settings;
    App application;qApp=&application;RenderConfig config;graph(config);application.engine.configuration=&config;
    const QString action=argv[2];const QString root=argv[3];
    if(action=="legacy") {
#ifdef ANDROID_APP_PHONE_INTERFACE
        settings.setValue("phone/graphics/mirrors",false);
#else
        settings.setValue("mirrorsEnabled",false);
#endif
    }
    RenderScriptingInterface render;render.loadSettings();bool safe=true;QJsonObject out;
    if(action=="true" || action=="false") render.setMirrorsEnabled(action=="true");
    if(action=="reapply") {
        render.setMirrorsEnabled(true);
        for(auto job:config.findChildren<task::JobConfig*>()) if(job->objectName().startsWith("RenderMirror")) job->setEnabled(false);
        render.setMirrorsEnabled(true);safe=allMatch(config,true);
    }
    if(action=="missing") {
        application.engine.configuration=nullptr;render.setMirrorsEnabled(false);render.setMirrorsEnabled(true);
        application.engine.configuration=&config;render.setMirrorsEnabled(true);
    }
    if(action=="replace") {
        render.setMirrorsEnabled(false);RenderConfig replacement;graph(replacement);application.engine.configuration=&replacement;
        render.setMirrorsEnabled(true);safe=allMatch(replacement,true)&&allMatch(config,false);
        application.engine.configuration=&config;render.setMirrorsEnabled(true);
    }
    if(action=="bad") {
        QObject unrelated;unrelated.setParent(&config);unrelated.setObjectName("RenderMirrorTask0Depth0");
        render.setMirrorsEnabled(false);render.setMirrorsEnabled(true);safe=!unrelated.property("enabled").isValid();
        unrelated.setParent(nullptr);
    }
    if(action=="qml") {
        QQmlEngine engine;engine.addImportPath(root+"/interface/resources/qml");
        qmlRegisterModule("TabletScriptingInterface",1,0);qmlRegisterModule("PerformanceEnums",1,0);
        auto metrics=api(engine,R"(import QtQml 2.15; QtObject { property real safeInsetLeft: 0;property real safeInsetTop: 0;property real safeInsetRight: 0;property real safeInsetBottom: 0;property real imeInsetBottom: 0;property bool keyboardVisible: false;property real surfaceWidth: 1024;property real surfaceHeight: 768;property real density: 1;property real fontScale: 1 })");
        qmlRegisterSingletonInstance("OverteIOS",1,0,"IOSTouchUiMetrics",metrics);
        QQmlFileSelector selector(&engine);
        selector.setExtraSelectors(qEnvironmentVariable("OVERTE_MIRROR_QML_SELECTORS").split(',',Qt::SkipEmptyParts));
        out["selected_qml"]=selector.selector()->select(root+"/scripts/system/settings/qml/pages/GraphicsSettings.qml");
        engine.rootContext()->setContextProperty("Render",&render);
        engine.rootContext()->setContextProperty("Tablet",api(engine,R"(import QtQml 2.15; QtObject { function playSound(x) {} })"));
        engine.rootContext()->setContextProperty("TabletEnums",api(engine,R"(import QtQml 2.15; QtObject { property int buttonClicked: 0 })"));
        engine.rootContext()->setContextProperty("Performance",api(engine,R"(import QtQml 2.15; QtObject { function getPerformancePreset(){return 5}function setPerformancePreset(x){}function getRefreshRateProfile(){return 3}function setRefreshRateProfile(x){}function getCustomRefreshRate(x){return 30}function setCustomRefreshRate(x,y){} })"));
        engine.rootContext()->setContextProperty("LODManager",api(engine,R"(import QtQml 2.15; QtObject { property int worldDetailQuality: 0 })"));
        engine.rootContext()->setContextProperty("Settings",api(engine,R"(import QtQml 2.15; QtObject { function getValue(x,y){return y}function setValue(x,y){} })"));
        engine.rootContext()->setContextProperty("currentPage",QString("Graphics"));
        engine.rootContext()->setContextProperty("header",api(engine,R"(import QtQml 2.15; QtObject { property real height: 40 })"));
        QQuickItem parent;parent.setWidth(1024);parent.setHeight(768);
        QQmlComponent c(&engine,QUrl::fromLocalFile(root+"/scripts/system/settings/Settings.qml"));
        auto item=qobject_cast<QQuickItem*>(c.beginCreate(engine.rootContext()));if(!item){for(auto error:c.errors())std::cerr<<error.toString().toStdString()<<'\n';return 2;}
        // Production Settings binds to its visual parent during completion.
        item->setParentItem(&parent);item->setProperty("currentPage","Graphics");c.completeCreate();
        if(c.isError()){for(auto error:c.errors())std::cerr<<error.toString().toStdString()<<'\n';delete item;return 2;}
        app.processEvents();auto control=item->findChild<QObject*>("settings.graphics.mirrors");assert(control);
        out["qml_initial"]=control->property("settingEnabled").toBool();
        QObject* toggle=nullptr;for(auto child:control->findChildren<QObject*>()) if(child->inherits("QQuickSwitch")) { toggle=child;break; }assert(toggle);
        assert(QMetaObject::invokeMethod(toggle,"toggle"));out["qml_false"]=!render.getMirrorsEnabled()&&allMatch(config,false);
        assert(QMetaObject::invokeMethod(toggle,"toggle"));out["qml_true"]=render.getMirrorsEnabled()&&allMatch(config,true);delete item;
    }
    int count=0;for(auto job:config.findChildren<task::JobConfig*>()) if(job->objectName().startsWith("RenderMirror")) ++count;
    out["qt_version"]=QString::fromLatin1(qVersion());
    out["value"]=render.getMirrorsEnabled();out["configs"]=count;out["all_match"]=allMatch(config,render.getMirrorsEnabled());out["safe"]=safe;
    out["unrelated_enabled"]=config.getJobConfig("RenderMainView.UnrelatedPass")->isEnabled();settings.sync();
    std::cout<<QJsonDocument(out).toJson(QJsonDocument::Compact).toStdString()<<'\n';
}
#include "test.moc"
