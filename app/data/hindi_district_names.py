"""Hindi (Devanagari) district-name aliases, for content-derived geography
tagging (app/processing/geography.py) on Hindi-language sources - most
notably local outlets like City News Rajasthan, whose article descriptions
reliably open with the district name in Hindi followed by a danda ("।")
or a period, e.g. "बूंदी। जिला..." ("Bundi. District...") - confirmed by
direct inspection of that outlet's real feed content, not a guess.

PROVENANCE AND CONFIDENCE - same caveat as district_seed.py: these
Devanagari spellings were generated from training-data knowledge, not
cross-checked against an authoritative source, since this build
environment's network egress blocks every reference site the same way it
blocks every news domain used elsewhere in this codebase. Standard
district-name spellings are far less prone to the "genuinely multiple
real spellings in use" problem english transliteration collisions cause
elsewhere in this codebase (district_seed.py's own docstring), but treat
this as needing the same verification pass before relying on it for
anything client-facing.

SCOPE: Rajasthan only so far - the state where the Hindi-leading-city-name
description pattern was actually found. Extending to other states'
districts (and eventually other Indian languages - Section user directly
asked for this) is a mechanical, self-contained addition to
HINDI_DISTRICT_NAMES below, same shape as district_seed.py's own SCOPE
note.
"""

# (Hindi name, English district name) - the English name must match
# district_seed.py's DISTRICTS spelling exactly, so a resolved Hindi name
# can be used as a direct district key everywhere else in the app.
HINDI_DISTRICT_NAMES: list[tuple[str, str]] = [
    ("अजमेर", "Ajmer"),
    ("अलवर", "Alwar"),
    ("बांसवाड़ा", "Banswara"),
    ("बारां", "Baran"),
    ("बाड़मेर", "Barmer"),
    ("भरतपुर", "Bharatpur"),
    ("भीलवाड़ा", "Bhilwara"),
    ("बीकानेर", "Bikaner"),
    ("बूंदी", "Bundi"),
    ("चित्तौड़गढ़", "Chittorgarh"),
    ("चूरू", "Churu"),
    ("दौसा", "Dausa"),
    ("धौलपुर", "Dholpur"),
    ("डूंगरपुर", "Dungarpur"),
    ("हनुमानगढ़", "Hanumangarh"),
    ("जयपुर", "Jaipur"),
    ("जैसलमेर", "Jaisalmer"),
    ("जालौर", "Jalore"),
    ("झालावाड़", "Jhalawar"),
    ("झुंझुनू", "Jhunjhunu"),
    ("जोधपुर", "Jodhpur"),
    ("करौली", "Karauli"),
    ("कोटा", "Kota"),
    ("नागौर", "Nagaur"),
    ("पाली", "Pali"),
    ("प्रतापगढ़", "Pratapgarh"),
    ("राजसमंद", "Rajsamand"),
    ("सवाई माधोपुर", "Sawai Madhopur"),
    ("सीकर", "Sikar"),
    ("सिरोही", "Sirohi"),
    ("श्री गंगानगर", "Sri Ganganagar"),
    ("गंगानगर", "Sri Ganganagar"),
    ("टोंक", "Tonk"),
    ("उदयपुर", "Udaipur"),
]
