# YAML in, iCalendar out

## YAML event file format

The top-level object is a mapping with two recognized keys: `calendar` and
`events`.  Other keys may be present but are ignored.

`calendar` is a mapping with the following keys, most of which set properties
on the top-level VCALENDAR object:

- `name`: the name of the calendar.
- `description`: the calendar description.
- `url`: "a location where a more dynamic rendition of the calendar information
  can be found" (the URL property).
- `published': a mapping with a `url` key where the ICS is published.  If
  supplied, this becomes the SOURCE property and an UPDATE-INTERVAL of one week
  is set.
- `languages`: currently ignored, but see below for translation information.
- `organizer`: (required) a mapping describing the organizer of the events;
  this sets the ORGANIZER property on each VEVENT.  Keys:
    - `cn`: becomes the CN (common name) parameter.
    - `uri`: becomes the ORGANIZER property value.

`events` is a sequence of mappings.  The order in YAML is the order in which
the VEVENT components appear in the ICS output.  This is significant only for
matching them up later, such as for generated UID values.

Each event mapping in `events` must specify the event time using either `start`
or `date` and `time`.  Date and time parsing formats are listed in `*_FORMATS`
constants.

- `start` and `end`: date-time values (`end` is optional).
- `date`, `time`, and `endtime`: separate date and time values (`endtime` is
  optional).

The following keys are also required:

- `title`: becomes the event SUMMARY (so perhaps this should be renamed).
- `description`: becomes the event DESCRIPTION.

The following keys are also optional:

- `uid`: the UID property; if missing, a random UUID will be generated (as
  recommended in RFC 7986).
- location: the LOCATION property.
- url: the URL property.

Recall that the ORGANIZER property, though it applies to a VEVENT, is set under
the `calendar` section.

Other keys are ignored (but may be used by templates.)

The values for `title`, `location`, `url`, and `description` may be given the
YAML tag `!jinja`.  They will then be treated as Jinja2 templates.  Within the
template, the items from this event mapping are available as variables.  If a
template uses a variable whose value would be a `!jinja` template, that
template is rendered first so the variable's value is actually the *rendered*
template.

Note that the YAML parser (`ruamel.yaml`) doesn't seem to support folded block
scalars.
