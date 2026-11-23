import React from 'react';
import { Map, Table, RotateCcw, Search, MapPin, AlertCircle } from 'lucide-react';

export default function FilterBar({
  currentView,
  onViewChange,
  kabupatenList,
  selectedKabupaten,
  onSelectKabupaten,
  selectedWarningLevel,
  onSelectWarningLevel,
  searchQuery,
  onSearchChange,
  onResetFilters,
  totalCount,
  filteredCount,
}) {
  const isFiltered =
    selectedKabupaten !== 'ALL' ||
    selectedWarningLevel !== 'ALL' ||
    searchQuery.trim() !== '';

  return (
    <div className="filter-bar">
      <div className="filter-controls-group">
        {/* Segmented Switch PETA / TABEL HTH */}
        <div className="view-switch-box" role="group" aria-label="Mode Tampilan">
          <button
            type="button"
            className={`btn-view-pill ${currentView === 'map' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('map')}
            title="Tampilan Peta Interaktif"
          >
            <Map size={14} />
            <span>PETA</span>
          </button>
          <button
            type="button"
            className={`btn-view-pill ${currentView === 'hth' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('hth')}
            title="Tampilan Tabel Peringatan Dini Lengkap"
          >
            <Table size={14} />
            <span>TABEL PERINGATAN DINI</span>
          </button>
        </div>

        {/* Kabupaten Filter */}
        <div className="filter-item">
          <label htmlFor="kabupaten-select" className="filter-label">
            <MapPin size={12} />
            <span>Kabupaten / Kota</span>
          </label>
          <select
            id="kabupaten-select"
            className="filter-select"
            value={selectedKabupaten}
            onChange={(e) => onSelectKabupaten(e.target.value)}
          >
            <option value="ALL">Semua Wilayah ({kabupatenList.length} Kab/Kota)</option>
            {kabupatenList.map((kab) => (
              <option key={kab} value={kab}>
                {kab}
              </option>
            ))}
          </select>
        </div>

        {/* Warning Level Filter */}
        <div className="filter-item">
          <label htmlFor="warning-select" className="filter-label">
            <AlertCircle size={12} />
            <span>Status Peringatan</span>
          </label>
          <select
            id="warning-select"
            className="filter-select"
            value={selectedWarningLevel}
            onChange={(e) => onSelectWarningLevel(e.target.value)}
          >
            <option value="ALL">Semua Status Peringatan</option>
            <option value="NORMAL">NORMAL / AMAN</option>
            <option value="WASPADA">WASPADA (Kuning)</option>
            <option value="SIAGA">SIAGA (Oranye)</option>
            <option value="AWAS">AWAS (Merah)</option>
            <option value="INCOMPLETE">EVALUASI TIDAK LENGKAP</option>
          </select>
        </div>

        {/* Search Input */}
        <div className="filter-item search-item">
          <label htmlFor="search-input" className="filter-label">
            <Search size={12} />
            <span>Cari Stasiun</span>
          </label>
          <div className="search-input-wrapper">
            <input
              id="search-input"
              type="text"
              placeholder="Nama stasiun, ID, atau wilayah..."
              className="filter-input"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
            />
            {searchQuery && (
              <button
                className="btn-clear-search"
                onClick={() => onSearchChange('')}
                title="Hapus pencarian"
              >
                &times;
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="filter-meta-group">
        <div className="filter-counter">
          Menampilkan <strong>{filteredCount}</strong> dari <strong>{totalCount}</strong> stasiun
        </div>

        {isFiltered && (
          <button
            className="btn-reset-filter"
            onClick={onResetFilters}
            title="Reset semua filter"
          >
            <RotateCcw size={13} />
            <span>Reset</span>
          </button>
        )}
      </div>
    </div>
  );
}
