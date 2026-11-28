import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Database,
  RefreshCw,
  FolderCog,
  Filter,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  FileSpreadsheet,
  RotateCcw,
  ShieldAlert,
  ChevronRight,
  Eye,
  Trash2,
  Calendar,
  Layers,
  Search,
  X,
  Edit3,
  Check,
  TrendingUp,
  Activity,
  CloudRain,
  Compass,
  FileText,
  Clock,
  ArrowRight,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import CanonicalStorageStatusCard from './CanonicalStorageStatusCard';
import RainfallManagementTab from './RainfallManagementTab';

/**
 * OperationalDataManager
 * Ruang Kerja Manajemen Data Operasional DSS-PIK BMKG Kepulauan Riau
 * Mendukung:
 * - Bagian A: 6 KPI Cards Real-Time (Total Batch, Berhasil, Rollback, Record Baru, Diperbarui, Ditolak)
 * - Bagian B: Tab Navigasi Terstruktur (Ringkasan Penyimpanan, Riwayat Batch, Koreksi & Pembatalan, Vintage ECMWF)
 * - Bagian C: Tabel Riwayat Batch Ingestion dengan Filter, Pencarian, & Pagination
 * - Bagian D: Modal Detail Batch Lengkap & Scoped Rollback
 * - Bagian E: Sub-Form Koreksi & Pembatalan Rekor (CH, SPI terisolasi per skala, Probabilitas Snapshot)
 * - Bagian F: Penjelajah Vintage Prakiraan ECMWF
 */
