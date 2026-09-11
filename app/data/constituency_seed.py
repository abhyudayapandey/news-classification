"""Constituency reference data for app/processing/geography.py's bare-name
constituency matching - see that module's docstring for why a bare
mention (no "Lok Sabha seat"/"Vidhan Sabha seat" suffix) needs a curated
name list rather than a generic capitalized-phrase guess.

PROVENANCE AND CONFIDENCE - read before trusting this for anything
client-facing: generated from training-data knowledge, not fetched from
an authoritative source (this build environment's network egress blocks
ECI/state CEO sites the same way it blocks every news domain used
elsewhere in this codebase - see app/data/district_seed.py's docstring
for the same caveat applied to districts).

Lok Sabha (MP) seats below are seeded for the states this build is
actively being pitched in (Rajasthan, Uttar Pradesh, Punjab,
Uttarakhand) - boundaries unchanged since the 2008 delimitation, so this
is the lower-risk half of this file.

Vidhan Sabha (MLA) seats are DELIBERATELY NOT seeded here yet, even
though they matter more for a state-election pitch than Lok Sabha does -
that's exactly why the bar is higher, not lower. Uttar Pradesh alone has
403 assembly seats; free-recalling several hundred hyper-local
constituency names per state is a fundamentally less reliable exercise
than the ~25-80-seat Lok Sabha lists above, and a wrong or missing seat
name is the kind of error a political client notices immediately. Source
these from each state's official delimitation list (ECI or the state
Chief Electoral Officer's site) before seeding MLA rows - don't extend
this list by free recall the way the rest of it was built.
"""

from app.models.enums import SeatType

