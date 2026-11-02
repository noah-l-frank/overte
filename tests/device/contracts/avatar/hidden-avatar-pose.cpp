// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QCoreApplication>
#include <QThread>
#include <QReadWriteLock>
#include <QVector>
#include <QDebug>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <JointData.h>
#include <NumericalConstants.h>
#include <iostream>
struct PerformanceTimer { explicit PerformanceTimer(const char*) {} };
struct PerformanceWarning { PerformanceWarning(bool,const char*) {} };
struct RenderArgs {};
namespace render { struct Transaction {}; }
namespace controller { enum Action { HEAD }; }
struct AvatarTransit { enum class Status { IDLE }; };
struct AvatarCertifyBanner { void show(int) {} void clear() {} };
namespace MenuOption { constexpr int PipelineWarnings=0; }
struct Menu { static Menu* getInstance(){static Menu instance;return &instance;} bool isOptionChecked(int){return false;} };
struct Scene { void enqueueTransaction(const render::Transaction&) {} };
struct App { Scene scene;Scene* getMain3DScene(){return &scene;} } app;
#undef qApp
#define qApp (&app)
#undef qCDebug
#define qCDebug(...) qDebug()
bool isNaN(glm::vec3){return false;}
glm::vec3 transformPoint(int,glm::vec3 v){return v;}
struct Pose { bool isValid(){return true;} glm::vec3 getTranslation(){return glm::vec3(0,1,0);} };
struct Rig {
    bool overrideActive=false;
    int frame=0,copies=0;
    void setEnableDebugDrawIKTargets(bool){}
    void setEnableDebugDrawIKConstraints(bool){}
    void setEnableDebugDrawIKChains(bool){}
    void overrideAnimation(const QString&,float,bool,float,float){overrideActive=true;}
    void restoreAnimation(){overrideActive=false;}
    void copyJointsIntoJointData(QVector<JointData>& target){
        ++copies;target.resize(1);target[0].translation=glm::vec3(frame,overrideActive?1:0,0);
        target[0].translationIsDefaultPose=false;
    }
};
struct Skeleton {
    Rig rig;bool loaded=true;int simulations=0;
    Rig& getRig(){return rig;}
    bool hasSkeleton(){return loaded;}
    void simulate(float){++simulations;if(loaded)++rig.frame;}
    bool getHeadPosition(glm::vec3& position){position=glm::vec3(rig.frame,1,0);return true;}
};
struct Head {
    int simulations=0;glm::vec3 position{};
    void setPosition(glm::vec3 value){position=value;}
    void setScale(float){}
    void simulate(float){++simulations;}
};
struct Avatar { int localDraws=0;void render(RenderArgs*){++localDraws;} };
namespace AvatarDataPacket {
@PACKET_FLAGS@
}
class MyAvatar : public QObject, public Avatar {
public:
    Skeleton model;Skeleton* _skeletonModel=&model;Head head;
    bool _shouldRender=true,meshVisible=true,_rigEnabled=true,_cauterizationNeedsUpdate=false;
    bool _enableDebugDrawIKTargets=false,_enableDebugDrawIKConstraints=false,_enableDebugDrawIKChains=false;
    QReadWriteLock _jointDataLock;QVector<JointData> _jointData;
    QVector<QVector<JointData>> packets;int relays=0;
    @VISIBILITY@
    void setEnableMeshVisible(bool visible){meshVisible=visible;}
    void render(RenderArgs*);
    void overrideAnimation(const QString&,float,bool,float,float);
    void restoreAnimation();
    void update(float deltaTime){
@SIMULATION@
    }
    void relayJointDataToChildren(){++relays;}
    bool applyGrabChanges(){return false;}
    Head* getHead(){return &head;}
    glm::vec3 getWorldPosition(){return glm::vec3(0);}
    float getModelScale(){return 1;}
    Pose getControllerPoseInSensorFrame(controller::Action){return {};}
    int getSensorToWorldMatrix(){return 0;}
    AvatarTransit::Status updateTransit(float,int,float,int){return AvatarTransit::Status::IDLE;}
    int getNextPosition(){return 0;}
    float getSensorToWorldScale(){return 1;}
    void updateRenderItem(render::Transaction&){}
    bool isCertifyFailed(){return false;}
    int getSessionUUID(){return 0;}
    void sendAvatarDataPacket(){
        int wantedFlags=AvatarDataPacket::PACKET_HAS_JOINT_DATA;
@PACKET_CACHE@
        packets.push_back(jointData);
    }
};
@METHODS@
@SEND_RATE@
quint64 tick=0;
quint64 usecTimestampNow(){return tick+=MIN_TIME_BETWEEN_MY_AVATAR_DATA_SENDS+1;}
struct Rate {int count=0;void increment(){++count;}};
class AvatarManager {
public:
    MyAvatar* _myAvatar;int _transitConfig=0;quint64 _lastSendAvatarDataTime=0;
    bool _myAvatarDataPacketsPaused=false;Rate _myAvatarSendRate;
    explicit AvatarManager(MyAvatar& avatar):_myAvatar(&avatar){}
    void handleTransitAnimations(AvatarTransit::Status){}
    void updateMyAvatar(float deltaTime);
};
@MANAGER@
QJsonObject run(bool visible,bool loading,bool overrideActive,bool rigEnabled,bool pausePackets){
    MyAvatar avatar;avatar.setShouldRenderLocally(visible);avatar.model.loaded=!loading;avatar._rigEnabled=rigEnabled;
    if(!rigEnabled){avatar._jointData.resize(1);avatar._jointData[0].translation=glm::vec3(99,77,0);}
    if(overrideActive)avatar.overrideAnimation("emote.fbx",60,false,0,100);
    AvatarManager manager(avatar);manager._myAvatarDataPacketsPaused=pausePackets;
    bool passed=true;
    for(int i=0;i<3;++i){
        manager.updateMyAvatar(0.1f);RenderArgs args;avatar.render(&args);
        if(!pausePackets){
            passed=passed&&avatar.packets.size()==i+1;
            if(!loading&&rigEnabled)passed=passed&&!avatar.packets.last().isEmpty()&&avatar.packets.last()[0].translation.x==i+1&&avatar.packets.last()[0].translation.y==(overrideActive?1:0);
            if(loading&&rigEnabled)passed=passed&&avatar.packets.last().isEmpty();
            if(!rigEnabled)passed=passed&&avatar.packets.last().size()==1&&avatar.packets.last()[0].translation.x==99&&avatar.packets.last()[0].translation.y==77;
        }
    }
    passed=passed&&avatar.model.simulations==3&&avatar.relays==3;
    passed=passed&&avatar.meshVisible==visible&&avatar.getShouldRenderLocally()==visible&&avatar.localDraws==(visible?3:0);
    passed=passed&&avatar.model.rig.copies==((!loading&&rigEnabled)?3:0);
    passed=passed&&avatar.head.simulations==(loading?0:3);
    if(pausePackets)passed=passed&&avatar.packets.isEmpty();
    // Cancellation and later readiness/resume must preserve pose advancement.
    avatar.restoreAnimation();avatar.model.loaded=true;manager._myAvatarDataPacketsPaused=false;
    int previousFrame=avatar.model.rig.frame;manager.updateMyAvatar(0.1f);
    passed=passed&&!avatar.model.rig.overrideActive&&avatar.model.rig.frame==previousFrame+1;
    if(rigEnabled)passed=passed&&!avatar.packets.last().isEmpty()&&avatar.packets.last()[0].translation.x==previousFrame+1&&avatar.packets.last()[0].translation.y==0;
    if(!rigEnabled)passed=passed&&avatar.packets.last()[0].translation.x==99&&avatar.packets.last()[0].translation.y==77;
    passed=passed&&avatar.head.position.x==avatar.model.rig.frame;
    passed=passed&&avatar.meshVisible==visible;
    return {{"visible",visible},{"initially_loading",loading},{"initial_override",overrideActive},{"rig_enabled",rigEnabled},{"initial_packet_pause",pausePackets},{"skeleton_simulations",avatar.model.simulations},{"joint_copies",avatar.model.rig.copies},{"outbound_packets",avatar.packets.size()},{"child_relays",avatar.relays},{"head_simulations",avatar.head.simulations},{"local_draws",avatar.localDraws},{"passed",passed}};
}
QJsonObject visibilityTransitions(){
    MyAvatar avatar;AvatarManager manager(avatar);RenderArgs args;
    avatar.setShouldRenderLocally(false);avatar.overrideAnimation("emote.fbx",60,false,0,100);
    manager.updateMyAvatar(0.1f);avatar.render(&args);
    avatar.setShouldRenderLocally(true);manager.updateMyAvatar(0.1f);avatar.render(&args);
    avatar.setShouldRenderLocally(false);avatar.restoreAnimation();manager.updateMyAvatar(0.1f);avatar.render(&args);
    bool passed=avatar.model.simulations==3&&avatar.model.rig.copies==3&&avatar.localDraws==1&&!avatar.meshVisible&&avatar.packets.size()==3;
    if(passed)for(int i=0;i<3;++i)passed=passed&&avatar.packets[i].size()==1&&avatar.packets[i][0].translation.x==i+1&&avatar.packets[i][0].translation.y==(i==2?0:1);
    return {{"case","hide-show-hide-during-override-then-cancel"},{"passed",passed}};
}
int main(int argc,char** argv){QCoreApplication app(argc,argv);QJsonArray results;bool passed=true;
 for(bool visible:{false,true})for(bool loading:{false,true})for(bool overrideActive:{false,true})for(bool rigEnabled:{false,true})for(bool paused:{false,true}){
  auto row=run(visible,loading,overrideActive,rigEnabled,paused);passed=passed&&row["passed"].toBool();results.push_back(row);
 }
 auto transition=visibilityTransitions();passed=passed&&transition["passed"].toBool();results.push_back(transition);
 std::cout<<QJsonDocument(results).toJson().toStdString();return passed?0:1;
}
