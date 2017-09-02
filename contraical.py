#!/usr/bin/env python3
from copy import copy
from datetime import datetime, timedelta
from uuid import uuid4

# pip install arrow icalendar ruamel.yaml
import arrow
from icalendar import Calendar, Event
from icalendar import Timezone, TimezoneDaylight, TimezoneStandard
from icalendar import vCalAddress, vText, vUri, vDuration, vRecur
from ruamel import yaml

def main():
    with open('cm.yaml') as f:
        data = yaml.safe_load(f)

    for lang in ('en', 'fr'):
        cal = make_ical(data['dances'], lang)
        with open('ContraMontreal.{}.ics'.format(lang), 'wb') as f:
            f.write(cal.to_ical())

# TODO: make items like "registration deadline" transparent.
TIME_FORMATS = ['h:mmA', 'h:mm A', 'hA', 'h A']
TZID = 'America/Montreal'
GROUP_KEYWORDS = ("and", "et", ",", "&", "On Call")
URI_P = "https://csclub.uwaterloo.ca/~ptsimony/calendars/ContraMontreal.{}.ics"
def make_ical(dances, lang=None):
    cal = Calendar()
    cal.add('prodid', '-//PTS//contraical.py//EN')
    cal.add('version', '2.0')
    cal.add('method', 'PUBLISH')
    cal.add('calscale', 'GREGORIAN')
    cal.add('x-wr-calname', "ContraMontreal")
    #cal.add('x-wr-caldesc', calendar description)
    cal.add('url', "http://contramontreal.org/") # calext draft
    source_uri = vUri(URI_P.format(lang))
    source_uri.params['value'] = 'URI'
    cal.add('source', source_uri) # calext draft
    refresh_interval = vDuration(timedelta(weeks=1)) # should be "P1W"
    refresh_interval.params['VALUE'] = 'DURATION'
    cal.add('x-published-ttl', refresh_interval)
    cal.add('refresh-interval', refresh_interval) # calext draft

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


    organizer = vCalAddress("http://contramontreal.org/")
    organizer.params['cn'] = vText("ContraMontreal")

    dances = translate_dance_data(dances, lang)
    for dance in dances:
        band, caller = dance['performers'].split(' / ', 1)
        multicallers = any(x in caller for x in GROUP_KEYWORDS)
        description = "Band: {}\nCaller{}: {}".format(
                band, "s" if multicallers else "", caller)
        if lang == 'fr':
            description = "Musiciens: {}\nCalleur{}: {}".format(
                    band, "s" if multicallers else "", caller)

        date = arrow.get(dance['date'], 'dddd, MMMM D, YYYY').date()
        a_start = arrow.get(dance['time'], TIME_FORMATS)
        start = dt_ical(datetime.combine(date, a_start.time()))
        if 'endtime' in dance:
            a_end = arrow.get(dance['endtime'], TIME_FORMATS)
            end = dt_ical(datetime.combine(date, a_end.time()))
        else:
            end = None

        event = Event()
        event.add('uid', make_uid())
        event.add('dtstamp', datetime.utcnow())
        event.add('dtstart', start)
        if end: event.add('dtend', end)
        event.add('summary', dance['title'])
        event.add('location', dance['location'])
        event.add('description', description)
        event.add('organizer', organizer)
        cal.add_component(event)

    return cal

def translate_dance_data(dances, lang):
    '''Return a copy of dances with the correct language selected.

    Replace the value for each foo property with the value of foo[lang].
    E.g. {title: Contra dance, title[fr]: Contredanse} becomes
         {title: Contredance, title[fr]: Contredanse} if lang == 'fr'
    Keys with no translation in the selected language are unchanged.
    Nested dictionaries are not handled.
    '''
    langtag = '[{}]'.format(lang)
    def translate(dance):
        translated = copy(dance)
        for key in dance:
            if key.endswith(langtag):
                base_key = key[:-len(langtag)]
                translated[base_key] = dance[key]
        return translated
    return [translate(dance) for dance in dances]


def dt_ical(dt):
    '''Convert a datetime to a vProperty'''
    arw = arrow.get(dt)
    prop = vText(arw.format('YYYYMMDDTHHmmss'))
    prop.params['TZID'] = TZID
    return prop

def make_uid():
    return str(uuid4())

if __name__ == '__main__':
    main()
