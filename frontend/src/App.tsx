import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Cpu,
  Database,
  FileSpreadsheet,
  GitBranch,
  History,
  Layers,
  Mic,
  MicOff,
  PlusCircle,
  RefreshCw,
  Route,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  Volume2,
  VolumeX,
} from "lucide-react";
import type {
  DemoPreset,
  MemoryItem,
  TurnPayload,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  meta?: Partial<TurnPayload>;
  voiceHotword?: string | null;
}

function renderInlineMarkdown(text: string, keyPrefix: string): React.ReactNode[] {
  const tokenRegex =
    /(\[([^\]]+)\]\((https?:\/\/[^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*)/g;
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let idx = 0;

  while ((match = tokenRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const key = `${keyPrefix}-inl-${idx++}`;
    if (match[2] && match[3]) {
      nodes.push(
        <a
          key={key}
          href={match[3]}
          target="_blank"
          rel="noreferrer"
          className="text-[#0066B3] underline hover:text-[#003B71] font-medium break-all"
        >
          {match[2]}
        </a>
      );
    } else if (match[4]) {
      nodes.push(
        <strong key={key} className="font-bold text-slate-900">
          {renderInlineMarkdown(match[4], key)}
        </strong>
      );
    } else if (match[5]) {
      nodes.push(
        <code
          key={key}
          className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[#003B71] font-mono text-[11px]"
        >
          {match[5]}
        </code>
      );
    } else if (match[6]) {
      nodes.push(
        <em key={key} className="italic text-slate-600">
          {match[6]}
        </em>
      );
    }
    lastIndex = tokenRegex.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function renderMarkdownContent(content: string): React.ReactNode {
  if (!content) return null;
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let bulletBuffer: string[] = [];

  const flushBullets = (keyBase: number) => {
    if (bulletBuffer.length === 0) return;
    const items = [...bulletBuffer];
    bulletBuffer = [];
    blocks.push(
      <ul key={`ul-${keyBase}`} className="list-disc pl-4 space-y-1.5 my-1.5">
        {items.map((item, j) => (
          <li key={`li-${keyBase}-${j}`} className="text-slate-700 leading-relaxed">
            {renderInlineMarkdown(item, `li-${keyBase}-${j}`)}
          </li>
        ))}
      </ul>
    );
  };

  lines.forEach((rawLine, i) => {
    const trimmed = rawLine.trim();
    if (!trimmed) {
      flushBullets(i);
      return;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushBullets(i);
      const level = headingMatch[1].length;
      const cleanHeading = headingMatch[2].trim();
      const headingClass =
        level <= 2
          ? "text-sm font-bold text-[#003B71] mt-2 mb-1"
          : level === 3
          ? "text-xs sm:text-sm font-bold text-[#00875A] mt-2.5 mb-1 border-b border-slate-200 pb-1"
          : "text-xs font-bold text-[#0066B3] mt-2 mb-0.5";
      blocks.push(
        <div key={`h-${i}`} className={headingClass}>
          {renderInlineMarkdown(cleanHeading, `h-${i}`)}
        </div>
      );
      return;
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      bulletBuffer.push(trimmed.slice(2).trim());
      return;
    }

    flushBullets(i);
    blocks.push(
      <p key={`p-${i}`} className="text-slate-800 leading-relaxed my-1">
        {renderInlineMarkdown(trimmed, `p-${i}`)}
      </p>
    );
  });

  flushBullets(lines.length);
  return <div className="space-y-1">{blocks}</div>;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<"chat" | "xray" | "eval" | "arch">("chat");
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [presets, setPresets] = useState<DemoPreset[]>([]);
  const [threadId, setThreadId] = useState<string>("hilo-sustentacion-01");
  const [userId, setUserId] = useState<string>("ana-carvajal");
  const [sectionFilter, setSectionFilter] = useState<string>("");
  const [searchMode, setSearchMode] = useState<"hybrid" | "dense" | "lexical">("hybrid");
  const [useLlm, setUseLlm] = useState<boolean>(true);

  const [question, setQuestion] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [lastTurn, setLastTurn] = useState<Partial<TurnPayload> | null>(null);
  const [storeMemories, setStoreMemories] = useState<MemoryItem[]>([]);
  const [threadCheckpoints, setThreadCheckpoints] = useState<Array<Record<string, any>>>([]);

  // Voz, Hotword ("Eder" / "Oye Eder" / "Hola Eder") y Modo Continuo "Eder Live" (Gemini Live style)
  const [isListeningMic, setIsListeningMic] = useState<boolean>(false);
  const [hotwordStandby, setHotwordStandby] = useState<boolean>(false);
  const [liveSessionActive, setLiveSessionActive] = useState<boolean>(false);
  const [liveActivity, setLiveActivity] = useState<
    "idle" | "standby" | "listening" | "thinking" | "speaking"
  >("idle");
  const [interimTranscript, setInterimTranscript] = useState<string>("");
  const [ttsEnabled, setTtsEnabled] = useState<boolean>(true);
  const [voiceBanner, setVoiceBanner] = useState<string>("");
  const [simulatedVoiceText, setSimulatedVoiceText] = useState<string>(
    "Oye Eder, ¿cuántas PQR se atendieron en el tercer trimestre?"
  );
  const recognitionRef = useRef<any>(null);
  const liveSessionRef = useRef<boolean>(false);
  const shouldKeepMicAliveRef = useRef<boolean>(false);
  const isTtsSpeakingRef = useRef<boolean>(false);
  const isProcessingVoiceRef = useRef<boolean>(false);
  const micMuteUntilRef = useRef<number>(0);
  const lastSpokenTtsRef = useRef<string>("");
  const lastSubmittedVoiceRef = useRef<{ text: string; ts: number }>({ text: "", ts: 0 });
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToChatBottom = () => {
    window.requestAnimationFrame(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
    });
  };

  useEffect(() => {
    if (activeTab === "chat" && messages.length > 0) {
      scrollToChatBottom();
    }
  }, [messages, isStreaming, activeTab]);

  // Evaluación Retrieval y Tablas
  const [evalData, setEvalData] = useState<Record<string, any> | null>(null);
  const [evalLoading, setEvalLoading] = useState<boolean>(false);
  const [tarifasPreview, setTarifasPreview] = useState<Array<Record<string, any>>>([]);

  const fetchBackendStatus = async () => {
    try {
      const [hRes, pRes] = await Promise.all([
        fetch(`${API_BASE}/api/health`),
        fetch(`${API_BASE}/api/presets`),
      ]);
      if (hRes.ok) {
        setHealth(await hRes.json());
      }
      if (pRes.ok) {
        const pData = await pRes.json();
        setPresets(pData.cases || []);
      }
      setErrorBanner(null);
    } catch (err: any) {
      setErrorBanner(
        `No se pudo conectar al backend FastAPI en :8000 (${err?.message || "red"}). Verifica que 'uv run fastapi dev api/main.py' esté activo.`
      );
    }
  };

  const fetchThreadAndStore = async (tid: string, uid: string) => {
    try {
      const [tRes, mRes] = await Promise.all([
        fetch(`${API_BASE}/api/threads/${encodeURIComponent(tid)}`),
        fetch(`${API_BASE}/api/memories/${encodeURIComponent(uid)}`),
      ]);
      if (tRes.ok) {
        const tData = await tRes.json();
        if (Array.isArray(tData.messages) && tData.messages.length > 0) {
          setMessages(
            tData.messages
              .filter((m: any) => m.role === "user" || m.role === "assistant")
              .map((m: any) => ({ role: m.role, content: m.content }))
          );
        } else {
          setMessages([]);
        }
        setThreadCheckpoints(tData.checkpoints_history || []);
      }
      if (mRes.ok) {
        const mData = await mRes.json();
        setStoreMemories(mData.memories || []);
      }
    } catch {
      // Silencioso en carga inicial
    }
  };

  useEffect(() => {
    fetchBackendStatus();
    fetchThreadAndStore(threadId, userId);
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.getVoices();
    }
  }, []);

  const selectMaleSpanishVoice = (): {
    voice: SpeechSynthesisVoice | null;
    isExplicitMale: boolean;
  } => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      return { voice: null, isExplicitMale: false };
    }
    const voices = window.speechSynthesis.getVoices() || [];
    const spanishVoices = voices.filter((v) => v.lang.toLowerCase().startsWith("es"));
    if (spanishVoices.length === 0) {
      return { voice: null, isExplicitMale: false };
    }

    const maleHints = [
      "gonzalo",
      "pablo",
      "raul",
      "raúl",
      "alonso",
      "alvaro",
      "álvaro",
      "diego",
      "jorge",
      "carlos",
      "tomas",
      "tomás",
      "emilio",
      "enrique",
      "mateo",
      "andres",
      "andrés",
      "juan",
      "miguel",
      "david",
      "manuel",
      "sebastian",
      "sebastián",
      "male",
      "hombre",
      "masculin",
    ];
    const femaleHints = [
      "salome",
      "salomé",
      "paulina",
      "monica",
      "mónica",
      "helena",
      "elena",
      "laura",
      "sabina",
      "dalia",
      "paloma",
      "lucia",
      "lucía",
      "camila",
      "sofia",
      "sofía",
      "valeria",
      "ximena",
      "female",
      "mujer",
    ];

    const scoreVoice = (v: SpeechSynthesisVoice) => {
      const name = v.name.toLowerCase();
      const lang = v.lang.toLowerCase();
      let score = 0;
      if (maleHints.some((h) => name.includes(h))) score += 100;
      if (femaleHints.some((h) => name.includes(h))) score -= 100;
      if (lang === "es-co") score += 20;
      else if (lang === "es-419" || lang === "es-mx" || lang === "es-us") score += 12;
      else if (lang === "es-es") score += 8;
      if (name.includes("natural") || name.includes("neural") || name.includes("online")) score += 5;
      return score;
    };

    const sorted = [...spanishVoices].sort((a, b) => scoreVoice(b) - scoreVoice(a));
    const best = sorted[0];
    const isExplicitMale = maleHints.some((h) => best.name.toLowerCase().includes(h));
    return { voice: best, isExplicitMale };
  };

  const pauseMicForSpeakerOutput = () => {
    isTtsSpeakingRef.current = true;
    try {
      recognitionRef.current?.abort();
    } catch {
      // Ignorar si ya estaba detenido
    }
  };

  const resumeMicAfterSpeakerOutput = (delayMs = 750) => {
    micMuteUntilRef.current = Date.now() + delayMs;
    window.setTimeout(() => {
      isTtsSpeakingRef.current = false;
      isProcessingVoiceRef.current = false;
      setLiveActivity(
        liveSessionRef.current
          ? "listening"
          : shouldKeepMicAliveRef.current
          ? "standby"
          : "idle"
      );
      if (shouldKeepMicAliveRef.current && recognitionRef.current) {
        try {
          recognitionRef.current.start();
        } catch {
          // Ya estaba corriendo
        }
      }
    }, delayMs);
  };

  const isEchoOfAssistantOrDuplicate = (spoken: string): boolean => {
    const clean = spoken
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!clean || clean.length < 2) return true;

    // 1. Evitar re-envío en bucle de la misma pregunta en menos de 8 segundos
    const now = Date.now();
    if (
      clean === lastSubmittedVoiceRef.current.text &&
      now - lastSubmittedVoiceRef.current.ts < 8000
    ) {
      return true;
    }

    // 2. Evitar capturar frases propias del asistente TTS por los altavoces
    const selfPhrases = [
      "soy eder",
      "te escucho en vivo",
      "datos exactos validados",
      "fuente estructurada",
      "tarifa aplicada",
      "subsidio contribucion",
      "subsidio contribución",
      "meta documento",
      "paso a modo de espera",
      "segun los registros",
      "según los registros",
      "fuentes oficiales",
    ];
    if (selfPhrases.some((p) => clean.includes(p))) {
      return true;
    }

    // 3. Superposición léxica con el último TTS pronunciado por Eder
    const lastTts = lastSpokenTtsRef.current;
    if (lastTts && clean.length > 10 && lastTts.includes(clean)) {
      return true;
    }
    return false;
  };

  const speakText = (text: string, onEndCallback?: () => void) => {
    if (!ttsEnabled || typeof window === "undefined" || !("speechSynthesis" in window)) {
      resumeMicAfterSpeakerOutput(250);
      if (onEndCallback) onEndCallback();
      return;
    }
    try {
      const spokenCleanText = text
        .replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu, " ")
        .replace(/\s+/g, " ")
        .trim();
      if (!spokenCleanText) {
        resumeMicAfterSpeakerOutput(250);
        if (onEndCallback) onEndCallback();
        return;
      }

      // Silenciar el micrófono ANTES de que hablen los altavoces para evitar bucle de eco
      pauseMicForSpeakerOutput();
      lastSpokenTtsRef.current = spokenCleanText
        .toLowerCase()
        .replace(/[^\p{L}\p{N}\s]/gu, " ")
        .replace(/\s+/g, " ")
        .trim();

      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(spokenCleanText);
      const { voice, isExplicitMale } = selectMaleSpanishVoice();
      if (voice) {
        utter.voice = voice;
        utter.lang = voice.lang;
      } else {
        utter.lang = "es-CO";
      }
      utter.rate = 1.03;
      utter.pitch = isExplicitMale ? 0.96 : 0.84;
      setLiveActivity("speaking");
      utter.onend = () => {
        resumeMicAfterSpeakerOutput(750);
        if (onEndCallback) onEndCallback();
      };
      utter.onerror = () => {
        resumeMicAfterSpeakerOutput(400);
        if (onEndCallback) onEndCallback();
      };
      window.speechSynthesis.speak(utter);
    } catch {
      resumeMicAfterSpeakerOutput(300);
      if (onEndCallback) onEndCallback();
    }
  };

  const interruptSpeechBargeIn = () => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    resumeMicAfterSpeakerOutput(200);
    setVoiceBanner("✋ Barge-In: Respuesta de voz interrumpida. Eder Live te escucha de nuevo...");
  };

  const handleSendQuestion = async (overrideQuestion?: string) => {
    const qText = (overrideQuestion ?? question).trim();
    if (!qText || isStreaming) return;

    setErrorBanner(null);
    setQuestion("");
    setIsStreaming(true);

    setMessages((prev) => [
      ...prev,
      { role: "user", content: qText },
      { role: "assistant", content: "" },
    ]);

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: qText,
          thread_id: threadId,
          user_id: userId,
          section_filter: sectionFilter || null,
          search_mode: searchMode,
          top_k: 4,
          use_llm: useLlm,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const rawEv of events) {
          const lines = rawEv.split("\n");
          let evType = "message";
          let dataStr = "";
          for (const line of lines) {
            if (line.startsWith("event:")) evType = line.slice(6).trim();
            if (line.startsWith("data:")) dataStr += line.slice(5).trim();
          }
          if (!dataStr) continue;
          const parsed = JSON.parse(dataStr);

          if (evType === "metadata") {
            setLastTurn(parsed);
          } else if (evType === "token") {
            const delta = parsed.delta || "";
            setMessages((prev) => {
              const copy = [...prev];
              const lastIdx = copy.length - 1;
              if (lastIdx >= 0 && copy[lastIdx].role === "assistant") {
                copy[lastIdx] = {
                  ...copy[lastIdx],
                  content: copy[lastIdx].content + delta,
                };
              }
              return copy;
            });
          } else if (evType === "done") {
            setLastTurn(parsed);
            setMessages((prev) => {
              const copy = [...prev];
              const lastIdx = copy.length - 1;
              if (lastIdx >= 0 && copy[lastIdx].role === "assistant") {
                copy[lastIdx] = {
                  role: "assistant",
                  content: parsed.answer || copy[lastIdx].content,
                  meta: parsed,
                };
              }
              return copy;
            });
            if (parsed.tts_speech_text) {
              speakText(parsed.tts_speech_text);
            }
          }
        }
      }

      await fetchBackendStatus();
      await fetchThreadAndStore(threadId, userId);
    } catch (err: any) {
      setErrorBanner(`Error al consultar el agente: ${err?.message || "Fallo de red"}`);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleVoiceCommandSubmit = async (
    spokenTranscript: string,
    requireHw: boolean,
    fromManualInput = false
  ) => {
    if (!fromManualInput && isEchoOfAssistantOrDuplicate(spokenTranscript)) {
      return;
    }

    const normalizedKey = spokenTranscript
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
    lastSubmittedVoiceRef.current = { text: normalizedKey, ts: Date.now() };

    // Pausar micrófono mientras se procesa el turno y habla el TTS (evita eco en bucle)
    isProcessingVoiceRef.current = true;
    pauseMicForSpeakerOutput();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setInterimTranscript("");
    setLiveActivity("thinking");
    setVoiceBanner(`🎙️ Procesando voz: "${spokenTranscript}"...`);
    try {
      const res = await fetch(`${API_BASE}/api/voice/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: spokenTranscript,
          require_hotword: requireHw,
          live_session_active: liveSessionRef.current,
          thread_id: threadId,
          user_id: userId,
          use_llm: useLlm,
        }),
      });
      const data = await res.json();
      if (!data.accepted) {
        resumeMicAfterSpeakerOutput(250);
        setVoiceBanner(
          `⏸️ Ignorado en espera: di "Eder", "Oye Eder" o "Hola Eder" para activar Eder Live (capturado: "${spokenTranscript}").`
        );
        return;
      }

      const analysis = data.voice_analysis;

      // Si el usuario dijo "Gracias Eder" / "Eso es todo" -> vuelve a espera
      if (analysis.sleep_requested) {
        liveSessionRef.current = false;
        setLiveSessionActive(false);
        setVoiceBanner(
          '🌙 Eder Live en espera. Cuando me necesites vuelve a decir "Oye Eder" o "Hola Eder".'
        );
        speakText(
          data.tts_speech_text ||
            "Con gusto. Paso a modo de espera; cuando me necesites solo di Oye Eder."
        );
        return;
      }

      // ¡Hotword detectado! Entramos o permanecemos en Eder Live (modo Gemini Live)
      liveSessionRef.current = true;
      setLiveSessionActive(true);

      if (analysis.wake_only) {
        setVoiceBanner(
          `🟢 Eder Live ACTIVO ("${analysis.matched_hotword}"). Habla libremente cuando Eder termine de saludarte (di "Gracias Eder" para salir).`
        );
        speakText(
          data.tts_speech_text ||
            "¡Hola! Soy Eder Live. Te escucho en vivo, dime qué necesitas de EMCALI."
        );
        return;
      }

      const turn: TurnPayload = data.turn;
      setVoiceBanner(
        `🟢 Eder Live (${analysis.matched_hotword || "Continuo"}) → "${analysis.clean_query}" · Micrófono silenciado mientras Eder habla para evitar eco`
      );
      setLastTurn(turn);
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: turn.question,
          voiceHotword: analysis.matched_hotword || "Eder Live",
        },
        {
          role: "assistant",
          content: turn.answer,
          meta: turn,
        },
      ]);
      if (data.tts_speech_text) {
        speakText(data.tts_speech_text);
      } else {
        resumeMicAfterSpeakerOutput(300);
      }
      await fetchThreadAndStore(threadId, userId);
    } catch (err: any) {
      resumeMicAfterSpeakerOutput(300);
      setVoiceBanner(`⚠️ Error procesando comando de voz: ${err?.message || "red"}`);
    }
  };

  const toggleBrowserMicrophone = (continuousHotword: boolean) => {
    const SpeechRec =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      setVoiceBanner(
        "ℹ️ Tu navegador actual no expone Web Speech API nativa; usa el simulador de Eder Live integrado aquí al lado."
      );
      return;
    }

    if (isListeningMic) {
      shouldKeepMicAliveRef.current = false;
      liveSessionRef.current = false;
      recognitionRef.current?.stop();
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      setIsListeningMic(false);
      setHotwordStandby(false);
      setLiveSessionActive(false);
      setLiveActivity("idle");
      setInterimTranscript("");
      setVoiceBanner("🛑 Micrófono y sesión Eder Live detenidos.");
      return;
    }

    shouldKeepMicAliveRef.current = true;
    const rec = new SpeechRec();
    rec.lang = "es-CO";
    rec.continuous = true;
    rec.interimResults = true;

    rec.onstart = () => {
      setIsListeningMic(true);
      setHotwordStandby(continuousHotword);
      setLiveActivity(liveSessionRef.current ? "listening" : "standby");
      setVoiceBanner(
        liveSessionRef.current
          ? '🟢 Eder Live escuchando en vivo... Habla con naturalidad (o di "Gracias Eder" para pausar)'
          : '🎧 Standby: di "Eder", "Oye Eder" o "Hola Eder" para despertar el modo Eder Live'
      );
    };

    rec.onresult = (event: any) => {
      // Bloqueo Half-Duplex: ignorar cualquier audio mientras Eder piensa, habla por TTS o está en ventana de eco
      if (
        isTtsSpeakingRef.current ||
        isProcessingVoiceRef.current ||
        Date.now() < micMuteUntilRef.current ||
        (typeof window !== "undefined" &&
          "speechSynthesis" in window &&
          window.speechSynthesis.speaking)
      ) {
        return;
      }

      let interim = "";
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) {
          finalTranscript += piece;
        } else {
          interim += piece;
        }
      }
      if (interim.trim()) {
        setInterimTranscript(interim.trim());
      }
      if (finalTranscript.trim()) {
        setInterimTranscript("");
        handleVoiceCommandSubmit(finalTranscript.trim(), continuousHotword, false);
      }
    };

    rec.onerror = () => {
      if (!shouldKeepMicAliveRef.current) {
        setIsListeningMic(false);
        setHotwordStandby(false);
        setLiveActivity("idle");
      }
    };

    rec.onend = () => {
      // No auto-reiniciar el micrófono mientras Eder está hablando por los altavoces (se reanuda en utter.onend)
      if (isTtsSpeakingRef.current || isProcessingVoiceRef.current) {
        return;
      }
      if (shouldKeepMicAliveRef.current) {
        try {
          rec.start();
          return;
        } catch {
          // Si ya está iniciando, ignorar
        }
      }
      setIsListeningMic(false);
      setHotwordStandby(false);
      setLiveActivity("idle");
    };

    recognitionRef.current = rec;
    rec.start();
  };

  const handleCreateNewThread = async () => {
    const suffix = Math.floor(100 + Math.random() * 900);
    const newTid = `hilo-nuevo-${suffix}`;
    setThreadId(newTid);
    setMessages([]);
    setLastTurn(null);
    setVoiceBanner("");
    await fetchThreadAndStore(newTid, userId);
  };

  const handleClearChat = () => {
    setMessages([]);
    setLastTurn(null);
    setVoiceBanner("");
    setInterimTranscript("");
  };

  const loadEvaluationMetrics = async () => {
    setEvalLoading(true);
    try {
      const [evRes, tarRes] = await Promise.all([
        fetch(`${API_BASE}/api/evaluation/retrieval`),
        fetch(`${API_BASE}/api/tools/tarifas?trimestre=2026-Q3`),
      ]);
      if (evRes.ok) setEvalData(await evRes.json());
      if (tarRes.ok) {
        const tJson = await tarRes.json();
        setTarifasPreview(tJson.rows || []);
      }
    } finally {
      setEvalLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "eval" || activeTab === "arch") {
      loadEvaluationMetrics();
    }
  }, [activeTab]);

  const routeBadgeColor = (choice?: string) => {
    switch (choice) {
      case "direct_reply":
        return "bg-amber-50 text-amber-800 border-amber-300";
      case "structured_tool":
        return "bg-sky-50 text-sky-800 border-sky-300";
      case "rag_search":
        return "bg-emerald-50 text-emerald-800 border-emerald-300";
      case "hybrid_multi_tool":
        return "bg-purple-50 text-purple-800 border-purple-300";
      default:
        return "bg-slate-100 text-slate-700 border-slate-300";
    }
  };

  const quickCitizenTopics = [
    {
      label: "⚡ Tarifas Energía Estrato 3",
      q: "¿Cuál es la tarifa aplicada de energía en estrato 3 para el tercer trimestre según el CSV?",
    },
    {
      label: "💧 Solicitudes PQR 2026-Q3",
      q: "¿Cuántas solicitudes PQR se atendieron en el tercer trimestre (2026-Q3)?",
    },
    {
      label: "📡 Cobertura Fibra Óptica",
      q: "¿Cuál es la cobertura actual de fibra óptica de EMCALI?",
    },
    {
      label: "🔐 Datos Personales (Ley 1581)",
      q: "¿Qué dice el corpus oficial sobre la Política de Tratamiento de Datos Personales (Ley 1581 de 2012), los plazos de respuesta y los derechos del titular?",
    },
    {
      label: "💳 Medios de Pago PSE",
      q: "¿Cuáles son los medios de pago habilitados por EMCALI?",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      {/* Header Institucional EMCALI E.I.C.E. E.S.P. */}
      <header className="bg-[#003B71] text-white shadow-md sticky top-0 z-30 border-b-4 border-[#00875A]">
        <div className="max-w-[1440px] mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-full bg-white/10 flex items-center justify-center border border-white/25 overflow-visible">
              <img
                src="/eder-avatar.jpg"
                alt="Eder caricatura"
                className={`h-10 w-10 rounded-full object-cover shadow-md border-2 border-emerald-300 transition-transform ${
                  isStreaming ? "eder-orbit" : ""
                }`}
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-base sm:text-lg tracking-tight text-white">
                  EMCALI E.I.C.E. E.S.P.
                </h1>
                <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-white/15 text-emerald-200 border border-white/20">
                  Eder · Asistente Virtual
                </span>
              </div>
              <p className="text-xs text-sky-100/90">
                Energía · Acueducto y Alcantarillado · Telecomunicaciones · Atención Ciudadana
              </p>
            </div>
          </div>

          {/* Navegación: Producto Ciudadano + Tabs Académicos */}
          <nav className="flex flex-wrap items-center gap-1 bg-[#00284D] p-1 rounded-xl border border-white/15">
            <button
              onClick={() => setActiveTab("chat")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === "chat"
                  ? "bg-[#00875A] text-white shadow"
                  : "text-sky-100 hover:bg-white/10"
              }`}
            >
              💬 Atención Ciudadana
            </button>
            <button
              onClick={() => setActiveTab("xray")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === "xray"
                  ? "bg-[#00875A] text-white shadow"
                  : "text-sky-100 hover:bg-white/10"
              }`}
            >
              🔬 Rayos-X & Validación
            </button>
            <button
              onClick={() => setActiveTab("eval")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === "eval"
                  ? "bg-[#00875A] text-white shadow"
                  : "text-sky-100 hover:bg-white/10"
              }`}
            >
              📊 Evaluación Retrieval
            </button>
            <button
              onClick={() => setActiveTab("arch")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === "arch"
                  ? "bg-[#00875A] text-white shadow"
                  : "text-sky-100 hover:bg-white/10"
              }`}
            >
              🏗️ Arquitectura & Datos
            </button>
          </nav>
        </div>
      </header>

      {errorBanner && (
        <div className="bg-rose-50 border-b border-rose-200 px-4 py-2 text-xs text-rose-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorBanner}</span>
          </div>
          <button
            onClick={fetchBackendStatus}
            className="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-700 text-white font-semibold cursor-pointer"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* VISTA 1: PRODUCTO CIUDADANO EMCALI (LIMPIO, SIN JERGAS ACADÉMICAS) */}
      {activeTab === "chat" && (
        <main className="max-w-5xl w-full mx-auto px-4 py-5 flex-1 flex flex-col gap-3.5">
          {/* Accesos rápidos de servicios EMCALI + Nueva conversación */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              {quickCitizenTopics.map((item) => (
                <button
                  key={item.label}
                  onClick={() => handleSendQuestion(item.q)}
                  disabled={isStreaming}
                  className="px-3 py-1.5 rounded-full bg-white hover:bg-emerald-50 border border-slate-200 hover:border-[#00875A]/50 text-xs font-medium text-[#003B71] shadow-xs transition cursor-pointer disabled:opacity-50"
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleClearChat}
                disabled={messages.length === 0 || isStreaming}
                className="px-3 py-1.5 rounded-full bg-white hover:bg-rose-50 border border-slate-200 hover:border-rose-300 text-slate-700 hover:text-rose-700 text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer disabled:opacity-40"
                title="Limpiar los mensajes visibles en el chat"
              >
                <Trash2 className="w-3.5 h-3.5 text-rose-500" />
                <span>Limpiar chat</span>
              </button>
              <button
                onClick={handleCreateNewThread}
                className="px-3 py-1.5 rounded-full bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer"
                title="Iniciar una nueva conversación"
              >
                <PlusCircle className="w-3.5 h-3.5 text-[#00875A]" />
                <span>Nueva conversación</span>
              </button>
            </div>
          </div>

          {/* Barra de Voz "Eder Live" estilo producto */}
          <div
            className={`p-3 rounded-2xl border transition-all flex flex-wrap items-center justify-between gap-2.5 shadow-xs ${
              liveSessionActive
                ? "bg-emerald-50/90 border-[#00875A]/50"
                : "bg-white border-slate-200"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => toggleBrowserMicrophone(true)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 border transition cursor-pointer ${
                  liveSessionActive
                    ? "bg-[#00875A] text-white border-[#006b47] shadow-sm"
                    : isListeningMic && hotwordStandby
                    ? "bg-[#003B71] text-white border-[#00284D] animate-pulse"
                    : "bg-[#003B71]/5 hover:bg-[#003B71]/10 text-[#003B71] border-[#003B71]/20"
                }`}
              >
                {isListeningMic ? (
                  <MicOff className="w-3.5 h-3.5" />
                ) : (
                  <Mic className="w-3.5 h-3.5" />
                )}
                <span>
                  {liveSessionActive
                    ? "🟢 Eder Live Activo (Pausar)"
                    : isListeningMic && hotwordStandby
                    ? 'Escuchando "Oye Eder"...'
                    : 'Hablar con Eder ("Oye Eder")'}
                </span>
              </button>

              {liveSessionActive && (
                <div className="px-2.5 py-1 rounded-full bg-white border border-emerald-300 flex items-center gap-2 text-[11px] font-semibold">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00875A] opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#00875A]"></span>
                  </span>
                  <span className="text-[#006b47]">
                    {liveActivity === "thinking"
                      ? "Eder consultando..."
                      : liveActivity === "speaking"
                      ? "🔊 Eder respondiendo"
                      : "🎙️ Te escucho en vivo"}
                  </span>
                </div>
              )}

              {liveActivity === "speaking" && (
                <button
                  onClick={interruptSpeechBargeIn}
                  className="px-2.5 py-1 rounded-xl bg-amber-50 hover:bg-amber-100 border border-amber-300 text-amber-800 text-xs font-semibold cursor-pointer"
                >
                  ✋ Interrumpir
                </button>
              )}

              <button
                onClick={() => setTtsEnabled((v) => !v)}
                className={`px-2.5 py-1.5 rounded-xl text-xs border flex items-center gap-1 cursor-pointer ${
                  ttsEnabled
                    ? "bg-emerald-50 text-[#006b47] border-emerald-200"
                    : "bg-slate-100 text-slate-500 border-slate-200"
                }`}
                title="Activar/Desactivar respuesta por voz"
              >
                {ttsEnabled ? (
                  <Volume2 className="w-3.5 h-3.5" />
                ) : (
                  <VolumeX className="w-3.5 h-3.5" />
                )}
                <span>Voz {ttsEnabled ? "ON" : "OFF"}</span>
              </button>
            </div>

            {/* Probador rápido de voz */}
            <div className="flex items-center gap-1.5 flex-1 min-w-[240px]">
              <input
                value={simulatedVoiceText}
                onChange={(e) => setSimulatedVoiceText(e.target.value)}
                placeholder={
                  liveSessionActive
                    ? 'Eder Live activo: escribe o habla tu pregunta (o "Gracias Eder")'
                    : 'Ej: "Oye Eder, ¿cuál es la tarifa en estrato 3?"'
                }
                className="flex-1 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-[#00875A]"
              />
              <button
                onClick={() => handleVoiceCommandSubmit(simulatedVoiceText, true, true)}
                className="px-3 py-1.5 rounded-xl bg-[#003B71] hover:bg-[#00284D] text-white text-xs font-semibold shrink-0 cursor-pointer"
              >
                {liveSessionActive ? "Enviar Voz" : "Probar Voz"}
              </button>
            </div>

            {interimTranscript && (
              <div className="w-full text-xs text-[#006b47] font-medium bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-200">
                🎙️ Escuchando: <em>"{interimTranscript}..."</em>
              </div>
            )}

            {voiceBanner && (
              <div className="w-full text-[11px] text-slate-600 font-medium px-1">
                {voiceBanner}
              </div>
            )}
          </div>

          {/* Ventana Principal de Conversación */}
          <div className="flex-1 min-h-[430px] max-h-[580px] overflow-y-auto p-5 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center py-14 text-slate-500">
                <div className="h-14 w-14 rounded-2xl bg-[#003B71]/10 flex items-center justify-center mb-3">
                  <Bot className="w-8 h-8 text-[#003B71]" />
                </div>
                <h2 className="text-base font-bold text-[#003B71]">
                  ¡Hola! Soy Eder, tu asistente virtual de EMCALI
                </h2>
                <p className="text-xs max-w-md mt-1.5 text-slate-600 leading-relaxed">
                  Pregúntame sobre tarifas de energía, acueducto, telecomunicaciones, medios de pago,
                  solicitudes PQR o políticas institucionales. También puedes decir{" "}
                  <strong>"Oye Eder"</strong> para conversar por voz.
                </p>
              </div>
            ) : (
              messages.map((msg, i) => {
                const isLastStreamingAssistant =
                  msg.role === "assistant" && isStreaming && i === messages.length - 1;
                return (
                  <div
                    key={i}
                    className={`flex items-start gap-2.5 ${
                      msg.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    {msg.role === "assistant" && (
                      <div className="shrink-0 w-10 h-10 flex items-center justify-center mt-1">
                        <img
                          src="/eder-avatar.jpg"
                          alt="Eder"
                          className={`w-8 h-8 rounded-full object-cover border-2 ${
                            isLastStreamingAssistant
                              ? "border-[#00875A] shadow-md eder-orbit"
                              : "border-slate-300"
                          }`}
                        />
                      </div>
                    )}
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs sm:text-[13px] leading-relaxed shadow-xs ${
                        msg.role === "user"
                          ? "bg-[#003B71] text-white whitespace-pre-wrap"
                          : "bg-slate-50 border border-slate-200 text-slate-800"
                      }`}
                    >
                      {msg.voiceHotword && (
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-sky-200 mb-1">
                          🎙️ {msg.voiceHotword}
                        </div>
                      )}
                      {isLastStreamingAssistant && !msg.content ? (
                        <span className="text-slate-500 italic">
                          Eder está generando la respuesta...
                        </span>
                      ) : msg.role === "assistant" ? (
                        renderMarkdownContent(msg.content)
                      ) : (
                        msg.content
                      )}
                    </div>
                  </div>
                );
              })
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Barra de Envío */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendQuestion();
            }}
            className="flex gap-2"
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Escribe tu consulta para Eder (ej. tarifas de energía, PQR, medios de pago, Ley 1581)..."
              className="flex-1 px-4 py-3 rounded-2xl bg-white border border-slate-300 text-xs sm:text-sm text-slate-900 shadow-xs focus:outline-none focus:border-[#00875A]"
            />
            <button
              type="submit"
              disabled={isStreaming || !question.trim()}
              className="px-5 py-3 rounded-2xl bg-[#00875A] hover:bg-[#006b47] disabled:opacity-50 text-white text-xs sm:text-sm font-bold flex items-center gap-2 shadow-sm cursor-pointer"
            >
              <Send className="w-4 h-4" />
              <span>Enviar</span>
            </button>
          </form>
        </main>
      )}

      {/* VISTA 2: TAB ACADÉMICO — RAYOS-X, CASOS DE VALIDACIÓN, PID, MEMORIA Y BLINDAJE */}
      {activeTab === "xray" && (
        <main className="max-w-[1440px] w-full mx-auto px-4 py-5 space-y-4">
          {/* Barra Técnica de Sesión, PID y Reinicio */}
          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs flex flex-wrap items-end justify-between gap-3">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 flex-1 min-w-[300px]">
              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                  Hilo Corto Plazo (SqliteSaver thread_id)
                </label>
                <div className="flex gap-1.5">
                  <input
                    value={threadId}
                    onChange={(e) => {
                      setThreadId(e.target.value);
                      fetchThreadAndStore(e.target.value, userId);
                    }}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-300 text-xs font-mono text-[#003B71]"
                  />
                  <button
                    onClick={handleCreateNewThread}
                    className="px-2.5 py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 text-[#00875A] text-xs font-semibold shrink-0 cursor-pointer"
                  >
                    + Hilo
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                  Usuario Largo Plazo (Store Namespace)
                </label>
                <div className="flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                  <input
                    value={userId}
                    onChange={(e) => {
                      setUserId(e.target.value);
                      fetchThreadAndStore(threadId, e.target.value);
                    }}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-300 text-xs font-mono text-purple-700"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                  Modo Qdrant & Filtro Payload
                </label>
                <div className="flex gap-1.5">
                  <select
                    value={searchMode}
                    onChange={(e) => setSearchMode(e.target.value as any)}
                    className="w-1/2 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-300 text-xs text-slate-800"
                  >
                    <option value="hybrid">Híbrido (RRF)</option>
                    <option value="dense">Denso (HNSW)</option>
                    <option value="lexical">Léxico (BM25)</option>
                  </select>
                  <select
                    value={sectionFilter}
                    onChange={(e) => setSectionFilter(e.target.value)}
                    className="w-1/2 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-300 text-xs text-slate-800"
                  >
                    <option value="">Todas secciones</option>
                    <option value="energia">energia</option>
                    <option value="acueducto">acueducto</option>
                    <option value="telco">telco</option>
                    <option value="proteccion-de-datos-personales">datos-personales</option>
                    <option value="about">about</option>
                    <option value="transparencia">transparencia</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer select-none bg-slate-50 px-3 py-2 rounded-lg border border-slate-300">
                  <input
                    type="checkbox"
                    checked={useLlm}
                    onChange={(e) => setUseLlm(e.target.checked)}
                    className="accent-[#00875A]"
                  />
                  <span className="font-semibold">DeepSeek API</span>
                </label>
                <button
                  onClick={() => {
                    fetchBackendStatus();
                    fetchThreadAndStore(threadId, userId);
                  }}
                  className="px-3 py-2 rounded-lg bg-[#003B71] hover:bg-[#00284D] text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                  title="Refrescar PID del Backend y recuperar el hilo desde SqliteSaver"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>PID: {health?.server_pid ?? "---"}</span>
                </button>
              </div>
            </div>
          </div>

          {/* 5 Casos Oficiales de Sustentación (1 Clic y salta al Chat o muestra traza) */}
          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-xs font-bold uppercase tracking-wider text-[#003B71] flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-[#00875A]" />
                Casos Oficiales de Validación Académica (Módulo 2)
              </span>
              <span className="text-[11px] text-slate-500">
                Ejecuta el caso en vivo y consulta la traza abajo o en Atención Ciudadana
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => {
                    handleSendQuestion(preset.question);
                    setActiveTab("chat");
                  }}
                  disabled={isStreaming}
                  title={`${preset.title}\n\n${preset.description}`}
                  className="p-2.5 rounded-xl bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-[#00875A] text-left transition flex flex-col justify-between cursor-pointer disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[11px] font-bold text-[#00875A]">{preset.number}</span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {preset.minute_block}
                    </span>
                  </div>
                  <p className="text-[11px] font-medium text-slate-700 line-clamp-2 mt-1 leading-tight">
                    {preset.title}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Grid de 4 Tarjetas de Rayos-X */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* 1. Router System One (Jev) */}
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between mb-2.5">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#003B71] flex items-center gap-1.5">
                  <Route className="w-4 h-4 text-[#00875A]" />
                  1. Router Agent & Gatekeeper System One (Jev)
                </h2>
                {lastTurn?.router_decision && (
                  <span
                    className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded border ${routeBadgeColor(
                      lastTurn.router_decision.choice
                    )}`}
                  >
                    Choice: {lastTurn.router_decision.choice}
                  </span>
                )}
              </div>

              {lastTurn?.router_decision ? (
                <div className="space-y-2 text-xs">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                      <span className="text-[10px] text-slate-500 block">Compuerta Noul</span>
                      <span
                        className={`font-mono font-bold ${
                          lastTurn.router_decision.noul_triggered
                            ? "text-amber-700"
                            : "text-slate-700"
                        }`}
                      >
                        {lastTurn.router_decision.noul_triggered
                          ? "TRUE (0 búsquedas)"
                          : "FALSE (tools)"}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                      <span className="text-[10px] text-slate-500 block">Jev Score</span>
                      <span className="font-mono font-bold text-[#00875A]">
                        {(lastTurn.router_decision.score * 100).toFixed(0)}% confianza
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                      <span className="text-[10px] text-slate-500 block">Tools invocadas</span>
                      <span className="font-mono text-[11px] text-[#003B71] font-semibold">
                        {lastTurn.router_decision.tools_to_invoke.length || "Ninguna"}
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-700 bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                    {lastTurn.router_decision.rationale}
                  </p>
                  <div className="text-[11px] font-mono text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-200 overflow-x-auto">
                    <span className="text-purple-700 font-semibold">Box: </span>
                    {JSON.stringify(lastTurn.router_decision.box)}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500">
                  Realiza una consulta en Atención Ciudadana para inspeccionar Choice, Noul, Score y
                  Box.
                </p>
              )}
            </div>

            {/* 2. Blindaje del RAG */}
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between mb-2.5">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#003B71] flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-[#00875A]" />
                  2. Blindaje del RAG (&lt;datos_pasivos_corpus&gt;)
                </h2>
                {lastTurn?.security_audit && (
                  <span
                    className={`text-[11px] font-bold px-2 py-0.5 rounded border flex items-center gap-1 ${
                      lastTurn.security_audit.any_injection_detected
                        ? "bg-rose-50 text-rose-700 border-rose-300"
                        : "bg-emerald-50 text-emerald-700 border-emerald-300"
                    }`}
                  >
                    {lastTurn.security_audit.any_injection_detected ? (
                      <>
                        <ShieldAlert className="w-3.5 h-3.5" />
                        INYECCIÓN BLOQUEADA
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        CONTEXTO PASIVO SEGURO
                      </>
                    )}
                  </span>
                )}
              </div>

              {lastTurn?.security_audit?.any_injection_detected ? (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs space-y-1">
                  <p className="font-semibold text-rose-800">
                    Reglas activadas: {lastTurn.security_audit.matched_rules.join(", ")}
                  </p>
                  {lastTurn.security_audit.events
                    .filter((ev) => ev.injection_detected)
                    .map((ev, idx) => (
                      <div key={idx} className="text-[11px] text-rose-700 font-mono">
                        Chunk `{ev.chunk_id}` neutralizado:{" "}
                        {ev.neutralized_segments.join(" | ")}
                      </div>
                    ))}
                </div>
              ) : (
                <p className="text-xs text-slate-600 leading-relaxed">
                  Todos los fragmentos recuperados de Qdrant ({health?.qdrant?.indexed_points ?? 1386}{" "}
                  chunks) se encapsulan en{" "}
                  <code className="text-[#00875A] font-mono">
                    &lt;datos_pasivos_corpus solo_lectura="true"&gt;
                  </code>{" "}
                  para impedir que instrucciones ocultas alteren al agente.
                </p>
              )}
            </div>

            {/* 3. Memoria Corto Plazo & Largo Plazo */}
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-2.5">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#003B71] flex items-center gap-1.5">
                  <History className="w-4 h-4 text-purple-600" />
                  3. Memoria Corto Plazo (SqliteSaver) & Largo Plazo (Store)
                </h2>
                <span className="text-[11px] font-mono text-slate-500">
                  Checkpoints: {threadCheckpoints.length}
                </span>
              </div>

              {lastTurn?.context_window && (
                <div className="grid grid-cols-3 gap-2 text-[11px]">
                  <div className="p-2 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-slate-500 block">Mensajes Hilo</span>
                    <span className="font-mono font-bold text-slate-800">
                      {lastTurn.context_window.kept_messages_after} /{" "}
                      {lastTurn.context_window.total_messages_before}
                    </span>
                  </div>
                  <div className="p-2 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-slate-500 block">trim_messages</span>
                    <span className="font-mono font-bold text-[#00875A]">
                      {lastTurn.context_window.tokens_after} /{" "}
                      {lastTurn.context_window.max_token_budget} tok
                    </span>
                  </div>
                  <div className="p-2 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-slate-500 block">Summarization</span>
                    <span className="font-mono font-bold text-purple-700">
                      {lastTurn.context_window.summarization_triggered ? "ACTIVO" : "En rango"}
                    </span>
                  </div>
                </div>
              )}

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <div className="text-[11px] font-semibold text-purple-700 mb-1.5">
                  Store Namespace (`users/{userId}/memories`) — Persiste entre hilos:
                </div>
                {storeMemories.length === 0 ? (
                  <p className="text-[11px] text-slate-500">
                    Sin hechos guardados aún para `{userId}`. Ejecuta el Caso 2A.
                  </p>
                ) : (
                  <div className="space-y-1">
                    {storeMemories.map((m, idx) => (
                      <div
                        key={idx}
                        className="text-[11px] flex items-center justify-between bg-white px-2.5 py-1.5 rounded-lg border border-slate-200"
                      >
                        <span>
                          <strong className="text-slate-800">{m.label}:</strong>{" "}
                          <span className="text-[#00875A] font-mono font-semibold">{m.value}</span>
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          hilo: {m.source_thread_id}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 4. Evidencia Qdrant & Pydantic */}
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-2.5 max-h-[320px] overflow-y-auto">
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#003B71] flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-amber-600" />
                4. Evidencia Recuperada: Citas Qdrant & Tools Pydantic
              </h2>

              {lastTurn?.structured_outputs && lastTurn.structured_outputs.length > 0 && (
                <div className="space-y-1.5">
                  {lastTurn.structured_outputs.map((rep, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-xl bg-sky-50 border border-sky-200 text-[11px]"
                    >
                      <div className="font-mono font-bold text-[#003B71]">
                        @tool {rep.tool_name} ({rep.records_matched} filas exactas)
                      </div>
                      <div className="text-slate-600 font-mono text-[10px] mt-1">
                        Métricas: {JSON.stringify(rep.summary_metrics)}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {lastTurn?.rag_citations && lastTurn.rag_citations.length > 0 ? (
                <div className="space-y-1.5">
                  {lastTurn.rag_citations.map((cit) => (
                    <div
                      key={cit.chunk_id}
                      className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-[11px]"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-[#00875A]">
                          #{cit.rank} · {cit.chunk_id}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500">
                          RRF: {cit.score} (Cos: {cit.dense_score} · BM25: {cit.lexical_score})
                        </span>
                      </div>
                      <a
                        href={cit.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[#0066B3] hover:underline font-medium block mt-0.5"
                      >
                        {cit.title} ({cit.source_url})
                      </a>
                    </div>
                  ))}
                </div>
              ) : (
                !lastTurn?.structured_outputs?.length && (
                  <p className="text-xs text-slate-500">
                    Cuando el Router invoca Qdrant o las tools CSV/JSON, las citas y esquemas
                    Pydantic aparecen aquí.
                  </p>
                )
              )}
            </div>
          </div>
        </main>
      )}

      {/* VISTA 3: EVALUACIÓN CUANTITATIVA DEL RETRIEVAL (Recall@10 / nDCG@10) */}
      {activeTab === "eval" && (
        <main className="max-w-[1400px] w-full mx-auto px-4 py-6 space-y-6">
          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-[#003B71]">
                Evaluación Cuantitativa del Retrieval sobre Qdrant (Criterio 4.2 — 7%)
              </h2>
              <p className="text-xs text-slate-600 mt-1">
                Benchmark reproducible sobre 25 consultas etiquetadas del corpus de EMCALI (1.386
                chunks indexados con HNSW Cosine m=16, ef_construct=128).
              </p>
            </div>
            <button
              onClick={loadEvaluationMetrics}
              disabled={evalLoading}
              className="px-4 py-2 rounded-xl bg-[#00875A] hover:bg-[#006b47] text-white text-xs font-bold cursor-pointer shadow-xs"
            >
              {evalLoading ? "Calculando..." : "Recalcular Recall@10 y nDCG@10"}
            </button>
          </div>

          {evalData?.modes && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(["hybrid", "dense", "lexical"] as const).map((modeKey) => {
                  const m = evalData.modes[modeKey];
                  if (!m) return null;
                  return (
                    <div
                      key={modeKey}
                      className={`p-4 rounded-2xl border shadow-xs ${
                        modeKey === "hybrid"
                          ? "bg-emerald-50/70 border-[#00875A]/50"
                          : "bg-white border-slate-200"
                      }`}
                    >
                      <div className="text-xs font-bold uppercase text-[#00875A]">
                        Modo: {modeKey.toUpperCase()} ({m.queries_evaluated} consultas)
                      </div>
                      <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                        <div className="p-2.5 rounded-xl bg-white border border-slate-200">
                          <span className="text-slate-500 block">Recall@10</span>
                          <span className="text-lg font-bold text-[#003B71] font-mono">
                            {(m.recall_at_10 * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-white border border-slate-200">
                          <span className="text-slate-500 block">nDCG@10</span>
                          <span className="text-lg font-bold text-[#00875A] font-mono">
                            {m.ndcg_at_10.toFixed(3)}
                          </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-white border border-slate-200">
                          <span className="text-slate-500 block">Recall@5</span>
                          <span className="font-bold text-slate-800 font-mono">
                            {(m.recall_at_5 * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-white border border-slate-200">
                          <span className="text-slate-500 block">MRR@10</span>
                          <span className="font-bold text-purple-700 font-mono">
                            {m.mrr_at_10.toFixed(3)}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="rounded-2xl bg-white border border-slate-200 shadow-xs overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-600 uppercase text-[11px]">
                    <tr>
                      <th className="p-3">#</th>
                      <th className="p-3">Categoría</th>
                      <th className="p-3">Consulta Etiquetada</th>
                      <th className="p-3">Sección</th>
                      <th className="p-3">1.er Rank</th>
                      <th className="p-3">Recall@10</th>
                      <th className="p-3">nDCG@10</th>
                      <th className="p-3">Top Chunk</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {evalData.modes.hybrid.per_query.map((row: any) => (
                      <tr key={row.id} className="hover:bg-slate-50">
                        <td className="p-3 font-mono text-slate-500">{row.id}</td>
                        <td className="p-3 font-semibold text-slate-800">{row.category}</td>
                        <td className="p-3 text-slate-700 max-w-md">{row.query}</td>
                        <td className="p-3 font-mono text-[#0066B3]">{row.expected_section}</td>
                        <td className="p-3 font-mono text-[#00875A] font-bold">
                          #{row.first_relevant_rank}
                        </td>
                        <td className="p-3 font-mono">{(row.recall_at_10 * 100).toFixed(0)}%</td>
                        <td className="p-3 font-mono text-purple-700">
                          {row.ndcg_at_10.toFixed(3)}
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-500">
                          {row.top_hit_chunk_id}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </main>
      )}

      {/* VISTA 4: ARQUITECTURA DESACOPLADA Y DATOS ESTRUCTURADOS CSV/JSON */}
      {activeTab === "arch" && (
        <main className="max-w-[1400px] w-full mx-auto px-4 py-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <div className="flex items-center gap-2 text-[#00875A] font-bold text-sm mb-2">
                <Cpu className="w-4 h-4" />
                <span>1. Separación Frontend / Backend</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Frontend propio en <strong>React 19 + TypeScript + Vite</strong> desacoplado del
                backend <strong>FastAPI</strong> (`api/main.py`). Comunicación vía HTTP JSON y{" "}
                <strong>Server-Sent Events (SSE)</strong> para streaming token a token.
              </p>
            </div>
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <div className="flex items-center gap-2 text-purple-700 font-bold text-sm mb-2">
                <GitBranch className="w-4 h-4" />
                <span>2. Grafo LangGraph + Memorias SQLite</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                <strong>Corto plazo:</strong> `SqliteSaver` por `thread_id` + `trim_messages` +
                `SummarizationMiddleware`. <strong>Largo plazo:</strong> `PersistentSqliteStore`
                con namespace `("users", user_id, "memories")` recuperable entre hilos con `search()`.
              </p>
            </div>
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <div className="flex items-center gap-2 text-[#003B71] font-bold text-sm mb-2">
                <FileSpreadsheet className="w-4 h-4" />
                <span>3. Tools Pydantic + Qdrant ANN + Blindaje</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Router Gatekeeper <strong>System One (Jev)</strong> que arbitra entre respuesta
                directa (`Noul`), `@tool` determinista sobre CSV/JSON con Pydantic y búsqueda
                híbrida en <strong>Qdrant HNSW</strong> protegida con `&lt;datos_pasivos_corpus&gt;`.
              </p>
            </div>
          </div>

          <div className="rounded-2xl bg-white border border-slate-200 shadow-xs p-4">
            <h3 className="text-sm font-bold text-[#003B71] mb-3">
              Vista en Vivo del Dataset Estructurado (`data/structured/tarifas_servicios_emcali.csv` — Corte 2026-Q3)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-600 uppercase text-[11px]">
                  <tr>
                    <th className="p-2.5">Servicio</th>
                    <th className="p-2.5">Estrato / Segmento</th>
                    <th className="p-2.5">Trimestre</th>
                    <th className="p-2.5">Tarifa Base (COP)</th>
                    <th className="p-2.5">Subsidio / Contrib.</th>
                    <th className="p-2.5">Tarifa Aplicada (COP)</th>
                    <th className="p-2.5">Meta Doc (COP)</th>
                    <th className="p-2.5">Factura Mes Est.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 font-mono">
                  {tarifasPreview.slice(0, 14).map((r, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="p-2.5 text-[#0066B3] font-semibold">{r.servicio}</td>
                      <td className="p-2.5 text-slate-700">
                        {r.estrato > 0 ? `Estrato ${r.estrato}` : r.segmento}
                      </td>
                      <td className="p-2.5 text-slate-700">{r.trimestre}</td>
                      <td className="p-2.5 text-slate-700">${r.tarifa_base_cop}</td>
                      <td className="p-2.5 text-slate-700">{r.subsidio_contribucion_pct}%</td>
                      <td className="p-2.5 text-[#00875A] font-bold">
                        ${r.tarifa_aplicada_cop}
                      </td>
                      <td className="p-2.5 text-slate-700">${r.meta_documento_cop}</td>
                      <td className="p-2.5 text-purple-700">${r.factura_estimada_mes_cop}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      )}
    </div>
  );
}
