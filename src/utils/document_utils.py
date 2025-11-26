import logging

from src.data.dataloader import load_document_to_dataframe
from src.retriever.passages import PassageBuilder

logger = logging.getLogger(__name__)


class DocumentUtils:
    @staticmethod
    def convert_document_to_passages(document_path: str) -> list[dict]:
        """
        Convert a document (DOCX or PDF) to a list of text passages.
        This is a placeholder implementation. Actual implementation would
        involve reading the document and splitting it into passages.
        """
        logger.info(f"Loading document from: {url}")
        df = load_document_to_dataframe(url)
        passages = PassageBuilder.build_passages_from_records(df)
        logger.info(f"Loaded {len(passages)} passages from document")
        return passages
