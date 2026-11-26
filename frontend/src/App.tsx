import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  CornerDownRight,
  Cpu,
  Database,
  FileSpreadsheet,
  FileText,
  GitBranch,
  History,
  Layers,
  LogOut,
  MapPin,
  Maximize2,
  Menu,
  MessageCircle,
  Mic,
  MicOff,
  Minimize2,
  Newspaper,
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
  X,
} from "lucide-react";
import type {
  DemoPreset,
  MemoryItem,
  TurnPayload,
} from "./types";
import { M3OperationsSuite, type M3Section } from "./components/M3OperationsSuite";

type PortalSection = M3Section | "xray" | "eval" | "arch";

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
          className="text-[#477D1C] underline decoration-[#CDE3B4] hover:text-[#2D5211] font-semibold break-all"
        >
          {match[2]}
        </a>
      );
    } else if (match[4]) {
      nodes.push(
        <strong key={key} className="font-bold text-[#141B12]">
          {renderInlineMarkdown(match[4], key)}
        </strong>
      );
    } else if (match[5]) {
      nodes.push(
        <code
          key={key}
          className="px-1.5 py-0.5 rounded-md bg-[#EEF6E6] border border-[#CDE3B4] text-[#2D5211] font-mono text-[11px]"
        >
          {match[5]}
        </code>
      );
    } else if (match[6]) {
      nodes.push(
        <em key={key} className="italic text-[#475569]">
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
          ? "text-sm font-extrabold text-[#141B12] mt-2.5 mb-1 tracking-tight"
          : level === 3
          ? "text-xs sm:text-sm font-bold text-[#477D1C] mt-2.5 mb-1 border-b border-[#DDE5D7] pb-1"
          : "text-xs font-bold text-[#2D5211] mt-2 mb-0.5";
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
      <p key={`p-${i}`} className="text-[#1E293B] leading-relaxed my-1">
        {renderInlineMarkdown(trimmed, `p-${i}`)}
      </p>
    );
  });

  flushBullets(lines.length);
  return <div className="space-y-1">{blocks}</div>;
}

