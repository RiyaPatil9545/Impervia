import re
import unicodedata


class TextPreprocessor:
    """
    Cleans and normalizes incoming user messages in memory before privacy detection.
    """

    # Matches control characters excluding standard whitespace (\n, \r, \t)
    CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
    # Matches multiple horizontal whitespace
    MULTI_SPACE_PATTERN = re.compile(r"[^\S\r\n]+")

    def preprocess(self, text: str) -> str:
        """
        Clean, normalize and normalize unicode representations.
        """
        if not text:
            return ""

        # Normalize unicode (NFKC: canonical decomposition followed by canonical composition)
        normalized = unicodedata.normalize("NFKC", text)

        # Remove invisible or binary control characters
        cleaned = self.CONTROL_CHARS_PATTERN.sub("", normalized)

        # Normalize spaces
        cleaned = self.MULTI_SPACE_PATTERN.sub(" ", cleaned)

        # Strip leading/trailing whitespaces
        return cleaned.strip()

    def segment_sentences(self, text: str) -> list[str]:
        """
        Split text into logical sentences/clauses for granular relevance/sensitive separation.
        """
        if not text:
            return []
        # Split on sentence/clause terminals (. ! ? ; : \n) keeping structure
        sentences = re.split(r"(?<=[.!?;:\n])\s+", text)
        return [s.strip() for s in sentences if s.strip()]


preprocessor = TextPreprocessor()
