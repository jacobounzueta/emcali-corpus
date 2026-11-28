import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export interface MaintenancePoint {
  mantenimiento_id: string;
  titulo: string;
  servicio: string;
  barrio: string;
  comuna: string;
  lat: number;
  lng: number;
  descripcion: string;
  fuente: string;
  estado: string;
  brigada_asignada: string;
  inicio_estimado: string;
  fin_estimado: string;
  created_at?: string;
  updated_at?: string;
}

export interface FailureHotspot {
  barrio: string;
  comuna: string;
  servicio: string;
  lat: number;
  lng: number;
  report_count: number;
  severity: "watch_single" | "warning_cluster" | "critical_dispatch";
  severity_label: string;
  dispatch_recommended: boolean;
  latest_report_at: string;
}

interface CaliMapPanelProps {
  maintenances: MaintenancePoint[];
  hotspots: FailureHotspot[];
  isManager: boolean;
  onSelectHotspotForDispatch?: (hotspot: FailureHotspot) => void;
}

const SERVICE_COLORS: Record<string, string> = {
  energia: "#f59e0b",
  acueducto: "#0284c7",
  alcantarillado: "#6366f1",
  telco_fibra: "#10b981",
};

const HOTSPOT_COLORS: Record<string, string> = {
  watch_single: "#eab308",
  warning_cluster: "#f97316",
  critical_dispatch: "#dc2626",
};

export const CaliMapPanel: React.FC<CaliMapPanelProps> = ({
  maintenances,
  hotspots,
  isManager,
  onSelectHotspotForDispatch,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: [3.4372, -76.5225],
      zoom: 12,
      scrollWheelZoom: true,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors | EMCALI Ops",
      maxZoom: 18,
    }).addTo(map);
    layerGroupRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerGroupRef.current = null;
    };
  }, []);

  useEffect(() => {
    const group = layerGroupRef.current;
    if (!group) return;
    group.clearLayers();

    // Capa 1: Mantenimientos Oficiales (Scraping EMCALI + Gestión)
    maintenances.forEach((m) => {
      const color = SERVICE_COLORS[m.servicio] || "#003B71";
      const marker = L.circleMarker([m.lat, m.lng], {
        radius: 9,
        color: "#0f172a",
        weight: 2,
        fillColor: color,
        fillOpacity: 0.9,
      });
      const fechaLabel = m.inicio_estimado || (m.created_at ? m.created_at.slice(0, 10) : "Hoy");
      marker.bindPopup(
        `<div style="font-size:12px;max-width:250px;">
          <div style="font-weight:700;color:#003B71;margin-bottom:3px;">🔧 ${m.titulo}</div>
          <div><b>Fecha / Inicio:</b> ${fechaLabel}${m.fin_estimado ? ` · <b>Fin:</b> ${m.fin_estimado}` : ""}</div>
          <div><b>Barrio:</b> ${m.barrio} (${m.comuna})</div>
          <div><b>Servicio:</b> ${m.servicio.toUpperCase()} · <b>Estado:</b> ${m.estado}</div>
          <div><b>Brigada:</b> ${m.brigada_asignada || "Por asignar"}</div>
          <div style="margin-top:4px;color:#475569;">${m.descripcion.slice(0, 140)}</div>
          <div style="margin-top:4px;font-size:10px;color:#64748b;">Fuente: ${m.fuente} · ID: ${m.mantenimiento_id}</div>
        </div>`
      );
      marker.addTo(group);
    });

    // Capa 2: Hotspots de Fallas Ciudadanas (Banderas para asignación de brigadas)
    hotspots.forEach((h) => {
      const color = HOTSPOT_COLORS[h.severity] || "#dc2626";
      const radius = Math.min(24, 11 + h.report_count * 3);
      const ring = L.circleMarker([h.lat, h.lng], {
        radius,
        color,
        weight: 3,
        dashArray: h.severity === "critical_dispatch" ? undefined : "4 3",
        fillColor: color,
        fillOpacity: 0.35,
      });
      const latestDate = h.latest_report_at ? h.latest_report_at.replace("T", " ").slice(0, 16) : "Reciente";
      ring.bindPopup(
        `<div style="font-size:12px;max-width:250px;">
          <div style="font-weight:700;color:${color};margin-bottom:3px;">⚠️ ${h.severity_label}</div>
          <div><b>Último reporte:</b> ${latestDate} UTC</div>
          <div><b>Barrio:</b> ${h.barrio} (${h.comuna})</div>
          <div><b>Servicio:</b> ${h.servicio.toUpperCase()}</div>
          <div><b>Reportes abiertos:</b> ${h.report_count}</div>
          <div style="margin-top:4px;font-size:11px;color:#475569;">
            ${
              isManager
                ? "Haz clic en 'Despachar Brigada' en el panel lateral para convertir en mantenimiento oficial."
                : "Reportes ciudadanos recibidos; equipo técnico EMCALI monitoreando."
            }
          </div>
        </div>`
      );
      if (isManager && onSelectHotspotForDispatch) {
        ring.on("click", () => onSelectHotspotForDispatch(h));
      }
      ring.addTo(group);
    });
  }, [maintenances, hotspots, isManager, onSelectHotspotForDispatch]);

  return (
    <div className="space-y-2">
      <div
        ref={containerRef}
        className="w-full h-[430px] rounded-xl border border-slate-200 shadow-inner z-10"
      />
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-600 px-1">
        <span className="font-semibold text-slate-800">Leyenda:</span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#f59e0b] inline-block border border-slate-700" />
          Energía
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#0284c7] inline-block border border-slate-700" />
          Acueducto
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#6366f1] inline-block border border-slate-700" />
          Alcantarillado
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#10b981] inline-block border border-slate-700" />
          Telco Fibra
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#dc2626]/40 border-2 border-[#dc2626] inline-block" />
          Hotspot Fallas (Brigada Sugerida)
        </span>
      </div>
    </div>
  );
};
