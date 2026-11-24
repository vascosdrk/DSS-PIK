import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  Trash2,
  MapPin,
  Calendar,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  ShieldAlert,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

export default function RainfallDeleteModal({ isOpen, onClose, onSuccess }) {
  // 5 steps: 1=Wilayah, 2=Periode, 3=Stasiun, 4=Pratinjau Dampak, 5=Selesai
  const [step, setStep] = useState(1);
  const [regencies, setRegencies] = useState([]);
  const [loadingRegencies, setLoadingRegencies] = useState(false);

  const [selectedRegency, setSelectedRegency] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [scopeMode, setScopeMode] = useState('ALL'); // 'ALL' | 'SELECTED'
  const [selectedStations, setSelectedStations] = useState([]);

  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [previewData, setPreviewData] = useState(null);

  const [operatorName, setOperatorName] = useState('OPERATOR_BMKG');
  const [reason, setReason] = useState('');
  const [confirmCheck, setConfirmCheck] = useState(false);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitError, setCommitError] = useState('');
  const [commitResult, setCommitResult] = useState(null);

  const activeRegencyObj = useMemo(
    () => regencies.find((r) => r.code === selectedRegency) || null,
    [regencies, selectedRegency]
  );

  const loadRegencies = useCallback(async () => {
    setLoadingRegencies(true);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_REGENCIES);
      if (res.ok) {
        const json = await res.json();
        setRegencies(json.regencies || []);
      }
    } catch (err) {
      console.error('Failed to load regencies:', err);
    } finally {
      setLoadingRegencies(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadRegencies();
      setStep(1);
      setSelectedRegency('');
      const today = new Date().toISOString().slice(0, 10);
      setStartDate(today);
      setEndDate(today);
      setScopeMode('ALL');
      setSelectedStations([]);
      setPreviewData(null);
      setPreviewError('');
      setReason('');
      setConfirmCheck(false);
      setCommitError('');
      setCommitResult(null);
    }
  }, [isOpen, loadRegencies]);

  const toggleStation = (sid) => {
    setSelectedStations((prev) =>
      prev.includes(sid) ? prev.filter((id) => id !== sid) : [...prev, sid]
    );
  };

  const handleRunPreview = async () => {
    setPreviewLoading(true);
    setPreviewError('');
    setConfirmCheck(false);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_DELETE_PREVIEW, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          regency_code: selectedRegency,
          start_date: startDate,
          end_date: endDate,
          station_ids: scopeMode === 'SELECTED' ? selectedStations : null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setPreviewData(data);
      setStep(4);
    } catch (err) {
      setPreviewError(err.message || 'Gagal memuat pratinjau penghapusan.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleCommitDelete = async () => {
    setCommitLoading(true);
    setCommitError('');
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_DELETE_COMMIT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          regency_code: selectedRegency,
          start_date: startDate,
          end_date: endDate,
          station_ids: scopeMode === 'SELECTED' ? selectedStations : null,
          reason: reason.trim(),
          operator: operatorName.trim() || 'OPERATOR_BMKG',
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || `HTTP ${res.status}`);
      setCommitResult(result);
      setStep(5);
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setCommitError(err.message || 'Gagal menghapus data curah hujan.');
    } finally {
      setCommitLoading(false);
    }
  };

  if (!isOpen) return null;

  const canGoStep4 =
    Boolean(selectedRegency && startDate && endDate && startDate <= endDate) &&
    (scopeMode === 'ALL' || selectedStations.length > 0);

  const canCommit =
    (previewData?.total_records || 0) > 0 && confirmCheck && reason.trim().length >= 3;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-3 sm:p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-rose-50/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center">
              <Trash2 size={17} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">HAPUS DATA CURAH HUJAN (VOID)</h2>
              <div className="text-[11px] text-slate-500">
                Tahap {step} / 5 {activeRegencyObj ? `• ${activeRegencyObj.label}` : ''}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Stepper */}
        <div className="grid grid-cols-5 border-b border-slate-100 bg-white px-5 py-2 text-[11px] font-medium">
          {['1. Wilayah', '2. Periode', '3. Stasiun', '4. Pratinjau', '5. Selesai'].map((lbl, idx) => {
            const num = idx + 1;
            const active = step === num;
            const done = step > num;
            return (
              <div
                key={lbl}
                className={`text-center py-1 rounded ${
                  active ? 'bg-rose-50 text-rose-800 font-bold' : done ? 'text-rose-600' : 'text-slate-400'
                }`}
              >
                {lbl}
              </div>
            );
          })}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* STEP 1: WILAYAH */}
          {step === 1 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Pilih Kabupaten / Kota</h3>
                <span className="text-[11px] text-slate-400">Penghapusan aman (soft-delete VOID)</span>
              </div>
              {loadingRegencies ? (
                <div className="py-8 text-center text-xs text-slate-500">Memuat wilayah...</div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                  {regencies.map((reg) => {
                    const selected = selectedRegency === reg.code;
                    return (
                      <button
                        key={reg.code}
                        type="button"
                        onClick={() => {
                          setSelectedRegency(reg.code);
                          setSelectedStations([]);
                        }}
                        className={`text-left px-4 py-3 rounded-lg border transition ${
                          selected
                            ? 'border-rose-500 bg-rose-50/50 ring-1 ring-rose-500/40'
                            : 'border-slate-200 hover:border-slate-300 bg-white'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <MapPin size={14} className={selected ? 'text-rose-600' : 'text-slate-400'} />
                          <span className="font-semibold text-xs text-slate-800">{reg.label}</span>
                        </div>
                        <div className="mt-1.5 pl-5.5 text-[11px] text-slate-500">{reg.stations_count} pos master</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* STEP 2: PERIODE */}
          {step === 2 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tentukan Rentang Tanggal</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-slate-50 border border-slate-200 rounded-lg p-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Tanggal Mulai</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Tanggal Akhir</label>
                  <input
                    type="date"
                    value={endDate}
                    min={startDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                  />
                </div>
              </div>
              {startDate && endDate && startDate > endDate && (
                <div className="text-xs text-rose-700 flex items-center gap-1.5">
                  <AlertCircle size={14} /> Tanggal mulai harus kurang dari atau sama dengan tanggal akhir.
                </div>
              )}
            </div>
          )}

          {/* STEP 3: CAKUPAN STASIUN */}
          {step === 3 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cakupan Stasiun</h3>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setScopeMode('ALL')}
                  className={`flex-1 py-2 px-3 rounded-lg border text-xs font-semibold transition ${
                    scopeMode === 'ALL' ? 'bg-rose-600 text-white border-rose-600' : 'bg-white text-slate-700 border-slate-300'
                  }`}
                >
                  Semua Stasiun ({activeRegencyObj?.stations_count || 0} Pos)
                </button>
                <button
                  type="button"
                  onClick={() => setScopeMode('SELECTED')}
                  className={`flex-1 py-2 px-3 rounded-lg border text-xs font-semibold transition ${
                    scopeMode === 'SELECTED' ? 'bg-rose-600 text-white border-rose-600' : 'bg-white text-slate-700 border-slate-300'
                  }`}
                >
                  Pilih Stasiun Tertentu ({selectedStations.length})
                </button>
              </div>

              {scopeMode === 'SELECTED' && (
                <div className="max-h-56 overflow-y-auto border border-slate-200 rounded-lg divide-y divide-slate-100">
                  {(activeRegencyObj?.stations || []).map((st) => {
                    const checked = selectedStations.includes(st.station_id);
                    return (
                      <label key={st.station_id} className="flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 cursor-pointer text-xs">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleStation(st.station_id)}
                        />
                        <span className="font-mono text-[11px] text-slate-500">{st.station_id}</span>
                        <span className="font-medium text-slate-800">{st.station_name}</span>
                      </label>
                    );
                  })}
                </div>
              )}

              {previewError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle size={15} /> {previewError}
                </div>
              )}
            </div>
          )}

          {/* STEP 4: PRATINJAU & KONFIRMASI */}
          {step === 4 && previewData && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Wilayah</div>
                  <div className="text-xs font-bold text-slate-900 mt-0.5 truncate">{previewData.regency_label}</div>
                </div>
                <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Periode</div>
                  <div className="text-xs font-mono font-bold text-slate-900 mt-0.5">{previewData.start_date} s/d {previewData.end_date}</div>
                </div>
                <div className="p-3 rounded-lg border border-amber-200 bg-amber-50">
                  <div className="text-[10px] font-semibold text-amber-700 uppercase">Stasiun Terdampak</div>
                  <div className="text-base font-mono font-bold text-amber-900">{previewData.affected_stations_count}</div>
                </div>
                <div className="p-3 rounded-lg border border-rose-200 bg-rose-50">
                  <div className="text-[10px] font-semibold text-rose-700 uppercase">Total Record VOID</div>
                  <div className="text-base font-mono font-bold text-rose-900">{previewData.total_records}</div>
                </div>
              </div>

              {previewData.total_records === 0 ? (
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 text-center">
                  Tidak ada data curah hujan aktif pada wilayah, periode, dan stasiun yang dipilih.
                </div>
              ) : (
                <>
                  <div className="border border-slate-200 rounded-lg overflow-hidden">
                    <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700">
                      Sampel Data Terdampak ({previewData.sample_records.length} dari {previewData.total_records} record)
                    </div>
                    <div className="max-h-44 overflow-y-auto">
                      <table className="w-full text-xs">
                        <thead className="bg-white sticky top-0 border-b border-slate-200 text-slate-500 text-[11px]">
                          <tr>
                            <th className="py-1.5 px-2.5 text-left">Tanggal</th>
                            <th className="py-1.5 px-2.5 text-left">Stasiun</th>
                            <th className="py-1.5 px-2.5 text-right">Nilai CH</th>
                            <th className="py-1.5 px-2.5 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {previewData.sample_records.map((r, i) => (
                            <tr key={i}>
                              <td className="py-1.5 px-2.5 font-mono">{r.observation_date}</td>
                              <td className="py-1.5 px-2.5">{r.station_name}</td>
                              <td className="py-1.5 px-2.5 text-right font-mono font-semibold">{r.display_value}</td>
                              <td className="py-1.5 px-2.5 text-center font-mono text-[10px] text-slate-600">{r.obs_status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="bg-rose-50/70 border border-rose-200 rounded-lg p-3.5 space-y-3 text-xs">
                    <div className="flex items-start gap-2 text-rose-900 font-medium">
                      <AlertTriangle size={15} className="shrink-0 mt-0.5 text-rose-600" />
                      <span>
                        Data akan ditandai <strong>VOID</strong> (soft-delete), tidak tampil pada tabel CH aktif maupun perhitungan SPI, dan dicatat penuh pada audit trail.
                      </span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">Operator</label>
                        <input
                          value={operatorName}
                          onChange={(e) => setOperatorName(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">Alasan Penghapusan (Wajib)</label>
                        <input
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          placeholder="Misal: Kesalahan periode impor sebelumnya..."
                          className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs"
                        />
                      </div>
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer font-semibold text-rose-900">
                      <input
                        type="checkbox"
                        checked={confirmCheck}
                        onChange={(e) => setConfirmCheck(e.target.checked)}
                      />
                      <span>Saya mengonfirmasi penonaktifan (VOID) {previewData.total_records} record pada periode ini.</span>
                    </label>
                  </div>
                </>
              )}

              {commitError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle size={15} /> {commitError}
                </div>
              )}
            </div>
          )}

          {/* STEP 5: SELESAI */}
          {step === 5 && commitResult && (
            <div className="py-6 text-center space-y-4">
              <CheckCircle2 size={42} className="mx-auto text-emerald-600" />
              <div>
                <h3 className="text-base font-bold text-slate-900">Penghapusan Data (VOID) Berhasil</h3>
                <p className="text-xs text-slate-600 mt-1">{commitResult.message}</p>
              </div>
              <div className="max-w-sm mx-auto bg-slate-50 border border-slate-200 rounded-lg p-3.5 text-xs space-y-1.5 text-left">
                <div className="flex justify-between"><span className="text-slate-500">Audit Batch ID</span><span className="font-mono font-bold">{commitResult.batch_id}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Record VOID</span><span className="font-mono font-bold text-rose-700">{commitResult.voided_records}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Stasiun</span><span className="font-mono">{commitResult.affected_stations_count}</span></div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-200 bg-slate-50">
          {step > 1 && step < 5 ? (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 flex items-center gap-1.5"
            >
              <ArrowLeft size={13} /> Kembali
            </button>
          ) : <div />}

          <div className="flex items-center gap-2">
            {step < 5 && (
              <button type="button" onClick={onClose} className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200/60">
                Batal
              </button>
            )}
            {step === 1 && (
              <button
                type="button"
                disabled={!selectedRegency}
                onClick={() => setStep(2)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                Lanjut <ArrowRight size={13} />
              </button>
            )}
            {step === 2 && (
              <button
                type="button"
                disabled={!startDate || !endDate || startDate > endDate}
                onClick={() => setStep(3)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                Lanjut <ArrowRight size={13} />
              </button>
            )}
            {step === 3 && (
              <button
                type="button"
                disabled={previewLoading || !canGoStep4}
                onClick={handleRunPreview}
                className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                {previewLoading ? 'Memeriksa...' : 'Pratinjau Dampak'} <ArrowRight size={13} />
              </button>
            )}
            {step === 4 && (
              <button
                type="button"
                disabled={commitLoading || !canCommit}
                onClick={handleCommitDelete}
                className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                <ShieldAlert size={14} />
                <span>{commitLoading ? 'Memproses VOID...' : 'Konfirmasi Hapus (VOID)'}</span>
              </button>
            )}
            {step === 5 && (
              <button type="button" onClick={onClose} className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold">
                Selesai
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
