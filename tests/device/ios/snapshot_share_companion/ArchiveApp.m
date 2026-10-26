// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <UIKit/UIKit.h>
#import <CommonCrypto/CommonDigest.h>
#import "ShareJournal.h"
#import "CompanionIdentity.h"
#import "ShareArchiveFiles.h"
#import "ShareSourceOutputs.h"
#include <sys/stat.h>
#include <unistd.h>

@interface OVTShareAdmissionSealButton : UIButton
@end
@implementation OVTShareAdmissionSealButton
- (BOOL)isEnabled {return [super isEnabled] && OVTSnapshotCompanionIdentity.shared.archiveAdmissionSealReady;}
@end
@interface OVTShareAdmissionSealOriginal : UILabel
@end
@implementation OVTShareAdmissionSealOriginal
- (NSString*)accessibilityValue {
    NSData* original=OVTSnapshotCompanionIdentity.shared.archiveAdmissionSealBytes;
    return original.length>0 && original.length<=262144?[[NSString alloc] initWithData:original encoding:NSUTF8StringEncoding]:@"";
}
@end
@interface OVTShareSourceInventoryButton : UIButton
@property(nonatomic,strong) OVTShareSourceOutputs* source;
@end
@implementation OVTShareSourceInventoryButton
- (BOOL)isEnabled {return [super isEnabled] && self.source.inventoryReady;}
@end
@interface OVTShareSourceInventoryOriginal : UILabel
@property(nonatomic,strong) OVTShareSourceOutputs* source;
@end
@implementation OVTShareSourceInventoryOriginal
- (NSString*)accessibilityValue {
    NSData* original=self.source.inventoryOriginal;
    return original.length>0 && original.length<=262144?[[NSString alloc] initWithData:original encoding:NSUTF8StringEncoding]:@"";
}
@end

