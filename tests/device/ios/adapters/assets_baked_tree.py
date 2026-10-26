"""Closed ordinary tree deletion of a freshly owned baked FBX namespace.

Tree1 recipes and literal ownership stay unchanged. Additional hidden paths
must come from the original qualified backend/parsed lineage, never UI guesses.
Local Model/cache and remote actor/render responsibility remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters import asset_backend_evidence as evidence,asset_backend_source as source,asset_backend_work as work
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same,pack
from ios.adapters.assets_budget import operation
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput
from ios.adapters.assets_tree_controls import owned_root
from ios.adapters.assets_tree_owner import OwnedAssetsTree

VERSION=1


def fresh_baseline(packet,digest):
    """Conservative original admission; this is not a fresh global actor lock."""
    source.digest(digest);need(evidence.ready_source(packet) and all(work.drained(packet['source'][key]) for key in ('workBefore','workAfter')))
    mapping=evidence.mapping(packet);prefix='/.baked/'+digest+'/'
    need(digest not in mapping.values() and digest not in evidence.blobs(packet) and not any(path.startswith(prefix) for path in mapping))
    return prefix


def admitted_mappings(before,*,owned_prefix,derived_prefix,original_hash,qualified,baseline_blobs):
    """Conservative original before-state, checked before normal confirmation."""
    source.digest(original_hash);owned_root(owned_prefix);need(owned_prefix.startswith('/renamed-') and derived_prefix=='/.baked/'+original_hash+'/')
    original={row['path']:row['hash'] for row in before['mappings']};derived={path:digest for path,digest in original.items() if path.startswith(derived_prefix)}
    need(len(original)==len(before['mappings']) and derived and derived==qualified and not set(derived.values())&set(baseline_blobs))
    owned={path:digest for path,digest in original.items() if path.startswith(owned_prefix)}
    need(owned and set(owned.values())=={original_hash}
        and not any(digest==original_hash and not path.startswith((owned_prefix,derived_prefix)) for path,digest in original.items()))
    return dict(owned=owned,derived=derived)


def deleted_mappings(before,after,*,owned_prefix,derived_prefix,original_hash,qualified,baseline_blobs):
    """Exact mapping delta over decoded originals from independent readers."""
    delta=admitted_mappings(before,owned_prefix=owned_prefix,derived_prefix=derived_prefix,original_hash=original_hash,
        qualified=qualified,baseline_blobs=baseline_blobs)
    expected=[row for row in before['mappings'] if not row['path'].startswith((owned_prefix,derived_prefix))]
    need(len({row['path'] for row in after['mappings']})==len(after['mappings']) and same(after['mappings'],expected));return delta


class OwnedAssetsBakedTree(OwnedAssetsTree):
    def __init__(self,parsed,store,*,lock):
        need(isinstance(parsed,OwnedAssetsParsedInput));self.parsed=parsed;self.backend=parsed.baking.backend
        super().__init__(parsed.model.usage.source,store,lock=lock)

    def guard(self):
        super().guard();self.parsed.guard();need(same(self.store.read(),self.previous));return True

    def lineage(self):
        need(self.parsed.state is not None and self.parsed.state['phase']=='observed' and self.upload.files.state['resource']=='asset-stand.fbx')
        parsed=self.parsed.state['result'];baked=self.parsed.baking.state['result']['proof']
        return dict(entityId=parsed['entityId'],sourceIndex=self.parsed.state['sourceIndex'],backendIndex=self.parsed.state['backendIndex'],
            originalHash=baked['originalHash'],outputHash=baked['outputHash'],outputPath=baked['outputPath'],metaHash=baked['metaHash'])

    def decode(self,value):
        exact(value,{'iosAssetsBakedTreeOwnerVersion','runId','role','binding','fileOwnerToken','page','lineage','payload'})
        need(type(value['iosAssetsBakedTreeOwnerVersion']) is int and value['iosAssetsBakedTreeOwnerVersion']==VERSION and same(value['lineage'],self.lineage()))
        legacy={key:deepcopy(item) for key,item in value.items() if key not in ('iosAssetsBakedTreeOwnerVersion','lineage')}
        legacy['iosAssetsTreeOwnerVersion']=1;return OwnedAssetsTree.decode(self,legacy)

    def save(self):
        self.guard();value=dict(iosAssetsBakedTreeOwnerVersion=VERSION,runId=self.upload.files.run,role=self.upload.role,binding=self.upload.binding,
            fileOwnerToken=self.upload.files.state['token'],page=self.upload.state['page'],lineage=self.lineage(),payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    def authority(self):
        lineage=self.lineage();backend=self.backend
        need(backend.state is not None and backend.state['baseline'] is not None)
        baseline=backend.packet(backend.state['samples'][backend.state['baseline']-1]);prefix=fresh_baseline(baseline,lineage['originalHash'])
        qualified=backend.packet(self.parsed.backend_row(lineage['backendIndex']));mapping=evidence.mapping(qualified)
        derived={path:digest for path,digest in mapping.items() if path.startswith(prefix)}
        need(derived.get(lineage['outputPath'])==lineage['outputHash'] and derived.get(prefix+'meta.json')==lineage['metaHash']
            and mapping.get(self.parsed.baking.usage.path())==lineage['originalHash'])
        return lineage,prefix,derived,evidence.blobs(baseline)

    @operation
    def reserve(self):
        self.guard();self.authority();return super().reserve()

    def deleted_proof(self,before,after):
        lineage,prefix,qualified,blobs=self.authority()
        return deleted_mappings(before,after,owned_prefix=self.prefix(True),derived_prefix=prefix,original_hash=lineage['originalHash'],
            qualified=qualified,baseline_blobs=blobs)

    def delete_admission(self,proof):
        super().delete_admission(proof);lineage,prefix,qualified,blobs=self.authority()
        admitted_mappings(proof,owned_prefix=self.prefix(True),derived_prefix=prefix,original_hash=lineage['originalHash'],qualified=qualified,baseline_blobs=blobs)

    @operation
    def deletion(self):
        self.guard();need(self.state['phase']=='deleted');self.decode(self.previous)
        delta=self.deleted_proof(self.read_proof('tree-delete-admission'),self.read_proof('tree-deleted'))
        return dict(assetBakedTreeDeleteProofVersion=VERSION,runId=self.upload.files.run,role=self.upload.role,lineage=self.lineage(),
            mappings=delta,resourceRetirementAvailable=False)
