import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Search,
  Edit3,
  Trash2,
  RotateCcw,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  RefreshCw,
  ShieldAlert,
  X,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

const VALUE_TYPE_OPTIONS = [
  { value: 'OBSERVED_VALID', label: 'Hujan Terukur (mm)' },
  { value: 'OBSERVED_ZERO', label: 'Tidak Ada Hujan (-)' },
  { value: 'TTU', label: 'Hujan Tidak Terukur (TTU)' },
  { value: 'MISSING', label: 'Data Tidak Masuk (9999)' },
  { value: 'DAMAGED', label: 'Alat Rusak (9999)' },
];

export default function RainfallManagementTab({ onDataChanged }) {
  const [subMode, setSubMode] = useState('RECORDS'); // 'RECORDS' | 'PERIOD_VOID' | 'RECOVERY'

  // Regencies & master stations
  const [regencies, setRegencies] = useState([]);
  const [filterRegency, setFilterRegency] = useState('');
  const [filterStation, setFilterStation] = useState('');
  const [filterStartDate, setFilterStartDate] = useState('');
  const [filterEndDate, setFilterEndDate] = useState('');
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [filterSource, setFilterSource] = useState('');

  // Records table state
  const [records, setRecords] = useState([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [feedback, setFeedback] = useState(null);

  // Inline Correction modal state
  const [correctTarget, setCorrectTarget] = useState(null);
  const [corrValueType, setCorrValueType] = useState('OBSERVED_VALID');
  const [corrRainfallMm, setCorrRainfallMm] = useState('');
  const [corrReason, setCorrReason] = useState('');
  const [corrLoading, setCorrLoading] = useState(false);

  // Selected VOID confirmation state
  const [showVoidSelectedModal, setShowVoidSelectedModal] = useState(false);
  const [voidSelectedReason, setVoidSelectedReason] = useState('');
  const [voidSelectedLoading, setVoidSelectedLoading] = useState(false);

  // Period VOID state (consolidated from deleted standalone modal)
  const [pvRegency, setPvRegency] = useState('');
  const [pvStartDate, setPvStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [pvEndDate, setPvEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [pvScope, setPvScope] = useState('ALL'); // 'ALL' | 'SELECTED'
  const [pvStations, setPvStations] = useState([]);
  const [pvPreview, setPvPreview] = useState(null);
  const [pvReason, setPvReason] = useState('');
  const [pvConfirm, setPvConfirm] = useState(false);
  const [pvLoading, setPvLoading] = useState(false);

  // Recovery VOID batches state
  const [voidBatches, setVoidBatches] = useState([]);
  const [loadingVoidBatches, setLoadingVoidBatches] = useState(false);
  const [recoverTarget, setRecoverTarget] = useState(null);
  const [recoverReason, setRecoverReason] = useState('');
  const [recoverLoading, setRecoverLoading] = useState(false);

  const loadRegencies = useCallback(async () => {
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_REGENCIES);
      if (res.ok) {
        const json = await res.json();
        setRegencies(json.regencies || []);
      }
    } catch (err) {
      console.error('Failed to load regencies:', err);
    }
  }, []);

  const fetchRecords = useCallback(async () => {
    setLoadingRecords(true);
    try {
      const url = API_ENDPOINTS.RAINFALL_V2_RECORDS({
        regency_code: filterRegency,
        station_id: filterStation,
        start_date: filterStartDate,
        end_date: filterEndDate,
        obs_status: filterStatus === 'ALL' ? '' : filterStatus,
        source: filterSource,
        limit: 100,
        offset: 0,
      });
      const res = await authFetch(url);
      if (res.ok) {
        const json = await res.json();
        setRecords(json.items || []);
        setTotalRecords(json.total || 0);
        setSelectedKeys([]);
      }
    } catch (err) {
      console.error('Failed to load rainfall records:', err);
    } finally {
      setLoadingRecords(false);
    }
  }, [filterRegency, filterStation, filterStartDate, filterEndDate, filterStatus, filterSource]);

  const fetchVoidBatches = useCallback(async () => {
    setLoadingVoidBatches(true);
    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_BATCHES({ data_type: 'CURAH_HUJAN', limit: 50 }));
      if (res.ok) {
        const json = await res.json();
        const onlyVoid = (json.items || []).filter(
          (b) => String(b.batch_id || '').startsWith('VOID_CH_') || String(b.file_name || '').startsWith('DELETE_VOID_')
        );
        setVoidBatches(onlyVoid);
      }
    } catch (err) {
      console.error('Failed to load VOID batches:', err);
    } finally {
      setLoadingVoidBatches(false);
    }
  }, []);

  useEffect(() => {
    loadRegencies();
  }, [loadRegencies]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  useEffect(() => {
    if (subMode === 'RECOVERY') {
      fetchVoidBatches();
    }
  }, [subMode, fetchVoidBatches]);

  const filterStationsList = useMemo(() => {
    if (!filterRegency) return regencies.flatMap((r) => r.stations || []);
    return regencies.find((r) => r.code === filterRegency)?.stations || [];
  }, [regencies, filterRegency]);

  const pvStationsList = useMemo(
    () => regencies.find((r) => r.code === pvRegency)?.stations || [],
    [regencies, pvRegency]
  );

  const rowKey = (r) => `${r.station_id}__${r.observation_date}`;

  const toggleSelectRow = (r) => {
    const k = rowKey(r);
    setSelectedKeys((prev) => (prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]));
  };

  const toggleSelectAll = () => {
    if (selectedKeys.length === records.length) {
      setSelectedKeys([]);
    } else {
      setSelectedKeys(records.map(rowKey));
    }
  };

  // Standardized single-record correction submit
  const handleSubmitCorrection = async (e) => {
    e.preventDefault();
    if (!correctTarget) return;
    setCorrLoading(true);
    setFeedback(null);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_RECORD_CORRECT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_id: correctTarget.station_id,
          observation_date: correctTarget.observation_date,
          value_type: corrValueType,
          rainfall_mm: corrValueType === 'OBSERVED_VALID' ? parseFloat(corrRainfallMm) : null,
          reason: corrReason.trim(),
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Gagal menyimpan koreksi');
      setFeedback({ type: 'success', text: json.message });
      setCorrectTarget(null);
      setCorrReason('');
      fetchRecords();
      if (onDataChanged) onDataChanged();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setCorrLoading(false);
    }
  };

  // Void selected records submit
  const handleSubmitVoidSelected = async () => {
    const targetRecords = records
      .filter((r) => selectedKeys.includes(rowKey(r)))
      .map((r) => ({ station_id: r.station_id, observation_date: r.observation_date }));
    if (targetRecords.length === 0) return;

    setVoidSelectedLoading(true);
    setFeedback(null);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_RECORDS_VOID_SELECTED, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ records: targetRecords, reason: voidSelectedReason.trim() }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Gagal membatalkan rekaman terpilih');
      setFeedback({ type: 'success', text: `${json.message} (Batch: ${json.batch_id})` });
      setShowVoidSelectedModal(false);
      setVoidSelectedReason('');
      fetchRecords();
      if (onDataChanged) onDataChanged();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setVoidSelectedLoading(false);
    }
  };

  // Period VOID preview & commit
  const handlePreviewPeriodVoid = async () => {
    if (!pvRegency || !pvStartDate || !pvEndDate) return;
    setPvLoading(true);
    setPvPreview(null);
    setPvConfirm(false);
    setFeedback(null);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_DELETE_PREVIEW, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          regency_code: pvRegency,
          start_date: pvStartDate,
          end_date: pvEndDate,
          station_ids: pvScope === 'SELECTED' ? pvStations : null,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Gagal membuat pratinjau pembatalan periode');
      setPvPreview(json);
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setPvLoading(false);
    }
  };

  const handleCommitPeriodVoid = async () => {
    if (!pvPreview || !pvConfirm || !pvReason.trim()) return;
    setPvLoading(true);
    setFeedback(null);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_DELETE_COMMIT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          regency_code: pvRegency,
          start_date: pvStartDate,
          end_date: pvEndDate,
          station_ids: pvScope === 'SELECTED' ? pvStations : null,
          reason: pvReason.trim(),
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Gagal membatalkan periode');
      setFeedback({ type: 'success', text: `${json.message} (Batch: ${json.batch_id})` });
      setPvPreview(null);
      setPvReason('');
      setPvConfirm(false);
      fetchRecords();
      if (onDataChanged) onDataChanged();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setPvLoading(false);
    }
  };

  // Recover VOID batch
  const handleRecoverBatch = async () => {
    if (!recoverTarget || !recoverReason.trim()) return;
    setRecoverLoading(true);
    setFeedback(null);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_VOID_BATCH_RECOVER(recoverTarget.batch_id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: recoverReason.trim() }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Gagal memulihkan batch VOID');
      setFeedback({ type: 'success', text: json.message });
      setRecoverTarget(null);
      setRecoverReason('');
      fetchVoidBatches();
      fetchRecords();
      if (onDataChanged) onDataChanged();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setRecoverLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Sub-navigation inside Tab 3 */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
        <div className="flex flex-wrap gap-1.5">
          {[
            { id: 'RECORDS', label: 'Data & Koreksi Rekaman' },
            { id: 'PERIOD_VOID', label: 'Pembatalan Berdasarkan Periode (VOID)' },
            { id: 'RECOVERY', label: 'Pemulihan Batch VOID' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSubMode(t.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                subMode === t.id
                  ? 'bg-emerald-700 text-white border-emerald-700'
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {subMode === 'RECORDS' && selectedKeys.length > 0 && (
          <button
            type="button"
            onClick={() => setShowVoidSelectedModal(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold"
          >
            <Trash2 size={13} />
            <span>Batalkan Rekaman Terpilih ({selectedKeys.length})</span>
          </button>
        )}
      </div>

      {feedback && (
        <div
          className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.type === 'success' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
            <span>{feedback.text}</span>
          </div>
          <button type="button" onClick={() => setFeedback(null)} className="text-xs opacity-60 hover:opacity-100">
            <X size={14} />
          </button>
        </div>
      )}

      {/* MODE A: FILTER + TABEL REKAMAN + KOREKSI + VOID TERPILIH */}
      {subMode === 'RECORDS' && (
        <div className="space-y-3">
          {/* Filter Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs">
            <div>
              <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Kabupaten/Kota</label>
              <select
                value={filterRegency}
                onChange={(e) => { setFilterRegency(e.target.value); setFilterStation(''); }}
                className="w-full px-2 py-1.5 rounded border border-slate-300 bg-white text-xs"
              >
                <option value="">Semua Wilayah</option>
                {regencies.map((r) => (
                  <option key={r.code} value={r.code}>{r.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Stasiun</label>
              <select
                value={filterStation}
                onChange={(e) => setFilterStation(e.target.value)}
                className="w-full px-2 py-1.5 rounded border border-slate-300 bg-white text-xs"
              >
                <option value="">Semua Stasiun</option>
                {filterStationsList.map((s) => (
                  <option key={s.station_id} value={s.station_id}>{s.station_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Tanggal Mulai</label>
              <input
                type="date"
                value={filterStartDate}
                onChange={(e) => setFilterStartDate(e.target.value)}
                className="w-full px-2 py-1.5 rounded border border-slate-300 bg-white font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Tanggal Akhir</label>
              <input
                type="date"
                value={filterEndDate}
                onChange={(e) => setFilterEndDate(e.target.value)}
                className="w-full px-2 py-1.5 rounded border border-slate-300 bg-white font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Status</label>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="w-full px-2 py-1.5 rounded border border-slate-300 bg-white text-xs"
              >
                <option value="ALL">Semua Status</option>
                <option value="OBSERVED_VALID">Hujan Terukur</option>
                <option value="OBSERVED_ZERO">Tidak Ada Hujan (-)</option>
                <option value="TTU">TTU</option>
                <option value="MISSING">Data Tidak Masuk (9999)</option>
                <option value="DAMAGED">Alat Rusak (9999)</option>
              </select>
            </div>
            <div className="flex items-end gap-1.5">
              <button
                type="button"
                onClick={fetchRecords}
                disabled={loadingRecords}
                className="flex-1 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold inline-flex items-center justify-center gap-1"
              >
                <Search size={12} /> <span>Cari</span>
              </button>
            </div>
          </div>

          {/* Observation Records Table */}
          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
            <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs text-slate-600">
              <span>Menampilkan <strong>{records.length}</strong> dari <strong>{totalRecords.toLocaleString('id-ID')}</strong> rekaman aktif</span>
              <span className="text-[11px] text-slate-400">Standar: <code>-</code> (0 mm) &bull; <code>TTU</code> &bull; <code>9999</code> (Missing/Rusak)</span>
            </div>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs text-left">
                <thead className="bg-white sticky top-0 border-b border-slate-200 text-slate-600">
                  <tr>
                    <th className="py-2 px-2.5 w-8">
                      <input
                        type="checkbox"
                        checked={records.length > 0 && selectedKeys.length === records.length}
                        onChange={toggleSelectAll}
                      />
                    </th>
                    <th className="py-2 px-2.5">Tanggal</th>
                    <th className="py-2 px-2.5">Kabupaten/Kota</th>
                    <th className="py-2 px-2.5">Stasiun</th>
                    <th className="py-2 px-2.5 text-right">Curah Hujan</th>
                    <th className="py-2 px-2.5">Status Observasi</th>
                    <th className="py-2 px-2.5">Sumber</th>
                    <th className="py-2 px-2.5 text-center">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loadingRecords ? (
                    <tr><td colSpan={8} className="py-8 text-center text-slate-400">Memuat data curah hujan...</td></tr>
                  ) : records.length === 0 ? (
                    <tr><td colSpan={8} className="py-8 text-center text-slate-400">Tidak ada rekaman sesuai filter.</td></tr>
                  ) : (
                    records.map((r) => {
                      const k = rowKey(r);
                      return (
                        <tr key={k} className="hover:bg-slate-50/70">
                          <td className="py-1.5 px-2.5">
                            <input
                              type="checkbox"
                              checked={selectedKeys.includes(k)}
                              onChange={() => toggleSelectRow(r)}
                            />
                          </td>
                          <td className="py-1.5 px-2.5 font-mono text-slate-700">{r.observation_date}</td>
                          <td className="py-1.5 px-2.5 text-slate-600">{r.kabupaten}</td>
                          <td className="py-1.5 px-2.5">
                            <div className="font-semibold text-slate-800">{r.station_name}</div>
                            <div className="font-mono text-[10px] text-slate-400">{r.station_id}</div>
                          </td>
                          <td className="py-1.5 px-2.5 text-right font-mono font-bold text-slate-900">{r.display_value}</td>
                          <td className="py-1.5 px-2.5 text-slate-700">{r.status_label}</td>
                          <td className="py-1.5 px-2.5 font-mono text-[10px] text-slate-500">{r.rainfall_source}</td>
                          <td className="py-1.5 px-2.5 text-center">
                            <button
                              type="button"
                              onClick={() => {
                                setCorrectTarget(r);
                                setCorrValueType(
                                  ['OBSERVED_VALID', 'OBSERVED_ZERO', 'TTU', 'MISSING', 'DAMAGED'].includes(r.obs_status)
                                    ? r.obs_status
                                    : 'OBSERVED_VALID'
                                );
                                setCorrRainfallMm(r.rainfall_mm !== null && r.rainfall_mm > 0 ? String(r.rainfall_mm) : '');
                                setCorrReason('');
                              }}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-sky-50 hover:bg-sky-100 text-sky-800 border border-sky-200 text-[11px] font-semibold"
                            >
                              <Edit3 size={11} /> Koreksi
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* MODE B: PEMBATALAN BERDASARKAN PERIODE (VOID) */}
      {subMode === 'PERIOD_VOID' && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-bold text-slate-600 mb-1">Kabupaten/Kota</label>
              <select
                value={pvRegency}
                onChange={(e) => { setPvRegency(e.target.value); setPvStations([]); setPvPreview(null); }}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white"
              >
                <option value="">-- Pilih Wilayah --</option>
                {regencies.map((r) => (
                  <option key={r.code} value={r.code}>{r.label} ({r.stations_count} pos)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-bold text-slate-600 mb-1">Tanggal Mulai</label>
              <input
                type="date"
                value={pvStartDate}
                onChange={(e) => { setPvStartDate(e.target.value); setPvPreview(null); }}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 font-mono"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold text-slate-600 mb-1">Tanggal Akhir</label>
              <input
                type="date"
                value={pvEndDate}
                min={pvStartDate}
                onChange={(e) => { setPvEndDate(e.target.value); setPvPreview(null); }}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 font-mono"
              />
            </div>
          </div>

          {pvRegency && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setPvScope('ALL'); setPvPreview(null); }}
                  className={`px-3 py-1.5 rounded border font-semibold ${pvScope === 'ALL' ? 'bg-slate-800 text-white border-slate-800' : 'bg-white text-slate-700 border-slate-300'}`}
                >
                  Semua Stasiun ({pvStationsList.length})
                </button>
                <button
                  type="button"
                  onClick={() => { setPvScope('SELECTED'); setPvPreview(null); }}
                  className={`px-3 py-1.5 rounded border font-semibold ${pvScope === 'SELECTED' ? 'bg-slate-800 text-white border-slate-800' : 'bg-white text-slate-700 border-slate-300'}`}
                >
                  Pilih Stasiun Tertentu ({pvStations.length})
                </button>
              </div>
              {pvScope === 'SELECTED' && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-40 overflow-y-auto p-2 border border-slate-200 rounded bg-slate-50">
                  {pvStationsList.map((s) => (
                    <label key={s.station_id} className="flex items-center gap-1.5 cursor-pointer text-[11px]">
                      <input
                        type="checkbox"
                        checked={pvStations.includes(s.station_id)}
                        onChange={() =>
                          setPvStations((prev) =>
                            prev.includes(s.station_id) ? prev.filter((x) => x !== s.station_id) : [...prev, s.station_id]
                          )
                        }
                      />
                      <span className="truncate">{s.station_name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="button"
              disabled={!pvRegency || !pvStartDate || !pvEndDate || (pvScope === 'SELECTED' && pvStations.length === 0) || pvLoading}
              onClick={handlePreviewPeriodVoid}
              className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold disabled:opacity-40"
            >
              {pvLoading ? 'Memeriksa...' : 'Pratinjau Dampak Pembatalan'}
            </button>
          </div>

          {pvPreview && (
            <div className="border border-rose-200 bg-rose-50/50 rounded-lg p-3.5 space-y-3">
              <div className="flex flex-wrap gap-4 text-xs">
                <span>Wilayah: <strong>{pvPreview.regency_label}</strong></span>
                <span>Periode: <strong className="font-mono">{pvPreview.start_date} s/d {pvPreview.end_date}</strong></span>
                <span>Stasiun Terdampak: <strong>{pvPreview.affected_stations_count}</strong></span>
                <span>Total Record VOID: <strong className="text-rose-700">{pvPreview.total_records}</strong></span>
              </div>

              {pvPreview.total_records > 0 && (
                <>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">Alasan Pembatalan (Wajib)</label>
                    <input
                      value={pvReason}
                      onChange={(e) => setPvReason(e.target.value)}
                      placeholder="Tuliskan alasan operasional pembatalan periode..."
                      className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white"
                    />
                  </div>
                  <label className="flex items-center gap-2 font-semibold text-rose-900 cursor-pointer">
                    <input type="checkbox" checked={pvConfirm} onChange={(e) => setPvConfirm(e.target.checked)} />
                    <span>Saya mengonfirmasi pembatalan (VOID) {pvPreview.total_records} rekaman ini.</span>
                  </label>
                  <button
                    type="button"
                    disabled={!pvConfirm || !pvReason.trim() || pvLoading}
                    onClick={handleCommitPeriodVoid}
                    className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold disabled:opacity-40 inline-flex items-center gap-1.5"
                  >
                    <ShieldAlert size={14} /> <span>Konfirmasi Pembatalan Periode (VOID)</span>
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* MODE C: PEMULIHAN BATCH VOID */}
      {subMode === 'RECOVERY' && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-slate-800">Daftar Batch Pembatalan (VOID) Curah Hujan</span>
            <button
              type="button"
              onClick={fetchVoidBatches}
              className="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 inline-flex items-center gap-1"
            >
              <RefreshCw size={12} className={loadingVoidBatches ? 'animate-spin' : ''} /> Segarkan
            </button>
          </div>
          <div className="overflow-x-auto border border-slate-200 rounded-lg">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600">
                <tr>
                  <th className="py-2 px-3">Batch ID</th>
                  <th className="py-2 px-3">Periode</th>
                  <th className="py-2 px-3 text-right">Record</th>
                  <th className="py-2 px-3">Operator &amp; Alasan</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3 text-center">Pemulihan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {voidBatches.length === 0 ? (
                  <tr><td colSpan={6} className="py-6 text-center text-slate-400">Belum ada batch pembatalan VOID.</td></tr>
                ) : (
                  voidBatches.map((b) => (
                    <tr key={b.batch_id}>
                      <td className="py-2 px-3 font-mono font-semibold text-slate-800">{b.batch_id}</td>
                      <td className="py-2 px-3 font-mono text-slate-600">{b.date_range_start} s/d {b.date_range_end}</td>
                      <td className="py-2 px-3 text-right font-mono">{b.total_records}</td>
                      <td className="py-2 px-3">
                        <div>{b.notes || b.file_name}</div>
                        <div className="text-[10px] text-slate-400">Oleh: {b.operator}</div>
                      </td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${b.status === 'CANCELLED' ? 'bg-slate-100 text-slate-500' : 'bg-rose-100 text-rose-800'}`}>
                          {b.status === 'CANCELLED' ? 'SUDAH DIPULIHKAN' : 'AKTIF VOID'}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-center">
                        {b.status !== 'CANCELLED' && (
                          <button
                            type="button"
                            onClick={() => { setRecoverTarget(b); setRecoverReason(''); }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-semibold"
                          >
                            <RotateCcw size={11} /> Pulihkan
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* INLINE CORRECTION MODAL */}
      {correctTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <form onSubmit={handleSubmitCorrection} className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <h4 className="font-bold text-sm text-slate-900">Koreksi Rekaman Curah Hujan</h4>
              <button type="button" onClick={() => setCorrectTarget(null)}><X size={16} /></button>
            </div>
            <div className="bg-slate-50 rounded p-2.5 space-y-1">
              <div><strong>Stasiun:</strong> {correctTarget.station_name} ({correctTarget.station_id})</div>
              <div><strong>Tanggal:</strong> <span className="font-mono">{correctTarget.observation_date}</span></div>
              <div><strong>Nilai Saat Ini:</strong> <span className="font-mono font-bold">{correctTarget.display_value}</span> ({correctTarget.status_label})</div>
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Jenis Nilai Baru</label>
              <select
                value={corrValueType}
                onChange={(e) => setCorrValueType(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white"
              >
                {VALUE_TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            {corrValueType === 'OBSERVED_VALID' && (
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Curah Hujan Terukur (mm)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  required
                  value={corrRainfallMm}
                  onChange={(e) => setCorrRainfallMm(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded border border-slate-300 font-mono"
                />
              </div>
            )}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Alasan Koreksi (Wajib)</label>
              <textarea
                rows={2}
                required
                value={corrReason}
                onChange={(e) => setCorrReason(e.target.value)}
                placeholder="Alasan koreksi observasi..."
                className="w-full px-2.5 py-1.5 rounded border border-slate-300"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setCorrectTarget(null)} className="px-3 py-1.5 rounded border border-slate-300">Batal</button>
              <button type="submit" disabled={corrLoading || !corrReason.trim()} className="px-4 py-1.5 rounded bg-emerald-700 hover:bg-emerald-800 text-white font-semibold disabled:opacity-40">
                {corrLoading ? 'Menyimpan...' : 'Simpan Koreksi'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* VOID SELECTED CONFIRM MODAL */}
      {showVoidSelectedModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <h4 className="font-bold text-sm text-rose-800">Konfirmasi Pembatalan (VOID)</h4>
              <button type="button" onClick={() => setShowVoidSelectedModal(false)}><X size={16} /></button>
            </div>
            <p className="text-slate-600">
              Sebanyak <strong>{selectedKeys.length} rekaman terpilih</strong> akan ditandai <strong>VOID</strong> dan tidak tampil pada tabel aktif maupun SPI.
            </p>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Alasan Pembatalan (Wajib)</label>
              <textarea
                rows={2}
                value={voidSelectedReason}
                onChange={(e) => setVoidSelectedReason(e.target.value)}
                placeholder="Alasan pembatalan rekaman..."
                className="w-full px-2.5 py-1.5 rounded border border-slate-300"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowVoidSelectedModal(false)} className="px-3 py-1.5 rounded border border-slate-300">Batal</button>
              <button
                type="button"
                disabled={voidSelectedLoading || !voidSelectedReason.trim()}
                onClick={handleSubmitVoidSelected}
                className="px-4 py-1.5 rounded bg-rose-600 hover:bg-rose-700 text-white font-semibold disabled:opacity-40"
              >
                {voidSelectedLoading ? 'Memproses...' : 'Konfirmasi VOID'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RECOVER BATCH CONFIRM MODAL */}
      {recoverTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <h4 className="font-bold text-sm text-emerald-800">Pulihkan Batch VOID</h4>
              <button type="button" onClick={() => setRecoverTarget(null)}><X size={16} /></button>
            </div>
            <p className="text-slate-600">
              Batch <strong className="font-mono">{recoverTarget.batch_id}</strong> ({recoverTarget.total_records} rekaman). Rekaman yang sudah dikoreksi setelah pembatalan akan dilewati otomatis demi mencegah konflik.
            </p>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Alasan Pemulihan (Wajib)</label>
              <textarea
                rows={2}
                value={recoverReason}
                onChange={(e) => setRecoverReason(e.target.value)}
                placeholder="Alasan pemulihan batch..."
                className="w-full px-2.5 py-1.5 rounded border border-slate-300"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setRecoverTarget(null)} className="px-3 py-1.5 rounded border border-slate-300">Batal</button>
              <button
                type="button"
                disabled={recoverLoading || !recoverReason.trim()}
                onClick={handleRecoverBatch}
                className="px-4 py-1.5 rounded bg-emerald-700 hover:bg-emerald-800 text-white font-semibold disabled:opacity-40"
              >
                {recoverLoading ? 'Memulihkan...' : 'Pulihkan Batch'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
