// Deterministic interview state machine — JS port of backend/state_machine.py.
export const NEUTRE = "NEUTRE";
export const CANDIDAT = "CANDIDAT";
export const RECRUTEUR = "RECRUTEUR";

const RESET_MARKERS = ["[reset]"];
const RECRUTEUR_MARKERS = [
  "[mode_simulation]", "[recruteur]", "simule un entretien", "joue le recruteur",
  "pose-moi une question", "pose moi une question", "question suivante",
];
const CANDIDAT_MARKERS = [
  "[reponse_orale]", "[réponse_orale]", "réponse à prononcer", "reponse a prononcer",
  "réponse à dire", "reponse a dire", "réponse orale", "reponse orale",
];
const SHORT_ACKS = new Set(["ok", "oui", "d'accord", "d accord", "je vois", "hmm", "mmh", "non"]);

const norm = (t) => (t || "").trim().toLowerCase();
const wordCount = (t) => (t || "").split(/\s+/).filter(Boolean).length;

function detectMarkers(text) {
  const t = norm(text);
  return {
    reset: RESET_MARKERS.some((m) => t.includes(m)),
    recruteur: RECRUTEUR_MARKERS.some((m) => t.includes(m)),
    candidat: CANDIDAT_MARKERS.some((m) => t.includes(m)),
  };
}
function isFirstPerson(text) {
  const t = text || "";
  return /\b(je|mon|ma|mes|moi|nous|notre)\b/i.test(t) || /j['’]/i.test(t);
}
function isShortAck(text) {
  const t = norm(text).replace(/[.!?]+$/, "");
  return wordCount(t) < 3 && SHORT_ACKS.has(t);
}
function isCandidateTone(text) {
  return (text || "").includes("?") || isFirstPerson(text) || isShortAck(text);
}
function voiceModule(state, conf, sc) {
  if (state !== CANDIDAT) return null;
  if (conf == null || conf < 0.7) return null;
  const s = (sc || "NORMAL").toUpperCase();
  if (s === "STRESS_HIGH") return "V9";
  if (s === "LECTURE_ROBOTIQUE") return "V8";
  if (s === "MONOTONE") return "V7_MONOTONE";
  if (s === "DEBIT_RAPIDE" || s === "DEBIT_LENT") return "V7_DEBIT";
  return null;
}

export function resolve({
  current_state = NEUTRE, prev_state = NEUTRE, text = "", tours_in = 0,
  voice_confidence = null, state_candidat = null, barge_in = false,
  has_image = false, incomprehension_in = 0,
}) {
  text = text || "";
  const trace = [];
  const modules = [];

  if (barge_in) {
    return {
      resolved_state: current_state, prev_state, tours: tours_in, reset: false,
      no_content: true, incomprehension: incomprehension_in, voice_module: null,
      modules: ["BARGE_IN"], trace: ["§10 BARGE-IN : état inchangé, génération annulée"],
    };
  }

  const { reset, recruteur: hasRecr, candidat: hasCand } = detectMarkers(text);
  const hasExplicit = reset || hasRecr || hasCand;
  let tours = hasExplicit ? 0 : tours_in + 1;

  if (reset) {
    return {
      resolved_state: NEUTRE, prev_state, tours: 0, reset: true, no_content: true,
      incomprehension: 0, voice_module: null, modules: ["RESET"],
      trace: ["§2 [RESET] → NEUTRE, aucun contenu"],
    };
  }

  const fp = isFirstPerson(text);
  let state;
  if (hasRecr) { state = RECRUTEUR; trace.push("§4.1 marqueur RECRUTEUR explicite → RECRUTEUR"); }
  else if (hasCand || (prev_state === RECRUTEUR && (fp || isShortAck(text)))) { state = CANDIDAT; trace.push("§4.2 marqueur/ réponse candidat → CANDIDAT"); }
  else { state = current_state; trace.push(`§4.3 conservation de l'état persistant (${state})`); }

  if (tours >= 3 && !hasExplicit) { state = NEUTRE; trace.push("§4.4 [TOURS_SANS_MARQUEUR] >= 3 → NEUTRE"); }

  // TM7 — only if entering state = CANDIDAT
  if (current_state === CANDIDAT && state !== RECRUTEUR && !reset) {
    if (isShortAck(text) || (wordCount(text) > 25 && !hasRecr) || (text.includes("?") && fp)) {
      if (state !== NEUTRE) state = CANDIDAT;
      modules.push("TM7"); trace.push("§6 TM7 : maintien CANDIDAT");
    }
  }
  // TM3 — auto return CANDIDAT after simulation
  if (prev_state === RECRUTEUR && !hasRecr) {
    const signals = [fp, !hasRecr, hasCand].filter(Boolean).length;
    if (signals >= 2 && state !== NEUTRE) { state = CANDIDAT; modules.push("TM3"); trace.push(`§7 TM3 : ${signals} signaux → retour CANDIDAT`); }
  }
  // TM5 — only if entering state = RECRUTEUR
  if (current_state === RECRUTEUR && !hasRecr && !reset) {
    if (isCandidateTone(text) && state !== NEUTRE) { state = CANDIDAT; modules.push("TM5"); trace.push("§8 TM5 : ton candidat en RECRUTEUR → CANDIDAT"); }
  }
  // COPILOTE PAR DÉFAUT — ne JAMAIS retomber sur la question méta "simuler ou aider ?".
  // Toute entrée substantielle (une vraie question/phrase) en NEUTRE signifie que
  // l'utilisateur veut de l'aide pour répondre → on force CANDIDAT. La simulation
  // reste opt-in via les marqueurs explicites ([MODE_SIMULATION], "simule un entretien"…).
  if (state === NEUTRE && !reset && !isShortAck(text) && wordCount(text) >= 4) {
    state = CANDIDAT;
    trace.push("§4.5 NEUTRE + contenu substantiel → CANDIDAT (copilote par défaut)");
  }
  // TM6 — voice
  const vmod = voiceModule(state, voice_confidence, state_candidat);
  if (vmod) { modules.push(vmod); trace.push(`§9 TM6 : module voix ${vmod} actif (conf>=0.7)`); }
  if (has_image && state === CANDIDAT) { modules.push("V1_VISION"); trace.push("§ V1 : image détectée → format vision"); }

  return {
    resolved_state: state, prev_state, tours, reset: false, no_content: false,
    incomprehension: incomprehension_in, voice_module: vmod,
    modules: modules.length ? modules : ["—"], trace,
  };
}
