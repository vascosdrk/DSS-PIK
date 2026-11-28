import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  X,
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Database,
  RefreshCw,
  History,
  Layers,
  Calendar,
  ShieldCheck,
  ChevronRight,
  ArrowRight,
  FileText,
  RotateCcw,
  Check,
  Info,
  Filter,
  CheckSquare,
  Square,
  Search
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import { formatDateIndo } from '../utils/formatters';
import CanonicalStorageStatusCard from './CanonicalStorageStatusCard';

const DATASET_TYPE_OPTIONS = [
  { value: 'AUTO_DETECT', label: 'Deteksi Otomatis (Rekomendasi)', desc: 'Sistem mengenali tipe data dari ekstensi & struktur berkas' },
  { value: 'CURAH_HUJAN', label: 'Curah Hujan Harian', desc: 'File Excel (.xlsx/.xls) format 7 kabupaten/kota Kepri' },
  { value: 'SPI_HARIAN', label: 'SPI Harian (30D / 90D)', desc: 'File Parquet SPI resolusi harian seluruh stasiun' },
  { value: 'SPI_DASARIAN', label: 'SPI Dasarian (30D / 90D)', desc: 'File Parquet SPI resolusi dasarian (Pemicu Utama PDKM)' },
  { value: 'SPI_BULANAN', label: 'SPI Bulanan (1 Bulan)', desc: 'File Excel (.xlsx) SPI bulanan multi-sheet/multi-pos' },
  { value: 'PROBABILITAS_DASARIAN', label: 'ECMWF Dasarian (Probabilitas & Deterministik)', desc: '3 workbook (.xlsx) per penerbitan (1 release_group_id): membaca Probabilitas (%) & Deterministik (mm)' },
  { value: 'PROBABILITAS_BULANAN', label: 'ECMWF Bulanan (Probabilitas & Deterministik)', desc: '1 workbook (.xlsx) bulan dinamis: membaca Probabilitas (%) & Deterministik (mm)' },
];

