import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Header from './components/Header';
import SimulationBanner from './components/SimulationBanner';
import KpiCards from './components/KpiCards';
import FilterBar from './components/FilterBar';
import MapLeaflet from './components/MapLeaflet';
import HthTable from './components/HthTable';
import StationDetailDrawer from './components/StationDetailDrawer';
import DailyRainfallTable from './components/DailyRainfallTable';
import DataCenter from './components/DataCenter';
import KamusPage from './components/KamusPage';
import LoginPage from './components/LoginPage';
import OfficialMapModal from './components/OfficialMapModal';
import ErrorBoundary from './components/ErrorBoundary';
import { API_ENDPOINTS, INSTITUTION_SHORT_NAME, authFetch, setStoredAuthToken, getStoredAuthToken } from './config';
import { ServerOff, RefreshCw, AlertTriangle, Flame, ShieldAlert, ChevronRight, Eye, CheckCircle2, Database } from 'lucide-react';

export default function App() {
  // Authentication State
  const [currentUser, setCurrentUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);

  const [stations, setStations] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Connection and UX Opening States
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // 'connecting' | 'ready' | 'error'
  const [connectionStepText, setConnectionStepText] = useState('Menghubungkan ke layanan DSS-PIK...');
  const [connectionDetailText, setConnectionDetailText] = useState('Memeriksa backend API dan basis data...');
  const [connectionDiagnostics, setConnectionDiagnostics] = useState(null);
  const [connectionStepNum, setConnectionStepNum] = useState(1);

  // Multi-Period State (10 Dasarians) & Readiness
  const [periods, setPeriods] = useState([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState('2026-09-das2');
  const [readinessInfo, setReadinessInfo] = useState(null);
  const [periodMode, setPeriodMode] = useState('auto');
  const [serverTime, setServerTime] = useState(null);

  // Official Map Modal State
  const [officialMapModalOpen, setOfficialMapModalOpen] = useState(false);
  const [officialMapType, setOfficialMapType] = useState('PDKM');

  // Navigation Tab: 'dashboard' | 'rainfall-table'
  const [activeTab, setActiveTab] = useState('dashboard');

  // View Mode: 'map' | 'hth'
  const [currentView, setCurrentView] = useState('map');

  // Filters
  const [selectedKabupaten, setSelectedKabupaten] = useState('ALL');
  const [selectedWarningLevel, setSelectedWarningLevel] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [mapFocusTrigger, setMapFocusTrigger] = useState(0);

  // Selected Station for Detail Drawer
  const [selectedStationId, setSelectedStationId] = useState(null);
  const [activeHazardTab, setActiveHazardTab] = useState('PDKM'); // 'PDKM' | 'PDCHT'

  // 0. Verify active session on mount with resilient retry
  useEffect(() => {
    let isMounted = true;
    let cancelled = false;

    const checkSession = async (attempt = 1) => {
      try {
        const res = await authFetch(API_ENDPOINTS.AUTH_ME);
        if (res.status === 401) {
          // Explicitly unauthorized: wipe token and show login
          if (isMounted) {
            setStoredAuthToken(null);
            setCurrentUser(null);
            setAuthChecking(false);
          }
          return;
        }
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        if (isMounted) {
          if (data && data.authenticated) {
            if (data.token) setStoredAuthToken(data.token);
            setCurrentUser(data);
          } else {
            setStoredAuthToken(null);
            setCurrentUser(null);
          }
          setAuthChecking(false);
        }
      } catch (err) {
        console.warn(`[DSS-PIK] Session verification attempt ${attempt} failed:`, err);
        const token = getStoredAuthToken();
        // If there is a stored token and we've retried fewer than 3 times, retry
        if (token && attempt < 3 && !cancelled) {
          setTimeout(() => {
            if (!cancelled && isMounted) checkSession(attempt + 1);
          }, 1200);
        } else {
          // Either no stored token, or attempts exhausted
          if (isMounted) {
            if (!token) {
              setCurrentUser(null);
            }
            setAuthChecking(false);
          }
        }
      }
    };

    checkSession(1);

    return () => {
      isMounted = false;
      cancelled = true;
    };
  }, []);

  const fetchReadiness = useCallback((periodId) => {
    authFetch(API_ENDPOINTS.PERIOD_READINESS(periodId))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.active_period_id) {
          setReadinessInfo(data);
        }
      })
      .catch((err) => console.warn('Failed to fetch period readiness:', err));
  }, []);

  // 1. Fetch available periods on initial load when authenticated
  useEffect(() => {
    if (!currentUser) return;
    let isMounted = true;
    authFetch(API_ENDPOINTS.PERIODS)
      .then((res) => {
        if (res.status === 401) {
          setStoredAuthToken(null);
          setCurrentUser(null);
          return null;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat daftar periode`);
        return res.json();
      })
      .then((data) => {
        if (isMounted && data && Array.isArray(data.periods)) {
          setPeriods(data.periods);
          if (data.active_period_id) {
            setSelectedPeriodId(data.active_period_id);
            fetchReadiness(data.active_period_id);
          }
          if (data.mode) {
            setPeriodMode(data.mode);
          }
          if (data.server_time) {
            setServerTime(data.server_time);
          }
        }
      })
      .catch((err) => {
        console.warn('Failed to load periods manifest:', err);
      });

    return () => {
      isMounted = false;
    };
  }, [currentUser, fetchReadiness]);

  // 2. Fetch enriched warning & HTH data for the selected period with graceful opening UX
  const fetchData = useCallback(async (periodId = selectedPeriodId, isManualRetry = false) => {
    if (!currentUser) return;
    setLoading(true);
    setError(null);
    setConnectionStatus('connecting');

    const maxRetries = isManualRetry ? 3 : 2;
    let attempt = 0;
    let success = false;
    let lastError = null;

    while (attempt <= maxRetries && !success) {
      if (attempt > 0) {
        setConnectionStepNum(1);
        setConnectionStepText(`Menghubungkan ulang ke layanan DSS-PIK (Percobaan ${attempt}/${maxRetries})...`);
        setConnectionDetailText('Memeriksa kesiapan layanan Backend API dan basis data...');
        await new Promise((r) => setTimeout(r, 1200));
      } else {
        setConnectionStepNum(1);
        setConnectionStepText('Menghubungkan ke layanan DSS-PIK...');
        setConnectionDetailText('Memeriksa backend API dan basis data...');
      }

      try {
        setConnectionStepNum(2);
        setConnectionDetailText('Memeriksa kesiapan basis data dan status layanan...');

        // Fetch period snapshot data
        setConnectionStepNum(3);
        setConnectionDetailText('Memuat data indikator dan status peringatan dini dasarian...');
        const res = await authFetch(API_ENDPOINTS.HTH_TABLE(periodId));

        if (res.status === 401) {
          setStoredAuthToken(null);
          setCurrentUser(null);
          return;
        }

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: Server merespons dengan status ${res.status}`);
        }

        const json = await res.json();
        setStations(json.data || []);
        setMeta(json.meta || null);
        success = true;
        setConnectionStatus('ready');
        setError(null);
        setConnectionDiagnostics(null);
        break;
      } catch (err) {
        console.warn(`[DSS-PIK] Fetch data attempt ${attempt + 1} failed:`, err);
        lastError = err;
        attempt++;
      }
    }

    if (!success) {
      // Gather diagnostic info from /health
      let healthData = null;
      try {
        const healthRes = await fetch(API_ENDPOINTS.HEALTH, { cache: 'no-cache' });
        if (healthRes.ok) {
          healthData = await healthRes.json();
        }
      } catch (e) {
        // backend completely unreachable
      }

      setConnectionStatus('error');
      setConnectionDiagnostics({
        apiUrl: API_ENDPOINTS.HEALTH.replace('/health', ''),
        apiStatus: healthData ? 'Aktif (HTTP 200)' : 'Tidak Merespons / Offline',
        dbStatus: healthData && healthData.database === 'connected' ? 'Terhubung' : 'Belum Siap / Terputus',
        authStatus: currentUser ? 'Sesi Operator Terdaftar' : 'Sesi Kedaluwarsa',
        detail: lastError ? lastError.message : 'Koneksi ke backend API terputus atau melebihi batas waktu.'
      });
      setError('Data DSS-PIK tidak dapat dimuat. Pastikan Backend API aktif.');
    }

    setLoading(false);
  }, [selectedPeriodId, currentUser]);

  useEffect(() => {
    if (currentUser) {
      fetchData(selectedPeriodId);
    }
  }, [selectedPeriodId, currentUser]);

  const handleLogout = async () => {
    try {
      await authFetch(API_ENDPOINTS.LOGOUT, {
        method: 'POST',
      });
    } catch (e) {
      console.warn('Logout error:', e);
    }
    setStoredAuthToken(null);
    setCurrentUser(null);
  };

  const handleSelectPeriod = async (newPid) => {
    if (!newPid) return;
    try {
      setLoading(true);
      const res = await authFetch(API_ENDPOINTS.PERIOD_SELECT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'manual', period_id: newPid }),
      });
      if (res.ok) {
        const data = await res.json();
        setPeriods(data.periods);
        setSelectedPeriodId(data.active_period_id);
        setPeriodMode(data.mode);
        setServerTime(data.server_time);
        fetchReadiness(data.active_period_id);
      } else {
        setSelectedPeriodId(newPid);
        fetchReadiness(newPid);
      }
    } catch (err) {
      console.warn('Failed to persist manual period to server:', err);
      setSelectedPeriodId(newPid);
      fetchReadiness(newPid);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshAndEvaluate = async () => {
    if (loading) return;
    try {
      setLoading(true);
      // 1. Call server refresh & evaluate endpoint
      const refreshRes = await authFetch(API_ENDPOINTS.WARNINGS_REFRESH_EVALUATE(selectedPeriodId), {
        method: 'POST',
      });
      if (refreshRes.status === 401) {
        setStoredAuthToken(null);
        setCurrentUser(null);
        return;
      }
      // 2. Fetch fresh period table & readiness
      await fetchData(selectedPeriodId);
      if (selectedPeriodId) {
        fetchReadiness(selectedPeriodId);
      }
      setLastUpdated(new Date().toISOString());
    } catch (err) {
      console.error('[DSS-PIK] Segarkan & Evaluasi gagal:', err);
      // Fallback normal fetch
      await fetchData(selectedPeriodId);
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchToRealtime = async () => {
    try {
      setLoading(true);
      const res = await authFetch(API_ENDPOINTS.PERIOD_SELECT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'auto' }),
      });
      if (res.ok) {
        const data = await res.json();
        setPeriods(data.periods);
        setSelectedPeriodId(data.active_period_id);
        setPeriodMode(data.mode);
        setServerTime(data.server_time);
        fetchReadiness(data.active_period_id);
      }
    } catch (err) {
      console.warn('Failed to revert to realtime period on server:', err);
    } finally {
      setLoading(false);
    }
  };

  // Derive unique Kabupaten list from actual data
  const kabupatenList = useMemo(() => {
    const set = new Set();
    stations.forEach((s) => {
      if (s.kabupaten) set.add(s.kabupaten);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'id'));
  }, [stations]);

  // Compute Warning Level Distribution Counts (Unified, PDKM, PDCHT)
  const counts = useMemo(() => {
    const c = { total: stations.length, NORMAL: 0, WASPADA: 0, SIAGA: 0, AWAS: 0, INCOMPLETE: 0 };
    stations.forEach((s) => {
      const raw = (s.warning_level || 'NORMAL').toUpperCase();
      if (raw === 'INCOMPLETE' || s.evaluation_status === 'INCOMPLETE') {
        c.INCOMPLETE += 1;
      } else {
        let lvl = 'NORMAL';
        if (raw.includes('AWAS')) lvl = 'AWAS';
        else if (raw.includes('SIAGA')) lvl = 'SIAGA';
        else if (raw.includes('WASPADA')) lvl = 'WASPADA';

        if (c[lvl] !== undefined) {
          c[lvl] += 1;
        }
      }
    });
    return c;
  }, [stations]);

  const pdkmCounts = useMemo(() => {
    const c = { total: stations.length, AMAN: 0, WASPADA: 0, SIAGA: 0, AWAS: 0, INSUFFICIENT: 0 };
    stations.forEach((s) => {
      const raw = (s.pdkm_status || 'NORMAL').toUpperCase();
      if (raw === 'INCOMPLETE' || raw === 'INSUFFICIENT_DATA') {
        c.INSUFFICIENT += 1;
      } else if (raw === 'AWAS') {
        c.AWAS += 1;
      } else if (raw === 'SIAGA') {
        c.SIAGA += 1;
      } else if (raw === 'WASPADA') {
        c.WASPADA += 1;
      } else {
        c.AMAN += 1;
      }
    });
    return c;
  }, [stations]);

  const pdchtCounts = useMemo(() => {
    const c = { total: stations.length, AMAN: 0, WASPADA: 0, SIAGA: 0, AWAS: 0, INSUFFICIENT: 0 };
    stations.forEach((s) => {
      const raw = (s.pdcht_status || 'NORMAL').toUpperCase();
      if (raw === 'INCOMPLETE' || raw === 'INSUFFICIENT_DATA') {
        c.INSUFFICIENT += 1;
      } else if (raw === 'AWAS') {
        c.AWAS += 1;
      } else if (raw === 'SIAGA') {
        c.SIAGA += 1;
      } else if (raw === 'WASPADA') {
        c.WASPADA += 1;
      } else {
        c.AMAN += 1;
      }
    });
    return c;
  }, [stations]);

  // Filtered Stations (Shared between Map & Table)
  const filteredStations = useMemo(() => {
    return stations.filter((s) => {
      if (selectedKabupaten !== 'ALL' && s.kabupaten !== selectedKabupaten) {
        return false;
      }
      if (selectedWarningLevel !== 'ALL') {
        const targetStatus = activeHazardTab === 'PDCHT' 
          ? (s.pdcht_status || 'NORMAL').toUpperCase()
          : (s.pdkm_status || 'NORMAL').toUpperCase();

        const isInc = targetStatus === 'INCOMPLETE' || targetStatus === 'INSUFFICIENT_DATA';
        if (selectedWarningLevel === 'INSUFFICIENT' || selectedWarningLevel === 'INCOMPLETE') {
          if (!isInc) return false;
        } else if (selectedWarningLevel === 'AMAN' || selectedWarningLevel === 'NORMAL') {
          if (targetStatus !== 'NORMAL' && targetStatus !== 'AMAN') return false;
        } else {
          if (targetStatus !== selectedWarningLevel) return false;
        }
      }
      if (searchQuery.trim() !== '') {
        const q = searchQuery.toLowerCase().trim();
        const nameMatch = (s.station_name || '').toLowerCase().includes(q);
        const idMatch = (s.station_id || '').toLowerCase().includes(q);
        const kabMatch = (s.kabupaten || '').toLowerCase().includes(q);
        if (!nameMatch && !idMatch && !kabMatch) {
          return false;
        }
      }
      return true;
    });
  }, [stations, selectedKabupaten, selectedWarningLevel, searchQuery, activeHazardTab]);

  const handleKpiFilterSelect = (cardId) => {
    if (cardId === 'ALL') {
      setSelectedWarningLevel('ALL');
      setSelectedKabupaten('ALL');
      setSearchQuery('');
      setSelectedStationId(null);
      setMapFocusTrigger((prev) => prev + 1);
      return;
    }
    if (selectedWarningLevel === cardId) {
      setSelectedWarningLevel('ALL');
    } else {
      setSelectedWarningLevel(cardId);
    }
  };

  const handleResetFilters = () => {
    setSelectedKabupaten('ALL');
    setSelectedWarningLevel('ALL');
    setSearchQuery('');
    setSelectedStationId(null);
    setMapFocusTrigger((prev) => prev + 1);
  };

  const selectedStationObj = useMemo(() => {
    if (!selectedStationId) return null;
    return stations.find((s) => s.station_id === selectedStationId) || null;
  }, [selectedStationId, stations]);

  // Priority stations requiring attention (AWAS, SIAGA, WASPADA) strictly according to activeHazardTab
  const priorityStations = useMemo(() => {
    return filteredStations.filter((s) => {
      const raw = activeHazardTab === 'PDCHT'
        ? (s.pdcht_status || 'NORMAL').toUpperCase()
        : (s.pdkm_status || 'NORMAL').toUpperCase();
      return raw.includes('AWAS') || raw.includes('SIAGA') || raw.includes('WASPADA');
    }).sort((a, b) => {
      const getScore = (stn) => {
        const lvlStr = activeHazardTab === 'PDCHT'
          ? (stn.pdcht_status || 'NORMAL').toUpperCase()
          : (stn.pdkm_status || 'NORMAL').toUpperCase();
        if (lvlStr.includes('AWAS')) return 3;
        if (lvlStr.includes('SIAGA')) return 2;
        if (lvlStr.includes('WASPADA')) return 1;
        return 0;
      };
      return getScore(b) - getScore(a);
    });
  }, [filteredStations, activeHazardTab]);

  const handleOpenOfficialMap = (type = 'PDKM') => {
    setOfficialMapType(type);
    setOfficialMapModalOpen(true);
  };

  const currentPeriodLabel = useMemo(() => {
    const p = periods.find((x) => x.period_id === selectedPeriodId);
    return p ? p.label : selectedPeriodId;
  }, [periods, selectedPeriodId]);

  const lastUpdated = stations.length > 0 ? stations[0].updated_at : null;

  if (authChecking) {
    return (
      <div className="auth-checking-container">
        <div className="auth-checking-card">
          <div className="spin spinner-xl"></div>
          <h3>Memeriksa Sesi DSS-PIK...</h3>
          <p>Memverifikasi otentikasi operator dengan server BMKG</p>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <LoginPage onLoginSuccess={(user) => setCurrentUser(user)} />;
  }

  return (
    <div className="app-container">
      {/* 1. Institutional Header with Navigation Tabs */}
      <Header
        onRefresh={handleRefreshAndEvaluate}
        loading={loading}
        totalStations={stations.length}
        lastUpdated={lastUpdated}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      {/* Tab 1: Peringatan Dini (Decision Support Dashboard) */}
      {activeTab === 'dashboard' && (
        <>
          {/* 2. Institutional Metadata & Multi-Period Selector Banner */}
          <SimulationBanner
            meta={meta}
            periods={periods}
            selectedPeriodId={selectedPeriodId}
            periodMode={periodMode}
            serverTime={serverTime}
            onSelectPeriod={handleSelectPeriod}
            onSwitchToRealtime={handleSwitchToRealtime}
            periodLoading={loading}
            onOpenOfficialMap={handleOpenOfficialMap}
            readinessInfo={readinessInfo}
          />

          {/* Main Content Area */}
          <main className="main-content">
            {/* 1. Operational Error Diagnostic Card */}
            {error && (
              <div className="operational-connection-error-card" role="alert">
                <div className="error-card-header">
                  <div className="error-icon-box">
                    <ServerOff size={24} />
                  </div>
                  <div className="error-title-group">
                    <h3>Koneksi Backend Belum Siap</h3>
                    <p>Data DSS-PIK tidak dapat dimuat setelah beberapa kali percobaan otomatis.</p>
                  </div>
                  <button
                    type="button"
                    className="btn-retry-primary"
                    onClick={() => fetchData(selectedPeriodId, true)}
                    disabled={loading}
                  >
                    <RefreshCw size={15} className={loading ? "spin" : ""} />
                    <span>{loading ? "Menghubungkan..." : "Coba Hubungkan Kembali"}</span>
                  </button>
                </div>

                <div className="error-diagnostics-grid">
                  <div className="diag-item">
                    <span className="diag-label">Alamat API Backend</span>
                    <span className="diag-val font-mono">{connectionDiagnostics?.apiUrl || (typeof window !== 'undefined' ? window.location.origin : '')}</span>
                  </div>
                  <div className="diag-item">
                    <span className="diag-label">Status Layanan API</span>
                    <span className={`diag-badge ${connectionDiagnostics?.apiStatus?.includes('Aktif') ? 'badge-ok' : 'badge-danger'}`}>
                      {connectionDiagnostics?.apiStatus || 'Offline'}
                    </span>
                  </div>
                  <div className="diag-item">
                    <span className="diag-label">Status Basis Data</span>
                    <span className={`diag-badge ${connectionDiagnostics?.dbStatus?.includes('Terhubung') ? 'badge-ok' : 'badge-danger'}`}>
                      {connectionDiagnostics?.dbStatus || 'Tidak Terhubung'}
                    </span>
                  </div>
                  <div className="diag-item">
                    <span className="diag-label">Status Sesi Operator</span>
                    <span className="diag-badge badge-ok">
                      {connectionDiagnostics?.authStatus || 'Sesi Aktif'}
                    </span>
                  </div>
                </div>

                <div className="error-troubleshoot-hints">
                  <h4>Panduan Pemecahan Masalah Operasional:</h4>
                  <ol>
                    <li>Pastikan launcher batch <strong>buka_dashboard_cews.bat</strong> atau <strong>run_cews_demo.bat</strong> sudah dijalankan.</li>
                    <li>Periksa apakah MariaDB (port 3306) dan Backend FastAPI (port 8000) aktif di terminal sistem.</li>
                    <li>Jika sistem baru dinyalakan, tunggu beberapa saat hingga modul Python selesai dimuat, lalu klik tombol <strong>Coba Hubungkan Kembali</strong>.</li>
                  </ol>
                </div>
              </div>
            )}

            {/* 2. Professional Opening Connection State (Neat, Neutral, Climatological) */}
            {connectionStatus === 'connecting' && stations.length === 0 && !error && (
              <div className="connection-probe-container">
                <div className="connection-probe-card">
                  <div className="connection-probe-header">
                    <div className="connection-probe-icon-box">
                      <RefreshCw size={24} className="spin text-forest" />
                    </div>
                    <div className="connection-probe-title-group">
                      <h3 className="connection-probe-title">{connectionStepText}</h3>
                      <p className="connection-probe-desc">{connectionDetailText}</p>
                    </div>
                  </div>

                  <div className="connection-probe-steps">
                    <div className={`probe-step-item ${connectionStepNum >= 1 ? 'active' : ''}`}>
                      <div className="probe-step-dot"></div>
                      <span>1. Menghubungkan ke Backend API BMKG (Port 8000)</span>
                    </div>
                    <div className={`probe-step-item ${connectionStepNum >= 2 ? 'active' : ''}`}>
                      <div className="probe-step-dot"></div>
                      <span>2. Memeriksa Kesiapan Basis Data MariaDB (Port 3306)</span>
                    </div>
                    <div className={`probe-step-item ${connectionStepNum >= 3 ? 'active' : ''}`}>
                      <div className="probe-step-dot"></div>
                      <span>3. Memuat Data Indikator Peringatan Dini Dasarian</span>
                    </div>
                  </div>

                  <div className="connection-probe-footer">
                    <span>Mohon tunggu beberapa saat. Sistem sedang melakukan sinkronisasi otomatis.</span>
                  </div>
                </div>
              </div>
            )}

            {/* 3. Subtle Refresh Loading Overlay (when stations are already cached) */}
            {loading && stations.length > 0 && !error && (
              <div className="loading-state-container" style={{ padding: '16px 20px', margin: '0 0 12px 0' }}>
                <div className="spin spinner-xl"></div>
                <h3 style={{ fontSize: '0.92rem' }}>Memperbarui Data Dasarian...</h3>
              </div>
            )}

            {/* Main Dashboard Workspace */}
            {!error && (
              <>
                {/* 3. Dual Hazard KPI Summary Cards */}
                <KpiCards
                  counts={counts}
                  pdkmCounts={pdkmCounts}
                  pdchtCounts={pdchtCounts}
                  activeHazardTab={activeHazardTab}
                  onSelectHazardTab={setActiveHazardTab}
                  selectedFilter={selectedWarningLevel}
                  onSelectFilter={handleKpiFilterSelect}
                />

                {/* 4. Filter Bar with Segmented Switch [PETA] [TABEL HTH] */}
                <FilterBar
                  currentView={currentView}
                  onViewChange={setCurrentView}
                  kabupatenList={kabupatenList}
                  selectedKabupaten={selectedKabupaten}
                  onSelectKabupaten={setSelectedKabupaten}
                  selectedWarningLevel={selectedWarningLevel}
                  onSelectWarningLevel={setSelectedWarningLevel}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  onResetFilters={handleResetFilters}
                  totalCount={stations.length}
                  filteredCount={filteredStations.length}
                />

                {/* 5. Balanced Workspace Layout */}
                {currentView === 'map' ? (
                  <div className="dashboard-split-layout">
                    {/* Left Column: Proportional Map (~44% width) */}
                    <div className="map-column-pane">
                      <MapLeaflet
                        stations={filteredStations}
                        selectedStation={selectedStationObj}
                        onSelectStation={(stn) => setSelectedStationId(stn.station_id)}
                        active={currentView === 'map'}
                        focusTrigger={mapFocusTrigger}
                        activeHazard={activeHazardTab}
                        onSelectHazard={setActiveHazardTab}
                        periodId={selectedPeriodId}
                      />
                    </div>

                    {/* Right Column: Station Details or Priority Overview (~56% width) */}
                    <div className="context-column-pane">
                      {selectedStationId ? (
                        <StationDetailDrawer
                          stationId={selectedStationId}
                          periodId={selectedPeriodId}
                          onClose={() => setSelectedStationId(null)}
                        />
                      ) : (
                        <div className="priority-overview-panel">
                          <div className="priority-header">
                            <div className="flex-align gap-2">
                              <ShieldAlert size={18} className="text-forest" />
                              <h3 className="priority-title">Daftar Titik Perhatian Khusus</h3>
                            </div>
                            <span className="priority-count-badge">
                              {priorityStations.length} Titik Perlu Pemantauan
                            </span>
                          </div>

                          <div className="priority-list-container">
                            {priorityStations.length === 0 ? (
                              <div className="priority-empty">
                                <p>Tidak ada stasiun berstatus peringatan pada kriteria filter saat ini.</p>
                              </div>
                            ) : (
                              priorityStations.map((stn) => {
                                const raw = (activeHazardTab === 'PDCHT'
                                  ? (stn.pdcht_status || 'NORMAL')
                                  : (stn.pdkm_status || 'NORMAL')
                                ).toUpperCase();
                                let lvl = 'NORMAL';
                                if (raw.includes('AWAS')) lvl = 'AWAS';
                                else if (raw.includes('SIAGA')) lvl = 'SIAGA';
                                else if (raw.includes('WASPADA')) lvl = 'WASPADA';

                                return (
                                  <div
                                    key={stn.station_id}
                                    className={`priority-card lvl-border-${lvl.toLowerCase()}`}
                                    onClick={() => setSelectedStationId(stn.station_id)}
                                    role="button"
                                    tabIndex={0}
                                  >
                                    <div className="priority-card-top">
                                      <span className={`badge-pill lvl-${lvl.toLowerCase()}`}>
                                        {lvl}
                                      </span>
                                      <span className="priority-card-kab">{stn.kabupaten}</span>
                                    </div>
                                    <h4 className="priority-card-name">{stn.station_name}</h4>
                                    <div className="priority-card-metrics">
                                      <span>ID: <strong className="font-mono">{stn.station_id}</strong></span>
                                      <span>HTH: <strong>{stn.hth_days_current != null ? `${stn.hth_days_current} hr` : '-'}</strong></span>
                                    </div>
                                    <div className="priority-card-footer">
                                      <span className="priority-inspect-link">
                                        <Eye size={12} />
                                        <span>Buka Detail & Fokus Peta</span>
                                        <ChevronRight size={12} />
                                      </span>
                                    </div>
                                  </div>
                                );
                              })
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  /* Full-Width HTH Table View */
                  <div className="dashboard-table-layout">
                    <HthTable
                      stations={filteredStations}
                      selectedStationId={selectedStationId}
                      onSelectStation={(stn) => setSelectedStationId(stn.station_id)}
                      prevDasarianLabel={meta?.prev_dasarian_label}
                      periodId={selectedPeriodId}
                    />
                  </div>
                )}
              </>
            )}
          </main>
        </>
      )}

      {/* Tab 2: Data Center (Data Curah Hujan, Data SPI, Data Probabilitas, Unduh Data) */}
      {(activeTab === 'data' || activeTab === 'rainfall-table') && (
        <main className="main-content data-tab-main">
          <ErrorBoundary name="Pusat Data (Data Center)">
            <DataCenter 
              activePeriodId={selectedPeriodId} 
              onDataIngestionCommitted={(commitRes) => {
                // Instantly sync dashboard evaluation, HTH, maps, and period readiness without manual reload
                fetchData(selectedPeriodId, true);
                fetchReadiness(selectedPeriodId);
              }}
            />
          </ErrorBoundary>
        </main>
      )}

      {/* Tab 3: Kamus (Istilah, Indikator, dan Ketentuan DSS-PIK) */}
      {activeTab === 'kamus' && (
        <main className="main-content kamus-tab-main">
          <ErrorBoundary name="Kamus Istilah & Regulasi">
            <KamusPage />
          </ErrorBoundary>
        </main>
      )}

      {/* Official BMKG Map Modal (PDKM & PDCHT) */}
      <ErrorBoundary name="Generator Peta Resmi BMKG">
        <OfficialMapModal
          isOpen={officialMapModalOpen}
          onClose={() => setOfficialMapModalOpen(false)}
          initialMapType={officialMapType}
          periodId={selectedPeriodId}
          periodLabel={currentPeriodLabel}
          stations={stations}
          currentUser={currentUser}
        />
      </ErrorBoundary>

      {/* 7. Institutional Footer */}
      <footer className="dashboard-footer">
        <div className="footer-left">
          <span>&copy; 2026 {INSTITUTION_SHORT_NAME} &bull; DSS-PIK Operasional</span>
        </div>
        <div className="footer-right">
          <span className="footer-disclaimer">
            Sistem Pendukung Keputusan Peringatan Dini Iklim Kepulauan Riau
          </span>
        </div>
      </footer>
    </div>
  );
}
