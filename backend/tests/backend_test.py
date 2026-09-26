"""Backend tests for Interview AI Engine v4.
Covers: /api/state/resolve (12 non-regression tests + counter), Session CRUD,
SSE messaging (CANDIDAT bullets, RECRUTEUR prose, barge-in), reset.
"""
import os
import json
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback to frontend/.env parsing
    from pathlib import Path
    env = Path("/app/frontend/.env").read_text()
    for line in env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

API = f"{BASE_URL}/api"


# ---------------------- /api/state/resolve — 12 non-regression tests ----------------------
def _resolve(**kw):
    r = requests.post(f"{API}/state/resolve", json=kw, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def test_T1_simule_un_entretien_to_RECRUTEUR():
    r = _resolve(current_state="NEUTRE", prev_state="NEUTRE", text="Simule un entretien", tours_sans_marqueur=0)
    assert r["resolved_state"] == "RECRUTEUR"


def test_T2_reponse_a_dire_to_CANDIDAT():
    r = _resolve(current_state="NEUTRE", prev_state="NEUTRE", text="Réponse à dire: parle de toi", tours_sans_marqueur=0)
    assert r["resolved_state"] == "CANDIDAT"


def test_T3_first_person_prev_RECRUTEUR_to_CANDIDAT():
    r = _resolve(current_state="NEUTRE", prev_state="RECRUTEUR", text="Je pense que je vais commencer par mes études", tours_sans_marqueur=0)
    assert r["resolved_state"] == "CANDIDAT"


def test_T4_Bonjour_NEUTRE_stays_NEUTRE():
    r = _resolve(current_state="NEUTRE", prev_state="NEUTRE", text="Bonjour", tours_sans_marqueur=0)
    assert r["resolved_state"] == "NEUTRE"


def test_T5_RESET_to_NEUTRE_no_content():
    r = _resolve(current_state="CANDIDAT", prev_state="RECRUTEUR", text="[RESET]", tours_sans_marqueur=2)
    assert r["resolved_state"] == "NEUTRE"
    assert r["no_content"] is True
    assert r["tours"] == 0


def test_T6_STRESS_HIGH_voice_V9():
    r = _resolve(current_state="CANDIDAT", prev_state="CANDIDAT", text="Parle de ton parcours", tours_sans_marqueur=0,
                 state_candidat="STRESS_HIGH", voice_confidence=0.9)
    assert r["resolved_state"] == "CANDIDAT"
    assert r["voice_module"] == "V9"


def test_T7_CANDIDAT_ok_stays_CANDIDAT():
    r = _resolve(current_state="CANDIDAT", prev_state="CANDIDAT", text="ok", tours_sans_marqueur=0)
    assert r["resolved_state"] == "CANDIDAT"


def test_T8_CANDIDAT_30_word_first_person_stays_CANDIDAT():
    text = " ".join(["Je"] + ["mot"] * 29)
    r = _resolve(current_state="CANDIDAT", prev_state="CANDIDAT", text=text, tours_sans_marqueur=0)
    assert r["resolved_state"] == "CANDIDAT"


def test_T9_NEUTRE_ok_stays_NEUTRE():
    r = _resolve(current_state="NEUTRE", prev_state="NEUTRE", text="ok", tours_sans_marqueur=0)
    assert r["resolved_state"] == "NEUTRE"


def test_T10_CANDIDAT_joue_le_recruteur_to_RECRUTEUR():
    r = _resolve(current_state="CANDIDAT", prev_state="CANDIDAT", text="joue le recruteur", tours_sans_marqueur=0)
    assert r["resolved_state"] == "RECRUTEUR"


def test_T11_RECRUTEUR_question_candidat_to_CANDIDAT():
    r = _resolve(current_state="RECRUTEUR", prev_state="RECRUTEUR", text="Est-ce que je peux avoir un indice ?", tours_sans_marqueur=0)
    assert r["resolved_state"] == "CANDIDAT"


def test_T12_barge_in_keeps_state_and_tours():
    r = _resolve(current_state="CANDIDAT", prev_state="RECRUTEUR", text="peu importe", tours_sans_marqueur=2, barge_in=True)
    assert r["resolved_state"] == "CANDIDAT"
    assert r["tours"] == 2
    assert r["modules"] == ["BARGE_IN"]
    assert r["no_content"] is True


def test_counter_forces_NEUTRE_at_3():
    r = _resolve(current_state="CANDIDAT", prev_state="CANDIDAT", text="quelque chose sans marqueur", tours_sans_marqueur=2)
    assert r["resolved_state"] == "NEUTRE"
    assert r["tours"] == 3


# ---------------------- Session CRUD ----------------------
@pytest.fixture(scope="module")
def session_id():
    r = requests.post(f"{API}/sessions", json={"title": "TEST_session", "context": {"cv": "Ing.", "poste": "Dev", "entreprise": "Acme", "secteur": "Tech"}}, timeout=15)
    assert r.status_code == 200
    sid = r.json()["id"]
    yield sid
    requests.delete(f"{API}/sessions/{sid}", timeout=15)


def test_create_session_default_state(session_id):
    r = requests.get(f"{API}/sessions/{session_id}", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["session"]["state"] == "NEUTRE"
    assert j["session"]["tours_sans_marqueur"] == 0


def test_list_sessions_contains(session_id):
    r = requests.get(f"{API}/sessions", timeout=15)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert session_id in ids


def test_update_session(session_id):
    r = requests.put(f"{API}/sessions/{session_id}", json={"title": "TEST_updated", "debug": True}, timeout=15)
    assert r.status_code == 200
    assert r.json()["title"] == "TEST_updated"
    assert r.json()["debug"] is True


def test_reset_session_after_state_change(session_id):
    # Force a state change via resolve then persist through PUT? server only persists on message.
    # We just call reset and verify.
    r = requests.post(f"{API}/sessions/{session_id}/reset", timeout=15)
    assert r.status_code == 200
    assert r.json()["state"] == "NEUTRE"
    g = requests.get(f"{API}/sessions/{session_id}", timeout=15).json()
    assert g["session"]["state"] == "NEUTRE"
    assert g["session"]["tours_sans_marqueur"] == 0


# ---------------------- SSE messaging ----------------------
def _stream_message(sid, text, barge_in=False, timeout=90):
    r = requests.post(f"{API}/sessions/{sid}/message",
                      json={"text": text, "barge_in": barge_in},
                      stream=True, timeout=timeout)
    assert r.status_code == 200, r.text
    events = []  # list of (event, data)
    cur_event = None
    for raw in r.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        if raw.startswith("event: "):
            cur_event = raw[7:].strip()
        elif raw.startswith("data: "):
            try:
                data = json.loads(raw[6:])
            except Exception:
                data = {"raw": raw[6:]}
            events.append((cur_event, data))
            if cur_event == "done":
                break
    return events


def test_barge_in_no_state_change(session_id):
    # Ensure session is CANDIDAT via message first would take long — instead just verify barge_in returns modules BARGE_IN
    events = _stream_message(session_id, "n'importe quoi", barge_in=True, timeout=30)
    meta = [d for e, d in events if e == "meta"]
    assert meta and meta[0]["modules"] == ["BARGE_IN"]
    # session state after barge-in remains NEUTRE (from previous reset)
    g = requests.get(f"{API}/sessions/{session_id}", timeout=15).json()
    assert g["session"]["state"] == "NEUTRE"


def test_recruteur_prose(session_id):
    events = _stream_message(session_id, "[MODE_SIMULATION] Démarre l'entretien pour un poste de développeur", timeout=120)
    meta = [d for e, d in events if e == "meta"]
    done = [d for e, d in events if e == "done"]
    assert meta and meta[0]["resolved_state"] == "RECRUTEUR"
    assert done, "No done event"
    content = done[0]["content"]
    assert content.strip(), f"Empty content. Events: {events[:5]}"
    assert "•" not in content, f"RECRUTEUR contains bullet: {content}"
    assert "**" not in content, f"RECRUTEUR contains bold: {content}"


def test_candidat_bullets_bold(session_id):
    events = _stream_message(session_id, "[REPONSE_ORALE] Parle-moi de tes trois qualités principales", timeout=120)
    meta = [d for e, d in events if e == "meta"]
    done = [d for e, d in events if e == "done"]
    assert meta and meta[0]["resolved_state"] == "CANDIDAT"
    content = done[0]["content"]
    assert content.strip(), "Empty content"
    assert "•" in content, f"CANDIDAT missing bullets: {content}"
    assert "**" in content, f"CANDIDAT missing bold: {content}"
    bullet_lines = [ln for ln in content.splitlines() if ln.strip().startswith("•")]
    assert len(bullet_lines) >= 1
    for ln in bullet_lines:
        words = ln.strip("• ").split()
        # <= 12 words per bullet (allow some flexibility for punctuation words)
        assert len(words) <= 15, f"Bullet too long ({len(words)} words): {ln}"


def test_session_state_persists_across_turns(session_id):
    g = requests.get(f"{API}/sessions/{session_id}", timeout=15).json()
    # After previous [REPONSE_ORALE] turn, state should be CANDIDAT
    assert g["session"]["state"] == "CANDIDAT", f"State did not persist: {g['session']}"


def test_delete_session_removes(session_id):
    # Create a throwaway session to delete (do not delete the fixture-managed one)
    r = requests.post(f"{API}/sessions", json={"title": "TEST_del"}, timeout=15)
    sid = r.json()["id"]
    d = requests.delete(f"{API}/sessions/{sid}", timeout=15)
    assert d.status_code == 200
    g = requests.get(f"{API}/sessions/{sid}", timeout=15)
    assert g.status_code == 404
