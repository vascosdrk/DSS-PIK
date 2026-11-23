import React from 'react';
import { 
  Sun, 
  CloudRain, 
  CheckCircle2, 
  AlertCircle, 
  AlertTriangle, 
  Flame, 
  HelpCircle,
  Layers
} from 'lucide-react';

export default function KpiCards({ 
  counts, 
  pdkmCounts, 
  pdchtCounts, 
  activeHazardTab = 'PDKM', // 'PDKM' | 'PDCHT'
  onSelectHazardTab,
  selectedFilter, 
  onSelectFilter 
}) {
  // Defensive fallbacks
  const pdkm = pdkmCounts || { total: 57, AMAN: 0, WASPADA: 0, SIAGA: 0, AWAS: 0, INSUFFICIENT: 0 };
  const pdcht = pdchtCounts || { total: 57, AMAN: 0, WASPADA: 0, SIAGA: 0, AWAS: 0, INSUFFICIENT: 0 };

  const activeCounts = activeHazardTab === 'PDCHT' ? pdcht : pdkm;

  const cards = [
    {
      id: 'ALL',
      title: 'TOTAL STASIUN',
      count: activeCounts.total || 57,
      icon: Layers,
      colorClass: 'kpi-total',
      description: 'Seluruh titik pemantauan Kepri',
    },
    {
      id: 'AMAN',
      title: 'AMAN / NORMAL',
      count: (activeCounts.AMAN || activeCounts.NORMAL || 0),
      icon: CheckCircle2,
      colorClass: 'kpi-normal',
      description: activeHazardTab === 'PDKM' ? 'Indikator kekeringan aman' : 'Probabilitas curah hujan tinggi aman',
    },
    {
      id: 'WASPADA',
      title: 'WASPADA',
      count: activeCounts.WASPADA || 0,
      icon: AlertCircle,
      colorClass: 'kpi-waspada',
      description: activeHazardTab === 'PDKM' ? 'Indikasi awal kekeringan (HTH / SPI / Pb20)' : 'Peluang curah hujan tinggi waspada (>50%)',
      highlightBadge: activeCounts.WASPADA > 0 ? `${activeCounts.WASPADA} Titik` : null,
    },
    {
      id: 'SIAGA',
      title: 'SIAGA',
      count: activeCounts.SIAGA || 0,
      icon: AlertTriangle,
      colorClass: 'kpi-siaga',
      description: activeHazardTab === 'PDKM' ? 'Peluang kekeringan signifikan (HTH / SPI)' : 'Peluang curah hujan tinggi siaga (>50%)',
      highlightBadge: activeCounts.SIAGA > 0 ? `${activeCounts.SIAGA} Titik` : null,
    },
    {
      id: 'AWAS',
      title: 'AWAS',
      count: activeCounts.AWAS || 0,
      icon: Flame,
      colorClass: 'kpi-awas',
      description: activeHazardTab === 'PDKM' ? 'Kekeringan ekstrem terverifikasi' : 'Peluang curah hujan ekstrem (>50%)',
      highlightBadge: activeCounts.AWAS > 0 ? `${activeCounts.AWAS} Titik` : null,
    },
    {
      id: 'INSUFFICIENT',
      title: 'DATA TIDAK CUKUP',
      count: (activeCounts.INSUFFICIENT || activeCounts.INCOMPLETE || 0),
      icon: HelpCircle,
      colorClass: 'kpi-incomplete',
      description: 'Parameter masukan belum lengkap',
      highlightBadge: (activeCounts.INSUFFICIENT || activeCounts.INCOMPLETE) > 0 
        ? `${activeCounts.INSUFFICIENT || activeCounts.INCOMPLETE} Titik` 
        : null,
    },
  ];

  return (
    <div className="dual-hazard-kpi-container mb-4">
      {/* 1. Hazard Mode Switcher Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3 bg-white p-2.5 rounded-xl border border-slate-200 shadow-2xs">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold text-slate-700 tracking-wide uppercase">
            Ringkasan Statistik Bahaya (Dual Hazard Status):
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeHazardTab === 'PDKM'
                ? 'bg-amber-600 text-white shadow-sm ring-2 ring-amber-300'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
            onClick={() => onSelectHazardTab && onSelectHazardTab('PDKM')}
            title="Tampilkan statistik Peringatan Dini Kekeringan Meteorologis"
          >
            <Sun size={15} />
            <span>PDKM (Kekeringan)</span>
            <span className={`ml-1 px-1.5 py-0.2 rounded-full text-[10px] ${activeHazardTab === 'PDKM' ? 'bg-amber-700 text-amber-100' : 'bg-slate-200 text-slate-700'}`}>
              {(pdkm.WASPADA || 0) + (pdkm.SIAGA || 0) + (pdkm.AWAS || 0)} Peringatan
            </span>
          </button>

          <button
            type="button"
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeHazardTab === 'PDCHT'
                ? 'bg-blue-600 text-white shadow-sm ring-2 ring-blue-300'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
            onClick={() => onSelectHazardTab && onSelectHazardTab('PDCHT')}
            title="Tampilkan statistik Peringatan Dini Curah Hujan Tinggi"
          >
            <CloudRain size={15} />
            <span>PDCHT (Hujan Tinggi)</span>
            <span className={`ml-1 px-1.5 py-0.2 rounded-full text-[10px] ${activeHazardTab === 'PDCHT' ? 'bg-blue-700 text-blue-100' : 'bg-slate-200 text-slate-700'}`}>
              {(pdcht.WASPADA || 0) + (pdcht.SIAGA || 0) + (pdcht.AWAS || 0)} Peringatan
            </span>
          </button>
        </div>
      </div>

      {/* 2. KPI Cards Grid */}
      <div className="kpi-grid">
        {cards.map((card) => {
          const IconComponent = card.icon;
          const isActive = selectedFilter === card.id;
          return (
            <div
              key={card.id}
              className={`kpi-card ${card.colorClass} ${isActive ? 'active' : ''}`}
              onClick={() => onSelectFilter(card.id)}
              role="button"
              tabIndex={0}
              title={`Filter stasiun dengan status ${card.title} pada mode ${activeHazardTab}`}
            >
              <div className="kpi-card-header">
                <span className="kpi-card-title">{card.title}</span>
                <div className="kpi-icon-wrapper">
                  <IconComponent size={18} />
                </div>
              </div>

              <div className="kpi-card-body">
                <span className="kpi-count">{card.count}</span>
                {card.highlightBadge && (
                  <span className="kpi-status-badge">{card.highlightBadge}</span>
                )}
              </div>

              <div className="kpi-card-footer">
                <span className="kpi-desc">{card.description}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
