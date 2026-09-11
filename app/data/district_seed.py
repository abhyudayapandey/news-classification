"""District reference data for app/processing/geography.py's bare-name
district matching - see that module's docstring for why a bare mention
(no "district" suffix) needs a curated name list rather than a generic
capitalized-phrase guess.

PROVENANCE AND CONFIDENCE - read before trusting this for anything
client-facing: this list was generated from training-data knowledge, not
fetched from an authoritative source - this build environment's network
egress blocks every reference site (ECI, state government portals,
Wikipedia) the same way it blocks every news domain used elsewhere in
this codebase. It has NOT been verified against an official source.

District boundaries in India are genuinely unstable, not just
theoretically: Rajasthan alone went from 33 districts to 50 in mid-2023,
then had most of those new districts merged back by the following state
government in 2024 - this file uses Rajasthan's long-stable 33-district
list on the theory that it's the least likely to already be wrong again
by the time anyone reads this, not because it's confirmed current. Treat
every state's list here as "good faith, needs a verification pass,"
exactly like config/outlets.yaml's feed URLs needed one - re-run
verification whenever a state's district count is in the news.

SCOPE: only the states this build is actively being pitched in
(Rajasthan, Uttar Pradesh, Punjab, Uttarakhand) are seeded so far. Adding
another state is a mechanical, self-contained addition to DISTRICTS below
- see sync_districts() for how it reaches the app.
"""

