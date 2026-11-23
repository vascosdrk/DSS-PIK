import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  X,
  Map,
  Download,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Sparkles,
  Loader2,
  ShieldCheck,
  Info,
  Code2,
  Copy,
  Check,
  FileCode,
  AlertCircle,
  Search,
  Layers,
  ArrowUp,
  CheckSquare
} from 'lucide-react';
import { API_BASE_URL, API_ENDPOINTS, INSTITUTION_NAME, authFetch } from '../config';

export const KABKOT_TABS = [
  { id: 'ALL', name: 'Semua', count: 59 },
  { id: 'BATAM', name: 'Batam', count: 12 },
  { id: 'BINTAN', name: 'Bintan', count: 10 },
  { id: 'KARIMUN', name: 'Karimun', count: 9 },
  { id: 'KEPULAUAN ANAMBAS', name: 'Anambas', count: 7 },
  { id: 'LINGGA', name: 'Lingga', count: 5 },
  { id: 'NATUNA', name: 'Natuna', count: 12 },
  { id: 'TANJUNGPINANG', name: 'Tanjungpinang', count: 4 },
];

export const REGENCY_LIST = [
  { id: 'BINTAN', name: 'Kabupaten Bintan', code: '21.01' },
  { id: 'KARIMUN', name: 'Kabupaten Karimun', code: '21.02' },
  { id: 'KEPULAUAN ANAMBAS', name: 'Kabupaten Kepulauan Anambas', code: '21.05' },
  { id: 'KOTA BATAM', name: 'Kota Batam', code: '21.71' },
  { id: 'KOTA TANJUNGPINANG', name: 'Kota Tanjungpinang', code: '21.72' },
  { id: 'LINGGA', name: 'Kabupaten Lingga', code: '21.04' },
  { id: 'NATUNA', name: 'Kabupaten Natuna', code: '21.03' },
];

