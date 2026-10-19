#include <QCoreApplication>
#include <QHash>
#include <QString>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonDocument>
#include <functional>
#include <iostream>
#include <vector>
#include <memory>
struct Base { virtual ~Base()=default; int updates=0; };
struct MakeLightingModelConfig : Base { bool enabled=true; void setHaze(bool v){enabled=v;++updates;} };
struct MakeLightingModel { using Config=MakeLightingModelConfig; };
namespace render { struct SwitchConfig:Base { int branch=0; void setBranch(int value){branch=value;++updates;} }; }
struct AntialiasingSetupConfig:Base { enum Mode{NONE,TAA,FXAA,MODE_COUNT}; bool playing=false; void none(){playing=false;++updates;} void play(){playing=true;++updates;} };
struct AntialiasingConfig:Base { double blend=1.0; bool fxaa=false; void setDebugFXAA(bool value){fxaa=value;++updates;} };
struct AntialiasingSetup { using Config=AntialiasingSetupConfig; }; struct Antialiasing { using Config=AntialiasingConfig; };
struct RenderMirrorTask { static constexpr size_t MAX_MIRROR_DEPTH=@DEPTH@, MAX_MIRRORS_PER_LEVEL=@COUNT@; };
struct Config {
 QHash<QString,Base*> jobs; std::vector<std::unique_ptr<Base>> owned; mutable QStringList misses;
 template<class T> T* add(const QString& path){auto p=std::make_unique<T>();auto* raw=p.get();jobs.insert(path,raw);owned.push_back(std::move(p));return raw;}
 Base* getJobConfig(const std::string& path) const {const auto name=QString::fromStdString(path);auto* p=jobs.value(name);if(!p)misses.push_back(name);return p;}
 Base* getConfig(const QString& path){return getJobConfig(path.toStdString());}
 @TYPED_CONFIG_GETTER@
};
struct Engine { Config* config=nullptr; Config* getConfiguration(){return config;} };
struct App { Engine engine; Engine* getRenderEngine(){return &engine;} } app;
#undef qApp
#define qApp (&app)
class RenderScriptingInterface {public:bool isDeferredRenderingAvailable() const;};
#ifdef HOST_ANDROID
#define Q_OS_ANDROID
#endif
@CAPABILITY@
#ifdef HOST_ANDROID
#undef Q_OS_ANDROID
#endif
@FUNCTIONS@
void buildView(Config& c,const QString& view,int depth,bool android) {
 c.add<Base>(view);
 c.add<MakeLightingModelConfig>(view+".@LIGHTING@");
 if(!android)c.add<render::SwitchConfig>(view+".@SWITCH@");
 const QStringList branches=android?QStringList{".@FORWARD@"}:QStringList{".@SWITCH@.@FORWARD@",".@SWITCH@.@SHADOW@.@DEFERRED@"};
 for(const auto& branch:branches){
  if(branch.endsWith(".@DEFERRED@")){c.add<AntialiasingSetupConfig>(view+branch+".@AASETUP@");c.add<AntialiasingConfig>(view+branch+".@AA@");}
  if(depth < int(RenderMirrorTask::MAX_MIRROR_DEPTH))for(size_t i=0;i<RenderMirrorTask::MAX_MIRRORS_PER_LEVEL;++i){
   QString suffix=QString::number(i)+"Depth"+QString::number(depth);
   buildView(c,view+branch+".@MIRROR@"+suffix+".@MIRRORVIEW@"+suffix,depth+1,android);
  }
 }
}
QJsonObject lightingCase(bool android,int repetition) {
 Config c; buildView(c,"RenderMainView",0,android);buildView(c,"RenderSecondView",0,android);app.engine.config=&c;
 recursivelyUpdateLightingModel("",[](MakeLightingModelConfig* p){p->setHaze(false);});
 int roots=0,rootUpdated=0,nested=0,nestedUpdated=0;
 for(auto it=c.jobs.cbegin();it!=c.jobs.cend();++it)if(auto* p=dynamic_cast<MakeLightingModelConfig*>(it.value())){
  if(it.key().contains(".@MIRROR@")){++nested;if(!p->enabled && p->updates==1)++nestedUpdated;}else{++roots;if(!p->enabled&&p->updates==1)++rootUpdated;}
 }
 return {{"case",android?"pico-direct-forward-lighting":"ios-desktop-lighting"},{"replacement_round",repetition},{"root_expected",roots},{"root_updated",rootUpdated},{"nested_expected",nested},{"nested_updated",nestedUpdated},{"passed",roots==rootUpdated&&nested==nestedUpdated},{"first_missing_lookup",c.misses.value(0)}};
}
QJsonObject aaCase(int repetition) {
 Config c;buildView(c,"RenderMainView",0,false);buildView(c,"RenderSecondView",0,false);app.engine.config=&c;
 recursivelyUpdateAntialiasingMode("",AntialiasingSetupConfig::FXAA);
 int expected=0,updated=0;
 for(auto* p:c.jobs)if(auto* a=dynamic_cast<AntialiasingConfig*>(p)){++expected;if(a->fxaa&&a->blend==0.25&&a->updates==1)++updated;}
 return {{"case","ios-desktop-deferred-AA"},{"replacement_round",repetition},{"expected",expected},{"updated",updated},{"passed",expected==updated},{"first_missing_lookup",c.misses.value(0)}};
}
QJsonObject methodCase(int method,int repetition) {
 Config c;buildView(c,"RenderMainView",0,false);buildView(c,"RenderSecondView",0,false);app.engine.config=&c;
 QStringList expected;
 for(auto it=c.jobs.cbegin();it!=c.jobs.cend();++it)if(dynamic_cast<render::SwitchConfig*>(it.value()))expected<<it.key();
 for(const auto& root:QStringList{"RenderMainView","RenderSecondView"})recursivelyUpdateMirrorRenderMethods(root,method,0);
 int updated=0;for(const auto& name:expected){auto* p=dynamic_cast<render::SwitchConfig*>(c.jobs.value(name));if(p&&p->branch==method&&p->updates==1)++updated;}
 return {{"case",method==1?"ios-desktop-mirror-method-forward":"ios-desktop-mirror-method-deferred"},{"replacement_round",repetition},{"expected",expected.size()},{"updated",updated},{"passed",expected.size()==updated},{"first_missing_lookup",c.misses.value(0)}};
}
int main(int argc,char** argv){QCoreApplication qt(argc,argv);QJsonArray rows;bool success=true;
#ifdef HOST_ANDROID
 bool expectedCapability=false;
#else
 bool expectedCapability=true;
#endif
 bool capability=RenderScriptingInterface().isDeferredRenderingAvailable();
 success=capability==expectedCapability;
 rows.append(QJsonObject{{"case","native-deferred-capability"},{"actual",capability},{"expected",expectedCapability},{"passed",success}});
 for(int round=0;round<2;++round)for(auto row:{lightingCase(true,round),lightingCase(false,round),aaCase(round),methodCase(0,round),methodCase(1,round)}){success=success&&row["passed"].toBool();rows.append(row);}
 std::cout<<QJsonDocument(QJsonObject{{"observations",rows}}).toJson().toStdString();return success?0:1;}
