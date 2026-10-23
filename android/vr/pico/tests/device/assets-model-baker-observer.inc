// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Passive observation of actual original HFM/CPU buffer and task lifetimes.
// The original Baker type/body is compiled through one named alias; the
// derived boundary stops before unqualified material/texture construction.
#define Baker OriginalSourceBaker
#include "model-baker/Baker.h"
#include "AssetsOriginalBakerBody.inc"
#undef Baker
static QJsonArray bakerOriginals;
static QJsonObject bakerHandoff;
static QPointer<task::JobConfig> bakerGraphRoot;
static std::weak_ptr<HFMModel> bakerInput;
static QJsonObject observeBakerHfm(const HFMModel::Pointer& model){
 if(!model){qFatal("An absent actual HFM model cannot be observed as processed");}
 QJsonArray meshes;
 for(const auto& mesh:model->meshes){
  QJsonArray vertices,indices,normals,tangents,texcoords;
  for(const auto& vertex:mesh.vertices){vertices.append(QJsonArray{vertex.x,vertex.y,vertex.z});}
  for(const auto& part:mesh.parts){for(const auto index:part.triangleIndices){indices.append(index);}}
  for(const auto& normal:mesh.normals){normals.append(QJsonArray{normal.x,normal.y,normal.z});}
  for(const auto& tangent:mesh.tangents){tangents.append(QJsonArray{tangent.x,tangent.y,tangent.z});}
  for(const auto& uv:mesh.texCoords){texcoords.append(QJsonArray{uv.x,uv.y});}
  QJsonObject row{{"vertices",vertices},{"indices",indices},{"normals",normals},{"tangents",tangents},{"texcoords",texcoords},
   {"parts",mesh.parts.size()},{"graphicsMeshExists",bool(mesh._mesh)},{"skinningDataValid",mesh.skinningDataValid}};
  if(mesh._mesh){const auto& actual=*mesh._mesh;QJsonArray actualVertices,actualIndices;
   for(size_t i=0;i<actual.getNumVertices();++i){const auto& vertex=actual.getVertexBuffer().get<glm::vec3>(i);actualVertices.append(QJsonArray{vertex.x,vertex.y,vertex.z});}
   for(size_t i=0;i<actual.getNumIndices();++i){actualIndices.append(int(actual.getIndexBuffer().get<uint32_t>(i)));}
   row.insert("bufferVertices",actualVertices);row.insert("bufferIndices",actualIndices);row.insert("bufferParts",int(actual.getNumParts()));
  }
  meshes.append(row);
 }
 QJsonArray textures;
 for(const auto& material:model->materials){textures.append(QJsonObject{{"name",material.albedoTexture.name},
  {"url",QString::fromUtf8(material.albedoTexture.filename)},{"embeddedBytes",material.albedoTexture.content.size()}});}
 return QJsonObject{{"id",QString::number(reinterpret_cast<quintptr>(model.get()),16)},{"url",model->originalURL},{"meshes",meshes},{"joints",model->joints.size()},
  {"materials",model->materials.size()},{"textures",textures},{"errors",model->loadErrorCount},
  {"thread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
  {"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};
}
namespace baker {
class Baker final:public OriginalSourceBaker {
 void record(const QString& phase){bakerOriginals.append(QJsonObject{{"phase",phase},
  {"id",QString::number(reinterpret_cast<quintptr>(this),16)},
  {"thread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
  {"graphId",QString::number(reinterpret_cast<quintptr>(bakerGraphRoot.data()),16)},{"graphAlive",!bakerGraphRoot.isNull()},{"inputAlive",!bakerInput.expired()},
  {"bufferCount",int(gpu::Buffer::getBufferCPUCount())},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}});}
public:
 Baker(const HFMModel::Pointer& model,const QVariantHash& mapping,const QUrl& base):OriginalSourceBaker(model,mapping,base){
  if(!bakerOriginals.isEmpty() || !model || gpu::Buffer::getBufferCPUCount()!=0){qFatal("Original Baker observation requires one empty actual CPU ownership scope");}
  bakerInput=model;{auto config=getConfiguration();bakerGraphRoot=config.get();}
  if(bakerGraphRoot.isNull()){qFatal("Original Baker graph configuration was not constructed");}
  parsedHandoff=observeBakerHfm(model);record("constructed");
 }
 void run(){record("run-enter");OriginalSourceBaker::run();bakerHandoff=observeBakerHfm(getHFMModel());record("run-exit");
  throw QString("Host qualification stops after original Baker before GeometryResource material construction");}
 ~Baker(){record("destructor-enter");}
};
}