# (constituency name, state, seat_type) - state values match
# app/processing/jurisdiction.py's INDIAN_STATES spelling exactly, so a
# guessed state and a guessed constituency can be cross-checked against
# each other. seat_type distinguishes a same-named Lok Sabha vs Vidhan
# Sabha seat (a real, common collision - see SeatType's own docstring).
CONSTITUENCIES: list[tuple[str, str, SeatType]] = [
    # Rajasthan - Lok Sabha (25)
    ("Ganganagar", "Rajasthan", SeatType.MP),
    ("Bikaner", "Rajasthan", SeatType.MP),
    ("Churu", "Rajasthan", SeatType.MP),
    ("Jhunjhunu", "Rajasthan", SeatType.MP),
    ("Sikar", "Rajasthan", SeatType.MP),
    ("Jaipur Rural", "Rajasthan", SeatType.MP),
    ("Jaipur", "Rajasthan", SeatType.MP),
    ("Alwar", "Rajasthan", SeatType.MP),
    ("Bharatpur", "Rajasthan", SeatType.MP),
    ("Karauli-Dholpur", "Rajasthan", SeatType.MP),
    ("Dausa", "Rajasthan", SeatType.MP),
    ("Tonk-Sawai Madhopur", "Rajasthan", SeatType.MP),
    ("Ajmer", "Rajasthan", SeatType.MP),
    ("Nagaur", "Rajasthan", SeatType.MP),
    ("Pali", "Rajasthan", SeatType.MP),
    ("Jodhpur", "Rajasthan", SeatType.MP),
    ("Barmer", "Rajasthan", SeatType.MP),
    ("Jalore", "Rajasthan", SeatType.MP),
    ("Udaipur", "Rajasthan", SeatType.MP),
    ("Banswara", "Rajasthan", SeatType.MP),
    ("Chittorgarh", "Rajasthan", SeatType.MP),
    ("Rajsamand", "Rajasthan", SeatType.MP),
    ("Bhilwara", "Rajasthan", SeatType.MP),
    ("Kota", "Rajasthan", SeatType.MP),
    ("Jhalawar-Baran", "Rajasthan", SeatType.MP),

    # Uttar Pradesh - Lok Sabha (80)
    ("Saharanpur", "Uttar Pradesh", SeatType.MP),
    ("Kairana", "Uttar Pradesh", SeatType.MP),
    ("Muzaffarnagar", "Uttar Pradesh", SeatType.MP),
    ("Bijnor", "Uttar Pradesh", SeatType.MP),
    ("Nagina", "Uttar Pradesh", SeatType.MP),
    ("Moradabad", "Uttar Pradesh", SeatType.MP),
    ("Rampur", "Uttar Pradesh", SeatType.MP),
    ("Sambhal", "Uttar Pradesh", SeatType.MP),
    ("Amroha", "Uttar Pradesh", SeatType.MP),
    ("Meerut", "Uttar Pradesh", SeatType.MP),
    ("Baghpat", "Uttar Pradesh", SeatType.MP),
    ("Ghaziabad", "Uttar Pradesh", SeatType.MP),
    ("Gautam Buddha Nagar", "Uttar Pradesh", SeatType.MP),
    ("Bulandshahr", "Uttar Pradesh", SeatType.MP),
    ("Aligarh", "Uttar Pradesh", SeatType.MP),
    ("Hathras", "Uttar Pradesh", SeatType.MP),
    ("Mathura", "Uttar Pradesh", SeatType.MP),
    ("Agra", "Uttar Pradesh", SeatType.MP),
    ("Fatehpur Sikri", "Uttar Pradesh", SeatType.MP),
    ("Firozabad", "Uttar Pradesh", SeatType.MP),
    ("Mainpuri", "Uttar Pradesh", SeatType.MP),
    ("Etah", "Uttar Pradesh", SeatType.MP),
    ("Badaun", "Uttar Pradesh", SeatType.MP),
    ("Aonla", "Uttar Pradesh", SeatType.MP),
    ("Bareilly", "Uttar Pradesh", SeatType.MP),
    ("Pilibhit", "Uttar Pradesh", SeatType.MP),
    ("Shahjahanpur", "Uttar Pradesh", SeatType.MP),
    ("Kheri", "Uttar Pradesh", SeatType.MP),
    ("Dhaurahra", "Uttar Pradesh", SeatType.MP),
    ("Sitapur", "Uttar Pradesh", SeatType.MP),
    ("Hardoi", "Uttar Pradesh", SeatType.MP),
    ("Misrikh", "Uttar Pradesh", SeatType.MP),
    ("Unnao", "Uttar Pradesh", SeatType.MP),
    ("Mohanlalganj", "Uttar Pradesh", SeatType.MP),
    ("Lucknow", "Uttar Pradesh", SeatType.MP),
    ("Rae Bareli", "Uttar Pradesh", SeatType.MP),
    ("Amethi", "Uttar Pradesh", SeatType.MP),
    ("Sultanpur", "Uttar Pradesh", SeatType.MP),
    ("Pratapgarh", "Uttar Pradesh", SeatType.MP),
    ("Farrukhabad", "Uttar Pradesh", SeatType.MP),
    ("Etawah", "Uttar Pradesh", SeatType.MP),
    ("Kannauj", "Uttar Pradesh", SeatType.MP),
    ("Kanpur", "Uttar Pradesh", SeatType.MP),
    ("Akbarpur", "Uttar Pradesh", SeatType.MP),
    ("Jalaun", "Uttar Pradesh", SeatType.MP),
    ("Jhansi", "Uttar Pradesh", SeatType.MP),
    ("Hamirpur", "Uttar Pradesh", SeatType.MP),
    ("Banda", "Uttar Pradesh", SeatType.MP),
    ("Fatehpur", "Uttar Pradesh", SeatType.MP),
    ("Kaushambi", "Uttar Pradesh", SeatType.MP),
    ("Phulpur", "Uttar Pradesh", SeatType.MP),
    ("Allahabad", "Uttar Pradesh", SeatType.MP),
    ("Barabanki", "Uttar Pradesh", SeatType.MP),
    ("Faizabad", "Uttar Pradesh", SeatType.MP),
    ("Ambedkar Nagar", "Uttar Pradesh", SeatType.MP),
    ("Bahraich", "Uttar Pradesh", SeatType.MP),
    ("Kaiserganj", "Uttar Pradesh", SeatType.MP),
    ("Shrawasti", "Uttar Pradesh", SeatType.MP),
    ("Gonda", "Uttar Pradesh", SeatType.MP),
    ("Domariyaganj", "Uttar Pradesh", SeatType.MP),
    ("Basti", "Uttar Pradesh", SeatType.MP),
    ("Sant Kabir Nagar", "Uttar Pradesh", SeatType.MP),
    ("Maharajganj", "Uttar Pradesh", SeatType.MP),
    ("Gorakhpur", "Uttar Pradesh", SeatType.MP),
    ("Kushinagar", "Uttar Pradesh", SeatType.MP),
    ("Deoria", "Uttar Pradesh", SeatType.MP),
    ("Bansgaon", "Uttar Pradesh", SeatType.MP),
    ("Lalganj", "Uttar Pradesh", SeatType.MP),
    ("Azamgarh", "Uttar Pradesh", SeatType.MP),
    ("Ghosi", "Uttar Pradesh", SeatType.MP),
    ("Salempur", "Uttar Pradesh", SeatType.MP),
    ("Ballia", "Uttar Pradesh", SeatType.MP),
    ("Jaunpur", "Uttar Pradesh", SeatType.MP),
    ("Machhlishahr", "Uttar Pradesh", SeatType.MP),
    ("Ghazipur", "Uttar Pradesh", SeatType.MP),
    ("Chandauli", "Uttar Pradesh", SeatType.MP),
    ("Varanasi", "Uttar Pradesh", SeatType.MP),
    ("Bhadohi", "Uttar Pradesh", SeatType.MP),
    ("Mirzapur", "Uttar Pradesh", SeatType.MP),
    ("Robertsganj", "Uttar Pradesh", SeatType.MP),

    # Punjab - Lok Sabha (13)
    ("Gurdaspur", "Punjab", SeatType.MP),
    ("Amritsar", "Punjab", SeatType.MP),
    ("Khadoor Sahib", "Punjab", SeatType.MP),
    ("Jalandhar", "Punjab", SeatType.MP),
    ("Hoshiarpur", "Punjab", SeatType.MP),
    ("Anandpur Sahib", "Punjab", SeatType.MP),
    ("Ludhiana", "Punjab", SeatType.MP),
    ("Fatehgarh Sahib", "Punjab", SeatType.MP),
    ("Faridkot", "Punjab", SeatType.MP),
    ("Firozpur", "Punjab", SeatType.MP),
    ("Bathinda", "Punjab", SeatType.MP),
    ("Sangrur", "Punjab", SeatType.MP),
    ("Patiala", "Punjab", SeatType.MP),

    # Uttarakhand - Lok Sabha (5)
    ("Tehri Garhwal", "Uttarakhand", SeatType.MP),
    ("Garhwal", "Uttarakhand", SeatType.MP),
    ("Almora", "Uttarakhand", SeatType.MP),
    ("Nainital-Udhamsingh Nagar", "Uttarakhand", SeatType.MP),
    ("Haridwar", "Uttarakhand", SeatType.MP),

    # Vidhan Sabha (MLA) seats: not seeded yet - see module docstring.
]
