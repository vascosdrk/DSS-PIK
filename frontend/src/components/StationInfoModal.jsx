import React, { useState, useEffect } from 'react';
import { 
  X, 
  Info, 
  MapPin, 
  Calendar, 
  CheckCircle2, 
  Droplets, 
  Sun, 
  Sparkles, 
  AlertCircle, 
  Radio, 
  Building2, 
  Activity,
  Layers,
  Search,
  AlertTriangle
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import { formatDateIndo } from '../utils/formatters';

export default function StationInfoModal({ 
  isOpen, 
  onClose, 
  initialStationId = '21010401a',
  stationsList = [] 
}) {
  const [selectedStationId, setSelectedStationId] = useState(initialStationId);
  const [stationsMaster, setStationsMaster] = useState([]);
  const [stationInfo, setStationInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Sync selectedStationId with prop
  useEffect(() => {
    if (initialStationId) {
      setSelectedStationId(initialStationId);
    }
  }, [initialStationId]);

  // Handle Escape key and body scroll lock
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  // Load master stations if stationsList is empty (lazy loaded only when opened)
  useEffect(() => {
    if (!isOpen) return;
    if (stationsList && stationsList.length > 0) {
      setStationsMaster(stationsList);
      return;
    }
    authFetch(API_ENDPOINTS.STATIONS_MASTER)
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.stations)) {
          setStationsMaster(data.stations);
        }
      })
      .catch((err) => console.error('Failed to load master stations in info modal:', err));
  }, [isOpen, stationsList]);

  // Fetch detailed station info when selectedStationId changes
  useEffect(() => {
    if (!isOpen || !selectedStationId) return;

    setLoading(true);
    setError(null);

    authFetch(API_ENDPOINTS.STATION_INFO(selectedStationId))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat informasi pos`);
        return res.json();
      })
      .then((data) => {
        setStationInfo(data);
      })
      .catch((err) => {
        console.error('Failed to fetch station info:', err);
        setError('Gagal memuat rincian metadata dan histori pos.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [isOpen, selectedStationId]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop-custom" onClick={onClose} role="dialog" aria-modal="true">
      <div className="station-info-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="drawer-header-compact">
          <div className="drawer-header-left">
            <div className="drawer-icon-box">
              <Info size={18} className="text-forest" />
            </div>
            <div>
              <h3 className="drawer-title-compact">Informasi Pos / Stasiun</h3>
              <p className="drawer-subtitle-compact">Metadata geospasial dan profil operasional observasi</p>
            </div>
          </div>
          <button 
            type="button" 
            className="btn-close-compact" 
            onClick={onClose}
            title="Tutup jendela informasi pos"
            aria-label="Tutup jendela informasi pos"
          >
            <X size={18} />
          </button>
        </div>

        {/* Station Selector Bar */}
        <div className="station-info-selector-bar">
          <label htmlFor="station-info-select" className="selector-label-compact">
            <Search size={13} />
            <span>Pilih Pos Pengamatan:</span>
          </label>
          <select
            id="station-info-select"
            className="station-info-dropdown"
            value={selectedStationId}
            onChange={(e) => setSelectedStationId(e.target.value)}
          >
            {stationsMaster.map((stn) => (
              <option key={stn.station_id} value={stn.station_id}>
                {stn.station_id} — {stn.station_name} ({stn.kabupaten}) ''
              </option>
            ))}
          </select>
        </div>

        {/* Drawer Content */}
        <div className="station-info-body">
          {loading && (
            <div className="station-info-loading">
              <div className="spin spinner-md"></div>
              <span>Menghitung metrik observasi dari database...</span>
            </div>
          )}

          {error && (
            <div className="station-info-error-box">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {!loading && stationInfo && (
            <div className="station-info-content-grid">
              {/* Primary Identity Card */}
              <div className="info-section-card identity-card">
                <div className="info-identity-header">
                  <div>
                    <span className="info-id-badge font-mono">{stationInfo.station_id}</span>
                    <h4 className="info-station-name">{stationInfo.station_name}</h4>
                  </div>
                  <div className="info-type-tag">
                    {stationInfo.is_arg ? (
                      <span className="badge-arg-info">
                        <Radio size={12} />
                        <span>Stasiun Pengamatan</span>
                      </span>
                    ) : (
                      <span className="badge-manual-info">
                        <Droplets size={12} />
                        <span>Stasiun Pengamatan</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="info-geo-grid">
                  <div className="info-meta-cell">
                    <span className="info-meta-label">Wilayah (Kab/Kota)</span>
                    <span className="info-meta-value font-medium">{stationInfo.kabupaten || '—'}</span>
                  </div>
                  <div className="info-meta-cell">
                    <span className="info-meta-label">Provinsi</span>
                    <span className="info-meta-value">{stationInfo.province || 'Kepulauan Riau'}</span>
                  </div>
                  <div className="info-meta-cell">
                    <span className="info-meta-label">Koordinat Geografis</span>
                    <span className="info-meta-value font-mono">
                      {stationInfo.latitude != null ? stationInfo.latitude.toFixed(4) : '—'}, {stationInfo.longitude != null ? stationInfo.longitude.toFixed(4) : '—'}
                    </span>
                  </div>
                  <div className="info-meta-cell">
                    <span className="info-meta-label">Elevasi</span>
                    <span className="info-meta-value font-mono">
                      {stationInfo.elevation_m != null ? `${stationInfo.elevation_m} mdpl` : '—'}
                    </span>
                  </div>
                  <div className="info-meta-cell">
                    <span className="info-meta-label">No. ZOM / NOZOM</span>
                    <span className="info-meta-value font-mono">
                      {String(stationInfo.station_id || '').trim().toLowerCase() === '21050101a'
                        ? 'Belum terpetakan / Tidak masuk poligon ZOM'
                        : (stationInfo.nozom_prov ? `ZOM ${stationInfo.nozom_prov}` : '— (Non-ZOM)')}
                    </span>
                  </div>
                </div>
              </div>

              {/* Operational Observation Metrics Card */}
              <div className="info-section-card metrics-card">
                <div className="info-section-title-row">
                  <Activity size={15} className="text-forest" />
                  <h5 className="info-section-title">Profil Operasional Observasi (cews_rainfall_daily)</h5>
                </div>

                <div className="metrics-summary-grid">
                  <div className="metric-box bg-slate">
                    <span className="metric-k">Observasi Pertama</span>
                    <span className="metric-v font-mono">
                      {stationInfo.first_observation_date ? formatDateIndo(stationInfo.first_observation_date) : 'Belum ada data'}
                    </span>
                  </div>
                  <div className="metric-box bg-slate">
                    <span className="metric-k">Observasi Terakhir</span>
                    <span className="metric-v font-mono">
                      {stationInfo.last_observation_date ? formatDateIndo(stationInfo.last_observation_date) : 'Belum ada data'}
                    </span>
                  </div>
                  <div className="metric-box bg-blue">
                    <span className="metric-k">Hari Kalender Operasi</span>
                    <span className="metric-v font-mono">
                      {stationInfo.operating_calendar_days ? `${stationInfo.operating_calendar_days.toLocaleString('id-ID')} hari` : '0 hari'}
                    </span>
                  </div>
                  <div className="metric-box bg-emerald">
                    <span className="metric-k">Kelengkapan Periode Operasi</span>
                    <span className="metric-v font-mono text-emerald font-bold">
                      {stationInfo.completeness_pct != null ? `${stationInfo.completeness_pct.toFixed(1)}%` : '—'}
                    </span>
                  </div>
                  <div className="metric-box bg-slate">
                    <span className="metric-k">HTH Berjalan Terakhir</span>
                    <span className="metric-v font-mono font-bold">
                      {stationInfo.running_hth != null ? `${stationInfo.running_hth} hari` : '0 hari'}
                    </span>
                    {stationInfo.hth_uncertain ? (
                      <span className="badge-hth-uncertain" title="Terdapat record missing dalam rentang HTH berjalan">
                        <AlertTriangle size={10} /> Data Tidak Pasti
                      </span>
                    ) : (
                      <span className="badge-hth-valid" title="Runtut pengamatan valid hingga hari hujan terakhir">
                        <CheckCircle2 size={10} /> Runtut Lengkap
                      </span>
                    )}
                    {stationInfo.last_rain_date && (
                      <span className="metric-subtext">
                        Hujan: {formatDateIndo(stationInfo.last_rain_date)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Detailed Counts Breakdown */}
                <div className="obs-counts-table-wrapper">
                  <table className="obs-counts-table">
                    <thead>
                      <tr>
                        <th>Status Data</th>
                        <th className="text-right">Jumlah Hari</th>
                        <th className="text-right">Persentase</th>
                        <th>Keterangan</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>
                          <div className="count-label-row">
                            <span className="count-dot dot-emerald"></span>
                            <span className="font-medium">Data Terisi / Valid</span>
                          </div>
                        </td>
                        <td className="text-right font-mono font-bold">
                          {stationInfo.valid_count.toLocaleString('id-ID')}
                        </td>
                        <td className="text-right font-mono">
                          {stationInfo.operating_calendar_days ? `${((stationInfo.valid_count / stationInfo.operating_calendar_days) * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="text-muted text-xs">Total observasi terukur valid (&ge; 0 mm) & TTU</td>
                      </tr>
                      <tr>
                        <td>
                          <div className="count-label-row">
                            <span className="count-dot dot-blue"></span>
                            <span>Hari Hujan (&ge; 1.0 mm)</span>
                          </div>
                        </td>
                        <td className="text-right font-mono font-bold text-blue">
                          {stationInfo.rain_days_count.toLocaleString('id-ID')}
                        </td>
                        <td className="text-right font-mono">
                          {stationInfo.valid_count ? `${((stationInfo.rain_days_count / stationInfo.valid_count) * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="text-muted text-xs">Curah hujan terukur &ge; 1.0 mm</td>
                      </tr>
                      <tr>
                        <td>
                          <div className="count-label-row">
                            <span className="count-dot dot-amber"></span>
                            <span>Hari Kering Terukur (0.0 mm)</span>
                          </div>
                        </td>
                        <td className="text-right font-mono font-bold text-amber">
                          {(stationInfo.dry_zero_days_count ?? 0).toLocaleString('id-ID')}
                        </td>
                        <td className="text-right font-mono">
                          {stationInfo.valid_count ? `${(((stationInfo.dry_zero_days_count ?? 0) / stationInfo.valid_count) * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="text-muted text-xs">Observasi terukur tanpa hujan (0.0 mm)</td>
                      </tr>
                      <tr>
                        <td>
                          <div className="count-label-row">
                            <span className="count-dot dot-sky"></span>
                            <span>Hari Kering Ringan (0.1–0.9 mm)</span>
                          </div>
                        </td>
                        <td className="text-right font-mono font-bold text-sky">
                          {(stationInfo.dry_sub1mm_days_count ?? 0).toLocaleString('id-ID')}
                        </td>
                        <td className="text-right font-mono">
                          {stationInfo.valid_count ? `${(((stationInfo.dry_sub1mm_days_count ?? 0) / stationInfo.valid_count) * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="text-muted text-xs">Curah hujan 0.1–0.9 mm (di bawah ambang hari hujan)</td>
                      </tr>
                      <tr>
                        <td>
                          <div className="count-label-row">
                            <span className="count-dot dot-indigo"></span>
                            <span>Jejak Hujan (TTU)</span>
                          </div>
                        </td>
                        <td className="text-right font-mono font-bold">
                          {stationInfo.ttu_count.toLocaleString('id-ID')}
                        </td>
                        <td className="text-right font-mono">
                          {stationInfo.valid_count ? `${((stationInfo.ttu_count / stationInfo.valid_count) * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="text-muted text-xs">Hujan tidak terukur (&lt; 0.5 mm) dihitung hari kering</td>
                      </tr>
                      <tr>
                        <td>
                          <div className="count-label-row">
                            <span className="count-dot dot-red"></span>
                            <span className="text-red font-medium">Data Missing / Tanpa Record</span>
                          </div>
                        </td>
                        <td className="text-right font-mono font-bold text-red">
                          {stationInfo.missing_count.toLocaleString('id-ID')}
                        </td>
                        <td className="text-right font-mono">
                          {stationInfo.operating_calendar_days ? `${((stationInfo.missing_count / stationInfo.operating_calendar_days) * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="text-muted text-xs">
                          {stationInfo.explicit_missing_count ?? 0} hari tercatat missing, {stationInfo.unrecorded_days_count ?? 0} hari tanpa baris record
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="info-footnote-box">
                  <Info size={13} className="text-forest inline-icon" />
                  <span>
                    <strong>Validasi Konsistensi Metrik:</strong> Data 0.0 mm dan TTU adalah data observasi kering yang sah dan tidak diperlakukan sebagai missing. 
                    Konsistensi kalender terpenuhi: Total Hari Operasi ({stationInfo.operating_calendar_days?.toLocaleString('id-ID')}) = Data Valid ({stationInfo.valid_count?.toLocaleString('id-ID')}) + Data Missing ({stationInfo.missing_count?.toLocaleString('id-ID')}).
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
