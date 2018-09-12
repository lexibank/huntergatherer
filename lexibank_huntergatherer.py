# coding: utf8
from __future__ import unicode_literals, print_function, division
import re

import attr
from clldutils import jsonlib
from clldutils.path import read_text, Path
from clldutils.text import split_text_with_context
from bs4 import BeautifulSoup

from clldutils.path import Path
from pylexibank.dataset import Metadata, Lexeme, Concept
from pylexibank.dataset import Dataset as BaseDataset
from lingpy import ipa2tokens

from hgutil import parse, itersources

URL = 'https://huntergatherer.la.utexas.edu'


@attr.s
class HGLexeme(Lexeme):
    Phonemic = attr.ib(default=None)
    Creator = attr.ib(default=None)


@attr.s
class HGConcept(Concept):
    Semantic_field = attr.ib(default=None)


class Dataset(BaseDataset):
    dir = Path(__file__).parent
    id = 'huntergatherer'
    lexeme_class = HGLexeme
    concept_class = HGConcept

    def _get(self, path):
        with self.raw.temp_download(
                self.metadata.url + path, self.raw.joinpath('.html'), self.log) as fname:
            return BeautifulSoup(read_text(fname), 'html.parser')

    def cmd_download(self, **kw):
        for a in self._get('/languages').find_all('a', href=True):
            if a['href'].startswith('/languages/language/'):
                parse(self._get(a['href']), a['href'].split('/')[-1], self.raw)

    def get_tokenizer(self):
        return lambda x, y: ipa2tokens(y, merge_vowels=False)

    def split_forms(self, row, value):
        value = self.lexemes.get(value, value)
        return [self.clean_form(row, form)
                for form in split_text_with_context(value, separators=',;')]

    def clean_form(self, row, form):
        form = BaseDataset.clean_form(self, row, form)
        if form not in [
            '?',
            '[missing]',
            'missing',
            '#NAME?',
            'X',
            '[absent]',
            '-',
            '--',
            '...'
        ]:
            return form

    def cmd_install(self, **kw):
        concept_map = {
            re.sub('^(\*|\$)', '', c.english): c.concepticon_id
            for c in self.conceptlist.concepts.values()}
        for c in self.concepts:
            concept_map[(c['ID'], c['GLOSS'])] = c['CONCEPTICON_ID'] or None
        language_map = {l['ID']: l['Glottocode'] or None for l in self.languages}

        sources = {}
        with self.cldf as ds:
            for path in sorted(self.raw.glob('*.json'), key=lambda _p: int(_p.stem)):
                data = jsonlib.load(path)
                iso = data.get('ISO 639-3')
                if iso:
                    iso = iso.strip()
                ds.add_language(
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
                            ds.add_sources(*[ref.source for ref in refs])
                            href, concept = item['English']
                            ds.add_concept(
                                ID=href.split('/')[-1],
                                Name=concept,
                                Concepticon_ID=concept_map.get(concept),
                                Semantic_field=item['Semantic Field'])
                            ds.add_lexemes(
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
