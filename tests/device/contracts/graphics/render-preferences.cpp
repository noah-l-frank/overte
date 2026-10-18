// Copyright 2026 Overte e.V.
// SPDX-License-Identifier: Apache-2.0
// Production methods/templates replace @...@; GPU/services are explicit boundaries.
#include <QCoreApplication>
#include <QSettings>
#include <QJsonDocument>
#include <QJsonObject>
#include <QReadWriteLock>
#include <QLoggingCategory>
#include <QVariant>
#include <QStringList>
#include <QWeakPointer>
#include <functional>
#include <algorithm>
#include <memory>
#include <mutex>
#include <array>
#include <iostream>
#include <cassert>
#include <stdexcept>
@SETTING_INTERFACE@
Q_LOGGING_CATEGORY(settings_handle,"fixture.settings")
QSettings* store;
QJsonObject writes;
namespace Setting {
// Only the async manager/JSON storage boundary is replaced. The full production
// Handle<T> implementation and Interface declaration remain unchanged.
void Interface::init() { _isInitialized=true;load(); }
void Interface::maybeInit() const { if(!_isInitialized) const_cast<Interface*>(this)->init(); }
void Interface::deinit() { if(_isInitialized) save(); }
void Interface::load() { if(store->contains(_key)) { _isSet=true;setVariant(store->value(_key)); } }
void Interface::save() { if(_isSet) { auto v=getVariant();store->setValue(_key,v);writes.insert(_key,QJsonValue::fromVariant(v)); } }
@HANDLE@
}
@LOCK@
namespace task {
class JobConfig:public QObject { Q_OBJECT
public: using QObject::QObject;bool enabled=true;void setEnabled(bool v){enabled=v;setProperty("enabled",v);} };
}
namespace render { struct Args { enum RenderMethod { DEFERRED,FORWARD }; };struct SwitchConfig:task::JobConfig { void setBranch(int){} }; }
struct RenderMirrorTask { static constexpr size_t MAX_MIRRORS_PER_LEVEL=3,MAX_MIRROR_DEPTH=1; };
struct Config {
    QMap<QString,task::JobConfig*> jobs;
    ~Config(){qDeleteAll(jobs);}
    QObject* getConfig(const QString& n){return jobs.value(n);}
};
struct Engine {Config config;Config* getConfiguration(){return &config;}};
struct MakeLightingModelConfig { void setShadow(bool){}void setHaze(bool){}void setBloom(bool){}void setAmbientOcclusion(bool){}void setLocalLighting(bool){}void setPointLight(bool){}void setSpotLight(bool){} };
struct Menu {static Menu* getInstance(){static Menu m;return &m;}void setIsOptionChecked(int,bool){} };
namespace MenuOption {enum {Shadows,AmbientOcclusion,LocalLights,MaterialProceduralShaders};}
struct Procedural {static bool enableProceduralShaders;};bool Procedural::enableProceduralShaders=true;
struct AntialiasingSetupConfig {enum Mode {NONE,TAA,FXAA,MODE_COUNT};};
constexpr bool RENDER_FORWARD=true;
@EXTRA_DECLARATIONS@
struct App {Engine engine;Engine* getRenderEngine(){return &engine;}@APP_MEMBERS@};
#undef qApp
App* qApp;
void recursivelyUpdateMirrorRenderMethods(const QString&,int,int){}
void recursivelyUpdateLightingModel(const QString&,std::function<void(MakeLightingModelConfig*)> f){MakeLightingModelConfig config;f(&config);}
void recursivelyUpdateAntialiasingMode(const QString&,AntialiasingSetupConfig::Mode){}
class RenderScriptingInterface:public QObject { Q_OBJECT
public:
    static RenderScriptingInterface* instance;
    static RenderScriptingInterface* getInstance(){return instance;}
    enum class RenderMethod {DEFERRED,FORWARD};
    static bool isValidRenderMethod(RenderMethod v){return v>=RenderMethod::DEFERRED && v<=RenderMethod::FORWARD;}
    @GUARD_DECLARATION@
    ReadWriteLockable _renderSettingLock;
    @RUNTIME@
    @SETTINGS@
    void loadSettings();
    void setFullScreenScreen(const QString& v){_fullScreenScreen=v;}
    QStringList getScreens()const{return {"Default"};}
    @DECLARATIONS@
signals:void settingsChanged();
};
RenderScriptingInterface* RenderScriptingInterface::instance=nullptr;
@METHODS@
@EXTRA_METHODS@
QJsonObject values(RenderScriptingInterface& r){return {
    {"shadowsEnabled",r.getShadowsEnabled()},{"hazeEnabled",r.getHazeEnabled()},
    {"bloomEnabled",r.getBloomEnabled()},{"ambientOcclusionEnabled",r.getAmbientOcclusionEnabled()},
    {"localLightingEnabled",r.getLocalLightingEnabled()},{"proceduralMaterialsEnabled",r.getProceduralMaterialsEnabled()},
    {"mirrorsEnabled",r.getMirrorsEnabled()},{"renderMethod",int(r.getRenderMethod())},
    {"antialiasingMode",int(r.getAntialiasingMode())},{"viewportResolutionScale",r.getViewportResolutionScale()}};}
