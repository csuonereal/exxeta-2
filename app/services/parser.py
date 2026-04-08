import base64
import fitz  # PyMuPDF
import io

class ParserService:
    @staticmethod
    def parse_input(input_type: str, content: str) -> str:
        if input_type == "text":
            return content
        elif input_type == "email":
            # For MVP, assume content is either raw EML text or already extracted email text
            # In a full flow, we might parse MIME/EML here
            return content
        elif input_type == "pdf":
            try:
                # content might be base64 encoded PDF
                pdf_bytes = base64.b64decode(content)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                return text
            except Exception as e:
                # fallback or error handling
                raise ValueError(f"Failed to parse PDF: {str(e)}")
        else:
            return content
