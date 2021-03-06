#!/usr/bin/env python3

from argparse import ArgumentParser
from copy import copy
import collections.abc
from datetime import datetime, timedelta
import itertools
from pathlib import Path
from uuid import uuid4

# pip install arrow icalendar Jinja2 ruamel.yaml
import arrow
from icalendar import Calendar, Event
from icalendar import Timezone, TimezoneDaylight, TimezoneStandard
from icalendar import vCalAddress, vText, vUri, vDuration, vRecur
import jinja2, jinja2.meta
from ruamel.yaml import YAML

def main():
    parser = ArgumentParser()
    parser.add_argument('yaml', metavar='IN.yaml', type=Path)
    parser.add_argument('ical', metavar='OUT.ical', type=Path, nargs='?',
        help="""ICS file path.  May contain '{lang}', which is replaced with
        the language code for each language.  If omitted, the stem of the YAML
        file name is used in the pattern {name}.{lang}.ics (multilingual) or
        {name}.ics (unilingual YAML spec).""")
    parser.add_argument('--update-yaml', action='store_true')
    parser.add_argument('--print-uids', action='store_true')
    parser.add_argument('--lang',
        help="Produce ICS files for the specified language only.")
    args = parser.parse_args()
    return do_main(args)

def do_main(args):
    yaml = YAML(typ='rt')
    yaml.register_class(YamlJinjaTemplate)
    yaml.register_class(YamlPluralString)
    data = yaml.load(args.yaml)

    if 'calendar' not in data:
        raise FormatError("missing top-level key 'calendar'")
    if 'events' not in data:
        raise FormatError("missing top-level key 'events'")

    langs = data['calendar'].get('languages', [])
    multilingual = len(langs) > 1

    if args.lang:
        langs = [args.lang]

    if len(langs) > 1 and args.ical and '{lang}' not in args.ical:
        print("multiple languages requested, but output filename is static")
        raise RuntimeError

    for lang in langs:
        if args.ical is None:
            if multilingual:
                name = "{}.{}.ics".format(args.yaml.stem, lang)
                ical = args.yaml.parent / name
            else:
                name = "{}.ics".format(args.yaml.stem)
                ical = args.yaml.parent / name
        else:
            ical = args.ical.format(lang=lang)

        try:
            with ical.open('rb') as f:
                old = get_events(Calendar.from_ical(f.read()))
        except FileNotFoundError:
            old = None

        cal = make_ical(data, lang, old)
        with ical.open('wb') as f:
            f.write(cal.to_ical())

        # This is probably broken
        if args.update_yaml:
            yaml.dump(data, args.yaml)

        # This should probably be different too
        if args.print_uids:
            for evdata in data['events']:
                print(evdata['uid'])

def get_events(cal):
    events = [c for c in cal.subcomponents if c.name == 'VEVENT']
    return {str(event.get('UID')): event for event in events}

class YamlJinjaTemplate:
    yaml_tag = '!jinja'

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_scalar(cls.yaml_tag, node.source)

    @classmethod
    def from_yaml(cls, constructor, node):
        return cls(node.value)

    def __init__(self, string):
        self.source = string
        self.template = jinja_env.from_string(string)

        ast = jinja_env.parse(string)
        self.refs = jinja2.meta.find_undeclared_variables(ast)

# FIXME: It's probably a mistake to make this a type/tag.
class YamlPluralString(str):
    yaml_tag = '!plural'
    plural = True

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_scalar(cls.yaml_tag, node)

    @classmethod
    def from_yaml(cls, constructor, node):
        return cls(node.value)

class TranslatedMap(collections.abc.Mapping):
    '''A proxy for a mapping with some translated entries.

    The underlying map must have keys ending with the language code in
    brackets, e.g. "foo[en]", for translated items, or no brackets if the item
    is not translated.  Language codes must be in [a-z]* but there are no
    length limits.

    Keys with no language tag are visible; keys with a language tag are exposed
    with the tag stripped (if the tag matches the selected language).

    >>> m = {'hi[en]': "Hello", 'hi[fr]': "Salut", 'date': "2017-09-08"}
    >>> tm = TranslatedMap(m, lang='en')
    >>> tm['date']
    "2017-09-08"
    >>> tm['hi']
    "Hello"
    >>> list(tm.keys())
    ['hi', 'date']
    '''
    def __init__(self, mapping, lang):
        self._mapping = mapping
        self.lang = lang

    def __getitem__(self, key):
        tr_key = '{key}[{lang}]'.format(key=key, lang=self.lang)
        if tr_key in self._mapping:
            return self._mapping[tr_key]
        return self._mapping[key]

    def __setitem__(self, key, value):
        tr_key = '{key}[{lang}]'.format(key=key, lang=self.lang)
        self._mapping[tr_key] = value

    def __contains__(self, key):
        tr_key = '{key}[{lang}]'.format(key=key, lang=self.lang)
        return tr_key in self._mapping or key in self._mapping

    def __iter__(self):
        tag = '[{lang}]'.format(lang=self.lang)
        for key in self._mapping:
            if key.endswith(tag):
                yield key[:-len(tag)]
            elif not key.endswith(']'):
                yield key

    def __len__(self):
        return sum(1 for _ in iter(self))

    def setdefault(self, key, default=None):
        '''Return `self[key]`, setting it to default if it was unset.

        If an assignment is made, it is with an untranslated key.
        '''
        if key in self:
            return self[key]
        self._mapping[key] = default
        return default

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def update(self, other):
        for key in other:
            self[key] = other[key]


