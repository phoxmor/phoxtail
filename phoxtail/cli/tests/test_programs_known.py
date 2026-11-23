"""Every program the CLI starts is one `tools.py` knows how to check for.

Commands check their programs before acting (`tools.require`), and that
only works for programs `tools.py` lists with an install hint. This reads
the CLI's source, finds every place it starts a program, and fails on one
it does not know, or on a launch it cannot read, so a new program cannot
ship unchecked.

`phoxtail/media/signals.py` runs ffmpeg inside Django on the server, not
from the CLI, so it is out of scope.
"""

import ast
from pathlib import Path

import pytest

from phoxtail.cli.utils import tools

CLI = Path(tools.__file__).parents[1]
KNOWN = (set(tools._INSTALL) - {tools.COMPOSE}) | {"sys.executable"}
LAUNCHERS = {"run", "call", "Popen", "check_call", "check_output"}
OTHER_WAYS = {"system", "popen", "execv", "execvp", "execl", "execlp", "spawnv", "spawnl"}


def programs_started(source: str) -> tuple[set[str], list[str]]:
    """The programs *source* starts, and the launches it could not read."""
    tree = ast.parse(source)
    constants = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    programs: set[str] = set()
    unreadable: list[str] = []

    def first(node: ast.expr, local: dict[str, list[ast.expr]]) -> set[str] | None:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return first(node.left, local)
        if isinstance(node, ast.Name) and node.id in local:
            found = [first(value, local) for value in local[node.id]]
            return None if None in found else set().union(*found)  # type: ignore[arg-type]
        if not (isinstance(node, ast.List) and node.elts):
            return None
        head = node.elts[0]
        if isinstance(head, ast.Starred):
            return first(head.value, local)
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return {head.value}
        if isinstance(head, ast.Name) and head.id in constants:
            return {constants[head.id]}
        if ast.unparse(head) == "sys.executable":
            return {"sys.executable"}
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("subprocess", "asyncio"):
            unreadable.append(f"line {node.lineno}: imports from {node.module}; call it as {node.module}.<name>")
        if isinstance(node, ast.Import) and any(a.name == "subprocess" and a.asname for a in node.names):
            unreadable.append(f"line {node.lineno}: renames subprocess")

    # Every node belongs to one scope, the module or its innermost function,
    # so each launch is read once, against that scope's own names.
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    for scope in [tree, *(n for n in ast.walk(tree) if isinstance(n, functions))]:
        own: list[ast.AST] = []
        pending = list(ast.iter_child_nodes(scope))
        while pending:
            child = pending.pop()
            own.append(child)
            if not isinstance(child, functions):
                pending.extend(ast.iter_child_nodes(child))
        local: dict[str, list[ast.expr]] = {}
        for inner in own:
            if isinstance(inner, ast.Assign) and isinstance(inner.targets[0], ast.Name):
                local.setdefault(inner.targets[0].id, []).append(inner.value)
        for call in own:
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                continue
            owner, name = ast.unparse(call.func.value), call.func.attr
            if owner == "os" and name in OTHER_WAYS or owner == "asyncio" and name.startswith("create_subprocess"):
                unreadable.append(f"line {call.lineno}: {owner}.{name}; use subprocess with a literal command")
            elif owner == "subprocess" and name in LAUNCHERS:
                found = first(call.args[0], local) if call.args else None
                if found is None:
                    unreadable.append(f"line {call.lineno}: can't tell what this runs")
                else:
                    programs |= found
    return programs, unreadable


@pytest.mark.parametrize("path", sorted(p for p in CLI.rglob("*.py") if "tests" not in p.parts), ids=str)
def test_every_program_started_is_known(path):
    programs, unreadable = programs_started(path.read_text())
    assert not unreadable, f"{path.relative_to(CLI)}: " + "; ".join(unreadable)
    unknown = programs - KNOWN
    assert not unknown, (
        f"{path.relative_to(CLI)} starts {sorted(unknown)}: add it to tools.py with its install hint, "
        "and tools.require it before the command acts."
    )


class TestTheScan:
    """The scan itself, on small sources: it finds what it must."""

    def test_an_unknown_program_is_named(self):
        programs, _ = programs_started('import subprocess\ndef f():\n    subprocess.run(["ffmpeg", "-i", "x"])\n')
        assert programs - KNOWN == {"ffmpeg"}

    def test_a_command_built_first_is_followed(self):
        source = 'import subprocess\ndef f():\n    cmd = ["docker", "ps"]\n    subprocess.call(cmd)\n'
        assert programs_started(source) == ({"docker"}, [])

    def test_a_command_it_cannot_read_fails(self):
        _, unreadable = programs_started("import subprocess\ndef f():\n    subprocess.run(make())\n")
        assert unreadable == ["line 3: can't tell what this runs"]

    def test_a_launch_outside_any_function_is_read(self):
        programs, _ = programs_started('import subprocess\nsubprocess.run(["ffmpeg"])\n')
        assert programs == {"ffmpeg"}

    def test_a_name_from_another_function_is_not_borrowed(self):
        source = 'import subprocess\ndef a():\n    cmd = ["docker"]\ndef b(cmd):\n    subprocess.run(cmd)\n'
        assert programs_started(source)[1] == ["line 5: can't tell what this runs"]

    def test_starting_a_program_another_way_fails(self):
        _, unreadable = programs_started('from subprocess import run\ndef f():\n    run(["ffmpeg"])\n')
        assert unreadable and "imports from subprocess" in unreadable[0]
