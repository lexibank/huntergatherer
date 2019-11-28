import re
import pathlib

import attr
from clldutils import jsonlib
from bs4 import BeautifulSoup

from pylexibank import Lexeme, Concept, FormSpec
from pylexibank import Dataset as BaseDataset
from lingpy import ipa2tokens

from hgutil import parse, itersources

URL = 'https://huntergatherer.la.utexas.edu'


@attr.s
class HGLexeme(Lexeme):
    Phonemic = attr.ib(default=None)
    Creator = attr.ib(default=None)


@attr.s
class HGConcept(Concept):
    Semantic_category = attr.ib(default=None)


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = 'huntergatherer'
    lexeme_class = HGLexeme
    concept_class = HGConcept
    form_spec = FormSpec(
        missing_data=(
            '?',
            '[missing]',
            'missing',
            '#NAME?',
            'X',
            '[absent]',
            '-',
            '--',
            '...'
        )
    )

    def _get(self, path, log):
        with self.raw_dir.temp_download(
                self.metadata.url + path, self.raw_dir.joinpath('.html'), log) as fname:
            return BeautifulSoup(fname.read_text(encoding='utf8'), 'html.parser')

    def cmd_download(self, args):
        for a in self._get('/languages', args.log).find_all('a', href=True):
            if a['href'].startswith('/languages/language/'):
                parse(self._get(a['href'], args.log), a['href'].split('/')[-1], self.raw_dir)

    def get_tokenizer(self):
        return lambda x, y: ipa2tokens(y, merge_vowels=False)

    def cmd_makecldf(self, args):
        concept_map = {
            re.sub('^(\*|\$)', '', c.english): c.concepticon_id
            for c in self.conceptlists[0].concepts.values()}
        for c in self.concepts:
            concept_map[(c['ID'], c['GLOSS'])] = c['CONCEPTICON_ID'] or None
        language_map = {l['ID']: l['Glottocode'] or None for l in self.languages}

        sources = {}
        for path in sorted(self.raw_dir.glob('*.json'), key=lambda _p: int(_p.stem)):
            data = jsonlib.load(path)
            iso = data.get('ISO 639-3')
            if iso:
                iso = iso.strip()
            args.writer.add_language(
                ID=data['id'],
                Name=data['name'],
                ISO639P3code=iso if iso not in {'no', 'XXX'} else None,
                Glottocode=language_map[data['id']])

            for table in ['basic', 'flora', 'cult']:
                if table not in data['tables']:
                    continue
                for item in data['tables'][table]['rows']:
                    item = dict(zip(data['tables'][table]['header'], item))
                    form = item['Orthographic Form'].strip()
                    if form:
                        refs = [
                            ref for ref in itersources(item, data, sources) if ref]
                        args.writer.add_sources(*[ref.source for ref in refs])
                        href, concept = item['English']
                        args.writer.add_concept(
                            ID=href.split('/')[-1],
                            Name=concept,
                            Concepticon_ID=concept_map.get(concept),
                            Semantic_category=item['Semantic Field'])
                        args.writer.add_lexemes(
                            Language_ID=data['id'],
                            Parameter_ID=href.split('/')[-1],
                            Value=form,
                            Loan=bool(
                                item['Loan Source'] or item['Wanderwort Status']),
                            Phonemic=item['Phonemicized Form'] or None,
                            Source=['%s' % ref for ref in refs],
                            Creator=item.get('Created By'),
                            Comment=item.get('General Notes'),
                        )
