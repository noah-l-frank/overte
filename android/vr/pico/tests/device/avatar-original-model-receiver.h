// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "AvatarOriginalModelResource.h"
#include "libraries/render-utils/src/FeatureModelLoads.h"
Q_DECLARE_LOGGING_CATEGORY(renderutils)
Q_DECLARE_LOGGING_CATEGORY(avatars_renderer)
// Constructor/Rig/scene/render operations are declared endpoints. Loaded
// geometry, ResourceWatcher and complete selected Model methods are originals.
namespace render {
struct Transaction {};
struct Scene {void enqueueTransaction(Transaction&) {}};
using ScenePointer=std::shared_ptr<Scene>;
}
struct AbstractViewStateInterface {
    static AbstractViewStateInterface* instance(){static AbstractViewStateInterface value;return &value;}
    render::ScenePointer getMain3DScene(){return std::make_shared<render::Scene>();}
};
struct AvatarLoaderRigActor {
    int e2eRigId()const{return 17;}
    void initFlow(bool){}void destroyAnimGraph(){}
};
class AvatarOriginalResourceWatcher:public GeometryResourceWatcher {
public:
    using GeometryResourceWatcher::GeometryResourceWatcher;
    struct Original {QPointer<GeometryResource> object;QWeakPointer<GeometryResource> weak;QString url,id;};
    QList<Original> originals;
    void setResource(GeometryResource::Pointer resource){
        if(resource){originals.append({resource.data(),resource.toWeakRef(),resource->getURL().toString(),
            QString::number(reinterpret_cast<quintptr>(resource.data()),16)});}
        GeometryResourceWatcher::setResource(resource);
    }
};
class Model:public QObject {
    Q_OBJECT
public:
    explicit Model(QObject* parent=nullptr):QObject(parent),_renderWatcher(_renderGeometry){
        connect(&_renderWatcher,&GeometryResourceWatcher::finished,this,&Model::loadURLFinished);
    }
    Q_INVOKABLE void setURL(const QUrl&);
    void loadURLFinished(bool);void deleteGeometry();void setTextures(const QVariantMap&);
    void removeFromScene(const render::ScenePointer&,render::Transaction&){}
    void invalidCalculatedMeshBoxes(){}void onInvalidate(){}
    // Complete exact original inline getters are generated, not substitutes.
#include "AvatarOriginalModelGetters.inc"
    AvatarLoaderRigActor& getRig(){return _rig;}
    int getResourceDownloadAttemptsRemaining(){return _renderWatcher.getResourceDownloadAttemptsRemaining();}
    int getResourceDownloadAttempts(){return _renderWatcher.getResourceDownloadAttempts();}
    std::weak_ptr<Geometry> weakGeometry()const{return _renderGeometry;}
    QUrl _url;
    Geometry::Pointer _renderGeometry;
    AvatarOriginalResourceWatcher _renderWatcher;
    AvatarLoaderRigActor _rig;
    bool _needsReload{false},_visualGeometryRequestFailed{false},_needsFixupInScene{false};
    std::function<float()> _loadingPriorityOperator=[] {return 0.0f;};
    QVariantMap _pendingTextures;
    std::vector<int> _meshStates;std::vector<float> _blendedBlendshapeCoefficients;
    overte::e2e::FeatureModelLoads _e2eModelLoads;
    const QString _e2eModelInstance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
signals:
    void setURLFinished(bool success);
};
