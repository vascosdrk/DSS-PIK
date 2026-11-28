import React from 'react';
import { RefreshCw, Activity, MapPin, ShieldAlert, Database, BookOpen, User, LogOut } from 'lucide-react';
import { INSTITUTION_SHORT_NAME } from '../config';

export default function Header({
  onRefresh,
  loading,
  totalStations,
  lastUpdated,
  activeTab = 'dashboard',
  onSelectTab,
  currentUser,
  onLogout,
}) {
  const formatTime = (isoStr) => {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('id-ID', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short',
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <header className="header-container">
      <div className="header-left">
        <div className="header-brand-block">
          <div className="header-wordmark-container">
            <img
              src="/dss_pik_shield_white_line_transparent.png"
              alt="Logo DSS-PIK"
              className="bmkg-header-logo"
            />
            <div>
              <div className="header-title-row">
                <span className="header-brand-title">
                  <em>Decision Support System</em> - Peringatan Iklim Kepri
                </span>
              </div>
              <p className="header-subtitle">
                Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
              </p>
            </div>
          </div>
        </div>

        {/* Primary Navigation Menu */}
        <nav className="header-nav-tabs" role="tablist">
          <button
            className={`header-nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => onSelectTab && onSelectTab('dashboard')}
            role="tab"
            aria-selected={activeTab === 'dashboard'}
          >
            <ShieldAlert size={15} />
            <span>Peringatan Dini</span>
          </button>
          <button
            className={`header-nav-tab ${activeTab === 'data' || activeTab === 'rainfall-table' ? 'active' : ''}`}
            onClick={() => onSelectTab && onSelectTab('data')}
            role="tab"
            aria-selected={activeTab === 'data' || activeTab === 'rainfall-table'}
          >
            <Database size={15} />
            <span>Data Center</span>
          </button>
          <button
            className={`header-nav-tab ${activeTab === 'kamus' ? 'active' : ''}`}
            onClick={() => onSelectTab && onSelectTab('kamus')}
            role="tab"
            aria-selected={activeTab === 'kamus'}
          >
            <BookOpen size={15} />
            <span>Kamus</span>
          </button>
        </nav>
      </div>

      <div className="header-right">
        <div className="header-meta-item">
          <span className="meta-label">Cakupan Wilayah</span>
          <span className="meta-value font-mono">
            <MapPin size={13} className="meta-icon" /> Kepulauan Riau ({totalStations || 57} Titik)
          </span>
        </div>

        <div className="header-meta-item">
          <span className="meta-label">Pembaruan Sistem</span>
          <span className="meta-value font-mono">
            <Activity size={13} className="meta-icon" /> {formatTime(lastUpdated)}
          </span>
        </div>

        {currentUser && (
          <div className="operator-badge-pill" title="Operator yang sedang bertugas">
            <User size={13} />
            <span className="font-mono">{currentUser.username || 'klimatkepri'}</span>
          </div>
        )}

        <button
          className="btn-refresh"
          onClick={onRefresh}
          disabled={loading}
          title="Segarkan dan evaluasi ulang seluruh data operasional (CH, SPI, Probabilitas) serta Decision Engine"
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
          <span>{loading ? 'Mengevaluasi…' : 'Segarkan & Evaluasi'}</span>
        </button>

        {onLogout && (
          <button
            className="btn-logout"
            onClick={onLogout}
            title="Keluar dari sistem DSS-PIK"
          >
            <LogOut size={13} />
            <span>Keluar</span>
          </button>
        )}
      </div>
    </header>
  );
}
