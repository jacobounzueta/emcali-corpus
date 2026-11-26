import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Droplets,
  Info,
  Lock,
  LogOut,
  MapPin,
  Newspaper,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserCheck,
  UserPlus,
  Wifi,
  Wrench,
  Zap,
} from "lucide-react";
import {
  CaliMapPanel,
  type FailureHotspot,
  type MaintenancePoint,
} from "./CaliMapPanel";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

interface AuthSession {
  authenticated: boolean;
  token?: string;
  username?: string;
  display_name: string;
  role: "citizen" | "manager";
}

interface UmapPoint {
  id: string;
  kind: string;
  section: string;
  label: string;
  snippet: string;
  x: number;
  y: number;
}

interface UmapResponse {
  method: string;
  metrics: {
    total_points: number;
    corpus_and_news_points: number;
    overlay_queries_and_tickets: number;
    silhouette_score: number;
    clusters_detected: number;
  };
  section_counts: Record<string, number>;
  points: UmapPoint[];
}

interface ToolCatalogItem {
  index: number;
  name: string;
  description: string;
  required_role: "citizen" | "manager";
  hitl_protected: boolean;
}

const UMAP_SECTION_COLORS: Record<string, string> = {
  energia: "#f59e0b",
  acueducto: "#0284c7",
  telco: "#10b981",
  telco_fibra: "#10b981",
  noticias: "#ec4899",
  sostenibilidad: "#22c55e",
  transparencia: "#6366f1",
  "proteccion-de-datos-personales": "#8b5cf6",
  "atencion-y-servicio-a-la-ciudadania": "#14b8a6",
  about: "#64748b",
  otros: "#94a3b8",
};

