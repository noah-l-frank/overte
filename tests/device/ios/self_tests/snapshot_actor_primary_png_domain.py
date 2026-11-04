"""Independent lower rasters before genuine normal input/Actor owner birth.

Native/GPU/SDK/HTTP/authentication remain declared models. Primary and Actor
encode their OWN predeclared raster functions; neither reads the other's PNG.
Actual Page/capture/artifact/PFS/OFS/lock/publication owners are unchanged.
"""
from contextlib import contextmanager
from copy import deepcopy
from io import BytesIO
import hashlib,uuid
from PIL import Image
from adapters.native_feature_observation import need
from ios.self_tests.snapshot_actor_pixel_domain import ActorPixelDomain,DeclaredActorFrame,RUN,TICKET
from ios.self_tests.test_ios_snapshot_captures import Native
from ios.adapters.snapshot_actor_primary_png_factory import retained_original_pixel_join

class ActorPrimaryPNGDomain(ActorPixelDomain):
    def __init__(self,case,*,rect=(0,0,128,128),actor_change=None,actor_pixel_change=False,primary_compression=6):
        super().__init__(case)
        self.rect=list(rect);x,y,w,h=self.rect;need(0<=x<x+w<=128 and 0<=y<y+h<=128)
        # Independent prechosen lower Primary raster, never an Actor result.
        with Image.new('RGBA',(w,h))as image:
            for yy in range(h):
                for xx in range(w):
                    sx,sy=x+xx,128-y-h+yy
                    image.putpixel((xx,yy),((sx*2)%256,(sy*2)%256,((sx//16+sy//16)%2)*200+20,255))
            buffer=BytesIO();image.save(buffer,format='PNG',compress_level=primary_compression);self.primary.f.bytes=buffer.getvalue()
        # A separately declared actual model render event BEFORE any Subject
        # PNG/Primary input owner records. The old constructor-only32px model
        # has no packet/PFS/publication original to rebind or retime.
        held=self.renderer.current;frame=deepcopy(held.inputs)
        frame.update(frameInstance=uuid.uuid4().hex,frameIndex=frame['frameIndex']+1,viewport=[0,0,128,128],
            recordedEpochMs=self.actor.clock(),consumedEpochMs=self.actor.clock())
        if actor_change is not None:actor_change(frame)
        rgba=bytearray()
        for yy in range(128):
            for xx in range(128):
                rgba.extend(((xx*2)%256,(yy*2)%256,((xx//16+yy//16)%2)*200+20,255))
        if actor_pixel_change:rgba[((128-y-h)*128+x)*4]^=1
        self.renderer.current=DeclaredActorFrame(frame,rgba);self.renderer.consume(self.actor.clock())
        self.prepared_primary=0
        primary=self.primary;native=primary.capture.native;domain=self
        def original_callback(cap,identity):
            # This lower producer replaces only its own optional provenance
            # callback. The ORIGINAL native model completion remains literal.
            raw=primary.f.f.h.path.read_bytes()
            with Image.open(BytesIO(raw))as image:
                image.load();extent=list(image.size);rgba=image.convert('RGBA').tobytes()
            need(extent==domain.rect[2:])
            row=deepcopy(primary.recorded[identity])
            row.update(callbackEpochMs=primary.capture.epoch(),readback=dict(sourceExtent=[128,128],rectBottomLeft=list(domain.rect),
                imageExtent=extent,pixelFormat='rgba8-top-left',pixelSha256=hashlib.sha256(rgba).hexdigest(),readEpochMs=primary.capture.epoch()))
            original=native.captures[identity][1]
            primary.provenance_rows[identity]=dict(captureInstance=identity,requestId=original['requestId'],frame=row)
            return Native.finish(native,cap,identity)
        native.finish=original_callback

    def prepare_primary(self):
        need(self.prepared_primary==0);self.prepared_primary+=1
        return self.primary.prepare()

    @contextmanager
    def retained_pair(self,*,publish=True):
        with self.primary.owner()as page:
            capture=self.primary.runtime.capture_child(page)
            if not any(row['kind']=='provenance'for row in capture.state['slots']):capture.provenance()
            rows=[row for row in capture.state['slots']if row['kind']=='provenance'];need(len(rows)==1)
            with self.pixels()as actor:
                if publish:actor.observe_original(1,TICKET)
                yield retained_original_pixel_join(capture,rows[0]['index'],actor.actors,1),actor