@interface OVTShareArchive : UIViewController
@property(nonatomic,strong) UITextField* runField;
@property(nonatomic,strong) UILabel* status;
@property(nonatomic,strong) UITextField* queryField;
@property(nonatomic,strong) UITextField* offsetField;
@property(nonatomic,strong) NSMutableSet<NSString*>* chunkNonces;
@property(nonatomic,strong) NSDictionary* importRecord;
@property(nonatomic,strong) NSURL* outputRoot;
@property(nonatomic,strong) OVTShareArchiveRetirement* retirement;
@property(nonatomic,strong) UILabel* admissionSealOriginal;
@property(nonatomic,strong) OVTShareSourceOutputs* sources;
@end
@implementation OVTShareArchive
- (void)viewDidLoad {
    [super viewDidLoad];self.view.backgroundColor=UIColor.systemBackgroundColor;
    self.sources=OVTShareSourceOutputs.shared;
    UIStackView* stack=[UIStackView new];stack.axis=UILayoutConstraintAxisVertical;stack.spacing=16;stack.translatesAutoresizingMaskIntoConstraints=NO;
    [self.view addSubview:stack];[NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.leadingAnchor constant:20],
        [stack.trailingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.trailingAnchor constant:-20],
        [stack.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:20]]];
    [stack addArrangedSubview:[OVTSnapshotCompanionIdentityPanel new]];
    self.runField=[UITextField new];self.runField.borderStyle=UITextBorderStyleRoundedRect;self.runField.placeholder=@"Completed Share run identifier";
    self.runField.autocorrectionType=UITextAutocorrectionTypeNo;self.runField.autocapitalizationType=UITextAutocapitalizationTypeNone;
    self.runField.accessibilityIdentifier=@"snapshot.share.archive.run";[stack addArrangedSubview:self.runField];
    UIButton* button=[UIButton buttonWithType:UIButtonTypeSystem];[button setTitle:@"Import unchanged Share original" forState:UIControlStateNormal];
    button.accessibilityIdentifier=@"snapshot.share.archive.import";[button addTarget:self action:@selector(importOriginal) forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:button];
    self.chunkNonces=[NSMutableSet new];
    self.queryField=[UITextField new];self.queryField.accessibilityIdentifier=@"snapshot.share.archive.query";self.queryField.placeholder=@"Fresh unchanged original chunk nonce";
    self.offsetField=[UITextField new];self.offsetField.accessibilityIdentifier=@"snapshot.share.archive.offset";self.offsetField.placeholder=@"Original byte offset";
    for (UITextField* field in @[self.queryField,self.offsetField]) {
        field.borderStyle=UITextBorderStyleRoundedRect;field.autocorrectionType=UITextAutocorrectionTypeNo;field.autocapitalizationType=UITextAutocapitalizationTypeNone;[stack addArrangedSubview:field];
    }
    UIButton* chunk=[UIButton buttonWithType:UIButtonTypeSystem];[chunk setTitle:@"Read unchanged imported original chunk" forState:UIControlStateNormal];
    chunk.accessibilityIdentifier=@"snapshot.share.archive.chunk";[chunk addTarget:self action:@selector(readOriginalChunk) forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:chunk];
    for (NSArray* control in @[@[@"Retire this imported original",@"snapshot.share.archive.retire",@"retireOriginal"],
            @[@"Inspect original retirement",@"snapshot.share.archive.retire-inspect",@"inspectRetirement"],
            @[@"Seal original admission reader",@"snapshot.share.archive.admission-seal",@"sealAdmission"]]) {
        BOOL seal=[control[1] isEqual:@"snapshot.share.archive.admission-seal"];
        UIButton* action=seal?[[OVTShareAdmissionSealButton alloc] initWithFrame:CGRectZero]:[UIButton buttonWithType:UIButtonTypeSystem];
        if (seal) {[action setTitleColor:UIColor.systemBlueColor forState:UIControlStateNormal];}
        [action setTitle:control[0] forState:UIControlStateNormal];
        action.accessibilityIdentifier=control[1];[action addTarget:self action:NSSelectorFromString(control[2]) forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:action];
    }
    self.status=[UILabel new];self.status.numberOfLines=0;self.status.accessibilityIdentifier=@"snapshot.share.archive.status";
    self.status.text=@"No original imported";[stack addArrangedSubview:self.status];
    self.admissionSealOriginal=[OVTShareAdmissionSealOriginal new];self.admissionSealOriginal.text=@"Original admission seal";
    self.admissionSealOriginal.accessibilityIdentifier=@"snapshot.share.archive.admission-seal-original";
    [stack addArrangedSubview:self.admissionSealOriginal];
    OVTShareSourceInventoryButton* inventory=[[OVTShareSourceInventoryButton alloc] initWithFrame:CGRectZero];inventory.source=self.sources;
    [inventory setTitle:@"Inspect frozen source originals" forState:UIControlStateNormal];[inventory setTitleColor:UIColor.systemBlueColor forState:UIControlStateNormal];
    inventory.accessibilityIdentifier=@"snapshot.share.archive.source-inventory";
    [inventory addTarget:self action:@selector(inspectSourceOutputs) forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:inventory];
    OVTShareSourceInventoryOriginal* original=[OVTShareSourceInventoryOriginal new];original.source=self.sources;original.text=@"Original source inventory";
    original.accessibilityIdentifier=@"snapshot.share.archive.source-inventory-original";[stack addArrangedSubview:original];
}
- (void)sealAdmission {
    NSDictionary* original=[OVTSnapshotCompanionIdentity.shared sealArchiveAdmission:self.queryField.text];
    NSData* raw=original?OVTSnapshotCompanionIdentity.shared.archiveAdmissionSealBytes:nil;
    if (original) {[self.sources freezeWithAdmissionSeal:raw];}
    self.status.text=raw?@"Original admission close result retained":@"Original admission reader remains owned or unknown";
}
- (void)inspectSourceOutputs {
    self.status.text=[self.sources inventory:self.queryField.text]?@"Original frozen source inventory retained":@"Source originals remain owned or unknown";
}
- (void)importOriginal {
    if (self.sources.producersFrozen) {self.status.text=@"Original source producers are sealed";return;}
    NSString* run=self.runField.text;NSURL* group=OVTShareGroup();
    if (!group || !OVTShareMatch(run,@"\\A[0-9a-f]{32}\\z")) {self.status.text=@"Invalid original identity";return;}
    NSURL* original=[group URLByAppendingPathComponent:[@"snapshot-share-" stringByAppendingString:run] isDirectory:YES];
    NSURL* metadataURL=[original URLByAppendingPathComponent:@"share-original.json"];struct stat metadataFirst,metadataAfter;
    BOOL metadataPinned=lstat(metadataURL.fileSystemRepresentation,&metadataFirst)==0;
    NSData* metadata=metadataPinned?OVTShareReadMetadata(metadataURL):nil;
    metadataPinned=metadata && lstat(metadataURL.fileSystemRepresentation,&metadataAfter)==0
        && [OVTShareFileRevision(metadataFirst) isEqual:OVTShareFileRevision(metadataAfter)];
    id record=metadata?[NSJSONSerialization JSONObjectWithData:metadata options:0 error:nil]:nil;
    if (!metadataPinned || ![record isKindOfClass:NSDictionary.class] || ![record[@"iosSnapshotShareOriginalVersion"] isEqual:@2]
            || ![record[@"runId"] isEqual:run] || ![record[@"phase"] isEqual:@"complete"]
            || ![record[@"artifact"] isEqual:@"original.bytes"]) {self.status.text=@"No completed original";return;}
    BOOL finished=NO;for (NSDictionary* event in record[@"events"]) {if ([event[@"kind"] isEqual:@"finish-issued"]) {finished=YES;}}
    if (!finished) {self.status.text=@"Finish the actual Share receiver first";return;}
    struct stat groupBefore,sourceBefore;
    if (lstat(original.fileSystemRepresentation,&groupBefore)!=0 || ![OVTShareRootIdentity(groupBefore) isEqual:record[@"rootIdentity"]]
        || lstat([original URLByAppendingPathComponent:@"original.bytes"].fileSystemRepresentation,&sourceBefore)!=0
        || !S_ISREG(sourceBefore.st_mode) || sourceBefore.st_nlink!=1 || sourceBefore.st_uid!=geteuid() || (sourceBefore.st_mode&0777)!=0600
        || ![OVTShareFileRevision(sourceBefore) isEqual:record[@"artifactRevision"]]) {self.status.text=@"Original source identity changed";return;}
    NSURL* documents=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL* output=[documents URLByAppendingPathComponent:[@"snapshot-share-" stringByAppendingString:run] isDirectory:YES];
    if (mkdir(output.fileSystemRepresentation,0700)!=0) {self.status.text=@"Existing responsibility; import will not repeat";return;}
    struct stat outputBirth;if (lstat(output.fileSystemRepresentation,&outputBirth)!=0 || !OVTShareRootIdentity(outputBirth)) {self.status.text=@"Import root identity unavailable";return;}
    NSDictionary* before=OVTShareClock();
    NSDictionary* intent=@{@"iosSnapshotShareImportVersion":@2,@"runId":run,@"phase":@"issued",@"clockBefore":before,
        @"instance":OVTShareID(),@"processId":@(NSProcessInfo.processInfo.processIdentifier),@"bundleId":NSBundle.mainBundle.bundleIdentifier,
        @"clockDomain":@"native-share-archive",@"basename":record[@"basename"],@"artifactRevision":NSNull.null,
        @"archiveRootIdentity":OVTShareRootIdentity(outputBirth),@"sourceArtifactRevision":record[@"artifactRevision"],@"groupRootIdentity":record[@"rootIdentity"]};
    NSData* intentBytes=[NSJSONSerialization dataWithJSONObject:intent options:0 error:nil];struct stat intentFirst,extensionFirst,importFirst;
    if (!OVTShareWrite(output,@"import-intent.json",intentBytes)
        || lstat([output URLByAppendingPathComponent:@"import-intent.json"].fileSystemRepresentation,&intentFirst)!=0) {self.status.text=@"Import intent failed";return;}
    NSString* hash=nil,*revision=nil;NSUInteger count=0;
    BOOL copied=OVTShareCopyFileAnchored([original URLByAppendingPathComponent:@"original.bytes"],[output URLByAppendingPathComponent:@"original.bytes"],&hash,&count,&revision);
    NSData* after=OVTShareReadMetadata([original URLByAppendingPathComponent:@"share-original.json"]);
    struct stat groupAfter,sourceAfter;
    copied=copied && lstat(original.fileSystemRepresentation,&groupAfter)==0 && [OVTShareRootIdentity(groupAfter) isEqual:record[@"rootIdentity"]]
        && lstat([original URLByAppendingPathComponent:@"original.bytes"].fileSystemRepresentation,&sourceAfter)==0
        && [OVTShareFileRevision(sourceAfter) isEqual:record[@"artifactRevision"]];
    if (!copied || ![metadata isEqualToData:after] || ![record[@"sha256"] isEqual:hash] || ![record[@"byteCount"] isEqual:@(count)]
            || !OVTShareWrite(output,@"original-extension.json",metadata)
            || lstat([output URLByAppendingPathComponent:@"original-extension.json"].fileSystemRepresentation,&extensionFirst)!=0) {self.status.text=@"Original changed or failed; responsibility retained";return;}
    unsigned char raw[CC_SHA256_DIGEST_LENGTH];CC_SHA256(metadata.bytes,(CC_LONG)metadata.length,raw);NSMutableString* metadataHash=[NSMutableString new];
    for (NSUInteger index=0;index<sizeof(raw);++index) {[metadataHash appendFormat:@"%02x",raw[index]];}
    NSMutableDictionary* completed=[intent mutableCopy];completed[@"phase"]=@"complete";completed[@"clockAfter"]=OVTShareClock();
    completed[@"originalMetadataSha256"]=metadataHash;completed[@"byteCount"]=@(count);completed[@"sha256"]=hash;completed[@"artifactRevision"]=revision;
    NSData* completedBytes=[NSJSONSerialization dataWithJSONObject:completed options:0 error:nil];
    BOOL saved=OVTShareWrite(output,@"import-original.json",completedBytes)
        && lstat([output URLByAppendingPathComponent:@"import-original.json"].fileSystemRepresentation,&importFirst)==0;
    if (saved) {
        self.importRecord=completed;self.outputRoot=output;
        self.retirement=[OVTShareArchiveRetirement ownerWithGroup:original archive:output imported:completed revisions:@{
            @"group/original.bytes":record[@"artifactRevision"],@"group/share-original.json":OVTShareFileRevision(metadataFirst),
            @"archive/original.bytes":revision,@"archive/original-extension.json":OVTShareFileRevision(extensionFirst),
            @"archive/import-intent.json":OVTShareFileRevision(intentFirst),@"archive/import-original.json":OVTShareFileRevision(importFirst)}
            metadata:metadata intent:intentBytes importedBytes:completedBytes sources:self.sources];
    }
    self.status.text=saved?@"Original bytes and unchanged extension ledger exposed in Documents":@"Import result failed; responsibility retained";
}
- (void)retireOriginal {
    if (self.sources.producersFrozen) {self.status.text=@"Original source producers are sealed";return;}
    self.status.text=[self.retirement retire:self.queryField.text]?@"Owned imported original retired":@"Original responsibility remains pending";
}
- (void)inspectRetirement {
    if (self.sources.producersFrozen) {self.status.text=@"Original source producers are sealed";return;}
    NSDictionary* packet=[self.retirement inspect:self.queryField.text];
    self.status.text=packet && [self.sources publish:OVTShareSourceRetireObservation bytes:[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil]]
        ?@"Actual retirement observation persisted":@"Retirement observation remains unavailable";
}
- (void)readOriginalChunk {
    if (self.sources.producersFrozen) {self.status.text=@"Original source producers are sealed";return;}
    NSString* nonce=self.queryField.text;
    if (!self.importRecord || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z") || [self.chunkNonces containsObject:nonce] || self.chunkNonces.count>=512) {self.status.text=@"Original chunk remains unavailable";return;}
    [self.chunkNonces addObject:nonce];NSDictionary* packet=OVTShareArchiveChunk(self.outputRoot,self.importRecord,nonce,self.offsetField.text);
    NSData* bytes=packet?[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil]:nil;
    self.status.text=[self.sources publish:OVTShareSourceChunk bytes:bytes]?@"Unchanged imported original chunk persisted":@"Original chunk remains unavailable";
}
@end
@interface OVTShareArchiveDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic,strong) UIWindow* window;
@end
@implementation OVTShareArchiveDelegate
- (BOOL)application:(UIApplication*)application didFinishLaunchingWithOptions:(NSDictionary*)options {
    self.window=[[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];self.window.rootViewController=[OVTShareArchive new];
    [self.window makeKeyAndVisible];return YES;
}
@end
int main(int argc,char* argv[]) {@autoreleasepool {return UIApplicationMain(argc,argv,nil,NSStringFromClass(OVTShareArchiveDelegate.class));}}
