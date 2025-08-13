from typing import Any, Dict, Generic, List, Literal, TypeVar, TypedDict

from pydantic import BaseModel, Field, RootModel

from typing_extensions import Annotated
from operator import add


def take_last(_, b):
    # in case of conflict, take the last value (branches are independent, order does not matter)
    return b


DataSource = Literal["attachment_file", "user_request", "other"]

Environment = Literal["shared", "prod", "preprod", "test", "dev"]

Operation = Literal["create", "update", "delete"]

AssetType = Literal[
    "Acetate",
    "AcetateCertificate",
    "AcetateDataSheet",
    "AcetateManufacturerCertificate",
    "AcetateProposal",
    "Attachment cached_Audit",
    "BaseMaterial",
    "BaseMaterialLibraryEntry",
    "Bom",
    "CaseItem",
    "CaseItemCertificate",
    "CaseItemTechInfo",
    "CaseItemVersion",
    "CaseManufacturerCertificate",
    "CaseSet",
    "CaseSetSupplierAssignment",
    "CatalogObjectTypeLibrary",
    "CatalogObjectTypeLibraryEntry",
    "CertificationRequest",
    "ComponentCertificate",
    "ComponentManufacturerCertificate",
    "ComponentReference",
    "ComponentSuggestedMeasure",
    "ComponentTypeLibrary",
    "ComponentTypeLibraryEntry",
    "Content",
    "Counter",
    "CustomComponent",
    "DamActivity",
    "DamBackUpData",
    "DamSeasonDate",
    "DamUser",
    "DamUserGroup",
    "DataChangeMeta",
    "DataChangeRequest",
    "DocumentInfo",
    "Eyewear",
    "EyewearAcetateLink",
    "EyewearComponentLink",
    "EyewearDesignerCertificate",
    "EyewearDropBallTest",
    "EyewearGalvanicTreatmentLink",
    "EyewearManufacturerAssignment",
    "EyewearManufacturerCertificate",
    "EyewearMediaImage",
    "EyewearMediaImagePreviewRanking",
    "EyewearTechInfo",
    "EyewearWithCaseSetLink",
    "EyewearWithComponentReferenceLink",
    "GalvanicTreatment",
    "GalvanicTreatmentCertificate",
    "GalvanicTreatmentDataSheet",
    "GalvanicTreatmentManufacturerCertificate",
    "GenericContent",
    "GenericContentCategory",
    "Hinge",
    "Lens",
    "LensDataSheet",
    "LensDataSheetRevision",
    "LensDropBallTest",
    "LensManufacturerCertificate",
    "Library",
    "LibraryEntry",
    "MainPartLibrary",
    "ManualComponent",
    "ManualGalvanicTreatment",
    "MaterialReference",
    "MigrationStatus",
    "MissingComponentRequest",
    "MissingGalvanicTreatmentRequest",
    "NosePad",
    "OptiTest",
    "Organization",
    "PackagingItem",
    "PackagingItemTechInfo",
    "PackagingItemVersion",
    "PackagingSet",
    "PackagingSetSupplierAssignment",
    "PackagingSetTechInfo",
    "PackagingSetVersion",
    "Pads",
    "PlatingMaterial",
    "PlatingMaterialCertificate",
    "PreviewImageContent",
    "Product",
    "ProductComponent",
    "ProductComponentCertificate",
    "ProductComponentSupplierAssignment",
    "ProductComponentTechInfo",
    "ProductComponentVersion",
    "ProductStatusUpdate",
    "RegionLibraryEntry",
    "Role",
    "Screw",
    "SupplierLibraryEntry",
    "TechDesign",
    "UnitOfMeasureLibrary",
    "User",
    "VmPopSnapshot",
    "Wirecore",
]

TaskType = Literal["data_migration", "other"]

Status = Literal[
    "schema_validation_passed",
    "file_selected",
    "file_selection_failed",
    "task_classification_failed",
    "data_migration_detected",
    "data_migration_classified",
    "data_migration_classification_failed",
    "other",
]

T = TypeVar("T", bound=BaseModel)
P = TypeVar("P", bound=BaseModel)


class LibraryEntry(BaseModel):
    key: str = Field(
        description="The key of the library entry, which is the unique identifier."
    )


class BaseMaterialPredicate(BaseModel):
    organizationId: str = Field(description="The organization ID")
    vendorCode: str = Field(
        description="The base material vendor code, which is the key of the base material."
    )


class MaterialPatch(BaseModel):
    material: LibraryEntry = Field(
        description="The base material key, which is the key of the base material."
    )


class AssetPatch(BaseModel, Generic[P, T]):
    predicate: P = Field(description="The predicate for the base material update.")
    patch: T = Field(description="The patch for the base material update.")


class AssetPatchList(RootModel[list[AssetPatch[P, T]]], Generic[P, T]):
    pass


class AssetOperation(BaseModel):
    asset_type: AssetType = Field(description="The type of the asset.")
    operation: Operation = Field(
        description="The operation to be performed on the asset."
    )
    data_source: DataSource
    file_url: str | None = Field(
        default=None,
        description="The URL of the file if the operation is related to a file.",
    )
    data: Dict[str, Any] | None = Field(
        default=None,
        description="Data for crud operations, if applicable.",
    )

    def __setitem__(self, key, value):
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise KeyError(f"Key '{key}' does not exist in AssetOperation.")

    def __getitem__(self, item):
        return getattr(self, item)


class GithubIssue(TypedDict):
    number: int
    title: str
    body: str


class MyState(TypedDict, total=False):
    issue: GithubIssue
    user_prompt: str
    user_input: str
    status: Status
    task_data: dict | None
    detected_operations: List[AssetOperation] | None
    op: Annotated[AssetOperation | None, take_last]
    op_index: Annotated[int | None, take_last]
    results: Annotated[List[Dict[str, Any]] | None, add]
    errors: Annotated[List[Dict[str, Any]] | None, add]
    total: int | None
    done: Annotated[int | None, add]
