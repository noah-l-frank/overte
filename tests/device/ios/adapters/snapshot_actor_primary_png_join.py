"""Typed equality of one saved Primary crop and an independent Actor PNG.

This reads original owners only. It neither captures nor refreshes a frame and
proves no temporal bracket, independent process authentication or native GPU.
"""
from copy import deepcopy
from io import BytesIO
import hashlib
from PIL import Image
from adapters.native_clock_join import digest
from adapters.native_feature_observation import integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_provenance_packet import SnapshotProvenancePacket
from ios.adapters.snapshot_scene import measured_entities
from ios.adapters.snapshot_actor_pixels import pixels
from ios.adapters.snapshot_actor_pixel_witness import SnapshotActorPixelWitnessOwner
from ios.adapters.snapshot_actor_pixel_publication import SnapshotActorPixelCanonicalPublication

class SnapshotActorPrimaryPNGJoin:
    def __init__(self,capture,provenance,actor,actor_original,publication):
        need(type(capture)is IOSSnapshotCaptureOwner and capture.historical is True
            and type(provenance)is SnapshotProvenancePacket
            and type(actor)is SnapshotActorPixelWitnessOwner and actor.historical is True
            and type(actor_original)is dict
            and type(publication)is SnapshotActorPixelCanonicalPublication and publication.historical is True)
        self.capture,self.provenance,self.actor,self.publication=capture,provenance,actor,publication
        self.actor_original=deepcopy(actor_original)
        need(capture.lock is provenance.lock and same(capture.binding,provenance.binding)
            and capture.run==provenance.run==actor.run==publication.run
            and provenance.role=='primary'and actor.role=='actor'
            and capture.store.path.parent==provenance.store.path.parent
            and capture.store.path.parent!=actor.store.path.parent and capture.lock.path!=actor.lock.path
            and capture.binding['targetFingerprint']!=actor.binding['targetFingerprint']
            and all(capture.binding[k]==actor.binding[k]for k in('sourceRevision','artifactSha256'))
            and capture.phase.fixture_url==actor.fixture_url==publication.actors.fixture_url
            and publication.lock is actor.lock and publication.actors.root==actor.store.path.parent
            and same(publication.binding,actor.binding))

    def proof(self):
        # Both real serialization instances remain held throughout all reads.
        self.capture.lock.assert_held();self.actor.lock.assert_held()
        primary=self.provenance.join_capture(self.capture)
        independent=self.actor.validate_original(self.actor_original)
        need(self.capture.state['ticket']==self.actor.state['ticket'])
        phase=self.capture.state['phaseOriginal'];before=independent['phaseBefore'];after=independent['phaseAfter']
        need(phase['instance']==before['instance']==after['instance']
            and phase['runId']==before['runId']==after['runId']
            and same(phase['activations'],before['activations'])and same(before['activations'],after['activations']))
        artifact=self.capture.history('artifact',self.capture.state['artifact'])
        need(artifact.state['phase']=='copied')
        fact,original=artifact.originals();primary_raw=artifact.read()
        need(primary_raw==original and same(fact['file'],primary['capture']['file']))
        packet=independent['nativeOriginal']['packet'];actor_raw=pixels(packet['source'],int(self.actor.binding['processIdentity']),packet['clockBefore']['epochMs'])
        a=primary['provenance']['frame'];b=packet['source']['frame']
        need(a['snapshotFrameProvenanceVersion']==b['snapshotFrameProvenanceVersion']==2
            and a['processId']==int(self.capture.binding['processIdentity'])
            and b['processId']==int(self.actor.binding['processIdentity'])
            and same(measured_entities(a['scene']),measured_entities(b['scene']))
            and same(a['camera'],b['camera'])and same(a['worldFromCamera'],b['worldFromCamera'])
            and same(a['viewport'],b['viewport']))
        pa,ba=a['readback'],b['readback']
        need(same(pa['sourceExtent'],ba['sourceExtent'])and ba['sourceExtent']==ba['imageExtent']
            and ba['rectBottomLeft']==[0,0,*ba['imageExtent']]
            and pa['pixelFormat']==ba['pixelFormat']=='rgba8-top-left')
        width,height=pa['sourceExtent'];x,y,w,h=pa['rectBottomLeft']
        need(all(integer(n,0)for n in(x,y))and all(integer(n,1,8192)for n in(width,height,w,h))
            and x+w<=width and y+h<=height and pa['imageExtent']==[w,h]and width*height<=8388608)
        # Original PNG encodings may differ; no file is changed or re-encoded.
        with Image.open(BytesIO(primary_raw))as image:
            need(image.format=='PNG'and image.size==(w,h));image.load();primary_rgba=image.convert('RGBA').tobytes()
        top_left=[x,height-y-h,x+w,height-y]
        with Image.open(BytesIO(actor_raw))as image:
            need(image.format=='PNG'and image.size==(width,height));image.load()
            with image.convert('RGBA')as full:
                actor_rgba=full.tobytes()
                with full.crop(tuple(top_left))as cropped:actor_crop=cropped.tobytes()
        need(hashlib.sha256(primary_rgba).hexdigest()==pa['pixelSha256']
            and hashlib.sha256(actor_rgba).hexdigest()==ba['pixelSha256']and primary_rgba==actor_crop)
        reference=self.publication.reference(self.actor.index)
        need(reference['ownerSha256']==self.actor_original['ownerSha256']
            and reference['packetOwnerSha256']==independent['packetOwnerSha256'])
        derived=self.publication.validate_original(reference);public=derived['public']
        expected=dict(ticket=derived['ticket'],actor='owned-observer',actorSequence=public['sequence'],
            capturedEpochMs=public['capturedEpochMs'],facts=deepcopy(public['facts']))
        rows=[row for row in self.publication.history()if row['intent']['body']['actorSequence']==self.actor.index]
        need(len(rows)==1 and rows[0]['mode']=='published'and same(rows[0]['intent']['body'],expected))
        entry=rows[0]['entry'];need(all(same(entry[key],value)for key,value in expected.items()))
        return dict(iosSnapshotActorPrimaryPNGComparisonVersion=1,profile='owned-original-rgba-crop-exact-v1',
            runId=self.capture.run,ticket=self.capture.state['ticket'],primaryBinding=deepcopy(self.capture.binding),actorBinding=deepcopy(self.actor.binding),
            primaryFrame={k:deepcopy(a[k])for k in('frameInstance','frameIndex','processId')},
            actorFrame={k:deepcopy(b[k])for k in('frameInstance','frameIndex','processId')},
            sourceExtent=[width,height],primaryRectBottomLeft=[x,y,w,h],actorRectTopLeft=top_left,
            hashes=dict(primaryPNG=hashlib.sha256(primary_raw).hexdigest(),actorPNG=hashlib.sha256(actor_raw).hexdigest(),
                primaryRGBA=hashlib.sha256(primary_rgba).hexdigest(),actorFullRGBA=hashlib.sha256(actor_rgba).hexdigest(),actorCropRGBA=hashlib.sha256(actor_crop).hexdigest()),
            originals=dict(primary=deepcopy(primary['pins']),primaryArtifactFile=deepcopy(artifact.state['file']),
                primaryArtifactOwnerSha256=digest(artifact.previous),actorWitnessOriginalSha256=digest(self.actor_original),
                actorNativeOriginalSha256=digest(independent['nativeOriginal']),actorPacketOwnerSha256=independent['packetOwnerSha256'],
                actorPublicationOriginalSha256=digest(rows[0]),actorPublicationOwnerSha256=digest(self.publication.store.read())),
            originalCropRGBAEqual=True,ownFrameCameraAndOriginalBytesBound=True,canonicalActorPixelOriginalPublished=True,
            pixelNormalizationApplied=False,PNGEncodedByteEqualityRequired=False,newCaptureOrQueryOrPOST=False,
            captureTemporalBracketingEstablished=False,independentProcessAuthenticationEstablished=False,
            completeSceneAppearanceFidelityEstablished=False,destinationCompositionEstablished=False,processOrSDKEndEstablished=False,
            nativeAdmissionQualified=False,nativeCompiled=False,nativeQualified=False,deviceQualified=False,wholeQualified=False)
