"""Custom sidebar navigation.

st.navigation's own section headers are static text labels - they aren't
clickable, can't collapse, and have no active state. A section header that
looks like a page button, toggles its children open/closed, and stays
highlighted while one of those children is active needs more than that, so
app.py hides the built-in nav (position="hidden") and the sidebar is rebuilt
here from st.button + st.page_link.

Routing is untouched: st.navigation still owns the page objects, their URLs
and the dispatch. Only the sidebar chrome is ours - which also means its
appearance is ours to maintain across Streamlit upgrades.

Any number of sections can be rendered (one per model - LDV, HDV, ...), and a
section can nest subsections (Saved Scenarios inside LDV Model). Each keeps
its own independent collapse state, and indents one step further per level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

import streamlit as st
from streamlit.navigation.page import StreamlitPage


@dataclass(frozen=True)
class NavSection:
    """One collapsible group in the sidebar: its own pages, then any nested
    subsections beneath them.

    `key` names the section's widgets and its CSS hooks, so it has to be
    unique across every section and legal inside a CSS class name - letters,
    digits, hyphens and underscores only.

    `start_expanded` is the collapse state on the first load of a session;
    after that the user's own toggling sticks until the tab is refreshed.
    """

    label: str
    key: str
    pages: list[StreamlitPage] = field(default_factory=list)
    subsections: list["NavSection"] = field(default_factory=list)
    start_expanded: bool = True

    def walk(self) -> Iterator["NavSection"]:
        """This section and every section nested under it."""
        yield self
        for sub in self.subsections:
            yield from sub.walk()

    def all_pages(self) -> Iterator[StreamlitPage]:
        """Every page in this section and its descendants."""
        for section in self.walk():
            yield from section.pages


def walk_sections(sections: list[NavSection], depth: int = 0):
    """(section, depth) for every section in the tree, parents before children."""
    for section in sections:
        yield section, depth
        yield from walk_sections(section.subsections, depth + 1)


def all_pages(sections: list[NavSection]) -> list[StreamlitPage]:
    """Every page across every section, in sidebar order - the list
    st.navigation needs."""
    return [page for section, _ in walk_sections(sections) for page in section.pages]


# Each nesting level indents by this much; level 0 sits at the page links'
# own 8px padding.
_BASE_PAD = 8
_INDENT_STEP = 20

# Streamlit's palette is theme-dependent (light and dark use different text,
# border and tint colours) and it exposes no CSS custom properties to read the
# active theme from. So nothing here is a hard-coded colour: the nav text
# inherits the sidebar's own colour, and the border and tint are derived from
# that with color-mix - which is how Streamlit builds its own (a border is
# rgba(text, 0.2), the active tint an ~0.15 overlay). Each color-mix is preceded
# by a mid-grey literal that reads acceptably on either theme, as a fallback for
# browsers without color-mix support.
_NAV_ITEM_HEIGHT = "32px"
_TINT_FALLBACK = "rgba(151, 166, 195, 0.15)"
_TINT = "color-mix(in srgb, currentColor 12%, transparent)"
_BORDER_FALLBACK = "rgba(151, 166, 195, 0.35)"
_BORDER = "color-mix(in srgb, currentColor 20%, transparent)"

# Every state in which a section header must keep the page-link text colour.
# A tertiary button otherwise turns primary-coloured on hover and focus.
_PINNED_STATES = [
    " button",
    " button:hover",
    " button:focus",
    " button:focus-visible",
    " button:active",
    " button p",
    ' button [data-testid="stIconMaterial"]',
]


def _toggle_key(section: NavSection) -> str:
    return f"nav_toggle_{section.key}"


def _subnav_key(section: NavSection) -> str:
    return f"nav_subnav_{section.key}"


def _state_key(section: NavSection) -> str:
    return f"nav_expanded_{section.key}"


def _selector(keys: list[str], *suffixes: str) -> str:
    """A comma-separated selector list covering every key x suffix pairing.
    Streamlit puts an `st-key-<widget key>` class on each keyed widget's
    container, which is the only stable styling hook it offers."""
    return ",\n    ".join(f"div.st-key-{k}{sfx}" for k in keys for sfx in suffixes)


def _indent_rules(sections: list[NavSection]) -> str:
    """Per-level indents. A nested section's own header sits where its parent's
    page links sit, and its links step in once more.

    Subnav containers are rendered as siblings rather than nested inside one
    another (see _render_section), so no container's selector can also match a
    deeper container's links - the padding of each level is set exactly once."""
    by_depth: dict[int, dict[str, list[str]]] = {}
    for section, depth in walk_sections(sections):
        level = by_depth.setdefault(depth, {"toggles": [], "subnavs": []})
        level["toggles"].append(_toggle_key(section))
        if section.pages:
            level["subnavs"].append(_subnav_key(section))

    rules = []
    for depth, level in sorted(by_depth.items()):
        toggle_pad = _BASE_PAD + depth * _INDENT_STEP
        link_pad = _BASE_PAD + (depth + 1) * _INDENT_STEP
        if level["toggles"]:
            rules.append(
                f"{_selector(level['toggles'], ' button')} {{ padding-left: {toggle_pad}px; }}"
            )
        if level["subnavs"]:
            rules.append(
                f"{_selector(level['subnavs'], ' a')} {{ padding-left: {link_pad}px !important; }}"
            )
    return "\n    ".join(rules)


