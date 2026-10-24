// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#if !defined(OVERTE_E2E_FEATURE_TESTS)
#error The Snapshot companion is a separate, explicitly selected test target.
#endif
#import "PhotosOriginal.h"
#import "CompanionIdentity.h"
#import <Photos/Photos.h>
#import <CommonCrypto/CommonDigest.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>

static const NSUInteger OVTMaximumOriginalBytes=256*1024*1024;
static NSDictionary* OVTClock(void) {
    return @{ @"epochMs":@((long long)(NSDate.date.timeIntervalSince1970*1000)),
              @"monotonicMs":@((long long)(NSProcessInfo.processInfo.systemUptime*1000)) };
}
static BOOL OVTMatch(NSString* value,NSString* expression) {
    return [value isKindOfClass:NSString.class] && [value rangeOfString:expression options:NSRegularExpressionSearch].location!=NSNotFound;
}
static NSString* OVTIdentifier(void) {return [[NSUUID.UUID.UUIDString lowercaseString] stringByReplacingOccurrencesOfString:@"-" withString:@""];}

@class OVTPhotosRead;
@class OVTPhotosDelete;
@interface OVTPhotosJournal : NSObject
@property(nonatomic,strong) NSRecursiveLock* lock;
@property(nonatomic,strong) NSURL* root;
@property(nonatomic,strong) NSMutableDictionary* record;
@property(nonatomic,weak) OVTPhotosRead* operation;
@property(nonatomic,weak) OVTPhotosDelete* deletion;
@property BOOL valid;
- (BOOL)persist;
- (BOOL)event:(NSString*)kind detail:(NSDictionary*)detail;
@end

@interface OVTPhotosDelete : NSObject
@property(nonatomic,strong) OVTPhotosJournal* journal;
@end

@interface OVTPhotosRead : NSObject {
@public
    int descriptor;
    CC_SHA256_CTX digest;
}
@property(nonatomic,strong) OVTPhotosJournal* journal;
@property NSUInteger count;
@property BOOL failed;
@end

