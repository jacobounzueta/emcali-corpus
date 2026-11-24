import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  LogOut,
  MapPin,
  Newspaper,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Wrench,
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
  const [subTab, setSubTab] = useState<"map" | "pqrs" | "news" | "umap_tools" | "iam">("map");
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
  const [loginUser, setLoginUser] = useState("rommel");
  const [loginPass, setLoginPass] = useState("emcali-ops-2026");
  const [statusMsg, setStatusMsg] = useState<string>("");

  // Map & Ops state
  const [serviceFilter, setServiceFilter] = useState("todos");
  const [maintenances, setMaintenances] = useState<MaintenancePoint[]>([]);
  const [hotspots, setHotspots] = useState<FailureHotspot[]>([]);
  const [pqrsList, setPqrsList] = useState<any[]>([]);
  const [newsList, setNewsList] = useState<any[]>([]);
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
      const [mapRes, pqrsRes, hitlRes] = await Promise.all([
        fetch(`${API_BASE}/api/map/overview?servicio=${serviceFilter}`),
        fetch(`${API_BASE}/api/pqrs`),
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
      if (hitlRes.ok) {
        const d = await hitlRes.json();
        setHitlPending(d.items || []);
      }
    } catch {
      // silent
    }
  }, [serviceFilter]);

  const loadNewsAndDigest = useCallback(async () => {
    try {
      const [nRes, dRes] = await Promise.all([
        fetch(`${API_BASE}/api/news?limit=20`),
        fetch(`${API_BASE}/api/newsletter/digest`),
      ]);
      if (nRes.ok) {
        const d = await nRes.json();
        setNewsList(d.items || []);
      }
      if (dRes.ok) {
        const d = await dRes.json();
        setNewsletterDigest(d.markdown_digest || "");
      }
    } catch {
      // silent
    }
  }, []);

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
    setStatusMsg(`✅ Sesión activa: ${data.display_name} (${data.role.toUpperCase()})`);
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
    setStatusMsg("🔄 Modo Ciudadano activo (herramientas de gestión bloqueadas por RBAC).");
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
    setStatusMsg(
      `🚑 Brigada despachada a ${h.barrio} (${data.maintenance.linked_failure_reports} fallas vinculadas).`
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
    <main className="max-w-[1440px] w-full mx-auto px-4 py-5 flex-1 space-y-4">
      {/* Barra IAM / RBAC: Cambio en vivo entre Chatbot Ciudadano y Gestión EMCALI */}
      <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 ${
              isManager
                ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                : "bg-sky-100 text-sky-900 border border-sky-300"
            }`}
          >
            {isManager ? <ShieldCheck className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
            {isManager ? "MODO GESTIÓN EMCALI (20/20 Tools)" : "MODO CIUDADANO (16/20 Tools · RBAC)"}
          </div>
          <span className="text-xs text-slate-600">{session.display_name}</span>
        </div>

        {isManager ? (
          <button
            onClick={handleLogout}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" /> Salir a Modo Ciudadano
          </button>
        ) : (
          <form onSubmit={handleLogin} className="flex flex-wrap items-center gap-2">
            <input
              value={loginUser}
              onChange={(e) => setLoginUser(e.target.value)}
              placeholder="Usuario gestión"
              className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs w-28"
            />
            <input
              type="password"
              value={loginPass}
              onChange={(e) => setLoginPass(e.target.value)}
              placeholder="Contraseña"
              className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs w-32"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-[#003B71] hover:bg-[#00284D] text-white text-xs font-semibold flex items-center gap-1 cursor-pointer"
            >
              <Lock className="w-3.5 h-3.5" /> Entrar Gestión EMCALI
            </button>
          </form>
        )}
      </section>

      {statusMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 px-4 py-2 rounded-xl text-xs font-medium flex items-center justify-between">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg("")} className="text-emerald-700 underline cursor-pointer">
            Cerrar
          </button>
        </div>
      )}

      {/* Sub-navegación M3 */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: "map", label: "🗺️ Mapa Cali, Mantenimientos & Brigadas" },
          { id: "pqrs", label: "📝 PQRS & Reporte de Fallas" },
          { id: "news", label: "📰 Noticias (310+) & Boletín OpenClaw" },
          { id: "umap_tools", label: "🧬 UMAP 2D, 20 Tools & HITL" },
          { id: "iam", label: "🔐 IAM Usuarios & WhatsApp Allowlist" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id as any)}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
              subTab === t.id
                ? "bg-[#003B71] text-white border-[#003B71] shadow"
                : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* SUB-TAB 1: MAPA INTERACTIVO CALI + HOTSPOTS + ACTIVACIÓN GESTIÓN */}
      {subTab === "map" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-[#003B71] flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-[#00875A]" /> Mapa Operativo de Cali — Mantenimientos y Alertas de Fallas
                </h2>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  En vivo (4s)
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                {["todos", "energia", "acueducto", "alcantarillado", "telco_fibra"].map((s) => (
                  <button
                    key={s}
                    onClick={() => setServiceFilter(s)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer ${
                      serviceFilter === s
                        ? "bg-[#00875A] text-white"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {s}
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
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-2.5">
              <h3 className="text-xs font-bold text-rose-700 flex items-center gap-1.5 uppercase">
                <AlertTriangle className="w-4 h-4" /> Hotspots de Fallas Ciudadanas ({hotspots.length})
              </h3>
              {hotspots.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Sin alertas de fallas abiertas. Reporta una falla en la pestaña PQRS & Fallas para ver el agrupamiento en vivo.
                </p>
              ) : (
                <div className="space-y-2 max-h-52 overflow-y-auto">
                  {hotspots.map((h) => (
                    <div
                      key={`${h.barrio}-${h.servicio}`}
                      className="p-2.5 rounded-xl bg-rose-50/70 border border-rose-200 text-xs flex items-center justify-between gap-2"
                    >
                      <div>
                        <div className="font-bold text-slate-900">
                          {h.barrio} · <span className="uppercase text-rose-700">{h.servicio}</span>
                        </div>
                        <div className="text-[11px] text-slate-600">
                          {h.report_count} reporte(s) · {h.severity_label}
                        </div>
                        <div className="text-[10px] text-slate-500">
                          🕒 {h.latest_report_at ? h.latest_report_at.replace("T", " ").slice(0, 16) : "Reciente"}
                        </div>
                      </div>
                      {isManager && (
                        <button
                          onClick={() => handleDispatchHotspot(h)}
                          className="px-2.5 py-1 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-[11px] font-bold shrink-0 cursor-pointer"
                        >
                          🚑 Despachar Brigada
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Activar Nuevo Punto de Mantenimiento (Solo Gestión EMCALI) */}
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-2.5">
              <h3 className="text-xs font-bold text-[#003B71] flex items-center gap-1.5 uppercase">
                <Wrench className="w-4 h-4 text-[#00875A]" /> Activar Punto de Mantenimiento
              </h3>
              {!isManager ? (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900">
                  🛡️ <b>RBAC (`tools.deny`):</b> Inicia sesión en modo <b>Gestión EMCALI</b> para activar mantenimientos o despachar brigadas en el mapa.
                </div>
              ) : (
                <form onSubmit={handleActivateMaintenance} className="space-y-2 text-xs">
                  <input
                    required
                    value={maintForm.titulo}
                    onChange={(e) => setMaintForm({ ...maintForm, titulo: e.target.value })}
                    placeholder="Título del mantenimiento"
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      value={maintForm.servicio}
                      onChange={(e) => setMaintForm({ ...maintForm, servicio: e.target.value })}
                      className="px-2 py-1.5 rounded-lg border border-slate-300"
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
                      className="px-2.5 py-1.5 rounded-lg border border-slate-300"
                    />
                  </div>
                  <input
                    value={maintForm.brigada_asignada}
                    onChange={(e) =>
                      setMaintForm({ ...maintForm, brigada_asignada: e.target.value })
                    }
                    placeholder="Brigada asignada"
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
                  />
                  <textarea
                    required
                    rows={2}
                    value={maintForm.descripcion}
                    onChange={(e) => setMaintForm({ ...maintForm, descripcion: e.target.value })}
                    placeholder="Descripción técnica de la intervención"
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
                  />
                  <button
                    type="submit"
                    className="w-full py-2 rounded-lg bg-[#00875A] hover:bg-emerald-700 text-white font-bold cursor-pointer"
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <form
            onSubmit={handleCreatePqrs}
            className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-2.5 text-xs"
          >
            <h3 className="text-sm font-bold text-[#003B71]">
              📝 Radicar PQRS (Por Contrato o por Cédula si no es cliente)
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={pqrsForm.tipo}
                onChange={(e) => setPqrsForm({ ...pqrsForm, tipo: e.target.value })}
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              >
                <option>Petición</option>
                <option>Queja</option>
                <option>Reclamo</option>
                <option>Sugerencia</option>
              </select>
              <select
                value={pqrsForm.servicio}
                onChange={(e) => setPqrsForm({ ...pqrsForm, servicio: e.target.value })}
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              >
                <option value="energia">Energía</option>
                <option value="acueducto">Acueducto</option>
                <option value="alcantarillado">Alcantarillado</option>
                <option value="telco_fibra">Telco Fibra</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={pqrsForm.identificador_tipo}
                onChange={(e) => setPqrsForm({ ...pqrsForm, identificador_tipo: e.target.value })}
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              >
                <option value="contrato">Cliente — Número de Contrato</option>
                <option value="cedula">No Cliente — Cédula</option>
              </select>
              <input
                required
                value={pqrsForm.identificador_valor}
                onChange={(e) => setPqrsForm({ ...pqrsForm, identificador_valor: e.target.value })}
                placeholder="Número (mín. 5 dígitos)"
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                required
                value={pqrsForm.nombre_ciudadano}
                onChange={(e) => setPqrsForm({ ...pqrsForm, nombre_ciudadano: e.target.value })}
                placeholder="Nombre completo"
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              />
              <input
                required
                value={pqrsForm.barrio}
                onChange={(e) => setPqrsForm({ ...pqrsForm, barrio: e.target.value })}
                placeholder="Barrio de Cali"
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              />
            </div>
            <textarea
              required
              rows={2}
              value={pqrsForm.descripcion}
              onChange={(e) => setPqrsForm({ ...pqrsForm, descripcion: e.target.value })}
              placeholder="Describe tu petición, queja, reclamo o sugerencia..."
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
            />
            <button
              type="submit"
              className="w-full py-2 rounded-lg bg-[#003B71] hover:bg-[#00284D] text-white font-bold cursor-pointer"
            >
              Radicar PQRS en SQLite
            </button>
          </form>

          <form
            onSubmit={handleCreateFailure}
            className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-2.5 text-xs"
          >
            <h3 className="text-sm font-bold text-rose-700">
              ⚠️ Reportar Falla de Servicio (Georreferencia y Alerta Brigadas)
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={failForm.servicio}
                onChange={(e) => setFailForm({ ...failForm, servicio: e.target.value })}
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
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
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={failForm.identificador_tipo}
                onChange={(e) => setFailForm({ ...failForm, identificador_tipo: e.target.value })}
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              >
                <option value="contrato">Cliente — Contrato</option>
                <option value="cedula">No Cliente — Cédula</option>
              </select>
              <input
                required
                value={failForm.identificador_valor}
                onChange={(e) => setFailForm({ ...failForm, identificador_valor: e.target.value })}
                placeholder="Número de contrato o cédula"
                className="px-2.5 py-1.5 rounded-lg border border-slate-300"
              />
            </div>
            <input
              value={failForm.direccion}
              onChange={(e) => setFailForm({ ...failForm, direccion: e.target.value })}
              placeholder="Dirección o referencia (opcional)"
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
            />
            <textarea
              required
              rows={2}
              value={failForm.descripcion}
              onChange={(e) => setFailForm({ ...failForm, descripcion: e.target.value })}
              placeholder="Describe la falla (ej. sin energía, fuga de agua, corte de fibra)..."
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
            />
            <button
              type="submit"
              className="w-full py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-bold cursor-pointer"
            >
              Reportar Falla en Mapa de Cali
            </button>
          </form>

          {/* Listado reciente de PQRS */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
            <h3 className="text-xs font-bold text-[#003B71] uppercase mb-2">
              Radicados PQRS Almacenados ({pqrsList.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="p-2">Radicado</th>
                    <th className="p-2">Tipo / Servicio</th>
                    <th className="p-2">Identificación</th>
                    <th className="p-2">Barrio</th>
                    <th className="p-2">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {pqrsList.slice(0, 10).map((p) => (
                    <tr key={p.radicado_id}>
                      <td className="p-2 font-mono font-bold text-[#003B71]">{p.radicado_id}</td>
                      <td className="p-2">
                        {p.tipo} · <span className="uppercase">{p.servicio}</span>
                      </td>
                      <td className="p-2">
                        {p.identificador_tipo}: <b>{p.identificador_valor}</b>
                      </td>
                      <td className="p-2">{p.barrio}</td>
                      <td className="p-2">
                        <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold">
                          {p.estado}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: NOTICIAS & BOLETÍN DIARIO OPENCLAW */}
      {subTab === "news" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#003B71] flex items-center gap-1.5">
                <Newspaper className="w-4 h-4 text-[#00875A]" /> Noticias Scrapeadas de EMCALI ({newsList.length} mostradas)
              </h3>
              <button
                onClick={loadNewsAndDigest}
                className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold flex items-center gap-1 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Actualizar
              </button>
            </div>
            <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
              {newsList.map((n) => (
                <div
                  key={n.noticia_id}
                  className="p-3 rounded-xl border border-slate-200 hover:border-sky-300 transition text-xs space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-slate-900">{n.titulo}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-100 text-slate-700">
                        📅 {n.fecha_publicacion || (n.scraped_at ? String(n.scraped_at).slice(0, 10) : "2026")}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          n.es_mantenimiento
                            ? "bg-amber-100 text-amber-900"
                            : "bg-sky-100 text-sky-900"
                        }`}
                      >
                        {n.categoria}
                      </span>
                    </div>
                  </div>
                  <p className="text-slate-600 line-clamp-2">{n.resumen}</p>
                  {n.barrios?.length > 0 && (
                    <div className="text-[11px] text-emerald-700 font-medium">
                      📍 Barrios detectados: {n.barrios.join(", ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-2.5">
              <h3 className="text-xs font-bold text-[#003B71] uppercase">
                📬 Vista Previa: Boletín Diario OpenClaw (WhatsApp)
              </h3>
              <pre className="whitespace-pre-wrap text-[11px] bg-slate-900 text-emerald-200 p-3 rounded-xl max-h-64 overflow-y-auto font-mono">
                {newsletterDigest || "Cargando boletín diario..."}
              </pre>
              <form onSubmit={handleSubscribeNewsletter} className="space-y-2 text-xs pt-1">
                <input
                  required
                  value={subForm.contacto}
                  onChange={(e) => setSubForm({ ...subForm, contacto: e.target.value })}
                  placeholder="WhatsApp E.164 (+57300...)"
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
                />
                <input
                  value={subForm.barrio_interes}
                  onChange={(e) => setSubForm({ ...subForm, barrio_interes: e.target.value })}
                  placeholder="Barrio de interés (ej. San Fernando)"
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300"
                />
                <button
                  type="submit"
                  className="w-full py-2 rounded-lg bg-[#00875A] hover:bg-emerald-700 text-white font-bold cursor-pointer"
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
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold text-[#003B71] flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-purple-600" /> Proyección UMAP 2D — Corpus EMCALI + Consultas + Tickets
                </h3>
                {umapData && (
                  <p className="text-xs text-slate-600">
                    {umapData.method} · Puntos: <b>{umapData.metrics.total_points}</b> · Clusters:{" "}
                    <b>{umapData.metrics.clusters_detected}</b> · Silhouette Score:{" "}
                    <b>{umapData.metrics.silhouette_score}</b>
                  </p>
                )}
              </div>
              <button
                onClick={() => loadCatalogAndUmap(true)}
                disabled={loadingUmap}
                className="px-3 py-1.5 rounded-lg bg-[#003B71] text-white text-xs font-semibold flex items-center gap-1 cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingUmap ? "animate-spin" : ""}`} />
                Recalcular UMAP
              </button>
            </div>

            {renderUmapSvg()}

            {hoveredPoint && (
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                <span className="font-bold text-[#003B71]">{hoveredPoint.id}</span> ·{" "}
                <span className="uppercase font-semibold text-emerald-700">
                  {hoveredPoint.section}
                </span>{" "}
                ({hoveredPoint.kind}) — {hoveredPoint.label}
              </div>
            )}
          </div>

          {/* Cola HITL */}
          {hitlPending.length > 0 && (
            <div className="bg-amber-50 rounded-2xl border border-amber-300 p-4 space-y-2">
              <h3 className="text-xs font-bold text-amber-900 uppercase">
                ⏳ Aprobaciones Human-in-the-Loop (HITL) Pendientes ({hitlPending.length})
              </h3>
              {hitlPending.map((a) => (
                <div
                  key={a.action_id}
                  className="bg-white p-3 rounded-xl border border-amber-200 flex items-center justify-between gap-2 text-xs"
                >
                  <div>
                    <div className="font-bold text-slate-900">
                      {a.action_id} · <code>{a.tool_name}</code>
                    </div>
                    <div className="text-slate-600">{a.summary}</div>
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => handleResolveHitl(a.action_id, true)}
                      className="px-2.5 py-1 rounded-lg bg-emerald-600 text-white font-bold cursor-pointer"
                    >
                      Aprobar
                    </button>
                    <button
                      onClick={() => handleResolveHitl(a.action_id, false)}
                      className="px-2.5 py-1 rounded-lg bg-rose-600 text-white font-bold cursor-pointer"
                    >
                      Rechazar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Catálogo de 20 Herramientas */}
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
            <h3 className="text-sm font-bold text-[#003B71] mb-2 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-[#00875A]" /> Catálogo Verificado de 20 Herramientas Pydantic v2 ({toolsCatalog.length}/20)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
              {toolsCatalog.map((t) => (
                <div
                  key={t.name}
                  className={`p-2.5 rounded-xl border ${
                    t.required_role === "manager"
                      ? "bg-amber-50/70 border-amber-200"
                      : "bg-slate-50 border-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="font-mono font-bold text-[11px] text-[#003B71] truncate">
                      {t.index}. {t.name}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 line-clamp-2">{t.description}</p>
                  <div className="mt-1.5 flex gap-1">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        t.required_role === "manager"
                          ? "bg-amber-200 text-amber-950"
                          : "bg-sky-100 text-sky-900"
                      }`}
                    >
                      {t.required_role}
                    </span>
                    {t.hitl_protected && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-900">
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
      {/* SUB-TAB 5: IAM USUARIOS & WHATSAPP ALLOWLIST (SOLO GESTIÓN EMCALI) */}
      {subTab === "iam" && (
        <div className="space-y-4">
          {!isManager ? (
            <div className="bg-amber-50 border border-amber-300 rounded-2xl p-6 text-xs text-amber-900">
              🛡️ <b>Acceso restringido (RBAC):</b> Inicia sesión en modo <b>Gestión EMCALI</b> arriba (cuenta admin por defecto: <code>rommel</code> / <code>emcali-ops-2026</code>) para controlar usuarios RBAC y el allowlist E.164 de WhatsApp en vivo.
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Control en vivo del Allowlist WhatsApp (OpenClaw) */}
              <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3">
                <h3 className="text-sm font-bold text-[#003B71]">
                  📱 WhatsApp Allowlist en Vivo (OpenClaw <code>allowFrom</code>)
                </h3>
                <p className="text-xs text-slate-600">
                  Agrega o remueve números E.164 (ej. invitados de EMCALI) sin tocar la terminal. OpenClaw recarga los cambios automáticamente.
                </p>
                <form onSubmit={handleAddWaPhone} className="flex gap-2 text-xs">
                  <input
                    required
                    value={newWaPhone}
                    onChange={(e) => setNewWaPhone(e.target.value)}
                    placeholder="+573183775357"
                    className="flex-1 px-2.5 py-1.5 rounded-lg border border-slate-300 font-mono"
                  />
                  <button
                    type="submit"
                    className="px-3 py-1.5 rounded-lg bg-[#00875A] hover:bg-emerald-700 text-white font-bold cursor-pointer"
                  >
                    + Agregar
                  </button>
                </form>
                <div className="space-y-1.5">
                  {waAllowlist.length === 0 ? (
                    <p className="text-xs text-slate-500">Sin números configurados en openclaw.json.</p>
                  ) : (
                    waAllowlist.map((phone) => (
                      <div
                        key={phone}
                        className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs"
                      >
                        <span className="font-mono font-bold text-slate-800">{phone}</span>
                        <button
                          onClick={() => handleRemoveWaPhone(phone)}
                          className="px-2 py-0.5 rounded bg-rose-100 hover:bg-rose-200 text-rose-800 font-semibold cursor-pointer"
                        >
                          Quitar
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Control de Usuarios RBAC */}
              <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3">
                <h3 className="text-sm font-bold text-[#003B71]">
                  👥 Administración de Usuarios RBAC ({adminUsers.length})
                </h3>
                <form onSubmit={handleSaveUser} className="grid grid-cols-2 gap-2 text-xs">
                  <input
                    required
                    value={newUserForm.username}
                    onChange={(e) => setNewUserForm({ ...newUserForm, username: e.target.value })}
                    placeholder="usuario (ej. jacobo)"
                    className="px-2.5 py-1.5 rounded-lg border border-slate-300"
                  />
                  <input
                    required
                    value={newUserForm.display_name}
                    onChange={(e) => setNewUserForm({ ...newUserForm, display_name: e.target.value })}
                    placeholder="Nombre visible"
                    className="px-2.5 py-1.5 rounded-lg border border-slate-300"
                  />
                  <select
                    value={newUserForm.role}
                    onChange={(e) =>
                      setNewUserForm({ ...newUserForm, role: e.target.value as "citizen" | "manager" })
                    }
                    className="px-2.5 py-1.5 rounded-lg border border-slate-300"
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
                    className="px-2.5 py-1.5 rounded-lg border border-slate-300"
                  />
                  <input
                    value={newUserForm.phone_e164}
                    onChange={(e) => setNewUserForm({ ...newUserForm, phone_e164: e.target.value })}
                    placeholder="WhatsApp E.164 (opcional)"
                    className="px-2.5 py-1.5 rounded-lg border border-slate-300 font-mono"
                  />
                  <button
                    type="submit"
                    className="py-1.5 rounded-lg bg-[#003B71] hover:bg-[#00284D] text-white font-bold cursor-pointer"
                  >
                    + Crear / Actualizar
                  </button>
                </form>

                <div className="space-y-1.5 max-h-60 overflow-y-auto">
                  {adminUsers.map((u) => (
                    <div
                      key={u.username}
                      className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs"
                    >
                      <div>
                        <span className="font-bold text-slate-900">{u.username}</span>{" "}
                        <span className="text-slate-600">({u.display_name})</span>
                        <div className="text-[11px] text-slate-500">
                          Rol: <b>{u.role}</b> · Tel: {u.phone_e164 || "—"}
                        </div>
                      </div>
                      <button
                        onClick={() => handleToggleUserActive(u)}
                        className={`px-2 py-0.5 rounded font-bold cursor-pointer ${
                          u.active
                            ? "bg-emerald-100 text-emerald-900"
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
          )}
        </div>
      )}
    </main>
  );
};
