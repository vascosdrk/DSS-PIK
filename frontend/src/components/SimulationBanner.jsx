import React from 'react';
import {
  Database,
  Calendar,
  Map,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Clock,
  Radio,
  Globe
} from 'lucide-react';
import PeriodSelector from './PeriodSelector';

export default function SimulationBanner({
  meta,
  periods = [],
  selectedPeriodId,
  periodMode = 'auto',
  serverTime = null,
  onSelectPeriod,
  onSwitchToRealtime,
  periodLoading = false,
  onOpenOfficialMap,
  readinessInfo = null,
}) {
  if (!meta && (!periods || periods.length === 0)) return null;

  const formatDateIndo = (dateStr) => {
    if (!dateStr || dateStr === 'TIDAK_TERSEDIA') return '-';
    try {
      const [year, month, day] = dateStr.split('-');
      const months = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
      ];
      return `${parseInt(day, 10)} ${months[parseInt(month, 10) - 1]} ${year}`;
    } catch {
      return dateStr;
    }
  };

  const cutoffFormatted = meta?.observation_cutoff
    ? formatDateIndo(meta.observation_cutoff)
    : (readinessInfo?.observation_cutoff_date ? formatDateIndo(readinessInfo.observation_cutoff_date) : 'Memuat...');

  const latestObsFormatted = readinessInfo?.latest_observation_date
    ? formatDateIndo(readinessInfo.latest_observation_date)
    : '-';

  const issueFormatted = meta?.forecast_issue
    ? formatDateIndo(meta.forecast_issue)
    : (readinessInfo?.forecast_issue_date ? formatDateIndo(readinessInfo.forecast_issue_date) : '-');

  const currentPeriod = periods.find((p) => p.period_id === selectedPeriodId);
  const isForecastPeriod = Boolean(currentPeriod?.is_forecast || meta?.is_forecast || selectedPeriodId?.includes('[Prakiraan]'));

  // Readiness Status Styling
  const readinessStatus = readinessInfo?.evaluation_readiness_status || 'READY';
  const isLagging = Boolean(readinessInfo?.is_lagging);
  const coveragePct = readinessInfo?.coverage_percentage != null ? readinessInfo.coverage_percentage : 100;

  let readinessBadge = (
    <span className="readiness-status-badge badge-ready" title="Seluruh parameter data lengkap dan terverifikasi">
      <CheckCircle2 size={12} />
      <span>Siap ({coveragePct}%)</span>
    </span>
  );

  if (isLagging || readinessStatus === 'LAGGING') {
    readinessBadge = (
      <span className="readiness-status-badge badge-lagging" title="Data observasi di database belum mencapai tanggal cutoff periode ini">
        <AlertTriangle size={12} />
        <span>Data Tertinggal</span>
      </span>
    );
  } else if (readinessStatus === 'PARTIAL') {
    readinessBadge = (
      <span className="readiness-status-badge badge-partial" title="Sebagian data stasiun/SPI belum lengkap">
        <AlertCircle size={12} />
        <span>Parsial ({coveragePct}%)</span>
      </span>
    );
  } else if (readinessStatus === 'NOT_READY') {
    readinessBadge = (
      <span className="readiness-status-badge badge-not-ready" title="Data belum mencukupi untuk evaluasi">
        <AlertCircle size={12} />
        <span>Belum Siap</span>
      </span>
    );
  }

  return (
    <div className="institutional-banner compact-operational-bar">
      <div className="banner-controls-group">
        <PeriodSelector
          periods={periods}
          selectedPeriodId={selectedPeriodId}
          periodMode={periodMode}
          onSelectPeriod={onSelectPeriod}
          onSwitchToRealtime={onSwitchToRealtime}
          loading={periodLoading}
        />

        <div className="period-metadata-grid">
          <div className="period-meta-card">
            <div className="period-meta-label">
              <Database size={13} />
              <span>Cutoff Observasi</span>
            </div>
            <div className="period-meta-val font-mono">{cutoffFormatted}</div>
          </div>

          <div className="period-meta-card">
            <div className="period-meta-label">
              <Clock size={13} />
              <span>Data Observasi DB</span>
            </div>
            <div className="period-meta-val font-mono">
              {latestObsFormatted}
            </div>
          </div>

          <div className="period-meta-card">
            <div className="period-meta-label">
              <Radio size={13} />
              <span>Kesiapan Evaluasi</span>
            </div>
            <div className="period-meta-val">
              {readinessBadge}
            </div>
          </div>
        </div>

        {/* Official BMKG Map Generator Action Buttons */}
        <div className="banner-action-buttons">
          <button
            type="button"
            className="btn-official-map btn-pdkm"
            onClick={() => onOpenOfficialMap && onOpenOfficialMap('PDKM')}
            title="Buka generator peta resmi Peringatan Dini Kekeringan Meteorologis (A4 Landscape BMKG)"
          >
            <Map size={13} />
            <span>Peta PDKM</span>
          </button>
          <button
            type="button"
            className="btn-official-map btn-pdcht"
            onClick={() => onOpenOfficialMap && onOpenOfficialMap('PDCHT')}
            title="Buka generator peta resmi Peringatan Dini Curah Hujan Tinggi (A4 Landscape BMKG)"
          >
            <Map size={13} />
            <span>Peta PDCHT</span>
          </button>
        </div>
      </div>

      {/* Operational Warning Alert Banner or Upcoming Forecast Period Banner */}
      {isForecastPeriod ? (
        <div className="period-lagging-warning-bar bg-purple-950/80 border-purple-500/80 text-purple-200">
          <Sparkles size={16} className="text-purple-400 shrink-0" />
          <div className="lagging-warning-text">
            <strong className="text-purple-300 font-bold tracking-wide">
              PERIODE PRAKIRAAN — BELUM MENJADI PERIODE OBSERVASI:
            </strong>{' '}
            <span>
              Dasarian ini belum berakhir dan data observasi curah hujan belum lengkap. Menampilkan indikator probabilitas prakiraan iklim tanpa menghasilkan peringatan observasi definitif.
            </span>
          </div>
        </div>
      ) : (isLagging || (readinessInfo && readinessInfo.warning_message)) && (
        <div className="period-lagging-warning-bar">
          <AlertTriangle size={15} className="text-amber shrink-0" />
          <div className="lagging-warning-text">
            <strong>Pemberitahuan Operasional: </strong>
            <span>
              {readinessInfo?.warning_message ||
                `Periode aktif (${meta?.period_label || selectedPeriodId}) melampaui data observasi terakhir di database (${latestObsFormatted}). Evaluasi berstatus data parsial/sementara.`}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
