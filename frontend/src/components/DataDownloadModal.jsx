import React, { useState, useEffect } from 'react';
import { 
  X, 
  Download, 
  FileSpreadsheet, 
  FileText, 
  Calendar, 
  CheckCircle2, 
  AlertCircle, 
  Layers, 
  Activity, 
  Percent,
  Droplets,
  Loader2
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

export default function DataDownloadModal({ 
  isOpen, 
  onClose, 
  initialDataType = 'RAINFALL',
  initialParams = {} 
}) {
  const [dataType, setDataType] = useState(initialDataType); // 'RAINFALL' | 'SPI' | 'PROBABILITY'
  const [fileFormat, setFileFormat] = useState('xlsx'); // 'xlsx' | 'csv'
  
  // Stations master list
  const [stationsMaster, setStationsMaster] = useState([]);
  const [stationSelectionMode, setStationSelectionMode] = useState('ALL'); // 'ALL' | 'SINGLE' | 'MULTI'
  const [selectedStationIds, setSelectedStationIds] = useState([]);
  
  // Periods list
  const [periodsList, setPeriodsList] = useState([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState('2026-09-das2');

  // Date filters for Rainfall and SPI
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-09-20');

  // SPI specific options
  const [spiPeriodType, setSpiPeriodType] = useState('DASARIAN'); // 'DASARIAN' | 'DAILY'
  const [spiTimescale, setSpiTimescale] = useState('30D'); // '30D' | '90D'

  // Download state
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  // Sync initial props
  useEffect(() => {
    if (initialDataType) setDataType(initialDataType);
    if (initialParams.periodType) setSpiPeriodType(initialParams.periodType);
    if (initialParams.timescale) setSpiTimescale(initialParams.timescale);
    if (initialParams.periodId) setSelectedPeriodId(initialParams.periodId);
  }, [initialDataType, initialParams]);

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

  // Load master stations & periods
  useEffect(() => {
    if (!isOpen) return;

    authFetch(API_ENDPOINTS.STATIONS_MASTER)
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.stations)) {
          setStationsMaster(data.stations);
        }
      })
      .catch((err) => console.error('Failed to load stations in download modal:', err));

    authFetch(API_ENDPOINTS.PERIODS)
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.periods)) {
          setPeriodsList(data.periods);
          if (data.periods.length > 0 && !selectedPeriodId) {
            setSelectedPeriodId(data.periods[0].period_id);
          }
        }
      })
      .catch((err) => console.error('Failed to load periods in download modal:', err));
  }, [isOpen]);

  if (!isOpen) return null;

  const handleStationToggle = (stnId) => {
    setSelectedStationIds((prev) => {
      if (prev.includes(stnId)) {
        return prev.filter((id) => id !== stnId);
      } else {
        return [...prev, stnId];
      }
    });
  };

  const handleExecuteDownload = async (e) => {
    e.preventDefault();
    setDownloading(true);
    setDownloadError(null);
    setDownloadSuccess(false);

    try {
      let downloadUrl = '';
      let filename = `DSS_PIK_${dataType}_${new Date().toISOString().slice(0, 10)}.${fileFormat}`;

      // Station ID param construction
      let stnParam = '';
      if (stationSelectionMode === 'SINGLE' && selectedStationIds.length > 0) {
        stnParam = selectedStationIds[0];
      } else if (stationSelectionMode === 'MULTI' && selectedStationIds.length > 0) {
        stnParam = selectedStationIds.join(',');
      }

      if (dataType === 'RAINFALL') {
        const params = {
          format: fileFormat,
          start_date: startDate,
          end_date: endDate,
        };
        if (stnParam) params.station_ids = stnParam;
        downloadUrl = API_ENDPOINTS.RAINFALL_DOWNLOAD(params);
        filename = `Curah_Hujan_${startDate}_sd_${endDate}.${fileFormat}`;
      } else if (dataType === 'SPI') {
        const params = {
          period_type: spiPeriodType,
          timescale: spiTimescale,
          format: fileFormat,
        };
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;
        if (stnParam) params.station_ids = stnParam;
        downloadUrl = API_ENDPOINTS.SPI_DOWNLOAD(params);
        filename = `SPI_${spiPeriodType}_${spiTimescale}_${startDate || 'awal'}_sd_${endDate || 'akhir'}.${fileFormat}`;
      } else if (dataType === 'PROBABILITY') {
        const params = {
          period_id: selectedPeriodId,
          format: fileFormat,
        };
        if (stnParam) params.station_ids = stnParam;
        downloadUrl = API_ENDPOINTS.PROBABILITY_DOWNLOAD(params);
        filename = `Probabilitas_ECMWF_${selectedPeriodId}.${fileFormat}`;
      }

      // Execute authenticated fetch
      const res = await authFetch(downloadUrl);
      if (!res.ok) {
        let errDetail = `HTTP ${res.status}`;
        try {
          const errJson = await res.json();
          if (errJson.detail) errDetail = errJson.detail;
        } catch {
          // fallback
        }
        throw new Error(errDetail);
      }

      // Extract filename from header if present
      const disposition = res.headers.get('content-disposition');
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename="?([^";]+)"?/);
        if (match && match[1]) filename = match[1];
      }

      const blob = await res.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const tempLink = document.createElement('a');
      tempLink.href = objectUrl;
      tempLink.setAttribute('download', filename);
      document.body.appendChild(tempLink);
      tempLink.click();
      tempLink.parentNode.removeChild(tempLink);
      window.URL.revokeObjectURL(objectUrl);

      setDownloadSuccess(true);
      setTimeout(() => {
        setDownloadSuccess(false);
      }, 3000);
    } catch (err) {
      console.error('Download execution failed:', err);
      setDownloadError(err.message || 'Gagal mengunduh berkas data.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="modal-backdrop-custom" onClick={onClose} role="dialog" aria-modal="true">
      <div className="download-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header-compact">
          <div className="modal-header-left">
            <div className="modal-icon-wrap bg-emerald">
              <Download size={19} className="text-white" />
            </div>
            <div>
              <h3 className="modal-title-compact">Pusat Unduh Data DSS-PIK</h3>
              <p className="modal-subtitle-compact">Ekspor resmi data observasi, SPI, dan prakiraan probabilitas</p>
            </div>
          </div>
          <button 
            type="button" 
            className="btn-close-compact" 
            onClick={onClose} 
            title="Tutup jendela unduh"
            aria-label="Tutup jendela unduh"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleExecuteDownload} className="download-modal-form">
          {/* 1. Data Type Selection Tabs */}
          <div className="download-form-section">
            <label className="section-label-bold">Pilih Kategori Dataset:</label>
            <div className="dataset-type-grid">
              <button
                type="button"
                className={`type-select-card ${dataType === 'RAINFALL' ? 'active' : ''}`}
                onClick={() => setDataType('RAINFALL')}
              >
                <Droplets size={20} className="type-card-icon text-blue" />
                <div className="type-card-text">
                  <span className="type-card-title">Curah Hujan (CH)</span>
                  <span className="type-card-desc">Observasi harian MariaDB (format wide/spreadsheet)</span>
                </div>
              </button>

              <button
                type="button"
                className={`type-select-card ${dataType === 'SPI' ? 'active' : ''}`}
                onClick={() => setDataType('SPI')}
              >
                <Activity size={20} className="type-card-icon text-forest" />
                <div className="type-card-text">
                  <span className="type-card-title">Indeks SPI</span>
                  <span className="type-card-desc">Dasarian / Harian akumulasi 30d & 90d</span>
                </div>
              </button>

              <button
                type="button"
                className={`type-select-card ${dataType === 'PROBABILITY' ? 'active' : ''}`}
                onClick={() => setDataType('PROBABILITY')}
              >
                <Percent size={20} className="type-card-icon text-indigo" />
                <div className="type-card-text">
                  <span className="type-card-title">Probabilitas ECMWF</span>
                  <span className="type-card-desc">Peluang curah hujan dasarian & bulanan (0–100%)</span>
                </div>
              </button>
            </div>
          </div>

          {/* 2. SPI Specific Options */}
          {dataType === 'SPI' && (
            <div className="download-form-section bg-light-panel">
              <label className="section-label-bold">Konfigurasi Sumber SPI:</label>
              <div className="spi-config-grid">
                <div>
                  <span className="filter-tiny-label">Resolusi Waktu</span>
                  <div className="segmented-switch mini-switch">
                    <button
                      type="button"
                      className={`switch-btn ${spiPeriodType === 'DASARIAN' ? 'active' : ''}`}
                      onClick={() => setSpiPeriodType('DASARIAN')}
                    >
                      Dasarian
                    </button>
                    <button
                      type="button"
                      className={`switch-btn ${spiPeriodType === 'DAILY' ? 'active' : ''}`}
                      onClick={() => setSpiPeriodType('DAILY')}
                    >
                      Harian
                    </button>
                  </div>
                </div>

                <div>
                  <span className="filter-tiny-label">Periode Akumulasi</span>
                  <div className="segmented-switch mini-switch">
                    <button
                      type="button"
                      className={`switch-btn ${spiTimescale === '30D' ? 'active' : ''}`}
                      onClick={() => setSpiTimescale('30D')}
                    >
                      30 Hari (30d)
                    </button>
                    <button
                      type="button"
                      className={`switch-btn ${spiTimescale === '90D' ? 'active' : ''}`}
                      onClick={() => setSpiTimescale('90D')}
                    >
                      90 Hari (90d)
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 3. Probability Specific Options */}
          {dataType === 'PROBABILITY' && (
            <div className="download-form-section bg-light-panel">
              <label htmlFor="modal-prob-period" className="section-label-bold">Pilih Periode Target Prakiraan:</label>
              <select
                id="modal-prob-period"
                className="form-control-input font-mono"
                value={selectedPeriodId}
                onChange={(e) => setSelectedPeriodId(e.target.value)}
              >
                {periodsList.map((p) => (
                  <option key={p.period_id} value={p.period_id}>
                    {p.label} ({p.date_range})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* 4. Date Range Filters (for RAINFALL and SPI) */}
          {(dataType === 'RAINFALL' || dataType === 'SPI') && (
            <div className="download-form-section">
              <label className="section-label-bold">Rentang Tanggal / Periode:</label>
              <div className="date-range-row">
                <div className="date-field">
                  <span className="filter-tiny-label">Tanggal Mulai</span>
                  <input
                    type="date"
                    className="form-control-input"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    required
                  />
                </div>
                <div className="date-field">
                  <span className="filter-tiny-label">Tanggal Selesai</span>
                  <input
                    type="date"
                    className="form-control-input"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>
          )}

          {/* 5. Station Selection Mode */}
          <div className="download-form-section">
            <label className="section-label-bold">Pilihan Pos Pengamatan:</label>
            <div className="station-mode-segmented">
              <button
                type="button"
                className={`switch-btn ${stationSelectionMode === 'ALL' ? 'active' : ''}`}
                onClick={() => setStationSelectionMode('ALL')}
              >
                Semua Pos (57 Titik)
              </button>
              <button
                type="button"
                className={`switch-btn ${stationSelectionMode === 'SINGLE' ? 'active' : ''}`}
                onClick={() => {
                  setStationSelectionMode('SINGLE');
                  if (selectedStationIds.length === 0 && stationsMaster.length > 0) {
                    setSelectedStationIds([stationsMaster[0].station_id]);
                  }
                }}
              >
                Satu Pos
              </button>
              <button
                type="button"
                className={`switch-btn ${stationSelectionMode === 'MULTI' ? 'active' : ''}`}
                onClick={() => setStationSelectionMode('MULTI')}
              >
                Beberapa Pos Terpilih
              </button>
            </div>

            {/* Single Station Select */}
            {stationSelectionMode === 'SINGLE' && (
              <div className="mt-2">
                <select
                  className="form-control-input"
                  value={selectedStationIds[0] || ''}
                  onChange={(e) => setSelectedStationIds([e.target.value])}
                >
                  {stationsMaster.map((stn) => (
                    <option key={stn.station_id} value={stn.station_id}>
                      {stn.station_id} — {stn.station_name} ({stn.kabupaten})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Multi Stations Checklist */}
            {stationSelectionMode === 'MULTI' && (
              <div className="multi-stn-checklist-container mt-2">
                <div className="multi-stn-header-meta">
                  <span>{selectedStationIds.length} stasiun terpilih</span>
                  <div className="flex-align gap-2">
                    <button
                      type="button"
                      className="btn-text-action"
                      onClick={() => setSelectedStationIds(stationsMaster.map((s) => s.station_id))}
                    >
                      Pilih Semua
                    </button>
                    <button
                      type="button"
                      className="btn-text-action"
                      onClick={() => setSelectedStationIds([])}
                    >
                      Hapus Pilihan
                    </button>
                  </div>
                </div>
                <div className="multi-stn-scrollbox">
                  {stationsMaster.map((stn) => {
                    const checked = selectedStationIds.includes(stn.station_id);
                    return (
                      <label key={stn.station_id} className="stn-checkbox-item">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => handleStationToggle(stn.station_id)}
                        />
                        <span className="font-mono text-xs">{stn.station_id}</span>
                        <span className="font-medium text-xs">{stn.station_name}</span>
                        <span className="text-muted text-xs">({stn.kabupaten})</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* 6. Export Format Selection */}
          <div className="download-form-section">
            <label className="section-label-bold">Format Berkas:</label>
            <div className="format-selection-row">
              <label className={`format-radio-card ${fileFormat === 'xlsx' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="fileFormat"
                  value="xlsx"
                  checked={fileFormat === 'xlsx'}
                  onChange={() => setFileFormat('xlsx')}
                />
                <FileSpreadsheet size={18} className="text-emerald" />
                <div>
                  <span className="format-title">Microsoft Excel (.xlsx)</span>
                  <span className="format-desc">Format tabular wide dengan styling rapi, formula, dan header stasiun</span>
                </div>
              </label>

              <label className={`format-radio-card ${fileFormat === 'csv' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="fileFormat"
                  value="csv"
                  checked={fileFormat === 'csv'}
                  onChange={() => setFileFormat('csv')}
                />
                <FileText size={18} className="text-blue" />
                <div>
                  <span className="format-title">Comma-Separated Values (.csv)</span>
                  <span className="format-desc">Teks terstruktur standar untuk analisis data atau pemodelan statistik</span>
                </div>
              </label>
            </div>
          </div>

          {/* Feedback messages */}
          {downloadError && (
            <div className="download-alert-banner alert-error">
              <AlertCircle size={16} />
              <span>{downloadError}</span>
            </div>
          )}

          {downloadSuccess && (
            <div className="download-alert-banner alert-success">
              <CheckCircle2 size={16} />
              <span>Berkas berhasil disiapkan dan diunduh ke peramban Anda!</span>
            </div>
          )}

          {/* Submit Action Buttons */}
          <div className="modal-footer-compact">
            <button
              type="button"
              className="btn-cancel-modal"
              onClick={onClose}
              disabled={downloading}
            >
              Batal
            </button>
            <button
              type="submit"
              className="btn-submit-download"
              disabled={downloading || (stationSelectionMode !== 'ALL' && selectedStationIds.length === 0)}
            >
              {downloading ? (
                <>
                  <Loader2 size={15} className="spin" />
                  <span>Memproses Ekspor...</span>
                </>
              ) : (
                <>
                  <Download size={15} />
                  <span>Unduh Data ({fileFormat.toUpperCase()})</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