@implementation OVTPhotosJournal
- (instancetype)init {
    if ((self=[super init])) { _lock=[NSRecursiveLock new];_valid=YES; }
    return self;
}
- (BOOL)persist {
    if (!_valid) {return NO;}
    NSError* error=nil;
    NSData* bytes=[NSJSONSerialization dataWithJSONObject:_record options:0 error:&error];
    if (!bytes || bytes.length>262144 || error) {_valid=NO;return NO;}
    NSString* pending=[_root.path stringByAppendingPathComponent:[@".record-" stringByAppendingString:OVTIdentifier()]];
    int output=open(pending.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if (output<0) {_valid=NO;return NO;}
    NSUInteger offset=0;BOOL ok=YES;
    while (offset<bytes.length) {
        ssize_t written=write(output,(const char*)bytes.bytes+offset,bytes.length-offset);
        if (written<0 && errno==EINTR) {continue;}
        if (written<=0) {ok=NO;break;}offset+=(NSUInteger)written;
    }
    if (fsync(output)!=0) {ok=NO;}if (close(output)!=0) {ok=NO;}
    NSString* destination=[_root.path stringByAppendingPathComponent:@"photos-original.json"];
    if (ok && rename(pending.fileSystemRepresentation,destination.fileSystemRepresentation)!=0) {ok=NO;}
    int directory=open(_root.path.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (directory<0) {ok=NO;}else {if (fsync(directory)!=0) {ok=NO;}close(directory);}
    if (!ok) {_valid=NO;}return ok;
}
- (BOOL)event:(NSString*)kind detail:(NSDictionary*)detail {
    [_lock lock];
    NSMutableArray* events=_record[@"events"];
    if (!_valid || events.count>=512) {_valid=NO;[_lock unlock];return NO;}
    [events addObject:@{@"sequence":@(events.count+1),@"kind":kind,@"clock":OVTClock(),@"detail":detail}];
    BOOL result=[self persist];[_lock unlock];return result;
}
@end

@implementation OVTPhotosRead
- (instancetype)init {
    if ((self=[super init])) {descriptor=-1;CC_SHA256_Init(&digest);}
    return self;
}
- (void)dealloc {
    if (descriptor>=0) {close(descriptor);descriptor=-1;}
    // No observation retains this owner. PhotoKit's real blocks and the
    // initiating stack determine its lifetime, including late block release.
    [_journal event:@"weak-expired" detail:@{}];
}
@end

@implementation OVTPhotosDelete
- (void)dealloc {[self.journal event:@"delete-weak-expired" detail:@{}];}
@end

@interface OVTPhotosOriginalController ()
@property(nonatomic,strong) UITextField* runField;
@property(nonatomic,strong) UITextField* assetField;
@property(nonatomic,strong) UITextField* nameField;
@property(nonatomic,strong) UITextField* queryField;
@property(nonatomic,strong) UILabel* status;
@property(nonatomic,strong) OVTPhotosJournal* journal;
@property(nonatomic,copy) NSString* instance;
@end

@implementation OVTPhotosOriginalController
- (UITextField*)field:(NSString*)name placeholder:(NSString*)placeholder stack:(UIStackView*)stack {
    UITextField* field=[UITextField new];field.borderStyle=UITextBorderStyleRoundedRect;
    field.autocorrectionType=UITextAutocorrectionTypeNo;field.autocapitalizationType=UITextAutocapitalizationTypeNone;
    field.accessibilityIdentifier=name;field.placeholder=placeholder;[stack addArrangedSubview:field];return field;
}
- (void)button:(NSString*)title name:(NSString*)name action:(SEL)action stack:(UIStackView*)stack {
    UIButton* button=[UIButton buttonWithType:UIButtonTypeSystem];[button setTitle:title forState:UIControlStateNormal];
    button.accessibilityIdentifier=name;[button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:button];
}
- (void)viewDidLoad {
    [super viewDidLoad];self.instance=OVTIdentifier();self.view.backgroundColor=UIColor.systemBackgroundColor;
    UIStackView* stack=[UIStackView new];stack.axis=UILayoutConstraintAxisVertical;stack.spacing=12;stack.translatesAutoresizingMaskIntoConstraints=NO;
    [self.view addSubview:stack];[NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.leadingAnchor constant:20],
        [stack.trailingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.trailingAnchor constant:-20],
        [stack.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:20]]];
    [stack addArrangedSubview:[OVTSnapshotCompanionIdentityPanel new]];
    self.runField=[self field:@"snapshot.destination.run" placeholder:@"Run identifier" stack:stack];
    self.assetField=[self field:@"snapshot.destination.asset" placeholder:@"Observed Photos placeholder identifier" stack:stack];
    self.nameField=[self field:@"snapshot.destination.basename" placeholder:@"Observed original capture filename" stack:stack];
    self.queryField=[self field:@"snapshot.destination.query" placeholder:@"Fresh read nonce" stack:stack];
    [self button:@"Authorize Photos read" name:@"snapshot.destination.authorize" action:@selector(authorizePhotos) stack:stack];
    [self button:@"Read Photos original" name:@"snapshot.destination.read" action:@selector(readOriginal) stack:stack];
    [self button:@"Inspect original owner" name:@"snapshot.destination.inspect" action:@selector(inspectOriginal) stack:stack];
    [self button:@"Delete this owned Photos asset" name:@"snapshot.destination.delete" action:@selector(deleteOriginal) stack:stack];
    self.status=[UILabel new];self.status.numberOfLines=0;self.status.accessibilityIdentifier=@"snapshot.destination.status";
    self.status.text=@"No original acquired";[stack addArrangedSubview:self.status];
}
- (void)authorizePhotos {
    // This is an actual normal test-companion button followed by the real OS
    // authorization alert. Its callback is not the client's Save permission.
    [PHPhotoLibrary requestAuthorizationForAccessLevel:PHAccessLevelReadWrite handler:^(PHAuthorizationStatus status) {
        dispatch_async(dispatch_get_main_queue(),^{self.status.text=[NSString stringWithFormat:@"Companion Photos authorization: %ld",(long)status];});
    }];
}
- (void)fail {self.status.text=@"Original unavailable; responsibility remains retained";}
- (void)readOriginal {
    if (self.journal) {[self fail];return;} // A second tap/reconstruction never repeats the native read.
    NSString* run=self.runField.text,*asset=self.assetField.text,*name=self.nameField.text;
    if (!OVTMatch(run,@"\\A[0-9a-f]{32}\\z") || asset.length<1 || asset.length>4096
            || OVTMatch(asset,@"[\\x00-\\x1f\\x7f]")
            || !OVTMatch(name,@"\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,20}_[0-9]{1,10}\\.(png|jpg|jpeg|webp|gif)\\z")
            || ![name hasPrefix:[@"parity-" stringByAppendingString:[run substringToIndex:16]]]) {[self fail];return;}
    PHAuthorizationStatus permission=[PHPhotoLibrary authorizationStatusForAccessLevel:PHAccessLevelReadWrite];
    if (permission!=PHAuthorizationStatusAuthorized && permission!=PHAuthorizationStatusLimited) {[self fail];return;}
    NSURL* documents=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL* root=[documents URLByAppendingPathComponent:[@"snapshot-photos-" stringByAppendingString:run] isDirectory:YES];
    NSError* error=nil;
    // Existing output, including an interrupted original from an old process,
    // is never adopted, overwritten or turned into a new owner.
    if (![NSFileManager.defaultManager createDirectoryAtURL:root withIntermediateDirectories:NO attributes:@{NSFilePosixPermissions:@0700} error:&error]) {[self fail];return;}
    OVTPhotosJournal* journal=[OVTPhotosJournal new];journal.root=root;self.journal=journal;
    journal.record=[@{@"iosSnapshotDestinationVersion":@1,@"runId":run,@"kind":@"photos-resource",@"basename":name,
        @"photosIdentifier":asset,@"instance":self.instance,@"processId":@(getpid()),@"clockDomain":@"native-companion-photos",
        @"createdClock":OVTClock(),@"events":[NSMutableArray new],@"queries":[NSMutableArray new],
        @"phase":@"issued",@"resource":NSNull.null,@"byteCount":@0,@"sha256":@"",@"artifact":@"original.bytes",@"deletion":NSNull.null} mutableCopy];
    if (![journal event:@"read-issued" detail:@{}]) {[self fail];return;}
    PHFetchResult<PHAsset*>* fetched=[PHAsset fetchAssetsWithLocalIdentifiers:@[asset] options:nil];
    if (fetched.count!=1) {journal.record[@"phase"]=@"failed";[journal event:@"read-failed" detail:@{}];[self fail];return;}
    NSArray<PHAssetResource*>* resources=[PHAssetResource assetResourcesForAsset:fetched.firstObject];
    NSMutableArray<PHAssetResource*>* originals=[NSMutableArray new];
    for (PHAssetResource* resource in resources) {
        if (resource.type==PHAssetResourceTypePhoto && [resource.originalFilename isEqualToString:name]) {[originals addObject:resource];}
    }
    if (originals.count!=1) {journal.record[@"phase"]=@"failed";[journal event:@"read-failed" detail:@{}];[self fail];return;}
    PHAssetResource* resource=originals.firstObject;
    journal.record[@"resource"]=@{@"originalFilename":resource.originalFilename,@"type":@(resource.type)};
    if (![journal event:@"resource-selected" detail:@{}]) {[self fail];return;}
    OVTPhotosRead* operation=[OVTPhotosRead new];operation.journal=journal;journal.operation=operation;
    operation->descriptor=open([[root URLByAppendingPathComponent:@"original.bytes"].path fileSystemRepresentation],O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if (operation->descriptor<0) {journal.record[@"phase"]=@"failed";[journal event:@"read-failed" detail:@{}];[self fail];return;}
    PHAssetResourceRequestOptions* options=[PHAssetResourceRequestOptions new];options.networkAccessAllowed=NO;
    [PHAssetResourceManager.defaultManager requestDataForAssetResource:resource options:options dataReceivedHandler:^(NSData* data) {
        [journal.lock lock];
        [journal event:@"callback-enter" detail:@{@"name":@"data"}];
        if (!journal.valid || operation.failed || data.length>OVTMaximumOriginalBytes-operation.count) {operation.failed=YES;}
        else {
            NSUInteger offset=0;
            while (offset<data.length) {
                ssize_t written=write(operation->descriptor,(const char*)data.bytes+offset,data.length-offset);
                if (written<0 && errno==EINTR) {continue;}
                if (written<=0) {operation.failed=YES;break;}offset+=(NSUInteger)written;
            }
            if (!operation.failed) {CC_SHA256_Update(&operation->digest,data.bytes,(CC_LONG)data.length);operation.count+=data.length;journal.record[@"byteCount"]=@(operation.count);}
        }
        [journal event:@"callback-left" detail:@{@"name":@"data"}];[journal.lock unlock];
    } completionHandler:^(NSError* failure) {
        [journal.lock lock];[journal event:@"callback-enter" detail:@{@"name":@"completion"}];
        struct stat actual={};
        BOOL success=!failure && !operation.failed && journal.valid && operation.count>0
            && fsync(operation->descriptor)==0 && fstat(operation->descriptor,&actual)==0 && S_ISREG(actual.st_mode)
            && actual.st_nlink==1 && actual.st_size==(off_t)operation.count;
        if (close(operation->descriptor)!=0) {success=NO;}operation->descriptor=-1;
        if (success) {
            unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256_Final(digest,&operation->digest);NSMutableString* hex=[NSMutableString new];
            for (NSUInteger i=0;i<CC_SHA256_DIGEST_LENGTH;++i) {[hex appendFormat:@"%02x",digest[i]];}
            journal.record[@"sha256"]=hex;journal.record[@"phase"]=@"complete";
            [journal event:@"read-completed" detail:@{}];
        } else {journal.record[@"phase"]=@"failed";[journal event:@"read-failed" detail:@{}];}
        [journal event:@"callback-left" detail:@{@"name":@"completion"}];[journal.lock unlock];
    }];
    self.status.text=@"Photos resource read issued once";
}
- (void)deleteOriginal {
    OVTPhotosJournal* journal=self.journal;
    if (!journal) {[self fail];return;}[journal.lock lock];
    NSDictionary* readEnd=[journal.record[@"events"] lastObject];
    if (!journal.valid || journal.operation || ![journal.record[@"phase"] isEqual:@"complete"]
            || ![readEnd[@"kind"] isEqual:@"weak-expired"]
            || journal.record[@"deletion"]!=NSNull.null
            || [PHPhotoLibrary authorizationStatusForAccessLevel:PHAccessLevelReadWrite]!=PHAuthorizationStatusAuthorized) {
        [journal.lock unlock];[self fail];return;
    }
    PHFetchResult<PHAsset*>* fetched=[PHAsset fetchAssetsWithLocalIdentifiers:@[journal.record[@"photosIdentifier"]] options:nil];
    if (fetched.count!=1) {[journal.lock unlock];[self fail];return;}
    NSArray<PHAssetResource*>* resources=[PHAssetResource assetResourcesForAsset:fetched.firstObject];
    if (resources.count!=1 || resources.firstObject.type!=PHAssetResourceTypePhoto
            || ![resources.firstObject.originalFilename isEqual:journal.record[@"basename"]]) {[journal.lock unlock];[self fail];return;}
    journal.record[@"deletion"]=[@{@"phase":@"issued"} mutableCopy];
    if (![journal event:@"delete-issued" detail:@{}]) {[journal.lock unlock];[self fail];return;}
    OVTPhotosDelete* deletion=[OVTPhotosDelete new];deletion.journal=journal;journal.deletion=deletion;
    [PHPhotoLibrary.sharedPhotoLibrary performChanges:^{
        // Keep the actual operation alive through both real PhotoKit blocks.
        OVTPhotosJournal* actual=deletion.journal;[actual.lock lock];[actual event:@"delete-changes-enter" detail:@{}];
        [PHAssetChangeRequest deleteAssets:fetched];
        [actual event:@"delete-changes-left" detail:@{}];[actual.lock unlock];
    } completionHandler:^(BOOL success,NSError* error) {
        OVTPhotosJournal* actual=deletion.journal;[actual.lock lock];[actual event:@"delete-completion-enter" detail:@{}];
        NSMutableDictionary* result=actual.record[@"deletion"];result[@"phase"]=success && !error?@"complete":@"failed";
        [actual event:@"delete-completed" detail:@{@"success":@(success),@"hasError":@(error!=nil)}];
        [actual event:@"delete-completion-left" detail:@{}];[actual.lock unlock];
    }];
    [journal.lock unlock];self.status.text=@"Owned Photos deletion issued once; OS confirmation may be required";
}
- (void)inspectOriginal {
    OVTPhotosJournal* journal=self.journal;NSString* query=self.queryField.text;
    if (!journal || !OVTMatch(query,@"\\Aios-[0-9a-f]{32}\\z")) {[self fail];return;}
    [journal.lock lock];NSMutableArray* queries=journal.record[@"queries"];
    for (NSDictionary* old in queries) {if ([old[@"requestId"] isEqual:query]) {[journal.lock unlock];[self fail];return;}}
    if (queries.count>=128 || !journal.valid) {[journal.lock unlock];[self fail];return;}
    PHAuthorizationStatus permission=[PHPhotoLibrary authorizationStatusForAccessLevel:PHAccessLevelReadWrite];
    // Limited visibility is not actual deletion/absence. Only full ReadWrite
    // authorization can qualify the independent post-delete asset lookup.
    id present=NSNull.null;
    if (permission==PHAuthorizationStatusAuthorized) {
        PHFetchResult<PHAsset*>* fetched=[PHAsset fetchAssetsWithLocalIdentifiers:@[journal.record[@"photosIdentifier"]] options:nil];
        present=@(fetched.count!=0);
    }
    if ([PHPhotoLibrary authorizationStatusForAccessLevel:PHAccessLevelReadWrite]!=permission) {
        journal.valid=NO;[journal.lock unlock];[self fail];return;
    }
    [queries addObject:@{@"requestId":query,@"clock":OVTClock(),@"operationAlive":@(journal.operation!=nil),
                         @"deletionAlive":@(journal.deletion!=nil),@"assetPresent":present,@"authorization":@(permission)}];
    BOOL saved=[journal persist];[journal.lock unlock];
    self.status.text=saved?@"Original inspection persisted":@"Original inspection failed";
}
@end
