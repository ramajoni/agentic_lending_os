"""
DAG Node 1 — Document field extraction.

Simulates extracting structured fields from submitted documents.
In a real system this would use OCR/parsing; here it copies from
the application payload since documents are already structured.
"""

from app.models.applicant import LoanApplication, ExtractedFields
from app.config.logger import get_logger

log = get_logger(__name__)


def extract_fields(application: LoanApplication) -> ExtractedFields:
    """Extract and normalize fields from the loan application and its documents.

    Args:
        application: The validated loan application.

    Returns:
        ExtractedFields with values from documents and the application.
    """
    log.info("DAG extraction — processing applicant %s", application.applicant_id)

    # In a real system, this would parse each document via OCR.
    # For the POC, we simulate extraction by copying from the structured input
    # and adding minor variations that a real OCR system might produce.
    extracted = ExtractedFields(
        applicant_id=application.applicant_id,
        name_from_pan=application.applicant_name,
        name_from_aadhaar=application.applicant_name,
        dob_from_pan=application.date_of_birth,
        dob_from_aadhaar=application.date_of_birth,
        address_from_aadhaar=application.address,
        income_from_itr=application.annual_income,
        income_from_bank_statement=application.annual_income,
        gst_business_name="",
        gst_business_address="",
        pan_number=application.pan_number,
        aadhaar_number=application.aadhaar_number,
        gst_number=application.gst_number,
    )

    # Pull data from submitted documents if present
    for doc in application.documents:
        content = doc.content
        if doc.document_type.value == "pan_card":
            extracted.name_from_pan = content.get("name", extracted.name_from_pan)
            extracted.dob_from_pan = content.get("dob", extracted.dob_from_pan)
        elif doc.document_type.value == "aadhaar_card":
            extracted.name_from_aadhaar = content.get("name", extracted.name_from_aadhaar)
            extracted.dob_from_aadhaar = content.get("dob", extracted.dob_from_aadhaar)
            extracted.address_from_aadhaar = content.get("address", extracted.address_from_aadhaar)
        elif doc.document_type.value == "itr":
            extracted.income_from_itr = content.get("income", extracted.income_from_itr)
        elif doc.document_type.value == "bank_statement":
            extracted.income_from_bank_statement = content.get("income", extracted.income_from_bank_statement)
        elif doc.document_type.value == "gst_certificate":
            extracted.gst_business_name = content.get("business_name", "")
            extracted.gst_business_address = content.get("business_address", "")

    log.info("DAG extraction — completed for applicant %s", application.applicant_id)
    return extracted
