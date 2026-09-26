"""Guards the contracts the frontend depends on but cannot test itself.

There is no frontend test runner in this repository, so a rule that only exists in a
`.module.css` file or inside a Cytoscape stylesheet object has no test of its own. Two
real defects lived in exactly that gap: the Miro palette migration left six
`var(--token)` references undefined, and nothing complained because a missing custom
property does not fail a build, a type check, or a lint run. It silently renders the
badge or the map node with no colour at all.

These tests read the source instead of a rendered DOM. That is a weaker guarantee than
a browser test and does not pretend to be one: it proves the rule is still written down
and that every token it names resolves. What it buys is that deleting or renaming a
rule, or editing a stylesheet without touching `index.css`, now fails the suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# `pytest.ini` sets `pythonpath = .` and the suite is run from `backend/`, so the
# frontend sits at a fixed relative location rather than being discovered.
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
INDEX_CSS = FRONTEND_SRC / "index.css"
CONNECTION_MAP = FRONTEND_SRC / "components" / "ConnectionMap.jsx"

_TOKEN_DECLARATION = re.compile(r"^\s*(--[a-z0-9-]+)\s*:", re.MULTILINE)
_TOKEN_REFERENCE = re.compile(r"var\(\s*(--[a-z0-9-]+)")


def _source_files() -> list[Path]:
    return sorted(
        path
        for pattern in ("**/*.css", "**/*.jsx", "**/*.js")
        for path in FRONTEND_SRC.glob(pattern)
    )


def _declared_tokens() -> set[str]:
    return set(_TOKEN_DECLARATION.findall(INDEX_CSS.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def declared() -> set[str]:
    return _declared_tokens()


def test_the_token_stylesheet_exists_and_declares_something() -> None:
    assert INDEX_CSS.is_file(), "index.css is the only place tokens are edited"
    assert len(_declared_tokens()) > 30, "the token set collapsed - did :root get gutted?"


def test_every_referenced_token_is_declared(declared: set[str]) -> None:
    """A `var(--x)` with no `--x` renders as nothing, silently.

    This is the exact failure the palette migration introduced.
    """

    undefined: dict[str, list[str]] = {}
    for path in _source_files():
        referenced = set(_TOKEN_REFERENCE.findall(path.read_text(encoding="utf-8")))
        missing = referenced - declared
        if missing:
            undefined[path.name] = sorted(missing)

    assert not undefined, (
        "these tokens are referenced but never declared in index.css: "
        f"{undefined}. A missing custom property does not fail the build - it renders "
        "with no colour, which is how the EXISTS and MISSING badges lost their palette."
    )


def test_status_and_entity_hues_are_still_distinct(declared: set[str]) -> None:
    """The status and entity hues carry meaning, so they must not be one colour.

    `--mutual`, `--missing` and `--oneway` are the three connection states; `--person`
    and `--place` are the two entity kinds. AGENTS.md §9 forbids collapsing them and
    forbids a `--positive` token returning in place of `--mutual`.
    """

    required = {
        "--mutual",
        "--missing",
        "--oneway",
        "--person",
        "--place",
        "--seed",
    }
    assert not (required - declared), f"missing status/entity tokens: {required - declared}"

    values = dict(
        (token, value)
        for token, value in re.findall(
            r"^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);", INDEX_CSS.read_text(encoding="utf-8"), re.MULTILINE
        )
    )
    for group in (("--mutual", "--missing", "--oneway"), ("--person", "--place")):
        resolved = {values[token].strip() for token in group}
        assert len(resolved) == len(group), f"these hues are now identical: {group}"


def test_positive_token_has_not_returned(declared: set[str]) -> None:
    assert "--positive" not in declared, (
        "AGENTS.md §9: success is --mutual. A green CTA is not a success indicator."
    )


def test_missing_nodes_are_styled_distinctly_on_the_map() -> None:
    """The missing-connection highlight is a stylesheet rule and nothing else.

    Without this there is no test that could notice it being deleted, which is why
    Phase 5 could never close its "missing-highlight test" exit criterion.
    """

    source = CONNECTION_MAP.read_text(encoding="utf-8")

    assert "selector: 'node[!exists]'" in source, (
        "the map no longer styles nodes with exists=false, so missing connections lose "
        "their highlight"
    )
    # The colour has to arrive as a value Cytoscape can parse. It used to be
    # asserted as the literal string "'background-color': 'var(--missing)'", which is
    # the form that silently dropped every colour on the map - see
    # test_cytoscape_styles_never_use_css_custom_properties. What matters is that the
    # missing node is painted from the --missing token, not a hardcoded hue.
    assert "const missing = token('--missing')" in source, (
        "the map must read --missing off :root; a literal hue here would drift from "
        "index.css, and 'var(--missing)' would not survive Cytoscape's parser at all"
    )
    assert "'background-color': missing" in source, (
        "missing nodes must be painted with the --missing hue, not a default node colour"
    )
    assert "shape: 'round-diamond'" in source, (
        "missing nodes also change shape; a colour-only cue fails for a reader who "
        "cannot distinguish the hues"
    )


def test_cytoscape_styles_never_use_css_custom_properties(declared: set[str]) -> None:
    """Cytoscape drops any `var()` colour, so the map loses its whole palette.

    Cytoscape resolves a style colour through `color2tuple`, which understands a
    named colour, hex, `rgb()` and `hsl()` and nothing else. A `var(--x)` returns
    nothing, the property is discarded, and the graph renders in Cytoscape's
    defaults - no error, no failed build, no failed lint. That is UAT-01: missing
    entities were not highlighted at all, and nothing in the repository noticed.

    The tokens are therefore read off `:root` with `getComputedStyle` and passed
    to Cytoscape as literals. This test is the guard for that decision.
    """

    source = CONNECTION_MAP.read_text(encoding="utf-8")
    stylesheet = source[source.index("function stylesheet()") :]

    offenders = _TOKEN_REFERENCE.findall(stylesheet)
    assert not offenders, (
        f"the Cytoscape stylesheet passes {sorted(set(offenders))} to Cytoscape, which "
        "cannot resolve CSS custom properties and will drop the property. Read the token "
        "with token('--name') instead."
    )

    # Every token the stylesheet asks for must exist, and must be a literal form
    # color2tuple accepts, or the fix above would read back an empty string.
    requested = set(re.findall(r"token\(\s*['\"](--[a-z0-9-]+)['\"]\s*\)", stylesheet))
    assert requested, "the stylesheet reads no tokens at all - did the fix get reverted?"
    assert not (requested - declared), f"read but never declared in index.css: {requested - declared}"

    values = dict(
        re.findall(r"^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);", INDEX_CSS.read_text(encoding="utf-8"), re.MULTILINE)
    )
    unparseable = {
        name: values[name].strip()
        for name in requested
        if not re.match(
            r"^(#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla)\()", values[name].strip()
        )
    }
    assert not unparseable, (
        f"these tokens are not a colour form Cytoscape can parse, so the map falls back "
        f"to its defaults: {unparseable}"
    )


def test_entity_nodes_are_styled_on_the_map() -> None:
    """Added in 570c49b: person and place nodes must not both fall back to one style."""

    source = CONNECTION_MAP.read_text(encoding="utf-8")

    for entity, shape in (("person", "ellipse"), ("place", "round-rectangle")):
        selector = f"""selector: 'node[entityType = "{entity}"]'"""
        assert selector in source, (
            f"{entity} nodes have no selector, so they render as the default node"
        )
        assert f"shape: '{shape}'" in source, (
            f"{entity} nodes must differ in shape as well as colour"
        )


def test_map_forwards_the_entity_type_from_the_payload() -> None:
    """`570c49b` only styles a node if the backend actually sends the field."""

    source = CONNECTION_MAP.read_text(encoding="utf-8")

    assert "entityType: node.entity_type" in source, (
        "elementsFor must copy entity_type onto the Cytoscape element, or the "
        "entity-type selectors can never match"
    )


def test_the_legend_names_every_node_type_the_map_draws() -> None:
    source = CONNECTION_MAP.read_text(encoding="utf-8")

    for label in ("Article node", "Person node", "Place node", "Missing entity"):
        assert f"label: '{label}'" in source, f"the legend lost its '{label}' entry"
