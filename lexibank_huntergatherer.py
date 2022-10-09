import pathlib

import attr
from bs4 import BeautifulSoup
from clldutils import jsonlib
from clldutils.misc import slug
from lingpy import ipa2tokens
from pylexibank import Dataset as BaseDataset
from pylexibank import Lexeme, Concept, FormSpec

from hgutil import parse, itersources

URL = "https://huntergatherer.la.utexas.edu"


@attr.s
class HGLexeme(Lexeme):
    Phonemic = attr.ib(default=None)
    Creator = attr.ib(default=None)


@attr.s
class HGConcept(Concept):
    Semantic_category = attr.ib(default=None)
    Database_ID = attr.ib(default=None)


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "huntergatherer"
    lexeme_class = HGLexeme
    concept_class = HGConcept
    form_spec = FormSpec(
        replacements=[
            ("From 'two' on, the numbers are borrowed from Portuguese, English, Dutch, according to which nation the group is dwelling in.", ""),
            ("[", ""),
            ("\u0300", ""),
            ("\u0075\u0335\u0303", "ʉ̃"),
            ("\u0301", ""),
            ("\u0323", ""),
            ("\u0303", ""),
            ("]", ""),
            ("0", ""),
            ("[none]", ""),
            ("[not cultivated]", ""),
            ("1", ""),
            ("2", ""),
            ("3", ""),
            ("4", ""),
            ("5", ""),
            ("6", ""),
            ("7", ""),
            ("8", ""),
            ("9", ""),
            ("3:", ""),
            ("4:", ""),
            ("5:", ""),
            ("6:", ""),
            ("1:", ""),
            ("2:", ""),
            ("maybe", ""),
            ("$", ""),
            ('"', ""),
            ("Quechua", ""),
            ("$", ""),
            ("SG OB", ""),
            ("NB", ""),
            ("^", ""),
            ("JPH", ""),
            ("Jivaro?", ""),
            ("CHM", ""),
            ("Nom. Class", ""),
            ("Nom. class", ""),
            ("no special term", ""),
            (" no name ever recorded", ""),
            ("compounded", ""),
            ("generic basket: ", ""),
            ("“breathe", ""),
            ("to be red", ""),
            ('""', ""),
            ("ngl turn off", ""),
            (">", ""),
            ("<", ""),
            (" ", "_"),

            ],
        brackets={
            "(": ")", "{": "}", "“": "”", "'": "'", "ʼ": "ʼ", "[": "]",
            "‘": "’"},
        first_form_only=True,
        separators=(";", "/", ",", "~", "&", ),
        missing_data=(")", "_", "??", "?", "[missing]", "missing", "#NAME?", "X", "[absent]", "-", "--", "...")
    )

    def _get(self, path, log):
        with self.raw_dir.temp_download(self.metadata.url + path, ".html", log) as fname:
            return BeautifulSoup(fname.read_text(encoding="utf8"), "html.parser")

    def cmd_download(self, args):
        for a in self._get("/languages", args.log).find_all("a", href=True):
            if a["href"].startswith("/languages/language/"):
                parse(self._get(a["href"], args.log), a["href"].split("/")[-1], self.raw_dir)

    @staticmethod
    def get_tokenizer():
        return lambda x, y: ipa2tokens(y, merge_vowels=False)

    def cmd_makecldf(self, args):
        concepts = args.writer.add_concepts(
            id_factory=lambda x: x.id.split("-")[-1] + "_" + slug(x.english),
            lookup_factory="Database_ID",
        )

        language_map = {lang["ID"]: lang["Glottocode"] or None for lang in self.languages}

        sources = {}
        for path in sorted(self.raw_dir.glob("*.json"), key=lambda _p: int(_p.stem)):
            data = jsonlib.load(path)
            iso = data.get("ISO 639-3")
            if iso:
                iso = iso.strip()
            args.writer.add_language(
                ID=data["id"],
                Name=data["name"],
                ISO639P3code=iso if iso not in {"no", "XXX"} else None,
                Glottocode=language_map[data["id"]],
            )

            for table in ["basic", "flora", "cult"]:
                if table not in data["tables"]:
                    continue
                for item in data["tables"][table]["rows"]:
                    item = dict(zip(data["tables"][table]["header"], item))
                    form = item["Orthographic Form"].strip()
                    if form and not "\n" in form:
                        refs = [ref for ref in itersources(item, data, sources) if ref]
                        args.writer.add_sources(*[ref.source for ref in refs])
                        href, _ = item["English"]

                        concept_database_id = href.split("/")[-1]

                        if not concepts.get(concept_database_id):
                            # https://huntergatherer.la.utexas.edu/lexical/feature/729
                            # is missing from the concept list(s)
                            continue
                        args.writer.add_lexemes(
                            Language_ID=data["id"],
                            Parameter_ID=concepts[concept_database_id],
                            Value=form,
                            Loan=bool(item["Loan Source"] or item["Wanderwort Status"]),
                            Phonemic=item["Phonemicized Form"] or None,
                            Source=["%s" % ref for ref in refs],
                            Creator=item.get("Created By"),
                            Comment=item.get("General Notes"),
                        )