def _css(sections: list[NavSection], active_keys: set[str]) -> str:
    """Styling the built-in nav would otherwise have given us for free: make
    section buttons read as nav items rather than buttons, indent each level
    under the one above, and paint an active section to match st.page_link's
    own active state (which Streamlit applies to the active page for us).

    All sections share one stylesheet - only the active-state rules and the
    per-level indents are emitted per section."""
    toggles = [_toggle_key(s) for s, _ in walk_sections(sections)]
    # Only top-level sections are outlined. A nested section sits inside its
    # parent's group, which already reads as one block - a second box drawn
    # inside the first just adds noise.
    top_toggles = [_toggle_key(s) for s, depth in walk_sections(sections) if depth == 0]
    active_toggles = [
        _toggle_key(s) for s, _ in walk_sections(sections) if s.key in active_keys
    ]

    active_rules = (
        f"""
    {_selector(active_toggles, " button")} {{
        background-color: {_TINT_FALLBACK};
        background-color: {_TINT};
    }}
    {_selector(active_toggles, " button p")} {{ font-weight: 600; }}
    """
        if active_toggles
        else ""
    )

    return f"""
    <style>
    /* Match st.page_link's geometry so section headers line up with the page
       links above and below them. */
    {_selector(toggles, "")} {{ margin-bottom: 2px; }}
    {_selector(toggles, " button")} {{
        height: {_NAV_ITEM_HEIGHT};
        min-height: {_NAV_ITEM_HEIGHT};
        padding-right: 8px;
        border-radius: 8px;
        border: none;
    }}
    {_selector(top_toggles, " button")} {{
        border: 1px solid {_BORDER_FALLBACK};
        border-color: {_BORDER};
    }}
    /* A button centres its content; nav items are left-aligned. The centring
       lives on the inner wrapper, not the button itself. */
    {_selector(toggles, " button > div")} {{
        justify-content: flex-start;
        width: 100%;
    }}
    {_selector(toggles, " button > div > span")} {{
        display: flex;
        align-items: center;
        justify-content: flex-start;
        width: 100%;
    }}
    /* Chevron to the far right, so labels start flush with the page links. The
       margin goes on the icon's wrapper span - the icon itself is only as wide
       as the glyph, so auto margins on it do nothing. */
    {_selector(toggles, " button > div > span > span")} {{
        margin-left: auto;
    }}
    /* Inheriting rather than pinning a literal keeps labels the same colour as
       the page links in whichever theme is active. */
    {_selector(toggles, *_PINNED_STATES)} {{
        color: inherit !important;
    }}
    {_selector(toggles, " button:focus", " button:focus-visible")} {{
        box-shadow: none;
        outline: none;
    }}
    {_selector(toggles, " button:hover")} {{
        background-color: {_TINT_FALLBACK};
        background-color: {_TINT};
    }}
    {active_rules}
    /* One indent step per nesting level. */
    {_indent_rules(sections)}
    </style>
    """


def _render_section(section: NavSection) -> None:
    """Header button, then this section's own page links, then any nested
    subsections - the latter rendered as siblings rather than inside this
    section's container, so each level's indent is styled exactly once."""
    state_key = _state_key(section)
    expanded = st.session_state[state_key]

    if st.button(
        section.label,
        key=_toggle_key(section),
        type="tertiary",
        width="stretch",
        icon=":material/expand_more:" if expanded else ":material/chevron_right:",
        icon_position="right",
    ):
        # Toggle only - a section is deliberately not a page of its own.
        # Rerun so the chevron redraws: the button was already sent to the
        # frontend with the pre-click icon earlier in this same run.
        st.session_state[state_key] = not expanded
        st.rerun()

    if not st.session_state[state_key]:
        return

    if section.pages:
        with st.container(key=_subnav_key(section)):
            for page in section.pages:
                st.page_link(page, width="stretch")

    for subsection in section.subsections:
        _render_section(subsection)


def render_sidebar(
    landing: StreamlitPage,
    sections: list[NavSection],
    active: StreamlitPage,
) -> None:
    """Draw the sidebar: the landing page link, then each section in order.
    `active` is the page st.navigation resolved for this run - used to decide
    which section headers show as active, which they do whenever one of their
    own pages (or a nested subsection's) is open, collapsed or not."""
    active_keys = {
        section.key
        for section, _ in walk_sections(sections)
        if any(p.url_path == active.url_path for p in section.all_pages())
    }

    for section, _ in walk_sections(sections):
        st.session_state.setdefault(_state_key(section), section.start_expanded)

    with st.sidebar:
        st.markdown(_css(sections, active_keys), unsafe_allow_html=True)
        st.page_link(landing, width="stretch")
        for section in sections:
            _render_section(section)
