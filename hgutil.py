# coding: utf8
from __future__ import unicode_literals, print_function, division
from collections import OrderedDict
import re

from clldutils import jsonlib

from pylexibank.util import get_reference

VALUE_MAP = {
    #'not done yet',
    #'n/a',
    #'no?',
    #'yes',
    #'check',
    #'24',
    #'1',
    #'21',
    #'no',
    #'no info',
    'approx 21': '21',
    #'yes?',
    #'0',
    #'3',
    #'2',
    #'5',
    #'4',
    #'7',
    #'6',
    #'8',
    #'2+',
    #'unclear',
    'yes, 3': '3',
    'not clear': 'unclear',
    'no applicable': 'n/a',
    #'6-7',
    #'11',
    #'10',
    #'13',
    #'12',
    #'15',
    'maybe': 'unclear',
    'no info.': 'no info',
    #'36',
    #'5+',
    #'other',
}


def parse_dl(dl):
    key = None
    for tag in dl.children:
        if tag.name == 'dt':
            key = tag.get_text()
        elif tag.name == 'dd':
            if key not in ['id', 'name', 'tables']:
                yield key, tag.get_text()


def rows(table):
    keys = [th.get_text() for th in table.find('thead').find_all('th')]
    rows = []
    for tr in table.find('tbody').find_all('tr'):
        tds = list(tr.find_all('td'))
        assert len(tds) == len(keys)
        values = []
        for td in tds:
            link, text = td.find('a'), td.get_text()
            values.append((link['href'], text) if link else text)
        rows.append(values)
    return dict(header=keys, rows=rows)


def parse(soup, id_, outdir):
    props = {'id': id_, 'name': soup.find('h2').get_text(), 'tables': {}}
    for i, dl in enumerate(soup.find_all('dl')):
        props.update(dict(list(parse_dl(dl))))

    for frame in [
        'basic_frame', 'flora_frame', 'cult_frame', 'grammar_frame', 'ethno_frame',
    ]:
        div = soup.find('div', id=frame)
        if div:
            props['tables'][frame.split('_')[0]] = rows(div.find('table'))
    jsonlib.dump(props, outdir.joinpath('{0}.json'.format(id_)), indent=4)


PAGES = re.compile('(?P<year>[0-9]{4})\s*(:|(,|\.)\s*p\.)\s*(?P<pages>[0-9]+(\-[0-9]+)?(,\s*[0-9]+(\-[0-9]+)?)*)\s*$')
AUTHOR_YEAR = re.compile('(?P<author>\w+)\s*(,|\-)?\s+(?P<year>[0-9]{4})$')
NAMEPART = '([A-Zvdcioy\xc1][BCDIMa-z\u1ef3\xe1\xe2\xe3\xe9\xe7\xed\xef\xfa\xf4\xf3\xfc\-\.]*([A-Z]\.)*)'
NAME = '(%s)(,?\s+%s)*' % (NAMEPART, NAMEPART)
AUTHORS = '(?P<authors>(%s)(\s+(&|and)\s+%s)*)' % (NAME, NAME)
AUTHORS_YEAR = re.compile('%s\s+(\((eds|(c|C)omp|recop|compiler)\.?\)\.?\s+)?\(?(?P<year>[0-9]{4})\)?([a-z])?((\.|,)?\s+)' % AUTHORS)


def get_authors(s):
    s = re.sub('\s+and\s+', ' & ', s)
    res = []
    for v in s.split(' & '):
        if ',' in v:
            res.append(v.split(',')[0])
        else:
            res.append(v.split()[-1])
    return ' and '.join(res)


def get_author_and_year(source):
    match = AUTHORS_YEAR.match(source)
    if match:
        return (
            get_authors(match.group('authors')),
            match.group('year'),
            source[match.end():].strip())
    return None, None, source


def get_source_and_pages(source):
    match = PAGES.search(source)
    if match:
        source = source[:match.start()]
        source += match.group('year')
        pages = match.group('pages')
    else:
        pages = None
    match = AUTHOR_YEAR.match(source)
    if match:
        return (
            match.group('author').replace(' & ', ' and '),
            match.group('year'),
            source[match.end():].strip(),
            pages)
    return None, None, source, pages


def itersources(item, lang, sources):
    source = item.get('Source', '')
    if source == 'See Language page':
        source = lang['Data Sources']
    source = source.strip()
    source = source.replace('Huber, R.; Reed, R.', 'Huber, R. and Reed, R.')

    if '\n\n' in source:
        for vv in source.split('\n\n'):
            if vv.strip():
                authors, year, rem = get_author_and_year(vv.strip())
                yield get_reference(authors, year, rem, None, sources)
    elif ';' in source:
        for vv in source.split(';'):
            if vv.strip():
                authors, year, rem, pages = get_source_and_pages(vv.strip())
                yield get_reference(authors, year, rem, pages, sources)
    else:
        authors, year, rem = get_author_and_year(source)
        yield get_reference(authors, year, rem, None, sources)


"kohI, kohhi7 “small intestine, waist, abdomen”"
"ĩík [swell], pux [pot boil over]"
