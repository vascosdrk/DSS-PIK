import React, { useState, useEffect, useMemo } from 'react';
import {
  X,
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  History,
  Calendar,
  ChevronDown,
  Layers,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

const STEPS = [
  '1. Konteks',
  '2. Unggah',
  '3. Pratinjau',
  '4. Otorisasi',
  '5. Selesai',
];

const DIFF_BADGE_MAP = {
  NEW: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  'NEW VINTAGE': 'bg-sky-100 text-sky-800 border-sky-200',
  UPDATED: 'bg-amber-100 text-amber-800 border-amber-200',
  REACTIVATED: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  IDENTICAL: 'bg-slate-100 text-slate-600 border-slate-200',
  REJECTED: 'bg-rose-100 text-rose-800 border-rose-200',
};

/**
 * EcmwfForecastInputModal
 * Popup khusus input & pembaruan prakiraan ECMWF (Probabilitas % + Deterministik mm)
 * dengan desain ringkas 5-tahap yang selaras dengan RainfallInputModal.
 */
export default function EcmwfForecastInputModal({
  isOpen,
  onClose,
  onSuccess,
  onOpenManagement,
}) {
  // Operator explicitly selects resolution in Step 1 (independent of active page tab)
  const [selectedResolution, setSelectedResolution] = useState(null); // 'DASARIAN' | 'BULANAN' | null
  const isBulanan = selectedResolution === 'BULANAN';
  const requiredFilesCount = isBulanan ? 1 : 3;
  const datasetType = isBulanan ? 'PROBABILITAS_BULANAN' : 'PROBABILITAS_DASARIAN';

  // Wizard state: 1=Konteks & Resolusi, 2=Unggah, 3=Pratinjau, 4=Otorisasi, 5=Selesai
  const [step, setStep] = useState(1);

  // Step 2: Upload state
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

  // Step 3: Preview state
  const [previewData, setPreviewData] = useState(null);
  const [previewTab, setPreviewTab] = useState('PROB'); // 'PROB' | 'DET'
  const [showTechDetails, setShowTechDetails] = useState(false);

  // Step 4: Authorization & Commit state
  const [operatorName, setOperatorName] = useState('OPERATOR_BMKG');
  const [operatorNotes, setOperatorNotes] = useState('');
  const [allowUpdateExisting, setAllowUpdateExisting] = useState(false);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitError, setCommitError] = useState('');

  // Step 5: Result state
  const [commitResult, setCommitResult] = useState(null);

  // Reset modal whenever opened
  useEffect(() => {
    if (isOpen) {
      setSelectedResolution(null);
      setStep(1);
      setSelectedFiles([]);
      setIsDragging(false);
      setPreviewLoading(false);
      setPreviewError('');
      setPreviewData(null);
      setPreviewTab('PROB');
      setShowTechDetails(false);
      setOperatorNotes('');
      setAllowUpdateExisting(false);
      setConfirmChecked(false);
      setCommitLoading(false);
      setCommitError('');
      setCommitResult(null);
    }
  }, [isOpen]);

  // Safely clear previous files & preview state whenever operator switches resolution
  const handleSelectResolution = (res) => {
    if (res !== selectedResolution) {
      setSelectedResolution(res);
      setSelectedFiles([]);
      setPreviewData(null);
      setPreviewError('');
      setCommitError('');
      setAllowUpdateExisting(false);
      setConfirmChecked(false);
    }
  };

  // Derived preview summary
  const summary = useMemo(() => {
    if (!previewData) return null;
    const s = previewData.summary || {};
    const det = s.deterministic_summary || {};
    const periods = previewData.periods_detected || s.periods_detected || [];
    const filenames =
      previewData.filenames ||
      s.filenames ||
      (previewData.filename ? [previewData.filename] : []);
    const filesCount = s.files_count ?? filenames.length ?? selectedFiles.length;
    const probUpdated = s.updated_records ?? s.total_updated ?? 0;
    const detUpdated = (det.updated_records ?? 0) + (det.reactivated_records ?? 0);
    const hasAdjustConflicts = Boolean(
      previewData.has_adjust_conflicts || s.has_adjust_conflicts
    );
    const isIncompleteDasarian = !isBulanan && filesCount !== 3;

    return {
      stagingToken: previewData.staging_token || previewData.session_id,
      issueDate: previewData.forecast_issue_date || s.forecast_issue_date || '—',
      resolution: previewData.forecast_resolution || (isBulanan ? 'BULANAN' : 'DASARIAN'),
      releaseGroupId: previewData.release_group_id || s.release_group_id || '—',
      filesCount,
      filenames,
      periods,
      periodIds: periods.map((p) => p.period_id),
      probTotal: s.total_records ?? s.total_rows ?? 0,
      probNew: (s.new_records ?? 0) + (s.new_vintage_records ?? 0),
      probUpdated,
      probIdentical: s.identical_records ?? 0,
      detSheetFound: det.sheet_found ?? (det.total_records ?? 0) > 0,
      detTotal: det.total_records ?? 0,
      detNew: (det.new_records ?? 0) + (det.new_vintage_records ?? 0),
      detUpdated,
      detIdentical: det.identical_records ?? 0,
      adjustedColumns: det.adjusted_columns_used || [],
      ignoredColumns: det.ignored_non_forecast_columns || [],
      warnings: previewData.warnings || s.warnings || [],
      hasAdjustConflicts,
      isIncompleteDasarian,
      requiresUpdateConfirm: probUpdated + detUpdated > 0,
      totalUpdatesCount: probUpdated + detUpdated,
      stationMapping:
        previewData.station_mapping_summary || s.station_mapping_summary || null,
      probSamples: previewData.diff_samples || [],
      detSamples: previewData.deterministic_diff_samples || [],
    };
  }, [previewData, isBulanan, selectedFiles.length]);

  // File selection helpers
  const addIncomingFiles = (fileList) => {
    const incoming = Array.from(fileList || []);
    if (incoming.length === 0) return;
    setPreviewError('');
    if (isBulanan) {
      setSelectedFiles([incoming[0]]);
    } else {
      setSelectedFiles((prev) => {
        const existingNames = new Set(prev.map((f) => f.name));
        const merged = [...prev];
        incoming.forEach((f) => {
          if (!existingNames.has(f.name)) {
            merged.push(f);
            existingNames.add(f.name);
          }
        });
        return merged;
      });
    }
  };

  const handleRemoveFile = (idx) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== idx));
    setPreviewError('');
  };

  // Call existing backend preview endpoint (unchanged logic)
  const handleRunPreview = async () => {
    if (selectedFiles.length === 0) return;
    if (isBulanan && selectedFiles.length !== 1) {
      setPreviewError('Penerbitan Bulanan memerlukan tepat 1 file workbook (.xlsx).');
      return;
    }
    if (!isBulanan && selectedFiles.length > 3) {
      setPreviewError('Penerbitan Dasarian maksimal 3 file workbook (.xlsx).');
      return;
    }

    setPreviewLoading(true);
    setPreviewError('');

    const formData = new FormData();
    selectedFiles.forEach((f) => formData.append('files', f));
    formData.append('file', selectedFiles[0]);
    formData.append('data_type', datasetType);
    formData.append('dataset_type', datasetType);

    try {
      const res = await authFetch(API_ENDPOINTS.INGESTION_PREVIEW, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}: Validasi berkas gagal.`);
      }
      setPreviewData(data);
      setPreviewTab('PROB');
      setStep(3);
    } catch (err) {
      setPreviewError(err.message || 'Gagal membaca dan memvalidasi berkas workbook.');
    } finally {
      setPreviewLoading(false);
    }
  };

  // Call existing backend atomic commit endpoint (unchanged logic)
  const handleCommit = async () => {
    if (!summary?.stagingToken || !confirmChecked) return;
    setCommitLoading(true);
    setCommitError('');

    try {
      const payload = {
        staging_token: summary.stagingToken,
        operator: operatorName.trim() || 'OPERATOR_BMKG',
        confirm_overwrite: true,
        selected_periods: summary.periodIds.length > 0 ? summary.periodIds : null,
        explicit_update_consent: allowUpdateExisting,
        approval_scope: JSON.stringify({
          operator: operatorName.trim() || 'OPERATOR_BMKG',
          explicit_update_consent: allowUpdateExisting,
          selected_periods: summary.periodIds,
          notes: operatorNotes.trim(),
        }),
      };

      const res = await authFetch(API_ENDPOINTS.INGESTION_COMMIT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(result.detail || `HTTP ${res.status}: Penyimpanan data gagal.`);
      }
      setCommitResult(result);
      setStep(5);
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setCommitError(err.message || 'Gagal menyimpan data ke basis data operasional.');
    } finally {
      setCommitLoading(false);
    }
  };

  if (!isOpen) return null;

  const fileCountExact = selectedFiles.length === requiredFilesCount;
  const fileCountTooMany = selectedFiles.length > requiredFilesCount;
  const canPreview =
    selectedFiles.length > 0 &&
    !fileCountTooMany &&
    selectedFiles.every((f) => /\.xlsx?$/i.test(f.name));
  const canProceedToAuth =
    Boolean(summary) && !summary.hasAdjustConflicts && !summary.isIncompleteDasarian;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-3 sm:p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden border border-slate-200">
        {/* Header — selaras dengan RainfallInputModal */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-800 flex items-center justify-center">
              <FileSpreadsheet size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                INPUT DATA PRAKIRAAN ECMWF
              </h2>
              <div className="flex items-center gap-2 text-[11px] text-slate-500">
                <span>Tahap {step} / 5</span>
                {selectedResolution && (
                  <>
                    <span>&bull;</span>
                    <span className="font-semibold text-blue-800">
                      {isBulanan ? 'Bulanan' : 'Dasarian'}
                    </span>
                  </>
                )}
                <span>&bull;</span>
                <span>Probabilitas (%) + Deterministik (mm)</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {onOpenManagement && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenManagement('BATCHES');
                }}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white hover:bg-slate-100 border border-slate-300 text-[11px] font-semibold text-slate-700 transition"
                title="Buka tabel riwayat batch di Manajemen Data Operasional"
              >
                <History size={13} className="text-slate-500" />
                <span>Riwayat Batch Lengkap</span>
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition"
              aria-label="Tutup"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* 5-Step Stepper Bar — selaras dengan RainfallInputModal */}
        <div className="grid grid-cols-5 border-b border-slate-100 bg-white px-5 py-2 text-[11px] font-medium">
          {STEPS.map((lbl, idx) => {
            const num = idx + 1;
            const active = step === num;
            const done = step > num;
            return (
              <div
                key={lbl}
                className={`text-center py-1 rounded ${
                  active
                    ? 'bg-blue-50 text-blue-900 font-bold'
                    : done
                      ? 'text-emerald-600'
                      : 'text-slate-400'
                }`}
              >
                {lbl}
              </div>
            );
          })}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* TAHAP 1: KONTEKS & PEMILIHAN RESOLUSI */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Pilih Resolusi Penerbitan ECMWF
                </h3>
                <span className="text-[11px] text-slate-400">
                  Probabilitas (%) + Deterministik (mm) diproses otomatis
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <button
                  type="button"
                  onClick={() => handleSelectResolution('DASARIAN')}
                  className={`text-left p-4 rounded-xl border transition-all duration-150 ${
                    selectedResolution === 'DASARIAN'
                      ? 'border-blue-800 bg-blue-50/60 ring-1 ring-blue-800/30 shadow-xs'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/70 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-slate-900">Dasarian</span>
                    {selectedResolution === 'DASARIAN' && (
                      <CheckCircle2 size={16} className="text-blue-800 shrink-0" />
                    )}
                  </div>
                  <div className="mt-1.5 text-xs font-semibold text-emerald-700">
                    Wajib 3 file workbook (.xlsx)
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">
                    1 penerbitan (release group) memproses Probabilitas (%) dan Deterministik (mm) secara atomik.
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectResolution('BULANAN')}
                  className={`text-left p-4 rounded-xl border transition-all duration-150 ${
                    selectedResolution === 'BULANAN'
                      ? 'border-blue-800 bg-blue-50/60 ring-1 ring-blue-800/30 shadow-xs'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/70 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-slate-900">Bulanan</span>
                    {selectedResolution === 'BULANAN' && (
                      <CheckCircle2 size={16} className="text-blue-800 shrink-0" />
                    )}
                  </div>
                  <div className="mt-1.5 text-xs font-semibold text-emerald-700">
                    Wajib 1 file workbook (.xlsx)
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">
                    1 workbook bulan dinamis memproses Probabilitas (%) dan Deterministik (mm) secara atomik.
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* TAHAP 2: UNGGAH BERKAS */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Unggah Workbook ECMWF {isBulanan ? 'Bulanan' : 'Dasarian'}
                </h3>
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold border ${
                    fileCountExact
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : fileCountTooMany
                        ? 'bg-rose-50 text-rose-800 border-rose-200'
                        : 'bg-amber-50 text-amber-800 border-amber-200'
                  }`}
                >
                  {fileCountExact ? (
                    <CheckCircle2 size={13} />
                  ) : (
                    <AlertTriangle size={13} />
                  )}
                  <span>
                    {selectedFiles.length} / {requiredFilesCount} file dipilih
                  </span>
                </span>
              </div>

              {/* Clean Dropzone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  addIncomingFiles(e.dataTransfer.files);
                }}
                className={`border-2 border-dashed rounded-xl p-6 text-center transition ${
                  isDragging
                    ? 'border-blue-600 bg-blue-50/50'
                    : 'border-slate-300 bg-slate-50/50'
                }`}
              >
                <UploadCloud size={28} className="mx-auto text-blue-700 mb-2" />
                <div className="text-xs font-semibold text-slate-800">
                  {isBulanan
                    ? 'Seret 1 file workbook ECMWF Bulanan ke sini'
                    : 'Seret 3 file workbook ECMWF Dasarian ke sini'}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 mb-3">
                  Format .xlsx &bull; Issue date dan periode dibaca otomatis
                </div>
                <label className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer transition">
                  <span>Pilih Berkas</span>
                  <input
                    type="file"
                    multiple={!isBulanan}
                    accept=".xlsx,.xls"
                    className="hidden"
                    onChange={(e) => {
                      addIncomingFiles(e.target.files);
                      e.target.value = '';
                    }}
                  />
                </label>
              </div>

              {/* Selected files list */}
              {selectedFiles.length > 0 && (
                <div className="border border-slate-200 rounded-lg divide-y divide-slate-100 bg-white">
                  {selectedFiles.map((f, idx) => {
                    const validExt = /\.xlsx?$/i.test(f.name);
                    return (
                      <div
                        key={`${f.name}-${idx}`}
                        className="flex items-center justify-between gap-3 px-3.5 py-2.5 text-xs"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <FileSpreadsheet
                            size={15}
                            className={validExt ? 'text-emerald-600 shrink-0' : 'text-rose-600 shrink-0'}
                          />
                          <span className="font-mono font-medium text-slate-800 truncate">
                            {f.name}
                          </span>
                          <span className="text-[11px] text-slate-400 shrink-0">
                            ({(f.size / 1024).toFixed(0)} KB)
                          </span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              validExt
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-rose-50 text-rose-700 border-rose-200'
                            }`}
                          >
                            {validExt ? 'Siap' : 'Format salah'}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleRemoveFile(idx)}
                            className="text-slate-400 hover:text-rose-600 font-bold px-1 text-sm"
                            aria-label={`Hapus ${f.name}`}
                          >
                            &times;
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {!isBulanan && selectedFiles.length > 0 && selectedFiles.length < 3 && (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-800 flex items-center gap-2">
                  <AlertTriangle size={14} className="shrink-0 text-amber-600" />
                  <span>
                    Pratinjau dapat dijalankan untuk {selectedFiles.length} file, namun penyimpanan penerbitan Dasarian mewajibkan 3 file workbook.
                  </span>
                </div>
              )}

              {previewError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2">
                  <AlertCircle size={15} className="shrink-0 mt-0.5 text-rose-600" />
                  <span>{previewError}</span>
                </div>
              )}
            </div>
          )}

          {/* TAHAP 3: PRATINJAU & RINGKASAN */}
          {step === 3 && summary && (
            <div className="space-y-4">
              {/* Compact Metadata Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="p-2.5 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="text-[10px] font-semibold uppercase text-slate-500">
                    Issue Date (Vintage)
                  </div>
                  <div className="text-sm font-bold font-mono text-slate-900 mt-0.5">
                    {summary.issueDate}
                  </div>
                </div>
                <div className="p-2.5 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="text-[10px] font-semibold uppercase text-slate-500">
                    Resolusi &amp; Berkas
                  </div>
                  <div className="text-sm font-bold text-blue-900 mt-0.5">
                    {summary.resolution} &middot; {summary.filesCount} file
                  </div>
                </div>
                <div className="p-2.5 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="text-[10px] font-semibold uppercase text-slate-500">
                    Release Group
                  </div>
                  <div
                    className="text-xs font-bold font-mono text-slate-800 mt-1 truncate"
                    title={summary.releaseGroupId}
                  >
                    {summary.releaseGroupId}
                  </div>
                </div>
                <div className="p-2.5 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="text-[10px] font-semibold uppercase text-slate-500">
                    Periode Target
                  </div>
                  <div className="text-sm font-bold font-mono text-slate-900 mt-0.5">
                    {summary.periods.length} periode
                  </div>
                </div>
              </div>

              {/* Target Period Pills */}
              {summary.periods.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                  <span className="inline-flex items-center gap-1 text-slate-500 font-semibold mr-1">
                    <Calendar size={12} /> Periode:
                  </span>
                  {summary.periods.map((p) => (
                    <span
                      key={p.period_id}
                      className="px-2 py-0.5 rounded bg-blue-50 text-blue-900 border border-blue-200 font-mono font-semibold"
                    >
                      {p.label || p.period_id}
                    </span>
                  ))}
                </div>
              )}

              {/* Probabilitas vs Deterministik Status Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800">
                      Probabilitas (%)
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                      Terbaca
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-1.5 text-center text-[11px]">
                    <div className="p-1.5 rounded bg-slate-50">
                      <div className="text-slate-400 text-[10px]">Total</div>
                      <div className="font-mono font-bold text-slate-800">{summary.probTotal}</div>
                    </div>
                    <div className="p-1.5 rounded bg-emerald-50/70">
                      <div className="text-emerald-700 text-[10px]">Baru</div>
                      <div className="font-mono font-bold text-emerald-700">+{summary.probNew}</div>
                    </div>
                    <div className="p-1.5 rounded bg-amber-50/70">
                      <div className="text-amber-700 text-[10px]">Update</div>
                      <div className="font-mono font-bold text-amber-700">{summary.probUpdated}</div>
                    </div>
                    <div className="p-1.5 rounded bg-slate-50">
                      <div className="text-slate-400 text-[10px]">Identik</div>
                      <div className="font-mono font-bold text-slate-600">{summary.probIdentical}</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800">
                      Deterministik (mm)
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        summary.detTotal > 0
                          ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                          : 'bg-amber-50 text-amber-800 border-amber-200'
                      }`}
                    >
                      {summary.detTotal > 0 ? 'Terbaca' : 'Tidak ada data'}
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-1.5 text-center text-[11px]">
                    <div className="p-1.5 rounded bg-slate-50">
                      <div className="text-slate-400 text-[10px]">Total</div>
                      <div className="font-mono font-bold text-slate-800">{summary.detTotal}</div>
                    </div>
                    <div className="p-1.5 rounded bg-emerald-50/70">
                      <div className="text-emerald-700 text-[10px]">Baru</div>
                      <div className="font-mono font-bold text-emerald-700">+{summary.detNew}</div>
                    </div>
                    <div className="p-1.5 rounded bg-amber-50/70">
                      <div className="text-amber-700 text-[10px]">Update</div>
                      <div className="font-mono font-bold text-amber-700">{summary.detUpdated}</div>
                    </div>
                    <div className="p-1.5 rounded bg-slate-50">
                      <div className="text-slate-400 text-[10px]">Identik</div>
                      <div className="font-mono font-bold text-slate-600">{summary.detIdentical}</div>
                    </div>
                  </div>
                  {summary.adjustedColumns.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1 pt-1 text-[10px]">
                      <span className="font-semibold text-emerald-800">Adjust:</span>
                      {summary.adjustedColumns.map((col, idx) => (
                        <span
                          key={idx}
                          className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono"
                        >
                          {col}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Concise Alerts: Conflict / Incomplete Release / Warnings */}
              {summary.hasAdjustConflicts && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-300 text-xs text-rose-900 flex items-start gap-2">
                  <AlertCircle size={15} className="text-rose-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Konflik kolom Adjust terdeteksi.</strong> Simpan diblokir hingga header workbook diklarifikasi.
                  </span>
                </div>
              )}

              {summary.isIncompleteDasarian && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-300 text-xs text-amber-900 flex items-start gap-2">
                  <AlertTriangle size={15} className="text-amber-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Berkas Dasarian belum lengkap ({summary.filesCount}/3).</strong> Lengkapi 3 file workbook sebelum menyimpan.
                  </span>
                </div>
              )}

              {summary.warnings.length > 0 && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertTriangle size={14} className="text-amber-600" />
                    <span>Peringatan ({summary.warnings.length})</span>
                  </div>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                    {summary.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Compact Sample Table */}
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
                  <span className="text-xs font-semibold text-slate-700">
                    Sampel Data Terbaca
                  </span>
                  <div className="inline-flex rounded-md border border-slate-300 overflow-hidden text-[11px]">
                    <button
                      type="button"
                      onClick={() => setPreviewTab('PROB')}
                      className={`px-2.5 py-1 font-semibold transition ${
                        previewTab === 'PROB'
                          ? 'bg-blue-900 text-white'
                          : 'bg-white text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      Probabilitas (%)
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreviewTab('DET')}
                      className={`px-2.5 py-1 font-semibold transition ${
                        previewTab === 'DET'
                          ? 'bg-blue-900 text-white'
                          : 'bg-white text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      Deterministik (mm)
                    </button>
                  </div>
                </div>

                <div className="max-h-48 overflow-y-auto">
                  {previewTab === 'PROB' ? (
                    <table className="w-full text-xs">
                      <thead className="bg-white sticky top-0 border-b border-slate-200 text-slate-500 text-[11px]">
                        <tr>
                          <th className="py-1.5 px-2.5 text-left">Periode</th>
                          <th className="py-1.5 px-2.5 text-left">Stasiun</th>
                          <th className="py-1.5 px-2.5 text-left">Parameter</th>
                          <th className="py-1.5 px-2.5 text-right">Nilai (%)</th>
                          <th className="py-1.5 px-2.5 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {summary.probSamples.slice(0, 25).map((r, i) => {
                          const st = r.change_type || 'NEW';
                          const val = r.new_value ?? r.probability_value;
                          return (
                            <tr key={i}>
                              <td className="py-1.5 px-2.5 font-mono">{r.target_period || r.period_id || '—'}</td>
                              <td className="py-1.5 px-2.5 truncate max-w-[180px]">{r.station_name || r.station_id}</td>
                              <td className="py-1.5 px-2.5 font-mono font-semibold">{r.indicator || r.forecast_parameter || '—'}</td>
                              <td className="py-1.5 px-2.5 text-right font-mono font-semibold">
                                {val !== null && val !== undefined ? `${val}%` : '—'}
                              </td>
                              <td className="py-1.5 px-2.5 text-center">
                                <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${DIFF_BADGE_MAP[st] || 'bg-slate-100'}`}>
                                  {st}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                        {summary.probSamples.length === 0 && (
                          <tr>
                            <td colSpan={5} className="py-4 text-center text-slate-400">
                              Tidak ada sampel probabilitas.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  ) : (
                    <table className="w-full text-xs">
                      <thead className="bg-white sticky top-0 border-b border-slate-200 text-slate-500 text-[11px]">
                        <tr>
                          <th className="py-1.5 px-2.5 text-left">Periode</th>
                          <th className="py-1.5 px-2.5 text-left">Stasiun</th>
                          <th className="py-1.5 px-2.5 text-right">Curah Hujan (mm)</th>
                          <th className="py-1.5 px-2.5 text-center">Kolom</th>
                          <th className="py-1.5 px-2.5 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {summary.detSamples.slice(0, 25).map((r, i) => {
                          const st = r.change_type || 'NEW';
                          return (
                            <tr key={i}>
                              <td className="py-1.5 px-2.5 font-mono">{r.period_id || r.target_period || '—'}</td>
                              <td className="py-1.5 px-2.5 truncate max-w-[180px]">{r.station_name || r.station_id}</td>
                              <td className="py-1.5 px-2.5 text-right font-mono font-semibold">
                                {r.value_mm !== null && r.value_mm !== undefined ? `${Number(r.value_mm).toFixed(1)} mm` : '—'}
                              </td>
                              <td className="py-1.5 px-2.5 text-center">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    r.adjustment_status === 'ADJUSTED'
                                      ? 'bg-emerald-100 text-emerald-800'
                                      : 'bg-sky-100 text-sky-800'
                                  }`}
                                >
                                  {r.adjustment_status || 'REGULAR'}
                                </span>
                              </td>
                              <td className="py-1.5 px-2.5 text-center">
                                <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${DIFF_BADGE_MAP[st] || 'bg-slate-100'}`}>
                                  {st}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                        {summary.detSamples.length === 0 && (
                          <tr>
                            <td colSpan={5} className="py-4 text-center text-slate-400">
                              Tidak ada sampel deterministik.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>

              {/* Expandable Technical Details */}
              <div className="border border-slate-200 rounded-lg bg-slate-50/70">
                <button
                  type="button"
                  onClick={() => setShowTechDetails((v) => !v)}
                  className="w-full flex items-center justify-between px-3.5 py-2 text-[11px] font-semibold text-slate-600 hover:text-slate-900"
                >
                  <span className="inline-flex items-center gap-1.5">
                    <Layers size={13} />
                    Detail Teknis Pemetaan &amp; Kolom
                  </span>
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${showTechDetails ? 'rotate-180' : ''}`}
                  />
                </button>
                {showTechDetails && (
                  <div className="px-3.5 pb-3 pt-1 border-t border-slate-200 text-[11px] text-slate-600 space-y-1.5">
                    {summary.stationMapping && (
                      <div>
                        Pos Master Terpetakan:{' '}
                        <strong className="font-mono text-slate-800">
                          {summary.stationMapping.matched_stations_count ?? 0}
                        </strong>
                        {' · '}Pos Eksternal Diisolasi:{' '}
                        <strong className="font-mono text-slate-800">
                          {summary.stationMapping.unmapped_external_stations_count ??
                            summary.stationMapping.unmapped_external_count ??
                            0}
                        </strong>
                      </div>
                    )}
                    {summary.ignoredColumns.length > 0 && (
                      <div>
                        Kolom non-prakiraan diabaikan:{' '}
                        <span className="font-mono">
                          {summary.ignoredColumns
                            .map((c) => (typeof c === 'string' ? c : c.header || c.source_column))
                            .join(', ')}
                        </span>
                      </div>
                    )}
                    <div className="font-mono text-[10px] text-slate-500">
                      Berkas: {summary.filenames.join(', ')}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAHAP 4: OTORISASI & SIMPAN */}
          {step === 4 && summary && (
            <div className="space-y-4">
              <div className="p-3 rounded-lg bg-blue-50/80 border border-blue-200 text-xs text-blue-950 flex items-center gap-2">
                <ShieldCheck size={16} className="text-blue-700 shrink-0" />
                <span>
                  Data <strong>Probabilitas (%)</strong> dan <strong>Deterministik (mm)</strong> untuk vintage{' '}
                  <strong className="font-mono">{summary.issueDate}</strong> akan disimpan dalam satu transaksi atomik.
                </span>
              </div>

              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-3 text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">
                      Operator
                    </label>
                    <input
                      type="text"
                      value={operatorName}
                      onChange={(e) => setOperatorName(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">
                      Catatan / Alasan (Opsional)
                    </label>
                    <input
                      type="text"
                      value={operatorNotes}
                      onChange={(e) => setOperatorNotes(e.target.value)}
                      placeholder="Misal: Rilis berkala ECMWF..."
                      className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs"
                    />
                  </div>
                </div>

                {summary.requiresUpdateConfirm && (
                  <label className="flex items-center gap-2 p-2.5 rounded border border-amber-300 bg-amber-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allowUpdateExisting}
                      onChange={(e) => setAllowUpdateExisting(e.target.checked)}
                    />
                    <span className="font-semibold text-amber-900">
                      Izinkan pembaruan {summary.totalUpdatesCount} baris data lama yang berbeda
                    </span>
                  </label>
                )}

                <label className="flex items-center gap-2 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={confirmChecked}
                    onChange={(e) => setConfirmChecked(e.target.checked)}
                  />
                  <span className="font-medium text-slate-800">
                    Saya telah memeriksa pratinjau dan menyetujui penyimpanan ke basis data operasional.
                  </span>
                </label>
              </div>

              {commitError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle size={15} className="shrink-0" />
                  <span>{commitError}</span>
                </div>
              )}
            </div>
          )}

          {/* TAHAP 5: SELESAI */}
          {step === 5 && commitResult && (
            <div className="py-5 text-center space-y-4">
              <CheckCircle2 size={44} className="mx-auto text-emerald-600" />
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Data Prakiraan ECMWF Tersimpan
                </h3>
                <p className="text-xs text-slate-600 mt-1">
                  {commitResult.message || 'Probabilitas (%) dan Deterministik (mm) berhasil disimpan secara atomik.'}
                </p>
              </div>
              <div className="max-w-md mx-auto bg-slate-50 border border-slate-200 rounded-lg p-3.5 text-xs space-y-1.5 text-left">
                <div className="flex justify-between">
                  <span className="text-slate-500">Status</span>
                  <span className="font-bold text-emerald-700">Berhasil</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Batch ID</span>
                  <span className="font-mono font-bold text-slate-800">{commitResult.batch_id || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Issue Date (Vintage)</span>
                  <span className="font-mono font-semibold text-slate-800">{summary?.issueDate || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Release Group</span>
                  <span className="font-mono text-slate-700">{commitResult.release_group_id || summary?.releaseGroupId || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Record Probabilitas (%)</span>
                  <span className="font-mono font-bold text-blue-800">
                    {commitResult.prob_written ?? summary?.probTotal ?? 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Record Deterministik (mm)</span>
                  <span className="font-mono font-bold text-emerald-700">
                    {commitResult.det_written ?? summary?.detTotal ?? 0}
                  </span>
                </div>
                {(summary?.warnings?.length || 0) > 0 && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Peringatan</span>
                    <span className="font-mono font-semibold text-amber-700">
                      {summary.warnings.length}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions — selaras dengan RainfallInputModal */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-200 bg-slate-50/80">
          {step > 1 && step < 5 ? (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              disabled={previewLoading || commitLoading}
              className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 flex items-center gap-1.5 disabled:opacity-50"
            >
              <ArrowLeft size={13} /> Kembali
            </button>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2">
            {step < 5 && (
              <button
                type="button"
                onClick={onClose}
                disabled={previewLoading || commitLoading}
                className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-600 disabled:opacity-50"
              >
                Batal
              </button>
            )}

            {step === 1 && (
              <button
                type="button"
                onClick={() => setStep(2)}
                disabled={!selectedResolution}
                className="px-4 py-1.5 rounded-lg bg-blue-900 hover:bg-blue-800 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
              >
                <span>Lanjut: Unggah Berkas</span>
                <ArrowRight size={13} />
              </button>
            )}

            {step === 2 && (
              <button
                type="button"
                onClick={handleRunPreview}
                disabled={!canPreview || previewLoading}
                className="px-4 py-1.5 rounded-lg bg-blue-900 hover:bg-blue-800 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
              >
                {previewLoading ? (
                  <>
                    <div className="spin spinner-sm" />
                    <span>Membaca Workbook...</span>
                  </>
                ) : (
                  <>
                    <span>Pratinjau &amp; Validasi</span>
                    <ArrowRight size={13} />
                  </>
                )}
              </button>
            )}

            {step === 3 && (
              <button
                type="button"
                onClick={() => setStep(4)}
                disabled={!canProceedToAuth}
                className="px-4 py-1.5 rounded-lg bg-blue-900 hover:bg-blue-800 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
              >
                <span>Lanjut: Otorisasi</span>
                <ArrowRight size={13} />
              </button>
            )}

            {step === 4 && (
              <button
                type="button"
                onClick={handleCommit}
                disabled={!confirmChecked || commitLoading}
                className="px-4 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
              >
                {commitLoading ? (
                  <>
                    <div className="spin spinner-sm" />
                    <span>Menyimpan...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck size={14} />
                    <span>Simpan Data</span>
                  </>
                )}
              </button>
            )}

            {step === 5 && (
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-1.5 rounded-lg bg-blue-900 hover:bg-blue-800 text-white text-xs font-semibold"
              >
                Selesai
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