export default function DataIngestionModal({
  isOpen,
  onClose,
  onIngestionSuccess,
  onOpenManagement,
  initialDatasetType = 'AUTO_DETECT',
}) {
  const [wizardStep, setWizardStep] = useState(1); // 1: Type & Files -> 3: Preview -> 4: Result

  // Form State
  const [datasetType, setDatasetType] = useState(initialDatasetType || 'AUTO_DETECT');
  const [timescale, setTimescale] = useState('30D'); // for Parquet
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);

  // Preview & Validation State
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState(null);
  const [previewData, setPreviewData] = useState(null);

  // Period-aware & Authorization State
  const [selectedPeriods, setSelectedPeriods] = useState([]);
  const [periodSearchQuery, setPeriodSearchQuery] = useState('');
  const [periodYearFilter, setPeriodYearFilter] = useState('ALL');
  const [explicitUpdateConsent, setExplicitUpdateConsent] = useState(false);
  const [diffFilterStatus, setDiffFilterStatus] = useState('ALL');
  const [diffFilterRegency, setDiffFilterRegency] = useState('ALL');
  const [diffFilterPeriod, setDiffFilterPeriod] = useState('ALL');
  const [diffProductTab, setDiffProductTab] = useState('PROB'); // 'PROB' | 'ENSMEAN'

  // Commit State
  const [operatorName, setOperatorName] = useState('OPERATOR_BMKG');
  const [operatorNotes, setOperatorNotes] = useState('Pembaruan data operasional berkala');
  const [confirmCheckbox, setConfirmCheckbox] = useState(false);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitError, setCommitError] = useState(null);
  const [commitResult, setCommitResult] = useState(null);

  // History State
  const [historyList, setHistoryList] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);

  // Fitur A: Live Canonical Storage Status State
  const [latestStatus, setLatestStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(false);

  const fetchLatestStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_LATEST_STATUS);
      if (res.ok) {
        const data = await res.json();
        setLatestStatus(data);
      }
    } catch (err) {
      console.error('Failed to load latest operational status:', err);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  // Reset wizard on modal open
  useEffect(() => {
    if (isOpen) {
      fetchLatestStatus();
      setWizardStep(1);
      setDatasetType(initialDatasetType || 'AUTO_DETECT');
      setSelectedFiles([]);
      setPreviewData(null);
      setPreviewError(null);
      setCommitResult(null);
      setCommitError(null);
      setConfirmCheckbox(false);
      setExplicitUpdateConsent(false);
      setSelectedPeriods([]);
      setPeriodSearchQuery('');
      setPeriodYearFilter('ALL');
      setDiffFilterStatus('ALL');
      setDiffFilterRegency('ALL');
      setDiffFilterPeriod('ALL');
    }
  }, [isOpen]);

  // When previewData is loaded, initialize selectedPeriods with all detected periods
  useEffect(() => {
    if (previewData?.summary?.periods_detected) {
      const pids = previewData.summary.periods_detected.map((p) => p.period_id);
      setSelectedPeriods(pids);
    }
  }, [previewData]);

  // Computed helper fields for preview - declared unconditionally before any early returns
  const previewSummary = useMemo(() => {
    if (!previewData) return null;
    const s = previewData.summary || {};
    return {
      dataType: previewData.data_type || previewData.detected_type || 'DATASET',
      filename: previewData.filename || 'berkas_input',
      totalRows: s.total_rows ?? s.total_records ?? previewData.total_incoming_records ?? 0,
      totalNew: s.total_new ?? s.new_count ?? previewData.new_records ?? 0,
      totalNewVintage: s.total_new_vintage ?? 0,
      totalUpdated: s.total_updated ?? s.updated_count ?? previewData.updated_records ?? 0,
      totalIdentical: s.total_identical ?? s.identical_count ?? previewData.identical_records ?? 0,
      totalMissing: s.total_missing ?? 0,
      totalDamaged: s.total_damaged ?? 0,
      totalAmbiguous: s.total_ambiguous ?? 0,
      startDate: s.date_range?.start ?? previewData.date_range?.start_date ?? '-',
      endDate: s.date_range?.end ?? previewData.date_range?.end_date ?? '-',
      affectedStationsCount: s.total_stations_recognized ?? previewData.affected_stations_count ?? 0,
      periodsDetected: s.periods_detected || [],
      regencyCounts: s.regency_counts || {},
      stationGaps: s.station_gaps || [],
      countsByStatus: s.counts_by_status || {},
      forecastIssueDate: previewData.forecast_issue_date || s.forecast_issue_date || null,
      forecastType: s.forecast_type || previewData.data_type || null,
      forecastResolution: previewData.forecast_resolution || null,
      releaseGroupId: previewData.release_group_id || s.release_group_id || null,
      filesCount: s.files_count ?? (Array.isArray(previewData.filenames) ? previewData.filenames.length : 1),
      filenames: previewData.filenames || s.filenames || (previewData.filename ? [previewData.filename] : []),
      deterministicSummary: s.deterministic_summary || null,
      ensmeanColumnResolution: previewData.ensmean_column_resolution || null,
      warnings: previewData.warnings || s.warnings || [],
      hasAdjustConflicts: Boolean(previewData.has_adjust_conflicts || s.has_adjust_conflicts),
      isIncompleteDasarianRelease:
        (previewData.data_type === 'PROBABILITAS_DASARIAN' || datasetType === 'PROBABILITAS_DASARIAN') &&
        Array.isArray(previewData.filenames) &&
        previewData.filenames.length > 0 &&
        previewData.filenames.length !== 3,
      stationMappingSummary: previewData.station_mapping_summary || s.station_mapping_summary || null,
      unmappedExternalStations: s.unmapped_external_stations || [],
      duplicateStations: s.duplicate_stations || [],
      diffList: (previewData.diff_samples && previewData.diff_samples.length > 0)
        ? previewData.diff_samples
        : (previewData.preview_items || []),
      detDiffList: previewData.deterministic_diff_samples || [],
      anomalies: previewData.anomalies || [],
    };
  }, [previewData, datasetType]);

  // Filtered diff samples list (period-aware & filterable)
  const filteredDiffList = useMemo(() => {
    if (!previewSummary?.diffList) return [];
    return previewSummary.diffList.filter((item) => {
      // 1. Period filter (dropdown or selected periods)
      const itemPeriod = item.period_id || item.target_period;
      if (diffFilterPeriod !== 'ALL') {
        if (itemPeriod !== diffFilterPeriod) return false;
      } else if (selectedPeriods.length > 0 && previewSummary?.periodsDetected?.length > 1) {
        if (itemPeriod && !selectedPeriods.includes(itemPeriod)) return false;
      }

      // 2. Status filter
      if (diffFilterStatus !== 'ALL') {
        const itemStatus = item.change_type || item.status || (item.old_rainfall_mm !== undefined && item.old_rainfall_mm !== null ? 'UPDATED' : 'NEW');
        if (itemStatus !== diffFilterStatus) return false;
      }

      // 3. Regency filter
      if (diffFilterRegency !== 'ALL') {
        const itemKab = item.kabupaten || '';
        if (!itemKab.toLowerCase().includes(diffFilterRegency.toLowerCase())) return false;
      }
      return true;
    });
  }, [previewSummary, diffFilterStatus, diffFilterRegency, diffFilterPeriod, selectedPeriods]);

  // Period selection toggles
  const togglePeriodSelection = (periodId) => {
    setSelectedPeriods((prev) => {
      if (prev.includes(periodId)) {
        return prev.filter((p) => p !== periodId);
      } else {
        return [...prev, periodId];
      }
    });
  };

  const selectAllPeriods = () => {
    if (previewSummary?.periodsDetected) {
      setSelectedPeriods(previewSummary.periodsDetected.map((p) => p.period_id));
    }
  };

  const deselectAllPeriods = () => {
    setSelectedPeriods([]);
  };

  // File Handlers
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const filesArray = Array.from(e.dataTransfer.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
    }
  };

  const handleRemoveFile = (idx) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // Step 3: Call Preview API
  const handleAnalyzeFiles = async () => {
    if (selectedFiles.length === 0) return;
    setPreviewLoading(true);
    setPreviewError(null);

    const formData = new FormData();
    selectedFiles.forEach((f) => {
      formData.append('files', f);
    });
    if (selectedFiles.length > 0) {
      formData.append('file', selectedFiles[0]);
    }
    formData.append('data_type', datasetType);
    formData.append('dataset_type', datasetType);
    formData.append('timescale', timescale);

    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_PREVIEW, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Validasi berkas gagal`);
      }

      const data = await res.json();
      setPreviewData(data);
      setWizardStep(3); // Go to Preview & Diff Step
    } catch (err) {
      console.error('Error analyzing files:', err);
      setPreviewError(err.message || 'Gagal memproses pratinjau berkas.');
    } finally {
      setPreviewLoading(false);
    }
  };

  // Step 4: Call Commit API
  const handleCommitIngestion = async () => {
    const token = previewData?.staging_token || previewData?.session_id;
    if (!token) return;
    if (!confirmCheckbox) return;
    if (selectedPeriods.length === 0 && previewSummary?.periodsDetected?.length > 0) {
      setCommitError('Pilih minimal satu periode target untuk disimpan.');
      return;
    }

    setCommitLoading(true);
    setCommitError(null);

    try {
      const payload = {
        staging_token: token,
        operator: operatorName || 'OPERATOR_BMKG',
        confirm_overwrite: true,
        selected_periods: selectedPeriods.length > 0 ? selectedPeriods : null,
        explicit_update_consent: explicitUpdateConsent,
        approval_scope: JSON.stringify({
          operator: operatorName,
          explicit_update_consent: explicitUpdateConsent,
          selected_periods: selectedPeriods,
          notes: operatorNotes,
        }),
      };

      const res = await authFetch(API_ENDPOINTS.INGESTION_COMMIT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Gagal menyimpan data`);
      }

      const result = await res.json();
      setCommitResult(result);
      setWizardStep(4); // Go to Result Step
      if (onIngestionSuccess) {
        onIngestionSuccess(result);
      }
    } catch (err) {
      console.error('Commit error:', err);
      setCommitError(err.message || 'Gagal menyimpan pembaruan ke database.');
    } finally {
      setCommitLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop-custom">
      <div className="ingestion-modal-container max-w-4xl">
        {/* Modal Header */}
        <div className="ingestion-modal-header">
          <div className="flex-align gap-3">
            <div className="ingestion-icon-badge">
              <Database size={20} className="text-forest" />
            </div>
            <div>
              <h2 className="ingestion-modal-title">Pusat Input &amp; Pembaruan Data Operasional</h2>
              <p className="ingestion-modal-subtitle">
                Modul Ingestion Aman DSS-PIK: Validasi Pratinjau Periode, Deteksi Diff, dan Komitmen Transaksional Atomik
              </p>
            </div>
          </div>

          <div className="flex-align gap-2">
            {onOpenManagement && (
              <button
                type="button"
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-300 transition"
                onClick={() => onOpenManagement('BATCHES')}
                title="Buka tabel Riwayat Batch Ingestion lengkap di Manajemen Data Operasional"
              >
                <History size={13} className="text-slate-600" />
                <span>Riwayat Batch Lengkap</span>
              </button>
            )}

            <button
              type="button"
              className="btn-modal-close"
              onClick={onClose}
              title="Tutup dialog ingestion"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="ingestion-modal-body">
          {/* 3-STEP INGESTION WIZARD */}
          <div className="ingestion-wizard-view">
            {/* RINGKASAN SINGKAT STATUS PENYIMPANAN KANONIKAL (1 BARIS RINGKAS) */}
            <div className="bg-slate-50 border border-slate-200 rounded-lg px-3.5 py-2.5 mb-4 flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex flex-wrap items-center gap-3 text-slate-700">
                <span className="inline-flex items-center font-bold text-slate-800">
                  <Database size={13} className="text-forest mr-1.5" />
                  Status Penyimpanan Aktif:
                </span>
                <span>
                  CH Terakhir: <strong className="font-mono text-slate-900">{latestStatus?.curah_hujan?.latest_date || '—'}</strong> ({latestStatus?.curah_hujan?.reported_stations_count ?? 0}/57 Pos)
                </span>
                <span className="text-slate-300">|</span>
                <span>
                  SPI Dasarian 30D: <strong className="font-mono text-slate-900">{latestStatus?.spi_dasarian_30d?.latest_date || '—'}</strong>
                </span>
                <span className="text-slate-300">|</span>
                <span>
                  ECMWF Dasarian: <strong className="font-mono text-purple-800">{latestStatus?.probabilitas_dasarian?.latest_target_period || '—'}</strong> (Issue: <span className="font-mono">{latestStatus?.probabilitas_dasarian?.latest_issue_date || '—'}</span>)
                </span>
              </div>
              <div className="flex items-center space-x-2">
                {onOpenManagement && (
                  <button
                    type="button"
                    onClick={() => onOpenManagement('STORAGE')}
                    className="text-[11px] font-semibold text-emerald-700 hover:text-emerald-800 underline"
                  >
                    Detail Penyimpanan →
                  </button>
                )}
              </div>
            </div>

            {/* Step Progress Bar */}
              <div className="wizard-progress-bar">
                <div className={`wizard-step-node ${wizardStep >= 1 ? 'active' : ''} ${wizardStep > 1 ? 'completed' : ''}`}>
                  <span className="step-circle">{wizardStep > 1 ? <Check size={12} /> : '1'}</span>
                  <span className="step-label">Tipe &amp; Unggah</span>
                </div>
                <div className="wizard-step-connector"></div>
                <div className={`wizard-step-node ${wizardStep >= 3 ? 'active' : ''} ${wizardStep > 3 ? 'completed' : ''}`}>
                  <span className="step-circle">{wizardStep > 3 ? <Check size={12} /> : '2'}</span>
                  <span className="step-label">Pratinjau Periode &amp; Diff</span>
                </div>
                <div className="wizard-step-connector"></div>
                <div className={`wizard-step-node ${wizardStep >= 4 ? 'active' : ''}`}>
                  <span className="step-circle">3</span>
                  <span className="step-label">Otorisasi &amp; Hasil</span>
                </div>
              </div>

              {/* STEP 1: TYPE SELECTION & UPLOAD */}
              {wizardStep <= 2 && (
                <div className="wizard-body-flow">
                  <div className="ingestion-section-block">
                    <label className="section-block-label">
                      <Layers size={14} className="inline-icon text-slate-500" />
                      <span>Kategori Dataset Operasional:</span>
                    </label>
                    <div className="dataset-options-grid">
                      {DATASET_TYPE_OPTIONS.map((opt) => (
                        <div
                          key={opt.value}
                          className={`dataset-option-card ${datasetType === opt.value ? 'selected' : ''}`}
                          onClick={() => setDatasetType(opt.value)}
                        >
                          <div className="flex-align gap-2">
                            <input
                              type="radio"
                              name="dataset_type"
                              checked={datasetType === opt.value}
                              onChange={() => setDatasetType(opt.value)}
                            />
                            <span className="font-semibold text-xs text-slate-800">{opt.label}</span>
                          </div>
                          <p className="text-xs text-muted mt-1">{opt.desc}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {(datasetType === 'SPI_HARIAN' || datasetType === 'SPI_DASARIAN') && (
                    <div className="ingestion-section-block">
                      <label className="section-block-label">
                        <Calendar size={14} className="inline-icon text-slate-500" />
                        <span>Skala Akumulasi SPI:</span>
                      </label>
                      <div className="segmented-switch" role="group">
                        <button
                          type="button"
                          className={`switch-btn ${timescale === '30D' ? 'active' : ''}`}
                          onClick={() => setTimescale('30D')}
                        >
                          30 Hari (30D - Acuan Otoritatif)
                        </button>
                        <button
                          type="button"
                          className={`switch-btn ${timescale === '90D' ? 'active' : ''}`}
                          onClick={() => setTimescale('90D')}
                        >
                          90 Hari (90D - Pendamping Informatif)
                        </button>
                      </div>
                    </div>
                  )}

                  {datasetType === 'PROBABILITAS_DASARIAN' && (
                    <div className="bg-sky-50 border border-sky-200 rounded-lg p-3 text-xs text-sky-900 mb-3 flex items-start gap-2">
                      <Info size={15} className="text-sky-700 shrink-0 mt-0.5" />
                      <div>
                        <strong>Aturan Penerbitan ECMWF Dasarian (3 Workbook = 1 Release Group):</strong>{' '}
                        Anda dapat melakukan pratinjau 1–3 berkas, namun <strong>penyimpanan (commit) penerbitan dasarian lengkap mewajibkan 3 workbook valid</strong> dengan <code>issue_date</code> identik dan tanpa konflik target. Sistem otomatis membaca data <strong>Probabilitas (%)</strong> sekaligus <strong>Deterministik (mm)</strong> dari ketiga workbook tersebut.
                      </div>
                    </div>
                  )}

                  {datasetType === 'PROBABILITAS_BULANAN' && (
                    <div className="bg-sky-50 border border-sky-200 rounded-lg p-3 text-xs text-sky-900 mb-3 flex items-start gap-2">
                      <Info size={15} className="text-sky-700 shrink-0 mt-0.5" />
                      <div>
                        <strong>Aturan Penerbitan ECMWF Bulanan:</strong>{' '}
                        Unggah 1 workbook bulanan (.xlsx) dengan periode bulan dinamis. Sistem otomatis membaca data <strong>Probabilitas (%)</strong> dan <strong>Deterministik (mm)</strong> dari berkas yang sama, memprioritaskan kolom <code>Adjust</code>, serta mengabaikan kolom non-prakiraan (analisis/obs).
                      </div>
                    </div>
                  )}

                  <div className="ingestion-section-block">
                    <label className="section-block-label">
                      <UploadCloud size={14} className="inline-icon text-slate-500" />
                      <span>Unggah Berkas (Mendukung Multi-File Excel / Parquet):</span>
                    </label>

                    <div
                      className={`ingestion-dropzone ${isDragging ? 'dragging' : ''}`}
                      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                      onDragLeave={() => setIsDragging(false)}
                      onDrop={handleDrop}
                    >
                      <UploadCloud size={32} className="text-sky-500 mb-2" />
                      <p className="font-semibold text-slate-700 text-sm">
                        Seret &amp; letakkan berkas di sini, atau telusuri folder
                      </p>
                      <p className="text-xs text-muted mb-3">
                        Format didukung: .xlsx, .xls, .parquet. Sistem akan membaca tanggal &amp; periode langsung dari isi berkas.
                      </p>

                      <label className="btn-browse-files">
                        <span>Pilih Berkas Komputer</span>
                        <input
                          type="file"
                          multiple
                          accept=".xlsx,.xls,.parquet"
                          onChange={handleFileChange}
                          style={{ display: 'none' }}
                        />
                      </label>
                    </div>

                    {selectedFiles.length > 0 && (
                      <div className="selected-files-list">
                        <span className="text-xs font-semibold text-slate-700">
                          {selectedFiles.length} berkas dipilih:
                        </span>
                        <div className="files-chips-container">
                          {selectedFiles.map((f, idx) => (
                            <div key={idx} className="file-chip">
                              <FileSpreadsheet size={13} className="text-emerald-700" />
                              <span className="file-name font-mono text-xs">{f.name}</span>
                              <span className="file-size text-muted text-xs">
                                ({(f.size / 1024).toFixed(0)} KB)
                              </span>
                              <button
                                type="button"
                                className="btn-remove-file"
                                onClick={() => handleRemoveFile(idx)}
                              >
                                &times;
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {previewError && (
                    <div className="table-error-banner">
                      <AlertCircle size={16} />
                      <span>{previewError}</span>
                    </div>
                  )}

                  <div className="wizard-actions-bar">
                    <button
                      type="button"
                      className="btn-wizard-cancel"
                      onClick={onClose}
                    >
                      Batal
                    </button>

                    <button
                      type="button"
                      className="btn-wizard-primary"
                      onClick={handleAnalyzeFiles}
                      disabled={selectedFiles.length === 0 || previewLoading}
                    >
                      {previewLoading ? (
                        <>
                          <div className="spin spinner-sm"></div>
                          <span>Menganalisis &amp; Memvalidasi...</span>
                        </>
                      ) : (
                        <>
                          <span>Lanjut: Pratinjau &amp; Validasi Diff</span>
                          <ArrowRight size={14} />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 3: PREVIEW, PERIOD SELECTION & SCOPED AUTHORIZATION */}
              {wizardStep === 3 && previewSummary && (
                <div className="wizard-body-flow">
                  {/* Summary Metric Cards */}
                  <div className="preview-metrics-grid">
                    <div className="metric-card">
                      <span className="metric-k">Tipe Terdeteksi</span>
                      <span className="metric-v-badge">{previewSummary.dataType}</span>
                    </div>
                    <div className="metric-card">
                      <span className="metric-k">Total Baris File</span>
                      <span className="metric-v font-mono">{previewSummary.totalRows?.toLocaleString('id-ID')}</span>
                    </div>
                    <div className="metric-card border-green">
                      <span className="metric-k text-emerald-800">Catatan Baru</span>
                      <span className="metric-v font-mono text-emerald-700">+{previewSummary.totalNew?.toLocaleString('id-ID')}</span>
                    </div>
                    {previewSummary.totalNewVintage > 0 && (
                      <div className="metric-card border-purple-300 bg-purple-50/40">
                        <span className="metric-k text-purple-900 font-bold">New Vintage (ECMWF)</span>
                        <span className="metric-v font-mono text-purple-700">+{previewSummary.totalNewVintage?.toLocaleString('id-ID')}</span>
                      </div>
                    )}
                    <div className="metric-card border-amber">
                      <span className="metric-k text-amber-800">Catatan Diperbarui</span>
                      <span className="metric-v font-mono text-amber-700">{previewSummary.totalUpdated?.toLocaleString('id-ID')}</span>
                    </div>
                    <div className="metric-card">
                      <span className="metric-k">Catatan Identik</span>
                      <span className="metric-v font-mono text-slate-500">{previewSummary.totalIdentical?.toLocaleString('id-ID')}</span>
                    </div>
                  </div>

                  {/* Scope & Regency Breakdown */}
                  <div className="preview-scope-card">
                    <div className="scope-row mb-1">
                      <span><strong>Rentang Observasi:</strong> {previewSummary.startDate} s.d. {previewSummary.endDate}</span>
                      <span><strong>Pos Dikenali:</strong> {previewSummary.affectedStationsCount} Pos</span>
                    </div>
                    {Object.keys(previewSummary.regencyCounts).length > 0 && (
                      <div className="flex-align gap-2 flex-wrap text-xs text-slate-600 mt-2">
                        <span className="font-semibold">Sebaran Wilayah:</span>
                        {Object.entries(previewSummary.regencyCounts).map(([kab, count]) => (
                          <span key={kab} className="badge-regency-pill">
                            {kab}: {count}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Unified ECMWF Probabilitas & ENSMEAN Summary Panel */}
                  {(previewSummary.deterministicSummary || previewSummary.releaseGroupId || previewSummary.warnings?.length > 0) && (
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs mb-3 space-y-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-200">
                        <div className="flex items-center gap-2 font-bold text-slate-800">
                          <Layers size={15} className="text-sky-700" />
                          <span>Ringkasan Terpadu ECMWF (Probabilitas &amp; Deterministik)</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                          {previewSummary.forecastIssueDate && (
                            <span className="px-2 py-0.5 rounded bg-sky-100 text-sky-900 font-semibold">
                              Issue: {previewSummary.forecastIssueDate}
                            </span>
                          )}
                          {previewSummary.forecastResolution && (
                            <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-900 font-semibold">
                              {previewSummary.forecastResolution}
                            </span>
                          )}
                          {previewSummary.releaseGroupId && (
                            <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-800">
                              Group: {previewSummary.releaseGroupId} ({previewSummary.filesCount} berkas)
                            </span>
                          )}
                        </div>
                      </div>

                      {previewSummary.deterministicSummary && (
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-[11px]">
                          <div className="bg-white p-2 rounded border border-slate-200">
                            <span className="text-slate-500 block">Deterministik Total:</span>
                            <span className="font-mono font-bold text-slate-900">
                              {previewSummary.deterministicSummary.total_records ?? 0} baris
                            </span>
                          </div>
                          <div className="bg-white p-2 rounded border border-emerald-200">
                            <span className="text-emerald-700 block">Deterministik Baru:</span>
                            <span className="font-mono font-bold text-emerald-700">
                              +{(previewSummary.deterministicSummary.new_records ?? 0) + (previewSummary.deterministicSummary.new_vintage_records ?? 0)}
                            </span>
                          </div>
                          <div className="bg-white p-2 rounded border border-amber-200">
                            <span className="text-amber-700 block">Deterministik Update:</span>
                            <span className="font-mono font-bold text-amber-700">
                              {previewSummary.deterministicSummary.updated_records ?? 0}
                            </span>
                          </div>
                          <div className="bg-white p-2 rounded border border-sky-200">
                            <span className="text-sky-700 block">Deterministik Reaktivasi:</span>
                            <span className="font-mono font-bold text-sky-700">
                              {previewSummary.deterministicSummary.reactivated_records ?? 0}
                            </span>
                          </div>
                          <div className="bg-white p-2 rounded border border-slate-200">
                            <span className="text-slate-500 block">Deterministik Identik:</span>
                            <span className="font-mono font-bold text-slate-600">
                              {previewSummary.deterministicSummary.identical_records ?? 0}
                            </span>
                          </div>
                        </div>
                      )}

                      {previewSummary.deterministicSummary?.adjusted_columns_used?.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                          <span className="font-semibold text-emerald-800">Kolom ADJUSTED Diprioritaskan:</span>
                          {previewSummary.deterministicSummary.adjusted_columns_used.map((col, idx) => (
                            <span key={idx} className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono border border-emerald-200">
                              {col}
                            </span>
                          ))}
                        </div>
                      )}

                      {previewSummary.deterministicSummary?.ignored_non_forecast_columns?.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                          <span className="font-semibold text-slate-600">IGNORED NON-FORECAST COLUMN:</span>
                          {previewSummary.deterministicSummary.ignored_non_forecast_columns.map((col, idx) => (
                            <span key={idx} className="px-2 py-0.5 rounded bg-slate-200 text-slate-700 font-mono">
                              {typeof col === 'string' ? col : (col.header || col.source_column || JSON.stringify(col))}
                            </span>
                          ))}
                        </div>
                      )}

                      {previewSummary.hasAdjustConflicts && (
                        <div className="p-2.5 rounded bg-rose-50 border border-rose-300 text-rose-900 flex items-start gap-2">
                          <AlertCircle size={15} className="text-rose-600 shrink-0 mt-0.5" />
                          <div>
                            <strong>Konflik Kolom Adjust Terdeteksi — Commit Diblokir:</strong> Terdapat lebih dari satu kandidat kolom <code>Adjust</code> untuk target periode yang sama. Klarifikasi header workbook terlebih dahulu.
                          </div>
                        </div>
                      )}

                      {previewSummary.isIncompleteDasarianRelease && (
                        <div className="p-2.5 rounded bg-amber-50 border border-amber-300 text-amber-900 flex items-start gap-2">
                          <AlertTriangle size={15} className="text-amber-600 shrink-0 mt-0.5" />
                          <div>
                            <strong>Penerbitan Dasarian Belum Lengkap ({previewSummary.filesCount}/3 berkas):</strong>{' '}
                            Pratinjau diizinkan untuk 1–3 berkas, tetapi <strong>Commit memerlukan tepat 3 workbook dasarian valid</strong> (tidak diperbolehkan partial release). Kembali ke Langkah 1 untuk melengkapi ketiga berkas.
                          </div>
                        </div>
                      )}

                      {previewSummary.warnings?.length > 0 && (
                        <div className="p-2.5 rounded bg-amber-50 border border-amber-200 text-amber-900">
                          <div className="font-semibold mb-1 flex items-center gap-1.5">
                            <AlertTriangle size={14} className="text-amber-600" />
                            <span>Peringatan &amp; Pemeriksaan Cakupan Sheet ({previewSummary.warnings.length}):</span>
                          </div>
                          <ul className="space-y-0.5 pl-4 list-disc text-[11px]">
                            {previewSummary.warnings.map((w, i) => (
                              <li key={i}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Station Mapping Validation Summary (Authoritative Metadata Check) */}
                  {previewSummary.stationMappingSummary && (
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs mb-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2 font-bold text-slate-800">
                          <ShieldCheck size={16} className="text-emerald-600" />
                          <span>Validasi Metadata Stasiun Otoritatif (station_metadata.parquet):</span>
                        </div>
                        <span className="font-mono text-[11px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-semibold">
                          {previewSummary.stationMappingSummary.matched_stations_count} Pos Master Terpetakan
                        </span>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                        <div className="bg-white p-2 rounded border border-slate-200">
                          <span className="text-slate-500 block">Total Baris File:</span>
                          <span className="font-mono font-bold text-slate-800">{previewSummary.stationMappingSummary.total_rows_in_file}</span>
                        </div>
                        <div className="bg-white p-2 rounded border border-slate-200">
                          <span className="text-slate-500 block">Pos Master Cocok:</span>
                          <span className="font-mono font-bold text-emerald-700">{previewSummary.stationMappingSummary.matched_stations_count} Pos (100%)</span>
                        </div>
                        <div className="bg-white p-2 rounded border border-slate-200">
                          <span className="text-slate-500 block">Pos Eksternal Diisolasi:</span>
                          <span className={`font-mono font-bold ${previewSummary.stationMappingSummary.unmapped_external_stations_count > 0 ? 'text-amber-600' : 'text-slate-600'}`}>
                            {previewSummary.stationMappingSummary.unmapped_external_stations_count} Pos
                          </span>
                        </div>
                        <div className="bg-white p-2 rounded border border-slate-200">
                          <span className="text-slate-500 block">Duplikat / Tabrakan:</span>
                          <span className="font-mono font-bold text-emerald-700">0 (Nol)</span>
                        </div>
                      </div>
                      {previewSummary.unmappedExternalStations?.length > 0 && (
                        <div className="mt-2 text-[11px] text-amber-800 bg-amber-50 p-2 rounded border border-amber-200 flex items-start space-x-1.5">
                          <Info size={14} className="text-amber-600 shrink-0 mt-0.5" />
                          <div>
                            <strong>Pos Eksternal Diisolasi Aman:</strong> Pos di luar 57 master stations (misal: <em>{previewSummary.unmappedExternalStations.join(', ')}</em>) diisolasi dan tidak disisipkan ke master stations, menjaga integritas 57 stasiun.
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Period Selection Cards - Compact Filtered Layout */}
                  {previewSummary.periodsDetected.length > 0 && (() => {
                    const availableYears = Array.from(new Set(
                      previewSummary.periodsDetected
                        .map(p => {
                          const m = String(p.period_id || p.label || '').match(/\d{4}/);
                          return m ? m[0] : null;
                        })
                        .filter(Boolean)
                    )).sort().reverse();

                    const filteredPeriods = previewSummary.periodsDetected.filter(p => {
                      const q = periodSearchQuery.trim().toLowerCase();
                      const matchesQuery = !q || 
                        (p.label && p.label.toLowerCase().includes(q)) || 
                        (p.period_id && p.period_id.toLowerCase().includes(q)) ||
                        (p.start_date && p.start_date.includes(q)) ||
                        (p.end_date && p.end_date.includes(q));
                      
                      const matchesYear = periodYearFilter === 'ALL' || 
                        String(p.period_id || p.label || '').includes(periodYearFilter);
                      
                      return matchesQuery && matchesYear;
                    });

                    return (
                      <div className="period-selection-section bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <div className="flex-between mb-2 flex-wrap gap-2">
                          <div className="flex-align gap-2">
                            <Calendar size={15} className="text-sky-600" />
                            <h5 className="text-xs font-bold text-slate-800">
                              Pilih Periode Target yang Akan Disimpan:
                            </h5>
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-100 text-sky-800 border border-sky-200">
                              {selectedPeriods.length} dari {previewSummary.periodsDetected.length} dipilih
                            </span>
                          </div>
                          <div className="flex-align gap-2 text-xs">
                            <button
                              type="button"
                              className="btn-link-xs text-sky-700 hover:text-sky-900 font-medium"
                              onClick={() => {
                                const allFilteredIds = filteredPeriods.map(p => p.period_id);
                                setSelectedPeriods(prev => Array.from(new Set([...prev, ...allFilteredIds])));
                              }}
                            >
                              Pilih Semua {filteredPeriods.length < previewSummary.periodsDetected.length ? 'Hasil Filter' : ''}
                            </button>
                            <span>|</span>
                            <button
                              type="button"
                              className="btn-link-xs text-slate-600 hover:text-slate-800 font-medium"
                              onClick={() => {
                                const filteredIdsSet = new Set(filteredPeriods.map(p => p.period_id));
                                setSelectedPeriods(prev => prev.filter(id => !filteredIdsSet.has(id)));
                              }}
                            >
                              Kosongkan
                            </button>
                          </div>
                        </div>

                        {/* Search & Quick Filter Toolbar */}
                        <div className="flex items-center gap-2 mb-2">
                          <div className="relative flex-1">
                            <Search size={13} className="absolute left-2.5 top-2.5 text-slate-400" />
                            <input
                              type="text"
                              className="w-full text-xs pl-7 pr-2.5 py-1.5 bg-white border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-sky-500 text-slate-800 placeholder-slate-400"
                              placeholder="Cari periode (cth: 2026, Oktober, das1)..."
                              value={periodSearchQuery}
                              onChange={(e) => setPeriodSearchQuery(e.target.value)}
                            />
                            {periodSearchQuery && (
                              <button
                                type="button"
                                className="absolute right-2 top-2 text-slate-400 hover:text-slate-600 text-xs"
                                onClick={() => setPeriodSearchQuery('')}
                              >
                                &times;
                              </button>
                            )}
                          </div>

                          {availableYears.length > 1 && (
                            <select
                              className="text-xs py-1.5 px-2 bg-white border border-slate-200 rounded-md text-slate-700 focus:outline-none focus:ring-1 focus:ring-sky-500"
                              value={periodYearFilter}
                              onChange={(e) => setPeriodYearFilter(e.target.value)}
                            >
                              <option value="ALL">Semua Tahun ({availableYears.length})</option>
                              {availableYears.map(y => (
                                <option key={y} value={y}>{y}</option>
                              ))}
                            </select>
                          )}
                        </div>

                        {/* Compact Scrollable Cards List */}
                        <div className="periods-detected-grid max-h-[170px] overflow-y-auto pr-1">
                          {filteredPeriods.length === 0 ? (
                            <div className="text-center py-4 text-xs text-slate-500 col-span-full">
                              Tidak ada periode yang cocok dengan pencarian "{periodSearchQuery}".
                            </div>
                          ) : (
                            filteredPeriods.map((p) => {
                              const isSelected = selectedPeriods.includes(p.period_id);
                              return (
                                <div
                                  key={p.period_id}
                                  className={`period-item-card cursor-pointer transition p-2 rounded-md border ${
                                    isSelected 
                                      ? 'bg-sky-50/70 border-sky-400 shadow-xs' 
                                      : 'bg-white border-slate-200 hover:border-slate-300 opacity-75'
                                  }`}
                                  onClick={() => togglePeriodSelection(p.period_id)}
                                >
                                  <div className="flex items-center justify-between">
                                    <span className="font-semibold text-xs text-slate-800">{p.label}</span>
                                    {isSelected ? <CheckSquare size={15} className="text-sky-600 shrink-0" /> : <Square size={15} className="text-slate-400 shrink-0" />}
                                  </div>
                                  <div className="text-[11px] text-slate-500 mt-0.5 truncate">
                                    <span>{p.start_date || p.period_id} s.d. {p.end_date || ''}</span>
                                  </div>
                                  <div className="flex items-center gap-1 flex-wrap mt-1.5">
                                    {p.new_count > 0 && (
                                      <span className="text-[10px] px-1.5 py-0.2 rounded font-medium bg-emerald-100 text-emerald-800">
                                        +{p.new_count} Baru
                                      </span>
                                    )}
                                    {p.updated_count > 0 && (
                                      <span className="text-[10px] px-1.5 py-0.2 rounded font-medium bg-amber-100 text-amber-800">
                                        {p.updated_count} Update
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })
                          )}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Station Continuity & Gaps Warning */}
                  {previewSummary.stationGaps.length > 0 && (
                    <div className="preview-anomalies-card border-rose">
                      <div className="flex-align gap-2 mb-1">
                        <AlertTriangle size={15} className="text-rose-600" />
                        <span className="font-semibold text-xs text-rose-900">
                          Peringatan Kelengkapan Deret Waktu ({previewSummary.stationGaps.length} stasiun memiliki tanggal hilang/gap):
                        </span>
                      </div>
                      <ul className="anomalies-list">
                        {previewSummary.stationGaps.slice(0, 5).map((gap, i) => (
                          <li key={i} className="text-xs text-rose-800">
                            &bull; <strong>{gap.station_name}</strong>: Terlewat {gap.missing_dates_count} tanggal ({gap.missing_dates.slice(0, 3).join(', ')}...)
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Anomalies & Warnings */}
                  {previewSummary.anomalies && previewSummary.anomalies.length > 0 && (
                    <div className="preview-anomalies-card">
                      <div className="flex-align gap-2 mb-1">
                        <AlertTriangle size={15} className="text-amber-600" />
                        <span className="font-semibold text-xs text-amber-900">Perhatian &amp; Anomali Terdeteksi:</span>
                      </div>
                      <ul className="anomalies-list">
                        {previewSummary.anomalies.slice(0, 8).map((anom, i) => (
                          <li key={i} className="text-xs text-amber-800">
                            &bull; {typeof anom === 'string' ? anom : `${anom.type || 'Peringatan'}: ${anom.raw || anom.raw_value || anom.message || ''}`}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Diff Table with Filters */}
                  <div className="preview-sample-section">
                    <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h5 className="text-xs font-semibold text-slate-700">
                          Pratinjau Diff Data ({diffProductTab === 'ENSMEAN' ? previewSummary.detDiffList.length : filteredDiffList.length} baris ditampilkan):
                        </h5>
                        {previewSummary.detDiffList.length > 0 && (
                          <div className="inline-flex rounded-md border border-slate-300 overflow-hidden text-[11px]">
                            <button
                              type="button"
                              onClick={() => setDiffProductTab('PROB')}
                              className={`px-2.5 py-1 font-semibold transition ${
                                diffProductTab === 'PROB'
                                  ? 'bg-slate-800 text-white'
                                  : 'bg-white text-slate-700 hover:bg-slate-50'
                              }`}
                            >
                              Probabilitas ({filteredDiffList.length})
                            </button>
                            <button
                              type="button"
                              onClick={() => setDiffProductTab('ENSMEAN')}
                              className={`px-2.5 py-1 font-semibold transition ${
                                diffProductTab === 'ENSMEAN'
                                  ? 'bg-sky-700 text-white'
                                  : 'bg-white text-slate-700 hover:bg-slate-50'
                              }`}
                            >
                              Deterministik mm ({previewSummary.detDiffList.length})
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="flex-align gap-2 flex-wrap">
                        {previewSummary.periodsDetected.length > 1 && (
                          <div className="flex-align gap-1 text-xs">
                            <Calendar size={12} className="text-slate-400" />
                            <select
                              className="select-xs-styled"
                              value={diffFilterPeriod}
                              onChange={(e) => setDiffFilterPeriod(e.target.value)}
                              title="Saring baris pratinjau berdasarkan periode"
                            >
                              <option value="ALL">Semua Periode Terpilih ({selectedPeriods.length})</option>
                              {previewSummary.periodsDetected.map((p) => (
                                <option key={p.period_id} value={p.period_id}>
                                  {p.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                        <div className="flex-align gap-1 text-xs">
                          <Filter size={12} className="text-slate-400" />
                          <select
                            className="select-xs-styled"
                            value={diffFilterStatus}
                            onChange={(e) => setDiffFilterStatus(e.target.value)}
                          >
                            <option value="ALL">Semua Status</option>
                            <option value="NEW">Hanya Baru (NEW)</option>
                            <option value="NEW VINTAGE">Penerbitan Baru (NEW VINTAGE)</option>
                            <option value="UPDATED">Hanya Update (UPDATED)</option>
                            <option value="IDENTICAL">Identik (IDENTICAL)</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Scope & Selection Summary Bar */}
                    <div className="flex items-center gap-2 flex-wrap mb-2 text-[11px] bg-slate-50 border border-slate-200 rounded p-1.5 text-slate-600">
                      <span><strong>Periode dalam Berkas:</strong> {previewSummary.periodsDetected.length || 1}</span>
                      <span>&bull;</span>
                      <span><strong>Periode Terpilih Disimpan:</strong> {selectedPeriods.length}</span>
                      <span>&bull;</span>
                      <span><strong>Rekor Terpilih:</strong> {filteredDiffList.length} baris ditampilkan</span>
                    </div>

                    <div className="table-responsive-wrapper max-h-56">
                      {diffProductTab === 'ENSMEAN' && previewSummary.detDiffList.length > 0 ? (
                        <table className="preview-diff-table">
                          <thead>
                            <tr>
                              <th>Issue Date</th>
                              <th>Target Period</th>
                              <th>ID Pos</th>
                              <th>Nama Pos</th>
                              <th className="text-right">Curah Hujan (mm)</th>
                              <th className="text-center">Status Kolom</th>
                              <th>Kolom Sumber</th>
                              <th className="text-center">Status Diff</th>
                            </tr>
                          </thead>
                          <tbody>
                            {previewSummary.detDiffList.slice(0, 35).map((row, rIdx) => {
                              const st = row.change_type || 'NEW';
                              return (
                                <tr key={rIdx}>
                                  <td className="font-mono text-xs">{row.issue_date || '—'}</td>
                                  <td className="font-mono text-xs font-semibold text-sky-700">{row.period_id || row.target_period || '—'}</td>
                                  <td className="font-mono text-xs font-semibold">{row.station_id || '—'}</td>
                                  <td className="text-xs truncate max-w-xs">{row.station_name || '—'}</td>
                                  <td className="text-right font-mono text-xs font-bold text-slate-900">
                                    {row.value_mm !== null && row.value_mm !== undefined ? `${Number(row.value_mm).toFixed(1)} mm` : '—'}
                                  </td>
                                  <td className="text-center">
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                      row.adjustment_status === 'ADJUSTED'
                                        ? 'bg-emerald-100 text-emerald-800'
                                        : 'bg-sky-100 text-sky-800'
                                    }`}>
                                      {row.adjustment_status || 'REGULAR'}
                                    </span>
                                  </td>
                                  <td className="font-mono text-[11px] text-slate-600">{row.source_column || '—'}</td>
                                  <td className="text-center">
                                    <span className={`badge-diff-status status-${String(st).toLowerCase()}`}>
                                      {st}
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      ) : (
                      <table className="preview-diff-table">
                        <thead>
                          {previewData?.data_type?.includes('PROBABILITAS') || datasetType?.includes('PROBABILITAS') ? (
                            <tr>
                              <th>Forecast Issue</th>
                              <th>Target Period</th>
                              <th>ID Pos</th>
                              <th>Nama Pos &amp; Wilayah</th>
                              <th>Indikator</th>
                              <th className="text-right">Nilai Baru</th>
                              <th className="text-right">Nilai Lama</th>
                              <th className="text-right">Diff</th>
                              <th className="text-center">Status Diff</th>
                            </tr>
                          ) : previewData?.data_type?.includes('SPI') || datasetType?.includes('SPI') ? (
                            <tr>
                              <th>Tanggal Referensi</th>
                              <th>ID Pos</th>
                              <th>Nama Pos &amp; Wilayah</th>
                              <th>Skala</th>
                              <th className="text-right">Nilai Baru</th>
                              <th className="text-right">Nilai Lama</th>
                              <th className="text-right">Diff</th>
                              <th className="text-center">Status Diff</th>
                            </tr>
                          ) : (
                            <tr>
                              <th>Tanggal Observasi</th>
                              <th>ID Pos</th>
                              <th>Nama Pos &amp; Wilayah</th>
                              <th className="text-right">Nilai Baru (mm)</th>
                              <th className="text-right">Nilai Lama (mm)</th>
                              <th className="text-right">Diff (mm)</th>
                              <th className="text-center">Status Diff</th>
                            </tr>
                          )}
                        </thead>
                        <tbody>
                          {filteredDiffList.length > 0 ? (
                            filteredDiffList.slice(0, 35).map((row, rIdx) => {
                              const isProbRow = previewData?.data_type?.includes('PROBABILITAS') || datasetType?.includes('PROBABILITAS');
                              const isSpiRow = previewData?.data_type?.includes('SPI') || datasetType?.includes('SPI');

                              const sid = row.station_id || '-';
                              const sname = row.station_name || '-';
                              const status = row.change_type || row.status || 'NEW';

                              if (isProbRow) {
                                const issue = row.forecast_issue_date || row.issue_date || '—';
                                const target = row.target_period || row.period_id || row.period_label || '—';
                                const indicator = row.indicator || row.forecast_parameter || '—';
                                const newV = row.new_value !== null && row.new_value !== undefined
                                  ? `${row.new_value}%`
                                  : (row.probability_value !== null && row.probability_value !== undefined ? `${row.probability_value}%` : '—');
                                const oldV = row.old_value !== null && row.old_value !== undefined ? `${row.old_value}%` : '—';
                                const diffV = row.diff !== null && row.diff !== undefined
                                  ? `${row.diff > 0 ? `+${row.diff}` : row.diff}%`
                                  : '—';

                                return (
                                  <tr key={rIdx}>
                                    <td className="font-mono text-xs">{issue}</td>
                                    <td className="font-mono text-xs font-semibold text-purple-700">{target}</td>
                                    <td className="font-mono text-xs font-semibold">{sid}</td>
                                    <td className="text-xs truncate max-w-xs">{sname}</td>
                                    <td className="font-mono text-xs font-bold text-slate-700">{indicator}</td>
                                    <td className="text-right font-mono text-xs font-bold text-purple-700">{newV}</td>
                                    <td className="text-right font-mono text-xs text-slate-500">{oldV}</td>
                                    <td className="text-right font-mono text-xs font-semibold text-slate-700">{diffV}</td>
                                    <td className="text-center">
                                      <span className={`badge-diff-status status-${String(status).toLowerCase()}`}>
                                        {status}
                                      </span>
                                    </td>
                                  </tr>
                                );
                              }

                              if (isSpiRow) {
                                const refD = row.ref_date || row.date || row.period_id || '—';
                                const scale = row.scale || timescale || '—';
                                const newV = row.new_value !== null && row.new_value !== undefined
                                  ? Number(row.new_value).toFixed(2)
                                  : (row.new_spi !== null && row.new_spi !== undefined ? Number(row.new_spi).toFixed(2) : '—');
                                const oldV = row.old_value !== null && row.old_value !== undefined
                                  ? Number(row.old_value).toFixed(2)
                                  : (row.old_spi !== null && row.old_spi !== undefined ? Number(row.old_spi).toFixed(2) : '—');
                                const diffV = row.diff !== null && row.diff !== undefined
                                  ? (row.diff > 0 ? `+${Number(row.diff).toFixed(2)}` : Number(row.diff).toFixed(2))
                                  : '—';

                                return (
                                  <tr key={rIdx}>
                                    <td className="font-mono text-xs">{refD}</td>
                                    <td className="font-mono text-xs font-semibold">{sid}</td>
                                    <td className="text-xs truncate max-w-xs">{sname}</td>
                                    <td className="font-mono text-xs text-indigo-700 font-semibold">{scale}</td>
                                    <td className="text-right font-mono text-xs font-bold text-indigo-700">{newV}</td>
                                    <td className="text-right font-mono text-xs text-slate-500">{oldV}</td>
                                    <td className="text-right font-mono text-xs font-semibold text-slate-700">{diffV}</td>
                                    <td className="text-center">
                                      <span className={`badge-diff-status status-${String(status).toLowerCase()}`}>
                                        {status}
                                      </span>
                                    </td>
                                  </tr>
                                );
                              }

                              // Default: Curah Hujan
                              const obsD = row.observation_date || row.date || '—';
                              const newV = row.new_value !== null && row.new_value !== undefined
                                ? `${row.new_value} mm`
                                : (row.new_rainfall_mm !== null && row.new_rainfall_mm !== undefined
                                  ? `${row.new_rainfall_mm} mm`
                                  : (row.obs_status ? `(${row.obs_status})` : '—'));
                              const oldV = row.old_value !== null && row.old_value !== undefined
                                ? `${row.old_value} mm`
                                : (row.old_rainfall_mm !== null && row.old_rainfall_mm !== undefined
                                  ? `${row.old_rainfall_mm} mm`
                                  : (row.old_obs_status ? `(${row.old_obs_status})` : '—'));
                              const diffV = row.diff !== null && row.diff !== undefined
                                ? `${row.diff > 0 ? `+${row.diff}` : row.diff} mm`
                                : '—';

                              return (
                                <tr key={rIdx}>
                                  <td className="font-mono text-xs">{obsD}</td>
                                  <td className="font-mono text-xs font-semibold">{sid}</td>
                                  <td className="text-xs truncate max-w-xs">{sname}</td>
                                  <td className="text-right font-mono text-xs font-bold text-sky-700">{newV}</td>
                                  <td className="text-right font-mono text-xs text-slate-500">{oldV}</td>
                                  <td className="text-right font-mono text-xs font-semibold text-slate-700">{diffV}</td>
                                  <td className="text-center">
                                    <span className={`badge-diff-status status-${String(status).toLowerCase()}`}>
                                      {status}
                                    </span>
                                  </td>
                                </tr>
                              );
                            })
                          ) : (
                            <tr>
                              <td colSpan={9} className="text-center text-xs text-muted py-3">
                                Tidak ada baris sampel yang cocok dengan filter.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                      )}
                    </div>
                  </div>

                  {/* Scoped Update Authorization & Operator Block */}
                  <div className="operator-confirm-box">
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className="text-xs font-semibold text-slate-700 block mb-1">
                          Nama Operator Bertanggung Jawab:
                        </label>
                        <input
                          type="text"
                          className="input-operator-styled"
                          value={operatorName}
                          onChange={(e) => setOperatorName(e.target.value)}
                          placeholder="Nama atau ID Petugas..."
                        />
                      </div>
                      <div>
                        <label className="text-xs font-semibold text-slate-700 block mb-1">
                          Catatan / Alasan Pembaruan:
                        </label>
                        <input
                          type="text"
                          className="input-operator-styled"
                          value={operatorNotes}
                          onChange={(e) => setOperatorNotes(e.target.value)}
                          placeholder="Misal: Input data observasi D3 September 2026..."
                        />
                      </div>
                    </div>

                    {/* Explicit Scoped Update Consent Checkbox */}
                    {previewSummary.totalUpdated > 0 && (
                      <div className={`update-consent-box ${explicitUpdateConsent ? 'consent-granted' : 'consent-pending'} mb-3 p-2.5 rounded border text-xs`}>
                        <label className="flex-align gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={explicitUpdateConsent}
                            onChange={(e) => setExplicitUpdateConsent(e.target.checked)}
                          />
                          <span className="font-semibold text-slate-800">
                            Saya mengizinkan pembaruan data pada periode terkait ({previewSummary.totalUpdated} catatan lama berbeda).
                          </span>
                        </label>
                        <p className="text-xs mt-1 text-slate-600 pl-5">
                          {explicitUpdateConsent ? (
                            <span className="text-emerald-700 font-medium">
                              ✓ Izin diberikan: Data lama pada periode yang dipilih akan diperbarui secara aman dengan integritas audit trail.
                            </span>
                          ) : (
                            <span className="text-amber-700 font-medium">
                              ⚠ Tanpa izin ini: Hanya catatan baru (NEW) yang akan disimpan. Catatan lama yang bernilai berbeda akan dilewati tanpa diubah.
                            </span>
                          )}
                        </p>
                      </div>
                    )}

                    <label className="confirm-checkbox-row">
                      <input
                        type="checkbox"
                        checked={confirmCheckbox}
                        onChange={(e) => setConfirmCheckbox(e.target.checked)}
                      />
                      <span className="text-xs text-slate-800 font-medium">
                        Saya menyatakan telah memverifikasi pratinjau data ini dan menyetujui penyimpanan ke basis data operasional DSS-PIK.
                      </span>
                    </label>
                  </div>

                  {commitError && (
                    <div className="table-error-banner">
                      <AlertCircle size={16} />
                      <span>{commitError}</span>
                    </div>
                  )}

                  <div className="wizard-actions-bar">
                    <button
                      type="button"
                      className="btn-wizard-cancel"
                      onClick={() => setWizardStep(1)}
                      disabled={commitLoading}
                    >
                      Kembali ke Pemilihan Berkas
                    </button>

                    <button
                      type="button"
                      className="btn-wizard-commit"
                      onClick={handleCommitIngestion}
                      disabled={
                        !confirmCheckbox ||
                        commitLoading ||
                        previewSummary.hasAdjustConflicts ||
                        previewSummary.isIncompleteDasarianRelease ||
                        (selectedPeriods.length === 0 && previewSummary.periodsDetected.length > 0)
                      }
                    >
                      {commitLoading ? (
                        <>
                          <div className="spin spinner-sm"></div>
                          <span>Menyimpan Transaksi Atomik...</span>
                        </>
                      ) : (
                        <>
                          <ShieldCheck size={15} />
                          <span>Simpan Periode Terpilih ({selectedPeriods.length})</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 4: RESULT & PERIOD SYNC */}
              {wizardStep === 4 && commitResult && (
                <div className="wizard-body-flow text-center py-6">
                  <div className="commit-success-badge mx-auto mb-3">
                    <CheckCircle2 size={42} className="text-emerald-600" />
                  </div>
                  <h3 className="text-base font-bold text-slate-800 mb-1">
                    Ingestion Data Berhasil Disimpan!
                  </h3>
                  <p className="text-xs text-slate-600 max-w-md mx-auto mb-4">
                    Data telah berhasil diselaraskan secara transaksional ke basis data operasional. Log audit telah dicatat secara permanen.
                  </p>

                  <div className="commit-metrics-card max-w-md mx-auto mb-6 text-left">
                    <div className="scope-row text-xs py-1">
                      <span className="text-muted">Batch ID:</span>
                      <span className="font-mono text-xs">{commitResult.batch_id}</span>
                    </div>
                    <div className="scope-row text-xs py-1">
                      <span className="text-muted">Dataset:</span>
                      <span className="font-semibold">{commitResult.data_type || commitResult.dataset_type}</span>
                    </div>
                    <div className="scope-row text-xs py-1">
                      <span className="text-muted">Periode Diperbarui:</span>
                      <span className="font-mono text-xs font-semibold text-sky-700">
                        {commitResult.periods_updated?.length > 0 ? commitResult.periods_updated.join(', ') : 'Semua Periode File'}
                      </span>
                    </div>
                    <div className="scope-row text-xs py-1">
                      <span className="text-muted">Catatan Baru Ditambahkan:</span>
                      <span className="font-mono font-bold text-emerald-700">+{commitResult.records_added ?? commitResult.new_records ?? 0}</span>
                    </div>
                    <div className="scope-row text-xs py-1">
                      <span className="text-muted">Catatan Diperbarui:</span>
                      <span className="font-mono font-bold text-amber-700">{commitResult.records_updated ?? commitResult.updated_records ?? 0}</span>
                    </div>
                    {commitResult.records_rejected > 0 && (
                      <div className="scope-row text-xs py-1">
                        <span className="text-muted">Catatan Dilewati (Tanpa Izin):</span>
                        <span className="font-mono font-bold text-slate-500">{commitResult.records_rejected}</span>
                      </div>
                    )}
                    <div className="scope-row text-xs py-1">
                      <span className="text-muted">Konsistensi Penyimpanan:</span>
                      <span className="font-semibold text-emerald-700">{commitResult.storage_consistency || 'KONSISTEN'}</span>
                    </div>
                  </div>

                  <div className="flex-align justify-center gap-3">
                    {onOpenManagement && (
                      <button
                        type="button"
                        className="btn-wizard-cancel"
                        onClick={() => onOpenManagement('BATCHES')}
                      >
                        Lihat Log Riwayat Batch
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn-wizard-primary"
                      onClick={onClose}
                    >
                      Selesai &amp; Tutup
                    </button>
                  </div>
                </div>
              )}
            </div>
        </div>
      </div>
    </div>
  );
}