export default function OperationalDataManager({ initialTab = 'STORAGE', initialCorrectionDataset = 'ALL' }) {
  // Active Tab: 'STORAGE' | 'BATCHES' | 'CORRECTIONS' | 'VINTAGES'
  const [managerTab, setManagerTab] = useState(initialTab);
  const [correctionDatasetFilter, setCorrectionDatasetFilter] = useState(initialCorrectionDataset || 'ALL');

  useEffect(() => {
    if (initialTab) setManagerTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (initialCorrectionDataset) setCorrectionDatasetFilter(initialCorrectionDataset);
  }, [initialCorrectionDataset]);

  // 1. KPI Operational Summary State
  const [summary, setSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // 2. Canonical Storage Status State
  const [latestStatus, setLatestStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(false);

  // 3. Batches List State
  const [batches, setBatches] = useState([]);
  const [batchesTotal, setBatchesTotal] = useState(0);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [filterType, setFilterType] = useState('ALL');
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [batchPage, setBatchPage] = useState(0);
  const limit = 20;

  // 4. Batch Detail Modal State
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // 5. Batch Rollback/Cancel Modal State
  const [cancelModalBatch, setCancelModalBatch] = useState(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelOperator, setCancelOperator] = useState('OPERATOR_BMKG');
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState(null);

  // 6. Master Stations for Dropdown
  const [masterStations, setMasterStations] = useState([]);

  // 7. Corrections & Voiding States
  // Sub-Form A: Koreksi Curah Hujan Harian
  const [corrStationId, setCorrStationId] = useState('21720201A');
  const [corrDate, setCorrDate] = useState('2026-10-10');
  const [corrNewRainfall, setCorrNewRainfall] = useState('');
  const [corrReason, setCorrReason] = useState('');
  const [corrOperator, setCorrOperator] = useState('OPERATOR_BMKG');
  const [corrLoading, setCorrLoading] = useState(false);

  // Sub-Form B: Void Curah Hujan
  const [voidChStationId, setVoidChStationId] = useState('21720201A');
  const [voidChDate, setVoidChDate] = useState('2026-10-10');
  const [voidChReason, setVoidChReason] = useState('');
  const [voidChOperator, setVoidChOperator] = useState('OPERATOR_BMKG');
  const [voidChLoading, setVoidChLoading] = useState(false);

  // Sub-Form C: Void SPI (terisolasi per skala & periode)
  const [voidSpiStationId, setVoidSpiStationId] = useState('21010401A');
  const [voidSpiPeriodType, setVoidSpiPeriodType] = useState('DASARIAN');
  const [voidSpiTimescale, setVoidSpiTimescale] = useState('30D');
  const [voidSpiDate, setVoidSpiDate] = useState('2026-10-01');
  const [voidSpiReason, setVoidSpiReason] = useState('');
  const [voidSpiOperator, setVoidSpiOperator] = useState('OPERATOR_BMKG');
  const [voidSpiLoading, setVoidSpiLoading] = useState(false);

  // Sub-Form D: Void Probabilitas ECMWF
  const [voidProbIssueDate, setVoidProbIssueDate] = useState('2026-10-19');
  const [voidProbTargetPeriod, setVoidProbTargetPeriod] = useState('2026-11-das1');
  const [voidProbStationId, setVoidProbStationId] = useState('');
  const [voidProbParam, setVoidProbParam] = useState('');
  const [voidProbReason, setVoidProbReason] = useState('');
  const [voidProbOperator, setVoidProbOperator] = useState('OPERATOR_BMKG');
  const [voidProbLoading, setVoidProbLoading] = useState(false);

  // Sub-Form E: Soft-Void & Reaktivasi ENSMEAN (Terisolasi dari Probabilitas)
  const [detActionMode, setDetActionMode] = useState('VOID'); // 'VOID' | 'REACTIVATE'
  const [detIssueDate, setDetIssueDate] = useState('');
  const [detResolution, setDetResolution] = useState('DASARIAN');
  const [detTargetPeriod, setDetTargetPeriod] = useState('');
  const [detStationId, setDetStationId] = useState('');
  const [detReason, setDetReason] = useState('');
  const [detConfirmChecked, setDetConfirmChecked] = useState(false);
  const [detOperator] = useState('OPERATOR_BMKG');
  const [detLoading, setDetLoading] = useState(false);
  const [detHistory, setDetHistory] = useState([]);
  const [loadingDetHistory, setLoadingDetHistory] = useState(false);
  const [detVintages, setDetVintages] = useState([]);
  const [loadingDetVintages, setLoadingDetVintages] = useState(false);

  // Action Success/Error Notification State
  const [actionAlert, setActionAlert] = useState(null); // { type: 'success' | 'error', message: string }

  // 8. Forecast Vintages State
  const [vintages, setVintages] = useState([]);
  const [loadingVintages, setLoadingVintages] = useState(false);

  // 9. Correction & Void Audit Logs State
  const [correctionLogs, setCorrectionLogs] = useState([]);
  const [loadingCorrectionLogs, setLoadingCorrectionLogs] = useState(false);

  // =========================================================================
  // DATA FETCHING
  // =========================================================================

  // Fetch Summary KPI
  const fetchSummary = useCallback(async () => {
    setLoadingSummary(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_OPERATIONAL_SUMMARY);
      if (res.ok) {
        const data = await res.json();
        setSummary(data);
      }
    } catch (e) {
      console.error('Failed to fetch operational summary KPI:', e);
    } finally {
      setLoadingSummary(false);
    }
  }, []);

  // Fetch Status Data Operasional
  const fetchStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_LATEST_STATUS);
      if (res.ok) {
        const data = await res.json();
        setLatestStatus(data);
      }
    } catch (e) {
      console.error('Failed to fetch operational status:', e);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  // Fetch Batches
  const fetchBatches = useCallback(async () => {
    setLoadingBatches(true);
    try {
      const params = {
        limit,
        offset: batchPage * limit,
        data_type: filterType !== 'ALL' ? filterType : undefined,
        status: filterStatus !== 'ALL' ? filterStatus : undefined,
      };
      const res = await authFetch(API_ENDPOINTS.INGESTION_BATCHES(params));
      if (res.ok) {
        const data = await res.json();
        setBatches(data.items || []);
        setBatchesTotal(data.total || 0);
      }
    } catch (e) {
      console.error('Failed to fetch batches:', e);
    } finally {
      setLoadingBatches(false);
    }
  }, [filterType, filterStatus, batchPage]);

  // Fetch Master Stations
  const fetchMasterStations = useCallback(async () => {
    try {
      const res = await authFetch(API_ENDPOINTS.STATIONS_MASTER);
      if (res.ok) {
        const data = await res.json();
        setMasterStations(data.stations || []);
      }
    } catch (e) {
      console.error('Failed to fetch stations master:', e);
    }
  }, []);

  // Fetch Vintages
  const fetchVintages = useCallback(async () => {
    setLoadingVintages(true);
    try {
      const res = await authFetch(API_ENDPOINTS.FORECAST_VINTAGES());
      if (res.ok) {
        const data = await res.json();
        setVintages(data.vintages || []);
      }
    } catch (e) {
      console.error('Failed to fetch forecast vintages:', e);
    } finally {
      setLoadingVintages(false);
    }
  }, []);

  // Fetch Correction & Void Logs
  const fetchCorrectionLogs = useCallback(async () => {
    setLoadingCorrectionLogs(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_CORRECTIONS_LOG(100));
      if (res.ok) {
        const data = await res.json();
        setCorrectionLogs(data.items || []);
      }
    } catch (e) {
      console.error('Failed to fetch correction logs:', e);
    } finally {
      setLoadingCorrectionLogs(false);
    }
  }, []);

  // Fetch Deterministic (ENSMEAN) Vintages & History
  const fetchDeterministicVintages = useCallback(async () => {
    setLoadingDetVintages(true);
    try {
      const res = await authFetch(API_ENDPOINTS.DETERMINISTIC_VINTAGES({ include_voided: true }));
      if (res.ok) {
        const data = await res.json();
        setDetVintages(data.vintages || []);
      }
    } catch (e) {
      console.error('Failed to fetch ENSMEAN vintages:', e);
    } finally {
      setLoadingDetVintages(false);
    }
  }, []);

  const fetchDeterministicHistory = useCallback(async () => {
    setLoadingDetHistory(true);
    try {
      const res = await authFetch(API_ENDPOINTS.DETERMINISTIC_HISTORY({ limit: 30 }));
      if (res.ok) {
        const data = await res.json();
        setDetHistory(data.history || []);
      }
    } catch (e) {
      console.error('Failed to fetch ENSMEAN history:', e);
    } finally {
      setLoadingDetHistory(false);
    }
  }, []);

  // Initial & Refresh Load
  const refreshAll = useCallback(() => {
    fetchSummary();
    fetchStatus();
    fetchBatches();
    fetchVintages();
    fetchMasterStations();
    fetchCorrectionLogs();
    fetchDeterministicVintages();
    fetchDeterministicHistory();
  }, [
    fetchSummary,
    fetchStatus,
    fetchBatches,
    fetchVintages,
    fetchMasterStations,
    fetchCorrectionLogs,
    fetchDeterministicVintages,
    fetchDeterministicHistory,
  ]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Filtered Batches by search query
  const filteredBatches = useMemo(() => {
    if (!searchQuery.trim()) return batches;
    const q = searchQuery.toLowerCase();
    return batches.filter(
      (b) =>
        b.batch_id?.toLowerCase().includes(q) ||
        b.file_name?.toLowerCase().includes(q) ||
        b.operator?.toLowerCase().includes(q) ||
        b.data_type?.toLowerCase().includes(q)
    );
  }, [batches, searchQuery]);

  // =========================================================================
  // ACTIONS & HANDLERS
  // =========================================================================

  // Open Batch Detail
  const handleOpenDetail = async (batchId) => {
    setLoadingDetail(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_BATCH_DETAIL(batchId));
      if (res.ok) {
        const data = await res.json();
        setSelectedBatch(data);
      }
    } catch (e) {
      console.error('Failed to fetch batch detail:', e);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Submit Batch Rollback
  const handleCancelBatchSubmit = async () => {
    if (!cancelModalBatch || !cancelReason.trim()) return;
    setCancelLoading(true);
    setCancelError(null);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_BATCH_CANCEL(cancelModalBatch.batch_id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason: cancelReason.trim(),
          operator: cancelOperator || 'OPERATOR_BMKG',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Pembatalan batch gagal`);
      }

      const resData = await res.json();
      setCancelModalBatch(null);
      setCancelReason('');
      setActionAlert({
        type: 'success',
        message: resData.message || `Batch ${resData.batch_id} berhasil dibatalkan.`,
      });
      refreshAll();
    } catch (err) {
      setCancelError(err.message || 'Gagal membatalkan batch.');
    } finally {
      setCancelLoading(false);
    }
  };

  // Sub-Form A: Koreksi Curah Hujan
  const handleRecordCorrection = async (e) => {
    e.preventDefault();
    if (!corrStationId || !corrDate || corrNewRainfall === '' || !corrReason.trim()) {
      setActionAlert({ type: 'error', message: 'Semua kolom koreksi dan alasan wajib diisi.' });
      return;
    }
    setCorrLoading(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_RECORD_CORRECT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_id: corrStationId.trim(),
          date: corrDate.trim(),
          new_rainfall_mm: parseFloat(corrNewRainfall),
          reason: corrReason.trim(),
          operator: corrOperator || 'OPERATOR_BMKG',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Koreksi gagal`);
      }

      const resData = await res.json();
      setActionAlert({ type: 'success', message: resData.message });
      setCorrNewRainfall('');
      setCorrReason('');
      refreshAll();
    } catch (err) {
      setActionAlert({ type: 'error', message: err.message || 'Gagal mengoreksi rekor CH.' });
    } finally {
      setCorrLoading(false);
    }
  };

  // Sub-Form B: Void Curah Hujan
  const handleVoidRainfall = async (e) => {
    e.preventDefault();
    if (!voidChStationId || !voidChDate || !voidChReason.trim()) {
      setActionAlert({ type: 'error', message: 'ID Pos, Tanggal, dan Alasan pembatalan wajib diisi.' });
      return;
    }
    setVoidChLoading(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_RECORD_VOID, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_id: voidChStationId.trim(),
          date: voidChDate.trim(),
          reason: voidChReason.trim(),
          operator: voidChOperator || 'OPERATOR_BMKG',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Pembatalan rekor gagal`);
      }

      const resData = await res.json();
      setActionAlert({ type: 'success', message: resData.message });
      setVoidChReason('');
      refreshAll();
    } catch (err) {
      setActionAlert({ type: 'error', message: err.message || 'Gagal membatalkan rekor CH.' });
    } finally {
      setVoidChLoading(false);
    }
  };

  // Sub-Form C: Void SPI (terisolasi per skala)
  const handleVoidSpi = async (e) => {
    e.preventDefault();
    if (!voidSpiStationId || !voidSpiDate || !voidSpiReason.trim()) {
      setActionAlert({ type: 'error', message: 'ID Pos, Tanggal/Periode, dan Alasan pembatalan SPI wajib diisi.' });
      return;
    }
    setVoidSpiLoading(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_SPI_VOID, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_id: voidSpiStationId.trim(),
          period_type: voidSpiPeriodType,
          timescale: voidSpiTimescale,
          date: voidSpiDate.trim(),
          reason: voidSpiReason.trim(),
          operator: voidSpiOperator || 'OPERATOR_BMKG',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Pembatalan rekor SPI gagal`);
      }

      const resData = await res.json();
      setActionAlert({ type: 'success', message: resData.message });
      setVoidSpiReason('');
      refreshAll();
    } catch (err) {
      setActionAlert({ type: 'error', message: err.message || 'Gagal membatalkan rekor SPI.' });
    } finally {
      setVoidSpiLoading(false);
    }
  };

  // Sub-Form D: Void Probabilitas Snapshot
  const handleVoidProbability = async (e) => {
    e.preventDefault();
    if (!voidProbIssueDate || !voidProbTargetPeriod || !voidProbReason.trim()) {
      setActionAlert({ type: 'error', message: 'Tanggal Issue, Periode Target, dan Alasan pembatalan probabilitas wajib diisi.' });
      return;
    }
    setVoidProbLoading(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_PROBABILITY_VOID, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          issue_date: voidProbIssueDate.trim(),
          target_period: voidProbTargetPeriod.trim(),
          station_id: voidProbStationId.trim() || null,
          forecast_parameter: voidProbParam.trim() || null,
          reason: voidProbReason.trim(),
          operator: voidProbOperator || 'OPERATOR_BMKG',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Pembatalan snapshot probabilitas gagal`);
      }

      const resData = await res.json();
      setActionAlert({ type: 'success', message: resData.message });
      setVoidProbReason('');
      refreshAll();
    } catch (err) {
      setActionAlert({ type: 'error', message: err.message || 'Gagal membatalkan snapshot probabilitas.' });
    } finally {
      setVoidProbLoading(false);
    }
  };

  // Sub-Form E: Soft-Void atau Reaktivasi ENSMEAN (Terisolasi dari Probabilitas)
  const handleDeterministicVoidOrReactivate = async (e) => {
    e.preventDefault();
    if (!detIssueDate || !detReason.trim()) {
      setActionAlert({
        type: 'error',
        message: 'Tanggal Issue (issue_date) dan Alasan wajib diisi untuk pengelolaan vintage deterministik.',
      });
      return;
    }
    if (!detConfirmChecked) {
      setActionAlert({
        type: 'error',
        message: 'Centang konfirmasi terlebih dahulu sebelum menjalankan Pembatalan / Aktifkan Kembali Vintage.',
      });
      return;
    }

    setDetLoading(true);
    try {
      const endpoint =
        detActionMode === 'REACTIVATE'
          ? API_ENDPOINTS.INGESTION_DETERMINISTIC_REACTIVATE
          : API_ENDPOINTS.INGESTION_DETERMINISTIC_VOID;

      const res = await authFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          issue_date: detIssueDate.trim(),
          forecast_resolution: detResolution,
          target_period: detTargetPeriod.trim() || null,
          station_id: detStationId.trim() || null,
          reason: detReason.trim(),
          operator: detOperator || 'OPERATOR_BMKG',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(
          errJson.detail || `HTTP ${res.status}: Operasi ${detActionMode} data deterministik gagal`
        );
      }

      const resData = await res.json();
      const affected =
        detActionMode === 'REACTIVATE'
          ? resData.records_reactivated ?? 0
          : resData.records_voided ?? 0;
      setActionAlert({
        type: 'success',
        message:
          detActionMode === 'REACTIVATE'
            ? `Aktifkan Kembali Vintage Deterministik (${detResolution}, issue ${detIssueDate}) berhasil: ${affected} rekor diaktifkan kembali (Audit: ${resData.audit_batch_id}).`
            : `Batalkan Vintage Deterministik (${detResolution}, issue ${detIssueDate}) berhasil: ${affected} rekor dinonaktifkan tanpa memengaruhi Probabilitas (Audit: ${resData.audit_batch_id}).`,
      });
      setDetReason('');
      setDetConfirmChecked(false);
      refreshAll();
    } catch (err) {
      setActionAlert({
        type: 'error',
        message: err.message || 'Gagal memproses tindakan data deterministik.',
      });
    } finally {
      setDetLoading(false);
    }
  };

  return (
    <div className="operational-management-container space-y-5">
      {/* 1. HEADER BANNER */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3.5">
            <div className="w-11 h-11 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-800 shrink-0">
              <FolderCog size={24} />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base sm:text-lg">
                Pusat Pengelolaan Data Operasional DSS-PIK
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Monitoring canonical storage real-time, audit batch ingestion, rollback terkendali, dan koreksi rekor observasi.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            <button
              type="button"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 text-xs font-semibold transition border border-slate-200"
              onClick={refreshAll}
              disabled={loadingStatus || loadingSummary}
              title="Segarkan seluruh indikator data operasional"
            >
              <RefreshCw size={13} className={loadingStatus || loadingSummary ? 'animate-spin text-emerald-700' : ''} />
              <span>Segarkan Semua</span>
            </button>
          </div>
        </div>

        {/* Action Alert Banner */}
        {actionAlert && (
          <div
            className={`mt-4 p-3 rounded-lg flex items-center justify-between text-xs border ${
              actionAlert.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-rose-50 border-rose-200 text-rose-800'
            }`}
          >
            <div className="flex items-center space-x-2">
              {actionAlert.type === 'success' ? (
                <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle size={16} className="text-rose-600 shrink-0" />
              )}
              <span className="font-medium">{actionAlert.message}</span>
            </div>
            <button
              type="button"
              onClick={() => setActionAlert(null)}
              className="text-slate-400 hover:text-slate-600 ml-2"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </div>

      {/* BAGIAN A: 6 OPERATIONAL SUMMARY KPI CARDS */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Card 1: Total Batch */}
        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
            Total Batch
          </div>
          <div className="text-xl sm:text-2xl font-mono font-bold text-slate-800">
            {summary?.total_batches ?? batchesTotal}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Sesi terdaftar di DB</div>
        </div>

        {/* Card 2: Batch Berhasil */}
        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs border-l-4 border-l-emerald-500">
          <div className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider mb-1">
            Batch Berhasil
          </div>
          <div className="text-xl sm:text-2xl font-mono font-bold text-emerald-700">
            {summary?.successful_batches ?? (batches.filter((b) => b.status === 'COMPLETED').length || 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Komitmen transaksional</div>
        </div>

        {/* Card 3: Batch Dibatalkan */}
        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs border-l-4 border-l-rose-500">
          <div className="text-[11px] font-semibold text-rose-700 uppercase tracking-wider mb-1">
            Batch Dibatalkan
          </div>
          <div className="text-xl sm:text-2xl font-mono font-bold text-rose-700">
            {summary?.rolled_back_batches ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Rollback berizin</div>
        </div>

        {/* Card 4: Total Record Baru */}
        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs border-l-4 border-l-sky-500">
          <div className="text-[11px] font-semibold text-sky-700 uppercase tracking-wider mb-1">
            Record Baru
          </div>
          <div className="text-xl sm:text-2xl font-mono font-bold text-sky-800">
            +{summary?.total_new_records?.toLocaleString('id-ID') ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Data baru tersimpan</div>
        </div>

        {/* Card 5: Total Record Diperbarui */}
        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs border-l-4 border-l-amber-500">
          <div className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider mb-1">
            Record Update
          </div>
          <div className="text-xl sm:text-2xl font-mono font-bold text-amber-700">
            {summary?.total_updated_records?.toLocaleString('id-ID') ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Update berizin operator</div>
        </div>

        {/* Card 6: Total Record Ditolak */}
        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs border-l-4 border-l-slate-400">
          <div className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">
            Record Ditolak
          </div>
          <div className="text-xl sm:text-2xl font-mono font-bold text-slate-700">
            {summary?.total_rejected_records?.toLocaleString('id-ID') ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Anomali / duplikat ditolak</div>
        </div>
      </div>

      {/* BAGIAN B: TAB NAVIGASI TERSTRUKTUR */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="flex border-b border-slate-200 overflow-x-auto bg-slate-50">
          <button
            type="button"
            className={`px-4 py-3 text-xs font-bold border-b-2 transition flex items-center space-x-2 whitespace-nowrap ${
              managerTab === 'STORAGE'
                ? 'border-emerald-600 text-emerald-900 bg-white'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
            onClick={() => setManagerTab('STORAGE')}
          >
            <Database size={15} className={managerTab === 'STORAGE' ? 'text-emerald-700' : 'text-slate-400'} />
            <span>1. Ringkasan Penyimpanan</span>
          </button>

          <button
            type="button"
            className={`px-4 py-3 text-xs font-bold border-b-2 transition flex items-center space-x-2 whitespace-nowrap ${
              managerTab === 'BATCHES'
                ? 'border-emerald-600 text-emerald-900 bg-white'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
            onClick={() => setManagerTab('BATCHES')}
          >
            <Layers size={15} className={managerTab === 'BATCHES' ? 'text-emerald-700' : 'text-slate-400'} />
            <span>2. Riwayat Batch Ingestion ({batchesTotal})</span>
          </button>

          <button
            type="button"
            className={`px-4 py-3 text-xs font-bold border-b-2 transition flex items-center space-x-2 whitespace-nowrap ${
              managerTab === 'CORRECTIONS'
                ? 'border-emerald-600 text-emerald-900 bg-white'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
            onClick={() => setManagerTab('CORRECTIONS')}
          >
            <Edit3 size={15} className={managerTab === 'CORRECTIONS' ? 'text-emerald-700' : 'text-slate-400'} />
            <span>3. Kelola Data (Koreksi &amp; Pembatalan)</span>
          </button>

          <button
            type="button"
            className={`px-4 py-3 text-xs font-bold border-b-2 transition flex items-center space-x-2 whitespace-nowrap ${
              managerTab === 'VINTAGES'
                ? 'border-emerald-600 text-emerald-900 bg-white'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
            onClick={() => setManagerTab('VINTAGES')}
          >
            <TrendingUp size={15} className={managerTab === 'VINTAGES' ? 'text-emerald-700' : 'text-slate-400'} />
            <span>4. Kelola Vintage ECMWF ({vintages.length})</span>
          </button>
        </div>

        {/* TAB 1: RINGKASAN PENYIMPANAN (CANONICAL STORAGE STATUS) */}
        {managerTab === 'STORAGE' && (
          <div className="p-4 sm:p-5">
            <CanonicalStorageStatusCard
              latestStatus={latestStatus}
              loadingStatus={loadingStatus}
              onRefresh={fetchStatus}
            />
          </div>
        )}

        {/* TAB 2: RIWAYAT BATCH INGESTION */}
        {managerTab === 'BATCHES' && (
          <div className="p-4 sm:p-5 space-y-4">
            {/* Toolbar Search & Filter */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div className="flex items-center space-x-2 flex-1 max-w-md">
                <div className="relative w-full">
                  <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Cari Batch ID, nama file, operator..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs">
                <div className="flex items-center space-x-1">
                  <span className="text-slate-500">Tipe:</span>
                  <select
                    value={filterType}
                    onChange={(e) => {
                      setFilterType(e.target.value);
                      setBatchPage(0);
                    }}
                    className="bg-white border border-slate-300 rounded px-2 py-1 text-xs"
                  >
                    <option value="ALL">Semua Tipe</option>
                    <option value="CURAH_HUJAN">Curah Hujan Harian</option>
                    <option value="SPI_HARIAN">SPI Harian</option>
                    <option value="SPI_DASARIAN">SPI Dasarian</option>
                    <option value="SPI_BULANAN">SPI Bulanan</option>
                    <option value="PROBABILITAS_DASARIAN">Probabilitas Dasarian</option>
                    <option value="PROBABILITAS_BULANAN">Probabilitas Bulanan</option>
                  </select>
                </div>

                <div className="flex items-center space-x-1">
                  <span className="text-slate-500">Status:</span>
                  <select
                    value={filterStatus}
                    onChange={(e) => {
                      setFilterStatus(e.target.value);
                      setBatchPage(0);
                    }}
                    className="bg-white border border-slate-300 rounded px-2 py-1 text-xs"
                  >
                    <option value="ALL">Semua Status</option>
                    <option value="COMMITTED">COMMITTED (Sukses)</option>
                    <option value="CANCELLED">CANCELLED (Rollback)</option>
                    <option value="VOIDED">VOIDED (Pembatalan)</option>
                  </select>
                </div>
                <button
                  type="button"
                  onClick={fetchBatches}
                  disabled={loadingBatches}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-300 rounded text-slate-700 text-xs font-medium"
                >
                  <RefreshCw size={12} className={loadingBatches ? 'animate-spin' : ''} />
                  <span>Segarkan Riwayat Batch</span>
                </button>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto border border-slate-200 rounded-lg">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3">Batch ID &amp; Waktu</th>
                    <th className="py-2.5 px-3">Tipe Data &amp; Skala</th>
                    <th className="py-2.5 px-3">Nama Berkas &amp; Operator</th>
                    <th className="py-2.5 px-3 text-center">Record Baru</th>
                    <th className="py-2.5 px-3 text-center">Update</th>
                    <th className="py-2.5 px-3 text-center">Identik</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-3 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {loadingBatches ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-400">
                        <RefreshCw size={18} className="animate-spin inline-block mr-2" />
                        Memuat riwayat batch...
                      </td>
                    </tr>
                  ) : filteredBatches.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-400">
                        Tidak ada batch ingestion ditemukan.
                      </td>
                    </tr>
                  ) : (
                    filteredBatches.map((b, idx) => (
                      <tr key={`${b.batch_id || 'batch'}-${b.id || idx}`} className="hover:bg-slate-50 transition">
                        <td className="py-2.5 px-3">
                          <div className="font-mono font-bold text-slate-800 text-[11px] truncate max-w-[200px]" title={b.batch_id}>
                            {b.batch_id}
                          </div>
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            {b.created_at || '—'}
                          </div>
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="font-semibold text-slate-700">{b.data_type}</span>
                          {b.timescale && (
                            <span className="ml-1 text-[10px] font-mono bg-indigo-50 text-indigo-700 px-1 py-0.2 rounded border border-indigo-200">
                              {b.timescale}
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-mono text-slate-700 truncate max-w-[180px]" title={b.file_name}>
                            {b.file_name || '—'}
                          </div>
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            Oleh: <span className="font-semibold">{b.operator || 'OPERATOR_BMKG'}</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono font-semibold text-emerald-700">
                          {b.new_records > 0 ? `+${b.new_records}` : '0'}
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono font-semibold text-amber-700">
                          {b.updated_records ?? 0}
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono text-slate-400">
                          {b.identical_records ?? 0}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {b.status === 'COMMITTED' || b.status === 'COMPLETED' ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                              COMMITTED
                            </span>
                          ) : b.status === 'CANCELLED' || b.status === 'ROLLED_BACK' ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                              CANCELLED
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                              {b.status}
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end space-x-1.5">
                            <button
                              type="button"
                              onClick={() => handleOpenDetail(b.batch_id)}
                              className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px] font-medium transition inline-flex items-center space-x-1"
                              title="Lihat rincian lengkap batch"
                            >
                              <Eye size={11} />
                              <span>Detail</span>
                            </button>
                            {(b.status === 'COMMITTED' || b.status === 'COMPLETED') && (
                              <button
                                type="button"
                                onClick={() => {
                                  setCancelModalBatch(b);
                                  setCancelReason('');
                                  setCancelError(null);
                                }}
                                className="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded text-[11px] font-medium transition inline-flex items-center space-x-1 border border-rose-200"
                                title="Batalkan/Rollback batch ini"
                              >
                                <RotateCcw size={11} />
                                <span>Rollback</span>
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex items-center justify-between text-xs text-slate-500 pt-2">
              <div>
                Menampilkan {batches.length > 0 ? batchPage * limit + 1 : 0} -{' '}
                {Math.min((batchPage + 1) * limit, batchesTotal)} dari {batchesTotal} batch
              </div>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  disabled={batchPage === 0}
                  onClick={() => setBatchPage((p) => Math.max(0, p - 1))}
                  className="px-2.5 py-1 bg-white border border-slate-300 rounded text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Sebelumnya
                </button>
                <span className="font-mono">Hal. {batchPage + 1}</span>
                <button
                  type="button"
                  disabled={(batchPage + 1) * limit >= batchesTotal}
                  onClick={() => setBatchPage((p) => p + 1)}
                  className="px-2.5 py-1 bg-white border border-slate-300 rounded text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Selanjutnya
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: KOREKSI & PEMBATALAN REKAMAN */}
        {managerTab === 'CORRECTIONS' && (
          <div className="p-4 sm:p-5 space-y-6">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-start space-x-2.5">
                <ShieldAlert size={16} className="text-amber-700 shrink-0 mt-0.5" />
                <div>
                  <strong>Pusat Audit Koreksi &amp; Pembatalan Rekaman BMKG:</strong> Seluruh tindakan koreksi dan pembatalan (void) direkam ke dalam audit log sistem dengan identitas operator, stempel waktu WIB, dan alasan penyesuaian.
                </div>
              </div>
              <div className="flex items-center flex-wrap gap-1.5 shrink-0">
                <span className="text-[11px] font-semibold text-amber-800">Filter Dataset:</span>
                {['ALL', 'CURAH_HUJAN', 'SPI', 'PROBABILITAS', 'ENSMEAN'].map((ds) => (
                  <button
                    key={ds}
                    type="button"
                    onClick={() => setCorrectionDatasetFilter(ds)}
                    className={`px-2 py-1 rounded text-[11px] font-semibold border transition ${
                      correctionDatasetFilter === ds
                        ? 'bg-amber-700 text-white border-amber-800'
                        : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {ds === 'ALL'
                      ? 'Semua'
                      : ds === 'CURAH_HUJAN'
                        ? 'Kelola Data Curah Hujan'
                        : ds === 'SPI'
                          ? 'Kelola Data SPI'
                          : ds === 'PROBABILITAS'
                            ? 'ECMWF Probabilitas (%)'
                            : 'ECMWF Deterministik (mm)'}
                  </button>
                ))}
              </div>
            </div>

            {/* PUSAT PENGELOLAAN CURAH HUJAN TERPADU (FILTER, TABEL, KOREKSI 5-STATUS, VOID TERPILIH/PERIODE, RECOVERY) */}
            {(correctionDatasetFilter === 'ALL' || correctionDatasetFilter === 'CURAH_HUJAN') && (
              <RainfallManagementTab
                onDataChanged={() => {
                  fetchCorrectionLogs();
                  fetchSummary();
                  fetchLatestStatus();
                }}
              />
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* SUB-FORM 3: PEMBATALAN (VOID) REKOR SPI TERISOLASI */}
              {(correctionDatasetFilter === 'ALL' || correctionDatasetFilter === 'SPI') && (
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-100">
                  <div className="p-1.5 bg-indigo-100 rounded text-indigo-800">
                    <Activity size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">Kelola Data SPI — Pembatalan Data</h4>
                    <p className="text-[11px] text-slate-500">Pembatalan rekor SPI terisolasi per skala 30D / 90D</p>
                  </div>
                </div>

                <form onSubmit={handleVoidSpi} className="space-y-3 text-xs">
                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Pos Pengamatan:</label>
                    <select
                      value={voidSpiStationId}
                      onChange={(e) => setVoidSpiStationId(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs focus:bg-white"
                    >
                      {masterStations.length > 0 ? (
                        masterStations.map((st) => (
                          <option key={st.station_id} value={st.station_id}>
                            {st.station_name} ({st.station_id}) - {st.kabupaten}
                          </option>
                        ))
                      ) : (
                        <option value="21010401A">Pos Toapaya (21010401A)</option>
                      )}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Resolusi Periode:</label>
                      <select
                        value={voidSpiPeriodType}
                        onChange={(e) => setVoidSpiPeriodType(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1.5 text-xs font-semibold"
                      >
                        <option value="DASARIAN">DASARIAN</option>
                        <option value="HARIAN">HARIAN</option>
                        <option value="BULANAN">BULANAN</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Skala Akumulasi:</label>
                      <select
                        value={voidSpiTimescale}
                        onChange={(e) => setVoidSpiTimescale(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1.5 font-mono text-xs font-semibold text-indigo-700"
                      >
                        <option value="30D">30 Hari (30D)</option>
                        <option value="90D">90 Hari (90D)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Tanggal / Ref Date:</label>
                    <input
                      type="date"
                      value={voidSpiDate}
                      onChange={(e) => setVoidSpiDate(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Alasan Void SPI (Audit Trail):</label>
                    <input
                      type="text"
                      placeholder="Contoh: Anomali perhitungan deret referensi"
                      value={voidSpiReason}
                      onChange={(e) => setVoidSpiReason(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                    />
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-slate-400">
                      Operator: <span className="font-semibold text-slate-600">{voidSpiOperator}</span>
                    </span>
                    <button
                      type="submit"
                      disabled={voidSpiLoading}
                      className="px-3 py-1.5 bg-indigo-700 hover:bg-indigo-800 text-white rounded text-xs font-semibold transition disabled:opacity-50"
                    >
                      {voidSpiLoading ? 'Membatalkan...' : 'Batalkan Data SPI'}
                    </button>
                  </div>
                </form>
              </div>
              )}

              {/* SUB-FORM 4: PEMBATALAN (VOID) PROBABILITAS ECMWF */}
              {(correctionDatasetFilter === 'ALL' || correctionDatasetFilter === 'PROBABILITAS') && (
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-100">
                  <div className="p-1.5 bg-purple-100 rounded text-purple-800">
                    <TrendingUp size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">Kelola Prakiraan ECMWF — Batalkan Vintage Probabilitas (%)</h4>
                    <p className="text-[11px] text-slate-500">Batalkan penerbitan (vintage) probabilitas per tanggal issue &amp; periode target</p>
                  </div>
                </div>

                <form onSubmit={handleVoidProbability} className="space-y-3 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Tanggal Rilis (Issue Date):</label>
                      <input
                        type="date"
                        value={voidProbIssueDate}
                        onChange={(e) => setVoidProbIssueDate(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Periode Target:</label>
                      <input
                        type="text"
                        placeholder="Contoh: 2026-11-das1"
                        value={voidProbTargetPeriod}
                        onChange={(e) => setVoidProbTargetPeriod(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Pos Spesifik (Kosongkan untuk Semua Pos):</label>
                    <input
                      type="text"
                      placeholder="Opsional, misal: 21010401A"
                      value={voidProbStationId}
                      onChange={(e) => setVoidProbStationId(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Alasan Pembatalan (Audit Trail):</label>
                    <input
                      type="text"
                      placeholder="Contoh: Rilis data revisi dari ECMWF / format ganda"
                      value={voidProbReason}
                      onChange={(e) => setVoidProbReason(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                    />
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-slate-400">
                      Operator: <span className="font-semibold text-slate-600">{voidProbOperator}</span>
                    </span>
                    <button
                      type="submit"
                      disabled={voidProbLoading}
                      className="px-3 py-1.5 bg-purple-700 hover:bg-purple-800 text-white rounded text-xs font-semibold transition disabled:opacity-50"
                    >
                      {voidProbLoading ? 'Membatalkan...' : 'Batalkan Vintage Probabilitas'}
                    </button>
                  </div>
                </form>
              </div>
              )}
            </div>

            {/* SUB-FORM 5: SOFT-VOID & REAKTIVASI ENSMEAN TERISOLASI */}
            {(correctionDatasetFilter === 'ALL' || correctionDatasetFilter === 'ENSMEAN') && (
              <div className="bg-white border border-sky-200 rounded-xl p-4 shadow-xs space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-100">
                  <div className="flex items-center space-x-2">
                    <div className="p-1.5 bg-sky-100 rounded text-sky-800">
                      <CloudRain size={16} />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-800">
                        Kelola Prakiraan ECMWF — Kelola Vintage Deterministik (mm)
                      </h4>
                      <p className="text-[11px] text-slate-500">
                        Batalkan atau aktifkan kembali vintage deterministik (mm) tanpa memengaruhi data Probabilitas (%).
                      </p>
                    </div>
                  </div>
                  <div className="inline-flex rounded-lg border border-slate-300 overflow-hidden text-xs">
                    <button
                      type="button"
                      onClick={() => setDetActionMode('VOID')}
                      className={`px-3 py-1 font-semibold transition ${
                        detActionMode === 'VOID'
                          ? 'bg-rose-700 text-white'
                          : 'bg-white text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      Batalkan Vintage
                    </button>
                    <button
                      type="button"
                      onClick={() => setDetActionMode('REACTIVATE')}
                      className={`px-3 py-1 font-semibold transition ${
                        detActionMode === 'REACTIVATE'
                          ? 'bg-emerald-700 text-white'
                          : 'bg-white text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      Aktifkan Kembali Vintage
                    </button>
                  </div>
                </div>

                <form onSubmit={handleDeterministicVoidOrReactivate} className="space-y-3 text-xs">
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Tanggal Issue (Wajib):</label>
                      <input
                        type="date"
                        value={detIssueDate}
                        onChange={(e) => setDetIssueDate(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Resolusi (Wajib):</label>
                      <select
                        value={detResolution}
                        onChange={(e) => setDetResolution(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs font-semibold"
                      >
                        <option value="DASARIAN">DASARIAN</option>
                        <option value="BULANAN">BULANAN</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Periode Target (Opsional):</label>
                      <input
                        type="text"
                        placeholder={detResolution === 'BULANAN' ? 'Contoh: 2026-11' : 'Contoh: 2026-11-das1'}
                        value={detTargetPeriod}
                        onChange={(e) => setDetTargetPeriod(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">ID Pos (Opsional):</label>
                      <input
                        type="text"
                        placeholder="Kosongkan = semua pos"
                        value={detStationId}
                        onChange={(e) => setDetStationId(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">
                      Alasan {detActionMode === 'REACTIVATE' ? 'Aktifkan Kembali' : 'Pembatalan'} Vintage (Wajib untuk Audit):
                    </label>
                    <input
                      type="text"
                      placeholder={
                        detActionMode === 'REACTIVATE'
                          ? 'Contoh: Verifikasi ulang mengonfirmasi data deterministik valid'
                          : 'Contoh: Workbook salah kolom / menunggu revisi'
                      }
                      value={detReason}
                      onChange={(e) => setDetReason(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                      required
                    />
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <label className="inline-flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={detConfirmChecked}
                        onChange={(e) => setDetConfirmChecked(e.target.checked)}
                      />
                      <span>
                        Saya mengonfirmasi tindakan{' '}
                        <strong>{detActionMode === 'REACTIVATE' ? 'Aktifkan Kembali Vintage' : 'Batalkan Vintage'}</strong>{' '}
                        ini (terisolasi dari data Probabilitas).
                      </span>
                    </label>
                    <button
                      type="submit"
                      disabled={detLoading || !detConfirmChecked || !detIssueDate || !detReason.trim()}
                      className={`px-3.5 py-1.5 text-white rounded text-xs font-semibold transition disabled:opacity-50 ${
                        detActionMode === 'REACTIVATE'
                          ? 'bg-emerald-700 hover:bg-emerald-800'
                          : 'bg-rose-700 hover:bg-rose-800'
                      }`}
                    >
                      {detLoading
                        ? 'Memproses...'
                        : detActionMode === 'REACTIVATE'
                          ? 'Aktifkan Kembali Vintage'
                          : 'Batalkan Vintage'}
                    </button>
                  </div>
                </form>

                {/* Riwayat Pengelolaan Vintage Deterministik */}
                <div className="pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                      Riwayat Pengelolaan Vintage Deterministik ({detHistory.length})
                    </span>
                    <button
                      type="button"
                      onClick={fetchDeterministicHistory}
                      disabled={loadingDetHistory}
                      className="px-2 py-0.5 bg-slate-100 hover:bg-slate-200 rounded text-slate-700 text-[11px] font-medium inline-flex items-center gap-1"
                    >
                      <RefreshCw size={11} className={loadingDetHistory ? 'animate-spin' : ''} />
                      <span>Segarkan</span>
                    </button>
                  </div>
                  <div className="overflow-x-auto border border-slate-200 rounded-lg max-h-52">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
                        <tr>
                          <th className="py-1.5 px-2.5">Waktu</th>
                          <th className="py-1.5 px-2.5">Tipe</th>
                          <th className="py-1.5 px-2.5">Batch / Berkas</th>
                          <th className="py-1.5 px-2.5 text-center">Jumlah</th>
                          <th className="py-1.5 px-2.5">Status</th>
                          <th className="py-1.5 px-2.5">Alasan &amp; Operator</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200">
                        {detHistory.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-4 text-center text-slate-400">
                              Belum ada riwayat ingestion/void/reaktivasi data deterministik tercatat.
                            </td>
                          </tr>
                        ) : (
                          detHistory.map((h, idx) => (
                            <tr key={h.batch_id || idx} className="hover:bg-slate-50">
                              <td className="py-1.5 px-2.5 font-mono text-[11px] text-slate-600">{h.created_at || '—'}</td>
                              <td className="py-1.5 px-2.5 font-semibold text-[11px]">{h.data_type}</td>
                              <td className="py-1.5 px-2.5 font-mono text-[11px] truncate max-w-[200px]" title={h.file_name || h.batch_id}>
                                {h.file_name || h.batch_id}
                              </td>
                              <td className="py-1.5 px-2.5 text-center font-mono">{h.total_records ?? 0}</td>
                              <td className="py-1.5 px-2.5">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  h.status === 'VOIDED'
                                    ? 'bg-rose-100 text-rose-800'
                                    : 'bg-emerald-100 text-emerald-800'
                                }`}>
                                  {h.status}
                                </span>
                              </td>
                              <td className="py-1.5 px-2.5 text-[11px]">
                                <div>{h.reason || '—'}</div>
                                <div className="text-[10px] text-slate-400">Oleh: {h.operator || 'OPERATOR_BMKG'}</div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* AUDIT LOG KOREKSI & PEMBATALAN REKAMAN */}
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Riwayat dan Audit Pengelolaan Data
                  </h4>
                  <p className="text-[11px] text-slate-500">
                    Jejak audit terpusat untuk Koreksi Data, Pembatalan Data, dan Pengelolaan Vintage.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={fetchCorrectionLogs}
                  disabled={loadingCorrectionLogs}
                  className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded text-slate-700 text-xs font-medium inline-flex items-center space-x-1"
                >
                  <RefreshCw size={12} className={loadingCorrectionLogs ? 'animate-spin' : ''} />
                  <span>Segarkan Log Koreksi</span>
                </button>
              </div>

              <div className="overflow-x-auto border border-slate-200 rounded-lg max-h-80">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
                    <tr>
                      <th className="py-2 px-3">Waktu (WIB)</th>
                      <th className="py-2 px-3">Dataset &amp; Tindakan</th>
                      <th className="py-2 px-3">Pos Pengamatan</th>
                      <th className="py-2 px-3">Tanggal / Periode</th>
                      <th className="py-2 px-3">Nilai Lama</th>
                      <th className="py-2 px-3">Nilai Baru</th>
                      <th className="py-2 px-3">Alasan &amp; Operator</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {loadingCorrectionLogs ? (
                      <tr>
                        <td colSpan={7} className="py-6 text-center text-slate-400">
                          Memuat log koreksi &amp; pembatalan...
                        </td>
                      </tr>
                    ) : correctionLogs.filter((c) => correctionDatasetFilter === 'ALL' || c.dataset === correctionDatasetFilter).length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-6 text-center text-slate-400">
                          Belum ada log koreksi atau pembatalan untuk filter ini.
                        </td>
                      </tr>
                    ) : (
                      correctionLogs
                        .filter((c) => correctionDatasetFilter === 'ALL' || c.dataset === correctionDatasetFilter)
                        .map((log, idx) => (
                          <tr key={log.log_id || idx} className="hover:bg-slate-50">
                            <td className="py-2 px-3 font-mono text-[11px] text-slate-600">{log.timestamp}</td>
                            <td className="py-2 px-3">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                                log.action_type?.includes('VOID')
                                  ? 'bg-rose-50 text-rose-700 border-rose-200'
                                  : 'bg-sky-50 text-sky-700 border-sky-200'
                              }`}>
                                {log.action_type}
                              </span>
                            </td>
                            <td className="py-2 px-3">
                              <div className="font-semibold text-slate-800">{log.station_name}</div>
                              <div className="font-mono text-[10px] text-slate-400">{log.station_id}</div>
                            </td>
                            <td className="py-2 px-3 font-mono text-[11px] text-slate-700">{log.target_date_or_period}</td>
                            <td className="py-2 px-3 font-mono text-[11px] text-slate-500">{log.old_value}</td>
                            <td className="py-2 px-3 font-mono text-[11px] font-bold text-slate-800">{log.new_value}</td>
                            <td className="py-2 px-3">
                              <div className="text-slate-700">{log.reason}</div>
                              <div className="text-[10px] text-slate-400">Oleh: {log.operator}</div>
                            </td>
                          </tr>
                        ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: VINTAGE PRAKIRAAN ECMWF */}
        {managerTab === 'VINTAGES' && (
          <div className="p-4 sm:p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                  Daftar Vintage Snapshot Prakiraan ECMWF
                </h4>
                <p className="text-xs text-slate-500">
                  Data snapshot probabilitas curah hujan ECMWF yang tersimpan di cews_forecast_snapshot.
                </p>
              </div>
              <button
                onClick={fetchVintages}
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded text-slate-700 text-xs font-medium inline-flex items-center space-x-1"
              >
                <RefreshCw size={12} className={loadingVintages ? 'animate-spin' : ''} />
                <span>Segarkan Vintage</span>
              </button>
            </div>

            <div className="overflow-x-auto border border-slate-200 rounded-lg">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3">Resolusi</th>
                    <th className="py-2.5 px-3">Periode Target</th>
                    <th className="py-2.5 px-3">Tanggal Issue</th>
                    <th className="py-2.5 px-3 text-center">Jumlah Pos</th>
                    <th className="py-2.5 px-3 text-center">Indikator</th>
                    <th className="py-2.5 px-3">File Sumber</th>
                    <th className="py-2.5 px-3 text-center">Status Vintage</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {loadingVintages ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        Memuat vintage prakiraan...
                      </td>
                    </tr>
                  ) : vintages.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        Belum ada vintage prakiraan ECMWF tersimpan.
                      </td>
                    </tr>
                  ) : (
                    vintages.map((v, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition">
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                            (v.forecast_resolution || (v.target_dasarian ? 'DASARIAN' : 'BULANAN')) === 'DASARIAN'
                              ? 'bg-blue-50 text-blue-700 border-blue-200'
                              : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                          }`}>
                            {v.forecast_resolution || (v.target_dasarian ? 'DASARIAN' : 'BULANAN')}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono font-bold text-purple-800">
                          <div>{v.target_period_label || v.target_period_id}</div>
                          <span className="text-[10px] text-slate-400 font-normal">({v.target_period_id})</span>
                        </td>
                        <td className="py-2.5 px-3 font-mono font-semibold text-slate-800">
                          {v.issue_date || v.forecast_issue_date || '—'}
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono font-semibold text-slate-700">
                          {v.stations_count ?? v.station_count ?? 52} Pos
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono text-slate-600">
                          {v.parameters_count ?? v.parameter_count ?? 4} Parameter
                        </td>
                        <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px] truncate max-w-xs" title={v.source_file}>
                          {v.source_file || '—'}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                            v.is_active_vintage || (v.vintage_status && v.vintage_status.includes('AKTIF'))
                              ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                              : 'bg-amber-100 text-amber-800 border-amber-300'
                          }`}>
                            {v.vintage_status || (v.is_active_vintage ? 'AKTIF (Terbaru)' : 'HISTORIS')}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Daftar Vintage Deterministik (mm) */}
            <div className="pt-4 border-t border-slate-200 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Daftar Vintage Prakiraan Deterministik (mm) — ({detVintages.length})
                  </h4>
                  <p className="text-xs text-slate-500">
                    Snapshot prakiraan curah hujan deterministik ECMWF yang tersimpan secara terisolasi.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={fetchDeterministicVintages}
                  className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded text-slate-700 text-xs font-medium inline-flex items-center space-x-1"
                >
                  <RefreshCw size={12} className={loadingDetVintages ? 'animate-spin' : ''} />
                  <span>Segarkan Deterministik</span>
                </button>
              </div>

              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2 px-3">Resolusi</th>
                      <th className="py-2 px-3">Issue Date</th>
                      <th className="py-2 px-3">Release Group</th>
                      <th className="py-2 px-3 text-center">Periode</th>
                      <th className="py-2 px-3 text-center">Stasiun Aktif</th>
                      <th className="py-2 px-3 text-center">Adjusted / Regular</th>
                      <th className="py-2 px-3 text-center">Voided</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {loadingDetVintages ? (
                      <tr>
                        <td colSpan={7} className="py-6 text-center text-slate-400">
                          Memuat vintage prakiraan deterministik...
                        </td>
                      </tr>
                    ) : detVintages.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-6 text-center text-slate-400">
                          Belum ada vintage prakiraan deterministik tersimpan di basis data lokal.
                        </td>
                      </tr>
                    ) : (
                      detVintages.map((dv, idx) => (
                        <tr key={`${dv.issue_date}-${dv.forecast_resolution}-${idx}`} className="hover:bg-slate-50">
                          <td className="py-2 px-3 font-semibold">{dv.forecast_resolution}</td>
                          <td className="py-2 px-3 font-mono font-bold text-slate-800">{dv.issue_date}</td>
                          <td className="py-2 px-3 font-mono text-[11px] text-slate-600">{dv.release_group_id || '—'}</td>
                          <td className="py-2 px-3 text-center font-mono">{dv.target_periods_count ?? 0}</td>
                          <td className="py-2 px-3 text-center font-mono">{dv.active_stations_count ?? 0}</td>
                          <td className="py-2 px-3 text-center font-mono">
                            {dv.adjusted_rows ?? 0} / {dv.regular_rows ?? 0}
                          </td>
                          <td className="py-2 px-3 text-center font-mono text-rose-700">{dv.voided_rows ?? 0}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* MODAL: DETAIL BATCH INGESTION */}
      {selectedBatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden border border-slate-200">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center space-x-2">
                <FileSpreadsheet size={18} className="text-emerald-700" />
                <h4 className="font-bold text-slate-800 text-sm">
                  Rincian Batch: <span className="font-mono text-emerald-800">{selectedBatch.batch_id}</span>
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setSelectedBatch(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200">
                <div>
                  <span className="text-slate-500 text-[11px]">Tipe Data:</span>
                  <div className="font-bold text-slate-800">{selectedBatch.data_type}</div>
                </div>
                <div>
                  <span className="text-slate-500 text-[11px]">Status:</span>
                  <div className="font-bold text-emerald-700">{selectedBatch.status}</div>
                </div>
                <div>
                  <span className="text-slate-500 text-[11px]">Nama Berkas:</span>
                  <div className="font-mono text-slate-800 truncate" title={selectedBatch.file_name}>
                    {selectedBatch.file_name || '—'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500 text-[11px]">Operator:</span>
                  <div className="font-semibold text-slate-800">{selectedBatch.operator || 'OPERATOR_BMKG'}</div>
                </div>
                <div>
                  <span className="text-slate-500 text-[11px]">Waktu Eksekusi:</span>
                  <div className="font-mono text-slate-700">{selectedBatch.created_at || '—'}</div>
                </div>
                <div>
                  <span className="text-slate-500 text-[11px]">SHA-256 Hash:</span>
                  <div className="font-mono text-[10px] text-slate-500 truncate" title={selectedBatch.file_hash_sha256}>
                    {selectedBatch.file_hash_sha256 || '—'}
                  </div>
                </div>
              </div>

              {/* Counts Breakdown */}
              <div className="grid grid-cols-4 gap-2 text-center">
                <div className="p-2 bg-emerald-50 rounded border border-emerald-200">
                  <div className="text-[10px] text-emerald-800 font-semibold">BARU</div>
                  <div className="font-mono font-bold text-emerald-700 text-sm">+{selectedBatch.new_records ?? 0}</div>
                </div>
                <div className="p-2 bg-amber-50 rounded border border-amber-200">
                  <div className="text-[10px] text-amber-800 font-semibold">UPDATE</div>
                  <div className="font-mono font-bold text-amber-700 text-sm">{selectedBatch.updated_records ?? 0}</div>
                </div>
                <div className="p-2 bg-slate-50 rounded border border-slate-200">
                  <div className="text-[10px] text-slate-600 font-semibold">IDENTIK</div>
                  <div className="font-mono font-bold text-slate-700 text-sm">{selectedBatch.identical_records ?? 0}</div>
                </div>
                <div className="p-2 bg-rose-50 rounded border border-rose-200">
                  <div className="text-[10px] text-rose-800 font-semibold">DITOLAK</div>
                  <div className="font-mono font-bold text-rose-700 text-sm">{selectedBatch.rejected_records ?? 0}</div>
                </div>
              </div>

              {selectedBatch.notes && (
                <div className="p-2.5 bg-slate-50 rounded border border-slate-200">
                  <span className="text-[11px] text-slate-500 font-semibold block mb-0.5">Catatan Operator:</span>
                  <span className="text-slate-700">{selectedBatch.notes}</span>
                </div>
              )}
            </div>

            <div className="p-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedBatch(null)}
                className="px-3 py-1.5 bg-white border border-slate-300 rounded text-slate-700 text-xs font-medium hover:bg-slate-100"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: KONFIRMASI ROLLBACK BATCH */}
      {cancelModalBatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-5 border border-slate-200 space-y-4">
            <div className="flex items-center space-x-2 text-rose-700">
              <ShieldAlert size={20} />
              <h4 className="font-bold text-slate-800 text-sm">Konfirmasi Rollback Batch</h4>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Anda akan membatalkan batch <strong className="font-mono text-slate-800">{cancelModalBatch.batch_id}</strong> ({cancelModalBatch.data_type}). Seluruh rekor yang disisipkan oleh batch ini akan dinonaktifkan atau dihapus dari penyimpanan kanonikal.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Alasan Pembatalan (Audit Trail):
              </label>
              <textarea
                rows={3}
                placeholder="Tuliskan alasan operasional pembatalan batch ini..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs focus:bg-white"
              />
            </div>

            {cancelError && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded text-rose-800 text-xs flex items-center space-x-1.5">
                <AlertCircle size={14} className="shrink-0" />
                <span>{cancelError}</span>
              </div>
            )}

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setCancelModalBatch(null)}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-medium"
              >
                Batal
              </button>
              <button
                type="button"
                disabled={cancelLoading || !cancelReason.trim()}
                onClick={handleCancelBatchSubmit}
                className="px-3 py-1.5 bg-rose-700 hover:bg-rose-800 text-white rounded text-xs font-semibold disabled:opacity-50 inline-flex items-center space-x-1"
              >
                <RotateCcw size={12} className={cancelLoading ? 'animate-spin' : ''} />
                <span>{cancelLoading ? 'Memproses Rollback...' : 'Ya, Batalkan Batch'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
