import os
import json
import tempfile
import sqlite3

import pytest


def test_output_formats(fixtures, fuzzy_rule_match):
    scan_path = fixtures.path('flask_app.py')

    # Test plain text output
    cli = fixtures.get_cli_output(['scan', scan_path, '--format', 'text'])
    output = cli.output
    assert '---[ Scan results for ' in output
    assert 'Scan score: ' in output

    # Test JSON output
    cli = fixtures.get_cli_output(['scan', scan_path, '--format', 'json'])
    output = json.loads(cli.output)
    assert output.get('name')
    assert len(output.get('hits', [])) > 3

    # Test SQLite output
    db_path = tempfile.NamedTemporaryFile()
    cli = fixtures.get_cli_output(
        ['scan', scan_path, '--format', 'sqlite', '--output-path', db_path.name]
    )
    db = sqlite3.connect(db_path.name)
    db.row_factory = sqlite3.Row

    inputs = [dict(x) for x in db.execute('SELECT * FROM inputs').fetchall()]
    assert len(inputs) == 1

    hits = [dict(x) for x in db.execute('SELECT * FROM hits').fetchall()]
    assert len(hits) > 3

    files = [dict(x) for x in db.execute('SELECT * FROM files').fetchall()]
    assert len(files) == 1

    with open(scan_path, 'rb') as fd:
        print(files)
        assert fd.read() == files[0]['data']


def test_non_existing(fixtures):
    """
    Test the behaviour if a non-existing location is passed to aura for scanning
    Aura should fail with exit code 1
    Printing error message to stdout
    No traceback should be printed as it should be handled by cli instead of propagating to interpreter
    """
    pth = 'does_not_exists_on_earth.py'
    cli = fixtures.get_cli_output(['scan', pth], check_exit_code=False)

    assert (cli.exception is None) or (type(cli.exception) == SystemExit)
    assert cli.exit_code == 1
    # Check that stderr doesn't contain traceback information
    assert "Traceback" not in cli.stderr
    # stderr should contain the error message
    assert "Invalid location" in cli.stderr
    # stdout should not contain any of these
    assert "Traceback" not in cli.stdout
    assert "Invalid location" not in cli.stdout


@pytest.mark.parametrize(
    "output_type",
    (
        "text",
        "json",
        "sqlite"
    )
)
def test_output_not_created_when_below_minimum_score(output_type, fixtures):
    """
    Test that an output file is never created if the minimum score is never reached
    This also tests that the output results are not outputted on stdout
    """
    with tempfile.TemporaryDirectory(prefix="aura_pytest_tempd_") as tmpd:
        cli = fixtures.scan_test_file(
            "misc.py",
            decode=False,
            args=[
                "--format", output_type,
                "--min-score", 1000,
                "--output-path", f"{tmpd}/aura_output"
            ]
        )

        assert len(os.listdir(tmpd)) == 0
        assert not os.path.exists(f"{tmpd}/aura_output")

        for keyword in ("os.system", "eval", "__reduce__"):
            assert keyword not in cli.stdout, (keyword, cli.stdout)