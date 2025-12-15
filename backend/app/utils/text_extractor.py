"""
파일에서 텍스트를 추출하는 유틸리티
지원 형식: PDF, DOCX, TXT, XLSX
"""
from typing import BinaryIO, Union
from io import BytesIO
import PyPDF2
from docx import Document
import openpyxl


class TextExtractor:
    """파일 형식에 따라 텍스트를 추출하는 클래스"""

    @staticmethod
    def extract_from_pdf(file: Union[BinaryIO, bytes]) -> str:
        """PDF 파일에서 텍스트 추출"""
        try:
            # bytes인 경우 BytesIO로 변환
            if isinstance(file, bytes):
                file = BytesIO(file)

            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            raise ValueError(f"PDF 텍스트 추출 실패: {str(e)}")

    @staticmethod
    def extract_from_docx(file: Union[BinaryIO, bytes]) -> str:
        """DOCX 파일에서 텍스트 추출"""
        try:
            # bytes인 경우 BytesIO로 변환
            if isinstance(file, bytes):
                file = BytesIO(file)

            doc = Document(file)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            raise ValueError(f"DOCX 텍스트 추출 실패: {str(e)}")

    @staticmethod
    def extract_from_txt(file: BinaryIO) -> str:
        """TXT 파일에서 텍스트 추출"""
        try:
            # file이 이미 bytes인 경우 처리
            if isinstance(file, bytes):
                content = file
            else:
                content = file.read()

            # UTF-8로 시도, 실패하면 CP949(한글 윈도우)로 시도
            try:
                return content.decode('utf-8').strip()
            except UnicodeDecodeError:
                return content.decode('cp949').strip()
        except Exception as e:
            raise ValueError(f"TXT 텍스트 추출 실패: {str(e)}")

    @staticmethod
    def extract_from_xlsx(file: Union[BinaryIO, bytes]) -> str:
        """XLSX 파일에서 텍스트 추출 (모든 시트의 셀 내용)"""
        try:
            # bytes인 경우 BytesIO로 변환
            if isinstance(file, bytes):
                file = BytesIO(file)

            workbook = openpyxl.load_workbook(file)
            text = ""
            for sheet in workbook.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    row_text = " ".join([str(cell) for cell in row if cell is not None])
                    if row_text.strip():
                        text += row_text + "\n"
            return text.strip()
        except Exception as e:
            raise ValueError(f"XLSX 텍스트 추출 실패: {str(e)}")

    @classmethod
    def extract_text(cls, file: Union[BinaryIO, bytes], filename: str) -> str:
        """
        파일 확장자에 따라 적절한 추출 메서드를 호출

        Args:
            file: 파일 객체
            filename: 파일명 (확장자 확인용)

        Returns:
            추출된 텍스트

        Raises:
            ValueError: 지원하지 않는 파일 형식
        """
        extension = filename.lower().split('.')[-1]

        extractors = {
            'pdf': cls.extract_from_pdf,
            'docx': cls.extract_from_docx,
            'doc': cls.extract_from_docx,
            'txt': cls.extract_from_txt,
            'xlsx': cls.extract_from_xlsx,
            'xls': cls.extract_from_xlsx,
        }

        extractor = extractors.get(extension)
        if not extractor:
            raise ValueError(f"지원하지 않는 파일 형식: {extension}")

        return extractor(file)
