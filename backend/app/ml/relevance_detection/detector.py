import re
from dataclasses import dataclass

from app.models.enums import RelevanceStatus
from app.services.privacy.preprocessing import preprocessor


@dataclass
class RelevanceAnalysisResult:
    status: RelevanceStatus
    academic_score: float
    has_academic_intent: bool
    academic_text: str | None
    non_academic_text: str | None


class AcademicRelevanceDetector:
    """
    Analyzes whether input text contains legitimate academic queries
    and separates academic components from personal/sensitive venting.
    """

    ACADEMIC_INTENT_PATTERNS = [
        r"\b(?:explain|solve|calculate|derive|prove|summarize|define|analyze)\b",
        r"\b(?:what\s+is|what\s+are|how\s+does|how\s+do|why\s+does|why\s+is)\b",
        r"\b(?:difference\s+between|compare\s+and\s+contrast|help\s+me\s+understand)\b",
        r"\b(?:theorem|formula|algorithm|equation|hypothesis|proof|derivation)\b",
        r"\b(?:homework|assignment|exam|quiz|lecture|syllabus|coursework)\b",
    ]

    ACADEMIC_DOMAINS = [
        # Computer Science & Engineering
        r"\b(?:algorithm|binary\s+tree|data\s+structure|time\s+complexity|big\s*o|sorting|graph|compiler|sql|database|dbms|normalization|bcnf|relational|schema|recursion|pointer|object\s+oriented|polymorphism|tcp|udp|osi\s+model|ip\s+address|cryptography|machine\s+learning|neural\s+network)\b",
        # Mathematics & Statistics
        r"\b(?:calculus|derivative|integral|eigenvalue|eigenvector|matrix|determinant|differential\s+equation|linear\s+algebra|probability|normal\s+distribution|hypothesis\s+test|standard\s+deviation|fourier|laplace)\b",
        # Natural Sciences
        r"\b(?:thermodynamics|newton'?s\s+law|quantum|kinematics|electromagnetism|photon|entropy|organic\s+chemistry|stoichiometry|covalent|dna|rna|mitosis|meiosis|photosynthesis|enzyme|protein|cellular\s+respiration)\b",
        # Humanities & Social Sciences
        r"\b(?:renaissance|industrial\s+revolution|world\s+war|cold\s+war|french\s+revolution|microeconomics|macroeconomics|inflation|gdp|fiscal\s+policy|cognitive\s+bias|operant\s+conditioning|behaviorism|epistemology|utilitarianism)\b",
    ]

    def __init__(self) -> None:
        self.intent_regexes = [re.compile(p, re.IGNORECASE) for p in self.ACADEMIC_INTENT_PATTERNS]
        self.domain_regexes = [re.compile(p, re.IGNORECASE) for p in self.ACADEMIC_DOMAINS]

    def _clean_punctuation(self, text: str) -> str:
        """Collapse multiple punctuation marks and clean up spacing."""
        if not text:
            return ""
        cleaned = re.sub(r"([.!?,;:])\1+", r"\1", text)
        cleaned = re.sub(r"[\s,;:-]+(?=[.!?])", "", cleaned)
        cleaned = re.sub(r"[\s,;:-]+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _score_sentence(self, sentence: str) -> float:
        score = 0.0
        for rx in self.intent_regexes:
            if rx.search(sentence):
                score += 0.4
        for rx in self.domain_regexes:
            if rx.search(sentence):
                score += 0.6
        return min(score, 1.0)

    def analyze(
        self,
        text: str,
        has_sensitive: bool = False,
        sensitive_texts: list[str] | None = None,
    ) -> RelevanceAnalysisResult:
        if not text or not text.strip():
            return RelevanceAnalysisResult(
                status=RelevanceStatus.not_applicable,
                academic_score=0.0,
                has_academic_intent=False,
                academic_text=None,
                non_academic_text=None,
            )

        cleaned_input = self._clean_punctuation(text)
        sentences = preprocessor.segment_sentences(cleaned_input)
        if not sentences:
            sentences = [cleaned_input]

        sens_texts = [st.lower() for st in (sensitive_texts or [])]

        academic_sentences: list[str] = []
        non_academic_sentences: list[str] = []
        total_score = 0.0

        for sentence in sentences:
            s_clean = self._clean_punctuation(sentence)
            s_lower = s_clean.lower()
            is_sensitive_sentence = any(st in s_lower for st in sens_texts) if sens_texts else False

            s_score = self._score_sentence(s_clean)
            total_score += s_score

            if s_score >= 0.4 and not is_sensitive_sentence:
                if not s_clean.endswith((".", "?", "!")):
                    s_clean += "."
                academic_sentences.append(s_clean)
            elif is_sensitive_sentence:
                # Attempt to isolate valid academic portion from sensitive clause
                isolated = s_clean
                for st in sens_texts:
                    isolated = re.sub(re.escape(st), "", isolated, flags=re.IGNORECASE)
                isolated = re.sub(r"^[\s,;:.-]+|[\s,;:.-]+$", "", isolated)
                isolated = re.sub(r"^(?:and|but|also|so|then|please)\s+", "", isolated, flags=re.IGNORECASE).strip()
                isolated = self._clean_punctuation(isolated)

                isolated_score = self._score_sentence(isolated) if isolated else 0.0
                if isolated_score >= 0.4 and len(isolated.split()) >= 2:
                    if not isolated.endswith((".", "?", "!")):
                        isolated += "."
                    academic_sentences.append(isolated)
                    non_academic_sentences.append(s_clean)
                else:
                    non_academic_sentences.append(s_clean)
            else:
                non_academic_sentences.append(s_clean)

        avg_score = total_score / len(sentences) if sentences else 0.0
        has_academic = len(academic_sentences) > 0

        academic_part = " ".join(academic_sentences).strip() if academic_sentences else None
        non_academic_part = " ".join(non_academic_sentences).strip() if non_academic_sentences else None

        if has_academic and has_sensitive:
            status = RelevanceStatus.mixed
        elif has_academic:
            status = RelevanceStatus.relevant
        elif has_sensitive:
            status = RelevanceStatus.not_relevant
        elif avg_score < 0.2 and len(text.split()) < 3:
            status = RelevanceStatus.unclear
        else:
            status = RelevanceStatus.not_relevant

        return RelevanceAnalysisResult(
            status=status,
            academic_score=round(avg_score, 3),
            has_academic_intent=has_academic,
            academic_text=academic_part,
            non_academic_text=non_academic_part,
        )


academic_relevance_detector = AcademicRelevanceDetector()
