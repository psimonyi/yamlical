# Usage:
# python3 yamlical.py source.yaml dest.ics --list-uids > uids
# awk -f add-uids.awk source.yaml | sponge source.yaml
# (note that the uids filename is hardcoded)

# Always print the source line.
{
    print;
}

# Skip ahead until we hit the `events` section.
NR = 0, /^events:/ {
    next;
}

# Inside the `events` section, look for each item, which hopefully are the only
# lines starting with a dash.  Copy the indentation (and replace the `-` with a
# space too), then add the next UID.
/^ *- *[a-z]+:/ {
    getline uid <"uids";
    print gensub(/( *)-( *).*/, "\\1 \\2", "1") "uid: " uid;
}