export const KECAMATAN_LIST = [
  { id: 'BATAM_BATAM_KOTA', name: 'BATAM KOTA', kabkot: 'BATAM' },
  { id: 'BATAM_BATU_AJI', name: 'BATU AJI', kabkot: 'BATAM' },
  { id: 'BATAM_BATU_AMPAR', name: 'BATU AMPAR', kabkot: 'BATAM' },
  { id: 'BATAM_BELAKANGPADANG', name: 'BELAKANGPADANG', kabkot: 'BATAM' },
  { id: 'BATAM_BENGKONG', name: 'BENGKONG', kabkot: 'BATAM' },
  { id: 'BATAM_BULANG', name: 'BULANG', kabkot: 'BATAM' },
  { id: 'BATAM_GALANG', name: 'GALANG', kabkot: 'BATAM' },
  { id: 'BATAM_LUBUK_BAJA', name: 'LUBUK BAJA', kabkot: 'BATAM' },
  { id: 'BATAM_NONGSA', name: 'NONGSA', kabkot: 'BATAM' },
  { id: 'BATAM_SAGULUNG', name: 'SAGULUNG', kabkot: 'BATAM' },
  { id: 'BATAM_SEI_BEDUK', name: 'SEI BEDUK', kabkot: 'BATAM' },
  { id: 'BATAM_SEKUPANG', name: 'SEKUPANG', kabkot: 'BATAM' },
  { id: 'BINTAN_BINTAN_PESISIR', name: 'BINTAN PESISIR', kabkot: 'BINTAN' },
  { id: 'BINTAN_BINTAN_TIMUR', name: 'BINTAN TIMUR', kabkot: 'BINTAN' },
  { id: 'BINTAN_BINTAN_UTARA', name: 'BINTAN UTARA', kabkot: 'BINTAN' },
  { id: 'BINTAN_GUNUNG_KIJANG', name: 'GUNUNG KIJANG', kabkot: 'BINTAN' },
  { id: 'BINTAN_MANTANG', name: 'MANTANG', kabkot: 'BINTAN' },
  { id: 'BINTAN_SERI_KUALA_LOBAM', name: 'SERI KUALA LOBAM', kabkot: 'BINTAN' },
  { id: 'BINTAN_TAMBELAN', name: 'TAMBELAN', kabkot: 'BINTAN' },
  { id: 'BINTAN_TELUK_BINTAN', name: 'TELUK BINTAN', kabkot: 'BINTAN' },
  { id: 'BINTAN_TELUK_SEBONG', name: 'TELUK SEBONG', kabkot: 'BINTAN' },
  { id: 'BINTAN_TOAPAYA', name: 'TOAPAYA', kabkot: 'BINTAN' },
  { id: 'KARIMUN_BURU', name: 'BURU', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_DURAI', name: 'DURAI', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_KARIMUN', name: 'KARIMUN', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_KUNDUR', name: 'KUNDUR', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_KUNDUR_BARAT', name: 'KUNDUR BARAT', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_KUNDUR_UTARA', name: 'KUNDUR UTARA', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_MERAL', name: 'MERAL', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_MORO', name: 'MORO', kabkot: 'KARIMUN' },
  { id: 'KARIMUN_TEBING', name: 'TEBING', kabkot: 'KARIMUN' },
  { id: 'KEPULAUAN_ANAMBAS_JEMAJA', name: 'JEMAJA', kabkot: 'KEPULAUAN ANAMBAS' },
  { id: 'KEPULAUAN_ANAMBAS_JEMAJA_TIMUR', name: 'JEMAJA TIMUR', kabkot: 'KEPULAUAN ANAMBAS' },
  { id: 'KEPULAUAN_ANAMBAS_PALMATAK', name: 'PALMATAK', kabkot: 'KEPULAUAN ANAMBAS' },
  { id: 'KEPULAUAN_ANAMBAS_SIANTAN', name: 'SIANTAN', kabkot: 'KEPULAUAN ANAMBAS' },
  { id: 'KEPULAUAN_ANAMBAS_SIANTAN_SELATAN', name: 'SIANTAN SELATAN', kabkot: 'KEPULAUAN ANAMBAS' },
  { id: 'KEPULAUAN_ANAMBAS_SIANTAN_TENGAH', name: 'SIANTAN TENGAH', kabkot: 'KEPULAUAN ANAMBAS' },
  { id: 'KEPULAUAN_ANAMBAS_SIANTAN_TIMUR', name: 'SIANTAN TIMUR', kabkot: 'KEPULAUAN ANAMBAS' },
  { id: 'LINGGA_LINGGA', name: 'LINGGA', kabkot: 'LINGGA' },
  { id: 'LINGGA_LINGGA_UTARA', name: 'LINGGA UTARA', kabkot: 'LINGGA' },
  { id: 'LINGGA_SENAYANG', name: 'SENAYANG', kabkot: 'LINGGA' },
  { id: 'LINGGA_SINGKEP', name: 'SINGKEP', kabkot: 'LINGGA' },
  { id: 'LINGGA_SINGKEP_BARAT', name: 'SINGKEP BARAT', kabkot: 'LINGGA' },
  { id: 'NATUNA_BUNGURAN_BARAT', name: 'BUNGURAN BARAT', kabkot: 'NATUNA' },
  { id: 'NATUNA_BUNGURAN_SELATAN', name: 'BUNGURAN SELATAN', kabkot: 'NATUNA' },
  { id: 'NATUNA_BUNGURAN_TENGAH', name: 'BUNGURAN TENGAH', kabkot: 'NATUNA' },
  { id: 'NATUNA_BUNGURAN_TIMUR', name: 'BUNGURAN TIMUR', kabkot: 'NATUNA' },
  { id: 'NATUNA_BUNGURAN_TIMUR_LAUT', name: 'BUNGURAN TIMUR LAUT', kabkot: 'NATUNA' },
  { id: 'NATUNA_BUNGURAN_UTARA', name: 'BUNGURAN UTARA', kabkot: 'NATUNA' },
  { id: 'NATUNA_MIDAI', name: 'MIDAI', kabkot: 'NATUNA' },
  { id: 'NATUNA_PULAU_LAUT', name: 'PULAU LAUT', kabkot: 'NATUNA' },
  { id: 'NATUNA_PULAU_TIGA', name: 'PULAU TIGA', kabkot: 'NATUNA' },
  { id: 'NATUNA_SERASAN', name: 'SERASAN', kabkot: 'NATUNA' },
  { id: 'NATUNA_SERASAN_TIMUR', name: 'SERASAN TIMUR', kabkot: 'NATUNA' },
  { id: 'NATUNA_SUBI', name: 'SUBI', kabkot: 'NATUNA' },
  { id: 'TANJUNGPINANG_BUKIT_BESTARI', name: 'BUKIT BESTARI', kabkot: 'TANJUNGPINANG' },
  { id: 'TANJUNGPINANG_TANJUNGPINANG_BARAT', name: 'TANJUNGPINANG BARAT', kabkot: 'TANJUNGPINANG' },
  { id: 'TANJUNGPINANG_TANJUNGPINANG_KOTA', name: 'TANJUNGPINANG KOTA', kabkot: 'TANJUNGPINANG' },
  { id: 'TANJUNGPINANG_TANJUNGPINANG_TIMUR', name: 'TANJUNGPINANG TIMUR', kabkot: 'TANJUNGPINANG' }
];

export default function OfficialMapModal({
  isOpen,
  onClose,
  initialMapType = 'UNIFIED',
  periodId = '2026-09-das2',
  periodLabel = 'Dasarian II September 2026',
  stations = [],
  currentUser,
}) {
  // Modal body scroll container ref for programmatic scrolling
  const bodyScrollRef = useRef(null);

  // Per-kecamatan decision state: 59 items
  const [decisions, setDecisions] = useState({});

  // Confirmed status per Kabupaten/Kota (track whether operator verified/confirmed the regency)
  // confirmedKabkot[kabkot] = true | false
  const [confirmedKabkot, setConfirmedKabkot] = useState({});

  // Recommendations data
  const [kecamatanRecs, setKecamatanRecs] = useState(null);
  const [loadingRecs, setLoadingRecs] = useState(false);

  // Active Tab for Kabkot
  const [activeTab, setActiveTab] = useState('ALL');

  // Filter States
  const [filterStatus, setFilterStatus] = useState('ALL'); // ALL, WASPADA, SIAGA, AWAS, AMAN, UNSELECTED
  const [searchTerm, setSearchTerm] = useState('');

  // Bulk Apply Controls
  const [bulkStatus, setBulkStatus] = useState('AMAN');

  // Map Generation State
  const [generatingMap, setGeneratingMap] = useState(null);
  const [generateError, setGenerateError] = useState(null);
  const [generatedResult, setGeneratedResult] = useState(null);

  // JSON SIH3 Export State
  const [jsonPreviewOpen, setJsonPreviewOpen] = useState(false);
  const [generatingJson, setGeneratingJson] = useState(false);
  const [jsonResult, setJsonResult] = useState(null);
  const [jsonError, setJsonError] = useState(null);
  const [copiedJson, setCopiedJson] = useState(false);

  // Handle ESC key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (jsonPreviewOpen) {
          setJsonPreviewOpen(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, jsonPreviewOpen, onClose]);

  // Quick lookup of backend recommendation object per kecamatan ID
  const kecamatanRecMap = useMemo(() => {
    if (!kecamatanRecs || !kecamatanRecs.kecamatan) return {};
    const map = {};
    kecamatanRecs.kecamatan.forEach((k) => {
      map[k.kecamatan_id] = k;
    });
    return map;
  }, [kecamatanRecs]);

  // Fetch authoritative DSS recommendations at KECAMATAN level
  const fetchRecommendations = useCallback(async () => {
    if (!periodId) return;
    setLoadingRecs(true);
    try {
      const url = API_ENDPOINTS.KECAMATAN_WARNINGS_RECOMMENDATIONS(periodId);
      const res = await authFetch(url);
      if (res.ok) {
        const data = await res.json();
        setKecamatanRecs(data);

        // Pre-populate decisions based on DSS recommendations
        const initialDecisions = {};
        KECAMATAN_LIST.forEach((item) => {
          const recObj = data.kecamatan?.find((k) => k.kecamatan_id === item.id);
          const pdkmLvl = recObj?.pdkm?.recommended_level || 'AMAN';
          const pdchtLvl = recObj?.pdcht?.recommended_level || 'AMAN';

          const pdkmActive = ['WASPADA', 'SIAGA', 'AWAS'].includes(pdkmLvl);
          const pdchtActive = ['WASPADA', 'SIAGA', 'AWAS'].includes(pdchtLvl);

          if (pdkmActive && !pdchtActive) {
            initialDecisions[item.id] = { warningType: 'PDKM', classification: pdkmLvl, overrideReason: '' };
          } else if (pdchtActive && !pdkmActive) {
            initialDecisions[item.id] = { warningType: 'PDCHT', classification: pdchtLvl, overrideReason: '' };
          } else if (pdkmActive && pdchtActive) {
            initialDecisions[item.id] = { warningType: 'PDKM', classification: pdkmLvl, overrideReason: '' };
          } else if (pdkmLvl === 'INSUFFICIENT_DATA' && pdchtLvl === 'INSUFFICIENT_DATA') {
            initialDecisions[item.id] = { warningType: 'NONE', classification: 'INSUFFICIENT_DATA', overrideReason: '' };
          } else {
            initialDecisions[item.id] = { warningType: 'NONE', classification: 'AMAN', overrideReason: '' };
          }
        });

        setDecisions((prev) => {
          const hasAny = Object.keys(prev).length > 0 && Object.values(prev).some((d) => d.warningType !== '');
          return hasAny ? prev : initialDecisions;
        });
      }
    } catch (err) {
      console.warn('Gagal memuat rekomendasi peringatan kecamatan:', err);
    } finally {
      setLoadingRecs(false);
    }
  }, [periodId]);

  useEffect(() => {
    if (isOpen) {
      setGeneratedResult(null);
      setGenerateError(null);
      setJsonResult(null);
      setJsonError(null);
      setConfirmedKabkot({});
      fetchRecommendations();
    }
  }, [isOpen, periodId, fetchRecommendations]);

  // Single Quick Setter for a Kecamatan
  const handleQuickStatusSet = (kecId, unifiedValue) => {
    setDecisions((prev) => {
      let wType = 'NONE';
      let classification = 'AMAN';

      if (unifiedValue === 'AMAN') {
        wType = 'NONE';
        classification = 'AMAN';
      } else if (unifiedValue === 'INSUFFICIENT_DATA') {
        wType = 'NONE';
        classification = 'INSUFFICIENT_DATA';
      } else if (unifiedValue.startsWith('PDKM_')) {
        wType = 'PDKM';
        classification = unifiedValue.replace('PDKM_', '');
      } else if (unifiedValue.startsWith('PDCHT_')) {
        wType = 'PDCHT';
        classification = unifiedValue.replace('PDCHT_', '');
      }

      return {
        ...prev,
        [kecId]: {
          ...(prev[kecId] || {}),
          warningType: wType,
          classification: classification,
        },
      };
    });
  };

  // Toggle Confirm for a Kabkot
  const handleToggleConfirmKabkot = (kabkotId) => {
    setConfirmedKabkot((prev) => ({
      ...prev,
      [kabkotId]: !prev[kabkotId],
    }));
  };

  // Reset all 59 kecamatan to DSS recommendations
  const handleApplyAllRecommendations = () => {
    if (!kecamatanRecs || !kecamatanRecs.kecamatan) return;
    const next = {};
    KECAMATAN_LIST.forEach((item) => {
      const recObj = kecamatanRecMap[item.id];
      const pdkmLvl = recObj?.pdkm?.recommended_level || 'AMAN';
      const pdchtLvl = recObj?.pdcht?.recommended_level || 'AMAN';

      const pdkmActive = ['WASPADA', 'SIAGA', 'AWAS'].includes(pdkmLvl);
      const pdchtActive = ['WASPADA', 'SIAGA', 'AWAS'].includes(pdchtLvl);

      if (pdkmActive && !pdchtActive) {
        next[item.id] = { warningType: 'PDKM', classification: pdkmLvl, overrideReason: '' };
      } else if (pdchtActive && !pdkmActive) {
        next[item.id] = { warningType: 'PDCHT', classification: pdchtLvl, overrideReason: '' };
      } else if (pdkmActive && pdchtActive) {
        next[item.id] = { warningType: 'PDKM', classification: pdkmLvl, overrideReason: '' };
      } else {
        next[item.id] = { warningType: 'NONE', classification: 'AMAN', overrideReason: '' };
      }
    });
    setDecisions(next);
    setConfirmedKabkot({});
  };

  // Bulk Apply to Current Active Tab (or all)
  const handleBulkApply = () => {
    let wType = 'NONE';
    let classification = 'AMAN';

    if (bulkStatus === 'AMAN') {
      wType = 'NONE';
      classification = 'AMAN';
    } else if (bulkStatus.startsWith('PDKM_')) {
      wType = 'PDKM';
      classification = bulkStatus.replace('PDKM_', '');
    } else if (bulkStatus.startsWith('PDCHT_')) {
      wType = 'PDCHT';
      classification = bulkStatus.replace('PDCHT_', '');
    }

    setDecisions((prev) => {
      const updated = { ...prev };
      const targets = activeTab === 'ALL'
        ? KECAMATAN_LIST
        : KECAMATAN_LIST.filter((k) => k.kabkot === activeTab);

      targets.forEach((k) => {
        updated[k.id] = {
          warningType: wType,
          classification: classification,
          overrideReason: `Penetapan seragam ${activeTab === 'ALL' ? 'seluruh wilayah' : activeTab}.`,
        };
      });
      return updated;
    });
  };

  // Scroll to Top Helper
  const handleScrollToTop = () => {
    if (bodyScrollRef.current) {
      bodyScrollRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Check if kecamatan has manual override from DSS
  const checkKecamatanOverride = useCallback((kecId) => {
    const dec = decisions[kecId];
    if (!dec || !dec.warningType) return false;
    const recObj = kecamatanRecMap[kecId];
    if (!recObj) return false;

    if (dec.warningType === 'PDKM') {
      const rec = recObj.pdkm?.recommended_level || 'AMAN';
      return dec.classification !== rec;
    } else if (dec.warningType === 'PDCHT') {
      const rec = recObj.pdcht?.recommended_level || 'AMAN';
      return dec.classification !== rec;
    } else if (dec.warningType === 'NONE') {
      const pdkmRec = recObj.pdkm?.recommended_level || 'AMAN';
      const pdchtRec = recObj.pdcht?.recommended_level || 'AMAN';
      return ['WASPADA', 'SIAGA', 'AWAS'].includes(pdkmRec) || ['WASPADA', 'SIAGA', 'AWAS'].includes(pdchtRec);
    }
    return false;
  }, [decisions, kecamatanRecMap]);

  // Filtered Kecamatan List
  const filteredKecamatanList = useMemo(() => {
    return KECAMATAN_LIST.filter((item) => {
      // 1. Tab Kabkot
      if (activeTab !== 'ALL' && item.kabkot !== activeTab) {
        return false;
      }

      const dec = decisions[item.id] || { warningType: '', classification: 'AMAN' };

      // 2. Status Pill Filter
      if (filterStatus !== 'ALL') {
        if (filterStatus === 'UNSELECTED') {
          if (dec.warningType && dec.warningType !== '') return false;
        } else if (filterStatus === 'AMAN') {
          if (dec.warningType !== 'NONE' && dec.classification !== 'AMAN') return false;
        } else {
          // WASPADA, SIAGA, AWAS
          if (dec.warningType === 'NONE' || dec.classification !== filterStatus) return false;
        }
      }

      // 3. Search query
      if (searchTerm.trim() !== '') {
        const q = searchTerm.toLowerCase();
        const matchesName = item.name.toLowerCase().includes(q);
        const matchesKab = item.kabkot.toLowerCase().includes(q);
        if (!matchesName && !matchesKab) return false;
      }

      return true;
    });
  }, [activeTab, filterStatus, searchTerm, decisions]);

  // Validation: count of unassigned kecamatan
  const unassignedCount = useMemo(() => {
    return KECAMATAN_LIST.filter((item) => {
      const dec = decisions[item.id];
      return !dec || !dec.warningType;
    }).length;
  }, [decisions]);

  // Metrics for active tab
  const statusCounts = useMemo(() => {
    let waspada = 0;
    let siaga = 0;
    let awas = 0;
    let aman = 0;
    let unassigned = 0;

    const targetList = activeTab === 'ALL'
      ? KECAMATAN_LIST
      : KECAMATAN_LIST.filter((k) => k.kabkot === activeTab);

    targetList.forEach((item) => {
      const dec = decisions[item.id];
      if (!dec || !dec.warningType) {
        unassigned++;
      } else if (dec.warningType === 'NONE' || dec.classification === 'AMAN') {
        aman++;
      } else if (dec.classification === 'WASPADA') {
        waspada++;
      } else if (dec.classification === 'SIAGA') {
        siaga++;
      } else if (dec.classification === 'AWAS') {
        awas++;
      }
    });

    return { waspada, siaga, awas, aman, unassigned, total: targetList.length };
  }, [decisions, activeTab]);

  // Build unified payload
  const buildUnifiedPayload = useCallback((targetMapType = 'PDKM') => {
    const kecamatanDecisionsMap = {};
    const regencyDecisionsMap = {};
    const regencyStatusMap = {};

    KECAMATAN_LIST.forEach((item) => {
      const dec = decisions[item.id] || {};
      let finalLevel = dec.classification || 'AMAN';
      let finalType = dec.warningType || null;

      if (dec.warningType === 'NONE' || !dec.warningType) {
        finalLevel = dec.classification === 'INSUFFICIENT_DATA' ? 'INSUFFICIENT_DATA' : 'AMAN';
        finalType = null;
      }

      kecamatanDecisionsMap[item.id] = {
        warning_type: finalType,
        classification: finalLevel,
        override_reason: dec.overrideReason?.trim() || null,
      };
    });

    const levelOrder = { 'AMAN': 0, 'WASPADA': 1, 'SIAGA': 2, 'AWAS': 3 };
    REGENCY_LIST.forEach((r) => {
      const regKab = r.id === 'KOTA BATAM' ? 'BATAM' : (r.id === 'KOTA TANJUNGPINANG' ? 'TANJUNGPINANG' : r.id);
      const kecsInReg = KECAMATAN_LIST.filter((k) => k.kabkot === regKab);

      let maxLvlNum = 0;
      let dominantType = null;

      kecsInReg.forEach((k) => {
        const kDec = kecamatanDecisionsMap[k.id];
        if (kDec && kDec.warning_type) {
          const lvlNum = levelOrder[kDec.classification] || 0;
          if (lvlNum > maxLvlNum) {
            maxLvlNum = lvlNum;
            dominantType = kDec.warning_type;
          }
        }
      });

      const maxLvl = ['AMAN', 'WASPADA', 'SIAGA', 'AWAS'][maxLvlNum];
      regencyDecisionsMap[r.id] = {
        warning_type: dominantType,
        classification: maxLvl,
        override_reason: null,
      };
      regencyStatusMap[r.id] = maxLvl;
    });

    return {
      period_id: periodId,
      period_label: periodLabel,
      map_type: targetMapType,
      scope: targetMapType,
      kecamatan_decisions: kecamatanDecisionsMap,
      regency_decisions: regencyDecisionsMap,
      regency_status: regencyStatusMap,
      operator_name: currentUser?.username || 'Petugas Operasional',
      notes: `Peta Resmi BMKG ${targetMapType} tingkat kecamatan diterbitkan melalui DSS-PIK.`,
      publish: false,
    };
  }, [decisions, periodId, periodLabel, currentUser]);

  // Action: Generate Map (JPG)
  const handleGenerateMap = async (targetMapType = 'PDKM') => {
    if (unassignedCount > 0) {
      setGenerateError(`Harap tentukan status untuk seluruh 59 kecamatan (${unassignedCount} belum dipilih).`);
      return;
    }

    setGeneratingMap(targetMapType);
    setGenerateError(null);
    setGeneratedResult(null);

    try {
      const payload = buildUnifiedPayload(targetMapType);
      const res = await authFetch(API_ENDPOINTS.MAP_GENERATE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Gagal menghasilkan peta resmi ${targetMapType} (HTTP ${res.status})`);
      }

      const data = await res.json();
      setGeneratedResult(data);
    } catch (err) {
      console.error('Map generation error:', err);
      setGenerateError(err.message || `Terjadi kesalahan sistem saat me-render peta resmi ${targetMapType} JPG.`);
    } finally {
      setGeneratingMap(null);
    }
  };

  // Action: Generate JSON
  const handleGenerateJson = async () => {
    if (unassignedCount > 0) {
      setJsonError(`Ekspor JSON memerlukan penetapan status seluruh 59 kecamatan (${unassignedCount} belum dipilih).`);
      return;
    }

    setGeneratingJson(true);
    setJsonError(null);

    try {
      const payload = buildUnifiedPayload('GABUNGAN');
      const res = await authFetch(API_ENDPOINTS.MAP_GENERATE_JSON, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Gagal membuat data JSON (HTTP ${res.status})`);
      }

      const data = await res.json();
      setJsonResult(data);
      setJsonPreviewOpen(true);
    } catch (err) {
      console.error('JSON generate error:', err);
      setJsonError(err.message || 'Gagal menghasilkan output data JSON.');
    } finally {
      setGeneratingJson(false);
    }
  };

  const handleCopyJson = () => {
    if (!jsonResult?.payload) return;
    navigator.clipboard.writeText(JSON.stringify(jsonResult.payload, null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop-custom" onClick={onClose} role="dialog" aria-modal="true">
      <div className="official-map-modal official-map-modal-wide" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="official-map-header">
          <div className="official-map-header-left">
            <div className="official-map-icon-box">
              <Map size={20} className="text-forest" />
            </div>
            <div>
              <h3 className="official-map-title">
                Penetapan Peringatan Dini & Peta Resmi (59 Kecamatan)
              </h3>
              <p className="official-map-subtitle">
                {INSTITUTION_NAME} &bull; Periode: <strong>{periodLabel}</strong> ({periodId})
              </p>
            </div>
          </div>

          <div className="flex-align gap-2">
            <button
              type="button"
              className="btn-apply-recommendation-clean"
              onClick={handleApplyAllRecommendations}
              title="Isi otomatis 59 kecamatan berdasarkan rekomendasi Decision Engine DSS-PIK"
              disabled={loadingRecs}
            >
              <Sparkles size={13} />
              <span>Reset Rekomendasi DSS</span>
            </button>
            <button
              type="button"
              className="btn-close-compact"
              onClick={onClose}
              title="Tutup jendela"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Body with explicit scroll container */}
        <div className="official-map-body-compact" ref={bodyScrollRef}>
          {/* TAB BAR: KABUPATEN / KOTA */}
          <div className="kabkot-nav-tabs">
            {KABKOT_TABS.map((tab) => {
              const isConfirmed = tab.id !== 'ALL' && confirmedKabkot[tab.id];
              return (
                <button
                  key={tab.id}
                  type="button"
                  className={`kabkot-tab-btn ${activeTab === tab.id ? 'active' : ''} ${isConfirmed ? 'confirmed' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <span>{tab.name}</span>
                  <span className="tab-count-badge">{tab.count}</span>
                  {isConfirmed && (
                    <span className="tab-confirm-check" title="Wilayah ini telah dikonfirmasi">
                      <Check size={12} />
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* CONFIRMATION STRIP PER KABUPATEN/KOTA */}
          {activeTab !== 'ALL' && (
            <div className={`kabkot-confirm-banner ${confirmedKabkot[activeTab] ? 'status-confirmed' : 'status-unconfirmed'}`}>
              <div className="confirm-banner-left">
                {confirmedKabkot[activeTab] ? (
                  <>
                    <CheckCircle2 size={16} className="text-emerald shrink-0" />
                    <span>
                      Status <strong>{statusCounts.total} Kecamatan di {activeTab}</strong> telah <strong>DIKONFIRMASI</strong> oleh petugas.
                    </span>
                  </>
                ) : (
                  <>
                    <AlertCircle size={16} className="text-amber shrink-0" />
                    <span>
                      Periksa dan tentukan status seluruh kecamatan di <strong>{activeTab}</strong>, lalu tekan tombol konfirmasi.
                    </span>
                  </>
                )}
              </div>
              <button
                type="button"
                className={`btn-confirm-kabkot ${confirmedKabkot[activeTab] ? 'btn-unconfirm' : ''}`}
                onClick={() => handleToggleConfirmKabkot(activeTab)}
              >
                {confirmedKabkot[activeTab] ? (
                  <>
                    <CheckSquare size={13} />
                    <span>Batal Konfirmasi ({activeTab})</span>
                  </>
                ) : (
                  <>
                    <Check size={13} />
                    <span>Konfirmasi Status {activeTab}</span>
                  </>
                )}
              </button>
            </div>
          )}

          {/* UNIFIED CONTROL BAR: Filter Status, Search, and Bulk Action in 1 Row */}
          <div className="unified-filter-action-bar">
            {/* Left: Quick Status Filter Pills */}
            <div className="filter-pills-cluster">
              <button
                type="button"
                className={`compact-pill-btn ${filterStatus === 'ALL' ? 'active' : ''}`}
                onClick={() => setFilterStatus('ALL')}
              >
                Semua ({statusCounts.total})
              </button>
              <button
                type="button"
                className={`compact-pill-btn pill-waspada ${filterStatus === 'WASPADA' ? 'active' : ''}`}
                onClick={() => setFilterStatus('WASPADA')}
              >
                <span className="dot dot-waspada"></span>
                Waspada ({statusCounts.waspada})
              </button>
              <button
                type="button"
                className={`compact-pill-btn pill-siaga ${filterStatus === 'SIAGA' ? 'active' : ''}`}
                onClick={() => setFilterStatus('SIAGA')}
              >
                <span className="dot dot-siaga"></span>
                Siaga ({statusCounts.siaga})
              </button>
              <button
                type="button"
                className={`compact-pill-btn pill-awas ${filterStatus === 'AWAS' ? 'active' : ''}`}
                onClick={() => setFilterStatus('AWAS')}
              >
                <span className="dot dot-awas"></span>
                Awas ({statusCounts.awas})
              </button>
              <button
                type="button"
                className={`compact-pill-btn pill-aman ${filterStatus === 'AMAN' ? 'active' : ''}`}
                onClick={() => setFilterStatus('AMAN')}
              >
                <span className="dot dot-aman"></span>
                Aman ({statusCounts.aman})
              </button>
            </div>

            {/* Middle: Fast Search */}
            <div className="compact-search-box">
              <Search size={13} className="compact-search-icon" />
              <input
                type="text"
                placeholder="Cari kecamatan..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="compact-search-input"
              />
              {searchTerm && (
                <button type="button" className="btn-clear-search-compact" onClick={() => setSearchTerm('')}>
                  &times;
                </button>
              )}
            </div>

            {/* Right: Quick Bulk Set for Current Selection */}
            <div className="fast-bulk-set-box">
              <Layers size={13} className="text-forest" />
              <span className="fast-bulk-label">Set Semua:</span>
              <select
                value={bulkStatus}
                onChange={(e) => setBulkStatus(e.target.value)}
                className="fast-bulk-select"
              >
                <option value="AMAN">Aman (Hijau)</option>
                <option value="PDKM_WASPADA">PDKM - Waspada (Kuning)</option>
                <option value="PDKM_SIAGA">PDKM - Siaga (Oranye)</option>
                <option value="PDKM_AWAS">PDKM - Awas (Merah)</option>
                <option value="PDCHT_WASPADA">PDCHT - Waspada (Kuning)</option>
                <option value="PDCHT_SIAGA">PDCHT - Siaga (Oranye)</option>
                <option value="PDCHT_AWAS">PDCHT - Awas (Merah)</option>
              </select>
              <button
                type="button"
                className="btn-apply-fast-bulk"
                onClick={handleBulkApply}
                title={`Terapkan status terpilih ke seluruh kecamatan di tab ${activeTab}`}
              >
                Terapkan
              </button>
            </div>
          </div>

          {/* KECAMATAN STREAMLINED LIST */}
          <div className="streamlined-kecamatan-list">
            {filteredKecamatanList.length === 0 ? (
              <div className="empty-kecamatan-notice">
                <Info size={16} className="text-slate-400" />
                <span>Tidak ada kecamatan yang cocok dengan kriteria filter saat ini.</span>
              </div>
            ) : (
              filteredKecamatanList.map((item) => {
                const dec = decisions[item.id] || { warningType: 'NONE', classification: 'AMAN' };
                const recObj = kecamatanRecMap[item.id];
                const pdkmRec = recObj?.pdkm?.recommended_level || 'AMAN';
                const pdchtRec = recObj?.pdcht?.recommended_level || 'AMAN';
                const stnCount = recObj?.stations_count || 0;
                const isInherited = recObj?.inherited_from_parent;
                const isOverride = checkKecamatanOverride(item.id);

                const currentUnifiedVal = dec.warningType === 'NONE' || !dec.warningType
                  ? (dec.classification === 'INSUFFICIENT_DATA' ? 'INSUFFICIENT_DATA' : 'AMAN')
                  : `${dec.warningType}_${dec.classification}`;

                return (
                  <div key={item.id} className="streamlined-kecamatan-row">
                    {/* Left: Name and Tags */}
                    <div className="streamlined-info-side">
                      <div className="streamlined-name-line">
                        <span className="kecamatan-name-text">{item.name}</span>
                        {activeTab === 'ALL' && (
                          <span className="kecamatan-kabkot-pill">{item.kabkot}</span>
                        )}
                        {isOverride && (
                          <span className="pill-override-indicator" title="Status ini telah disesuaikan manual oleh petugas">
                            Disesuaikan
                          </span>
                        )}
                      </div>
                      <div className="streamlined-meta-line">
                        <span className="rec-hint-text">
                          Rekomendasi DSS: <strong className={`rec-tag-${pdkmRec.toLowerCase()}`}>PDKM {pdkmRec}</strong> &bull; <strong className={`rec-tag-${pdchtRec.toLowerCase()}`}>PDCHT {pdchtRec}</strong>
                        </span>
                        <span className="bullet-sep">&bull;</span>
                        <span className="pos-count-text">
                          {isInherited ? 'Mengikuti Kab/Kota' : `${stnCount} Pos Pengamatan`}
                        </span>
                      </div>
                    </div>

                    {/* Right: 1 Single Simple Dropdown for Instant Selection */}
                    <div className="streamlined-select-side">
                      <select
                        className={`streamlined-status-select status-style-${dec.warningType === 'NONE' ? 'aman' : dec.classification.toLowerCase()}`}
                        value={currentUnifiedVal}
                        onChange={(e) => handleQuickStatusSet(item.id, e.target.value)}
                      >
                        <option value="AMAN">AMAN (Tidak Ada Peringatan)</option>
                        <option value="INSUFFICIENT_DATA">DATA TIDAK CUKUP (Insufficient Data)</option>
                        <optgroup label="PDKM (Kekeringan)">
                          <option value="PDKM_WASPADA">PDKM — WASPADA (Kuning)</option>
                          <option value="PDKM_SIAGA">PDKM — SIAGA (Oranye)</option>
                          <option value="PDKM_AWAS">PDKM — AWAS (Merah)</option>
                        </optgroup>
                        <optgroup label="PDCHT (Curah Hujan Tinggi)">
                          <option value="PDCHT_WASPADA">PDCHT — WASPADA (Kuning)</option>
                          <option value="PDCHT_SIAGA">PDCHT — SIAGA (Oranye)</option>
                          <option value="PDCHT_AWAS">PDCHT — AWAS (Merah)</option>
                        </optgroup>
                      </select>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Validation / Error Messages */}
          {generateError && (
            <div className="map-error-banner">
              <AlertTriangle size={16} />
              <span>{generateError}</span>
            </div>
          )}
          {jsonError && (
            <div className="map-error-banner">
              <AlertTriangle size={16} />
              <span>{jsonError}</span>
            </div>
          )}

          {/* Action Output Strip */}
          <div className="dual-output-action-strip">
            <div className="dual-output-desc">
              <strong>Keluaran Peringatan Dini:</strong> Pilih format output untuk me-render peta resmi atau mengekspor JSON level kecamatan.
            </div>

            <div className="dual-output-btn-group">
              <button
                type="button"
                className="btn-dual-generate-map btn-peta-pdkm"
                onClick={() => handleGenerateMap('PDKM')}
                disabled={Boolean(generatingMap) || generatingJson}
                title="Render Peta Resmi PDKM (Kekeringan) level 59 Kecamatan (JPG 150 DPI)"
              >
                {generatingMap === 'PDKM' ? (
                  <>
                    <Loader2 size={15} className="spin" />
                    <span>Me-render Peta PDKM...</span>
                  </>
                ) : (
                  <>
                    <Map size={15} />
                    <span>Generate Peta PDKM (JPG)</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="btn-dual-generate-map btn-peta-pdcht"
                onClick={() => handleGenerateMap('PDCHT')}
                disabled={Boolean(generatingMap) || generatingJson}
                title="Render Peta Resmi PDCHT (Curah Hujan Tinggi) level 59 Kecamatan (JPG 150 DPI)"
              >
                {generatingMap === 'PDCHT' ? (
                  <>
                    <Loader2 size={15} className="spin" />
                    <span>Me-render Peta PDCHT...</span>
                  </>
                ) : (
                  <>
                    <Map size={15} />
                    <span>Generate Peta PDCHT (JPG)</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="btn-dual-generate-json"
                onClick={handleGenerateJson}
                disabled={Boolean(generatingMap) || generatingJson}
                title="Bentuk dan unduh dokumen JSON terstandar level 59 kecamatan"
              >
                {generatingJson ? (
                  <>
                    <Loader2 size={15} className="spin" />
                    <span>Mengekspor JSON...</span>
                  </>
                ) : (
                  <>
                    <Code2 size={15} />
                    <span>Ekspor JSON (Kecamatan)</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Generated Result Preview */}
          {generatedResult && (
            <div className="generated-map-result-card">
              <div className="result-card-header">
                <div className="flex-align gap-2">
                  <CheckCircle2 size={16} className="text-emerald" />
                  <span className="result-card-title">
                    {generatedResult.map_type === 'PDKM'
                      ? 'Peta Resmi BMKG PDKM (Kekeringan) Level Kecamatan Berhasil Dibuat'
                      : 'Peta Resmi BMKG PDCHT (Curah Hujan Tinggi) Level Kecamatan Berhasil Dibuat'}
                  </span>
                </div>
                <div className="result-download-actions">
                  <button
                    type="button"
                    className="btn-scroll-top-banner"
                    onClick={handleScrollToTop}
                    title="Gulir ke atas untuk merevisi pilihan status kecamatan"
                  >
                    <ArrowUp size={13} />
                    <span>Revisi / Gulir Ke Atas</span>
                  </button>
                  <a
                    href={`${API_BASE_URL}${generatedResult.jpg_url || generatedResult.download_jpg_url}`}
                    target="_blank"
                    rel="noreferrer"
                    download={generatedResult.jpg_filename}
                    className="btn-download-map btn-jpg"
                  >
                    <Download size={13} />
                    <span>Unduh Peta JPG (1653&times;1170)</span>
                  </a>
                  {generatedResult.pdf_url && (
                    <a
                      href={`${API_BASE_URL}${generatedResult.pdf_url || generatedResult.download_pdf_url}`}
                      target="_blank"
                      rel="noreferrer"
                      download={generatedResult.pdf_filename}
                      className="btn-download-map btn-pdf"
                    >
                      <FileText size={13} />
                      <span>Unduh Dokumen PDF</span>
                    </a>
                  )}
                </div>
              </div>

              <div className="result-preview-viewport">
                <img
                  src={`${API_BASE_URL}${generatedResult.jpg_url || generatedResult.png_url}`}
                  alt="Pratinjau Peta Resmi BMKG Level Kecamatan"
                  className="result-preview-img"
                />
              </div>

              <div className="result-meta-footer font-mono text-xs">
                <span>File: {generatedResult.jpg_filename}</span>
                <span>Resolusi: 1653 &times; 1170 px (A4 Landscape Standar BMKG, 150 DPI)</span>
                <span>Segmentasi: 59 Kecamatan Terwarnai Presisi</span>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="official-map-footer">
          <div className="footer-left-info">
            <ShieldCheck size={14} className="text-forest" />
            <span>Operator: <strong>{currentUser?.username || 'klimatkepri'}</strong></span>
            <span className="footer-pipe-sep">|</span>
            <span>Standar: <strong>Peta Resmi BMKG &bull; JSON SIH3 Level Kecamatan</strong></span>
          </div>

          <div className="footer-right-actions">
            {generatedResult && (
              <button
                type="button"
                className="btn-scroll-top-banner"
                onClick={handleScrollToTop}
                title="Gulir ke atas untuk merevisi pilihan kecamatan"
              >
                <ArrowUp size={13} />
                <span>Gulir Ke Atas (Revisi)</span>
              </button>
            )}
            <button
              type="button"
              className="btn-secondary-compact"
              onClick={onClose}
              disabled={Boolean(generatingMap) || generatingJson}
            >
              Tutup
            </button>
          </div>
        </div>

        {/* In-Modal JSON Preview Dialog */}
        {jsonPreviewOpen && jsonResult && (
          <div className="json-preview-overlay" onClick={() => setJsonPreviewOpen(false)}>
            <div className="json-preview-modal" onClick={(e) => e.stopPropagation()}>
              <div className="json-preview-header">
                <div className="flex-align gap-2">
                  <FileCode size={18} className="text-forest" />
                  <div>
                    <h4 className="json-preview-title">Pratinjau Data JSON Peringatan Dini (Level Kecamatan)</h4>
                    <span className="json-preview-subtitle">
                      ID: <strong className="font-mono">{jsonResult.publication_id}</strong> &bull; Lingkup: <strong>59 Kecamatan &bull; 7 Kabupaten/Kota</strong>
                    </span>
                  </div>
                </div>

                <div className="flex-align gap-2">
                  <span className="badge-validation-valid">
                    <CheckCircle2 size={13} />
                    <span>59 Kecamatan Terstruktur</span>
                  </span>
                  <button
                    type="button"
                    className="btn-close-compact"
                    onClick={() => setJsonPreviewOpen(false)}
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* JSON Summary Metrics (reading standardized overall_status, overall_region_status, data_coverage & publication.status) */}
              <div className="json-summary-strip">
                <div className="summary-pill">
                  <span className="pill-label">Status Publikasi</span>
                  <span className="pill-val font-mono text-xs">
                    {jsonResult.payload?.publication?.status || 'Aktif'} (Rev {jsonResult.payload?.publication?.revision || 1})
                  </span>
                </div>
                <div className="summary-pill">
                  <span className="pill-label">Kecamatan</span>
                  <span className="pill-val">{jsonResult.payload?.kecamatan?.length || 59}</span>
                </div>
                <div className="summary-pill">
                  <span className="pill-label">WASPADA</span>
                  <span className="pill-val text-amber">
                    {jsonResult.payload?.kecamatan?.filter((k) => (k.overall_status || k.final_decision?.level) === 'WASPADA').length || 0}
                  </span>
                </div>
                <div className="summary-pill">
                  <span className="pill-label">SIAGA</span>
                  <span className="pill-val text-orange-600">
                    {jsonResult.payload?.kecamatan?.filter((k) => (k.overall_status || k.final_decision?.level) === 'SIAGA').length || 0}
                  </span>
                </div>
                <div className="summary-pill">
                  <span className="pill-label">AWAS</span>
                  <span className="pill-val text-red-600">
                    {jsonResult.payload?.kecamatan?.filter((k) => (k.overall_status || k.final_decision?.level) === 'AWAS').length || 0}
                  </span>
                </div>
                <div className="summary-pill">
                  <span className="pill-label">AMAN</span>
                  <span className="pill-val text-emerald">
                    {jsonResult.payload?.kecamatan?.filter((k) => (k.overall_status || k.final_decision?.level) === 'AMAN').length || 0}
                  </span>
                </div>
                <div className="summary-pill">
                  <span className="pill-label">DATA KURANG</span>
                  <span className="pill-val text-slate-600">
                    {jsonResult.payload?.kecamatan?.filter((k) => (k.overall_status || k.final_decision?.level) === 'INSUFFICIENT_DATA').length || 0}
                  </span>
                </div>
              </div>

              {/* Formatted JSON Code Viewer */}
              <div className="json-code-viewport">
                <pre className="json-code-block font-mono text-xs">
                  {JSON.stringify(jsonResult.payload, null, 2)}
                </pre>
              </div>

              {/* Footer Actions */}
              <div className="json-preview-footer">
                <div className="flex-align gap-2">
                  <button
                    type="button"
                    className="btn-json-action"
                    onClick={handleCopyJson}
                  >
                    {copiedJson ? <Check size={13} className="text-emerald" /> : <Copy size={13} />}
                    <span>{copiedJson ? 'Disalin ke Clipboard' : 'Salin JSON'}</span>
                  </button>
                  <a
                    href={`${API_BASE_URL}${jsonResult.json_url || `/api/v1/maps/download/${jsonResult.download_filename}`}`}
                    download={jsonResult.download_filename}
                    className="btn-json-action"
                  >
                    <Download size={13} />
                    <span>Unduh File JSON ({jsonResult.download_filename})</span>
                  </a>
                </div>

                <div className="flex-align gap-2">
                  <button
                    type="button"
                    className="btn-secondary-compact"
                    onClick={() => setJsonPreviewOpen(false)}
                  >
                    Tutup Pratinjau
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
