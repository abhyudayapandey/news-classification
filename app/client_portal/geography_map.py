"""The client portal's district/seat map widget - see
app/routers/client_ui.py's dashboard and geography-detail routes.

Map geometry (SVG path data, one file per state per view) lives under
app/static/maps/<slug>/{districts,seats}.json, generated once by a
scratch script from two open datasets (a per-state Census-2011 district
TopoJSON and an all-India ECI assembly-constituency shapefile) and
matched by name against our own seeded gazetteer
(app/data/district_seed.py / constituency_seed.py, which stays the
source of truth for names - the open datasets are trusted for geometry
only). A shape whose name didn't match anything seeded is still present
in the file (so the state outline isn't missing a piece) but flagged
`"matched": false`, and the map only makes matched shapes clickable.

MAP_STATES is deliberately the same 7 states the gazetteer itself covers
(app/data/constituency_seed.py's own docstring) - there is no map data,
and so no map feature, for a state with no seeded district/constituency
names to click through to.
"""

MAP_STATES = ["Rajasthan", "Uttar Pradesh", "Punjab", "Uttarakhand", "Goa", "Himachal Pradesh", "Gujarat"]


def state_slug(state: str) -> str:
    return state.lower().replace(" ", "-")
