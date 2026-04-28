import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Set


@dataclass
class Analysis:
    surface: str
    lemma: str
    analysis: str
    weight: float


class MorAzClient:
    """
    Python client for MorAz running inside a Docker container.

    It calls:

        docker exec -i <container_name> hfst-lookup <analyzer_path>

    and sends words through stdin.

    Example:
        from moraz_client import MorAzClient

        moraz = MorAzClient()
        print(moraz.normalize_word("quşların"))
        print(moraz.normalize_text("balığın güllərin məhsulları"))
    """

    def __init__(
        self,
        container_name: str = "moraz-hfst",
        analyzer_path: str = "/MorAz/az.inv.hfst",
        timeout: int = 30,
    ):
        self.container_name = container_name
        self.analyzer_path = analyzer_path
        self.timeout = timeout

    def _lookup_raw(self, words: List[str]) -> str:
        if not words:
            return ""

        input_text = "\n".join(words) + "\n"

        cmd = [
            "docker",
            "exec",
            "-i",
            self.container_name,
            "hfst-lookup",
            self.analyzer_path,
        ]

        proc = subprocess.run(
            cmd,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=self.timeout,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                "MorAz lookup failed.\n"
                f"Command: {' '.join(cmd)}\n"
                f"STDERR:\n{proc.stderr}\n"
                f"STDOUT:\n{proc.stdout}"
            )

        return proc.stdout

    @staticmethod
    def _parse_output(output: str, requested_words: List[str]) -> Dict[str, List[Analysis]]:
        results: Dict[str, List[Analysis]] = {w: [] for w in requested_words}

        for raw_line in output.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            # hfst-lookup may print prompts like:
            # > quşların\tquş<NOM><Num:Pl>...\t0.000000
            if line.startswith("> "):
                line = line[2:].strip()
            elif line == ">":
                continue

            parts = line.split("\t")

            if len(parts) < 3:
                continue

            surface, analysis_str, weight_str = parts[0], parts[1], parts[2]

            if analysis_str == "+?":
                continue

            lemma = analysis_str.split("<", 1)[0]

            try:
                weight = float(weight_str)
            except ValueError:
                weight = 0.0

            results.setdefault(surface, []).append(
                Analysis(
                    surface=surface,
                    lemma=lemma,
                    analysis=analysis_str,
                    weight=weight,
                )
            )

        return results

    def analyze_many(self, words: List[str]) -> Dict[str, List[Analysis]]:
        normalized_words = [w.strip().lower() for w in words if w and w.strip()]

        if not normalized_words:
            return {}

        output = self._lookup_raw(normalized_words)
        return self._parse_output(output, normalized_words)

    def analyze_word(self, word: str) -> List[Analysis]:
        word = word.strip().lower()

        if not word:
            return []

        return self.analyze_many([word]).get(word, [])

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Simple Azerbaijani-aware tokenizer.

        Keeps Azerbaijani letters and digits.
        """
        return re.findall(r"[0-9A-Za-zƏəÖöÜüĞğÇçŞşİı]+", text.lower())

    @staticmethod
    def has_unsafe_lexical_suffix(word: str) -> bool:
        """
        These suffixes often create new lexical meaning.

        For search normalization, we usually do not want:
            südlü -> süd
            yağlı -> yağ
            balıqçı -> balıq
            duzsuz -> duz
            ağaclıq -> ağac
        """
        unsafe_suffixes = (
            "lı", "li", "lu", "lü",
            "sız", "siz", "suz", "süz",
            "çı", "çi", "çu", "çü",
            "lıq", "lik", "luq", "lük",
            "laş", "ləş",
            "lan", "lən",
        )
        return word.endswith(unsafe_suffixes)

    def normalize_word(self, word: str) -> str:
        """
        Conservative search normalization.

        Rules:
        - Unknown word: keep original.
        - Dangerous lexical suffix: keep original.
        - All analyses share same lemma: return lemma.
        - Conflicting lemmas: keep original.
        """
        word = word.strip().lower()

        if not word:
            return word

        if len(word) <= 2:
            return word

        if self.has_unsafe_lexical_suffix(word):
            return word

        analyses = self.analyze_word(word)

        if not analyses:
            return word

        lemmas: Set[str] = {a.lemma for a in analyses if a.lemma}

        if len(lemmas) == 1:
            return next(iter(lemmas))

        return word

    def normalize_text(self, text: str) -> str:
        """
        Normalize a full text by tokenizing and analyzing tokens in batch.
        """
        tokens = self.tokenize(text)

        if not tokens:
            return ""

        analyzed = self.analyze_many(tokens)

        normalized: List[str] = []

        for token in tokens:
            if len(token) <= 2 or self.has_unsafe_lexical_suffix(token):
                normalized.append(token)
                continue

            analyses = analyzed.get(token, [])
            lemmas = {a.lemma for a in analyses if a.lemma}

            if len(lemmas) == 1:
                normalized.append(next(iter(lemmas)))
            else:
                normalized.append(token)

        return " ".join(normalized)