TIME_FORMATS = ['h:mmA', 'h:mm A', 'hA', 'h A']
DATE_FORMATS = ['dddd, MMMM D, YYYY',
                'dddd, MMMM Do, YYYY',
                'dddd MMMM Do, YYYY',
                'dddd MMMM Do YYYY',
                'MMM D, YYYY',
                'MMM D  YYYY',
                'MMM  D  YYYY',
                'MMMM D  YYYY',
                'MMM Do, YYYY',
                'MMMM D, YYYY']
DT_FORMATS = ['YYYY-MM-DD h:mmA', 'YYYY-MM-DD h:mm']

# TZID should really be data.calendar.timezone
TZID = 'America/Toronto'

def make_ical(data, lang, old):
    caldata = TranslatedMap(data['calendar'], lang=lang)

    cal = Calendar()
    cal.add('prodid', 'yamlical.py')
    cal.add('version', '2.0')
    cal.add('method', 'PUBLISH')
    if 'name' in caldata:
        cal.add('name', caldata['name'])
        cal.add('x-wr-calname', caldata['name'])
    if 'description' in caldata:
        cal.add('description', caldata['description'])
        cal.add('x-wr-caldesc', caldata['description'])
    if 'url' in caldata:
        cal.add('url', caldata['url'])
    if 'published' in caldata:
        pubdata = TranslatedMap(caldata['published'], lang=lang)
        url = vUri(pubdata['url'])
        url.params['value'] = 'URI'
        cal.add('source', url)
        # Todo: make this come from calendar.published.refresh_interval.
        refresh_interval = vDuration(timedelta(days=1))
        refresh_interval.params['VALUE'] = 'DURATION'
        cal.add('x-published-ttl', refresh_interval)
        cal.add('refresh-interval', refresh_interval)

    add_timezone(cal)

    if 'organizer' in caldata:
        organizer = vCalAddress(caldata['organizer']['uri'])
        organizer.params['cn'] = vText(caldata['organizer']['cn'])
    else:
        organizer = None

    for evdata_raw in data['events']:
        evdata = TranslatedMap(evdata_raw, lang=lang)
        if 'overlay' in evdata:
            apply_overlay(evdata, TranslatedMap(evdata['overlay'], lang=lang))

        end = None # default if not specified
        if 'date' in evdata:
            # Calculate the start and end timestamps from time/endtime.
            date = arrow.get(evdata['date'], DATE_FORMATS).date()
            a_start = arrow.get(evdata['time'], TIME_FORMATS)
            start = datetime.combine(date, a_start.time())
            if 'endtime' in evdata:
                a_end = arrow.get(evdata['endtime'], TIME_FORMATS)
                end = datetime.combine(date, a_end.time())
        else:
            start = arrow.get(evdata['start'], DT_FORMATS)
            if 'end' in evdata:
                end = arrow.get(evdata['end'], DT_FORMATS)

        event = Event()
        uid = evdata.setdefault('uid', make_uid()) # Add uid if needed.
        event.add('uid', uid)
        event.add('dtstart', dt_ical(start))
        if end: event.add('dtend', dt_ical(end))
        event.add('summary', apply_template(evdata, 'title'))
        if 'location' in evdata:
            event.add('location', apply_template(evdata, 'location'))
        if 'url' in evdata:
            event.add('url', apply_template(evdata, 'url'))
        if 'description' in evdata:
            event.add('description', apply_template(evdata, 'description'))
        if organizer:
            event.add('organizer', organizer)
        if evdata.get('cancelled', False):
            event.add('status', 'CANCELLED')

        if old and uid in old and events_equal(event, old[uid]):
            event['DTSTAMP'] = old[uid]['DTSTAMP']
        else:
            event.add('dtstamp', datetime.utcnow())

        cal.add_component(event)

    return cal