export default function App() {
  const [activeSection, setActiveSection] = useState<PortalSection>("map_reports");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState<boolean>(false);
  const [mileDrawerOpen, setMileDrawerOpen] = useState<boolean>(false);
  const [mileDrawerExpanded, setMileDrawerExpanded] = useState<boolean>(false);

  const getOrCreateAnonId = (): string => {
    let anon = localStorage.getItem("emcali_anon_id");
    if (!anon) {
      anon = `anon-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem("emcali_anon_id", anon);
    }
    return anon;
  };

  const resolveActiveUserIdentity = (): {
    uid: string;
    tid: string;
    role: "citizen" | "manager";
    authenticated: boolean;
    displayName: string;
  } => {
    try {
      const saved = localStorage.getItem("emcali_auth_session");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed?.authenticated && parsed?.username) {
          const uname = String(parsed.username).toLowerCase();
          return {
            uid: uname,
            tid: `user-${uname}-chat`,
            role: parsed.role === "manager" ? "manager" : "citizen",
            authenticated: true,
            displayName: String(parsed.display_name || parsed.username),
          };
        }
      }
    } catch {
      // ignore
    }
    const anon = getOrCreateAnonId();
    return {
      uid: anon,
      tid: `${anon}-chat`,
      role: "citizen",
      authenticated: false,
      displayName: "Ciudadano",
    };
  };

  const initialIdentity = resolveActiveUserIdentity();
  const [authRole, setAuthRole] = useState<"citizen" | "manager">(initialIdentity.role);
  const [authAuthenticated, setAuthAuthenticated] = useState<boolean>(initialIdentity.authenticated);
  const [authDisplayName, setAuthDisplayName] = useState<string>(initialIdentity.displayName);
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [presets, setPresets] = useState<DemoPreset[]>([]);
  const [threadId, setThreadId] = useState<string>(initialIdentity.tid);
  const [userId, setUserId] = useState<string>(initialIdentity.uid);
  const [sectionFilter, setSectionFilter] = useState<string>("");
  const [searchMode, setSearchMode] = useState<"hybrid" | "dense" | "lexical">("hybrid");
  const [useLlm, setUseLlm] = useState<boolean>(true);

  const [question, setQuestion] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);

  const getChatAuthHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    try {
      const saved = localStorage.getItem("emcali_auth_session");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed?.token) headers["Authorization"] = `Bearer ${parsed.token}`;
      }
    } catch {
      // ignore
    }
    return headers;
  };

  const loadPersonalChatHistory = async (targetUserId: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/api/chat/history?user_id=${encodeURIComponent(targetUserId)}`,
        { headers: getChatAuthHeaders() }
      );
      if (res.ok) {
        const data = await res.json();
        const restored: ChatMessage[] = (data.messages || []).map((m: any) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: String(m.content || ""),
        }));
        setMessages(restored);
      }
    } catch {
      // silent
    }
  };

  useEffect(() => {
    loadPersonalChatHistory(userId);
    const syncAuth = () => {
      const next = resolveActiveUserIdentity();
      setAuthRole(next.role);
      setAuthAuthenticated(next.authenticated);
      setAuthDisplayName(next.displayName);
      setUserId(next.uid);
      setThreadId(next.tid);
      if (next.role !== "manager") {
        setActiveSection((cur) => (cur === "iam" ? "map_reports" : cur));
      }
      loadPersonalChatHistory(next.uid);
    };
    window.addEventListener("emcali-auth-changed", syncAuth);
    window.addEventListener("storage", syncAuth);
    return () => {
      window.removeEventListener("emcali-auth-changed", syncAuth);
      window.removeEventListener("storage", syncAuth);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [lastTurn, setLastTurn] = useState<Partial<TurnPayload> | null>(null);
  const [storeMemories, setStoreMemories] = useState<MemoryItem[]>([]);
  const [threadCheckpoints, setThreadCheckpoints] = useState<Array<Record<string, any>>>([]);

  // Voz, Hotword ("Melva" / "Oye Melva" / "Hola Melva") y Modo Continuo "Melva Live" (Gemini Live style)
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
    "Oye Melva, ¿cuántas PQR se atendieron en el tercer trimestre?"
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
    });
  };

  useEffect(() => {
    if (mileDrawerOpen && messages.length > 0) {
      scrollToChatBottom();
    }
  }, [messages, isStreaming, mileDrawerOpen]);

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
      "soy melva",
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

    // 3. Superposición léxica con el último TTS pronunciado por Melva
    const lastTts = lastSpokenTtsRef.current;
    if (lastTts && clean.length > 10 && lastTts.includes(clean)) {
      return true;
    }
    return false;
  };

  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const speakWithBrowserFallback = (spokenCleanText: string, onEndCallback?: () => void) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      resumeMicAfterSpeakerOutput(250);
      if (onEndCallback) onEndCallback();
      return;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(spokenCleanText);
    const voices = window.speechSynthesis.getVoices();
    const femaleCo =
      voices.find(
        (v) =>
          v.lang.toLowerCase().startsWith("es-co") &&
          /salome|helena|sabina|paulina|monica|female|woman/i.test(v.name)
      ) ||
      voices.find((v) => v.lang.toLowerCase().startsWith("es-co")) ||
      voices.find(
        (v) =>
          v.lang.toLowerCase().startsWith("es") &&
          /salome|helena|sabina|paulina|monica|elena|laura|female/i.test(v.name)
      );
    if (femaleCo) {
      utter.voice = femaleCo;
      utter.lang = femaleCo.lang;
    } else {
      utter.lang = "es-CO";
    }
    utter.rate = 1.02;
    utter.pitch = 1.05;
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
  };

  const speakText = (text: string, onEndCallback?: () => void) => {
    if (!ttsEnabled || typeof window === "undefined") {
      resumeMicAfterSpeakerOutput(250);
      if (onEndCallback) onEndCallback();
      return;
    }
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

    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    setLiveActivity("speaking");
    fetch(`${API_BASE}/api/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: spokenCleanText }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`TTS HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        currentAudioRef.current = audio;
        audio.onended = () => {
          URL.revokeObjectURL(audioUrl);
          if (currentAudioRef.current === audio) currentAudioRef.current = null;
          resumeMicAfterSpeakerOutput(700);
          if (onEndCallback) onEndCallback();
        };
        audio.onerror = () => {
          URL.revokeObjectURL(audioUrl);
          if (currentAudioRef.current === audio) currentAudioRef.current = null;
          speakWithBrowserFallback(spokenCleanText, onEndCallback);
        };
        audio.play().catch(() => {
          URL.revokeObjectURL(audioUrl);
          speakWithBrowserFallback(spokenCleanText, onEndCallback);
        });
      })
      .catch(() => {
        speakWithBrowserFallback(spokenCleanText, onEndCallback);
      });
  };

  const interruptSpeechBargeIn = () => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    resumeMicAfterSpeakerOutput(200);
    setVoiceBanner("✋ Barge-In: Respuesta de voz interrumpida. Melva Live te escucha de nuevo...");
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
        headers: getChatAuthHeaders(),
        body: JSON.stringify({
          question: qText,
          thread_id: threadId,
          user_id: userId,
          section_filter: sectionFilter || null,
          search_mode: searchMode,
          top_k: 6,
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
          `⏸️ Ignorado en espera: di "Melva", "Oye Melva" o "Hola Melva" para activar Melva Live (capturado: "${spokenTranscript}").`
        );
        return;
      }

      const analysis = data.voice_analysis;

      // Si el usuario dijo "Gracias Melva" / "Eso es todo" -> vuelve a espera
      if (analysis.sleep_requested) {
        liveSessionRef.current = false;
        setLiveSessionActive(false);
        setVoiceBanner(
          '🌙 Melva Live en espera. Cuando me necesites vuelve a decir "Oye Melva" o "Hola Melva".'
        );
        speakText(
          data.tts_speech_text ||
            "Con gusto. Paso a modo de espera; cuando me necesites solo di Oye Melva."
        );
        return;
      }

      // ¡Hotword detectado! Entramos o permanecemos en Melva Live (modo Gemini Live)
      liveSessionRef.current = true;
      setLiveSessionActive(true);

      if (analysis.wake_only) {
        setVoiceBanner(
          `🟢 Melva Live ACTIVO ("${analysis.matched_hotword}"). Habla libremente cuando Melva termine de saludarte (di "Gracias Melva" para salir).`
        );
        speakText(
          data.tts_speech_text ||
            "¡Hola! Soy Melva Live. Te escucho en vivo, dime qué necesitas de EMCALI."
        );
        return;
      }

      const turn: TurnPayload = data.turn;
      setVoiceBanner(
        `🟢 Melva Live (${analysis.matched_hotword || "Continuo"}) → "${analysis.clean_query}" · Micrófono silenciado mientras Melva habla para evitar eco`
      );
      setLastTurn(turn);
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: turn.question,
          voiceHotword: analysis.matched_hotword || "Melva Live",
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
        "ℹ️ Tu navegador actual no expone Web Speech API nativa; usa el simulador de Melva Live integrado aquí al lado."
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
      setVoiceBanner("🛑 Micrófono y sesión Melva Live detenidos.");
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
          ? '🟢 Melva Live escuchando en vivo... Habla con naturalidad (o di "Gracias Melva" para pausar)'
          : '🎧 Standby: di "Melva", "Oye Melva" o "Hola Melva" para despertar el modo Melva Live'
      );
    };

    rec.onresult = (event: any) => {
      // Bloqueo Half-Duplex: ignorar cualquier audio mientras Melva piensa, habla por TTS o está en ventana de eco
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
      // No auto-reiniciar el micrófono mientras Melva está hablando por los altavoces (se reanuda en utter.onend)
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

  const handleClearChat = async () => {
    setMessages([]);
    setLastTurn(null);
    setVoiceBanner("");
    setInterimTranscript("");
    try {
      await fetch(`${API_BASE}/api/chat/history?user_id=${encodeURIComponent(userId)}`, {
        method: "DELETE",
        headers: getChatAuthHeaders(),
      });
    } catch {
      // silent
    }
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
    if (activeSection === "eval" || activeSection === "arch") {
      loadEvaluationMetrics();
    }
  }, [activeSection]);

  const handleTopBarLogout = () => {
    localStorage.removeItem("emcali_auth_session");
    window.dispatchEvent(new Event("emcali-auth-changed"));
    if (activeSection === "iam") {
      setActiveSection("map_reports");
    }
  };

  const navigateToSection = (section: PortalSection) => {
    setActiveSection(section);
    setMobileSidebarOpen(false);
  };

  const isM3Section = (sec: PortalSection): sec is M3Section =>
    sec === "map_reports" ||
    sec === "pqrs" ||
    sec === "news" ||
    sec === "umap_tools" ||
    sec === "iam" ||
    sec === "auth";

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

  const sidebarItemClass = (id: PortalSection) =>
    `w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-2xl text-xs font-bold transition cursor-pointer text-left ${
      activeSection === id
        ? "bg-[#EEF6E6] text-[#2D5211] border border-[#CDE3B4] shadow-xs"
        : "text-[#1E293B] border border-transparent hover:bg-[#F3F6F1] hover:text-[#477D1C]"
    }`;

  const renderSidebarNav = () => (
    <div className="flex flex-col h-full justify-between gap-6">
      <div className="space-y-5">
        {/* GENERAL (Ciudadanía) */}
        <div className="space-y-1">
          <div className="px-3.5 text-[10px] font-extrabold uppercase tracking-widest text-[#5B6757]">
            General · Ciudadanía
          </div>
          <button
            onClick={() => navigateToSection("map_reports")}
            className={sidebarItemClass("map_reports")}
          >
            <MapPin className="w-4 h-4 shrink-0 text-[#579624]" />
            <span>Mapa y Reportes</span>
          </button>
          <button
            onClick={() => navigateToSection("pqrs")}
            className={sidebarItemClass("pqrs")}
          >
            <FileText className="w-4 h-4 shrink-0 text-[#579624]" />
            <span>PQRS</span>
          </button>
          <button
            onClick={() => navigateToSection("news")}
            className={sidebarItemClass("news")}
          >
            <Newspaper className="w-4 h-4 shrink-0 text-[#579624]" />
            <span>Noticias y Boletín</span>
          </button>
        </div>

        {/* GESTIÓN EMCALI (Solo Manager) */}
        {authRole === "manager" && (
          <div className="space-y-1 pt-3 border-t border-[#E7EDE3]">
            <div className="px-3.5 text-[10px] font-extrabold uppercase tracking-widest text-[#B45309]">
              Gestión EMCALI
            </div>
            <button
              onClick={() => navigateToSection("iam")}
              className={sidebarItemClass("iam")}
            >
              <ShieldCheck className="w-4 h-4 shrink-0 text-[#F5820D]" />
              <span>IAM y WhatsApp Allowlist</span>
            </button>
          </div>
        )}

        {/* ACADÉMICO (TAAML) */}
        <div className="space-y-1 pt-3 border-t border-[#E7EDE3]">
          <div className="px-3.5 text-[10px] font-extrabold uppercase tracking-widest text-[#5B6757]">
            Académico (TAAML)
          </div>
          <button
            onClick={() => navigateToSection("xray")}
            className={sidebarItemClass("xray")}
          >
            <Activity className="w-4 h-4 shrink-0 text-[#477D1C]" />
            <span>Rayos-X (Jev y Memoria)</span>
          </button>
          <button
            onClick={() => navigateToSection("umap_tools")}
            className={sidebarItemClass("umap_tools")}
          >
            <Sparkles className="w-4 h-4 shrink-0 text-[#477D1C]" />
            <span>UMAP y 20 Tools</span>
          </button>
          <button
            onClick={() => navigateToSection("eval")}
            className={sidebarItemClass("eval")}
          >
            <Database className="w-4 h-4 shrink-0 text-[#477D1C]" />
            <span>Evaluación Retrieval</span>
          </button>
          <button
            onClick={() => navigateToSection("arch")}
            className={sidebarItemClass("arch")}
          >
            <Cpu className="w-4 h-4 shrink-0 text-[#477D1C]" />
            <span>Arquitectura</span>
          </button>
        </div>
      </div>

      {/* Tarjeta sutil de acceso directo a Melva en el pie del sidebar */}
      <div className="p-3.5 rounded-2xl bg-[#EEF6E6] border border-[#CDE3B4] space-y-2">
        <div className="flex items-center gap-2">
          <img
            src="/melva-avatar.jpg"
            alt="Melva"
            className="w-8 h-8 rounded-full object-cover border-2 border-[#579624] shrink-0"
          />
          <div className="min-w-0">
            <div className="text-xs font-extrabold text-[#141B12] truncate">Melva · Asistente IA</div>
            <div className="text-[10px] text-[#2D5211] font-medium">Voz en vivo &amp; WhatsApp</div>
          </div>
        </div>
        <button
          onClick={() => {
            setMileDrawerOpen(true);
            setMobileSidebarOpen(false);
          }}
          className="w-full py-1.5 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white text-[11px] font-bold transition cursor-pointer"
        >
          Abrir chat con Melva
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F3F6F1] text-[#141B12] flex flex-col">
      {/* Header Institucional EMCALI 2026 — ¡Siempre Juntos! */}
      <header className="bg-white/95 backdrop-blur-md sticky top-0 z-30 shadow-[0_2px_12px_rgba(20,27,18,0.04)]">
        <div className="max-w-[1560px] mx-auto px-4 sm:px-6 pt-3 pb-2.5 flex items-center justify-between gap-3">
          {/* Izquierda: Menú móvil + Brand Lockup EMCALI ¡Siempre Juntos! + Static Melva Avatar */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileSidebarOpen((v) => !v)}
              className="lg:hidden p-2 rounded-xl border border-[#DDE5D7] bg-[#F7FAF4] text-[#141B12] hover:bg-[#EEF6E6] cursor-pointer"
              aria-label="Abrir menú de navegación"
            >
              {mobileSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <button
              type="button"
              onClick={() => navigateToSection("map_reports")}
              className="flex items-center gap-3 text-left cursor-pointer"
            >
              <div className="h-10 w-10 rounded-full bg-[#EEF6E6] flex items-center justify-center border border-[#CDE3B4] shrink-0">
                <img
                  src="/melva-avatar.jpg"
                  alt="Melva, asistente virtual de EMCALI"
                  className="h-8 w-8 rounded-full object-cover shadow-xs border-2 border-[#579624]"
                />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <div className="flex flex-col leading-none">
                    <h1 className="font-extrabold text-lg sm:text-xl tracking-tight text-[#141B12] leading-none">
                      EMCALI
                    </h1>
                    <span className="text-[11px] font-bold text-[#579624] tracking-tight mt-0.5">
                      ¡Siempre Juntos!
                    </span>
                  </div>
                  <span className="hidden sm:inline-block text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#EEF6E6] text-[#2D5211] border border-[#CDE3B4]">
                    Portal Digital 2026
                  </span>
                </div>
                <p className="text-[11px] text-[#5B6757] hidden md:block mt-0.5">
                  Energía · Acueducto y Alcantarillado · Telecomunicaciones · Atención Ciudadana
                </p>
              </div>
            </button>
          </div>

          {/* Derecha: Botón sutil Hablar con Melva + Reportar Falla + Mi cuenta / Sesión */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMileDrawerOpen((v) => !v)}
              className={`px-3.5 py-2 rounded-full text-xs font-bold border transition cursor-pointer flex items-center gap-1.5 ${
                mileDrawerOpen
                  ? "bg-[#2D5211] text-white border-[#2D5211]"
                  : "bg-[#EEF6E6] hover:bg-[#E1F0D3] text-[#2D5211] border-[#CDE3B4]"
              }`}
              title="Abrir o cerrar el asistente virtual Mile"
            >
              <MessageCircle className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Hablar con Melva</span>
            </button>

            <button
              type="button"
              onClick={() => navigateToSection("map_reports")}
              className="hidden sm:flex px-4 py-2 rounded-full bg-[#F5820D] hover:bg-[#DC7006] text-white text-xs font-bold transition cursor-pointer shadow-xs items-center gap-1.5"
              title="Reportar una falla o ver mantenimientos en el mapa"
            >
              <span>Reportar Falla</span>
              <span aria-hidden="true">↗</span>
            </button>

            {authAuthenticated ? (
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => navigateToSection(authRole === "manager" ? "iam" : "auth")}
                  className={`px-3.5 py-2 rounded-full text-xs font-bold transition cursor-pointer shadow-xs flex items-center gap-1.5 ${
                    authRole === "manager"
                      ? "bg-[#FACC15] hover:bg-[#F5C400] text-[#141B12]"
                      : "bg-[#579624] hover:bg-[#477D1C] text-white"
                  }`}
                  title={authDisplayName}
                >
                  <span>
                    {authRole === "manager" ? "Gestión EMCALI" : authDisplayName.split(" ")[0]}
                  </span>
                  <span aria-hidden="true">↗</span>
                </button>
                <button
                  type="button"
                  onClick={handleTopBarLogout}
                  className="p-2 rounded-full bg-[#F3F6F1] hover:bg-rose-50 border border-[#DDE5D7] hover:border-rose-300 text-[#1E293B] hover:text-rose-700 transition cursor-pointer"
                  title="Cerrar sesión"
                  aria-label="Cerrar sesión"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => navigateToSection("auth")}
                className="px-4 py-2 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white text-xs font-bold transition cursor-pointer shadow-xs flex items-center gap-1.5"
                title="Iniciar sesión o crear cuenta ciudadana"
              >
                <span>Mi cuenta</span>
                <span aria-hidden="true">↗</span>
              </button>
            )}
          </div>
        </div>
        {/* Franja verde salvia característica del portal EMCALI 2026 */}
        <div className="max-w-[1560px] mx-auto px-4 sm:px-6 pb-2">
          <div className="h-1.5 w-full rounded-full bg-[#DCECC9]" />
        </div>
      </header>

      {errorBanner && (
        <div className="bg-rose-50 border-b border-rose-200 px-4 py-2.5 text-xs text-rose-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorBanner}</span>
          </div>
          <button
            onClick={fetchBackendStatus}
            className="px-3 py-1 rounded-full bg-rose-600 hover:bg-rose-700 text-white font-semibold cursor-pointer"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Drawer de Sidebar en Móvil */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden flex">
          <div
            className="fixed inset-0 bg-[#141B12]/40 backdrop-blur-xs"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <aside className="relative w-72 max-w-[85vw] bg-white h-full p-4 shadow-2xl border-r border-[#DDE5D7] overflow-y-auto z-50">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#E7EDE3]">
              <span className="font-extrabold text-sm text-[#141B12]">Navegación EMCALI</span>
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="p-1.5 rounded-full hover:bg-[#F3F6F1] text-[#5B6757] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            {renderSidebarNav()}
          </aside>
        </div>
      )}

      {/* Cuerpo Principal: Sidebar Izquierdo Fijo (Desktop) + Área de Contenido */}
      <div className="flex-1 flex max-w-[1560px] w-full mx-auto">
        <aside className="hidden lg:block w-64 shrink-0 px-4 py-6">
          <div className="sticky top-24 bg-white rounded-3xl border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] p-3.5 max-h-[calc(100vh-7rem)] overflow-y-auto">
            {renderSidebarNav()}
          </div>
        </aside>

        <main className="flex-1 min-w-0 px-4 sm:px-6 py-6 pb-24">
          {/* SECCIONES OPERATIVAS & CIUDADANAS (M3) */}
          {isM3Section(activeSection) && (
            <M3OperationsSuite
              activeSection={activeSection}
              onNavigateSection={(sec) => navigateToSection(sec)}
            />
          )}

          {/* VISTA 2: TAB ACADÉMICO — RAYOS-X, CASOS DE VALIDACIÓN, PID, MEMORIA Y BLINDAJE */}
          {activeSection === "xray" && (
            <div className="space-y-5">
          <div>
            <div className="text-xs font-semibold text-[#477D1C]">
              Observabilidad LangGraph · Router System One (Jev) &amp; Blindaje RAG
            </div>
            <div className="w-10 h-0.5 bg-[#579624] rounded-full my-1.5" />
            <h2 className="text-2xl font-extrabold tracking-tight text-[#141B12]">
              Rayos-X y Validación en Vivo
            </h2>
          </div>

          {/* Barra Técnica de Sesión, PID y Reinicio */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] flex flex-wrap items-end justify-between gap-3">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 flex-1 min-w-[300px]">
              <div>
                <label className="block text-[11px] font-semibold text-[#5B6757] mb-1">
                  Hilo Corto Plazo (SqliteSaver thread_id)
                </label>
                <div className="flex gap-1.5">
                  <input
                    value={threadId}
                    onChange={(e) => {
                      setThreadId(e.target.value);
                      fetchThreadAndStore(e.target.value, userId);
                    }}
                    className="w-full px-3 py-1.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-xs font-mono text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <button
                    onClick={handleCreateNewThread}
                    className="px-3 py-1.5 rounded-xl bg-[#EEF6E6] hover:bg-[#E1F0D3] border border-[#CDE3B4] text-[#2D5211] text-xs font-bold shrink-0 cursor-pointer"
                  >
                    + Hilo
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#5B6757] mb-1">
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
                    className="w-full px-3 py-1.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-xs font-mono text-purple-700 focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#5B6757] mb-1">
                  Modo Qdrant &amp; Filtro Payload
                </label>
                <div className="flex gap-1.5">
                  <select
                    value={searchMode}
                    onChange={(e) => setSearchMode(e.target.value as any)}
                    className="w-1/2 px-2.5 py-1.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-xs text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  >
                    <option value="hybrid">Híbrido (RRF)</option>
                    <option value="dense">Denso (HNSW)</option>
                    <option value="lexical">Léxico (BM25)</option>
                  </select>
                  <select
                    value={sectionFilter}
                    onChange={(e) => setSectionFilter(e.target.value)}
                    className="w-1/2 px-2.5 py-1.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-xs text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
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
                <label className="flex items-center gap-1.5 text-xs text-[#1E293B] cursor-pointer select-none bg-[#F7FAF4] px-3 py-2 rounded-xl border border-[#DDE5D7]">
                  <input
                    type="checkbox"
                    checked={useLlm}
                    onChange={(e) => setUseLlm(e.target.checked)}
                    className="accent-[#579624]"
                  />
                  <span className="font-semibold">DeepSeek API</span>
                </label>
                <button
                  onClick={() => {
                    fetchBackendStatus();
                    fetchThreadAndStore(threadId, userId);
                  }}
                  className="px-3.5 py-2 rounded-full bg-[#141B12] hover:bg-[#283324] text-white text-xs font-bold flex items-center gap-1.5 cursor-pointer"
                  title="Refrescar PID del Backend y recuperar el hilo desde SqliteSaver"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>PID: {health?.server_pid ?? "---"}</span>
                </button>
              </div>
            </div>
          </div>

          {/* 5 Casos Oficiales de Sustentación (1 Clic y salta al Chat o muestra traza) */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <span className="text-xs font-extrabold uppercase tracking-wider text-[#141B12] flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-[#579624]" />
                Casos Oficiales de Validación Académica (Módulo 2)
              </span>
              <span className="text-[11px] text-[#5B6757]">
                Ejecuta el caso en vivo y consulta la traza abajo o en Atención Ciudadana
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => {
                    handleSendQuestion(preset.question);
                    setMileDrawerOpen(true);
                  }}
                  disabled={isStreaming}
                  title={`${preset.title}\n\n${preset.description}`}
                  className="p-3 rounded-xl bg-[#F7FAF4] hover:bg-[#EEF6E6] border border-[#DDE5D7] hover:border-[#579624] text-left transition flex flex-col justify-between cursor-pointer disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[11px] font-extrabold text-[#477D1C]">{preset.number}</span>
                    <span className="text-[10px] text-[#5B6757] font-mono">
                      {preset.minute_block}
                    </span>
                  </div>
                  <p className="text-[11px] font-semibold text-[#141B12] line-clamp-2 mt-1 leading-tight">
                    {preset.title}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Grid de 4 Tarjetas de Rayos-X */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* 1. Router System One (Jev) */}
            <div className="p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-[#141B12] flex items-center gap-1.5">
                  <Route className="w-4 h-4 text-[#579624]" />
                  1. Router Agent &amp; Gatekeeper System One (Jev)
                </h2>
                {lastTurn?.router_decision && (
                  <span
                    className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${routeBadgeColor(
                      lastTurn.router_decision.choice
                    )}`}
                  >
                    Choice: {lastTurn.router_decision.choice}
                  </span>
                )}
              </div>

              {lastTurn?.router_decision ? (
                <div className="space-y-2.5 text-xs">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="p-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7]">
                      <span className="text-[10px] text-[#5B6757] block">Compuerta Noul</span>
                      <span
                        className={`font-mono font-bold ${
                          lastTurn.router_decision.noul_triggered
                            ? "text-[#DC7006]"
                            : "text-[#141B12]"
                        }`}
                      >
                        {lastTurn.router_decision.noul_triggered
                          ? "TRUE (0 búsquedas)"
                          : "FALSE (tools)"}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7]">
                      <span className="text-[10px] text-[#5B6757] block">Jev Score</span>
                      <span className="font-mono font-bold text-[#477D1C]">
                        {(lastTurn.router_decision.score * 100).toFixed(0)}% confianza
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7]">
                      <span className="text-[10px] text-[#5B6757] block">Tools invocadas</span>
                      <span className="font-mono text-[11px] text-[#141B12] font-bold">
                        {lastTurn.router_decision.tools_to_invoke.length || "Ninguna"}
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-[#1E293B] bg-[#F7FAF4] p-3 rounded-xl border border-[#DDE5D7]">
                    {lastTurn.router_decision.rationale}
                  </p>
                  <div className="text-[11px] font-mono text-[#475569] bg-[#F7FAF4] p-3 rounded-xl border border-[#DDE5D7] overflow-x-auto">
                    <span className="text-purple-700 font-semibold">Box: </span>
                    {JSON.stringify(lastTurn.router_decision.box)}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[#5B6757]">
                  Realiza una consulta en Atención Ciudadana para inspeccionar Choice, Noul, Score y
                  Box.
                </p>
              )}
            </div>

            {/* 2. Blindaje del RAG */}
            <div className="p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-[#141B12] flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-[#579624]" />
                  2. Blindaje del RAG (&lt;datos_pasivos_corpus&gt;)
                </h2>
                {lastTurn?.security_audit && (
                  <span
                    className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border flex items-center gap-1 ${
                      lastTurn.security_audit.any_injection_detected
                        ? "bg-rose-50 text-rose-700 border-rose-300"
                        : "bg-[#EEF6E6] text-[#2D5211] border-[#CDE3B4]"
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
                <p className="text-xs text-[#475569] leading-relaxed">
                  Todos los fragmentos recuperados de Qdrant ({health?.qdrant?.indexed_points ?? 1386}{" "}
                  chunks) se encapsulan en{" "}
                  <code className="text-[#2D5211] bg-[#EEF6E6] px-1.5 py-0.5 rounded font-mono">
                    &lt;datos_pasivos_corpus solo_lectura="true"&gt;
                  </code>{" "}
                  para impedir que instrucciones ocultas alteren al agente.
                </p>
              )}
            </div>

            {/* 3. Memoria Corto Plazo & Largo Plazo */}
            <div className="p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-[#141B12] flex items-center gap-1.5">
                  <History className="w-4 h-4 text-purple-600" />
                  3. Memoria Corto Plazo (SqliteSaver) &amp; Largo Plazo (Store)
                </h2>
                <span className="text-[11px] font-mono text-[#5B6757]">
                  Checkpoints: {threadCheckpoints.length}
                </span>
              </div>

              {lastTurn?.context_window && (
                <div className="grid grid-cols-3 gap-2 text-[11px]">
                  <div className="p-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7]">
                    <span className="text-[#5B6757] block">Mensajes Hilo</span>
                    <span className="font-mono font-bold text-[#141B12]">
                      {lastTurn.context_window.kept_messages_after} /{" "}
                      {lastTurn.context_window.total_messages_before}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7]">
                    <span className="text-[#5B6757] block">trim_messages</span>
                    <span className="font-mono font-bold text-[#477D1C]">
                      {lastTurn.context_window.tokens_after} /{" "}
                      {lastTurn.context_window.max_token_budget} tok
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7]">
                    <span className="text-[#5B6757] block">Summarization</span>
                    <span className="font-mono font-bold text-purple-700">
                      {lastTurn.context_window.summarization_triggered ? "ACTIVO" : "En rango"}
                    </span>
                  </div>
                </div>
              )}

              <div className="p-3 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7]">
                <div className="text-[11px] font-semibold text-purple-700 mb-1.5">
                  Store Namespace (`users/{userId}/memories`) — Persiste entre hilos:
                </div>
                {storeMemories.length === 0 ? (
                  <p className="text-[11px] text-[#5B6757]">
                    Sin hechos guardados aún para `{userId}`. Ejecuta el Caso 2A.
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {storeMemories.map((m, idx) => (
                      <div
                        key={idx}
                        className="text-[11px] flex items-center justify-between bg-white px-3 py-1.5 rounded-lg border border-[#DDE5D7]"
                      >
                        <span>
                          <strong className="text-[#141B12]">{m.label}:</strong>{" "}
                          <span className="text-[#477D1C] font-mono font-semibold">{m.value}</span>
                        </span>
                        <span className="text-[10px] text-[#5B6757] font-mono">
                          hilo: {m.source_thread_id}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 4. Evidencia Qdrant & Pydantic */}
            <div className="p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3 max-h-[340px] overflow-y-auto">
              <h2 className="text-xs font-extrabold uppercase tracking-wider text-[#141B12] flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-[#F5820D]" />
                4. Evidencia Recuperada: Citas Qdrant &amp; Tools Pydantic
              </h2>

              {lastTurn?.structured_outputs && lastTurn.structured_outputs.length > 0 && (
                <div className="space-y-1.5">
                  {lastTurn.structured_outputs.map((rep, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-[#EEF6E6] border border-[#CDE3B4] text-[11px]"
                    >
                      <div className="font-mono font-bold text-[#2D5211]">
                        @tool {rep.tool_name} ({rep.records_matched} filas exactas)
                      </div>
                      <div className="text-[#475569] font-mono text-[10px] mt-1">
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
                      className="p-3 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[11px]"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-[#477D1C]">
                          #{cit.rank} · {cit.chunk_id}
                        </span>
                        <span className="font-mono text-[10px] text-[#5B6757]">
                          RRF: {cit.score} (Cos: {cit.dense_score} · BM25: {cit.lexical_score})
                        </span>
                      </div>
                      <a
                        href={cit.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[#477D1C] hover:underline font-semibold block mt-0.5"
                      >
                        {cit.title} ({cit.source_url})
                      </a>
                    </div>
                  ))}
                </div>
              ) : (
                !lastTurn?.structured_outputs?.length && (
                  <p className="text-xs text-[#5B6757]">
                    Cuando el Router invoca Qdrant o las tools CSV/JSON, las citas y esquemas
                    Pydantic aparecen aquí.
                  </p>
                )
              )}
            </div>
          </div>
            </div>
          )}

          {/* VISTA 3: EVALUACIÓN CUANTITATIVA DEL RETRIEVAL (Recall@10 / nDCG@10) */}
          {activeSection === "eval" && (
            <div className="space-y-6">
          <div className="p-5 sm:p-6 rounded-3xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-xs font-semibold text-[#477D1C]">
                Benchmark Reproducible · Qdrant HNSW + BM25 (Criterio 4.2 — 7%)
              </div>
              <div className="w-10 h-0.5 bg-[#579624] rounded-full my-1.5" />
              <h2 className="text-2xl font-extrabold tracking-tight text-[#141B12]">
                Evaluación Cuantitativa del Retrieval
              </h2>
              <p className="text-xs text-[#5B6757] mt-1">
                Benchmark reproducible sobre 25 consultas etiquetadas del corpus de EMCALI (1.386
                chunks indexados con HNSW Cosine m=16, ef_construct=128).
              </p>
            </div>
            <button
              onClick={loadEvaluationMetrics}
              disabled={evalLoading}
              className="px-5 py-2.5 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white text-xs font-bold cursor-pointer shadow-xs transition"
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
                      className={`p-5 rounded-2xl border shadow-[0_2px_12px_rgba(20,27,18,0.05)] ${
                        modeKey === "hybrid"
                          ? "bg-[#EEF6E6] border-[#CDE3B4]"
                          : "bg-white border-[#DDE5D7]"
                      }`}
                    >
                      <div className="text-xs font-extrabold uppercase text-[#2D5211]">
                        Modo: {modeKey.toUpperCase()} ({m.queries_evaluated} consultas)
                      </div>
                      <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                        <div className="p-3 rounded-xl bg-white border border-[#DDE5D7]">
                          <span className="text-[#5B6757] block">Recall@10</span>
                          <span className="text-lg font-extrabold text-[#141B12] font-mono">
                            {(m.recall_at_10 * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="p-3 rounded-xl bg-white border border-[#DDE5D7]">
                          <span className="text-[#5B6757] block">nDCG@10</span>
                          <span className="text-lg font-extrabold text-[#477D1C] font-mono">
                            {m.ndcg_at_10.toFixed(3)}
                          </span>
                        </div>
                        <div className="p-3 rounded-xl bg-white border border-[#DDE5D7]">
                          <span className="text-[#5B6757] block">Recall@5</span>
                          <span className="font-bold text-[#1E293B] font-mono">
                            {(m.recall_at_5 * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="p-3 rounded-xl bg-white border border-[#DDE5D7]">
                          <span className="text-[#5B6757] block">MRR@10</span>
                          <span className="font-bold text-purple-700 font-mono">
                            {m.mrr_at_10.toFixed(3)}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F3F6F1] text-[#475569] uppercase text-[11px] font-bold">
                    <tr>
                      <th className="p-3.5">#</th>
                      <th className="p-3.5">Categoría</th>
                      <th className="p-3.5">Consulta Etiquetada</th>
                      <th className="p-3.5">Sección</th>
                      <th className="p-3.5">1.er Rank</th>
                      <th className="p-3.5">Recall@10</th>
                      <th className="p-3.5">nDCG@10</th>
                      <th className="p-3.5">Top Chunk</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E7EDE3]">
                    {evalData.modes.hybrid.per_query.map((row: any) => (
                      <tr key={row.id} className="hover:bg-[#F7FAF4]">
                        <td className="p-3.5 font-mono text-[#5B6757]">{row.id}</td>
                        <td className="p-3.5 font-bold text-[#141B12]">{row.category}</td>
                        <td className="p-3.5 text-[#1E293B] max-w-md">{row.query}</td>
                        <td className="p-3.5 font-mono text-[#477D1C] font-semibold">{row.expected_section}</td>
                        <td className="p-3.5 font-mono text-[#2D5211] font-bold">
                          #{row.first_relevant_rank}
                        </td>
                        <td className="p-3.5 font-mono">{(row.recall_at_10 * 100).toFixed(0)}%</td>
                        <td className="p-3.5 font-mono text-purple-700">
                          {row.ndcg_at_10.toFixed(3)}
                        </td>
                        <td className="p-3.5 font-mono text-[11px] text-[#5B6757]">
                          {row.top_hit_chunk_id}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
            </div>
          )}

          {/* VISTA 4: ARQUITECTURA DESACOPLADA Y DATOS ESTRUCTURADOS CSV/JSON */}
          {activeSection === "arch" && (
            <div className="space-y-6">
          <div>
            <div className="text-xs font-semibold text-[#477D1C]">
              Ingeniería de Plataforma · React 19 + FastAPI + LangGraph + Qdrant
            </div>
            <div className="w-10 h-0.5 bg-[#579624] rounded-full my-1.5" />
            <h2 className="text-2xl font-extrabold tracking-tight text-[#141B12]">
              Arquitectura y Datos Estructurados
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
              <div className="flex items-center gap-2 text-[#477D1C] font-extrabold text-sm mb-2">
                <Cpu className="w-4 h-4" />
                <span>1. Separación Frontend / Backend</span>
              </div>
              <p className="text-xs text-[#475569] leading-relaxed">
                Frontend propio en <strong className="text-[#141B12]">React 19 + TypeScript + Vite</strong> desacoplado del
                backend <strong className="text-[#141B12]">FastAPI</strong> (`api/main.py`). Comunicación vía HTTP JSON y{" "}
                <strong className="text-[#141B12]">Server-Sent Events (SSE)</strong> para streaming token a token.
              </p>
            </div>
            <div className="p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
              <div className="flex items-center gap-2 text-purple-700 font-extrabold text-sm mb-2">
                <GitBranch className="w-4 h-4" />
                <span>2. Grafo LangGraph + Memorias SQLite</span>
              </div>
              <p className="text-xs text-[#475569] leading-relaxed">
                <strong className="text-[#141B12]">Corto plazo:</strong> `SqliteSaver` por `thread_id` + `trim_messages` +
                `SummarizationMiddleware`. <strong className="text-[#141B12]">Largo plazo:</strong> `PersistentSqliteStore`
                con namespace `("users", user_id, "memories")` recuperable entre hilos con `search()`.
              </p>
            </div>
            <div className="p-5 rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
              <div className="flex items-center gap-2 text-[#DC7006] font-extrabold text-sm mb-2">
                <FileSpreadsheet className="w-4 h-4" />
                <span>3. Tools Pydantic + Qdrant ANN + Blindaje</span>
              </div>
              <p className="text-xs text-[#475569] leading-relaxed">
                Router Gatekeeper <strong className="text-[#141B12]">System One (Jev)</strong> que arbitra entre respuesta
                directa (`Noul`), `@tool` determinista sobre CSV/JSON con Pydantic y búsqueda
                híbrida en <strong className="text-[#141B12]">Qdrant HNSW</strong> protegida con `&lt;datos_pasivos_corpus&gt;`.
              </p>
            </div>
          </div>

          <div className="rounded-2xl bg-white border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] p-5">
            <h3 className="text-sm font-extrabold text-[#141B12] mb-3">
              Vista en Vivo del Dataset Estructurado (`data/structured/tarifas_servicios_emcali.csv` — Corte 2026-Q3)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F3F6F1] text-[#475569] uppercase text-[11px] font-bold">
                  <tr>
                    <th className="p-3">Servicio</th>
                    <th className="p-3">Estrato / Segmento</th>
                    <th className="p-3">Trimestre</th>
                    <th className="p-3">Tarifa Base (COP)</th>
                    <th className="p-3">Subsidio / Contrib.</th>
                    <th className="p-3">Tarifa Aplicada (COP)</th>
                    <th className="p-3">Meta Doc (COP)</th>
                    <th className="p-3">Factura Mes Est.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E7EDE3] font-mono">
                  {tarifasPreview.slice(0, 14).map((r, i) => (
                    <tr key={i} className="hover:bg-[#F7FAF4]">
                      <td className="p-3 text-[#477D1C] font-bold">{r.servicio}</td>
                      <td className="p-3 text-[#1E293B]">
                        {r.estrato > 0 ? `Estrato ${r.estrato}` : r.segmento}
                      </td>
                      <td className="p-3 text-[#1E293B]">{r.trimestre}</td>
                      <td className="p-3 text-[#1E293B]">${r.tarifa_base_cop}</td>
                      <td className="p-3 text-[#1E293B]">{r.subsidio_contribucion_pct}%</td>
                      <td className="p-3 text-[#2D5211] font-bold">
                        ${r.tarifa_aplicada_cop}
                      </td>
                      <td className="p-3 text-[#1E293B]">${r.meta_documento_cop}</td>
                      <td className="p-3 text-purple-700">${r.factura_estimada_mes_cop}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
            </div>
          )}
        </main>
      </div>

      {/* WIDGET FLOTANTE MILE (INFERIOR DERECHA — ESTILO PORTAL EMCALI 2026) */}
      {!mileDrawerOpen && (
        <button
          type="button"
          onClick={() => setMileDrawerOpen(true)}
          className="fixed bottom-5 right-5 z-40 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white shadow-[0_10px_30px_rgba(45,82,17,0.35)] border-2 border-white/80 pl-2 pr-5 py-2 flex items-center gap-3 transition-all hover:scale-[1.02] cursor-pointer"
          aria-label="Abrir asistente virtual Mile"
        >
          <div className="relative shrink-0">
            <img
              src="/melva-avatar.jpg"
              alt="Melva, asistente virtual de EMCALI"
              className="h-11 w-11 rounded-full object-cover border-2 border-white shadow-xs"
            />
            <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-[#A3E635] ring-2 ring-[#579624]" />
          </div>
          <div className="text-left leading-tight">
            <div className="text-xs sm:text-sm font-extrabold tracking-tight">
              ¿En qué te puedo ayudar?
            </div>
            <div className="text-[11px] font-semibold text-[#EEF6E6]">
              Melva · Asistente Virtual EMCALI
            </div>
          </div>
        </button>
      )}

      {/* SLIDE-OVER DRAWER DE MILE (CHAT + VOZ MILE LIVE + HISTORIAL AISLADO) */}
      {mileDrawerOpen && (
        <aside
          className={`fixed bottom-4 right-4 z-50 flex flex-col bg-white rounded-3xl border border-[#DDE5D7] shadow-[0_18px_56px_rgba(20,27,18,0.24)] overflow-hidden transition-all duration-200 h-[86vh] max-h-[780px] ${
            mileDrawerExpanded
              ? "w-[calc(100vw-2rem)] sm:w-[680px]"
              : "w-[calc(100vw-2rem)] sm:w-[460px]"
          }`}
          aria-label="Asistente Virtual Mile"
        >
          {/* Cabecera Verde EMCALI del Drawer */}
          <div className="bg-[#579624] text-white px-4 py-3 flex items-center justify-between gap-2 shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="relative shrink-0">
                <img
                  src="/melva-avatar.jpg"
                  alt="Melva"
                  className="h-9 w-9 rounded-full object-cover border-2 border-white shadow-xs"
                />
                <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-[#A3E635] ring-2 ring-[#579624]" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-extrabold leading-tight truncate">
                  Melva · Asistente Virtual
                </div>
                <div className="text-[11px] text-[#EEF6E6] truncate">
                  {authRole === "manager"
                    ? "Modo Gerencial (20 Tools)"
                    : "Atención Ciudadana · Sync WhatsApp"}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={handleClearChat}
                disabled={messages.length === 0 || isStreaming}
                className="p-1.5 rounded-full hover:bg-white/15 text-white/90 hover:text-white disabled:opacity-40 cursor-pointer"
                title="Limpiar historial visible del chat"
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleCreateNewThread}
                className="p-1.5 rounded-full hover:bg-white/15 text-white/90 hover:text-white cursor-pointer"
                title="Nueva conversación"
              >
                <PlusCircle className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setMileDrawerExpanded((v) => !v)}
                className="hidden sm:inline-flex p-1.5 rounded-full hover:bg-white/15 text-white/90 hover:text-white cursor-pointer"
                title={mileDrawerExpanded ? "Contraer panel" : "Expandir panel"}
              >
                {mileDrawerExpanded ? (
                  <Minimize2 className="w-4 h-4" />
                ) : (
                  <Maximize2 className="w-4 h-4" />
                )}
              </button>
              <button
                type="button"
                onClick={() => setMileDrawerOpen(false)}
                className="p-1.5 rounded-full hover:bg-white/15 text-white/90 hover:text-white cursor-pointer"
                title="Cerrar asistente"
                aria-label="Cerrar asistente"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Barra de Voz Melva Live dentro del Drawer */}
          <div
            className={`px-3.5 py-2.5 border-b border-[#DDE5D7] space-y-2 shrink-0 ${
              liveSessionActive ? "bg-[#EEF6E6]" : "bg-[#F7FAF4]"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-1.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => toggleBrowserMicrophone(true)}
                  className={`px-3 py-1.5 rounded-full text-[11px] font-bold flex items-center gap-1.5 border transition cursor-pointer ${
                    liveSessionActive
                      ? "bg-[#579624] text-white border-[#477D1C]"
                      : isListeningMic && hotwordStandby
                      ? "bg-[#141B12] text-white border-[#141B12] animate-pulse"
                      : "bg-white hover:bg-[#EEF6E6] text-[#2D5211] border-[#CDE3B4]"
                  }`}
                >
                  {isListeningMic ? (
                    <MicOff className="w-3.5 h-3.5" />
                  ) : (
                    <Mic className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {liveSessionActive
                      ? "🟢 Melva Live (Pausar)"
                      : isListeningMic && hotwordStandby
                      ? 'Escuchando "Oye Melva"...'
                      : 'Voz ("Oye Melva")'}
                  </span>
                </button>

                {liveActivity === "speaking" && (
                  <button
                    type="button"
                    onClick={interruptSpeechBargeIn}
                    className="px-2.5 py-1 rounded-full bg-[#FFF4E8] hover:bg-orange-100 border border-[#F5820D]/40 text-[#B45309] text-[11px] font-bold cursor-pointer"
                  >
                    ✋ Parar
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => setTtsEnabled((v) => !v)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border flex items-center gap-1 cursor-pointer ${
                  ttsEnabled
                    ? "bg-[#EEF6E6] text-[#2D5211] border-[#CDE3B4]"
                    : "bg-white text-slate-500 border-[#DDE5D7]"
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

            {liveSessionActive && (
              <div className="px-2.5 py-1 rounded-full bg-white border border-[#CDE3B4] inline-flex items-center gap-2 text-[10px] font-bold">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#579624] opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#579624]"></span>
                </span>
                <span className="text-[#2D5211]">
                  {liveActivity === "thinking"
                    ? "Melva consultando..."
                    : liveActivity === "speaking"
                    ? "🔊 Melva respondiendo"
                    : "🎙️ Te escucho en vivo"}
                </span>
              </div>
            )}

            <div className="flex items-center gap-1.5">
              <input
                value={simulatedVoiceText}
                onChange={(e) => setSimulatedVoiceText(e.target.value)}
                placeholder='Simulador voz: "Oye Melva, tarifa estrato 3"'
                className="flex-1 px-3 py-1.5 rounded-full bg-white border border-[#DDE5D7] text-[11px] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
              <button
                type="button"
                onClick={() => handleVoiceCommandSubmit(simulatedVoiceText, true, true)}
                className="px-3 py-1.5 rounded-full bg-[#141B12] hover:bg-[#283324] text-white text-[11px] font-bold shrink-0 cursor-pointer"
              >
                {liveSessionActive ? "Enviar" : "Probar"}
              </button>
            </div>

            {interimTranscript && (
              <div className="text-[11px] text-[#2D5211] font-medium bg-[#EEF6E6] px-3 py-1 rounded-xl border border-[#CDE3B4]">
                🎙️ Escuchando: <em>"{interimTranscript}..."</em>
              </div>
            )}

            {voiceBanner && (
              <div className="text-[10px] text-[#475569] font-medium leading-snug">
                {voiceBanner}
              </div>
            )}
          </div>

          {/* Stream de Mensajes de Melva */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-white">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center py-8 px-3 text-[#5B6757]">
                <div className="h-14 w-14 rounded-2xl bg-[#EEF6E6] border border-[#CDE3B4] flex items-center justify-center mb-3 shadow-xs">
                  <Bot className="w-7 h-7 text-[#579624]" />
                </div>
                <span className="px-3 py-0.5 rounded-full bg-[#FACC15] text-[#141B12] text-[10px] font-extrabold mb-2">
                  EMCALI ¡Siempre Juntos! · 24/7
                </span>
                <h3 className="text-sm font-extrabold text-[#141B12]">
                  ¡Hola! Soy Melva, tu asistente virtual
                </h3>
                <p className="text-xs mt-1 text-[#5B6757] leading-relaxed">
                  Consúltame sobre tarifas, PQRS, fallas en tu barrio, cobertura de fibra óptica o
                  di <strong className="text-[#141B12]">"Oye Melva"</strong> para hablar por voz.
                </p>
              </div>
            ) : (
              messages.map((msg, i) => {
                const isLastStreamingAssistant =
                  msg.role === "assistant" && isStreaming && i === messages.length - 1;
                return (
                  <div
                    key={i}
                    className={`flex items-start gap-2 ${
                      msg.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    {msg.role === "assistant" && (
                      <div className="shrink-0 w-9 h-9 flex items-center justify-center mt-0.5">
                        <img
                          src="/melva-avatar.jpg"
                          alt="Melva"
                          className={`w-7 h-7 rounded-full object-cover border-2 ${
                            isLastStreamingAssistant
                              ? "border-[#579624] shadow-md eder-orbit"
                              : "border-[#CDE3B4]"
                          }`}
                        />
                      </div>
                    )}
                    <div
                      className={`max-w-[84%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed shadow-xs ${
                        msg.role === "user"
                          ? "bg-[#579624] text-white rounded-tr-sm whitespace-pre-wrap"
                          : "bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] rounded-tl-sm"
                      }`}
                    >
                      {msg.voiceHotword && (
                        <div className="text-[10px] font-bold uppercase tracking-wider text-[#EEF6E6] mb-1">
                          🎙️ {msg.voiceHotword}
                        </div>
                      )}
                      {isLastStreamingAssistant && !msg.content ? (
                        <span className="text-[#5B6757] italic">
                          Melva está generando la respuesta...
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

          {/* Barra de Envío + Preguntas Rápidas (Debajo del Input) */}
          <div className="p-3 border-t border-[#DDE5D7] bg-[#F7FAF4] space-y-2.5 shrink-0">
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
                placeholder="Escribe tu consulta para Melva..."
                className="flex-1 px-4 py-2.5 rounded-full bg-white border border-[#DDE5D7] text-xs text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
              <button
                type="submit"
                disabled={isStreaming || !question.trim()}
                className="px-4 py-2.5 rounded-full bg-[#579624] hover:bg-[#477D1C] disabled:opacity-50 text-white text-xs font-bold flex items-center gap-1.5 shadow-xs transition cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Enviar</span>
              </button>
            </form>

            {/* Sugerencias rápidas claramente vinculadas al chat */}
            <div className="space-y-1.5">
              <div className="text-[10px] font-bold text-[#477D1C] flex items-center gap-1">
                <CornerDownRight className="w-3 h-3 text-[#579624]" />
                <span>Preguntas rápidas (clic para enviar al chat):</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {quickCitizenTopics.map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => handleSendQuestion(item.q)}
                    disabled={isStreaming}
                    title={`Enviar al chat: "${item.q}"`}
                    className="px-2.5 py-1 rounded-full bg-white hover:bg-[#EEF6E6] border border-[#DDE5D7] hover:border-[#579624] text-[11px] font-semibold text-[#141B12] hover:text-[#2D5211] transition flex items-center gap-1 cursor-pointer disabled:opacity-50"
                  >
                    <span>{item.label}</span>
                    <Send className="w-2.5 h-2.5 text-[#579624]" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}
