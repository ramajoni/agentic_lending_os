"""
Tool: request_additional_document

Generates a request for the applicant to submit a specific
missing or clarifying document. TERMINAL — pauses the case.
"""

from app.config.logger import get_logger

log = get_logger(__name__)


def request_additional_document(
    document_type: str = "",
    reason: str = "",
    applicant_id: str = "",
    **kwargs,
) -> dict:
    """Request a specific document from the applicant.

    Args:
        document_type: Type of document needed (e.g., 'address_proof', 'salary_slip').
        reason: Why this document is needed.
        applicant_id: For logging context.

    Returns:
        Dict confirming the document request was generated.
    """
    if not document_type and "documents_requested" in kwargs:
        docs = kwargs["documents_requested"]
        document_type = ", ".join(docs) if isinstance(docs, list) else str(docs)
    if not reason and "rationale" in kwargs:
        reason = kwargs["rationale"]

    log.info(
        "Tool [request_additional_document] — type='%s', applicant='%s'",
        document_type, applicant_id,
    )

    return {
        "tool": "request_additional_document",
        "is_terminal": True,
        "document_type": document_type,
        "reason": reason,
        "status": "document_request_generated",
        "message": f"Request for '{document_type}' has been generated and queued for delivery to applicant.",
        "applicant_id": applicant_id,
    }