def events_equal(event_a, event_b):
    '''Return whether two events are the same, ignoring DTSTAMP and comparing
    values by how they will be serialized.'''
    akeys = set(event_a.keys()) - {'DTSTAMP'}
    bkeys = set(event_b.keys()) - {'DTSTAMP'}

    if akeys != bkeys:
        return False

    for key in akeys:
        a, b = event_a[key], event_b[key]
        if a != b and (a.to_ical() != b.to_ical() or a.params != b.params):
            return False

    return True

jinja_env = jinja2.Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
    )

def template_urldate(date):
    '''Template filter: convert a date to the code used in Ottawa Contra URLs.
    '''
    return arrow.get(date, DATE_FORMATS).format('MMMD')

jinja_env.filters['urldate'] = template_urldate

def apply_overlay(evdata, overlay):
    '''Modify evdata by overlaying the `overlay` mapping.

    Every entry in overlay is copied into evdata, replacing an entry with a
    matching key if it exists.  When the overlay entry's value is a Jinja
    template, however, it is handled specially: the template may only refer to
    its own field name, and the replacement value is the underlying value
    before the overlay is applied.

    If the underlying value is a template that refers to overridden
    fields, the used value for those templates will not be overridden.
    '''
    computed_overlay = {}
    for field, value in overlay.items():
        if isinstance(value, YamlJinjaTemplate):
            orig_value = apply_template(evdata, field)
            new_value = value.template.render({field: orig_value})
        else:
            new_value = value
        computed_overlay[field] = new_value

    evdata.update(computed_overlay)
    return evdata

def apply_template(evdata, field, _progress=[]):
    '''If evdata[field] is a template, return the rendered template.

    (If it's not a template, return the value unchanged.)

    Instead of using Jinja's template inclusion mechanisms, template values are
    resolved recursively.  If this template uses a value whose type is a
    template, e.g. "{{foo}}", where evdata['foo'] is a template, the value
    available to this template will be the result of rendering the 'foo'
    template by the same process.
    '''
    if field in _progress:
        raise RuntimeError("template inclusion has a loop: {}".format(
            _progress))

    value = evdata[field]
    if not isinstance(value, YamlJinjaTemplate):
        return value

    progress = _progress + [field]
    fields = {k: apply_template(evdata, k, progress)
        for k in value.refs if k in evdata}

    return fold_whitespace(value.template.render(fields))

def fold_whitespace(s):
    '''Apply whitespace folding (kind of like YAML does normally).

    This comes after applying Jinja templates so that Jinja blocks don't leave
    extra line breaks around.
    '''

    def isblank(l):
        '''Return whether l is a blank line'''
        return not l or l.isspace()

    paras = ['' if blank else ' '.join(lines)
             for blank, lines in itertools.groupby(s.strip().splitlines(),
                                                   isblank)]
    return '\n'.join(paras)

def dt_ical(dt):
    '''Convert a datetime to a vProperty'''
    arw = arrow.get(dt)
    prop = vText(arw.format('YYYYMMDDTHHmmss'))
    prop.params['TZID'] = TZID
    return prop

def make_uid():
    return str(uuid4())

def add_timezone(cal):
    cal.add('x-wr-timezone', TZID)
    timezone = Timezone()
    timezone.add('tzid', TZID)
    tz_std = TimezoneStandard()
    tz_std.add('dtstart',
            vText(arrow.get('2006-11-06 02:00').format('YYYYMMDDTHHmmss')))
    tz_std.add('rrule', vRecur(freq='YEARLY', bymonth='11', byday='+1SU'))
    tz_std.add('tzoffsetfrom', timedelta(hours=-4))
    tz_std.add('tzoffsetto', timedelta(hours=-5))
    tz_std.add('tzname', "EST")
    timezone.add_component(tz_std)

    tz_dst = TimezoneDaylight()
    tz_dst.add('dtstart',
            vText(arrow.get('2006-03-13 02:00').format('YYYYMMDDTHHmmss')))
    tz_dst.add('rrule', vRecur(freq='YEARLY', bymonth='3', byday='+2SU'))
    tz_dst.add('tzoffsetfrom', timedelta(hours=-5))
    tz_dst.add('tzoffsetto', timedelta(hours=-4))
    tz_dst.add('tzname', "EDT")
    timezone.add_component(tz_dst)

    cal.add_component(timezone)

if __name__ == '__main__':
    main()
