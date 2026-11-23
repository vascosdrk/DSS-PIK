import React, { useState, useMemo, useEffect } from 'react';
import {
  CloudRain,
  Sun,
  AlertCircle,
  TrendingUp,
  Droplets,
  Calendar,
  BarChart2,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Sparkles,
  Info,
  RotateCcw,
} from 'lucide-react';
import { formatDateIndo } from '../utils/formatters';

/**
 * Komponen Ringkasan Statistik Stasiun & Visualisasi Deret Observasi
 * Dilengkapi kontrol rentang tanggal dinamis (Bagian B1–B5 DSS-PIK).
 * D1: 8 Statistik Utama + Median
 * D2: Statistik Tambahan (Expandable)
 * D3: Aturan Perhitungan Ketat (Cutoff, Missing break streak, TTU = 0 mm Jejak Hujan)
 */
export default function RainfallObservationSummary({
  data = [],
  periodStart,
  periodEnd,
  stationName,
  stationId,
  loading = false,
  error = null,
  cutoffDate = '2026-09-20',
  isCustomRange = false,
  onApplyRange,
  onResetRange,
  showTableToggle = true,
}) {
  const [showTable, setShowTable] = useState(true);
  const [showAdditional, setShowAdditional] = useState(false);

  // Dynamic Date Controls State
  const [startDateInput, setStartDateInput] = useState(periodStart || '');
  const [endDateInput, setEndDateInput] = useState(periodEnd || '');
  const [dateError, setDateError] = useState('');

  // Sync inputs with active props
  useEffect(() => {
    if (periodStart) setStartDateInput(periodStart);
    if (periodEnd) setEndDateInput(periodEnd);
    setDateError('');
  }, [periodStart, periodEnd]);

  const handleApply = (e) => {
    if (e) e.preventDefault();
    if (!startDateInput || !endDateInput) {
      setDateError('Tanggal awal dan tanggal akhir harus ditentukan.');
      return;
    }
    if (startDateInput > endDateInput) {
      setDateError('Tanggal awal tidak boleh melebihi tanggal akhir.');
      return;
    }
    setDateError('');
    if (onApplyRange) {
      onApplyRange(startDateInput, endDateInput);
    }
  };

  const handleReset = (e) => {
    if (e) e.preventDefault();
    setDateError('');
    if (onResetRange) {
      onResetRange();
    }
  };

  const isBeyondCutoff = useMemo(() => {
    if (!cutoffDate || !periodEnd) return false;
    return periodEnd > cutoffDate;
  }, [cutoffDate, periodEnd]);

  // Perhitungan Statistik Observasi Curah Hujan (D1 & D2)
  const stats = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        totalCh: 0,
        avgCh: 0,
        medianCh: 0,
        maxCh: 0,
        maxChDate: null,
        rainDays: 0,
        dryDays: 0,
        validDays: 0,
        missingDays: 0,
        completeness: 0,
        totalDays: 0,
        minPositiveCh: null,
        minPositiveDate: null,
        stdDev: 0,
        daysGte20: 0,
        daysGte50: 0,
        daysGte100: 0,
        longestDryStreak: 0,
        longestWetStreak: 0,
      };
    }

    const totalDays = data.length;
    let total = 0;
    let validCount = 0;
    let rainCount = 0;
    let dryCount = 0;
    let missingCount = 0;
    let maxVal = -1;
    let maxDate = null;
    let minPosVal = Infinity;
    let minPosDate = null;
    let daysGte20 = 0;
    let daysGte50 = 0;
    let daysGte100 = 0;

    const validVals = [];

    // Streak trackers (wajib berhenti / putus saat menemukan data missing)
    let currentDryStreak = 0;
    let maxDryStreak = 0;
    let currentWetStreak = 0;
    let maxWetStreak = 0;

    data.forEach((item) => {
      const val = item.rainfall_mm;
      const isMissing =
        val === null ||
        val === undefined ||
        item.status === 'Tidak tersedia' ||
        (item.obs_status && String(item.obs_status).startsWith('MISSING'));

      if (isMissing) {
        missingCount += 1;
        // Tanggal missing memutuskan rangkaian hari kering dan basah
        currentDryStreak = 0;
        currentWetStreak = 0;
      } else {
        validCount += 1;
        total += val;
        validVals.push(val);

        if (val >= 1.0) {
          rainCount += 1;
          currentWetStreak += 1;
          if (currentWetStreak > maxWetStreak) maxWetStreak = currentWetStreak;
          currentDryStreak = 0;
        } else {
          // CH < 1.0 mm (termasuk 0.0 mm dan TTU)
          dryCount += 1;
          currentDryStreak += 1;
          if (currentDryStreak > maxDryStreak) maxDryStreak = currentDryStreak;
          currentWetStreak = 0;
        }

        if (val > maxVal) {
          maxVal = val;
          maxDate = item.date;
        }

        if (val > 0 && val < minPosVal) {
          minPosVal = val;
          minPosDate = item.date;
        }

        if (val >= 20.0) daysGte20 += 1;
        if (val >= 50.0) daysGte50 += 1;
        if (val >= 100.0) daysGte100 += 1;
      }
    });

    const avg = validCount > 0 ? total / validCount : 0;
    const completeness = totalDays > 0 ? (validCount / totalDays) * 100 : 0;

    // Median CH harian observasi valid
    let median = 0;
    if (validVals.length > 0) {
      const sorted = [...validVals].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      median = sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    }

    // Simpangan baku (sample standard deviation jika > 1 observasi)
    let stdDev = 0;
    if (validCount > 1) {
      const sumSquares = validVals.reduce((acc, v) => acc + Math.pow(v - avg, 2), 0);
      stdDev = Math.sqrt(sumSquares / (validCount - 1));
    }

    return {
      totalCh: total,
      avgCh: avg,
      medianCh: median,
      maxCh: maxVal >= 0 ? maxVal : 0,
      maxChDate: maxDate,
      rainDays: rainCount,
      dryDays: dryCount,
      validDays: validCount,
      missingDays: missingCount,
      completeness,
      totalDays,
      minPositiveCh: minPosVal !== Infinity ? minPosVal : null,
      minPositiveDate: minPosDate,
      stdDev,
      daysGte20,
      daysGte50,
      daysGte100,
      longestDryStreak: maxDryStreak,
      longestWetStreak: maxWetStreak,
    };
  }, [data]);

  // Format short date for chart axis (e.g., '15 Sep')
  const formatShortDate = (dStr) => {
    if (!dStr) return '';
    try {
      const parts = dStr.split('-');
      if (parts.length === 3) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
        return `${parseInt(parts[2], 10)} ${months[parseInt(parts[1], 10) - 1]}`;
      }
      return dStr;
    } catch {
      return dStr;
    }
  };

  return (
    <div className="rainfall-observation-section">
      {/* Header Ringkasan Statistik */}
      <div className="rainfall-obs-header">
        <div className="flex-align gap-2">
          <BarChart2 size={16} className="text-forest" />
          <h4 className="rainfall-obs-title">Ringkasan Statistik Observasi</h4>
          {isCustomRange && (
            <span className="badge-custom-tag">Rentang Kustom</span>
          )}
        </div>
        {periodStart && periodEnd && (
          <span className="rainfall-obs-period-badge">
            <Calendar size={11} className="inline-icon" />
            {formatShortDate(periodStart)} – {formatShortDate(periodEnd)} ({stats.totalDays} hari)
          </span>
        )}
      </div>

      {/* Kontrol Rentang Tanggal Dinamis (Bagian B1) */}
      <div className="rainfall-range-controls-panel">
        <div className="range-controls-row">
          <div className="range-input-group">
            <span className="range-label">
              <Calendar size={13} className="inline-icon text-muted" />
              Rentang Analisis:
            </span>
            <div className="range-dates-inline">
              <input
                type="date"
                className="input-date-custom"
                value={startDateInput}
                onChange={(e) => {
                  setStartDateInput(e.target.value);
                  setDateError('');
                }}
                disabled={loading}
              />
              <span className="range-sep">s/d</span>
              <input
                type="date"
                className="input-date-custom"
                value={endDateInput}
                onChange={(e) => {
                  setEndDateInput(e.target.value);
                  setDateError('');
                }}
                disabled={loading}
              />
            </div>
          </div>

          <div className="range-buttons-group">
            <button
              type="button"
              className="btn-apply-range"
              onClick={handleApply}
              disabled={loading}
            >
              Terapkan
            </button>
            <button
              type="button"
              className="btn-reset-range"
              onClick={handleReset}
              disabled={loading}
              title="Kembali ke rentang default 15 hari sesuai cutoff peringatan"
            >
              <RotateCcw size={12} className="inline-icon" />
              Reset (15 Hari)
            </button>
          </div>
        </div>

        {dateError && (
          <div className="range-error-msg">
            <AlertCircle size={13} className="inline-icon text-red" />
            <span>{dateError}</span>
          </div>
        )}

        <div className="range-disclaimer-row">
          <span className="range-disclaimer-tag">Filter Analisis Observasi</span>
          <span className="range-disclaimer-text">
            Pengaturan rentang ini hanya memengaruhi ringkasan statistik dan visualisasi deret harian di bawah ini. HTH operasional, SPI, probabilitas, dan status peringatan stasiun tidak berubah.
          </span>
        </div>

        {isBeyondCutoff && (
          <div className="range-cutoff-notice">
            <Info size={13} className="inline-icon text-amber-700" />
            <span>
              Rentang observasi mencakup tanggal setelah cutoff peringatan ({formatDateIndo(cutoffDate)}). Indikator peringatan tetap mengacu pada cutoff operasional.
            </span>
          </div>
        )}
      </div>

      {loading && (
        <div className="rainfall-obs-box loading">
          <div className="spin spinner-sm"></div>
          <span>Memuat data ringkasan statistik observasi curah hujan...</span>
        </div>
      )}

      {error && !loading && (
        <div className="rainfall-obs-box error">
          <AlertCircle size={16} className="text-amber-700" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && (!data || data.length === 0 || stats.validDays === 0) && (
        <div className="rainfall-obs-box empty-alert">
          <AlertCircle size={20} className="text-amber-600" />
          <div>
            <h5 className="font-semibold text-sm">Data Observasi Tidak Tersedia</h5>
            <p className="text-xs text-muted mt-1">
              Tidak ada rekaman observasi valid untuk stasiun ini pada rentang yang dipilih ({periodStart ? formatShortDate(periodStart) : '-'} – {periodEnd ? formatShortDate(periodEnd) : '-'}). Silakan sesuaikan tanggal atau periksa data curah hujan.
            </p>
          </div>
        </div>
      )}

      {!loading && !error && stats.validDays > 0 && (
        <>
          {/* D1: Grid 8 Statistik Utama + Median */}
          <div className="rainfall-stats-grid">
        {/* 1. Total CH */}
        <div className="rainfall-stat-card">
          <span className="rstat-label">Total Curah Hujan</span>
          <span className="rstat-val font-mono">{stats.totalCh.toFixed(1)} <small>mm</small></span>
          <span className="rstat-sub text-muted">Akumulasi {stats.validDays} hari valid</span>
        </div>

        {/* 2. Rata-rata CH Valid */}
        <div className="rainfall-stat-card">
          <span className="rstat-label">Rata-rata Harian</span>
          <span className="rstat-val font-mono">{stats.avgCh.toFixed(1)} <small>mm/hr</small></span>
          <span className="rstat-sub text-muted">Per hari observasi valid</span>
        </div>

        {/* 3. Median CH */}
        <div className="rainfall-stat-card">
          <span className="rstat-label">Median Harian</span>
          <span className="rstat-val font-mono">{stats.medianCh.toFixed(1)} <small>mm/hr</small></span>
          <span className="rstat-sub text-muted">Nilai tengah hari valid</span>
        </div>

        {/* 4. CH Maksimum */}
        <div className="rainfall-stat-card">
          <span className="rstat-label">CH Maksimum</span>
          <span className="rstat-val font-mono highlight-ch">{stats.maxCh.toFixed(1)} <small>mm</small></span>
          <span className="rstat-sub font-mono text-xs">
            {stats.maxChDate ? formatShortDate(stats.maxChDate) : '-'}
          </span>
        </div>

        {/* 5. Hari Hujan (>= 1 mm) */}
        <div className="rainfall-stat-card">
          <span className="rstat-label flex-align gap-1">
            <Droplets size={12} className="text-emerald-700" />
            Hari Hujan (≥ 1 mm)
          </span>
          <span className="rstat-val font-mono text-emerald-800">{stats.rainDays} <small>hari</small></span>
          <span className="rstat-sub text-muted">Observasi basah</span>
        </div>

        {/* 6. Hari Tanpa Hujan (< 1 mm) */}
        <div className="rainfall-stat-card">
          <span className="rstat-label flex-align gap-1">
            <Sun size={12} className="text-amber-700" />
            Hari Tanpa Hujan (&lt; 1 mm)
          </span>
          <span className="rstat-val font-mono text-amber-800">{stats.dryDays} <small>hari</small></span>
          <span className="rstat-sub text-muted">Termasuk 0 mm &amp; TTU</span>
        </div>

        {/* 7. Hari Observasi Valid */}
        <div className="rainfall-stat-card">
          <span className="rstat-label flex-align gap-1">
            <CheckCircle2 size={12} className="text-blue-700" />
            Hari Valid
          </span>
          <span className="rstat-val font-mono text-blue-800">{stats.validDays} <small>hari</small></span>
          <span className="rstat-sub text-muted">Tersedia untuk evaluasi</span>
        </div>

        {/* 8. Hari Missing */}
        <div className="rainfall-stat-card">
          <span className="rstat-label flex-align gap-1">
            <AlertCircle size={12} className={stats.missingDays > 0 ? 'text-red' : 'text-muted'} />
            Data Missing
          </span>
          <span className={`rstat-val font-mono ${stats.missingDays > 0 ? 'text-red' : 'text-muted'}`}>
            {stats.missingDays} <small>hari</small>
          </span>
          <span className="rstat-sub text-muted">Tidak ada data observasi</span>
        </div>

        {/* 9. Kelengkapan Data */}
        <div className="rainfall-stat-card">
          <span className="rstat-label">Kelengkapan Data</span>
          <span className={`rstat-val font-mono ${stats.completeness < 70 ? 'text-amber-700' : 'text-emerald-700'}`}>
            {stats.completeness.toFixed(1)} <small>%</small>
          </span>
          <span className="rstat-sub text-muted">{stats.validDays} dari {stats.totalDays} hari kalender</span>
        </div>
      </div>

      {/* D2: Detail Tambahan: Statistik Distribusi Opsional */}
      <div className="rainfall-additional-stats-box">
        <button
          type="button"
          className="btn-toggle-additional-stats"
          onClick={() => setShowAdditional((prev) => !prev)}
        >
          <div className="flex-align gap-2">
            <TrendingUp size={13} className="text-forest" />
            <span>Statistik Distribusi &amp; Rangkaian Hari</span>
          </div>
          {showAdditional ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        {showAdditional && (
          <div className="additional-stats-content">
            <div className="additional-stats-grid">
              <div className="add-stat-item">
                <span className="add-stat-k">CH Min Positif (&gt; 0 mm):</span>
                <span className="add-stat-v font-mono">
                  {stats.minPositiveCh !== null ? `${stats.minPositiveCh.toFixed(1)} mm (${formatShortDate(stats.minPositiveDate)})` : 'Tidak ada'}
                </span>
              </div>
              <div className="add-stat-item">
                <span className="add-stat-k">Simpangan Baku (Std Dev):</span>
                <span className="add-stat-v font-mono">{stats.stdDev.toFixed(2)} mm</span>
              </div>
              <div className="add-stat-item">
                <span className="add-stat-k">Hari CH ≥ 20 mm:</span>
                <span className="add-stat-v font-mono">{stats.daysGte20} hari</span>
              </div>
              <div className="add-stat-item">
                <span className="add-stat-k">Hari CH ≥ 50 mm:</span>
                <span className="add-stat-v font-mono">{stats.daysGte50} hari</span>
              </div>
              <div className="add-stat-item">
                <span className="add-stat-k">Hari CH ≥ 100 mm:</span>
                <span className="add-stat-v font-mono">{stats.daysGte100} hari</span>
              </div>
              <div className="add-stat-item">
                <span className="add-stat-k">Rangkaian Kering Terpanjang:</span>
                <span className="add-stat-v font-mono text-amber-800">{stats.longestDryStreak} hari</span>
              </div>
              <div className="add-stat-item">
                <span className="add-stat-k">Rangkaian Hujan Terpanjang:</span>
                <span className="add-stat-v font-mono text-emerald-800">{stats.longestWetStreak} hari</span>
              </div>
            </div>

            <div className="additional-stats-disclaimer">
              <Info size={12} className="inline-icon text-muted" />
              <span>
                Ambang 20, 50, dan 100 mm digunakan sebagai statistik deskriptif distribusi data dan bukan ambang resmi peringatan dini.
                Rangkaian hari terputus otomatis jika ditemukan tanggal observasi missing.
              </span>
            </div>
          </div>
        )}
      </div>



      {/* Collapsible Raw Observation Subtable */}
      {showTableToggle && (
        <div className="rainfall-subtable-toggle-wrap">
          <button
            type="button"
            className="btn-toggle-subtable"
            onClick={() => setShowTable((prev) => !prev)}
          >
            <span>{showTable ? 'Sembunyikan Tabel Deret Harian' : 'Tampilkan Tabel Deret Harian'}</span>
            {showTable ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>

          {showTable && (
            <div className="history-table-wrapper mt-2">
              <table className="rainfall-daily-subtable">
                <thead>
                  <tr>
                    <th>Tanggal</th>
                    <th className="text-right">Curah Hujan (mm)</th>
                    <th>Keterangan</th>
                    <th className="text-right">HTH Berjalan</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((dayItem, dIdx) => {
                    const isMissing =
                      dayItem.rainfall_mm === null ||
                      dayItem.rainfall_mm === undefined ||
                      dayItem.status === 'Tidak tersedia' ||
                      (dayItem.obs_status && String(dayItem.obs_status).startsWith('MISSING'));
                    const isTtu =
                      (!isMissing && dayItem.status && dayItem.status.includes('TTU')) ||
                      dayItem.is_ttu ||
                      dayItem.obs_status === 'TTU';
                    const isRain = !isMissing && !isTtu && dayItem.rainfall_mm >= 1.0;
                    const isDry = !isMissing && !isRain;

                    return (
                      <tr key={dIdx} className={isRain ? 'row-rain-day' : isDry ? 'row-dry-day' : 'row-missing-day'}>
                        <td className="font-mono font-medium">{formatDateIndo(dayItem.date)}</td>
                        <td className="text-right font-mono font-bold">
                          {!isMissing ? (
                            <span className={isRain ? 'text-rain-highlight' : 'text-dry-value'}>
                              {dayItem.rainfall_mm.toFixed(1)} mm
                            </span>
                          ) : (
                            <span className="text-muted">Tidak tersedia</span>
                          )}
                        </td>
                        <td>
                          {isRain ? (
                            <span className="badge-condition rain-condition">
                              <Droplets size={11} />
                              <span>Hujan ({dayItem.rainfall_mm.toFixed(1)} mm)</span>
                            </span>
                          ) : isTtu ? (
                            <span className="badge-condition ttu-condition">
                              <Sparkles size={11} />
                              <span>TTU (Jejak Hujan &bull; 0 mm)</span>
                            </span>
                          ) : isDry ? (
                            <span className="badge-condition dry-condition">
                              <Sun size={11} />
                              <span>Hari Tanpa Hujan (0 mm)</span>
                            </span>
                          ) : (
                            <span className="badge-condition missing-condition">Tidak tersedia</span>
                          )}
                        </td>
                        <td className="text-right font-mono text-xs">
                          {dayItem.hth_days != null ? `${dayItem.hth_days} hr` : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
        </>
      )}
    </div>
  );
}
