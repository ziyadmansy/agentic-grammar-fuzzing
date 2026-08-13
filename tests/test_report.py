import json

from scripts.make_report import main


def test_report_contains_campaign_metrics(tmp_path, monkeypatch) -> None:
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps({"status": "accepted", "structure": "{}"}) + "\n")
    output = tmp_path / "report.md"
    monkeypatch.setattr("sys.argv", ["make_report", str(results), "--output", str(output)])

    main()

    assert "Acceptance rate: 100.0%" in output.read_text()