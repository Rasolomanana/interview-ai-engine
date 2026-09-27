import { useRef, useState, useCallback, useEffect } from "react";
import { transcribeBlob } from "./api";

// Auto-listen: capture the recruiter audio and transcribe it automatically.
// Two sources:
//   - "mic": your microphone (place a phone nearby) via the browser's Web Speech API (live, free).
//   - "tab": a Teams/Zoom browser tab audio via getDisplayMedia, transcribed in ~7s windows with Whisper.
export function useAutoListen({ onQuestion }) {
  const [active, setActive] = useState(false);
  const [source, setSource] = useState("mic");
  const [transcript, setTranscript] = useState("");
  const [busy, setBusy] = useState(false);
  const [auto, setAuto] = useState(true);

  const activeRef = useRef(false);
  const autoRef = useRef(true);
  const streamRef = useRef(null);
  const recRef = useRef(null);
  const speechRef = useRef(null);
  const bufRef = useRef("");

  useEffect(() => { autoRef.current = auto; }, [auto]);

  // Reset the captured question (buffer + field). Used after each generation.
  const clearTranscript = useCallback(() => {
    bufRef.current = "";
    setTranscript("");
  }, []);

  // Manual edits from the UI must stay in sync with the internal buffer,
  // otherwise the next recognition result would overwrite the user's change.
  const editTranscript = useCallback((value) => {
    bufRef.current = value;
    setTranscript(value);
  }, []);

  const emit = useCallback((text) => {
    const t = (text || "").trim();
    if (t && t.split(/\s+/).length >= 2) onQuestion?.(t);
  }, [onQuestion]);

  const stop = useCallback(() => {
    activeRef.current = false;
    setActive(false);
    try { speechRef.current && speechRef.current.stop(); } catch (e) {}
    speechRef.current = null;
    try { recRef.current && recRef.current.state !== "inactive" && recRef.current.stop(); } catch (e) {}
    recRef.current = null;
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch (e) {}
    streamRef.current = null;
  }, []);

  const startMic = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) throw new Error("Reconnaissance vocale non supportée par ce navigateur.");
    const rec = new SR();
    rec.lang = "fr-FR"; rec.continuous = true; rec.interimResults = true;
    bufRef.current = "";
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) {
          const seg = r[0].transcript.trim();
          bufRef.current = (bufRef.current ? bufRef.current + " " : "") + seg;
          setTranscript(bufRef.current + " ");
          if (autoRef.current && /[?.!]$/.test(seg)) emit(seg);
        } else interim += r[0].transcript;
      }
      setTranscript((bufRef.current ? bufRef.current + " " : "") + interim);
    };
    rec.onend = () => { if (activeRef.current) { try { rec.start(); } catch (e) {} } };
    speechRef.current = rec;
    try { rec.start(); } catch (e) {}
  }, [emit]);

  const recordWindow = useCallback(() => {
    if (!activeRef.current || !streamRef.current) return;
    const audio = new MediaStream(streamRef.current.getAudioTracks());
    let mr;
    try { mr = new MediaRecorder(audio, { mimeType: "audio/webm" }); } catch (e) { mr = new MediaRecorder(audio); }
    recRef.current = mr;
    const chunks = [];
    mr.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    mr.onstop = async () => {
      const blob = new Blob(chunks, { type: "audio/webm" });
      if (blob.size > 3000) {
        setBusy(true);
        try {
          const text = (await transcribeBlob(blob)).trim();
          if (text) {
            bufRef.current = (bufRef.current ? bufRef.current + " " : "") + text;
            setTranscript(bufRef.current);
            if (autoRef.current && text.includes("?")) emit(text);
          }
        } catch (e) {} finally { setBusy(false); }
      }
      if (activeRef.current) recordWindow();
    };
    mr.start();
    setTimeout(() => { try { mr.state === "recording" && mr.stop(); } catch (e) {} }, 7000);
  }, [emit]);

  const start = useCallback(async (src) => {
    bufRef.current = ""; setTranscript(""); setSource(src); activeRef.current = true; setActive(true);
    try {
      if (src === "tab") {
        const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
        if (!stream.getAudioTracks().length) {
          stream.getTracks().forEach((t) => t.stop());
          activeRef.current = false; setActive(false);
          throw new Error("Aucun audio partagé. Choisissez un onglet et cochez « Partager l'audio de l'onglet ».");
        }
        streamRef.current = stream;
        const v = stream.getVideoTracks()[0];
        if (v) v.addEventListener("ended", () => stop());
        recordWindow();
      } else {
        try { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); streamRef.current = s; } catch (e) {}
        startMic();
      }
    } catch (e) {
      activeRef.current = false; setActive(false);
      throw e;
    }
  }, [recordWindow, startMic, stop]);

  useEffect(() => () => stop(), [stop]);
  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices;
  return { active, source, transcript, busy, auto, setAuto, start, stop, supported, setTranscript: editTranscript, clearTranscript };
}
