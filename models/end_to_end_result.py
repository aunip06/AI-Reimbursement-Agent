from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.claim import Claim
from models.claim_evidence import ClaimEvidence
from models.claim_processing_result import ClaimProcessingResult


WorkflowStatus = Literal[
    "LOCAL_ERROR",
    "COMPLETED",
]


class EndToEndClaimResult(BaseModel):
    """
    Complete result for one Excel claim processed against
    its exact mapped PDF page.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    claim: Claim

    evidence: ClaimEvidence

    processing_result: ClaimProcessingResult | None = None

    workflow_status: WorkflowStatus

    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_workflow_result(self):
        if self.evidence.status == "READY":
            if self.processing_result is None:
                raise ValueError(
                    "READY evidence requires a processing result."
                )

            if self.workflow_status != "COMPLETED":
                raise ValueError(
                    "READY evidence requires workflow_status=COMPLETED."
                )

        if self.evidence.status != "READY":
            if self.processing_result is not None:
                raise ValueError(
                    "Local evidence errors must not contain "
                    "an agent-processing result."
                )

            if self.workflow_status != "LOCAL_ERROR":
                raise ValueError(
                    "Evidence preparation failure requires "
                    "workflow_status=LOCAL_ERROR."
                )

        return self