export const M3OperationsSuite: React.FC = () => {
  const [subTab, setSubTab] = useState<"map" | "pqrs" | "news" | "umap_tools" | "iam" | "auth">(
    "map"
  );
  const [session, setSession] = useState<AuthSession>(() => {
    try {
      const saved = localStorage.getItem("emcali_auth_session");
      if (saved) return JSON.parse(saved);
    } catch {
      // ignore
    }
    return {
      authenticated: false,
      role: "citizen",
      display_name: "Ciudadano (Acceso Público)",
    };
  });
  const [loginUser, setLoginUser] = useState("");
  const [loginPass, setLoginPass] = useState("");
  const [regForm, setRegForm] = useState({
    username: "",
    display_name: "",
    password: "",
    phone_e164: "",
  });
  const [showHotspotInfo, setShowHotspotInfo] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string>("");

  // Map & Ops state
  const [serviceFilter, setServiceFilter] = useState("todos");
  const [maintenances, setMaintenances] = useState<MaintenancePoint[]>([]);
  const [hotspots, setHotspots] = useState<FailureHotspot[]>([]);
  const [pqrsList, setPqrsList] = useState<any[]>([]);
  const [pqrsEdits, setPqrsEdits] = useState<Record<string, { estado: string; notas: string }>>({});
  const [failureReportsList, setFailureReportsList] = useState<any[]>([]);
  const [failureEdits, setFailureEdits] = useState<
    Record<string, { estado: string; notas: string }>
  >({});
  const [newsList, setNewsList] = useState<any[]>([]);
  const [refreshingNews, setRefreshingNews] = useState(false);
  const [newsletterDigest, setNewsletterDigest] = useState<string>("");
  const [toolsCatalog, setToolsCatalog] = useState<ToolCatalogItem[]>([]);
  const [hitlPending, setHitlPending] = useState<any[]>([]);
  const [umapData, setUmapData] = useState<UmapResponse | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<UmapPoint | null>(null);
  const [loadingUmap, setLoadingUmap] = useState(false);

  // Forms state
  const [pqrsForm, setPqrsForm] = useState({
    tipo: "Reclamo",
    servicio: "energia",
    identificador_tipo: "contrato",
    identificador_valor: "",
    nombre_ciudadano: "",
    barrio: "San Fernando",
    descripcion: "",
    telefono_e164: "",
  });
  const [failForm, setFailForm] = useState({
    servicio: "acueducto",
    identificador_tipo: "cedula",
    identificador_valor: "",
    nombre_ciudadano: "",
    barrio: "Ciudad Jardín",
    direccion: "",
    descripcion: "",
  });
  const [maintForm, setMaintForm] = useState({
    titulo: "",
    servicio: "acueducto",
    barrio: "San Fernando",
    descripcion: "",
    brigada_asignada: "Brigada EMCALI Sur-04",
  });
  const [subForm, setSubForm] = useState({
    contacto: "+57",
    nombre: "",
    barrio_interes: "Todos",
  });
  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [waAllowlist, setWaAllowlist] = useState<string[]>([]);
  const [newWaPhone, setNewWaPhone] = useState("+57");
  const [newUserForm, setNewUserForm] = useState({
    username: "",
    display_name: "",
    role: "manager" as "citizen" | "manager",
    password: "",
    phone_e164: "",
    department: "Operaciones EMCALI",
  });

  const isManager = session.role === "manager";
  const authHeaders = useCallback((): Record<string, string> => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (session.token) h["Authorization"] = `Bearer ${session.token}`;
    return h;
  }, [session.token]);

  const loadMapAndOps = useCallback(async () => {
    try {
      const [mapRes, pqrsRes, failRes, hitlRes] = await Promise.all([
        fetch(`${API_BASE}/api/map/overview?servicio=${serviceFilter}`),
        fetch(`${API_BASE}/api/pqrs`),
        fetch(`${API_BASE}/api/failures`),
        fetch(`${API_BASE}/api/hitl/pending`),
      ]);
      if (mapRes.ok) {
        const d = await mapRes.json();
        setMaintenances(d.maintenances || []);
        setHotspots(d.failure_hotspots || []);
      }
      if (pqrsRes.ok) {
        const d = await pqrsRes.json();
        setPqrsList(d.items || []);
      }
      if (failRes.ok) {
        const d = await failRes.json();
        setFailureReportsList(d.items || []);
      }
      if (hitlRes.ok) {
        const d = await hitlRes.json();
        setHitlPending(d.items || []);
      }
    } catch {
      // silent
    }
  }, [serviceFilter]);

  const loadNewsAndDigest = useCallback(async (forceLiveRefresh = false) => {
    try {
      if (forceLiveRefresh) setRefreshingNews(true);
      const [nRes, dRes] = await Promise.all([
        fetch(`${API_BASE}/api/news?limit=25${forceLiveRefresh ? "&refresh=true" : ""}`),
        fetch(`${API_BASE}/api/newsletter/digest`),
      ]);
      if (nRes.ok) {
        const d = await nRes.json();
        setNewsList(d.items || []);
        if (forceLiveRefresh) {
          const syncedCount = d.sync?.live_news_ingested ?? 0;
          setStatusMsg(
            syncedCount > 0
              ? `✅ Noticias actualizadas en vivo desde EMCALI (${syncedCount} artículos sincronizados).`
              : "✅ Noticias actualizadas."
          );
          loadMapAndOps();
        }
      }
      if (dRes.ok) {
        const d = await dRes.json();
        setNewsletterDigest(d.markdown_digest || "");
      }
    } catch {
      if (forceLiveRefresh) {
        setStatusMsg("⚠️ No fue posible conectar con el feed en vivo de EMCALI en este momento.");
      }
    } finally {
      if (forceLiveRefresh) setRefreshingNews(false);
    }
  }, [loadMapAndOps]);

  const loadCatalogAndUmap = useCallback(async (refreshUmap = false) => {
    try {
      setLoadingUmap(true);
      const [catRes, umapRes] = await Promise.all([
        fetch(`${API_BASE}/api/tools/catalog`),
        fetch(`${API_BASE}/api/evaluation/umap?refresh=${refreshUmap}`),
      ]);
      if (catRes.ok) {
        const d = await catRes.json();
        setToolsCatalog(d.tools || []);
      }
      if (umapRes.ok) {
        setUmapData(await umapRes.json());
      }
    } finally {
      setLoadingUmap(false);
    }
  }, []);

  const loadAdminIam = useCallback(async () => {
    if (!session.token || session.role !== "manager") return;
    try {
      const [uRes, waRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/users`, { headers: authHeaders() }),
        fetch(`${API_BASE}/api/admin/whatsapp/allowlist`, { headers: authHeaders() }),
      ]);
      if (uRes.ok) {
        const d = await uRes.json();
        setAdminUsers(d.items || []);
      }
      if (waRes.ok) {
        const d = await waRes.json();
        setWaAllowlist(d.allowFrom || []);
      }
    } catch {
      // silent
    }
  }, [session.token, session.role, authHeaders]);

  useEffect(() => {
    loadMapAndOps();
    const timer = window.setInterval(() => {
      loadMapAndOps();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [loadMapAndOps]);

  useEffect(() => {
    if (subTab === "news") loadNewsAndDigest();
    if (subTab === "umap_tools" && !umapData) loadCatalogAndUmap(false);
    if (subTab === "iam" && isManager) loadAdminIam();
  }, [subTab, loadNewsAndDigest, loadCatalogAndUmap, umapData, isManager, loadAdminIam]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: loginUser, password: loginPass }),
    });
    if (!res.ok) {
      setStatusMsg("❌ Credenciales inválidas.");
      return;
    }
    const data = await res.json();
    const nextSession: AuthSession = {
      authenticated: true,
      token: data.token,
      username: data.username,
      display_name: data.display_name,
      role: data.role,
    };
    setSession(nextSession);
    localStorage.setItem("emcali_auth_session", JSON.stringify(nextSession));
    window.dispatchEvent(new Event("emcali-auth-changed"));
    setLoginUser("");
    setLoginPass("");
    setSubTab("map");
    setStatusMsg(`✅ Sesión activa: ${data.display_name} (${data.role.toUpperCase()})`);
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(regForm),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ Error en registro: ${data.detail}`);
      return;
    }
    const nextSession: AuthSession = {
      authenticated: true,
      token: data.token,
      username: data.username,
      display_name: data.display_name,
      role: data.role,
    };
    setSession(nextSession);
    localStorage.setItem("emcali_auth_session", JSON.stringify(nextSession));
    window.dispatchEvent(new Event("emcali-auth-changed"));
    setRegForm({ username: "", display_name: "", password: "", phone_e164: "" });
    setSubTab("map");
    setStatusMsg(`🎉 Cuenta creada e iniciada: ${data.display_name} (${data.role.toUpperCase()})`);
  };

  const handleLogout = () => {
    const guest: AuthSession = {
      authenticated: false,
      role: "citizen",
      display_name: "Ciudadano (Acceso Público)",
    };
    setSession(guest);
    localStorage.removeItem("emcali_auth_session");
    window.dispatchEvent(new Event("emcali-auth-changed"));
    if (subTab === "iam") setSubTab("map");
    setStatusMsg("🔄 Sesión cerrada. Modo Ciudadano público activo.");
  };

  const handleCreatePqrs = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/pqrs`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(pqrsForm),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ Error PQRS: ${JSON.stringify(data.detail)}`);
      return;
    }
    setStatusMsg(`✅ PQRS radicada: ${data.ticket.radicado_id}`);
    setPqrsForm({ ...pqrsForm, identificador_valor: "", descripcion: "" });
    loadMapAndOps();
  };

  const handleUpdatePqrsStatus = async (
    radicadoId: string,
    fallbackEstado: string,
    fallbackNotas: string
  ) => {
    const draft = pqrsEdits[radicadoId] || { estado: fallbackEstado, notas: fallbackNotas };
    const res = await fetch(`${API_BASE}/api/pqrs/${encodeURIComponent(radicadoId)}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({
        nuevo_estado: draft.estado,
        notas_gestion: draft.notas,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ Error al actualizar PQRS: ${data.detail || "Sin permisos"}`);
      return;
    }
    setStatusMsg(
      data.whatsapp_notified
        ? `✅ Radicado ${radicadoId} actualizado a "${data.ticket.estado}" y notificado por WhatsApp.`
        : `✅ Radicado ${radicadoId} actualizado a "${data.ticket.estado}".`
    );
    loadMapAndOps();
  };

  const handleUpdateFailureStatus = async (
    reporteId: string,
    fallbackEstado: string,
    fallbackNotas: string
  ) => {
    const draft = failureEdits[reporteId] || { estado: fallbackEstado, notas: fallbackNotas };
    const res = await fetch(`${API_BASE}/api/failures/${encodeURIComponent(reporteId)}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({
        nuevo_estado: draft.estado,
        notas_gestion: draft.notas,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ Error al actualizar reporte de falla: ${data.detail || "Sin permisos"}`);
      return;
    }
    setStatusMsg(
      data.whatsapp_notified
        ? `✅ Reporte ${reporteId} actualizado a "${data.report.estado}" y respuesta enviada por WhatsApp.`
        : `✅ Reporte ${reporteId} actualizado a "${data.report.estado}".`
    );
    loadMapAndOps();
  };

  const handleCloseMaintenance = async (maintenanceId: string) => {
    const res = await fetch(
      `${API_BASE}/api/maintenances/${encodeURIComponent(maintenanceId)}/close`,
      {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({ notas_cierre: "Falla resuelta y verificada en terreno." }),
      }
    );
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ Error al cerrar mantenimiento: ${data.detail || "Sin permisos"}`);
      return;
    }
    setStatusMsg(`✅ Mantenimiento ${maintenanceId} finalizado y hotspot resuelto.`);
    loadMapAndOps();
  };

  const handleCreateFailure = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/failures`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(failForm),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ Error reporte de falla: ${JSON.stringify(data.detail)}`);
      return;
    }
    setStatusMsg(
      `⚠️ Falla ${data.report.reporte_id} registrada en ${data.report.barrio}. Mapa y hotspots actualizados.`
    );
    setFailForm({ ...failForm, identificador_valor: "", descripcion: "" });
    loadMapAndOps();
  };

  const handleActivateMaintenance = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/maintenances`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(maintForm),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`🛡️ Bloqueado por RBAC: ${data.detail}`);
      return;
    }
    setStatusMsg(`🔧 Mantenimiento activado en el mapa: ${data.maintenance.mantenimiento_id}`);
    setMaintForm({ ...maintForm, titulo: "", descripcion: "" });
    loadMapAndOps();
  };

  const handleDispatchHotspot = async (h: FailureHotspot) => {
    const res = await fetch(`${API_BASE}/api/maintenances/dispatch`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        barrio: h.barrio,
        servicio: h.servicio,
        brigada_asignada: `Brigada Respuesta Rápida (${h.servicio.toUpperCase()})`,
        notas: `Despacho automático por ${h.report_count} reportes ciudadanos en ${h.barrio}.`,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`🛡️ ${data.detail}`);
      return;
    }
    const waQueued = data.maintenance.whatsapp_notifications_queued ?? 0;
    setStatusMsg(
      `🚑 Brigada despachada a ${h.barrio} (${data.maintenance.linked_failure_reports} fallas vinculadas · ${waQueued} aviso(s) WhatsApp enviados).`
    );
    loadMapAndOps();
  };

  const handleResolveHitl = async (actionId: string, approved: boolean) => {
    const res = await fetch(`${API_BASE}/api/hitl/${actionId}/resolve`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ approved }),
    });
    if (res.ok) {
      setStatusMsg(`✅ Acción HITL ${actionId} ${approved ? "aprobada y ejecutada" : "rechazada"}.`);
      loadMapAndOps();
    }
  };

  const handleSubscribeNewsletter = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/newsletter/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...subForm, canal: "whatsapp", frecuencia: "diaria" }),
    });
    if (res.ok) {
      setStatusMsg(`📰 Suscripción confirmada al boletín diario OpenClaw (${subForm.contacto}).`);
    }
  };

  const handleAddWaPhone = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/admin/whatsapp/allowlist`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ phone_e164: newWaPhone.trim() }),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ ${data.detail}`);
      return;
    }
    setWaAllowlist(data.allowFrom || []);
    setNewWaPhone("+57");
    setStatusMsg(`✅ Número ${data.phone_e164} agregado al allowlist de WhatsApp (hot-reload activo).`);
  };

  const handleRemoveWaPhone = async (phone: string) => {
    const res = await fetch(
      `${API_BASE}/api/admin/whatsapp/allowlist/${encodeURIComponent(phone)}`,
      { method: "DELETE", headers: authHeaders() }
    );
    if (res.ok) {
      const data = await res.json();
      setWaAllowlist(data.allowFrom || []);
      setStatusMsg(`🗑️ Número ${phone} removido del allowlist de WhatsApp.`);
    }
  };

  const handleSaveUser = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/api/admin/users`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ...newUserForm, active: true }),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatusMsg(`❌ ${data.detail}`);
      return;
    }
    setStatusMsg(`✅ Usuario RBAC '${data.user.username}' (${data.user.role}) guardado.`);
    setNewUserForm({
      username: "",
      display_name: "",
      role: "manager",
      password: "",
      phone_e164: "",
      department: "Operaciones EMCALI",
    });
    loadAdminIam();
  };

  const handleToggleUserActive = async (u: any) => {
    const res = await fetch(`${API_BASE}/api/admin/users`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        username: u.username,
        display_name: u.display_name,
        role: u.role,
        phone_e164: u.phone_e164,
        department: u.department,
        active: !u.active,
      }),
    });
    if (res.ok) {
      setStatusMsg(`🔄 Usuario '${u.username}' ${!u.active ? "activado" : "desactivado"}.`);
      loadAdminIam();
    }
  };

  // Escalado de coordenadas UMAP para el SVG interactivo
  const renderUmapSvg = () => {
    if (!umapData || umapData.points.length === 0) return null;
    const xs = umapData.points.map((p) => p.x);
    const ys = umapData.points.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const pad = 28;
    const W = 680;
    const H = 360;
    const scaleX = (x: number) =>
      pad + ((x - minX) / Math.max(1e-6, maxX - minX)) * (W - 2 * pad);
    const scaleY = (y: number) =>
      H - pad - ((y - minY) / Math.max(1e-6, maxY - minY)) * (H - 2 * pad);

    return (
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-[340px] bg-slate-950 rounded-xl border border-slate-800"
      >
        {umapData.points.map((pt) => {
          const cx = scaleX(pt.x);
          const cy = scaleY(pt.y);
          const isOverlay = pt.kind !== "corpus_chunk" && pt.kind !== "news_article";
          const fill = UMAP_SECTION_COLORS[pt.section] || "#38bdf8";
          return (
            <circle
              key={`${pt.kind}-${pt.id}`}
              cx={cx}
              cy={cy}
              r={isOverlay ? 6 : 4}
              fill={isOverlay ? "#ffffff" : fill}
              stroke={isOverlay ? "#ef4444" : "#0f172a"}
              strokeWidth={isOverlay ? 2 : 0.7}
              opacity={isOverlay ? 0.98 : 0.8}
              className="cursor-pointer transition-all"
              onMouseEnter={() => setHoveredPoint(pt)}
            />
          );
        })}
      </svg>
    );
  };

  return (
    <main className="max-w-[1440px] w-full mx-auto px-4 sm:px-6 py-6 flex-1 space-y-5">
      {/* Encabezado Editorial EMCALI 2026 + Barra de Sesión RBAC */}
      <section className="bg-white rounded-3xl border border-[#DDE5D7] shadow-[0_2px_12px_rgba(20,27,18,0.05)] p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-semibold text-[#477D1C]">
            Portal Operativo EMCALI ¡Siempre Juntos!
          </div>
          <div className="w-10 h-0.5 bg-[#579624] rounded-full my-1.5" />
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight text-[#141B12]">
              Reparaciones, Mantenimientos y Gestión
            </h2>
            <span
              className={`px-3 py-1 rounded-full text-[11px] font-bold flex items-center gap-1.5 border ${
                isManager
                  ? "bg-[#FACC15] text-[#141B12] border-[#E5B800]"
                  : "bg-[#EEF6E6] text-[#2D5211] border-[#CDE3B4]"
              }`}
            >
              {isManager ? <ShieldCheck className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
              {isManager ? "MODO GESTIÓN EMCALI (20/20 Tools)" : "MODO CIUDADANO (16/20 Tools · RBAC)"}
            </span>
          </div>
          <p className="text-xs text-[#5B6757] mt-1">{session.display_name}</p>
        </div>

        {session.authenticated ? (
          <button
            onClick={handleLogout}
            className="px-4 py-2 rounded-full bg-[#141B12] hover:bg-[#283324] text-white text-xs font-bold flex items-center gap-1.5 shadow-xs transition cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" /> Cerrar Sesión
          </button>
        ) : (
          <button
            onClick={() => setSubTab("auth")}
            className="px-4 py-2 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white text-xs font-bold flex items-center gap-1.5 shadow-xs transition cursor-pointer"
          >
            <Lock className="w-3.5 h-3.5" /> Iniciar Sesión / Registrarse ↗
          </button>
        )}
      </section>

      {statusMsg && (
        <div className="bg-[#EEF6E6] border border-[#CDE3B4] text-[#2D5211] px-4 py-2.5 rounded-2xl text-xs font-semibold flex items-center justify-between shadow-xs">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg("")} className="text-[#477D1C] hover:text-[#2D5211] underline cursor-pointer">
            Cerrar
          </button>
        </div>
      )}

      {/* Sub-navegación M3 estilo pills EMCALI 2026 (IAM oculto si no es manager; Login/Registro visible si no autenticado) */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: "map", label: "🗺️ Mapa Cali, Mantenimientos & Brigadas" },
          { id: "pqrs", label: "📝 PQRS & Reporte de Fallas" },
          { id: "news", label: "📰 Noticias & Boletín OpenClaw" },
          { id: "umap_tools", label: "🧬 UMAP 2D, 20 Tools & HITL" },
          ...(isManager ? [{ id: "iam", label: "🔐 IAM Usuarios & WhatsApp Allowlist" }] : []),
          ...(!session.authenticated ? [{ id: "auth", label: "🔑 Iniciar Sesión / Registro" }] : []),
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id as any)}
            className={`px-4 py-2 rounded-full text-xs font-bold border transition cursor-pointer ${
              subTab === t.id
                ? "bg-[#579624] text-white border-[#477D1C] shadow-xs"
                : "bg-white text-[#1E293B] border-[#DDE5D7] hover:border-[#579624] hover:bg-[#EEF6E6] hover:text-[#2D5211]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* SUB-TAB 1: MAPA INTERACTIVO CALI + HOTSPOTS + ACTIVACIÓN GESTIÓN */}
      {subTab === "map" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2.5">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-sm font-extrabold text-[#141B12] flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-[#579624]" /> Mapa Operativo de Cali — Mantenimientos y Alertas de Fallas
                </h2>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#EEF6E6] border border-[#CDE3B4] text-[#2D5211] text-[10px] font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#579624] animate-pulse" />
                  En vivo (4s)
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  {
                    id: "todos",
                    label: "Todos",
                    inactive: "bg-[#F3F6F1] text-[#1E293B] border-[#DDE5D7] hover:bg-[#E7EDE3]",
                    active: "bg-[#141B12] text-white border-[#141B12] shadow-xs",
                  },
                  {
                    id: "energia",
                    label: "Energía",
                    inactive: "bg-yellow-50 text-yellow-950 border-yellow-300 hover:bg-yellow-100",
                    active: "bg-[#FACC15] text-[#141B12] border-[#D9AA00] shadow-xs",
                  },
                  {
                    id: "acueducto",
                    label: "Acueducto",
                    inactive: "bg-sky-50 text-sky-900 border-sky-300 hover:bg-sky-100",
                    active: "bg-sky-600 text-white border-sky-700 shadow-xs",
                  },
                  {
                    id: "alcantarillado",
                    label: "Alcantarillado",
                    inactive: "bg-teal-50 text-teal-900 border-teal-300 hover:bg-teal-100",
                    active: "bg-teal-600 text-white border-teal-700 shadow-xs",
                  },
                  {
                    id: "telco_fibra",
                    label: "Telco Fibra",
                    inactive: "bg-purple-50 text-purple-900 border-purple-300 hover:bg-purple-100",
                    active: "bg-purple-600 text-white border-purple-700 shadow-xs",
                  },
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setServiceFilter(f.id)}
                    className={`px-3 py-1 rounded-full text-[11px] font-bold border transition cursor-pointer ${
                      serviceFilter === f.id ? f.active : f.inactive
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
            <CaliMapPanel
              maintenances={maintenances}
              hotspots={hotspots}
              isManager={isManager}
              onSelectHotspotForDispatch={handleDispatchHotspot}
            />
          </div>

          <div className="space-y-4">
            {/* Hotspots de Fallas para Asignación de Brigadas */}
            <div className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs font-extrabold text-rose-700 flex items-center gap-1.5 uppercase tracking-wide">
                  <AlertTriangle className="w-4 h-4" /> Hotspots de Fallas Ciudadanas ({hotspots.length})
                </h3>
                <button
                  type="button"
                  onClick={() => setShowHotspotInfo((prev) => !prev)}
                  title="¿Qué es un Hotspot de Falla Ciudadana?"
                  className="p-1.5 rounded-full text-rose-700 hover:bg-rose-100 transition cursor-pointer"
                  aria-label="Información sobre hotspots de fallas ciudadanas"
                >
                  <Info className="w-4 h-4" />
                </button>
              </div>
              {showHotspotInfo && (
                <div className="p-3 rounded-2xl bg-[#F7FAF4] border border-[#DDE5D7] text-[11px] text-[#1E293B] leading-relaxed">
                  <b>¿Qué es un Hotspot?</b> Agrupa automáticamente los reportes de fallas
                  enviados por ciudadanos (WhatsApp o Web) por <b>barrio y servicio</b>:
                  <ul className="list-disc pl-4 mt-1 space-y-0.5">
                    <li><b>1 reporte:</b> seguimiento preventivo.</li>
                    <li><b>2–3 reportes:</b> alerta de acumulación en el sector.</li>
                    <li><b>4+ reportes:</b> crítico — brigada recomendada.</li>
                  </ul>
                  <div className="mt-1">
                    Gestión EMCALI usa estas alertas para <b>priorizar y despachar brigadas</b> y
                    notificar automáticamente por WhatsApp a los afectados.
                  </div>
                </div>
              )}
              {hotspots.length === 0 ? (
                <p className="text-xs text-[#5B6757]">
                  Sin alertas de fallas abiertas. Reporta una falla en la pestaña PQRS &amp; Fallas para ver el agrupamiento en vivo.
                </p>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto pr-0.5">
                  {hotspots.map((h) => (
                    <div
                      key={`${h.barrio}-${h.servicio}`}
                      className="p-3 rounded-2xl bg-rose-50/70 border border-rose-200 text-xs flex items-center justify-between gap-2"
                    >
                      <div>
                        <div className="font-bold text-[#141B12]">
                          {h.barrio} · <span className="uppercase text-rose-700">{h.servicio}</span>
                        </div>
                        <div className="text-[11px] text-[#475569]">
                          {h.report_count} reporte(s) · {h.severity_label}
                        </div>
                        <div className="text-[10px] text-[#5B6757]">
                          🕒 {h.latest_report_at ? h.latest_report_at.replace("T", " ").slice(0, 16) : "Reciente"}
                        </div>
                      </div>
                      {isManager &&
                        ((h as any).crew_dispatched ? (
                          <div className="flex flex-col items-end gap-1 shrink-0">
                            <span className="px-2.5 py-0.5 rounded-full bg-[#EEF6E6] border border-[#CDE3B4] text-[#2D5211] text-[10px] font-bold">
                              🚑 Brigada en sitio ({(h as any).assigned_maintenance_id})
                            </span>
                            <button
                              onClick={() =>
                                handleCloseMaintenance((h as any).assigned_maintenance_id)
                              }
                              className="px-3 py-1 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white text-[10px] font-bold cursor-pointer transition"
                            >
                              ✅ Marcar Resuelto
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => handleDispatchHotspot(h)}
                            className="px-3 py-1.5 rounded-full bg-[#F5820D] hover:bg-[#DC7006] text-white text-[11px] font-bold shrink-0 cursor-pointer transition"
                          >
                            🚑 Despachar Brigada
                          </button>
                        ))}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Activar Nuevo Punto de Mantenimiento (Solo Gestión EMCALI) */}
            <div className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs font-extrabold text-[#141B12] flex items-center gap-1.5 uppercase tracking-wide">
                  <Wrench className="w-4 h-4 text-[#579624]" /> Activar Punto de Mantenimiento
                </h3>
                <span className="px-2.5 py-0.5 rounded-full bg-[#FACC15] text-[#141B12] text-[10px] font-extrabold">
                  Reparaciones
                </span>
              </div>
              {!isManager ? (
                <div className="p-3.5 rounded-2xl bg-[#FFF4E8] border border-[#F5820D]/30 text-xs text-[#9A3412]">
                  🛡️ <b>RBAC (`tools.deny`):</b> Inicia sesión en modo <b>Gestión EMCALI</b> para activar mantenimientos o despachar brigadas en el mapa.
                </div>
              ) : (
                <form onSubmit={handleActivateMaintenance} className="space-y-2.5 text-xs">
                  <input
                    required
                    value={maintForm.titulo}
                    onChange={(e) => setMaintForm({ ...maintForm, titulo: e.target.value })}
                    placeholder="Título del mantenimiento"
                    className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      value={maintForm.servicio}
                      onChange={(e) => setMaintForm({ ...maintForm, servicio: e.target.value })}
                      className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                    >
                      <option value="acueducto">Acueducto</option>
                      <option value="energia">Energía</option>
                      <option value="alcantarillado">Alcantarillado</option>
                      <option value="telco_fibra">Telco Fibra</option>
                    </select>
                    <input
                      required
                      value={maintForm.barrio}
                      onChange={(e) => setMaintForm({ ...maintForm, barrio: e.target.value })}
                      placeholder="Barrio (ej. Granada)"
                      className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                    />
                  </div>
                  <input
                    value={maintForm.brigada_asignada}
                    onChange={(e) =>
                      setMaintForm({ ...maintForm, brigada_asignada: e.target.value })
                    }
                    placeholder="Brigada asignada"
                    className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <textarea
                    required
                    rows={2}
                    value={maintForm.descripcion}
                    onChange={(e) => setMaintForm({ ...maintForm, descripcion: e.target.value })}
                    placeholder="Descripción técnica de la intervención"
                    className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <button
                    type="submit"
                    className="w-full py-2.5 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white font-bold shadow-xs transition cursor-pointer"
                  >
                    + Activar en Mapa de Cali
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: PQRS & REPORTE DE FALLAS */}
      {subTab === "pqrs" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <form
            onSubmit={handleCreatePqrs}
            className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3 text-xs"
          >
            <div>
              <div className="text-[11px] font-semibold text-[#477D1C]">Atención Formal</div>
              <div className="w-8 h-0.5 bg-[#579624] rounded-full my-1" />
              <h3 className="text-base font-extrabold tracking-tight text-[#141B12]">
                📝 Radicar PQRS (Por Contrato o por Cédula si no es cliente)
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <select
                value={pqrsForm.tipo}
                onChange={(e) => setPqrsForm({ ...pqrsForm, tipo: e.target.value })}
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              >
                <option>Petición</option>
                <option>Queja</option>
                <option>Reclamo</option>
                <option>Sugerencia</option>
              </select>
              <select
                value={pqrsForm.servicio}
                onChange={(e) => setPqrsForm({ ...pqrsForm, servicio: e.target.value })}
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              >
                <option value="energia">Energía</option>
                <option value="acueducto">Acueducto</option>
                <option value="alcantarillado">Alcantarillado</option>
                <option value="telco_fibra">Telco Fibra</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <select
                value={pqrsForm.identificador_tipo}
                onChange={(e) => setPqrsForm({ ...pqrsForm, identificador_tipo: e.target.value })}
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              >
                <option value="contrato">Cliente — Número de Contrato</option>
                <option value="cedula">No Cliente — Cédula</option>
              </select>
              <input
                required
                value={pqrsForm.identificador_valor}
                onChange={(e) => setPqrsForm({ ...pqrsForm, identificador_valor: e.target.value })}
                placeholder="Número (mín. 5 dígitos)"
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <input
                required
                value={pqrsForm.nombre_ciudadano}
                onChange={(e) => setPqrsForm({ ...pqrsForm, nombre_ciudadano: e.target.value })}
                placeholder="Nombre completo"
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
              <input
                required
                value={pqrsForm.barrio}
                onChange={(e) => setPqrsForm({ ...pqrsForm, barrio: e.target.value })}
                placeholder="Barrio de Cali"
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
            </div>
            <textarea
              required
              rows={2}
              value={pqrsForm.descripcion}
              onChange={(e) => setPqrsForm({ ...pqrsForm, descripcion: e.target.value })}
              placeholder="Describe tu petición, queja, reclamo o sugerencia..."
              className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
            />
            <button
              type="submit"
              className="w-full py-2.5 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white font-bold shadow-xs transition cursor-pointer"
            >
              Radicar PQRS en SQLite
            </button>
          </form>

          <form
            onSubmit={handleCreateFailure}
            className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3 text-xs"
          >
            <div>
              <div className="text-[11px] font-semibold text-[#DC7006]">Alerta Ciudadana</div>
              <div className="w-8 h-0.5 bg-[#F5820D] rounded-full my-1" />
              <h3 className="text-base font-extrabold tracking-tight text-[#141B12]">
                ⚠️ Reportar Falla de Servicio (Georreferencia y Alerta Brigadas)
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <select
                value={failForm.servicio}
                onChange={(e) => setFailForm({ ...failForm, servicio: e.target.value })}
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              >
                <option value="acueducto">Acueducto</option>
                <option value="energia">Energía</option>
                <option value="alcantarillado">Alcantarillado</option>
                <option value="telco_fibra">Telco Fibra</option>
              </select>
              <input
                required
                value={failForm.barrio}
                onChange={(e) => setFailForm({ ...failForm, barrio: e.target.value })}
                placeholder="Barrio afectado (ej. Ciudad Jardín)"
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <select
                value={failForm.identificador_tipo}
                onChange={(e) => setFailForm({ ...failForm, identificador_tipo: e.target.value })}
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              >
                <option value="contrato">Cliente — Contrato</option>
                <option value="cedula">No Cliente — Cédula</option>
              </select>
              <input
                required
                value={failForm.identificador_valor}
                onChange={(e) => setFailForm({ ...failForm, identificador_valor: e.target.value })}
                placeholder="Número de contrato o cédula"
                className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
            </div>
            <input
              value={failForm.direccion}
              onChange={(e) => setFailForm({ ...failForm, direccion: e.target.value })}
              placeholder="Dirección o referencia (opcional)"
              className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
            />
            <textarea
              required
              rows={2}
              value={failForm.descripcion}
              onChange={(e) => setFailForm({ ...failForm, descripcion: e.target.value })}
              placeholder="Describe la falla (ej. sin energía, fuga de agua, corte de fibra)..."
              className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
            />
            <button
              type="submit"
              className="w-full py-2.5 rounded-full bg-[#F5820D] hover:bg-[#DC7006] text-white font-bold shadow-xs transition cursor-pointer"
            >
              Reportar Falla en Mapa de Cali
            </button>
          </form>

          {/* Listado reciente de PQRS */}
          <div className="lg:col-span-2 bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
            <h3 className="text-xs font-extrabold text-[#141B12] uppercase tracking-wider mb-3">
              Radicados PQRS Almacenados ({pqrsList.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-[#F3F6F1] text-[#475569] uppercase text-[11px] font-bold">
                  <tr>
                    <th className="p-2.5">Radicado</th>
                    <th className="p-2.5">Tipo / Servicio</th>
                    <th className="p-2.5">Identificación</th>
                    <th className="p-2.5">Barrio</th>
                    <th className="p-2.5">Estado</th>
                    {isManager && <th className="p-2.5">Gestión EMCALI (Manager)</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E7EDE3]">
                  {pqrsList.slice(0, 15).map((p) => {
                    const draft = pqrsEdits[p.radicado_id] || {
                      estado: p.estado,
                      notas: p.notas_gestion || "",
                    };
                    return (
                      <tr key={p.radicado_id} className="hover:bg-[#F7FAF4]">
                        <td className="p-2.5 font-mono font-bold text-[#141B12]">{p.radicado_id}</td>
                        <td className="p-2.5 text-[#1E293B]">
                          {p.tipo} · <span className="uppercase font-semibold">{p.servicio}</span>
                        </td>
                        <td className="p-2.5 text-[#1E293B]">
                          {p.identificador_tipo}: <b>{p.identificador_valor}</b>
                        </td>
                        <td className="p-2.5 text-[#1E293B]">{p.barrio}</td>
                        <td className="p-2.5">
                          <span className="px-2.5 py-0.5 rounded-full bg-[#EEF6E6] border border-[#CDE3B4] text-[#2D5211] font-bold">
                            {p.estado}
                          </span>
                          {p.notas_gestion && (
                            <p className="text-[10px] text-[#5B6757] mt-0.5 max-w-[160px] truncate" title={p.notas_gestion}>
                              {p.notas_gestion}
                            </p>
                          )}
                        </td>
                        {isManager && (
                          <td className="p-2.5">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <select
                                value={draft.estado}
                                onChange={(e) =>
                                  setPqrsEdits((prev) => ({
                                    ...prev,
                                    [p.radicado_id]: { ...draft, estado: e.target.value },
                                  }))
                                }
                                className="rounded-lg border border-[#DDE5D7] px-2 py-1 text-[11px] bg-white focus:outline-none focus:border-[#579624]"
                              >
                                <option value="Radicado">Radicado</option>
                                <option value="En gestión">En gestión</option>
                                <option value="Escalado">Escalado</option>
                                <option value="Resuelto">Resuelto</option>
                                <option value="Cerrado">Cerrado</option>
                              </select>
                              <input
                                type="text"
                                placeholder="Nota de gestión..."
                                value={draft.notas}
                                onChange={(e) =>
                                  setPqrsEdits((prev) => ({
                                    ...prev,
                                    [p.radicado_id]: { ...draft, notas: e.target.value },
                                  }))
                                }
                                className="rounded-lg border border-[#DDE5D7] px-2 py-1 text-[11px] w-28 focus:outline-none focus:border-[#579624]"
                              />
                              <button
                                type="button"
                                onClick={() =>
                                  handleUpdatePqrsStatus(
                                    p.radicado_id,
                                    p.estado,
                                    p.notas_gestion || ""
                                  )
                                }
                                className="px-3 py-1 rounded-full bg-[#141B12] hover:bg-[#283324] text-white text-[11px] font-bold cursor-pointer"
                              >
                                Guardar
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Listado reciente de Reportes de Fallas Ciudadanas con Gestión & Respuesta WhatsApp */}
          <div className="lg:col-span-2 bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h3 className="text-xs font-extrabold text-[#141B12] uppercase tracking-wider">
                ⚠️ Reportes Ciudadanos de Fallas Almacenados ({failureReportsList.length})
              </h3>
              {isManager && (
                <span className="text-[11px] text-[#2D5211] bg-[#EEF6E6] border border-[#CDE3B4] px-3 py-0.5 rounded-full font-semibold">
                  📱 Al guardar, se responde automáticamente por WhatsApp si hay contacto
                </span>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-[#F3F6F1] text-[#475569] uppercase text-[11px] font-bold">
                  <tr>
                    <th className="p-2.5">Reporte</th>
                    <th className="p-2.5">Servicio / Barrio</th>
                    <th className="p-2.5">Ciudadano / Contacto</th>
                    <th className="p-2.5">Descripción</th>
                    <th className="p-2.5">Estado</th>
                    {isManager && <th className="p-2.5">Tramitar y Responder (WhatsApp)</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E7EDE3]">
                  {failureReportsList.slice(0, 20).map((f) => {
                    const draft = failureEdits[f.reporte_id] || {
                      estado: f.estado,
                      notas: f.notas_gestion || "",
                    };
                    return (
                      <tr key={f.reporte_id} className="hover:bg-[#F7FAF4]">
                        <td className="p-2.5 font-mono font-bold text-[#141B12]">
                          {f.reporte_id}
                          {f.maintenance_id && (
                            <div className="text-[10px] text-[#477D1C] font-semibold">
                              🔧 {f.maintenance_id}
                            </div>
                          )}
                        </td>
                        <td className="p-2.5">
                          <span className="uppercase font-bold text-[#141B12]">{f.servicio}</span>
                          <div className="text-[11px] text-[#5B6757]">{f.barrio}</div>
                        </td>
                        <td className="p-2.5">
                          <div className="font-semibold text-[#141B12]">{f.nombre_ciudadano}</div>
                          <div className="text-[10px] text-[#5B6757]">
                            {f.identificador_tipo}: {f.identificador_valor}
                          </div>
                          {f.telefono_e164 && (
                            <span className="inline-block mt-0.5 px-2 py-0.5 rounded-full bg-[#EEF6E6] text-[#2D5211] text-[10px] font-mono">
                              📱 {f.telefono_e164}
                            </span>
                          )}
                        </td>
                        <td className="p-2.5 max-w-[200px]">
                          <p className="text-[11px] text-[#1E293B] line-clamp-2" title={f.descripcion}>
                            {f.descripcion}
                          </p>
                          <div className="text-[10px] text-[#5B6757] mt-0.5">
                            🕒 {f.created_at ? f.created_at.replace("T", " ").slice(0, 16) : ""}
                          </div>
                        </td>
                        <td className="p-2.5">
                          <span
                            className={`px-2.5 py-0.5 rounded-full font-bold ${
                              f.estado === "Resuelto"
                                ? "bg-[#EEF6E6] text-[#2D5211] border border-[#CDE3B4]"
                                : f.estado === "Brigada asignada"
                                ? "bg-sky-100 text-sky-900"
                                : "bg-[#FACC15]/40 text-[#141B12]"
                            }`}
                          >
                            {f.estado}
                          </span>
                          {f.notas_gestion && (
                            <p
                              className="text-[10px] text-[#5B6757] mt-0.5 max-w-[160px] truncate"
                              title={f.notas_gestion}
                            >
                              {f.notas_gestion}
                            </p>
                          )}
                        </td>
                        {isManager && (
                          <td className="p-2.5">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <select
                                value={draft.estado}
                                onChange={(e) =>
                                  setFailureEdits((prev) => ({
                                    ...prev,
                                    [f.reporte_id]: { ...draft, estado: e.target.value },
                                  }))
                                }
                                className="rounded-lg border border-[#DDE5D7] px-2 py-1 text-[11px] bg-white focus:outline-none focus:border-[#579624]"
                              >
                                <option value="Reportado">Reportado</option>
                                <option value="Agrupado en alerta">Agrupado en alerta</option>
                                <option value="Brigada asignada">Brigada asignada</option>
                                <option value="Resuelto">Resuelto</option>
                              </select>
                              <input
                                type="text"
                                placeholder="Respuesta al ciudadano..."
                                value={draft.notas}
                                onChange={(e) =>
                                  setFailureEdits((prev) => ({
                                    ...prev,
                                    [f.reporte_id]: { ...draft, notas: e.target.value },
                                  }))
                                }
                                className="rounded-lg border border-[#DDE5D7] px-2 py-1 text-[11px] w-36 focus:outline-none focus:border-[#579624]"
                              />
                              <button
                                type="button"
                                onClick={() =>
                                  handleUpdateFailureStatus(
                                    f.reporte_id,
                                    f.estado,
                                    f.notas_gestion || ""
                                  )
                                }
                                className="px-3 py-1 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white text-[11px] font-bold cursor-pointer"
                              >
                                Responder
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: NOTICIAS & BOLETÍN DIARIO OPENCLAW */}
      {subTab === "news" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="text-[11px] font-semibold text-[#477D1C]">
                  Reparaciones, Mantenimientos y Actualidad
                </div>
                <div className="w-8 h-0.5 bg-[#579624] rounded-full my-1" />
                <h3 className="text-base font-extrabold tracking-tight text-[#141B12] flex items-center gap-1.5">
                  <Newspaper className="w-4 h-4 text-[#579624]" /> Noticias Scrapeadas de EMCALI ({newsList.length} mostradas)
                </h3>
              </div>
              <button
                onClick={() => loadNewsAndDigest(true)}
                disabled={refreshingNews}
                className="px-3.5 py-2 rounded-full bg-[#EEF6E6] hover:bg-[#E1F0D3] border border-[#CDE3B4] text-[#2D5211] disabled:opacity-60 text-xs font-bold flex items-center gap-1.5 transition cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${refreshingNews ? "animate-spin" : ""}`} />{" "}
                {refreshingNews ? "Sincronizando..." : "Actualizar"}
              </button>
            </div>
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {newsList.map((n) => {
                const catLow = String(n.categoria || "").toLowerCase();
                const isMaint = Boolean(n.es_mantenimiento) || catLow.includes("manten") || catLow.includes("reparac");
                let iconBg = "bg-[#EEF6E6] text-[#2D5211] border-[#CDE3B4]";
                let CategoryIcon = Newspaper;
                if (isMaint) {
                  iconBg = "bg-[#FACC15] text-[#141B12] border-[#E5B800]";
                  CategoryIcon = Wrench;
                } else if (catLow.includes("energ")) {
                  iconBg = "bg-yellow-100 text-yellow-900 border-yellow-300";
                  CategoryIcon = Zap;
                } else if (catLow.includes("acueducto") || catLow.includes("alcantarillado")) {
                  iconBg = "bg-sky-100 text-sky-900 border-sky-300";
                  CategoryIcon = Droplets;
                } else if (catLow.includes("telco") || catLow.includes("fibra")) {
                  iconBg = "bg-purple-100 text-purple-900 border-purple-300";
                  CategoryIcon = Wifi;
                }
                return (
                  <div
                    key={n.noticia_id}
                    className="p-3.5 rounded-2xl border border-[#DDE5D7] hover:border-[#579624] bg-[#FCFDFB] hover:bg-[#F7FAF4] transition text-xs flex items-start gap-3.5"
                  >
                    <div
                      title={n.categoria}
                      className={`w-12 h-12 rounded-2xl border flex items-center justify-center shrink-0 shadow-xs ${iconBg}`}
                    >
                      <CategoryIcon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-extrabold text-[#141B12] leading-snug">{n.titulo}</span>
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-[#F3F6F1] border border-[#DDE5D7] text-[#475569] shrink-0">
                          📅 {n.fecha_publicacion || (n.scraped_at ? String(n.scraped_at).slice(0, 10) : "2026")}
                        </span>
                      </div>
                      <p className="text-[#475569] line-clamp-2">{n.resumen}</p>
                      {n.barrios?.length > 0 && (
                        <div className="text-[11px] text-[#477D1C] font-semibold">
                          📍 Barrios detectados: {n.barrios.join(", ")}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3">
              <h3 className="text-xs font-extrabold text-[#141B12] uppercase tracking-wider">
                📬 Vista Previa: Boletín Diario OpenClaw (WhatsApp)
              </h3>
              <pre className="whitespace-pre-wrap text-[11px] bg-[#141B12] text-[#DCECC9] p-3.5 rounded-2xl max-h-64 overflow-y-auto font-mono">
                {newsletterDigest || "Cargando boletín diario..."}
              </pre>
              <form onSubmit={handleSubscribeNewsletter} className="space-y-2.5 text-xs pt-1">
                <input
                  required
                  value={subForm.contacto}
                  onChange={(e) => setSubForm({ ...subForm, contacto: e.target.value })}
                  placeholder="WhatsApp E.164 (+57300...)"
                  className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                />
                <input
                  value={subForm.barrio_interes}
                  onChange={(e) => setSubForm({ ...subForm, barrio_interes: e.target.value })}
                  placeholder="Barrio de interés (ej. San Fernando)"
                  className="w-full px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                />
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white font-bold shadow-xs transition cursor-pointer"
                >
                  Suscribir al Boletín Diario
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 4: UMAP 2D + 20 TOOLS + HITL */}
      {subTab === "umap_tools" && (
        <div className="space-y-5">
          <div className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-[11px] font-semibold text-[#477D1C]">
                  Espacio Semántico de Embeddings
                </div>
                <div className="w-8 h-0.5 bg-[#579624] rounded-full my-1" />
                <h3 className="text-base font-extrabold tracking-tight text-[#141B12] flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-[#579624]" /> Proyección UMAP 2D — Corpus EMCALI + Consultas + Tickets
                </h3>
                {umapData && (
                  <p className="text-xs text-[#5B6757] mt-0.5">
                    {umapData.method} · Puntos: <b className="text-[#141B12]">{umapData.metrics.total_points}</b> · Clusters:{" "}
                    <b className="text-[#141B12]">{umapData.metrics.clusters_detected}</b> · Silhouette Score:{" "}
                    <b className="text-[#477D1C]">{umapData.metrics.silhouette_score}</b>
                  </p>
                )}
              </div>
              <button
                onClick={() => loadCatalogAndUmap(true)}
                disabled={loadingUmap}
                className="px-4 py-2 rounded-full bg-[#141B12] hover:bg-[#283324] text-white text-xs font-bold flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingUmap ? "animate-spin" : ""}`} />
                Recalcular UMAP
              </button>
            </div>

            {renderUmapSvg()}

            {hoveredPoint && (
              <div className="p-3 rounded-2xl bg-[#F7FAF4] border border-[#DDE5D7] text-xs">
                <span className="font-bold text-[#141B12]">{hoveredPoint.id}</span> ·{" "}
                <span className="uppercase font-bold text-[#477D1C]">
                  {hoveredPoint.section}
                </span>{" "}
                ({hoveredPoint.kind}) — {hoveredPoint.label}
              </div>
            )}
          </div>

          {/* Cola HITL */}
          {hitlPending.length > 0 && (
            <div className="bg-[#FFF4E8] rounded-3xl border border-[#F5820D]/40 p-5 space-y-2.5">
              <h3 className="text-xs font-extrabold text-[#9A3412] uppercase tracking-wider">
                ⏳ Aprobaciones Human-in-the-Loop (HITL) Pendientes ({hitlPending.length})
              </h3>
              {hitlPending.map((a) => (
                <div
                  key={a.action_id}
                  className="bg-white p-3.5 rounded-2xl border border-[#F5820D]/25 flex items-center justify-between gap-2 text-xs"
                >
                  <div>
                    <div className="font-bold text-[#141B12]">
                      {a.action_id} · <code>{a.tool_name}</code>
                    </div>
                    <div className="text-[#475569]">{a.summary}</div>
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => handleResolveHitl(a.action_id, true)}
                      className="px-3.5 py-1.5 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white font-bold cursor-pointer"
                    >
                      Aprobar
                    </button>
                    <button
                      onClick={() => handleResolveHitl(a.action_id, false)}
                      className="px-3.5 py-1.5 rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold cursor-pointer"
                    >
                      Rechazar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Catálogo de 20 Herramientas */}
          <div className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)]">
            <h3 className="text-sm font-extrabold text-[#141B12] mb-3 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-[#579624]" /> Catálogo Verificado de 20 Herramientas Pydantic v2 ({toolsCatalog.length}/20)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs">
              {toolsCatalog.map((t) => (
                <div
                  key={t.name}
                  className={`p-3 rounded-2xl border ${
                    t.required_role === "manager"
                      ? "bg-[#FFF4E8]/70 border-[#F5820D]/30"
                      : "bg-[#F7FAF4] border-[#DDE5D7]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="font-mono font-bold text-[11px] text-[#141B12] truncate">
                      {t.index}. {t.name}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#475569] line-clamp-2">{t.description}</p>
                  <div className="mt-2 flex gap-1.5">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        t.required_role === "manager"
                          ? "bg-[#FACC15] text-[#141B12]"
                          : "bg-[#EEF6E6] text-[#2D5211] border border-[#CDE3B4]"
                      }`}
                    >
                      {t.required_role}
                    </span>
                    {t.hitl_protected && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-900">
                        HITL
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 6: INICIAR SESIÓN & REGISTRO CIUDADANO (SIN CREDENCIALES PRECARGADAS) */}
      {subTab === "auth" && !session.authenticated && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <form
            onSubmit={handleLogin}
            className="bg-white rounded-3xl border border-[#DDE5D7] p-6 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3.5 text-xs"
          >
            <div>
              <div className="text-[11px] font-semibold text-[#477D1C]">Mi Cuenta EMCALI</div>
              <div className="w-8 h-0.5 bg-[#579624] rounded-full my-1" />
              <h3 className="text-base font-extrabold tracking-tight text-[#141B12] flex items-center gap-1.5">
                <Lock className="w-4 h-4 text-[#579624]" /> Iniciar Sesión (Ciudadano o Gestión EMCALI)
              </h3>
            </div>
            <p className="text-[#475569] leading-relaxed">
              Ingresa con tus credenciales registradas. Las cuentas con rol <b className="text-[#141B12]">Gestión EMCALI</b>{" "}
              desbloquean el panel IAM, despacho de brigadas y el Chatbot Gerencial (20 tools).
            </p>
            <div className="space-y-2.5">
              <input
                required
                autoComplete="username"
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                placeholder="Nombre de usuario"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
              <input
                required
                type="password"
                autoComplete="current-password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                placeholder="Contraseña"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
            </div>
            <button
              type="submit"
              className="w-full py-2.5 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white font-bold shadow-xs transition cursor-pointer"
            >
              Entrar
            </button>
          </form>

          <form
            onSubmit={handleRegister}
            className="bg-white rounded-3xl border border-[#DDE5D7] p-6 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3.5 text-xs"
          >
            <div>
              <div className="text-[11px] font-semibold text-[#DC7006]">Nuevo Registro</div>
              <div className="w-8 h-0.5 bg-[#F5820D] rounded-full my-1" />
              <h3 className="text-base font-extrabold tracking-tight text-[#141B12] flex items-center gap-1.5">
                <UserPlus className="w-4 h-4 text-[#F5820D]" /> Registro de Nuevo Usuario Ciudadano
              </h3>
            </div>
            <p className="text-[#475569] leading-relaxed">
              Crea tu cuenta ciudadana para dar seguimiento a tus PQRS, reportes de fallas y
              preferencias de barrio. <i>(Por seguridad RBAC, el auto-registro asigna rol Ciudadano.)</i>
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <input
                required
                minLength={3}
                autoComplete="username"
                value={regForm.username}
                onChange={(e) => setRegForm({ ...regForm, username: e.target.value })}
                placeholder="Usuario (mín. 3 caracteres)"
                className="px-3.5 py-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
              <input
                required
                value={regForm.display_name}
                onChange={(e) => setRegForm({ ...regForm, display_name: e.target.value })}
                placeholder="Nombre completo"
                className="px-3.5 py-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
              <input
                required
                type="password"
                minLength={6}
                autoComplete="new-password"
                value={regForm.password}
                onChange={(e) => setRegForm({ ...regForm, password: e.target.value })}
                placeholder="Contraseña (mín. 6 caracteres)"
                className="px-3.5 py-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
              <input
                value={regForm.phone_e164}
                onChange={(e) => setRegForm({ ...regForm, phone_e164: e.target.value })}
                placeholder="WhatsApp E.164 opcional (+57...)"
                className="px-3.5 py-2.5 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] font-mono focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
              />
            </div>
            <button
              type="submit"
              className="w-full py-2.5 rounded-full bg-[#F5820D] hover:bg-[#DC7006] text-white font-bold shadow-xs transition cursor-pointer"
            >
              Crear Cuenta Ciudadana
            </button>
          </form>
        </div>
      )}

      {/* SUB-TAB 5: IAM USUARIOS & WHATSAPP ALLOWLIST (SOLO GESTIÓN EMCALI) */}
      {subTab === "iam" && isManager && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Control en vivo del Allowlist WhatsApp (OpenClaw) */}
              <div className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3.5">
                <h3 className="text-sm font-extrabold text-[#141B12]">
                  📱 WhatsApp Allowlist en Vivo (OpenClaw <code>allowFrom</code>)
                </h3>
                <p className="text-xs text-[#475569]">
                  Agrega o remueve números E.164 (ej. invitados de EMCALI) sin tocar la terminal. OpenClaw recarga los cambios automáticamente.
                </p>
                <form onSubmit={handleAddWaPhone} className="flex gap-2 text-xs">
                  <input
                    required
                    value={newWaPhone}
                    onChange={(e) => setNewWaPhone(e.target.value)}
                    placeholder="+573183775357"
                    className="flex-1 px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] font-mono text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white font-bold cursor-pointer"
                  >
                    + Agregar
                  </button>
                </form>
                <div className="space-y-2">
                  {waAllowlist.length === 0 ? (
                    <p className="text-xs text-[#5B6757]">Sin números configurados en openclaw.json.</p>
                  ) : (
                    waAllowlist.map((phone) => (
                      <div
                        key={phone}
                        className="flex items-center justify-between px-3.5 py-2.5 rounded-2xl bg-[#F7FAF4] border border-[#DDE5D7] text-xs"
                      >
                        <span className="font-mono font-bold text-[#141B12]">{phone}</span>
                        <button
                          onClick={() => handleRemoveWaPhone(phone)}
                          className="px-2.5 py-1 rounded-full bg-rose-100 hover:bg-rose-200 text-rose-800 font-bold cursor-pointer"
                        >
                          Quitar
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Control de Usuarios RBAC */}
              <div className="bg-white rounded-3xl border border-[#DDE5D7] p-5 shadow-[0_2px_12px_rgba(20,27,18,0.05)] space-y-3.5">
                <h3 className="text-sm font-extrabold text-[#141B12]">
                  👥 Administración de Usuarios RBAC ({adminUsers.length})
                </h3>
                <form onSubmit={handleSaveUser} className="grid grid-cols-2 gap-2.5 text-xs">
                  <input
                    required
                    value={newUserForm.username}
                    onChange={(e) => setNewUserForm({ ...newUserForm, username: e.target.value })}
                    placeholder="usuario (ej. jacobo)"
                    className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <input
                    required
                    value={newUserForm.display_name}
                    onChange={(e) => setNewUserForm({ ...newUserForm, display_name: e.target.value })}
                    placeholder="Nombre visible"
                    className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <select
                    value={newUserForm.role}
                    onChange={(e) =>
                      setNewUserForm({ ...newUserForm, role: e.target.value as "citizen" | "manager" })
                    }
                    className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  >
                    <option value="manager">Manager (Gestión 20/20)</option>
                    <option value="citizen">Citizen (Público 16/20)</option>
                  </select>
                  <input
                    required
                    type="password"
                    value={newUserForm.password}
                    onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
                    placeholder="Contraseña (mín. 4)"
                    className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <input
                    value={newUserForm.phone_e164}
                    onChange={(e) => setNewUserForm({ ...newUserForm, phone_e164: e.target.value })}
                    placeholder="WhatsApp E.164 (opcional)"
                    className="px-3 py-2 rounded-xl bg-[#F7FAF4] border border-[#DDE5D7] font-mono text-[#141B12] focus:outline-none focus:ring-2 focus:ring-[#579624]/30 focus:border-[#579624]"
                  />
                  <button
                    type="submit"
                    className="py-2 rounded-full bg-[#579624] hover:bg-[#477D1C] text-white font-bold cursor-pointer"
                  >
                    + Crear / Actualizar
                  </button>
                </form>

                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {adminUsers.map((u) => (
                    <div
                      key={u.username}
                      className="flex items-center justify-between px-3.5 py-2.5 rounded-2xl bg-[#F7FAF4] border border-[#DDE5D7] text-xs"
                    >
                      <div>
                        <span className="font-bold text-[#141B12]">{u.username}</span>{" "}
                        <span className="text-[#475569]">({u.display_name})</span>
                        <div className="text-[11px] text-[#5B6757]">
                          Rol: <b>{u.role}</b> · Tel: {u.phone_e164 || "—"}
                        </div>
                      </div>
                      <button
                        onClick={() => handleToggleUserActive(u)}
                        className={`px-3 py-1 rounded-full font-bold cursor-pointer ${
                          u.active
                            ? "bg-[#EEF6E6] text-[#2D5211] border border-[#CDE3B4]"
                            : "bg-slate-200 text-slate-600"
                        }`}
                      >
                        {u.active ? "Activo" : "Inactivo"}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
        </div>
      )}
    </main>
  );
};
