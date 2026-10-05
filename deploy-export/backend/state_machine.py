"""Deterministic state machine for the interview AI engine.

The application (NOT the LLM) owns state routing, the turn counter, barge-in
and signal injection, per BLOC 2.3 / 2.4 of the specification. This module is
pure (no I/O) so it is fully unit-testable and drives the 12 non-regression
tests deterministically.
"""
from __future__ import annotations
import re
from typing import Optional

NEUTRE = "NEUTRE"
CANDIDAT = "CANDIDAT"
RECRUTEUR = "RECRUTEUR"

RESET_MARKERS = ["[reset]"]
RECRUTEUR_MARKERS = [
    "[mode_simulation]",
    "[recruteur]",
    "simule un entretien",
    "joue le recruteur",
    "pose-moi une question",
    "pose moi une question",
    "question suivante",
]
CANDIDAT_MARKERS = [
    "[reponse_orale]",
    "[réponse_orale]",
    "réponse à prononcer",
    "reponse a prononcer",
    "réponse à dire",
    "reponse a dire",
    "réponse orale",
    "reponse orale",
]

SHORT_ACKS = {"ok", "oui", "d'accord", "d accord", "je vois", "hmm", "mmh", "non"}
FIRST_PERSON = re.compile(r"\b(je|j'|mon|ma|mes|moi|nous|notre)\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def detect_markers(text: str):
    t = _norm(text)
    reset = any(m in t for m in RESET_MARKERS)
    recruteur = any(m in t for m in RECRUTEUR_MARKERS)
    candidat = any(m in t for m in CANDIDAT_MARKERS)
    return reset, recruteur, candidat


def is_first_person(text: str) -> bool:
    return bool(FIRST_PERSON.search(text or ""))


def word_count(text: str) -> int:
    return len((text or "").split())


def is_short_ack(text: str) -> bool:
    t = _norm(text).rstrip(".!?")
    return word_count(t) < 3 and t in SHORT_ACKS


def is_candidate_tone(text: str) -> bool:
    """Candidate tone / question inside RECRUTEUR mode (TM5 trigger)."""
    return ("?" in (text or "")) or is_first_person(text) or is_short_ack(text)


def voice_module(state: str, voice_confidence: Optional[float], state_candidat: Optional[str]):
    """TM6 — only active in CANDIDAT with VOICE_CONFIDENCE >= 0.7.
    Priority: STRESS_HIGH > LECTURE_ROBOTIQUE > MONOTONE > DEBIT_*.
    """
    if state != CANDIDAT:
        return None
    if voice_confidence is None or voice_confidence < 0.7:
        return None
    sc = (state_candidat or "NORMAL").upper()
    if sc == "STRESS_HIGH":
        return "V9"
    if sc == "LECTURE_ROBOTIQUE":
        return "V8"
    if sc == "MONOTONE":
        return "V7_MONOTONE"
    if sc in ("DEBIT_RAPIDE", "DEBIT_LENT"):
        return "V7_DEBIT"
    return None


def resolve(
    current_state: str,
    prev_state: str,
    text: str,
    tours_in: int,
    voice_confidence: Optional[float] = None,
    state_candidat: Optional[str] = None,
    barge_in: bool = False,
    has_image: bool = False,
    incomprehension_in: int = 0,
) -> dict:
    """Resolve the authoritative next ÉTAT following the strict order of §4/§5.

    Returns a dict with the resolved state, updated turn counter, active
    modules and a human-readable trace for the DEBUG overlay.
    """
    text = text or ""
    current_state = current_state or NEUTRE
    prev_state = prev_state or NEUTRE
    trace = []
    modules = []

    # §10 BARGE-IN — never change state, do not touch the counter.
    if barge_in:
        return {
            "resolved_state": current_state,
            "prev_state": prev_state,
            "tours": tours_in,
            "reset": False,
            "no_content": True,
            "incomprehension": incomprehension_in,
            "voice_module": None,
            "modules": ["BARGE_IN"],
            "trace": ["§10 BARGE-IN : état inchangé, génération annulée"],
        }

    reset, has_recr, has_cand = detect_markers(text)
    has_explicit = reset or has_recr or has_cand

    # BLOC 2.3 — turn counter: reset to 0 on any explicit marker, else +1.
    tours = 0 if has_explicit else tours_in + 1

    # §5.1 Explicit markers first — [RESET]
    if reset:
        trace.append("§2 [RESET] → NEUTRE, aucun contenu")
        return {
            "resolved_state": NEUTRE,
            "prev_state": prev_state,
            "tours": 0,
            "reset": True,
            "no_content": True,
            "incomprehension": 0,
            "voice_module": None,
            "modules": ["RESET"],
            "trace": trace,
        }

    fp = is_first_person(text)

    # §4 PRIORITÉ STRICTE de détection
    if has_recr:
        state = RECRUTEUR
        trace.append("§4.1 marqueur RECRUTEUR explicite → RECRUTEUR")
    elif has_cand or (prev_state == RECRUTEUR and (fp or is_short_ack(text))):
        state = CANDIDAT
        trace.append("§4.2 marqueur/ réponse candidat → CANDIDAT")
    else:
        state = current_state
        trace.append(f"§4.3 conservation de l'état persistant ({state})")

    # §4.4 reset NEUTRE si compteur >= 3 (impossible si marqueur car remis à 0)
    if tours >= 3 and not has_explicit:
        state = NEUTRE
        trace.append("§4.4 [TOURS_SANS_MARQUEUR] >= 3 → NEUTRE")

    # §5.2 TM7 — normalisation réponse candidat (UNIQUEMENT si état entrant CANDIDAT)
    if current_state == CANDIDAT and state != RECRUTEUR and not reset:
        if is_short_ack(text) or (word_count(text) > 25 and not has_recr) or ("?" in text and fp):
            if state != NEUTRE:  # counter override wins
                state = CANDIDAT
            modules.append("TM7")
            trace.append("§6 TM7 : maintien CANDIDAT")

    # §5.3 TM3 — retour auto CANDIDAT après simulation (>= 2 signaux)
    if prev_state == RECRUTEUR and not has_recr:
        signals = sum([fp, (not has_recr), has_cand])
        if signals >= 2 and state != NEUTRE:
            state = CANDIDAT
            modules.append("TM3")
            trace.append(f"§7 TM3 : {signals} signaux → retour CANDIDAT")

    # §5.4 TM5 — correction de confusion (UNIQUEMENT si état entrant RECRUTEUR)
    if current_state == RECRUTEUR and not has_recr and not reset:
        if is_candidate_tone(text) and state != NEUTRE:
            state = CANDIDAT
            modules.append("TM5")
            trace.append("§8 TM5 : ton candidat en RECRUTEUR → CANDIDAT")

    # §5.5 TM6 — auto-check voix
    vmod = voice_module(state, voice_confidence, state_candidat)
    if vmod:
        modules.append(vmod)
        trace.append(f"§9 TM6 : module voix {vmod} actif (conf>=0.7)")

    if has_image and state == CANDIDAT:
        modules.append("V1_VISION")
        trace.append("§ V1 : image détectée → format vision")

    return {
        "resolved_state": state,
        "prev_state": prev_state,
        "tours": tours,
        "reset": False,
        "no_content": False,
        "incomprehension": incomprehension_in,
        "voice_module": vmod,
        "modules": modules or ["—"],
        "trace": trace,
    }
