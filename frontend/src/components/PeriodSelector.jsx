import React, { useState } from 'react';
import {
  Calendar,
  ChevronDown,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Clock,
  User,
  RotateCcw,
  Sparkles,
  X
} from 'lucide-react';

const MONTHS_LIST = [
  { value: 1, label: 'Januari' },
  { value: 2, label: 'Februari' },
  { value: 3, label: 'Maret' },
  { value: 4, label: 'April' },
  { value: 5, label: 'Mei' },
  { value: 6, label: 'Juni' },
  { value: 7, label: 'Juli' },
  { value: 8, label: 'Agustus' },
  { value: 9, label: 'September' },
  { value: 10, label: 'Oktober' },
  { value: 11, label: 'November' },
  { value: 12, label: 'Desember' },
];

export default function PeriodSelector({
  periods = [],
  selectedPeriodId = '2026-09-das2',
  periodMode = 'auto',
  onSelectPeriod,
  onSwitchToRealtime,
  loading = false,
}) {
  const currentPeriod = periods.find((p) => p.period_id === selectedPeriodId) || periods[0] || null;
  const [showCustomModal, setShowCustomModal] = useState(false);

  // Custom picker state
  const [customYear, setCustomYear] = useState(2026);
  const [customMonth, setCustomMonth] = useState(10);
  const [customDasarian, setCustomDasarian] = useState('das3');

  const handleDropdownChange = (e) => {
    const val = e.target.value;
    if (val === '__CUSTOM__') {
      setShowCustomModal(true);
    } else {
      onSelectPeriod && onSelectPeriod(val);
    }
  };

  const handleApplyCustomPeriod = (e) => {
    e.preventDefault();
    const pid = `${customYear}-${String(customMonth).padStart(2, '0')}-${customDasarian}`;
    setShowCustomModal(false);
    onSelectPeriod && onSelectPeriod(pid);
  };

  return (
    <div className="period-selector-container">
      {/* TIER 1: Header Status Bar (Label, Mode Badge, Switch Button, and Data Status) */}
      <div className="period-selector-header">
        <div className="period-header-left">
          <label htmlFor="dss-period-dropdown" className="period-selector-label">
            <Calendar size={13} className="text-forest" />
            <span>Periode Peringatan Dini</span>
          </label>

          {/* Operating Mode Indicator (Real-Time vs Manual) */}
          {periodMode === 'manual' ? (
            <span
              className="period-mode-badge badge-manual"
              title="Sistem menggunakan periode manual pilihan petugas (tersimpan di server)"
            >
              <User size={11} />
              <span>Mode Manual</span>
            </span>
          ) : (
            <span
              className="period-mode-badge badge-auto"
              title="Sistem otomatis mengikuti tanggal aktual server dalam zona waktu Asia/Jakarta (WIB)"
            >
              <Clock size={11} />
              <span>Real-Time</span>
            </span>
          )}
        </div>

        <div className="period-header-right">
          {periodMode === 'manual' && (
            <button
              type="button"
              className="btn-switch-realtime"
              onClick={onSwitchToRealtime}
              disabled={loading}
              title="Kembalikan sistem ke mode otomatis mengikuti waktu kalender server (Asia/Jakarta)"
            >
              <RotateCcw size={11} />
              <span>Ikuti Waktu Real-time</span>
            </button>
          )}

          {loading ? (
            <span className="period-loading-badge">
              <Loader2 size={11} className="spin" />
              <span>Memuat...</span>
            </span>
          ) : (
            currentPeriod && (
              currentPeriod.is_forecast ? (
                <span className="period-status-badge badge-forecast bg-purple-100 text-purple-800 border border-purple-300" title="Periode Prakiraan — Belum menjadi periode observasi">
                  <Sparkles size={11} className="text-purple-600" />
                  <span>Prakiraan (+1)</span>
                </span>
              ) : currentPeriod.has_complete_data ? (
                <span className="period-status-badge badge-verified" title="Semua parameter observasi, SPI, dan ECMWF terverifikasi lengkap">
                  <CheckCircle2 size={11} />
                  <span>Terverifikasi</span>
                </span>
              ) : (
                <span className="period-status-badge badge-partial" title="Sebagian parameter tidak tersedia atau belum lengkap">
                  <AlertCircle size={11} />
                  <span>Data Parsial</span>
                </span>
              )
            )
          )}
        </div>
      </div>

      {/* TIER 2: Dropdown Dasarian Selector spanning full width */}
      <div className="period-dropdown-box">
        <select
          id="dss-period-dropdown"
          className="period-dropdown-select"
          value={selectedPeriodId}
          onChange={handleDropdownChange}
          disabled={loading}
          title="Pilih salah satu dari dasarian dalam jendela aktif atau tentukan periode lain"
        >
          {periods.map((p) => (
            <option key={p.period_id} value={p.period_id}>
              {p.label} ({p.date_range}){p.is_default ? ' — [Aktif]' : ''}{p.is_forecast ? ' 🔮 [Prakiraan]' : ''}
            </option>
          ))}
          <option value="__CUSTOM__">➕ Pilih Periode Dasarian Lain...</option>
        </select>
        <ChevronDown size={14} className="period-dropdown-caret" />
      </div>

      {/* Modal / Popover Pemilihan Periode Bebas Lintas Bulan & Tahun */}
      {showCustomModal && (
        <div className="custom-period-modal-backdrop" onClick={() => setShowCustomModal(false)}>
          <div className="custom-period-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="custom-period-modal-header">
              <div className="flex-align gap-2">
                <Sparkles size={16} className="text-forest" />
                <h4>Pilih Periode Dasarian Manual</h4>
              </div>
              <button
                type="button"
                className="btn-modal-close"
                onClick={() => setShowCustomModal(false)}
                title="Tutup"
              >
                <X size={16} />
              </button>
            </div>
            <p className="custom-period-modal-desc">
              Tentukan dasarian target secara eksplisit. Jendela 10 dasarian akan otomatis digeser
              dengan dasarian yang Anda pilih sebagai periode aktif.
            </p>

            <form onSubmit={handleApplyCustomPeriod} className="custom-period-form">
              <div className="custom-form-grid">
                <div className="form-group">
                  <label htmlFor="custom-year">Tahun</label>
                  <select
                    id="custom-year"
                    value={customYear}
                    onChange={(e) => setCustomYear(parseInt(e.target.value, 10))}
                  >
                    <option value={2024}>2024</option>
                    <option value={2025}>2025</option>
                    <option value={2026}>2026</option>
                    <option value={2027}>2027</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="custom-month">Bulan</label>
                  <select
                    id="custom-month"
                    value={customMonth}
                    onChange={(e) => setCustomMonth(parseInt(e.target.value, 10))}
                  >
                    {MONTHS_LIST.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="custom-dasarian">Dasarian</label>
                  <select
                    id="custom-dasarian"
                    value={customDasarian}
                    onChange={(e) => setCustomDasarian(e.target.value)}
                  >
                    <option value="das1">Dasarian I (1–10)</option>
                    <option value="das2">Dasarian II (11–20)</option>
                    <option value="das3">Dasarian III (21–Akhir Bulan)</option>
                  </select>
                </div>
              </div>

              <div className="custom-period-modal-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCustomModal(false)}
                >
                  Batal
                </button>
                <button type="submit" className="btn btn-primary">
                  Terapkan Periode
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
