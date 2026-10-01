import json

from dotsci_protocol.cli import main


def make_dir(tmp_path):
    (tmp_path / "results.json").write_text('{"x": 1}')
    (tmp_path / "log.txt").write_text("hello")
    return tmp_path


def test_commit_prove_verify_round_trip(tmp_path, capsys):
    directory = tmp_path / "out"
    directory.mkdir()
    make_dir(directory)
    assert main(["commit", str(directory)]) == 0
    committed = json.loads(capsys.readouterr().out)
    assert committed["size"] == 2 and committed["root"].startswith("0x") and len(committed["root"]) == 66

    assert main(["prove", str(directory), "log.txt"]) == 0
    proof = json.loads(capsys.readouterr().out)
    assert proof["root"] == committed["root"]
    proof_file = tmp_path / "proof.json"
    proof_file.write_text(json.dumps(proof))

    assert main(["verify", committed["root"], str(proof_file)]) == 0
    assert main(["verify", "0x" + "00" * 32, str(proof_file)]) == 1


def test_errors_are_reported_not_raised(tmp_path, capsys):
    assert main(["commit", str(tmp_path / "missing")]) == 1
    directory = tmp_path / "d"
    directory.mkdir()
    (directory / "a.txt").write_text("a")
    assert main(["prove", str(directory), "nope.txt"]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert main(["verify", "0x" + "00" * 32, str(bad)]) == 1
