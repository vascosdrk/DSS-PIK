import React, { useState } from 'react';
import { 
  Droplets, 
  Activity, 
  Percent, 
  Download, 
  Info, 
  FileSpreadsheet,
  Database,
  UploadCloud,
  ShieldAlert,
  CloudRain
} from 'lucide-react';
import DailyRainfallTable from './DailyRainfallTable';
import SpiDataTable from './SpiDataTable';
import ProbabilityDataTable from './ProbabilityDataTable';
import DeterministicForecastTable from './DeterministicForecastTable';
import StationInfoModal from './StationInfoModal';
import DataDownloadModal from './DataDownloadModal';
import DataIngestionModal from './DataIngestionModal';
import EcmwfForecastInputModal from './EcmwfForecastInputModal';
import RainfallInputModal from './RainfallInputModal';
import SpiGeneratorModal from './SpiGeneratorModal';
import OperationalDataManager from './OperationalDataManager';
import ErrorBoundary from './ErrorBoundary';

export default function DataCenter({ initialSubTab = 'rainfall', activePeriodId = '2026-09-das2', onDataIngestionCommitted }) {
  const [activeSubTab, setActiveSubTab] = useState(initialSubTab); // 'rainfall' | 'spi' | 'probability' | 'management'
  // 2-Level Forecast Hierarchy: Level 1 = Resolusi (DASARIAN | BULANAN), Level 2 = Jenis Data (PROBABILITAS | DETERMINISTIK)
  const [forecastResolution, setForecastResolution] = useState(
    activePeriodId && !activePeriodId.includes('das') ? 'BULANAN' : 'DASARIAN'
  );
  const [forecastDataType, setForecastDataType] = useState('PROBABILITAS');
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [showIngestionModal, setShowIngestionModal] = useState(false);
  const [showEcmwfModal, setShowEcmwfModal] = useState(false);
  const [ecmwfModalResolution, setEcmwfModalResolution] = useState('DASARIAN');
  const [showRainfallInputModal, setShowRainfallInputModal] = useState(false);
  const [showGeneratorModal, setShowGeneratorModal] = useState(false);
  const [generatorContext, setGeneratorContext] = useState({ resolution: 'DASARIAN', timescale: 30 });
  const [spiRefreshTrigger, setSpiRefreshTrigger] = useState(0);
  const [ingestionCategory, setIngestionCategory] = useState('AUTO_DETECT');
  const [managementInitialTab, setManagementInitialTab] = useState('STORAGE');
  const [managementCorrectionFilter, setManagementCorrectionFilter] = useState('ALL');
  const [refreshKey, setRefreshKey] = useState(0);
  const [downloadModalContext, setDownloadModalContext] = useState({ type: 'RAINFALL', params: {} });
  const [selectedStationForInfo, setSelectedStationForInfo] = useState('21010401a');

  const handleOpenDownload = (category = 'RAINFALL', params = {}) => {
    setDownloadModalContext({ type: category, params });
    setShowDownloadModal(true);
  };

  const handleOpenInfo = (stationId = '21010401a') => {
    setSelectedStationForInfo(stationId);
    setShowInfoModal(true);
  };

  const handleOpenIngestion = (category = 'AUTO_DETECT') => {
    if (category === 'CURAH_HUJAN') {
      setShowRainfallInputModal(true);
      return;
    }
    if (category === 'PROBABILITAS_DASARIAN' || category === 'PROBABILITAS_BULANAN') {
      setEcmwfModalResolution(category === 'PROBABILITAS_BULANAN' ? 'BULANAN' : 'DASARIAN');
      setShowEcmwfModal(true);
      return;
    }
    setIngestionCategory(category);
    setShowIngestionModal(true);
  };

  const handleOpenGenerator = (resType, ts) => {
    const rawRes = String(resType || 'DASARIAN').trim().toUpperCase();
    const mappedRes = rawRes === 'DAILY' || rawRes === 'HARIAN'
      ? 'HARIAN'
      : rawRes === 'BULANAN'
        ? 'BULANAN'
        : 'DASARIAN';
    const rawTs = String(ts || '30').trim().toUpperCase();
    const mappedTs = rawTs.includes('90') ? 90 : 30;
    setGeneratorContext({ resolution: mappedRes, timescale: mappedTs });
    setShowGeneratorModal(true);
  };

  const handleOpenManagement = (tab = 'STORAGE', correctionDataset = 'ALL') => {
    setManagementInitialTab(tab);
    setManagementCorrectionFilter(correctionDataset || 'ALL');
    setActiveSubTab('management');
  };

  return (
    <div className="data-center-wrapper">
      {/* 1. Data Center Header & Submenu Navigation */}
      <div className="data-center-nav-header">
        <div className="data-center-brand-group">
          <div className="data-center-title-row">
            <Database size={20} className="text-forest" />
            <h2 className="data-center-heading">Pusat Data DSS-PIK</h2>
            <span className="badge-dataset-count">57 Stasiun Master Kepri</span>
          </div>
          <p className="data-center-subheading">
            Akses terpadu observasi curah hujan harian (MariaDB), 5 skala SPI (Parquet), serta multi-vintage prakiraan probabilistik (%) dan deterministik (mm) ECMWF
          </p>
        </div>

        <div className="data-center-actions-right">
          <button
            type="button"
            className="btn-action-info-pos"
            onClick={() => handleOpenInfo(selectedStationForInfo)}
            title="Buka profil dan metadata lengkap 57 pos pengamatan master"
          >
            <Info size={15} />
            <span>Informasi Pos</span>
          </button>

          <button
            type="button"
            className="btn-action-download-global"
            onClick={() => handleOpenDownload(
              activeSubTab === 'rainfall'
                ? 'RAINFALL'
                : activeSubTab === 'spi'
                  ? 'SPI'
                  : 'ECMWF',
              activeSubTab === 'probability'
                ? { ecmwfResolution: forecastResolution, ecmwfDataType: forecastDataType }
                : {}
            )}
            title="Buka Pusat Unduh Data DSS-PIK (Curah Hujan, SPI, Prakiraan ECMWF)"
          >
            <Download size={15} />
            <span>Pusat Unduh Data</span>
          </button>
        </div>
      </div>

      {/* 2. Sub-Tab Switcher */}
      <div className="data-subtabs-bar" role="tablist">
        <button
          type="button"
          className={`data-subtab-btn ${activeSubTab === 'rainfall' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('rainfall')}
          role="tab"
          aria-selected={activeSubTab === 'rainfall'}
        >
          <Droplets size={16} />
          <span>Data Curah Hujan</span>
        </button>

        <button
          type="button"
          className={`data-subtab-btn ${activeSubTab === 'spi' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('spi')}
          role="tab"
          aria-selected={activeSubTab === 'spi'}
        >
          <Activity size={16} />
          <span>Data SPI</span>
        </button>

        <button
          type="button"
          className={`data-subtab-btn ${activeSubTab === 'probability' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('probability')}
          role="tab"
          aria-selected={activeSubTab === 'probability'}
        >
          <Percent size={16} />
          <span>Data Probabilitas &amp; Deterministik</span>
        </button>

        <button
          type="button"
          className={`data-subtab-btn ${activeSubTab === 'management' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('management')}
          role="tab"
          aria-selected={activeSubTab === 'management'}
        >
          <Database size={16} />
          <span>Manajemen Data Operasional</span>
        </button>
      </div>

      {/* 3. Sub-Tab View Content */}
      <div className="data-subtab-content">
        {activeSubTab === 'rainfall' && (
          <div className="data-panel-fade-in">
            <DailyRainfallTable
              key={`rainfall-${refreshKey}`}
              onOpenInfo={(stnId) => handleOpenInfo(stnId)}
              onOpenDownload={handleOpenDownload}
              onOpenIngestion={handleOpenIngestion}
              onOpenManagement={handleOpenManagement}
            />
          </div>
        )}

        {activeSubTab === 'spi' && (
          <div className="data-panel-fade-in">
            <SpiDataTable
              refreshTrigger={spiRefreshTrigger}
              onOpenDownload={handleOpenDownload}
              onOpenIngestion={handleOpenIngestion}
              onOpenManagement={handleOpenManagement}
              onOpenGenerator={handleOpenGenerator}
            />
          </div>
        )}

        {activeSubTab === 'probability' && (
          <div className="data-panel-fade-in ecmwf-hub-stack">
            {/* 1. Unified Page Header: Data Probabilitas & Deterministik */}
            <div className="prob-v2-header">
              <div className="prob-v2-title-group">
                <div className="prob-v2-icon-box">
                  {forecastDataType === 'DETERMINISTIK' ? <CloudRain size={20} /> : <Percent size={20} />}
                </div>
                <div>
                  <div className="prob-v2-title-row">
                    <h2 className="prob-v2-title">Data Probabilitas &amp; Deterministik</h2>
                    <span className="prob-v2-res-pill">{forecastResolution}</span>
                    <span className="prob-v2-res-pill">
                      {forecastDataType === 'DETERMINISTIK' ? 'DETERMINISTIK (MM)' : 'PROBABILITAS (%)'}
                    </span>
                  </div>
                  <p className="prob-v2-desc">
                    Pengelolaan multi-vintage prakiraan probabilistik (%) dan deterministik (mm) ECMWF untuk 57 pos pengamatan Kepulauan Riau.
                  </p>
                </div>
              </div>

              <div className="prob-v2-header-right">
                <div className="prob-v2-actions">
                  <button
                    type="button"
                    className="prob-v2-btn-primary"
                    onClick={() => handleOpenIngestion('PROBABILITAS_DASARIAN')}
                    title="Unggah workbook ECMWF (pilih resolusi Dasarian atau Bulanan di dalam popup)"
                  >
                    <UploadCloud size={15} />
                    <span>Input / Pembaruan Data</span>
                  </button>

                  <button
                    type="button"
                    className="prob-v2-btn-secondary"
                    onClick={() =>
                      handleOpenManagement(
                        'CORRECTIONS',
                        forecastDataType === 'DETERMINISTIK' ? 'ENSMEAN' : 'PROBABILITAS'
                      )
                    }
                    title="Buka panel Kelola Vintage ECMWF (Pembatalan & Aktifkan Kembali Vintage)"
                  >
                    <ShieldAlert size={14} className="text-rose-600" />
                    <span>Kelola Vintage</span>
                  </button>
                </div>
              </div>
            </div>

            {/* 2. Two-Level Primary Filter Hierarchy: Level 1 Resolusi -> Level 2 Jenis Data */}
            <div className="ecmwf-hierarchy-card">
              <div className="ecmwf-hierarchy-levels">
                {/* TINGKAT 1 — RESOLUSI PRAKIRAAN */}
                <div className="ecmwf-level-group">
                  <span className="ecmwf-level-label">Resolusi Prakiraan</span>
                  <div className="ecmwf-level-seg" role="group" aria-label="Resolusi Prakiraan">
                    <button
                      type="button"
                      className={`ecmwf-level-btn ${forecastResolution === 'DASARIAN' ? 'active' : ''}`}
                      onClick={() => setForecastResolution('DASARIAN')}
                      aria-pressed={forecastResolution === 'DASARIAN'}
                    >
                      <span>Dasarian</span>
                    </button>
                    <button
                      type="button"
                      className={`ecmwf-level-btn ${forecastResolution === 'BULANAN' ? 'active' : ''}`}
                      onClick={() => setForecastResolution('BULANAN')}
                      aria-pressed={forecastResolution === 'BULANAN'}
                    >
                      <span>Bulanan</span>
                    </button>
                  </div>
                </div>

                <div className="ecmwf-level-divider" aria-hidden="true" />

                {/* TINGKAT 2 — JENIS DATA */}
                <div className="ecmwf-level-group">
                  <span className="ecmwf-level-label">Jenis Data</span>
                  <div className="ecmwf-level-seg" role="tablist" aria-label="Jenis Data Prakiraan">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={forecastDataType === 'PROBABILITAS'}
                      className={`ecmwf-level-btn ${forecastDataType === 'PROBABILITAS' ? 'active' : ''}`}
                      onClick={() => setForecastDataType('PROBABILITAS')}
                    >
                      <span>Probabilitas</span>
                      <span className="ecmwf-level-unit">%</span>
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={forecastDataType === 'DETERMINISTIK'}
                      className={`ecmwf-level-btn ${forecastDataType === 'DETERMINISTIK' ? 'active' : ''}`}
                      onClick={() => setForecastDataType('DETERMINISTIK')}
                    >
                      <span>Deterministik</span>
                      <span className="ecmwf-level-unit">mm</span>
                    </button>
                  </div>
                </div>
              </div>

              <div className="prob-v2-count-summary">
                Mode aktif:{' '}
                <strong>
                  {forecastDataType === 'DETERMINISTIK' ? 'Deterministik' : 'Probabilitas'}{' '}
                  {forecastResolution === 'BULANAN' ? 'Bulanan' : 'Dasarian'}
                </strong>
              </div>
            </div>

            {/* 3. Active Table View (Strictly Isolated by Jenis Data, Synchronized to Resolusi) */}
            {forecastDataType === 'PROBABILITAS' ? (
              <ProbabilityDataTable
                key={`prob-${refreshKey}`}
                activePeriodId={activePeriodId}
                externalResolutionMode={forecastResolution}
                embeddedMode={true}
                onOpenDownload={handleOpenDownload}
                onOpenIngestion={handleOpenIngestion}
                onOpenManagement={handleOpenManagement}
              />
            ) : (
              <DeterministicForecastTable
                key={`det-${refreshKey}`}
                resolutionMode={forecastResolution}
                embeddedMode={true}
                onOpenIngestion={handleOpenIngestion}
                onOpenManagement={handleOpenManagement}
              />
            )}
          </div>
        )}

        {activeSubTab === 'management' && (
          <div className="data-panel-fade-in">
            <OperationalDataManager
              key={`mgmt-${refreshKey}-${managementInitialTab}-${managementCorrectionFilter}`}
              initialTab={managementInitialTab}
              initialCorrectionDataset={managementCorrectionFilter}
            />
          </div>
        )}
      </div>

      {/* 4. Modals with Error Boundary Protection */}
      <ErrorBoundary name="Informasi Pos Pengamatan">
        <StationInfoModal
          isOpen={showInfoModal}
          onClose={() => setShowInfoModal(false)}
          initialStationId={selectedStationForInfo}
        />
      </ErrorBoundary>

      <ErrorBoundary name="Unduh Data Resmi">
        <DataDownloadModal
          isOpen={showDownloadModal}
          onClose={() => setShowDownloadModal(false)}
          initialDataType={downloadModalContext.type}
          initialParams={downloadModalContext.params}
        />
      </ErrorBoundary>

      <ErrorBoundary name="Pusat Input & Pembaruan Data Operasional">
        <DataIngestionModal
          isOpen={showIngestionModal}
          onClose={() => setShowIngestionModal(false)}
          initialDatasetType={ingestionCategory}
          onOpenManagement={(tab) => {
            setShowIngestionModal(false);
            handleOpenManagement(tab);
          }}
          onIngestionSuccess={(res) => {
            setRefreshKey((prev) => prev + 1);
            setSpiRefreshTrigger((prev) => prev + 1);
            if (onDataIngestionCommitted) {
              onDataIngestionCommitted(res);
            }
          }}
        />
      </ErrorBoundary>

      <ErrorBoundary name="Input Data Prakiraan ECMWF">
        <EcmwfForecastInputModal
          isOpen={showEcmwfModal}
          onClose={() => setShowEcmwfModal(false)}
          onOpenManagement={(tab) => {
            setShowEcmwfModal(false);
            handleOpenManagement(tab);
          }}
          onSuccess={(res) => {
            setRefreshKey((prev) => prev + 1);
            if (onDataIngestionCommitted) {
              onDataIngestionCommitted(res);
            }
          }}
        />
      </ErrorBoundary>

      <ErrorBoundary name="Input Data Curah Hujan">
        <RainfallInputModal
          isOpen={showRainfallInputModal}
          onClose={() => setShowRainfallInputModal(false)}
          onSuccess={(res) => {
            setRefreshKey((prev) => prev + 1);
            if (onDataIngestionCommitted) {
              onDataIngestionCommitted(res);
            }
          }}
        />
      </ErrorBoundary>

      <ErrorBoundary name="Generator Nilai SPI (Manual SPI Generator)">
        <SpiGeneratorModal
          isOpen={showGeneratorModal}
          onClose={() => setShowGeneratorModal(false)}
          initialResolution={generatorContext.resolution}
          initialTimescale={generatorContext.timescale}
          onGenerationSuccess={(data) => {
            setSpiRefreshTrigger((prev) => prev + 1);
            if (onDataIngestionCommitted) {
              onDataIngestionCommitted({ data_type: 'SPI_GENERATOR', data });
            }
          }}
        />
      </ErrorBoundary>
    </div>
  );
}
