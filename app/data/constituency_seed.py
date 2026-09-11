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

Lok Sabha (MP) seats below are seeded for the four states this build was
originally pitched in (Rajasthan, Uttar Pradesh, Punjab, Uttarakhand)
plus Goa, Himachal Pradesh, and Gujarat - boundaries unchanged since the
2008 delimitation, so this is the lower-risk half of this file.

Uttarakhand's 70 MLA seats, Punjab's 117 MLA seats, Rajasthan's 200 MLA
seats, and Uttar Pradesh's 403 MLA seats ARE seeded below, all built via
the same method: not free recall, but multiple cross-referenced WebSearch
passes, name by name, checking each against a real "<Name> Assembly
constituency" Wikipedia article existing and cross-checking district-wise
sub-counts (all 75 UP districts) against known per-district seat totals.
This caught genuine search-summarization/undercounting artifacts every
time: for Uttarakhand, an Uttarkashi-district seat name spuriously
repeated into the unrelated Kumaon-hills district group; for Punjab, an
initial pass came up one seat short of the official 117 (missing
Sujanpur, which turned out to belong to Pathankot district rather than
the initially-assumed Gurdaspur - Pathankot was carved out of Gurdaspur
district in 2011, after most district-level assembly-seat groupings
people recall were fixed); for Rajasthan, cross-referencing surfaced a
real same-name collision this schema can't fully represent - see the
note on "Shahpura" in the Rajasthan MLA block below; for Uttar Pradesh,
an initial pass came up two seats short of the official 403 - Najibabad
(Bijnor district) and Kunda (Pratapgarh district) were each missing from
an otherwise-plausible-looking district sub-list, caught only because
the running district-wise sum didn't reconcile to 403. The district-wise
sub-counts below sum to exactly 70 for Uttarakhand, 117 for Punjab, 200
for Rajasthan (199 distinct rows because of the Shahpura collision), and
403 for Uttar Pradesh - still not a substitute for the official ECI
list, but meaningfully more verified than the Lok Sabha lists above,
which is why this file distinguishes the two provenances rather than
caveating everything identically.

Uttar Pradesh's own MLA seats also produced several real same-state
MP/MLA name collisions beyond the ones already seeded (e.g. Machhlishahr,
Kannauj, Mohanlalganj, Ghosi, Dhaurahra, Misrikh, Robertsganj,
Domariyaganj, Pratapgarh) - all handled the same way, via SeatType, no
new code needed.

