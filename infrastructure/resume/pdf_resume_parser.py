from pdfminer.high_level import extract_text


class PdfResumeParser:

    def extract_text(self, file_path: str) -> str:
        return extract_text(file_path)