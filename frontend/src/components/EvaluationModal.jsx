import React, { useState, useEffect } from 'react';
import {
  X,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  CloudRain,
  Compass,
  ShieldCheck,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

export default function EvaluationModal({ stationId, periodId = '2026-09-das2', onClose, onSelectStation, onEvaluated }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!stationId) return;
    let isMounted = true;
    setLoading(true);
    setError(null);

    authFetch(API_ENDPOINTS.STATION_EVALUATION(stationId, periodId))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat data evaluasi diagnostik`);
        return res.json();
      })
      .then((json) => {
        if (isMounted) {
          setData(json);
          setLoading(false);
          if (onEvaluated && json?.evaluation?.status) {
            onEvaluated(stationId, json.evaluation.status);
          }
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Gagal terhubung ke endpoint evaluasi data.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [stationId, periodId]);

  if (!stationId) return null;

  // Status mapping
  const getStatusDisplay = (status) => {
    switch (status) {
      case 'CONSISTENT':
        return { label: 'Konsisten', class: 'status-consistent' };
      case 'REVIEW_REQUIRED':
        return { label: 'Perlu Ditinjau', class: 'status-review' };
      case 'INSUFFICIENT_DATA':
        return { label: 'Data Tidak Cukup', class: 'status-insufficient' };
      default:
        return { label: status || 'UNKNOWN', class: 'status-default' };
    }
  };

  const formatDateIndo = (d) => {
    if (!d) return '-';
    try {
      const parts = d.split('-');
      if (parts.length === 3) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
        return `${parseInt(parts[2], 10)} ${months[parseInt(parts[1], 10) - 1]} ${parts[0]}`;
      }
      return d;
    } catch {
      return d;
    }
  };

  const statusDisplay = data ? getStatusDisplay(data.evaluation.status) : null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog evaluation-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div className="modal-header-titles">
            <div className="flex-align gap-2">
              <ShieldCheck className="text-emerald-700" size={20} />
              <h3 className="modal-title">EVALUASI DIAGNOSTIK DATA</h3>
            </div>
            {data && (
              <p className="modal-subtitle">
                <strong>{data.station.station_name}</strong> &bull; <span className="font-mono">{data.station.station_id}</span> ({data.station.kabupaten})
              </p>
            )}
          </div>
          <button className="btn-modal-close" onClick={onClose} title="Tutup Evaluasi">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="modal-body">
          {loading && (
            <div className="modal-state-box">
              <div className="spin spinner-lg"></div>
              <p>Menjalankan audit diagnostik data observasi...</p>
            </div>
          )}

          {error && (
            <div className="modal-state-box text-red">
              <AlertTriangle size={32} />
              <p className="font-bold mt-2">Gagal Menjalankan Evaluasi</p>
              <p className="text-xs text-muted">{error}</p>
            </div>
          )}

          {!loading && !error && data && (
            <div className="eval-flow">
              {/* 1. Diagnostic Status Banner */}
              <div className={`eval-status-banner ${statusDisplay.class}`}>
                <div className="eval-status-row">
                  <div className="flex-align gap-3">
                    {data.evaluation.status === 'CONSISTENT' ? (
                      <CheckCircle2 size={24} className="status-icon-consistent" />
                    ) : data.evaluation.status === 'REVIEW_REQUIRED' ? (
                      <AlertTriangle size={24} className="status-icon-review" />
                    ) : (
                      <HelpCircle size={24} className="status-icon-insufficient" />
                    )}
                    <div>
                      <span className="eval-status-tag">{statusDisplay.label}</span>
                      <p className="eval-status-lead">
                        {data.evaluation.status === 'CONSISTENT'
                          ? 'Data observasi terverifikasi konsisten dengan pipeline HTH dan master stasiun.'
                          : data.evaluation.status === 'REVIEW_REQUIRED'
                          ? 'Ditemukan selisih atau variasi data yang memerlukan perhatian teknis.'
                          : 'Data observasi belum mencukupi untuk evaluasi komparatif lengkap.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Reasons List */}
                {data.evaluation.reasons && data.evaluation.reasons.length > 0 && (
                  <ul className="eval-reasons-list">
                    {data.evaluation.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* 2. Konsistensi HTH */}
              <div className="eval-section">
                <div className="section-title-row">
                  <CloudRain size={15} />
                  <h4>Konsistensi Hari Tanpa Hujan (HTH)</h4>
                </div>
                <div className="eval-metrics-grid">
                  <div className="eval-metric-card">
                    <span className="m-label">HTH Peringatan Aktif</span>
                    <span className="m-val font-mono">{data.hth_diagnostic.current_warning_hth} hari</span>
                    <span className="m-sub">Status: {data.current_state.warning_level}</span>
                  </div>

                  <div className="eval-metric-card">
                    <span className="m-label">HTH Pipeline Harian</span>
                    <span className="m-val font-mono">
                      {data.hth_diagnostic.pipeline_hth !== null
                        ? `${data.hth_diagnostic.pipeline_hth} hari`
                        : 'N/A'}
                    </span>
                    <span className={`m-sub ${data.hth_diagnostic.match ? 'text-green-700 font-bold' : 'text-amber-700'}`}>
                      {data.hth_diagnostic.match ? '✓ Sesuai Pipeline' : '⚠ Selisih Nilai'}
                    </span>
                  </div>

                  <div className="eval-metric-card">
                    <span className="m-label">Hujan Terakhir (≥ 1 mm)</span>
                    <span className="m-val">
                      {formatDateIndo(data.hth_diagnostic.last_rain_date)}
                    </span>
                    <span className="m-sub">
                      {data.hth_diagnostic.days_since_last_rain !== null
                        ? `${data.hth_diagnostic.days_since_last_rain} hari lalu`
                        : 'Tanggal Kejadian'}
                    </span>
                  </div>

                  <div className="eval-metric-card">
                    <span className="m-label">Missing Data Observasi</span>
                    <span className="m-val font-mono">
                      {data.hth_diagnostic.missing_observation_days} hari
                    </span>
                    <span className="m-sub">Periode Terakhir</span>
                  </div>
                </div>
              </div>

              {/* 3. Konteks Pos Terdekat (Spatial Neighbors) */}
              <div className="eval-section">
                <div className="section-title-row">
                  <Compass size={15} />
                  <h4>Konteks Pos Terdekat</h4>
                </div>
                <p className="section-desc">
                  Referensi spasial variabilitas lokal stasiun-stasiun terdekat di sekitarnya.
                </p>

                <div className="table-responsive-wrapper">
                  <table className="eval-nearest-table">
                    <thead>
                      <tr>
                        <th>Pos / Stasiun</th>
                        <th className="text-right">Jarak</th>
                        <th className="text-right">HTH</th>
                        <th className="text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.nearest_stations && data.nearest_stations.map((n) => (
                        <tr key={n.station_id} className="nearest-row">
                          <td>
                            <strong>{n.station_name}</strong>
                            <div className="font-mono text-xs text-muted">{n.station_id} ({n.kabupaten})</div>
                          </td>
                          <td className="text-right font-mono font-bold text-forest">
                            {n.distance_km} km
                          </td>
                          <td className="text-right font-mono font-bold">
                            {n.hth_days_current !== null ? `${n.hth_days_current} hr` : '-'}
                          </td>
                          <td className="text-center">
                            <span className={`badge-pill lvl-${n.warning_level.toLowerCase()}`}>
                              {n.warning_level}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* 4. Mini Daily Rainfall Strip if available */}
              {data.observation_diagnostics &&
                data.observation_diagnostics.recent_rainfall &&
                data.observation_diagnostics.recent_rainfall.length > 0 && (
                  <div className="eval-section">
                    <div className="section-title-row">
                      <CloudRain size={15} />
                      <h4>Deret Observasi Curah Hujan Harian</h4>
                    </div>

                    <div className="rainfall-strip-container">
                      {data.observation_diagnostics.recent_rainfall.map((d, idx) => {
                        const dayNum = parseInt(d.date.split('-')[2], 10);
                        const isRain = d.rainfall_mm > 0;
                        return (
                          <div
                            key={idx}
                            className={`rainfall-tile ${isRain ? 'tile-rain' : 'tile-dry'} ${d.is_missing ? 'tile-missing' : ''}`}
                            title={`${d.date}: ${d.rainfall_mm} mm (HTH: ${d.hth_days} hr)`}
                          >
                            <span className="tile-day">{dayNum}</span>
                            <div className="tile-bar-wrap">
                              <div
                                className="tile-bar"
                                style={{
                                  height: isRain ? `${Math.min(100, Math.max(20, d.rainfall_mm * 2))}%` : '4px',
                                }}
                              />
                            </div>
                            <span className="tile-rain-val font-mono">
                              {d.rainfall_mm > 0 ? d.rainfall_mm.toFixed(0) : '0'}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

              {/* Disclaimer */}
              <div className="eval-disclaimer-card">
                <p>
                  * Evaluasi diagnostik bersifat read-only untuk verifikasi kualitas data dan tidak mengubah status peringatan operasional.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
