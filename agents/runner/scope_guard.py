"""Static scope guard for the runner's Page Object edits.

Prompt instructions alone didn't hold the line here: in testing, the runner
was told explicitly "touch only what this failure implicates" and still
bundled an unrelated property "improvement" into a fix. This module gives
the outer Python loop a way to catch that mechanically instead of trusting
the model to self-police.

The key finding that shaped this design: a pytest traceback's captured call
stack includes the actual source line that raised the error (e.g.
`page_obj.username_input.fill(username)` from the module layer), so it
names the exact property involved even when the test itself only calls a
module-level flow function like `login(...)` that touches several
properties. Matching property names against the traceback text is a much
tighter signal than asking "which properties could this test conceivably
reach" via static call-graph analysis -- verified directly: for a test that
calls `login()` (which touches both username_input and password_input), a
locator timeout on username_input produces a traceback containing
"username_input" but NOT "password_input", because the failing call never
reached the password_input line. The call-graph approach would have allowed
both properties for that test; traceback matching correctly allows only one.

Deliberately scoped to Page Object property-level changes only -- it does
not guard module.py/fixtures.py edits. That's a documented boundary, not an
oversight: the observed failure mode was specifically a page-object property
edited outside the failing test's need, and a precise guard across all 4
layers would be a much larger static-analysis project for a failure mode
that hasn't actually been observed there.
"""

import ast
import re


def _property_blocks(source: str) -> dict[str, str]:
    """Map property name -> its full source text (decorator + body) in a Page Object file."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    class_node = next((n for n in tree.body if isinstance(n, ast.ClassDef)), None)
    if class_node is None:
        return {}
    blocks: dict[str, str] = {}
    for node in class_node.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any(isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list):
            continue
        deco_start = min(d.lineno for d in node.decorator_list) - 1
        blocks[node.name] = "".join(lines[deco_start:node.end_lineno])
    return blocks


def changed_properties(before: str, after: str) -> set[str]:
    """Property names whose source block differs between two file versions."""
    before_blocks = _property_blocks(before)
    after_blocks = _property_blocks(after)
    return {
        name for name, block in after_blocks.items()
        if before_blocks.get(name) != block
    }


def _find_function(source: str, name: str) -> ast.FunctionDef | None:
    tree = ast.parse(source)
    return next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name),
        None,
    )


def _direct_property_refs(func: ast.FunctionDef, fixture_param: str) -> set[str]:
    return {
        node.attr
        for node in ast.walk(func)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == fixture_param
    }


def _called_names(func: ast.FunctionDef) -> set[str]:
    return {
        node.func.id
        for node in ast.walk(func)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _module_function_property_refs(module_source: str, function_names: set[str]) -> set[str]:
    if not function_names:
        return set()
    tree = ast.parse(module_source)
    refs: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name in function_names):
            continue
        if not node.args.args:
            continue
        first_param = node.args.args[0].arg
        refs |= {
            inner.attr
            for inner in ast.walk(node)
            if isinstance(inner, ast.Attribute)
            and isinstance(inner.value, ast.Name)
            and inner.value.id == first_param
        }
    return refs


def _known_property_names(page_object_source: str) -> set[str]:
    return set(_property_blocks(page_object_source).keys())


def properties_named_in_traceback(traceback_text: str, known_names: set[str]) -> set[str]:
    """Property names that literally appear (as whole identifiers) in the
    failure's traceback/call-stack text -- the primary, evidence-based
    signal. See module docstring for why this beats a static call-graph.
    """
    return {name for name in known_names if re.search(rf"\b{re.escape(name)}\b", traceback_text)}


def allowed_properties(
    test_name: str,
    traceback_text: str,
    page_object_source: str,
    spec_source: str,
    module_source: str | None,
) -> set[str] | None:
    """Properties this failing test may legitimately need touched in the
    Page Object. Prefers evidence (property names named in the traceback);
    falls back to static call-graph reachability only when the traceback
    doesn't name anything (e.g. a pure assertion mismatch with no locator
    call in the failing frame). Returns None if the test function can't be
    statically resolved at all -- callers should skip the guard rather than
    block the pipeline on an analysis edge case, not treat None as "nothing
    allowed".
    """
    known_names = _known_property_names(page_object_source)
    from_evidence = properties_named_in_traceback(traceback_text, known_names)
    if from_evidence:
        return from_evidence

    func = _find_function(spec_source, test_name)
    if func is None or not func.args.args:
        return None
    fixture_param = func.args.args[0].arg

    direct = _direct_property_refs(func, fixture_param)
    called = _called_names(func)
    transitive = _module_function_property_refs(module_source, called) if module_source else set()
    return direct | transitive


def test_name_from_nodeid(nodeid: str) -> str:
    """'tests/specs/test_login.py::test_foo[chromium]' -> 'test_foo'"""
    name = nodeid.split("::")[-1]
    return name.split("[")[0]
