import json

from pipeline.cli import main
from tests.conftest import FIXTURES


def run(capsys, *argv):
    rc = main(list(argv))
    return rc, json.loads(capsys.readouterr().out)


def test_cli_end_to_end_offline(archive, capsys, synthetic_video, tmp_path):
    rc, res = run(capsys, "ingest-video", str(synthetic_video), "--adapter", "local", "--media", "video",
                  "--lang", "en", "--synthetic")
    assert rc == 0 and res["stages"]["captions"] == "ok"
    sid = res["source_id"]

    rc, res = run(capsys, "extract-frames", sid, "--every", "3")
    assert len(res["frame_ids"]) == 2

    rc, res = run(capsys, "ingest-doc", str(FIXTURES / "synthetic_page.html"), "--synthetic")
    web_sid, snap = res["source_id"], res["snapshot_id"]

    rc, res = run(capsys, "add-trader", "SYNTHETIC-TRADER-B", "--synthetic")
    trader = res["trader_id"]

    rc, res = run(capsys, "add-observation", "--source-id", web_sid, "--snapshot-id", snap, "--kind", "quote",
                  "--content", "SYNTHETIC", "--quote", "alpha bravo", "--extractor", "human",
                  "--trader-id", trader, "--synthetic")
    assert res["quote_verified"] is True
    obs = res["observation_id"]

    rc, res = run(capsys, "add-trade", "--trader-id", trader, "--direction", "short",
                  "--evidence", f"{obs}:entry", "--status", "corroborated", "--synthetic")
    assert res["trade_id"].startswith("trade_")

    rc, res = run(capsys, "annotate", "observation", obs, "tag", '"synthetic"', "--annotator", "test",
                  "--synthetic")
    assert rc == 0

    rc, res = run(capsys, "status")
    assert res["tables"]["observations"] == 1 and res["synthetic_rows"]["trades"] == 1

    rc, res = run(capsys, "export-parquet", "--out", str(tmp_path / "pq"))
    assert len(res["written"]) > 10

    rc, res = run(capsys, "purge-synthetic")
    assert rc == 1 and "hint" in res                          # dry run without --yes
    rc, res = run(capsys, "purge-synthetic", "--yes")
    rc, res = run(capsys, "status")
    assert all(v == 0 for v in res["tables"].values())


def test_cli_reports_validation_errors(archive, capsys):
    rc, res = run(capsys, "add-observation", "--source-id", "src_nope", "--kind", "x", "--content", "y",
                  "--extractor", "human")
    assert rc == 1 and "unknown source_id" in res["error"]


def test_cli_query(archive, capsys):
    main(["query", "SELECT 1 AS one"])
    assert json.loads(capsys.readouterr().out) == [{"one": 1}]