Goa's 40 MLA seats and Himachal Pradesh's 68 MLA seats are seeded below,
same cross-referenced-search provenance, both reconciling cleanly to
their official totals (Goa: 20+20 across its two Lok Sabha groupings;
Himachal Pradesh: 17 seats in each of its four Lok Sabha groupings, all
of which - Kangra, Hamirpur, Mandi, Shimla - are themselves also real
same-state MP/MLA name collisions, the same pattern as elsewhere in this
file). Gujarat's Lok Sabha seats are seeded the same way as the other
states' Lok Sabha lists above; its 182 MLA seats are not yet seeded -
same bar as Uttar Pradesh's Vidhan Sabha seats, pending the same
cross-referenced-search treatment.
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

    # Goa - Lok Sabha (2)
    ("North Goa", "Goa", SeatType.MP),
    ("South Goa", "Goa", SeatType.MP),

    # Himachal Pradesh - Lok Sabha (4)
    ("Kangra", "Himachal Pradesh", SeatType.MP),
    ("Hamirpur", "Himachal Pradesh", SeatType.MP),
    ("Mandi", "Himachal Pradesh", SeatType.MP),
    ("Shimla", "Himachal Pradesh", SeatType.MP),

    # Gujarat - Lok Sabha (26)
    ("Kachchh", "Gujarat", SeatType.MP),
    ("Banaskantha", "Gujarat", SeatType.MP),
    ("Patan", "Gujarat", SeatType.MP),
    ("Mahesana", "Gujarat", SeatType.MP),
    ("Sabarkantha", "Gujarat", SeatType.MP),
    ("Gandhinagar", "Gujarat", SeatType.MP),
    ("Ahmedabad East", "Gujarat", SeatType.MP),
    ("Ahmedabad West", "Gujarat", SeatType.MP),
    ("Surendranagar", "Gujarat", SeatType.MP),
    ("Rajkot", "Gujarat", SeatType.MP),
    ("Porbandar", "Gujarat", SeatType.MP),
    ("Jamnagar", "Gujarat", SeatType.MP),
    ("Junagadh", "Gujarat", SeatType.MP),
    ("Amreli", "Gujarat", SeatType.MP),
    ("Bhavnagar", "Gujarat", SeatType.MP),
    ("Anand", "Gujarat", SeatType.MP),
    ("Kheda", "Gujarat", SeatType.MP),
    ("Panchmahal", "Gujarat", SeatType.MP),
    ("Dahod", "Gujarat", SeatType.MP),
    ("Vadodara", "Gujarat", SeatType.MP),
    ("Chhota Udaipur", "Gujarat", SeatType.MP),
    ("Bharuch", "Gujarat", SeatType.MP),
    ("Bardoli", "Gujarat", SeatType.MP),
    ("Surat", "Gujarat", SeatType.MP),
    ("Navsari", "Gujarat", SeatType.MP),
    ("Valsad", "Gujarat", SeatType.MP),

    # Uttarakhand - Lok Sabha (5)
    ("Tehri Garhwal", "Uttarakhand", SeatType.MP),
    ("Garhwal", "Uttarakhand", SeatType.MP),
    ("Almora", "Uttarakhand", SeatType.MP),
    ("Nainital-Udhamsingh Nagar", "Uttarakhand", SeatType.MP),
    ("Haridwar", "Uttarakhand", SeatType.MP),

    # Uttarakhand - Vidhan Sabha / MLA (70) - see module docstring for
    # this state's different (search-cross-referenced) provenance.
    # Uttarkashi district (3)
    ("Purola", "Uttarakhand", SeatType.MLA),
    ("Yamunotri", "Uttarakhand", SeatType.MLA),
    ("Gangotri", "Uttarakhand", SeatType.MLA),
    # Chamoli district (3)
    ("Badrinath", "Uttarakhand", SeatType.MLA),
    ("Tharali", "Uttarakhand", SeatType.MLA),
    ("Karnaprayag", "Uttarakhand", SeatType.MLA),
    # Rudraprayag district (2)
    ("Kedarnath", "Uttarakhand", SeatType.MLA),
    ("Rudraprayag", "Uttarakhand", SeatType.MLA),
    # Tehri Garhwal district (6)
    ("Ghansali", "Uttarakhand", SeatType.MLA),
    ("Devprayag", "Uttarakhand", SeatType.MLA),
    ("Narendranagar", "Uttarakhand", SeatType.MLA),
    ("Pratapnagar", "Uttarakhand", SeatType.MLA),
    ("Tehri", "Uttarakhand", SeatType.MLA),
    ("Dhanaulti", "Uttarakhand", SeatType.MLA),
    # Dehradun district (10)
    ("Chakrata", "Uttarakhand", SeatType.MLA),
    ("Vikasnagar", "Uttarakhand", SeatType.MLA),
    ("Sahaspur", "Uttarakhand", SeatType.MLA),
    ("Dharampur", "Uttarakhand", SeatType.MLA),
    ("Raipur", "Uttarakhand", SeatType.MLA),
    ("Rajpur Road", "Uttarakhand", SeatType.MLA),
    ("Dehradun Cantt", "Uttarakhand", SeatType.MLA),
    ("Mussoorie", "Uttarakhand", SeatType.MLA),
    ("Doiwala", "Uttarakhand", SeatType.MLA),
    ("Rishikesh", "Uttarakhand", SeatType.MLA),
    # Haridwar district (11)
    ("Haridwar Rural", "Uttarakhand", SeatType.MLA),
    ("BHEL Ranipur", "Uttarakhand", SeatType.MLA),
    ("Jwalapur", "Uttarakhand", SeatType.MLA),
    ("Bhagwanpur", "Uttarakhand", SeatType.MLA),
    ("Jhabrera", "Uttarakhand", SeatType.MLA),
    ("Piran Kaliyar", "Uttarakhand", SeatType.MLA),
    ("Roorkee", "Uttarakhand", SeatType.MLA),
    ("Khanpur", "Uttarakhand", SeatType.MLA),
    ("Manglaur", "Uttarakhand", SeatType.MLA),
    ("Laksar", "Uttarakhand", SeatType.MLA),
    # "Haridwar" itself as an MLA seat name collides with the LS seat name
    # above (SeatType disambiguates - see this module's own MP/MLA
    # collision note and geography.py's handling of exactly this case).
    ("Haridwar", "Uttarakhand", SeatType.MLA),
    # Pauri Garhwal district (6)
    ("Yamkeshwar", "Uttarakhand", SeatType.MLA),
    ("Pauri", "Uttarakhand", SeatType.MLA),
    ("Srinagar", "Uttarakhand", SeatType.MLA),
    ("Chaubattakhal", "Uttarakhand", SeatType.MLA),
    ("Lansdowne", "Uttarakhand", SeatType.MLA),
    ("Kotdwar", "Uttarakhand", SeatType.MLA),
    # Pithoragarh district (4)
    ("Dharchula", "Uttarakhand", SeatType.MLA),
    ("Didihat", "Uttarakhand", SeatType.MLA),
    ("Gangolihat", "Uttarakhand", SeatType.MLA),
    ("Pithoragarh", "Uttarakhand", SeatType.MLA),
    # Bageshwar district (2)
    ("Kapkot", "Uttarakhand", SeatType.MLA),
    ("Bageshwar", "Uttarakhand", SeatType.MLA),
    # Almora district (6)
    ("Dwarahat", "Uttarakhand", SeatType.MLA),
    ("Salt", "Uttarakhand", SeatType.MLA),
    ("Ranikhet", "Uttarakhand", SeatType.MLA),
    ("Someshwar", "Uttarakhand", SeatType.MLA),
    ("Almora", "Uttarakhand", SeatType.MLA),
    ("Jageshwar", "Uttarakhand", SeatType.MLA),
    # Champawat district (2)
    ("Lohaghat", "Uttarakhand", SeatType.MLA),
    ("Champawat", "Uttarakhand", SeatType.MLA),
    # Nainital district (6)
    ("Lalkuwan", "Uttarakhand", SeatType.MLA),
    ("Bhimtal", "Uttarakhand", SeatType.MLA),
    ("Nainital", "Uttarakhand", SeatType.MLA),
    ("Haldwani", "Uttarakhand", SeatType.MLA),
    ("Kaladhungi", "Uttarakhand", SeatType.MLA),
    ("Ramnagar", "Uttarakhand", SeatType.MLA),
    # Udham Singh Nagar district (9)
    ("Jaspur", "Uttarakhand", SeatType.MLA),
    ("Kashipur", "Uttarakhand", SeatType.MLA),
    ("Bazpur", "Uttarakhand", SeatType.MLA),
    ("Gadarpur", "Uttarakhand", SeatType.MLA),
    ("Rudrapur", "Uttarakhand", SeatType.MLA),
    ("Kichha", "Uttarakhand", SeatType.MLA),
    ("Sitarganj", "Uttarakhand", SeatType.MLA),
    ("Nanakmatta", "Uttarakhand", SeatType.MLA),
    ("Khatima", "Uttarakhand", SeatType.MLA),

    # Punjab - Vidhan Sabha / MLA (117) - see module docstring for this
    # state's search-cross-referenced provenance, and how the 116-vs-117
    # discrepancy (Sujanpur belongs to Pathankot, not Gurdaspur) was found.
    # Pathankot district (3)
    ("Sujanpur", "Punjab", SeatType.MLA),
    ("Bhoa", "Punjab", SeatType.MLA),
    ("Pathankot", "Punjab", SeatType.MLA),
    # Gurdaspur district (7)
    ("Gurdaspur", "Punjab", SeatType.MLA),
    ("Dina Nagar", "Punjab", SeatType.MLA),
    ("Qadian", "Punjab", SeatType.MLA),
    ("Batala", "Punjab", SeatType.MLA),
    ("Sri Hargobindpur", "Punjab", SeatType.MLA),
    ("Fatehgarh Churian", "Punjab", SeatType.MLA),
    ("Dera Baba Nanak", "Punjab", SeatType.MLA),
    # Amritsar district (11)
    ("Ajnala", "Punjab", SeatType.MLA),
    ("Raja Sansi", "Punjab", SeatType.MLA),
    ("Majitha", "Punjab", SeatType.MLA),
    ("Jandiala", "Punjab", SeatType.MLA),
    ("Amritsar North", "Punjab", SeatType.MLA),
    ("Amritsar West", "Punjab", SeatType.MLA),
    ("Amritsar Central", "Punjab", SeatType.MLA),
    ("Amritsar East", "Punjab", SeatType.MLA),
    ("Amritsar South", "Punjab", SeatType.MLA),
    ("Attari", "Punjab", SeatType.MLA),
    ("Baba Bakala", "Punjab", SeatType.MLA),
    # Tarn Taran district (4)
    ("Tarn Taran", "Punjab", SeatType.MLA),
    ("Khem Karan", "Punjab", SeatType.MLA),
    ("Patti", "Punjab", SeatType.MLA),
    ("Khadoor Sahib", "Punjab", SeatType.MLA),
    # Kapurthala district (4)
    ("Phagwara", "Punjab", SeatType.MLA),
    ("Kapurthala", "Punjab", SeatType.MLA),
    ("Sultanpur Lodhi", "Punjab", SeatType.MLA),
    ("Bholath", "Punjab", SeatType.MLA),
    # Jalandhar district (9)
    ("Phillaur", "Punjab", SeatType.MLA),
    ("Nakodar", "Punjab", SeatType.MLA),
    ("Shahkot", "Punjab", SeatType.MLA),
    ("Kartarpur", "Punjab", SeatType.MLA),
    ("Jalandhar West", "Punjab", SeatType.MLA),
    ("Jalandhar Central", "Punjab", SeatType.MLA),
    ("Jalandhar North", "Punjab", SeatType.MLA),
    ("Jalandhar Cantt", "Punjab", SeatType.MLA),
    ("Adampur", "Punjab", SeatType.MLA),
    # Hoshiarpur district (7)
    ("Chabbewal", "Punjab", SeatType.MLA),
    ("Hoshiarpur", "Punjab", SeatType.MLA),
    ("Sham Chaurasi", "Punjab", SeatType.MLA),
    ("Dasuya", "Punjab", SeatType.MLA),
    ("Mukerian", "Punjab", SeatType.MLA),
    ("Garhshankar", "Punjab", SeatType.MLA),
    ("Urmar", "Punjab", SeatType.MLA),
    # Shaheed Bhagat Singh Nagar district (3)
    ("Banga", "Punjab", SeatType.MLA),
    ("Nawan Shahr", "Punjab", SeatType.MLA),
    ("Balachaur", "Punjab", SeatType.MLA),
    # Rupnagar district (3)
    ("Anandpur Sahib", "Punjab", SeatType.MLA),
    ("Rupnagar", "Punjab", SeatType.MLA),
    ("Chamkaur Sahib", "Punjab", SeatType.MLA),
    # SAS Nagar / Mohali district (3)
    ("Kharar", "Punjab", SeatType.MLA),
    ("Sahibzada Ajit Singh Nagar", "Punjab", SeatType.MLA),
    ("Dera Bassi", "Punjab", SeatType.MLA),
    # Fatehgarh Sahib district (3)
    ("Bassi Pathana", "Punjab", SeatType.MLA),
    ("Fatehgarh Sahib", "Punjab", SeatType.MLA),
    ("Amloh", "Punjab", SeatType.MLA),
    # Ludhiana district (14)
    ("Khanna", "Punjab", SeatType.MLA),
    ("Samrala", "Punjab", SeatType.MLA),
    ("Sahnewal", "Punjab", SeatType.MLA),
    ("Ludhiana East", "Punjab", SeatType.MLA),
    ("Ludhiana South", "Punjab", SeatType.MLA),
    ("Atam Nagar", "Punjab", SeatType.MLA),
    ("Ludhiana Central", "Punjab", SeatType.MLA),
    ("Ludhiana West", "Punjab", SeatType.MLA),
    ("Ludhiana North", "Punjab", SeatType.MLA),
    ("Gill", "Punjab", SeatType.MLA),
    ("Payal", "Punjab", SeatType.MLA),
    ("Dakha", "Punjab", SeatType.MLA),
    ("Raikot", "Punjab", SeatType.MLA),
    ("Jagraon", "Punjab", SeatType.MLA),
    # Moga district (4)
    ("Nihal Singh Wala", "Punjab", SeatType.MLA),
    ("Bagha Purana", "Punjab", SeatType.MLA),
    ("Moga", "Punjab", SeatType.MLA),
    ("Dharamkot", "Punjab", SeatType.MLA),
    # Firozpur district (4)
    ("Firozpur City", "Punjab", SeatType.MLA),
    ("Firozpur Rural", "Punjab", SeatType.MLA),
    ("Guru Har Sahai", "Punjab", SeatType.MLA),
    ("Zira", "Punjab", SeatType.MLA),
    # Fazilka district (4)
    ("Jalalabad", "Punjab", SeatType.MLA),
    ("Fazilka", "Punjab", SeatType.MLA),
    ("Abohar", "Punjab", SeatType.MLA),
    ("Balluana", "Punjab", SeatType.MLA),
    # Faridkot district (3)
    ("Faridkot", "Punjab", SeatType.MLA),
    ("Kotkapura", "Punjab", SeatType.MLA),
    ("Jaitu", "Punjab", SeatType.MLA),
    # Sri Muktsar Sahib district (4)
    ("Lambi", "Punjab", SeatType.MLA),
    ("Gidderbaha", "Punjab", SeatType.MLA),
    ("Malout", "Punjab", SeatType.MLA),
    ("Sri Muktsar Sahib", "Punjab", SeatType.MLA),
    # Bathinda district (6)
    ("Bathinda Rural", "Punjab", SeatType.MLA),
    ("Bathinda Urban", "Punjab", SeatType.MLA),
    ("Bhucho Mandi", "Punjab", SeatType.MLA),
    ("Maur", "Punjab", SeatType.MLA),
    ("Rampura Phul", "Punjab", SeatType.MLA),
    ("Talwandi Sabo", "Punjab", SeatType.MLA),
    # Mansa district (3)
    ("Mansa", "Punjab", SeatType.MLA),
    ("Sardulgarh", "Punjab", SeatType.MLA),
    ("Budhlada", "Punjab", SeatType.MLA),
    # Sangrur district (5)
    ("Dhuri", "Punjab", SeatType.MLA),
    ("Sunam", "Punjab", SeatType.MLA),
    ("Sangrur", "Punjab", SeatType.MLA),
    ("Lehra", "Punjab", SeatType.MLA),
    ("Dirba", "Punjab", SeatType.MLA),
    # Barnala district (3)
    ("Barnala", "Punjab", SeatType.MLA),
    ("Bhadaur", "Punjab", SeatType.MLA),
    ("Mehal Kalan", "Punjab", SeatType.MLA),
    # Malerkotla district (2)
    ("Malerkotla", "Punjab", SeatType.MLA),
    ("Amargarh", "Punjab", SeatType.MLA),
    # Patiala district (8)
    ("Nabha", "Punjab", SeatType.MLA),
    ("Patiala Rural", "Punjab", SeatType.MLA),
    ("Rajpura", "Punjab", SeatType.MLA),
    ("Ghanaur", "Punjab", SeatType.MLA),
    ("Sanour", "Punjab", SeatType.MLA),
    ("Patiala Town", "Punjab", SeatType.MLA),
    ("Samana", "Punjab", SeatType.MLA),
    ("Shutrana", "Punjab", SeatType.MLA),

    # Rajasthan - Vidhan Sabha / MLA (200 official seats, 199 rows here -
    # see module docstring for this state's search-cross-referenced
    # provenance and the real "Shahpura" name collision noted below).
    # Sri Ganganagar district (6)
    ("Ganganagar", "Rajasthan", SeatType.MLA),
    ("Karanpur", "Rajasthan", SeatType.MLA),
    ("Raisinghnagar", "Rajasthan", SeatType.MLA),
    ("Sadulshahar", "Rajasthan", SeatType.MLA),
    ("Anupgarh", "Rajasthan", SeatType.MLA),
    ("Suratgarh", "Rajasthan", SeatType.MLA),
    # Hanumangarh district (5)
    ("Sangaria", "Rajasthan", SeatType.MLA),
    ("Pilibanga", "Rajasthan", SeatType.MLA),
    ("Hanumangarh", "Rajasthan", SeatType.MLA),
    ("Bhadra", "Rajasthan", SeatType.MLA),
    ("Nohar", "Rajasthan", SeatType.MLA),
    # Bikaner district (7)
    ("Khajuwala", "Rajasthan", SeatType.MLA),
    ("Bikaner West", "Rajasthan", SeatType.MLA),
    ("Bikaner East", "Rajasthan", SeatType.MLA),
    ("Kolayat", "Rajasthan", SeatType.MLA),
    ("Lunkaransar", "Rajasthan", SeatType.MLA),
    ("Dungargarh", "Rajasthan", SeatType.MLA),
    ("Nokha", "Rajasthan", SeatType.MLA),
    # Churu district (6)
    ("Sadulpur", "Rajasthan", SeatType.MLA),
    ("Taranagar", "Rajasthan", SeatType.MLA),
    ("Sardarshahar", "Rajasthan", SeatType.MLA),
    ("Churu", "Rajasthan", SeatType.MLA),
    ("Ratangarh", "Rajasthan", SeatType.MLA),
    ("Sujangarh", "Rajasthan", SeatType.MLA),
    # Jhunjhunu district (7)
    ("Pilani", "Rajasthan", SeatType.MLA),
    ("Surajgarh", "Rajasthan", SeatType.MLA),
    ("Jhunjhunu", "Rajasthan", SeatType.MLA),
    ("Mandawa", "Rajasthan", SeatType.MLA),
    ("Nawalgarh", "Rajasthan", SeatType.MLA),
    ("Khetri", "Rajasthan", SeatType.MLA),
    ("Udaipurwati", "Rajasthan", SeatType.MLA),
    # Sikar district (8)
    ("Fatehpur", "Rajasthan", SeatType.MLA),
    ("Lachhmangarh", "Rajasthan", SeatType.MLA),
    ("Dhod", "Rajasthan", SeatType.MLA),
    ("Sikar", "Rajasthan", SeatType.MLA),
    ("Danta Ramgarh", "Rajasthan", SeatType.MLA),
    ("Khandela", "Rajasthan", SeatType.MLA),
    ("Srimadhopur", "Rajasthan", SeatType.MLA),
    ("Neem Ka Thana", "Rajasthan", SeatType.MLA),
    # Jaipur district (19)
    ("Kishanpole", "Rajasthan", SeatType.MLA),
    ("Dudu", "Rajasthan", SeatType.MLA),
    ("Vidyadhar Nagar", "Rajasthan", SeatType.MLA),
    ("Hawa Mahal", "Rajasthan", SeatType.MLA),
    ("Kotputli", "Rajasthan", SeatType.MLA),
    ("Viratnagar", "Rajasthan", SeatType.MLA),
    # "Shahpura" is a real same-name collision between two distinct
    # Rajasthan MLA seats (this one in Jaipur district, another in
    # Bhilwara district) - unlike every other MP/MLA collision this file
    # handles via seat_type, both are MLA, so this (name, state,
    # seat_type) schema genuinely can't tell them apart. Seeded once: a
    # bare "Shahpura" mention still correctly resolves to an MLA seat,
    # it just can't say which one - see module docstring.
    ("Shahpura", "Rajasthan", SeatType.MLA),
    ("Chomu", "Rajasthan", SeatType.MLA),
    ("Phulera", "Rajasthan", SeatType.MLA),
    ("Jhotwara", "Rajasthan", SeatType.MLA),
    ("Amber", "Rajasthan", SeatType.MLA),
    ("Jamwa Ramgarh", "Rajasthan", SeatType.MLA),
    ("Civil Lines", "Rajasthan", SeatType.MLA),
    ("Adarsh Nagar", "Rajasthan", SeatType.MLA),
    ("Malviya Nagar", "Rajasthan", SeatType.MLA),
    ("Sanganer", "Rajasthan", SeatType.MLA),
    ("Bagru", "Rajasthan", SeatType.MLA),
    ("Bassi", "Rajasthan", SeatType.MLA),
    ("Chaksu", "Rajasthan", SeatType.MLA),
    # Alwar district (11)
    ("Alwar Rural", "Rajasthan", SeatType.MLA),
    ("Alwar Urban", "Rajasthan", SeatType.MLA),
    ("Bansur", "Rajasthan", SeatType.MLA),
    ("Behror", "Rajasthan", SeatType.MLA),
    ("Kathumar", "Rajasthan", SeatType.MLA),
    ("Kishangarh Bas", "Rajasthan", SeatType.MLA),
    ("Mundawar", "Rajasthan", SeatType.MLA),
    ("Rajgarh-Laxmangarh", "Rajasthan", SeatType.MLA),
    ("Ramgarh", "Rajasthan", SeatType.MLA),
    ("Thanagazi", "Rajasthan", SeatType.MLA),
    ("Tijara", "Rajasthan", SeatType.MLA),
    # Bharatpur district (7)
    ("Deeg-Kumher", "Rajasthan", SeatType.MLA),
    ("Bharatpur", "Rajasthan", SeatType.MLA),
    ("Kaman", "Rajasthan", SeatType.MLA),
    ("Nagar", "Rajasthan", SeatType.MLA),
    ("Weir", "Rajasthan", SeatType.MLA),
    ("Nadbai", "Rajasthan", SeatType.MLA),
    ("Bayana", "Rajasthan", SeatType.MLA),
    # Dholpur district (4)
    ("Dholpur", "Rajasthan", SeatType.MLA),
    ("Bari", "Rajasthan", SeatType.MLA),
    ("Rajakhera", "Rajasthan", SeatType.MLA),
    ("Baseri", "Rajasthan", SeatType.MLA),
    # Karauli district (4)
    ("Todabhim", "Rajasthan", SeatType.MLA),
    ("Hindaun", "Rajasthan", SeatType.MLA),
    ("Karauli", "Rajasthan", SeatType.MLA),
    ("Sapotra", "Rajasthan", SeatType.MLA),
    # Dausa district (5)
    ("Bandikui", "Rajasthan", SeatType.MLA),
    ("Mahuwa", "Rajasthan", SeatType.MLA),
    ("Sikrai", "Rajasthan", SeatType.MLA),
    ("Dausa", "Rajasthan", SeatType.MLA),
    ("Lalsot", "Rajasthan", SeatType.MLA),
    # Sawai Madhopur district (4)
    ("Gangapur", "Rajasthan", SeatType.MLA),
    ("Bamanwas", "Rajasthan", SeatType.MLA),
    ("Sawai Madhopur", "Rajasthan", SeatType.MLA),
    ("Khandar", "Rajasthan", SeatType.MLA),
    # Tonk district (4)
    ("Deoli-Uniara", "Rajasthan", SeatType.MLA),
    ("Malpura", "Rajasthan", SeatType.MLA),
    ("Niwai", "Rajasthan", SeatType.MLA),
    ("Tonk", "Rajasthan", SeatType.MLA),
    # Ajmer district (8) - includes Beawar, seeded here under Ajmer since
    # district_seed.py uses the pre-August-2023 33-district list, before
    # Beawar was carved out as its own district.
    ("Kishangarh", "Rajasthan", SeatType.MLA),
    ("Pushkar", "Rajasthan", SeatType.MLA),
    ("Ajmer North", "Rajasthan", SeatType.MLA),
    ("Ajmer South", "Rajasthan", SeatType.MLA),
    ("Nasirabad", "Rajasthan", SeatType.MLA),
    ("Masuda", "Rajasthan", SeatType.MLA),
    ("Kekri", "Rajasthan", SeatType.MLA),
    ("Beawar", "Rajasthan", SeatType.MLA),
    # Nagaur district (10)
    ("Ladnun", "Rajasthan", SeatType.MLA),
    ("Deedwana", "Rajasthan", SeatType.MLA),
    ("Jayal", "Rajasthan", SeatType.MLA),
    ("Nagaur", "Rajasthan", SeatType.MLA),
    ("Khinvsar", "Rajasthan", SeatType.MLA),
    ("Makrana", "Rajasthan", SeatType.MLA),
    ("Parbatsar", "Rajasthan", SeatType.MLA),
    ("Nawan", "Rajasthan", SeatType.MLA),
    ("Degana", "Rajasthan", SeatType.MLA),
    ("Merta", "Rajasthan", SeatType.MLA),
    # Pali district (6)
    ("Sojat", "Rajasthan", SeatType.MLA),
    ("Pali", "Rajasthan", SeatType.MLA),
    ("Marwar Junction", "Rajasthan", SeatType.MLA),
    ("Bali", "Rajasthan", SeatType.MLA),
    ("Sumerpur", "Rajasthan", SeatType.MLA),
    ("Jaitaran", "Rajasthan", SeatType.MLA),
    # Jodhpur district (10)
    ("Bhopalgarh", "Rajasthan", SeatType.MLA),
    ("Bilara", "Rajasthan", SeatType.MLA),
    ("Jodhpur", "Rajasthan", SeatType.MLA),
    ("Lohawat", "Rajasthan", SeatType.MLA),
    ("Luni", "Rajasthan", SeatType.MLA),
    ("Osian", "Rajasthan", SeatType.MLA),
    ("Phalodi", "Rajasthan", SeatType.MLA),
    ("Sardarpura", "Rajasthan", SeatType.MLA),
    ("Shergarh", "Rajasthan", SeatType.MLA),
    ("Soorsagar", "Rajasthan", SeatType.MLA),
    # Jaisalmer district (2)
    ("Jaisalmer", "Rajasthan", SeatType.MLA),
    ("Pokaran", "Rajasthan", SeatType.MLA),
    # Barmer district (7)
    ("Sheo", "Rajasthan", SeatType.MLA),
    ("Barmer", "Rajasthan", SeatType.MLA),
    ("Baytoo", "Rajasthan", SeatType.MLA),
    ("Pachpadra", "Rajasthan", SeatType.MLA),
    ("Siwana", "Rajasthan", SeatType.MLA),
    ("Gudha Malani", "Rajasthan", SeatType.MLA),
    ("Chohtan", "Rajasthan", SeatType.MLA),
    # Jalore district (5)
    ("Ahore", "Rajasthan", SeatType.MLA),
    ("Jalore", "Rajasthan", SeatType.MLA),
    ("Bhinmal", "Rajasthan", SeatType.MLA),
    ("Sanchore", "Rajasthan", SeatType.MLA),
    ("Raniwara", "Rajasthan", SeatType.MLA),
    # Sirohi district (3)
    ("Sirohi", "Rajasthan", SeatType.MLA),
    ("Pindwara-Abu", "Rajasthan", SeatType.MLA),
    ("Reodar", "Rajasthan", SeatType.MLA),
    # Udaipur district (8)
    ("Gogunda", "Rajasthan", SeatType.MLA),
    ("Jhadol", "Rajasthan", SeatType.MLA),
    ("Kherwara", "Rajasthan", SeatType.MLA),
    ("Mavli", "Rajasthan", SeatType.MLA),
    ("Salumber", "Rajasthan", SeatType.MLA),
    ("Udaipur", "Rajasthan", SeatType.MLA),
    ("Udaipur Rural", "Rajasthan", SeatType.MLA),
    ("Vallabhnagar", "Rajasthan", SeatType.MLA),
    # Rajsamand district (4)
    ("Bhim", "Rajasthan", SeatType.MLA),
    ("Kumbhalgarh", "Rajasthan", SeatType.MLA),
    ("Rajsamand", "Rajasthan", SeatType.MLA),
    ("Nathdwara", "Rajasthan", SeatType.MLA),
    # Dungarpur district (4)
    ("Aspur", "Rajasthan", SeatType.MLA),
    ("Sagwara", "Rajasthan", SeatType.MLA),
    ("Dungarpur", "Rajasthan", SeatType.MLA),
    ("Chorasi", "Rajasthan", SeatType.MLA),
    # Banswara district (5)
    ("Bagidora", "Rajasthan", SeatType.MLA),
    ("Garhi", "Rajasthan", SeatType.MLA),
    ("Banswara", "Rajasthan", SeatType.MLA),
    ("Ghatol", "Rajasthan", SeatType.MLA),
    ("Kushalgarh", "Rajasthan", SeatType.MLA),
    # Chittorgarh district (5)
    ("Kapasan", "Rajasthan", SeatType.MLA),
    ("Begun", "Rajasthan", SeatType.MLA),
    ("Chittorgarh", "Rajasthan", SeatType.MLA),
    ("Nimbahera", "Rajasthan", SeatType.MLA),
    ("Bari Sadri", "Rajasthan", SeatType.MLA),
    # Bhilwara district (7) - Shahpura excluded here, already seeded once
    # under Jaipur district above (see the collision note there).
    ("Bhilwara", "Rajasthan", SeatType.MLA),
    ("Asind", "Rajasthan", SeatType.MLA),
    ("Mandal", "Rajasthan", SeatType.MLA),
    ("Sahara", "Rajasthan", SeatType.MLA),
    ("Mandalgarh", "Rajasthan", SeatType.MLA),
    ("Jahazpur", "Rajasthan", SeatType.MLA),
    # Bundi district (3)
    ("Bundi", "Rajasthan", SeatType.MLA),
    ("Keshoraipatan", "Rajasthan", SeatType.MLA),
    ("Hindoli", "Rajasthan", SeatType.MLA),
    # Kota district (6)
    ("Ladpura", "Rajasthan", SeatType.MLA),
    ("Kota North", "Rajasthan", SeatType.MLA),
    ("Kota South", "Rajasthan", SeatType.MLA),
    ("Ramganj Mandi", "Rajasthan", SeatType.MLA),
    ("Pipalda", "Rajasthan", SeatType.MLA),
    ("Sangod", "Rajasthan", SeatType.MLA),
    # Baran district (4)
    ("Anta", "Rajasthan", SeatType.MLA),
    ("Kishanganj", "Rajasthan", SeatType.MLA),
    ("Baran-Atru", "Rajasthan", SeatType.MLA),
    ("Chhabra", "Rajasthan", SeatType.MLA),
    # Jhalawar district (4)
    ("Dag", "Rajasthan", SeatType.MLA),
    ("Jhalrapatan", "Rajasthan", SeatType.MLA),
    ("Khanpur", "Rajasthan", SeatType.MLA),
    ("Manohar Thana", "Rajasthan", SeatType.MLA),
    # Pratapgarh district (2)
    ("Pratapgarh", "Rajasthan", SeatType.MLA),
    ("Dhariawad", "Rajasthan", SeatType.MLA),

    # Uttar Pradesh - Vidhan Sabha / MLA (403) - see module docstring for
    # this state's search-cross-referenced provenance and the
    # Najibabad/Kunda undercount that was caught and fixed.
    # Agra district (9)
    ("Etmadpur", "Uttar Pradesh", SeatType.MLA),
    ("Agra Cantt", "Uttar Pradesh", SeatType.MLA),
    ("Agra North", "Uttar Pradesh", SeatType.MLA),
    ("Agra South", "Uttar Pradesh", SeatType.MLA),
    ("Agra Rural", "Uttar Pradesh", SeatType.MLA),
    ("Bah", "Uttar Pradesh", SeatType.MLA),
    ("Fatehabad", "Uttar Pradesh", SeatType.MLA),
    ("Kheragarh", "Uttar Pradesh", SeatType.MLA),
    ("Fatehpur Sikri", "Uttar Pradesh", SeatType.MLA),
    # Aligarh district (7)
    ("Khair", "Uttar Pradesh", SeatType.MLA),
    ("Barauli", "Uttar Pradesh", SeatType.MLA),
    ("Atrauli", "Uttar Pradesh", SeatType.MLA),
    ("Koil", "Uttar Pradesh", SeatType.MLA),
    ("Aligarh", "Uttar Pradesh", SeatType.MLA),
    ("Chharra", "Uttar Pradesh", SeatType.MLA),
    ("Iglas", "Uttar Pradesh", SeatType.MLA),
    # Prayagraj district (12)
    ("Phaphamau", "Uttar Pradesh", SeatType.MLA),
    ("Soraon", "Uttar Pradesh", SeatType.MLA),
    ("Phulpur", "Uttar Pradesh", SeatType.MLA),
    ("Pratappur", "Uttar Pradesh", SeatType.MLA),
    ("Handia", "Uttar Pradesh", SeatType.MLA),
    ("Meja", "Uttar Pradesh", SeatType.MLA),
    ("Karachhana", "Uttar Pradesh", SeatType.MLA),
    ("Allahabad West", "Uttar Pradesh", SeatType.MLA),
    ("Allahabad North", "Uttar Pradesh", SeatType.MLA),
    ("Allahabad South", "Uttar Pradesh", SeatType.MLA),
    ("Bara", "Uttar Pradesh", SeatType.MLA),
    ("Koraon", "Uttar Pradesh", SeatType.MLA),
    # Ambedkar Nagar district (5)
    ("Katehari", "Uttar Pradesh", SeatType.MLA),
    ("Akbarpur", "Uttar Pradesh", SeatType.MLA),
    ("Tanda", "Uttar Pradesh", SeatType.MLA),
    ("Jalalpur", "Uttar Pradesh", SeatType.MLA),
    ("Alapur", "Uttar Pradesh", SeatType.MLA),
    # Amethi district (5)
    ("Tiloi", "Uttar Pradesh", SeatType.MLA),
    ("Salon", "Uttar Pradesh", SeatType.MLA),
    ("Jagdishpur", "Uttar Pradesh", SeatType.MLA),
    ("Gauriganj", "Uttar Pradesh", SeatType.MLA),
    ("Amethi", "Uttar Pradesh", SeatType.MLA),
    # Amroha district (4)
    ("Dhanaura", "Uttar Pradesh", SeatType.MLA),
    ("Naugawan Sadat", "Uttar Pradesh", SeatType.MLA),
    ("Amroha", "Uttar Pradesh", SeatType.MLA),
    ("Hasanpur", "Uttar Pradesh", SeatType.MLA),
    # Auraiya district (3)
    ("Auraiya", "Uttar Pradesh", SeatType.MLA),
    ("Bidhuna", "Uttar Pradesh", SeatType.MLA),
    ("Dibiyapur", "Uttar Pradesh", SeatType.MLA),
    # Ayodhya district (5)
    ("Rudauli", "Uttar Pradesh", SeatType.MLA),
    ("Milkipur", "Uttar Pradesh", SeatType.MLA),
    ("Bikapur", "Uttar Pradesh", SeatType.MLA),
    ("Ayodhya", "Uttar Pradesh", SeatType.MLA),
    ("Goshainganj", "Uttar Pradesh", SeatType.MLA),
    # Azamgarh district (10)
    ("Atrauliya", "Uttar Pradesh", SeatType.MLA),
    ("Gopalpur", "Uttar Pradesh", SeatType.MLA),
    ("Sagri", "Uttar Pradesh", SeatType.MLA),
    ("Mubarakpur", "Uttar Pradesh", SeatType.MLA),
    ("Azamgarh", "Uttar Pradesh", SeatType.MLA),
    ("Nizamabad", "Uttar Pradesh", SeatType.MLA),
    ("Phoolpur-Pawai", "Uttar Pradesh", SeatType.MLA),
    ("Didarganj", "Uttar Pradesh", SeatType.MLA),
    ("Lalganj", "Uttar Pradesh", SeatType.MLA),
    ("Mehnagar", "Uttar Pradesh", SeatType.MLA),
    # Baghpat district (3)
    ("Chhaprauli", "Uttar Pradesh", SeatType.MLA),
    ("Baraut", "Uttar Pradesh", SeatType.MLA),
    ("Baghpat", "Uttar Pradesh", SeatType.MLA),
    # Bahraich district (7)
    ("Balha", "Uttar Pradesh", SeatType.MLA),
    ("Nanpara", "Uttar Pradesh", SeatType.MLA),
    ("Matera", "Uttar Pradesh", SeatType.MLA),
    ("Mahasi", "Uttar Pradesh", SeatType.MLA),
    ("Bahraich", "Uttar Pradesh", SeatType.MLA),
    ("Payagpur", "Uttar Pradesh", SeatType.MLA),
    ("Kaiserganj", "Uttar Pradesh", SeatType.MLA),
    # Ballia district (7)
    ("Belthara Road", "Uttar Pradesh", SeatType.MLA),
    ("Sikanderpur", "Uttar Pradesh", SeatType.MLA),
    ("Bansdih", "Uttar Pradesh", SeatType.MLA),
    ("Phephana", "Uttar Pradesh", SeatType.MLA),
    ("Ballia Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Bairia", "Uttar Pradesh", SeatType.MLA),
    ("Rasra", "Uttar Pradesh", SeatType.MLA),
    # Balrampur district (4)
    ("Tulsipur", "Uttar Pradesh", SeatType.MLA),
    ("Gainsari", "Uttar Pradesh", SeatType.MLA),
    ("Utraula", "Uttar Pradesh", SeatType.MLA),
    ("Balrampur", "Uttar Pradesh", SeatType.MLA),
    # Banda district (4)
    ("Tindwari", "Uttar Pradesh", SeatType.MLA),
    ("Baberu", "Uttar Pradesh", SeatType.MLA),
    ("Naraini", "Uttar Pradesh", SeatType.MLA),
    ("Banda", "Uttar Pradesh", SeatType.MLA),
    # Barabanki district (6)
    ("Kursi", "Uttar Pradesh", SeatType.MLA),
    ("Ram Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Barabanki", "Uttar Pradesh", SeatType.MLA),
    ("Zaidpur", "Uttar Pradesh", SeatType.MLA),
    ("Dariyabad", "Uttar Pradesh", SeatType.MLA),
    ("Haidergarh", "Uttar Pradesh", SeatType.MLA),
    # Bareilly district (9)
    ("Baheri", "Uttar Pradesh", SeatType.MLA),
    ("Meerganj", "Uttar Pradesh", SeatType.MLA),
    ("Bhojipura", "Uttar Pradesh", SeatType.MLA),
    ("Nawabganj", "Uttar Pradesh", SeatType.MLA),
    ("Faridpur", "Uttar Pradesh", SeatType.MLA),
    ("Bithari Chainpur", "Uttar Pradesh", SeatType.MLA),
    ("Bareilly", "Uttar Pradesh", SeatType.MLA),
    ("Bareilly Cantt", "Uttar Pradesh", SeatType.MLA),
    ("Aonla", "Uttar Pradesh", SeatType.MLA),
    # Basti district (5)
    ("Harraiya", "Uttar Pradesh", SeatType.MLA),
    ("Kaptanganj", "Uttar Pradesh", SeatType.MLA),
    ("Rudhauli", "Uttar Pradesh", SeatType.MLA),
    ("Basti Sadar", "Uttar Pradesh", SeatType.MLA),
    ("Mahadewa", "Uttar Pradesh", SeatType.MLA),
    # Bhadohi district (3)
    ("Bhadohi", "Uttar Pradesh", SeatType.MLA),
    ("Gyanpur", "Uttar Pradesh", SeatType.MLA),
    ("Aurai", "Uttar Pradesh", SeatType.MLA),
    # Bijnor district (8)
    ("Bijnor", "Uttar Pradesh", SeatType.MLA),
    ("Chandpur", "Uttar Pradesh", SeatType.MLA),
    ("Barhapur", "Uttar Pradesh", SeatType.MLA),
    ("Nagina", "Uttar Pradesh", SeatType.MLA),
    ("Dhampur", "Uttar Pradesh", SeatType.MLA),
    ("Nehtaur", "Uttar Pradesh", SeatType.MLA),
    ("Noorpur", "Uttar Pradesh", SeatType.MLA),
    ("Najibabad", "Uttar Pradesh", SeatType.MLA),
    # Budaun district (6)
    ("Bisauli", "Uttar Pradesh", SeatType.MLA),
    ("Sahaswan", "Uttar Pradesh", SeatType.MLA),
    ("Bilsi", "Uttar Pradesh", SeatType.MLA),
    ("Badaun", "Uttar Pradesh", SeatType.MLA),
    ("Shekhupur", "Uttar Pradesh", SeatType.MLA),
    ("Dataganj", "Uttar Pradesh", SeatType.MLA),
    # Bulandshahr district (7)
    ("Sikandrabad", "Uttar Pradesh", SeatType.MLA),
    ("Bulandshahr", "Uttar Pradesh", SeatType.MLA),
    ("Syana", "Uttar Pradesh", SeatType.MLA),
    ("Anupshahr", "Uttar Pradesh", SeatType.MLA),
    ("Debai", "Uttar Pradesh", SeatType.MLA),
    ("Shikarpur", "Uttar Pradesh", SeatType.MLA),
    ("Khurja", "Uttar Pradesh", SeatType.MLA),
    # Chandauli district (4)
    ("Mughalsarai", "Uttar Pradesh", SeatType.MLA),
    ("Sakaldiha", "Uttar Pradesh", SeatType.MLA),
    ("Saiyadraja", "Uttar Pradesh", SeatType.MLA),
    ("Chakia", "Uttar Pradesh", SeatType.MLA),
    # Chitrakoot district (2)
    ("Chitrakoot", "Uttar Pradesh", SeatType.MLA),
    ("Manikpur", "Uttar Pradesh", SeatType.MLA),
    # Deoria district (7)
    ("Rudrapur", "Uttar Pradesh", SeatType.MLA),
    ("Deoria", "Uttar Pradesh", SeatType.MLA),
    ("Pathardeva", "Uttar Pradesh", SeatType.MLA),
    ("Rampur Karkhana", "Uttar Pradesh", SeatType.MLA),
    ("Bhatpar Rani", "Uttar Pradesh", SeatType.MLA),
    ("Salempur", "Uttar Pradesh", SeatType.MLA),
    ("Barhaj", "Uttar Pradesh", SeatType.MLA),
    # Etah district (4)
    ("Aliganj", "Uttar Pradesh", SeatType.MLA),
    ("Etah", "Uttar Pradesh", SeatType.MLA),
    ("Marhara", "Uttar Pradesh", SeatType.MLA),
    ("Jalesar", "Uttar Pradesh", SeatType.MLA),
    # Etawah district (3)
    ("Jaswantnagar", "Uttar Pradesh", SeatType.MLA),
    ("Etawah", "Uttar Pradesh", SeatType.MLA),
    ("Bharthana", "Uttar Pradesh", SeatType.MLA),
    # Farrukhabad district (4)
    ("Kaimganj", "Uttar Pradesh", SeatType.MLA),
    ("Amritpur", "Uttar Pradesh", SeatType.MLA),
    ("Farrukhabad", "Uttar Pradesh", SeatType.MLA),
    ("Bhojpur", "Uttar Pradesh", SeatType.MLA),
    # Fatehpur district (6)
    ("Jahanabad", "Uttar Pradesh", SeatType.MLA),
    ("Bindki", "Uttar Pradesh", SeatType.MLA),
    ("Fatehpur", "Uttar Pradesh", SeatType.MLA),
    ("Ayah Shah", "Uttar Pradesh", SeatType.MLA),
    ("Husainganj", "Uttar Pradesh", SeatType.MLA),
    ("Khaga", "Uttar Pradesh", SeatType.MLA),
    # Firozabad district (5)
    ("Tundla", "Uttar Pradesh", SeatType.MLA),
    ("Jasrana", "Uttar Pradesh", SeatType.MLA),
    ("Firozabad", "Uttar Pradesh", SeatType.MLA),
    ("Shikohabad", "Uttar Pradesh", SeatType.MLA),
    ("Sirsaganj", "Uttar Pradesh", SeatType.MLA),
    # Gautam Buddha Nagar district (3)
    ("Noida", "Uttar Pradesh", SeatType.MLA),
    ("Dadri", "Uttar Pradesh", SeatType.MLA),
    ("Jewar", "Uttar Pradesh", SeatType.MLA),
    # Ghaziabad district (5)
    ("Loni", "Uttar Pradesh", SeatType.MLA),
    ("Muradnagar", "Uttar Pradesh", SeatType.MLA),
    ("Sahibabad", "Uttar Pradesh", SeatType.MLA),
    ("Ghaziabad", "Uttar Pradesh", SeatType.MLA),
    ("Modinagar", "Uttar Pradesh", SeatType.MLA),
    # Ghazipur district (7)
    ("Jakhania", "Uttar Pradesh", SeatType.MLA),
    ("Saidpur", "Uttar Pradesh", SeatType.MLA),
    ("Ghazipur", "Uttar Pradesh", SeatType.MLA),
    ("Jangipur", "Uttar Pradesh", SeatType.MLA),
    ("Zahoorabad", "Uttar Pradesh", SeatType.MLA),
    ("Mohammadabad", "Uttar Pradesh", SeatType.MLA),
    ("Zamania", "Uttar Pradesh", SeatType.MLA),
    # Gonda district (7)
    ("Mehnaun", "Uttar Pradesh", SeatType.MLA),
    ("Gonda", "Uttar Pradesh", SeatType.MLA),
    ("Katra Bazar", "Uttar Pradesh", SeatType.MLA),
    ("Colonelganj", "Uttar Pradesh", SeatType.MLA),
    ("Tarabganj", "Uttar Pradesh", SeatType.MLA),
    ("Mankapur", "Uttar Pradesh", SeatType.MLA),
    ("Gaura", "Uttar Pradesh", SeatType.MLA),
    # Gorakhpur district (9)
    ("Campierganj", "Uttar Pradesh", SeatType.MLA),
    ("Pipraich", "Uttar Pradesh", SeatType.MLA),
    ("Gorakhpur Urban", "Uttar Pradesh", SeatType.MLA),
    ("Gorakhpur Rural", "Uttar Pradesh", SeatType.MLA),
    ("Sahjanwa", "Uttar Pradesh", SeatType.MLA),
    ("Khajani", "Uttar Pradesh", SeatType.MLA),
    ("Chauri Chaura", "Uttar Pradesh", SeatType.MLA),
    ("Bansgaon", "Uttar Pradesh", SeatType.MLA),
    ("Chillupar", "Uttar Pradesh", SeatType.MLA),
    # Hamirpur district (2)
    ("Hamirpur", "Uttar Pradesh", SeatType.MLA),
    ("Rath", "Uttar Pradesh", SeatType.MLA),
    # Hapur district (3)
    ("Hapur", "Uttar Pradesh", SeatType.MLA),
    ("Garhmukteshwar", "Uttar Pradesh", SeatType.MLA),
    ("Dhaulana", "Uttar Pradesh", SeatType.MLA),
    # Hardoi district (8)
    ("Sawayajpur", "Uttar Pradesh", SeatType.MLA),
    ("Shahabad", "Uttar Pradesh", SeatType.MLA),
    ("Hardoi", "Uttar Pradesh", SeatType.MLA),
    ("Gopamau", "Uttar Pradesh", SeatType.MLA),
    ("Sandi", "Uttar Pradesh", SeatType.MLA),
    ("Bilgram-Mallanwan", "Uttar Pradesh", SeatType.MLA),
    ("Balamau", "Uttar Pradesh", SeatType.MLA),
    ("Sandila", "Uttar Pradesh", SeatType.MLA),
    # Hathras district (3)
    ("Hathras", "Uttar Pradesh", SeatType.MLA),
    ("Sadabad", "Uttar Pradesh", SeatType.MLA),
    ("Sikandra Rao", "Uttar Pradesh", SeatType.MLA),
    # Jalaun district (3)
    ("Madhogarh", "Uttar Pradesh", SeatType.MLA),
    ("Kalpi", "Uttar Pradesh", SeatType.MLA),
    ("Orai", "Uttar Pradesh", SeatType.MLA),
    # Jaunpur district (9)
    ("Badlapur", "Uttar Pradesh", SeatType.MLA),
    ("Jaunpur", "Uttar Pradesh", SeatType.MLA),
    ("Kerakat", "Uttar Pradesh", SeatType.MLA),
    ("Machhlishahr", "Uttar Pradesh", SeatType.MLA),
    ("Malhani", "Uttar Pradesh", SeatType.MLA),
    ("Mariyahu", "Uttar Pradesh", SeatType.MLA),
    ("Mungra Badshahpur", "Uttar Pradesh", SeatType.MLA),
    ("Shahganj", "Uttar Pradesh", SeatType.MLA),
    ("Zafrabad", "Uttar Pradesh", SeatType.MLA),
    # Jhansi district (4)
    ("Babina", "Uttar Pradesh", SeatType.MLA),
    ("Jhansi Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Mauranipur", "Uttar Pradesh", SeatType.MLA),
    ("Garautha", "Uttar Pradesh", SeatType.MLA),
    # Kannauj district (3)
    ("Chhibramau", "Uttar Pradesh", SeatType.MLA),
    ("Tirwa", "Uttar Pradesh", SeatType.MLA),
    ("Kannauj", "Uttar Pradesh", SeatType.MLA),
    # Kanpur Dehat district (4)
    ("Rasulabad", "Uttar Pradesh", SeatType.MLA),
    ("Akbarpur-Raniya", "Uttar Pradesh", SeatType.MLA),
    ("Sikandra", "Uttar Pradesh", SeatType.MLA),
    ("Bhognipur", "Uttar Pradesh", SeatType.MLA),
    # Kanpur Nagar district (10)
    ("Sishamau", "Uttar Pradesh", SeatType.MLA),
    ("Arya Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Kidwai Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Govind Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Kanpur Cantonment", "Uttar Pradesh", SeatType.MLA),
    ("Bithoor", "Uttar Pradesh", SeatType.MLA),
    ("Kalyanpur", "Uttar Pradesh", SeatType.MLA),
    ("Maharajpur", "Uttar Pradesh", SeatType.MLA),
    ("Ghatampur", "Uttar Pradesh", SeatType.MLA),
    ("Bilhaur", "Uttar Pradesh", SeatType.MLA),
    # Kasganj district (3)
    ("Kasganj", "Uttar Pradesh", SeatType.MLA),
    ("Amanpur", "Uttar Pradesh", SeatType.MLA),
    ("Patiyali", "Uttar Pradesh", SeatType.MLA),
    # Kaushambi district (3)
    ("Sirathu", "Uttar Pradesh", SeatType.MLA),
    ("Manjhanpur", "Uttar Pradesh", SeatType.MLA),
    ("Chail", "Uttar Pradesh", SeatType.MLA),
    # Lakhimpur Kheri district (8)
    ("Palia", "Uttar Pradesh", SeatType.MLA),
    ("Nighasan", "Uttar Pradesh", SeatType.MLA),
    ("Gola Gokrannath", "Uttar Pradesh", SeatType.MLA),
    ("Srinagar", "Uttar Pradesh", SeatType.MLA),
    ("Dhaurahra", "Uttar Pradesh", SeatType.MLA),
    ("Lakhimpur", "Uttar Pradesh", SeatType.MLA),
    ("Kasta", "Uttar Pradesh", SeatType.MLA),
    ("Mohammadi", "Uttar Pradesh", SeatType.MLA),
    # Kushinagar district (7)
    ("Khadda", "Uttar Pradesh", SeatType.MLA),
    ("Padrauna", "Uttar Pradesh", SeatType.MLA),
    ("Tamkuhi Raj", "Uttar Pradesh", SeatType.MLA),
    ("Fazilnagar", "Uttar Pradesh", SeatType.MLA),
    ("Kasia", "Uttar Pradesh", SeatType.MLA),
    ("Hata", "Uttar Pradesh", SeatType.MLA),
    ("Ramkola", "Uttar Pradesh", SeatType.MLA),
    # Lalitpur district (2)
    ("Lalitpur", "Uttar Pradesh", SeatType.MLA),
    ("Mehroni", "Uttar Pradesh", SeatType.MLA),
    # Lucknow district (9)
    ("Malihabad", "Uttar Pradesh", SeatType.MLA),
    ("Bakhshi Ka Talab", "Uttar Pradesh", SeatType.MLA),
    ("Sarojini Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Lucknow West", "Uttar Pradesh", SeatType.MLA),
    ("Lucknow North", "Uttar Pradesh", SeatType.MLA),
    ("Lucknow East", "Uttar Pradesh", SeatType.MLA),
    ("Lucknow Central", "Uttar Pradesh", SeatType.MLA),
    ("Lucknow Cantt", "Uttar Pradesh", SeatType.MLA),
    ("Mohanlalganj", "Uttar Pradesh", SeatType.MLA),
    # Maharajganj district (5)
    ("Pharenda", "Uttar Pradesh", SeatType.MLA),
    ("Nautanwa", "Uttar Pradesh", SeatType.MLA),
    ("Siswa", "Uttar Pradesh", SeatType.MLA),
    ("Maharajganj", "Uttar Pradesh", SeatType.MLA),
    ("Paniyara", "Uttar Pradesh", SeatType.MLA),
    # Mahoba district (2)
    ("Mahoba", "Uttar Pradesh", SeatType.MLA),
    ("Charkhari", "Uttar Pradesh", SeatType.MLA),
    # Mainpuri district (4)
    ("Mainpuri", "Uttar Pradesh", SeatType.MLA),
    ("Bhongaon", "Uttar Pradesh", SeatType.MLA),
    ("Kishni", "Uttar Pradesh", SeatType.MLA),
    ("Karhal", "Uttar Pradesh", SeatType.MLA),
    # Mathura district (5)
    ("Chhata", "Uttar Pradesh", SeatType.MLA),
    ("Mant", "Uttar Pradesh", SeatType.MLA),
    ("Goverdhan", "Uttar Pradesh", SeatType.MLA),
    ("Mathura", "Uttar Pradesh", SeatType.MLA),
    ("Baldev", "Uttar Pradesh", SeatType.MLA),
    # Mau district (4)
    ("Madhuban", "Uttar Pradesh", SeatType.MLA),
    ("Ghosi", "Uttar Pradesh", SeatType.MLA),
    ("Muhammadabad-Gohna", "Uttar Pradesh", SeatType.MLA),
    ("Mau", "Uttar Pradesh", SeatType.MLA),
    # Meerut district (7)
    ("Siwalkhas", "Uttar Pradesh", SeatType.MLA),
    ("Sardhana", "Uttar Pradesh", SeatType.MLA),
    ("Hastinapur", "Uttar Pradesh", SeatType.MLA),
    ("Kithore", "Uttar Pradesh", SeatType.MLA),
    ("Meerut Cantt", "Uttar Pradesh", SeatType.MLA),
    ("Meerut", "Uttar Pradesh", SeatType.MLA),
    ("Meerut South", "Uttar Pradesh", SeatType.MLA),
    # Mirzapur district (5)
    ("Chhanbey", "Uttar Pradesh", SeatType.MLA),
    ("Mirzapur", "Uttar Pradesh", SeatType.MLA),
    ("Majhawan", "Uttar Pradesh", SeatType.MLA),
    ("Chunar", "Uttar Pradesh", SeatType.MLA),
    ("Marihan", "Uttar Pradesh", SeatType.MLA),
    # Moradabad district (6)
    ("Thakurdwara", "Uttar Pradesh", SeatType.MLA),
    ("Kanth", "Uttar Pradesh", SeatType.MLA),
    ("Moradabad Rural", "Uttar Pradesh", SeatType.MLA),
    ("Moradabad Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Kundarki", "Uttar Pradesh", SeatType.MLA),
    ("Bilari", "Uttar Pradesh", SeatType.MLA),
    # Muzaffarnagar district (6)
    ("Muzaffarnagar", "Uttar Pradesh", SeatType.MLA),
    ("Budhana", "Uttar Pradesh", SeatType.MLA),
    ("Charthawal", "Uttar Pradesh", SeatType.MLA),
    ("Khatauli", "Uttar Pradesh", SeatType.MLA),
    ("Meerapur", "Uttar Pradesh", SeatType.MLA),
    ("Purqazi", "Uttar Pradesh", SeatType.MLA),
    # Pilibhit district (4)
    ("Pilibhit", "Uttar Pradesh", SeatType.MLA),
    ("Barkhera", "Uttar Pradesh", SeatType.MLA),
    ("Puranpur", "Uttar Pradesh", SeatType.MLA),
    ("Bisalpur", "Uttar Pradesh", SeatType.MLA),
    # Pratapgarh district (7)
    ("Rampur Khas", "Uttar Pradesh", SeatType.MLA),
    ("Babaganj", "Uttar Pradesh", SeatType.MLA),
    ("Kunda", "Uttar Pradesh", SeatType.MLA),
    ("Vishwanathganj", "Uttar Pradesh", SeatType.MLA),
    ("Pratapgarh", "Uttar Pradesh", SeatType.MLA),
    ("Patti", "Uttar Pradesh", SeatType.MLA),
    ("Raniganj", "Uttar Pradesh", SeatType.MLA),
    # Raebareli district (5)
    ("Bachhrawan", "Uttar Pradesh", SeatType.MLA),
    ("Harchandpur", "Uttar Pradesh", SeatType.MLA),
    ("Raebareli", "Uttar Pradesh", SeatType.MLA),
    ("Sareni", "Uttar Pradesh", SeatType.MLA),
    ("Unchahar", "Uttar Pradesh", SeatType.MLA),
    # Rampur district (5)
    ("Suar", "Uttar Pradesh", SeatType.MLA),
    ("Chamraua", "Uttar Pradesh", SeatType.MLA),
    ("Bilaspur", "Uttar Pradesh", SeatType.MLA),
    ("Rampur", "Uttar Pradesh", SeatType.MLA),
    ("Milak", "Uttar Pradesh", SeatType.MLA),
    # Saharanpur district (7)
    ("Behat", "Uttar Pradesh", SeatType.MLA),
    ("Nakur", "Uttar Pradesh", SeatType.MLA),
    ("Saharanpur Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Saharanpur Dehat", "Uttar Pradesh", SeatType.MLA),
    ("Deoband", "Uttar Pradesh", SeatType.MLA),
    ("Rampur Maniharan", "Uttar Pradesh", SeatType.MLA),
    ("Gangoh", "Uttar Pradesh", SeatType.MLA),
    # Sambhal district (4)
    ("Sambhal", "Uttar Pradesh", SeatType.MLA),
    ("Chandausi", "Uttar Pradesh", SeatType.MLA),
    ("Asmoli", "Uttar Pradesh", SeatType.MLA),
    ("Gunnaur", "Uttar Pradesh", SeatType.MLA),
    # Sant Kabir Nagar district (3)
    ("Mehdawal", "Uttar Pradesh", SeatType.MLA),
    ("Khalilabad", "Uttar Pradesh", SeatType.MLA),
    ("Dhanghata", "Uttar Pradesh", SeatType.MLA),
    # Shahjahanpur district (6)
    ("Katra", "Uttar Pradesh", SeatType.MLA),
    ("Jalalabad", "Uttar Pradesh", SeatType.MLA),
    ("Tilhar", "Uttar Pradesh", SeatType.MLA),
    ("Powayan", "Uttar Pradesh", SeatType.MLA),
    ("Shahjahanpur", "Uttar Pradesh", SeatType.MLA),
    ("Dadraul", "Uttar Pradesh", SeatType.MLA),
    # Shamli district (3)
    ("Shamli", "Uttar Pradesh", SeatType.MLA),
    ("Kairana", "Uttar Pradesh", SeatType.MLA),
    ("Thana Bhawan", "Uttar Pradesh", SeatType.MLA),
    # Shravasti district (2)
    ("Shravasti", "Uttar Pradesh", SeatType.MLA),
    ("Bhinga", "Uttar Pradesh", SeatType.MLA),
    # Siddharthnagar district (5)
    ("Shohratgarh", "Uttar Pradesh", SeatType.MLA),
    ("Kapilvastu", "Uttar Pradesh", SeatType.MLA),
    ("Bansi", "Uttar Pradesh", SeatType.MLA),
    ("Itwa", "Uttar Pradesh", SeatType.MLA),
    ("Domariyaganj", "Uttar Pradesh", SeatType.MLA),
    # Sitapur district (9)
    ("Maholi", "Uttar Pradesh", SeatType.MLA),
    ("Sitapur", "Uttar Pradesh", SeatType.MLA),
    ("Hargaon", "Uttar Pradesh", SeatType.MLA),
    ("Laharpur", "Uttar Pradesh", SeatType.MLA),
    ("Biswan", "Uttar Pradesh", SeatType.MLA),
    ("Sevata", "Uttar Pradesh", SeatType.MLA),
    ("Mahmoodabad", "Uttar Pradesh", SeatType.MLA),
    ("Sidhauli", "Uttar Pradesh", SeatType.MLA),
    ("Misrikh", "Uttar Pradesh", SeatType.MLA),
    # Sonbhadra district (4)
    ("Robertsganj", "Uttar Pradesh", SeatType.MLA),
    ("Ghorawal", "Uttar Pradesh", SeatType.MLA),
    ("Obra", "Uttar Pradesh", SeatType.MLA),
    ("Duddhi", "Uttar Pradesh", SeatType.MLA),
    # Sultanpur district (5)
    ("Isauli", "Uttar Pradesh", SeatType.MLA),
    ("Sultanpur", "Uttar Pradesh", SeatType.MLA),
    ("Sadar", "Uttar Pradesh", SeatType.MLA),
    ("Lambhua", "Uttar Pradesh", SeatType.MLA),
    ("Kadipur", "Uttar Pradesh", SeatType.MLA),
    # Unnao district (6)
    ("Bangarmau", "Uttar Pradesh", SeatType.MLA),
    ("Safipur", "Uttar Pradesh", SeatType.MLA),
    ("Mohan", "Uttar Pradesh", SeatType.MLA),
    ("Unnao", "Uttar Pradesh", SeatType.MLA),
    ("Bhagwant Nagar", "Uttar Pradesh", SeatType.MLA),
    ("Purwa", "Uttar Pradesh", SeatType.MLA),
    # Varanasi district (8)
    ("Pindra", "Uttar Pradesh", SeatType.MLA),
    ("Ajagara", "Uttar Pradesh", SeatType.MLA),
    ("Shivpur", "Uttar Pradesh", SeatType.MLA),
    ("Rohaniya", "Uttar Pradesh", SeatType.MLA),
    ("Varanasi North", "Uttar Pradesh", SeatType.MLA),
    ("Varanasi South", "Uttar Pradesh", SeatType.MLA),
    ("Varanasi Cantt", "Uttar Pradesh", SeatType.MLA),
    ("Sevapuri", "Uttar Pradesh", SeatType.MLA),

    # Goa - Vidhan Sabha / MLA (40) - see module docstring for this
    # state's search-cross-referenced provenance.
    # North Goa Lok Sabha grouping (20)
    ("Mandrem", "Goa", SeatType.MLA),
    ("Pernem", "Goa", SeatType.MLA),
    ("Bicholim", "Goa", SeatType.MLA),
    ("Tivim", "Goa", SeatType.MLA),
    ("Mapusa", "Goa", SeatType.MLA),
    ("Siolim", "Goa", SeatType.MLA),
    ("Saligao", "Goa", SeatType.MLA),
    ("Calangute", "Goa", SeatType.MLA),
    ("Porvorim", "Goa", SeatType.MLA),
    ("Aldona", "Goa", SeatType.MLA),
    ("Panaji", "Goa", SeatType.MLA),
    ("Taleigao", "Goa", SeatType.MLA),
    ("Santa Cruz", "Goa", SeatType.MLA),
    ("St. Andre", "Goa", SeatType.MLA),
    ("Cumbarjua", "Goa", SeatType.MLA),
    ("Maem", "Goa", SeatType.MLA),
    ("Sanquelim", "Goa", SeatType.MLA),
    ("Poriem", "Goa", SeatType.MLA),
    ("Valpoi", "Goa", SeatType.MLA),
    ("Priol", "Goa", SeatType.MLA),
    # South Goa Lok Sabha grouping (20)
    ("Ponda", "Goa", SeatType.MLA),
    ("Siroda", "Goa", SeatType.MLA),
    ("Marcaim", "Goa", SeatType.MLA),
    ("Mormugao", "Goa", SeatType.MLA),
    ("Vasco Da Gama", "Goa", SeatType.MLA),
    ("Dabolim", "Goa", SeatType.MLA),
    ("Cortalim", "Goa", SeatType.MLA),
    ("Nuvem", "Goa", SeatType.MLA),
    ("Curtorim", "Goa", SeatType.MLA),
    ("Fatorda", "Goa", SeatType.MLA),
    ("Margao", "Goa", SeatType.MLA),
    ("Benaulim", "Goa", SeatType.MLA),
    ("Navelim", "Goa", SeatType.MLA),
    ("Cuncolim", "Goa", SeatType.MLA),
    ("Velim", "Goa", SeatType.MLA),
    ("Quepem", "Goa", SeatType.MLA),
    ("Curchorem", "Goa", SeatType.MLA),
    ("Sanvordem", "Goa", SeatType.MLA),
    ("Sanguem", "Goa", SeatType.MLA),
    ("Canacona", "Goa", SeatType.MLA),

    # Himachal Pradesh - Vidhan Sabha / MLA (68) - see module docstring
    # for this state's search-cross-referenced provenance; Kangra,
    # Hamirpur, Mandi, and Shimla each collide with the Lok Sabha seat of
    # the same name (same treatment as every other MP/MLA collision in
    # this file).
    # Kangra Lok Sabha grouping (17)
    ("Churah", "Himachal Pradesh", SeatType.MLA),
    ("Chamba", "Himachal Pradesh", SeatType.MLA),
    ("Dalhousie", "Himachal Pradesh", SeatType.MLA),
    ("Bhattiyat", "Himachal Pradesh", SeatType.MLA),
    ("Nurpur", "Himachal Pradesh", SeatType.MLA),
    ("Indora", "Himachal Pradesh", SeatType.MLA),
    ("Fatehpur", "Himachal Pradesh", SeatType.MLA),
    ("Jawali", "Himachal Pradesh", SeatType.MLA),
    ("Jawalamukhi", "Himachal Pradesh", SeatType.MLA),
    ("Jaisinghpur", "Himachal Pradesh", SeatType.MLA),
    ("Sullah", "Himachal Pradesh", SeatType.MLA),
    ("Nagrota", "Himachal Pradesh", SeatType.MLA),
    ("Kangra", "Himachal Pradesh", SeatType.MLA),
    ("Shahpur", "Himachal Pradesh", SeatType.MLA),
    ("Dharamshala", "Himachal Pradesh", SeatType.MLA),
    ("Palampur", "Himachal Pradesh", SeatType.MLA),
    ("Baijnath", "Himachal Pradesh", SeatType.MLA),
    # Hamirpur Lok Sabha grouping (17)
    ("Dehra", "Himachal Pradesh", SeatType.MLA),
    ("Jaswan-Pragpur", "Himachal Pradesh", SeatType.MLA),
    ("Dharampur", "Himachal Pradesh", SeatType.MLA),
    ("Bhoranj", "Himachal Pradesh", SeatType.MLA),
    ("Sujanpur", "Himachal Pradesh", SeatType.MLA),
    ("Hamirpur", "Himachal Pradesh", SeatType.MLA),
    ("Barsar", "Himachal Pradesh", SeatType.MLA),
    ("Nadaun", "Himachal Pradesh", SeatType.MLA),
    ("Chintpurni", "Himachal Pradesh", SeatType.MLA),
    ("Gagret", "Himachal Pradesh", SeatType.MLA),
    ("Haroli", "Himachal Pradesh", SeatType.MLA),
    ("Una", "Himachal Pradesh", SeatType.MLA),
    ("Kutlehar", "Himachal Pradesh", SeatType.MLA),
    ("Jhanduta", "Himachal Pradesh", SeatType.MLA),
    ("Ghumarwin", "Himachal Pradesh", SeatType.MLA),
    ("Bilaspur", "Himachal Pradesh", SeatType.MLA),
    ("Sri Naina Deviji", "Himachal Pradesh", SeatType.MLA),
    # Mandi Lok Sabha grouping (17)
    ("Kinnaur", "Himachal Pradesh", SeatType.MLA),
    ("Bharmour", "Himachal Pradesh", SeatType.MLA),
    ("Lahaul and Spiti", "Himachal Pradesh", SeatType.MLA),
    ("Manali", "Himachal Pradesh", SeatType.MLA),
    ("Kullu", "Himachal Pradesh", SeatType.MLA),
    ("Banjar", "Himachal Pradesh", SeatType.MLA),
    ("Anni", "Himachal Pradesh", SeatType.MLA),
    ("Karsog", "Himachal Pradesh", SeatType.MLA),
    ("Sundernagar", "Himachal Pradesh", SeatType.MLA),
    ("Nachan", "Himachal Pradesh", SeatType.MLA),
    ("Seraj", "Himachal Pradesh", SeatType.MLA),
    ("Darang", "Himachal Pradesh", SeatType.MLA),
    ("Jogindernagar", "Himachal Pradesh", SeatType.MLA),
    ("Mandi", "Himachal Pradesh", SeatType.MLA),
    ("Balh", "Himachal Pradesh", SeatType.MLA),
    ("Sarkaghat", "Himachal Pradesh", SeatType.MLA),
    ("Rampur", "Himachal Pradesh", SeatType.MLA),
    # Shimla Lok Sabha grouping (17)
    ("Arki", "Himachal Pradesh", SeatType.MLA),
    ("Nalagarh", "Himachal Pradesh", SeatType.MLA),
    ("Doon", "Himachal Pradesh", SeatType.MLA),
    ("Solan", "Himachal Pradesh", SeatType.MLA),
    ("Kasauli", "Himachal Pradesh", SeatType.MLA),
    ("Pachhad", "Himachal Pradesh", SeatType.MLA),
    ("Nahan", "Himachal Pradesh", SeatType.MLA),
    ("Sri Renukaji", "Himachal Pradesh", SeatType.MLA),
    ("Paonta Sahib", "Himachal Pradesh", SeatType.MLA),
    ("Shillai", "Himachal Pradesh", SeatType.MLA),
    ("Chopal", "Himachal Pradesh", SeatType.MLA),
    ("Theog", "Himachal Pradesh", SeatType.MLA),
    ("Kasumpti", "Himachal Pradesh", SeatType.MLA),
    ("Shimla", "Himachal Pradesh", SeatType.MLA),
    ("Shimla Rural", "Himachal Pradesh", SeatType.MLA),
    ("Jubbal-Kotkhai", "Himachal Pradesh", SeatType.MLA),
    ("Rohru", "Himachal Pradesh", SeatType.MLA),

    # Gujarat Vidhan Sabha (MLA) seats: not seeded yet - see module
    # docstring.
]