void choices(RenderScriptingInterface& r,bool v){
    r.setShadowsEnabled(v);r.setHazeEnabled(v);r.setBloomEnabled(v);r.setAmbientOcclusionEnabled(v);
    r.setLocalLightingEnabled(v);r.setProceduralMaterialsEnabled(v);r.setMirrorsEnabled(v);
    r.setRenderMethod(v?RenderScriptingInterface::RenderMethod::DEFERRED:RenderScriptingInterface::RenderMethod::FORWARD);
    r.setAntialiasingMode(v?AntialiasingSetupConfig::FXAA:AntialiasingSetupConfig::TAA);
    r.setViewportResolutionScale(v?0.75f:0.5f);
}
int main(int argc,char** argv){
    QCoreApplication application(argc,argv);assert(argc>=3);QSettings settings(argv[1],QSettings::IniFormat);store=&settings;
    App app;qApp=&app;RenderScriptingInterface render;RenderScriptingInterface::instance=&render;
    for(const auto& view:QStringList{"RenderMainView","RenderSecondView"}) for(int i=0;i<3;++i){
        auto base=view+".RenderForwardTask.RenderMirrorTask"+QString::number(i)+"Depth0";
        app.engine.config.jobs[base]=new task::JobConfig;
        app.engine.config.jobs[base+".RenderMirrorView"+QString::number(i)+"Depth0"]=new task::JobConfig;
    }
    const QString action=argv[2];
    @STARTUP@
    if(action=="true" || action=="false") choices(render,action=="true");
    if(action=="guard") {
        choices(render,true);settings.sync();writes={};
        {
            RenderScriptingInterface::ScopedSettingsOverride outer(render);choices(render,false);
            {RenderScriptingInterface::ScopedSettingsOverride inner(render);choices(render,true);}
            choices(render,false);
        }
        assert(writes.isEmpty());assert(settings.value("hazeEnabled").toBool());assert(!render.getHazeEnabled());
        render.setViewportResolutionScale(0.9f);assert(!writes.isEmpty());choices(render,true);writes={};
        try {RenderScriptingInterface::ScopedSettingsOverride scoped(render);choices(render,false);throw std::runtime_error("test");} catch(const std::runtime_error&){}
        assert(writes.isEmpty());render.setViewportResolutionScale(0.8f);assert(!writes.isEmpty());choices(render,true);writes={};
        [&]{RenderScriptingInterface::ScopedSettingsOverride scoped(render);choices(render,false);return;}();
        assert(writes.isEmpty());render.setViewportResolutionScale(0.6f);assert(!writes.isEmpty());choices(render,true);
    }
    @ACTION@
    settings.sync();auto out=values(render);QJsonObject saved;for(const auto& key:settings.allKeys()) saved[key]=QJsonValue::fromVariant(settings.value(key));
    out["saved"]=saved;out["writes"]=writes;out["qt_version"]=qVersion();
    bool mirrors=true;for(auto job:app.engine.config.jobs) if(job->enabled!=render.getMirrorsEnabled()) mirrors=false;
    out["mirror_graph_matches"]=mirrors;
    std::cout<<QJsonDocument(out).toJson(QJsonDocument::Compact).constData()<<std::endl;
}
#include "test.moc"
