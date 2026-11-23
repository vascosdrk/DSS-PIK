import React, { useState } from 'react';
import { 
  Droplets, 
  Activity, 
  Percent, 
  Download, 
  Info, 
  FileSpreadsheet,
  Database,
  UploadCloud
} from 'lucide-react';
import DailyRainfallTable from './DailyRainfallTable';
import SpiDataTable from './SpiDataTable';
import ProbabilityDataTable from './ProbabilityDataTable';
import StationInfoModal from './StationInfoModal';
import DataDownloadModal from './DataDownloadModal';
import DataIngestionModal from './DataIngestionModal';
import SpiGeneratorModal from './SpiGeneratorModal';
import OperationalDataManager from './OperationalDataManager';
import ErrorBoundary from './ErrorBoundary';

export default function DataCenter({ initialSubTab = 'rainfall', activePeriodId = '2026-09-das2', onDataIngestionCommitted }) {
  const [activeSubTab, setActiveSubTab] = useState(initialSubTab); // 'rainfall' | 'spi' | 'probability' | 'management'
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [showIngestionModal, setShowIngestionModal] = useState(false);
  const [showGeneratorModal, setShowGeneratorModal] = useState(false);
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
    setIngestionCategory(category);
    setShowIngestionModal(true);
  };

  const handleOpenGenerator = (resType, ts) => {
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
            Akses terpadu terhadap observasi curah hujan harian (MariaDB), 5 skala SPI (Parquet), dan multi-vintage prakiraan probabilitas iklim ECMWF
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
              activeSubTab === 'rainfall' ? 'RAINFALL' : activeSubTab === 'spi' ? 'SPI' : 'PROBABILITY'
            )}
            title="Buka pusat unduhan resmi lintas dataset (CH, SPI, Probabilitas)"
          >
            <Download size={15} />
            <span>Unduh Semua Dataset</span>
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
          <span>Data Probabilitas</span>
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
              key={`spi-${refreshKey}`}
              onOpenDownload={handleOpenDownload}
              onOpenIngestion={handleOpenIngestion}
              onOpenManagement={handleOpenManagement}
              onOpenGenerator={handleOpenGenerator}
            />
          </div>
        )}

        {activeSubTab === 'probability' && (
          <div className="data-panel-fade-in">
            <ProbabilityDataTable
              key={`prob-${refreshKey}`}
              activePeriodId={activePeriodId}
              onOpenDownload={handleOpenDownload}
              onOpenIngestion={handleOpenIngestion}
              onOpenManagement={handleOpenManagement}
            />
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
          onGenerationSuccess={(data) => {
            setRefreshKey((prev) => prev + 1);
            if (onDataIngestionCommitted) {
              onDataIngestionCommitted({ data_type: 'SPI_GENERATOR', data });
            }
          }}
        />
      </ErrorBoundary>
    </div>
  );
}
