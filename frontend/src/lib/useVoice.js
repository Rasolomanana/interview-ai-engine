import { useRef, useState, useCallback, useEffect } from "react";

// Web Speech API live transcription + lightweight client-side prosodic analysis.
// Produces [STATE_CANDIDAT] and [VOICE_CONFIDENCE] required by BLOC 2.1.
export function useVoice() {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [metrics, setMetrics] = useState({
    stateCandidat: "NORMAL",
    voiceConfidence: 0.0,
    stress: 0,
    monotone: 0,
    rate: 0, // words per minute
    volume: 0,
  });

  const recRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);
  const streamRef = useRef(null);
  const startTimeRef = useRef(0);
  const wordCountRef = useRef(0);
  const energyHistRef = useRef([]);
  const confRef = useRef(0);

  const stop = useCallback(() => {
    setListening(false);
    try { recRef.current?.stop(); } catch (e) {}
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch (e) {}
    try { audioCtxRef.current?.close(); } catch (e) {}
    audioCtxRef.current = null;
  }, []);

  const analyseLoop = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const buf = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buf.length);
      const hist = energyHistRef.current;
      hist.push(rms);
      if (hist.length > 90) hist.shift();

      const mean = hist.reduce((a, b) => a + b, 0) / hist.length;
      const variance = hist.reduce((a, b) => a + (b - mean) ** 2, 0) / hist.length;
      const std = Math.sqrt(variance);

      // Heuristics: high sustained energy + jitter => stress; low variance => monotone.
      const stress = Math.min(1, (rms * 3 + std * 6));
      const monotone = Math.max(0, 1 - std * 25);
      const elapsedMin = Math.max(0.05, (Date.now() - startTimeRef.current) / 60000);
      const rate = Math.round(wordCountRef.current / elapsedMin);

      let stateCandidat = "NORMAL";
      if (stress > 0.72) stateCandidat = "STRESS_HIGH";
      else if (monotone > 0.7) stateCandidat = "MONOTONE";
      else if (rate > 170) stateCandidat = "DEBIT_RAPIDE";
      else if (rate > 0 && rate < 90) stateCandidat = "DEBIT_LENT";

      setMetrics({
        stateCandidat,
        voiceConfidence: Number(confRef.current.toFixed(2)),
        stress: Number(stress.toFixed(2)),
        monotone: Number(monotone.toFixed(2)),
        rate,
        volume: Number(rms.toFixed(3)),
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
  }, []);

  const start = useCallback(async () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    setTranscript("");
    wordCountRef.current = 0;
    energyHistRef.current = [];
    confRef.current = 0;
    startTimeRef.current = Date.now();

    // Audio graph for prosody.
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      src.connect(analyser);
      analyserRef.current = analyser;
      analyseLoop();
    } catch (e) {
      // mic denied — analysis stays neutral
    }

    if (SR) {
      const rec = new SR();
      rec.lang = "fr-FR";
      rec.continuous = true;
      rec.interimResults = true;
      rec.onresult = (e) => {
        let finalText = "";
        let interim = "";
        let conf = 0;
        let n = 0;
        for (let i = 0; i < e.results.length; i++) {
          const res = e.results[i];
          if (res.isFinal) {
            finalText += res[0].transcript + " ";
            conf += res[0].confidence || 0.85;
            n++;
          } else {
            interim += res[0].transcript;
          }
        }
        const full = (finalText + interim).trim();
        setTranscript(full);
        wordCountRef.current = full.split(/\s+/).filter(Boolean).length;
        if (n > 0) confRef.current = conf / n;
        else if (full) confRef.current = Math.max(confRef.current, 0.75);
      };
      rec.onerror = () => {};
      rec.onend = () => { if (recRef.current === rec && listening) { try { rec.start(); } catch (e) {} } };
      recRef.current = rec;
      try { rec.start(); } catch (e) {}
    }
    setListening(true);
  }, [analyseLoop, listening]);

  useEffect(() => () => stop(), [stop]);

  const supported = typeof window !== "undefined" && !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  return { listening, transcript, metrics, start, stop, setTranscript, supported };
}
