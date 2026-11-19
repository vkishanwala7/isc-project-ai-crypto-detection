"""API end-to-end tests: health, validation, analyze, sign, verify, integrity lab, cases, report, audit."""
from __future__ import annotations

from conftest import make_jpeg

from app.services.evidence import interpret


def test_health_reports_subsystems(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert set(j["subsystems"]) >= {"api", "database", "ai_model", "c2pa", "signing_keys"}
    assert j["subsystems"]["c2pa"]["ok"] is True
    assert j["status"] in ("ok", "degraded")


def test_upload_type_validation(client):
    r = client.post("/api/analyze", files={"file": ("x.jpg", b"GIF89a fake", "image/jpeg")})
    assert r.status_code == 415 and r.json()["detail"]["code"] == "UNSUPPORTED_FORMAT"
    r = client.post("/api/analyze", files={"file": ("x.jpg", b"", "image/jpeg")})
    assert r.status_code == 400


def test_upload_size_validation(client, monkeypatch):
    from app.core.config import settings
    object.__setattr__(settings, "max_image_bytes", 1000)
    try:
        r = client.post("/api/analyze", files={"file": ("big.jpg", make_jpeg(), "image/jpeg")})
    finally:
        object.__setattr__(settings, "max_image_bytes", 15 * 1024 * 1024)
    assert r.status_code == 413 and r.json()["detail"]["code"] == "FILE_TOO_LARGE"


def test_analyze_persists_case_with_separate_dimensions(client):
    r = client.post("/api/analyze", files={"file": ("scene.jpg", make_jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["kind"] == "analysis"
    assert c["provenance_status"] == "NO_PROVENANCE_FOUND"
    assert c["analyses"] and c["provenance"]
    assert c["summary"]["provenance_dimension"] == "NO_PROVENANCE_FOUND"
    assert "fake" not in c["summary"]["headline"].lower()
    # durable case retrievable via id and share reference
    assert client.get(f"/api/cases/{c['id']}").status_code == 200
    assert client.get(f"/api/cases/{c['share_ref']}").json()["id"] == c["id"]


def test_sign_verify_tamper_flow(client):
    jpeg = make_jpeg(seed=9)
    r = client.post("/api/provenance/sign", files={"file": ("cap.jpg", jpeg, "image/jpeg")}, data={"source": "browser_capture"})
    assert r.status_code == 200, r.text
    c = r.json()
    rec = next(p for p in c["provenance"] if p["operation"] == "sign")
    assert rec["status"] == "VALID_PROVENANCE"
    assert rec["details"]["post_sign_verification"]["c2pa"]["status"] == "VALID_PROVENANCE"
    assert "after browser capture" in rec["details"]["capture_statement"]
    signed = next(a for a in c["assets"] if a["role"] == "signed")
    env = next(a for a in c["assets"] if a["role"] == "envelope")
    sb = client.get(signed["url"]).content
    eb = client.get(env["url"]).content

    # independent verification of the downloaded signed file + envelope
    v = client.post("/api/provenance/verify", files={"file": ("s.jpg", sb, "image/jpeg"), "credential": ("e.json", eb, "application/json")}).json()
    assert v["provenance_status"] == "VALID_PROVENANCE"
    sim = v["provenance"][0]["details"]["similar_known_asset"]
    assert sim["found"] and sim["exact_byte_match"]

    # tampered copy fails
    b = bytearray(sb)
    b[-300] ^= 0x10
    v2 = client.post("/api/provenance/verify", files={"file": ("t.jpg", bytes(b), "image/jpeg"), "credential": ("e.json", eb, "application/json")}).json()
    assert v2["provenance_status"] == "TAMPERED_OR_INVALID"

    # verify by share reference
    rr = client.post(f"/api/provenance/verify-ref/{c['share_ref']}")
    assert rr.status_code == 200 and rr.json()["result"]["status"] == "VALID_PROVENANCE"


def test_upload_sign_uses_opened_action(client):
    r = client.post("/api/provenance/sign", files={"file": ("up.jpg", make_jpeg(seed=11), "image/jpeg")}, data={"source": "upload"})
    rec = next(p for p in r.json()["provenance"] if p["operation"] == "sign")
    actions = rec["details"]["post_sign_verification"]["c2pa"]["actions"]
    assert actions[0]["action"] == "c2pa.opened"


def test_integrity_lab_real_failures(client):
    r = client.post("/api/integrity/tamper-demo", data={"use_demo_asset": "true"})
    assert r.status_code == 200, r.text
    c = r.json()
    lab = next(p for p in c["provenance"] if p["operation"] == "tamper_test")["details"]
    assert all(lab["expectations_met"].values()), lab["expectations_met"]
    assert lab["signed"]["sha256"] != lab["tampered_bytes"]["sha256"]
    assert lab["tampered_bytes"]["bytes_changed"] == 1
    roles = {a["role"] for a in c["assets"]}
    assert {"original", "signed", "envelope", "tampered_bytes", "tampered_visual"} <= roles


def test_integrity_lab_never_modifies_original(client):
    jpeg = make_jpeg(seed=21)
    import hashlib
    c = client.post("/api/integrity/tamper-demo", files={"file": ("mine.jpg", jpeg, "image/jpeg")}).json()
    orig = next(a for a in c["assets"] if a["role"] == "original")
    assert orig["sha256"] == hashlib.sha256(jpeg).hexdigest()
    assert client.get(orig["url"]).content == jpeg


def test_report_export_and_audit(client):
    cases = client.get("/api/cases").json()
    assert cases["total"] >= 1
    cid = cases["items"][0]["id"]
    r = client.get(f"/api/cases/{cid}/report.json")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    rep = r.json()
    assert rep["case"]["id"] == cid and "disclaimer" in rep
    acts = client.get("/api/activity?limit=500").json()["items"]
    kinds = {a["action"] for a in acts}
    assert {"upload", "sign", "verify", "tamper_test", "report_export"} <= kinds


def test_dashboard_counts_from_records(client):
    d = client.get("/api/dashboard/summary").json()
    assert d["counts"]["total_cases"] == client.get("/api/cases?include_samples=false").json()["total"]
    assert d["counts"]["integrity_lab_runs"] >= 1
    assert len(d["activity_series"]) == 14


def test_delete_case(client):
    c = client.post("/api/provenance/verify", files={"file": ("d.jpg", make_jpeg(seed=30), "image/jpeg")}).json()
    asset_url = c["assets"][0]["url"]
    assert client.delete(f"/api/cases/{c['id']}").status_code == 200
    assert client.get(f"/api/cases/{c['id']}").status_code == 404
    assert client.get(asset_url).status_code == 404


def test_file_endpoint_rejects_paths(client):
    assert client.get("/api/files/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/api/files/" + "0" * 32).status_code == 404


def test_model_metrics_never_fabricated(client):
    m = client.get("/api/model/metrics").json()
    if not m["available"]:
        assert "test" not in m
    else:
        assert m["test"]["confusion_matrix"]["tp"] + m["test"]["confusion_matrix"]["fn"] == m["n_test_fake"]


def test_evidence_matrix_rules():
    assert "Integrity verification failed" in interpret({"status": "COMPLETED", "verdict": "LOW_MANIPULATION_SIGNAL"}, "TAMPERED_OR_INVALID")["headline"]
    h = interpret({"status": "COMPLETED", "verdict": "LOW_MANIPULATION_SIGNAL"}, "NO_PROVENANCE_FOUND")["headline"]
    assert "Origin remains unverified" in h and "fake" not in h.lower()
    h = interpret({"status": "MODEL_UNAVAILABLE", "verdict": "INCONCLUSIVE"}, "VALID_PROVENANCE")
    assert h["ai_dimension"] == "MODEL_UNAVAILABLE" and "no score was fabricated" in h["headline"]
    assert interpret({"status": "COMPLETED", "verdict": "LIKELY_MANIPULATED"}, "VALID_PROVENANCE")["tone"] == "warning"


def test_cors_restricted(client):
    r = client.options("/api/health", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "http://evil.example"
    r = client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
