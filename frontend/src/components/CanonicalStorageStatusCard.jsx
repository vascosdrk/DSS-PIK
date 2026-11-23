import React, { useState } from 'react';
import { INSTITUTION_NAME } from '../config';
import {
  Database,
  CloudRain,
  Activity,
  BarChart2,
  Calendar,
  TrendingUp,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  Radio,
  Layers,
  X
} from 'lucide-react';

/**
 * CanonicalStorageStatusCard
 * Kartu Monitoring Status Data Operasional (Canonical Storage) BMKG Kepulauan Riau
 * Desain modern, terang (white card), ringkas, dan selaras dengan Dashboard DSS-PIK.
 */
export default function CanonicalStorageStatusCard({
  latestStatus,
  loadingStatus,
  onRefresh,
  compact = false,
}) {
  const [showMissingModal, setShowMissingModal] = useState(false);

  const ch = latestStatus?.curah_hujan;
  const spiH30 = latestStatus?.spi_harian_30d;
  const spiH90 = latestStatus?.spi_harian_90d;
  const spiD30 = latestStatus?.spi_dasarian_30d;
  const spiD90 = latestStatus?.spi_dasarian_90d;
  const spiM = latestStatus?.spi_bulanan;
  const probD = latestStatus?.probabilitas_dasarian;
  const probM = latestStatus?.probabilitas_bulanan;

  const coveragePct = ch?.coverage_pct ?? 0;
  const missingCount = ch?.missing_stations_count ?? 0;
  const missingStations = ch?.missing_stations ?? ch?.missing_stations_list ?? [];

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 sm:p-5 text-slate-800 mb-6">
      {/* A. HEADER STATUS */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-forest-light/10 border border-forest/20 rounded-lg text-forest">
            <Database size={22} />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base sm:text-lg font-bold text-slate-800 tracking-wide">
                Status Data Operasional (Canonical Storage)
              </h3>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
                LIVE
              </span>
              <span className="hidden md:inline-flex items-center text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
                MariaDB &amp; Parquet Aktif
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Monitoring Kesiapan Data Real-Time {INSTITUTION_NAME}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between sm:justify-end space-x-3">
          <div className="text-right text-[11px] text-slate-500">
            <span>Pemeriksaan: </span>
            <span className="font-mono text-slate-700 font-semibold">
              {latestStatus?.checked_at ? `${latestStatus.checked_at} WIB` : '—'}
            </span>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loadingStatus}
              title="Segarkan status data operasional real-time"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-lg text-xs font-semibold transition shadow-sm disabled:opacity-50"
            >
              <RefreshCw size={13} className={loadingStatus ? 'animate-spin text-forest' : 'text-slate-500'} />
              <span>{loadingStatus ? 'Memeriksa...' : 'Segarkan Status Penyimpanan'}</span>
            </button>
          )}
        </div>
      </div>

      {/* B. BARIS 1: CURAH HUJAN HARIAN */}
      <div className="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-3 sm:p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
              <CloudRain size={20} />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">Curah Hujan Harian</span>
                <span className="text-[11px] px-1.5 py-0.2 rounded bg-blue-50 text-blue-700 border border-blue-200 font-medium">MariaDB</span>
              </div>
              <div className="flex items-center space-x-4 text-xs text-slate-600 mt-1">
                <span>Tanggal Terakhir: <strong className="font-mono text-slate-800">{ch?.latest_date || '—'}</strong></span>
                <span className="text-slate-300">|</span>
                <span>Dasarian: <strong className="text-slate-800">{ch?.latest_dasarian_label || '—'}</strong></span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between md:justify-end space-x-4">
            <div className="text-right">
              <div className="text-xs text-slate-600">
                Pos Melapor: <strong className="font-mono text-slate-900">{ch?.reported_stations_count ?? 0}</strong> / {ch?.total_stations_master ?? 57} Pos ({coveragePct.toFixed(1)}%)
              </div>
              <div className="w-36 sm:w-44 bg-slate-200 rounded-full h-2 mt-1.5 overflow-hidden">
                <div
                  className="bg-emerald-600 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, coveragePct))}%` }}
                />
              </div>
            </div>

            {missingCount > 0 && (
              <button
                type="button"
                onClick={() => setShowMissingModal(true)}
                className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 rounded-md transition shadow-xs"
                title="Lihat daftar pos yang belum melapor"
              >
                <AlertTriangle size={12} className="text-amber-600" />
                <span>{missingCount} Pos Belum Melapor</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* C. BARIS 2: SPI MULTI-SKALA (5 KARTU) */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <BarChart2 size={15} className="text-forest" />
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">
              Monitoring SPI Multi-Skala (Parquet)
            </span>
          </div>
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
            Cakupan: 57 Stasiun
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
          {/* Card 1: SPI Harian 30D */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 hover:border-slate-300 transition">
            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
              <span className="font-semibold text-slate-700">Harian 30D</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            </div>
            <div className="font-mono text-xs font-bold text-slate-900">{spiH30?.latest_date || '—'}</div>
            <div className="text-[11px] text-slate-500 mt-1">
              Pos: <strong className="text-slate-800">{spiH30?.stations_count ?? 0}</strong>/57 Stasiun
            </div>
          </div>

          {/* Card 2: SPI Harian 90D */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 hover:border-slate-300 transition">
            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
              <span className="font-semibold text-slate-700">Harian 90D</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            </div>
            <div className="font-mono text-xs font-bold text-slate-900">{spiH90?.latest_date || '—'}</div>
            <div className="text-[11px] text-slate-500 mt-1">
              Pos: <strong className="text-slate-800">{spiH90?.stations_count ?? 0}</strong>/57 Stasiun
            </div>
          </div>

          {/* Card 3: SPI Dasarian 30D */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 hover:border-slate-300 transition">
            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
              <span className="font-semibold text-slate-700">Dasarian 30D</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            </div>
            <div className="font-mono text-xs font-bold text-slate-900">{spiD30?.latest_date || '—'}</div>
            <div className="text-[11px] text-slate-500 mt-1">
              Pos: <strong className="text-slate-800">{spiD30?.stations_count ?? 0}</strong>/57 Stasiun
            </div>
          </div>

          {/* Card 4: SPI Dasarian 90D */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 hover:border-slate-300 transition">
            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
              <span className="font-semibold text-slate-700">Dasarian 90D</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            </div>
            <div className="font-mono text-xs font-bold text-slate-900">{spiD90?.latest_date || '—'}</div>
            <div className="text-[11px] text-slate-500 mt-1">
              Pos: <strong className="text-slate-800">{spiD90?.stations_count ?? 0}</strong>/57 Stasiun
            </div>
          </div>

          {/* Card 5: SPI Bulanan */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 hover:border-slate-300 transition">
            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
              <span className="font-semibold text-slate-700">Bulanan</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            </div>
            <div className="font-mono text-xs font-bold text-slate-900">{spiM?.latest_date || '—'}</div>
            <div className="text-[11px] text-slate-500 mt-1">
              Pos: <strong className="text-slate-800">{spiM?.stations_count ?? 0}</strong>/57 Stasiun
            </div>
          </div>
        </div>
      </div>

      {/* D. BARIS 3: PROBABILITAS ECMWF (2 KARTU) */}
      <div className="mt-4">
        <div className="flex items-center space-x-2 mb-2">
          <TrendingUp size={15} className="text-purple-600" />
          <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">
            Prakiraan Probabilistik ECMWF (Canonical Snapshot Store)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Probabilitas Dasarian */}
          <div className="bg-purple-50/50 border border-purple-200/80 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-purple-900">Probabilitas Dasarian</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                TERSEDIA
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-500 block text-[11px]">Periode Target:</span>
                <strong className="text-slate-800 font-mono">{probD?.latest_target_period || '—'}</strong>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Tanggal Penerbitan:</span>
                <strong className="text-slate-800 font-mono">{probD?.latest_issue_date || '—'}</strong>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Cakupan Pos:</span>
                <span className="text-slate-800"><strong>{probD?.stations_count ?? 0}</strong>/57 Stasiun</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Indikator Operasional:</span>
                <span className="text-slate-800">pb20, pa150, pa200, pa300</span>
              </div>
            </div>
          </div>

          {/* Probabilitas Bulanan */}
          <div className="bg-indigo-50/50 border border-indigo-200/80 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-indigo-900">Probabilitas Bulanan</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                TERSEDIA
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-500 block text-[11px]">Bulan Target:</span>
                <strong className="text-slate-800 font-mono">{probM?.latest_target_period || '—'}</strong>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Tanggal Penerbitan:</span>
                <strong className="text-slate-800 font-mono">{probM?.latest_issue_date || '—'}</strong>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Cakupan Pos:</span>
                <span className="text-slate-800"><strong>{probM?.stations_count ?? 0}</strong>/57 Stasiun</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[11px]">Indikator Operasional:</span>
                <span className="text-slate-800">pa300, pa400, pa500</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* MODAL: DAFTAR POS BELUM MELAPOR */}
      {showMissingModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full max-h-[85vh] flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center space-x-2 text-amber-800">
                <AlertTriangle size={18} />
                <h4 className="font-bold text-sm">Daftar Pos Belum Melapor ({missingCount} Pos)</h4>
              </div>
              <button
                type="button"
                onClick={() => setShowMissingModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-4 overflow-y-auto divide-y divide-slate-100 text-xs">
              {missingStations.length === 0 ? (
                <p className="text-center text-slate-500 py-4 italic">Semua stasiun telah melapor pada tanggal cutoff.</p>
              ) : (
                missingStations.map((stn, idx) => (
                  <div key={stn.station_id || idx} className="py-2 flex items-center justify-between">
                    <div>
                      <span className="font-mono font-medium text-slate-800">{stn.station_id}</span>
                      <span className="ml-2 text-slate-700">{stn.station_name}</span>
                    </div>
                    <span className="text-slate-400 text-[11px]">{stn.kabupaten || '—'}</span>
                  </div>
                ))
              )}
            </div>
            <div className="px-5 py-3 border-t border-slate-200 bg-slate-50 text-right">
              <button
                type="button"
                onClick={() => setShowMissingModal(false)}
                className="px-4 py-1.5 bg-slate-700 hover:bg-slate-800 text-white text-xs font-medium rounded-lg"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