# (district name, state) - state values match app/processing/jurisdiction.py's
# INDIAN_STATES spelling exactly, so a guessed state and a guessed district
# can be cross-checked against each other.
DISTRICTS: list[tuple[str, str]] = [
    # Rajasthan (33 - the long-stable list; see module docstring on why not the 2023 50-district split)
    ("Ajmer", "Rajasthan"),
    ("Alwar", "Rajasthan"),
    ("Banswara", "Rajasthan"),
    ("Baran", "Rajasthan"),
    ("Barmer", "Rajasthan"),
    ("Bharatpur", "Rajasthan"),
    ("Bhilwara", "Rajasthan"),
    ("Bikaner", "Rajasthan"),
    ("Bundi", "Rajasthan"),
    ("Chittorgarh", "Rajasthan"),
    ("Churu", "Rajasthan"),
    ("Dausa", "Rajasthan"),
    ("Dholpur", "Rajasthan"),
    ("Dungarpur", "Rajasthan"),
    ("Hanumangarh", "Rajasthan"),
    ("Jaipur", "Rajasthan"),
    ("Jaisalmer", "Rajasthan"),
    ("Jalore", "Rajasthan"),
    ("Jhalawar", "Rajasthan"),
    ("Jhunjhunu", "Rajasthan"),
    ("Jodhpur", "Rajasthan"),
    ("Karauli", "Rajasthan"),
    ("Kota", "Rajasthan"),
    ("Nagaur", "Rajasthan"),
    ("Pali", "Rajasthan"),
    ("Pratapgarh", "Rajasthan"),
    ("Rajsamand", "Rajasthan"),
    ("Sawai Madhopur", "Rajasthan"),
    ("Sikar", "Rajasthan"),
    ("Sirohi", "Rajasthan"),
    ("Sri Ganganagar", "Rajasthan"),
    ("Tonk", "Rajasthan"),
    ("Udaipur", "Rajasthan"),

    # Uttar Pradesh (75)
    ("Agra", "Uttar Pradesh"),
    ("Aligarh", "Uttar Pradesh"),
    ("Prayagraj", "Uttar Pradesh"),
    ("Ambedkar Nagar", "Uttar Pradesh"),
    ("Amethi", "Uttar Pradesh"),
    ("Amroha", "Uttar Pradesh"),
    ("Auraiya", "Uttar Pradesh"),
    ("Ayodhya", "Uttar Pradesh"),
    ("Azamgarh", "Uttar Pradesh"),
    ("Baghpat", "Uttar Pradesh"),
    ("Bahraich", "Uttar Pradesh"),
    ("Ballia", "Uttar Pradesh"),
    ("Balrampur", "Uttar Pradesh"),
    ("Banda", "Uttar Pradesh"),
    ("Barabanki", "Uttar Pradesh"),
    ("Bareilly", "Uttar Pradesh"),
    ("Basti", "Uttar Pradesh"),
    ("Bhadohi", "Uttar Pradesh"),
    ("Bijnor", "Uttar Pradesh"),
    ("Budaun", "Uttar Pradesh"),
    ("Bulandshahr", "Uttar Pradesh"),
    ("Chandauli", "Uttar Pradesh"),
    ("Chitrakoot", "Uttar Pradesh"),
    ("Deoria", "Uttar Pradesh"),
    ("Etah", "Uttar Pradesh"),
    ("Etawah", "Uttar Pradesh"),
    ("Farrukhabad", "Uttar Pradesh"),
    ("Fatehpur", "Uttar Pradesh"),
    ("Firozabad", "Uttar Pradesh"),
    ("Gautam Buddha Nagar", "Uttar Pradesh"),
    ("Ghaziabad", "Uttar Pradesh"),
    ("Ghazipur", "Uttar Pradesh"),
    ("Gonda", "Uttar Pradesh"),
    ("Gorakhpur", "Uttar Pradesh"),
    ("Hamirpur", "Uttar Pradesh"),
    ("Hapur", "Uttar Pradesh"),
    ("Hardoi", "Uttar Pradesh"),
    ("Hathras", "Uttar Pradesh"),
    ("Jalaun", "Uttar Pradesh"),
    ("Jaunpur", "Uttar Pradesh"),
    ("Jhansi", "Uttar Pradesh"),
    ("Kannauj", "Uttar Pradesh"),
    ("Kanpur Dehat", "Uttar Pradesh"),
    ("Kanpur Nagar", "Uttar Pradesh"),
    ("Kasganj", "Uttar Pradesh"),
    ("Kaushambi", "Uttar Pradesh"),
    ("Lakhimpur Kheri", "Uttar Pradesh"),
    ("Kushinagar", "Uttar Pradesh"),
    ("Lalitpur", "Uttar Pradesh"),
    ("Lucknow", "Uttar Pradesh"),
    ("Maharajganj", "Uttar Pradesh"),
    ("Mahoba", "Uttar Pradesh"),
    ("Mainpuri", "Uttar Pradesh"),
    ("Mathura", "Uttar Pradesh"),
    ("Mau", "Uttar Pradesh"),
    ("Meerut", "Uttar Pradesh"),
    ("Mirzapur", "Uttar Pradesh"),
    ("Moradabad", "Uttar Pradesh"),
    ("Muzaffarnagar", "Uttar Pradesh"),
    ("Pilibhit", "Uttar Pradesh"),
    ("Pratapgarh", "Uttar Pradesh"),
    ("Raebareli", "Uttar Pradesh"),
    ("Rampur", "Uttar Pradesh"),
    ("Saharanpur", "Uttar Pradesh"),
    ("Sambhal", "Uttar Pradesh"),
    ("Sant Kabir Nagar", "Uttar Pradesh"),
    ("Shahjahanpur", "Uttar Pradesh"),
    ("Shamli", "Uttar Pradesh"),
    ("Shravasti", "Uttar Pradesh"),
    ("Siddharthnagar", "Uttar Pradesh"),
    ("Sitapur", "Uttar Pradesh"),
    ("Sonbhadra", "Uttar Pradesh"),
    ("Sultanpur", "Uttar Pradesh"),
    ("Unnao", "Uttar Pradesh"),
    ("Varanasi", "Uttar Pradesh"),

    # Punjab (23)
    ("Amritsar", "Punjab"),
    ("Barnala", "Punjab"),
    ("Bathinda", "Punjab"),
    ("Faridkot", "Punjab"),
    ("Fatehgarh Sahib", "Punjab"),
    ("Fazilka", "Punjab"),
    ("Ferozepur", "Punjab"),
    ("Gurdaspur", "Punjab"),
    ("Hoshiarpur", "Punjab"),
    ("Jalandhar", "Punjab"),
    ("Kapurthala", "Punjab"),
    ("Ludhiana", "Punjab"),
    ("Malerkotla", "Punjab"),
    ("Mansa", "Punjab"),
    ("Moga", "Punjab"),
    ("Sri Muktsar Sahib", "Punjab"),
    ("Pathankot", "Punjab"),
    ("Patiala", "Punjab"),
    ("Rupnagar", "Punjab"),
    ("Mohali", "Punjab"),
    ("Sangrur", "Punjab"),
    ("Shaheed Bhagat Singh Nagar", "Punjab"),
    ("Tarn Taran", "Punjab"),

    # Uttarakhand (13)
    ("Almora", "Uttarakhand"),
    ("Bageshwar", "Uttarakhand"),
    ("Chamoli", "Uttarakhand"),
    ("Champawat", "Uttarakhand"),
    ("Dehradun", "Uttarakhand"),
    ("Haridwar", "Uttarakhand"),
    ("Nainital", "Uttarakhand"),
    ("Pauri Garhwal", "Uttarakhand"),
    ("Pithoragarh", "Uttarakhand"),
    ("Rudraprayag", "Uttarakhand"),
    ("Tehri Garhwal", "Uttarakhand"),
    ("Udham Singh Nagar", "Uttarakhand"),
    ("Uttarkashi", "Uttarakhand"),
]
