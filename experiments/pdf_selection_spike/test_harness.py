"""Native-state and JS-unit tests; never described as browser/DOM evidence."""

import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

from fixtures import CASES, make_snapshot
from spike_state import HarnessState, STATE_KEY, transition

HERE = Path(__file__).parent


@pytest.fixture(autouse=True)
def fresh_component_registry(monkeypatch):
    # Each AppTest owns a fresh runtime; register inside it, not during collection.
    monkeypatch.delitem(sys.modules, "component", raising=False)


def test_transition_rejects_replay_and_recovers():
    initial = HarnessState(("unicode", 1, 0), make_snapshot("unicode", 1, "mount"))
    event = dict(version=1, revision=initial.snapshot.revision, instance="mount", page=1,
                 sequence=1, ranges=[[0, 1, 4]], text="😀积分")
    accepted = transition(initial, event)
    assert accepted.selection.text == "😀积分"
    replay = transition(accepted, event)
    assert replay.last_sequence == 1 and replay.selection is None and replay.error
    event["sequence"] = 2
    recovered = transition(replay, event)
    assert recovered.last_sequence == 2 and recovered.error is None


@pytest.mark.parametrize("case", CASES)
def test_fixture_app_mount_and_navigation(case, monkeypatch):
    monkeypatch.syspath_prepend(str(HERE))
    app = AppTest.from_file(str(HERE / "app.py")).run()
    assert not app.exception
    app.selectbox(key="g3_case").select(case).run()
    assert not app.exception
    first = app.session_state[STATE_KEY]
    app.button[0].click().run()
    assert app.session_state[STATE_KEY].snapshot.instance == first.snapshot.instance
    app.selectbox(key="g3_page").select(2).run()
    assert not app.exception
    assert app.session_state[STATE_KEY].snapshot.instance != first.snapshot.instance
    assert app.session_state[STATE_KEY].selection is None


def test_app_rehydrates_acceptance_and_invalidates_remount(monkeypatch):
    monkeypatch.syspath_prepend(str(HERE))
    app = AppTest.from_file(str(HERE / "app.py")).run()
    state = app.session_state[STATE_KEY]
    event = dict(version=1, revision=state.snapshot.revision, instance=state.snapshot.instance,
                 page=1, sequence=1, ranges=[[0, 0, 6]], text="Select")
    # AppTest cannot emit a CCv2 DOM selection. Inject a separately tested transition.
    app.session_state[STATE_KEY] = transition(state, event)
    app.run()
    assert not app.exception
    assert app.code[0].value == "Select"
    app.button[0].click().run()
    assert app.code[0].value == "Select"
    app.number_input[0].set_value(1).run()
    assert not app.exception
    assert app.session_state[STATE_KEY].selection is None
    assert len(app.code) == 0


def test_js_unicode_event_matches_python_contract():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node runtime needed for isolated JS unit test")
    fixture = make_snapshot("unicode", 1, "mount")
    module = ast.parse((HERE / "component.py").read_text(encoding="utf-8"))
    js = next(ast.literal_eval(node.value) for node in module.body
              if isinstance(node, ast.Assign) and any(
                  isinstance(target, ast.Name) and target.id == "JS" for target in node.targets))
    script = js + """
const assert = (await import('node:assert/strict')).default;
assert.equal(codePointOffset('A😀积分', 3), 2);
assert.equal(codePointOffset('A😀积分', 5), 4);
assert.throws(() => codePointOffset('A😀积分', 2));
assert.throws(() => codePointOffset('abc', -1));
assert.throws(() => codePointOffset('abc', 1.2));
const data = {revision:'synthetic-v1:unicode', instance:'mount', page:1,
              spans:[{text:'A😀积分 ∑ α é 中文'}]};
assert.throws(() => selectionEvent(data, [], 1));
assert.throws(() => selectionEvent(data, [[0,0,100]], 1));
console.log(JSON.stringify(selectionEvent(data, [[0,1,4]], 1)));
"""
    result = subprocess.run([node, "--input-type=module"], input=script, text=True,
                            encoding="utf-8", capture_output=True, timeout=15, check=True)
    accepted = transition(HarnessState(("unicode", 1, 0), fixture), json.loads(result.stdout))
    assert accepted.selection.text == "😀积分"
