import pytesseract

from pdf2image import (
    convert_from_path
)

def extract_text_from_scanned_pdf(
    pdf_path
):

    extracted_text = ""

    # CONVERT PDF → IMAGES

    images = convert_from_path(
        pdf_path
    )

    # OCR EACH PAGE

    for image in images:

        text = pytesseract.image_to_string(
            image
        )

        extracted_text += (
            text + "\n"
        )

    return extracted_text