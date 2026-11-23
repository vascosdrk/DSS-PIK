import React, { useEffect, useRef, useState, useMemo } from 'react';
import L from 'leaflet';
import { Maximize2, Layers } from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

function normalizeWarningLevel(raw) {
  if (!raw) return 'NORMAL';
  const str = String(raw).toUpperCase().trim();
  if (str.includes('AWAS')) return 'AWAS';
  if (str.includes('SIAGA')) return 'SIAGA';
  if (str.includes('WASPADA')) return 'WASPADA';
  return 'NORMAL';
}

export default function MapLeaflet({
  stations = [],
  selectedStation,
  onSelectStation,
  active = true,
  focusTrigger = 0,
  activeHazard = 'PDKM', // 'PDKM' | 'PDCHT'
  onSelectHazard,
  periodId = null,
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);

  // Vector Boundary & ZOM Layer State
  const [showKabkot, setShowKabkot] = useState(true);
  const [showKecamatan, setShowKecamatan] = useState(false);
  const [showZom, setShowZom] = useState(false);
  const [decisionPayload, setDecisionPayload] = useState(null);

  const kabkotLayerRef = useRef(null);
  const kecamatanLayerRef = useRef(null);
  const zomLayerRef = useRef(null);
  const geoCacheRef = useRef({});

  // Fetch standardized decision-based JSON for WebGIS Kab/Kota & Kecamatan layers
  useEffect(() => {
    let isMounted = true;
    const loadDecisionJson = async () => {
      try {
        const res = await authFetch(API_ENDPOINTS.SIH3_PUBLICATION_PREVIEW, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ period_id: periodId || null }),
        });
        if (res.ok) {
          const json = await res.json();
          if (isMounted && json?.payload) {
            setDecisionPayload(json.payload);
          }
        }
      } catch (err) {
        console.warn('Gagal memuat JSON keputusan standar untuk layer WebGIS:', err);
      }
    };
    loadDecisionJson();
    return () => {
      isMounted = false;
    };
  }, [periodId]);

  const regionDecisionByKey = useMemo(() => {
    const map = {};
    if (decisionPayload?.regions) {
      decisionPayload.regions.forEach((r) => {
        if (r.sih3_polygon_key) map[r.sih3_polygon_key.toUpperCase()] = r;
        if (r.region_name) map[r.region_name.toUpperCase()] = r;
        if (r.region_code) map[r.region_code] = r;
      });
    }
    return map;
  }, [decisionPayload]);

  const kecamatanDecisionById = useMemo(() => {
    const map = {};
    if (decisionPayload?.kecamatan) {
      decisionPayload.kecamatan.forEach((k) => {
        if (k.kecamatan_id) map[k.kecamatan_id.toUpperCase()] = k;
      });
    }
    return map;
  }, [decisionPayload]);

  // Invalidate map size when toggled to active or window resizes
  useEffect(() => {
    if (active && mapInstanceRef.current) {
      const timer = setTimeout(() => {
        mapInstanceRef.current?.invalidateSize();
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [active]);

  useEffect(() => {
    const handleResize = () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Precise Bounding Box of Kepulauan Riau (Lingga to Natuna, Karimun to Serasan)
  const KEPRI_BOUNDS = [
    [-0.65, 103.20], // Southernmost Lingga/Singkep with padding
    [4.85, 109.15],  // Northernmost Natuna with balanced ocean margin
  ];

  // Initialize Leaflet Map once
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      minZoom: 5,
      maxZoom: 18,
      zoomControl: false,
    });

    // Fit exact Kepri bounds preventing Lingga cutoff and excessive north ocean void
    map.fitBounds(KEPRI_BOUNDS, { padding: [20, 20] });

    // Add Zoom Control at top right
    L.control.zoom({ position: 'topright' }).addTo(map);

    // Standard OpenStreetMap tiles
    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | DSS-PIK BMKG Kepri',
    });
    osmLayer.addTo(map);

    // LayerGroup for markers
    const markersLayer = L.layerGroup().addTo(map);
    markersLayerRef.current = markersLayer;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Handle Batas Kabupaten / Kota Layer (Default Active) — enriched with standardized regions[] decision JSON
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (kabkotLayerRef.current && map.hasLayer(kabkotLayerRef.current)) {
      map.removeLayer(kabkotLayerRef.current);
      kabkotLayerRef.current = null;
    }

    if (showKabkot) {
      const fetchKabkot = async () => {
        try {
          let data = geoCacheRef.current['kabkot'];
          if (!data) {
            const res = await authFetch(API_ENDPOINTS.GEO_LAYER('kabkot'));
            if (res.ok) {
              data = await res.json();
              geoCacheRef.current['kabkot'] = data;
            }
          }
          if (data && mapInstanceRef.current) {
            const layer = L.geoJSON(data, {
              style: {
                color: '#0284c7',
                weight: 2,
                fill: false,
                opacity: 0.85,
              },
              onEachFeature: (feature, l) => {
                const rawName = feature.properties?.region_name || feature.properties?.name || feature.properties?.KABKOT || 'Kabupaten/Kota';
                const normKey = String(rawName).trim().toUpperCase();
                const regDec = regionDecisionByKey[normKey]
                  || regionDecisionByKey[`KOTA ${normKey}`]
                  || regionDecisionByKey[`KABUPATEN ${normKey}`];

                if (regDec) {
                  const ovStatus = regDec.overall_region_status || 'AMAN';
                  const pdkmFin = regDec.hazard_assessments?.PDKM?.final_level || 'AMAN';
                  const pdchtFin = regDec.hazard_assessments?.PDCHT?.final_level || 'AMAN';
                  const covPct = regDec.data_coverage?.coverage_percentage ?? regDec.station_coverage?.percentage ?? 0;
                  l.bindTooltip(
                    `<strong>${regDec.region_name}</strong> &bull; Status: <strong>${ovStatus}</strong> (PDKM: ${pdkmFin} | PDCHT: ${pdchtFin})`,
                    { sticky: true }
                  );
                  l.bindPopup(
                    `<div style="font-size:12px;line-height:1.45;color:#1e293b;">
                      <div style="font-weight:700;font-size:13px;border-bottom:1px solid #cbd5e1;padding-bottom:3px;margin-bottom:5px;">
                        ${regDec.region_name} (${regDec.region_code})
                      </div>
                      <div><strong>Status Akhir Wilayah:</strong> ${ovStatus}</div>
                      <div><strong>PDKM:</strong> ${pdkmFin} (Rek: ${regDec.hazard_assessments?.PDKM?.recommended_level || '—'})</div>
                      <div><strong>PDCHT:</strong> ${pdchtFin} (Rek: ${regDec.hazard_assessments?.PDCHT?.recommended_level || '—'})</div>
                      <div><strong>Cakupan Data:</strong> ${regDec.data_coverage?.valid_stations ?? 0}/${regDec.data_coverage?.total_stations ?? 0} pos (${covPct}%)</div>
                      <div><strong>Sumber Keputusan:</strong> ${regDec.operator_decision?.decision_source || 'DSS_RECOMMENDATION'}</div>
                    </div>`,
                    { maxWidth: 280 }
                  );
                } else {
                  l.bindTooltip(rawName, { sticky: true });
                }
              },
            });
            kabkotLayerRef.current = layer;
            layer.addTo(mapInstanceRef.current);
          }
        } catch (err) {
          console.warn('Gagal memuat layer batas kabupaten/kota:', err);
        }
      };
      fetchKabkot();
    }
  }, [showKabkot, regionDecisionByKey]);

  // Handle Batas Kecamatan Layer — enriched with standardized kecamatan[] decision JSON
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (kecamatanLayerRef.current && map.hasLayer(kecamatanLayerRef.current)) {
      map.removeLayer(kecamatanLayerRef.current);
      kecamatanLayerRef.current = null;
    }

    if (showKecamatan) {
      const fetchKec = async () => {
        try {
          let data = geoCacheRef.current['kecamatan'];
          if (!data) {
            const res = await authFetch(API_ENDPOINTS.GEO_LAYER('kecamatan'));
            if (res.ok) {
              data = await res.json();
              geoCacheRef.current['kecamatan'] = data;
            }
          }
          if (data && mapInstanceRef.current) {
            const layer = L.geoJSON(data, {
              style: (feature) => {
                const kab = String(feature.properties?.KABKOT || '').trim().toUpperCase();
                const kec = String(feature.properties?.KECAMATAN || '').trim().toUpperCase();
                const kid = `${kab}_${kec}`.replace(/\s+/g, '_');
                const kDec = kecamatanDecisionById[kid];
                const st = kDec?.overall_status || 'AMAN';
                const fillColor = st === 'AWAS' ? '#ef4444' : st === 'SIAGA' ? '#f97316' : st === 'WASPADA' ? '#eab308' : st === 'INSUFFICIENT_DATA' ? '#94a3b8' : '#22c55e';
                return {
                  color: '#475569',
                  weight: 1,
                  dashArray: '3, 4',
                  fillColor,
                  fillOpacity: kDec ? 0.16 : 0,
                  opacity: 0.7,
                };
              },
              onEachFeature: (feature, l) => {
                const kec = feature.properties?.KECAMATAN || 'Kecamatan';
                const kabRaw = feature.properties?.KABKOT || '';
                const kabLabel = feature.properties?.region_name || kabRaw;
                const kid = `${String(kabRaw).trim().toUpperCase()}_${String(kec).trim().toUpperCase()}`.replace(/\s+/g, '_');
                const kDec = kecamatanDecisionById[kid];

                if (kDec) {
                  const ov = kDec.overall_status || kDec.final_decision?.level || 'AMAN';
                  const pdkmFin = kDec.hazard_assessments?.PDKM?.final_level || 'AMAN';
                  const pdchtFin = kDec.hazard_assessments?.PDCHT?.final_level || 'AMAN';
                  l.bindTooltip(
                    `<strong>Kec. ${kDec.kecamatan_name}</strong> (${kDec.kabkot}) &bull; <strong>${ov}</strong>`,
                    { sticky: true }
                  );
                  l.bindPopup(
                    `<div style="font-size:12px;line-height:1.45;color:#1e293b;">
                      <div style="font-weight:700;font-size:13px;border-bottom:1px solid #cbd5e1;padding-bottom:3px;margin-bottom:5px;">
                        Kec. ${kDec.kecamatan_name} &bull; ${kDec.kabkot}
                      </div>
                      <div><strong>Status Akhir:</strong> ${ov}</div>
                      <div><strong>PDKM:</strong> ${pdkmFin} (Rek: ${kDec.recommendations?.PDKM?.level || '—'})</div>
                      <div><strong>PDCHT:</strong> ${pdchtFin} (Rek: ${kDec.recommendations?.PDCHT?.level || '—'})</div>
                      <div><strong>Pos Terkait:</strong> ${kDec.stations_count} pos ${kDec.inherited_from_parent ? '(Mewarisi Kab/Kota)' : ''}</div>
                      <div><strong>Keputusan:</strong> ${kDec.final_decision?.is_override ? 'Override Operator' : 'Rekomendasi DSS'} (${kDec.final_decision?.operator || 'DSS-PIK'})</div>
                    </div>`,
                    { maxWidth: 280 }
                  );
                } else {
                  l.bindTooltip(`Kec. ${kec} (${kabLabel})`, { sticky: true });
                }
              },
            });
            kecamatanLayerRef.current = layer;
            layer.addTo(mapInstanceRef.current);
          }
        } catch (err) {
          console.warn('Gagal memuat layer batas kecamatan:', err);
        }
      };
      fetchKec();
    }
  }, [showKecamatan, kecamatanDecisionById]);

  // Handle Zona Musim (ZOM) Layer
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (showZom) {
      if (zomLayerRef.current) {
        if (!map.hasLayer(zomLayerRef.current)) {
          zomLayerRef.current.addTo(map);
        }
      } else {
        const fetchZom = async () => {
          try {
            let data = geoCacheRef.current['zom'];
            let analysisData = geoCacheRef.current['zom_analysis'];
            if (!data) {
              const res = await authFetch(API_ENDPOINTS.GEO_LAYER('zom'));
              if (res.ok) {
                data = await res.json();
                geoCacheRef.current['zom'] = data;
              }
            }
            if (!analysisData) {
              const resA = await authFetch(API_ENDPOINTS.GEO_ZOM_ANALYSIS());
              if (resA.ok) {
                analysisData = await resA.json();
                geoCacheRef.current['zom_analysis'] = analysisData;
              }
            }

            const zomStatsMap = {};
            if (analysisData && analysisData.zom_polygons) {
              analysisData.zom_polygons.forEach((z) => {
                zomStatsMap[z.no_zom] = z;
              });
            }

            if (data && mapInstanceRef.current) {
              const layer = L.geoJSON(data, {
                style: {
                  color: '#7c3aed',
                  weight: 1.5,
                  fillColor: '#8b5cf6',
                  fillOpacity: 0.18,
                  opacity: 0.85,
                },
                onEachFeature: (feature, l) => {
                  const p = feature.properties || {};
                  const zomCode = p.NO_ZOM || 'ZOM';
                  const zomType = p.ZOM || '';
                  const stats = zomStatsMap[zomCode];

                  l.bindTooltip(`<strong>${zomCode}</strong> (${zomType}) &bull; ${stats ? `${stats.station_count} pos` : ''}`, { sticky: true });

                  let stnListHtml = '';
                  if (stats && stats.stations && stats.stations.length > 0) {
                    const stnPreview = stats.stations.slice(0, 4).map((s) => `${s.station_name} (${s.hth_days != null ? `${s.hth_days} hr` : '—'})`).join(', ');
                    stnListHtml = `
                      <div style="margin-top: 4px; padding-top: 4px; border-top: 1px dashed #ddd6fe; font-size: 11px;">
                        <strong>Pos Terpetakan (${stats.station_count}):</strong> ${stnPreview}${stats.stations.length > 4 ? ` (+${stats.stations.length - 4} pos)` : ''}
                      </div>
                      ${stats.hth_statistics?.avg_hth != null ? `<div style="font-size: 11px; color: #475569;">Rata-rata HTH: <strong>${stats.hth_statistics.avg_hth} hari</strong> (Maks: ${stats.hth_statistics.max_hth} hari)</div>` : ''}
                    `;
                  }

                  const popupHtml = `
                    <div style="font-family: inherit; font-size: 12px; line-height: 1.4; color: #1e293b; padding: 2px;">
                      <div style="font-weight: 700; font-size: 13px; color: #6b21a8; border-bottom: 1px solid #e9d5ff; padding-bottom: 3px; margin-bottom: 5px;">
                        ${zomCode} &bull; ${zomType}
                      </div>
                      <div style="margin-bottom: 2px;"><strong>Awal Musim Hujan (AMH):</strong> ${p.AMH || '—'} (Puncak: ${p.PUNCAK_MH || '—'})</div>
                      <div style="margin-bottom: 2px;"><strong>Awal Musim Kemarau (AMK):</strong> ${p.AMK || '—'} (Puncak: ${p.PUNCAK_MK || '—'})</div>
                      <div><strong>Sifat MH:</strong> ${p.SIFAT_MH || '—'} &bull; <strong>Sifat MK:</strong> ${p.SIFAT_MK || '—'}</div>
                      ${stnListHtml}
                    </div>
                  `;
                  l.bindPopup(popupHtml, { maxWidth: 300 });
                },
              });
              zomLayerRef.current = layer;
              layer.addTo(mapInstanceRef.current);
            }
          } catch (err) {
            console.warn('Gagal memuat layer Zona Musim (ZOM):', err);
          }
        };
        fetchZom();
      }
    } else {
      if (zomLayerRef.current && map.hasLayer(zomLayerRef.current)) {
        map.removeLayer(zomLayerRef.current);
      }
    }
  }, [showZom]);

  // Update Markers when stations or selectedStation change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();

    const bounds = [];

    stations.forEach((station) => {
      if (station.latitude == null || station.longitude == null) return;
      const lat = parseFloat(station.latitude);
      const lng = parseFloat(station.longitude);
      bounds.push([lat, lng]);

      const isSelected = selectedStation && selectedStation.station_id === station.station_id;
      const isArg = station.is_arg || ['21010603B', '21010802B', '21020402B', '21040101B', '21710501B'].includes(station.station_id);
      
      const rawStatus = activeHazard === 'PDCHT' 
        ? (station.pdcht_status || 'NORMAL') 
        : (station.pdkm_status || 'NORMAL');
        
      const isIncomplete = rawStatus === 'INCOMPLETE' || rawStatus === 'INSUFFICIENT_DATA';
      const level = normalizeWarningLevel(rawStatus);

      // Custom DivIcon based on Warning Level & Evaluation Completeness
      let iconHtml = '';
      let iconSize = [18, 18];
      let iconAnchor = [9, 9];
      let zIndex = 100;

      const argTagHtml = '';

      if (level === 'AWAS') {
        iconSize = [32, 32];
        iconAnchor = [16, 16];
        zIndex = 2000;
        iconHtml = `
          <div class="custom-marker awas-marker ${isSelected ? 'selected' : ''}" title="${station.station_name} (AWAS)">
            <div class="pulse-ring awas-ring"></div>
            <div class="marker-core awas-core">!</div>
            ${argTagHtml}
          </div>
        `;
      } else if (level === 'SIAGA') {
        iconSize = [28, 28];
        iconAnchor = [14, 14];
        zIndex = 1500;
        iconHtml = `
          <div class="custom-marker siaga-marker ${isSelected ? 'selected' : ''}" title="${station.station_name} (SIAGA)">
            <div class="pulse-ring siaga-ring"></div>
            <div class="marker-core siaga-core">▲</div>
            ${argTagHtml}
          </div>
        `;
      } else if (level === 'WASPADA') {
        iconSize = [26, 26];
        iconAnchor = [13, 13];
        zIndex = 1000;
        iconHtml = `
          <div class="custom-marker waspada-marker ${isSelected ? 'selected' : ''}" title="${station.station_name} (WASPADA)">
            <div class="pulse-ring waspada-ring"></div>
            <div class="marker-core waspada-core">!</div>
            ${argTagHtml}
          </div>
        `;
      } else if (isIncomplete) {
        // INCOMPLETE / PARSIAL: Neutral styling
        iconSize = [22, 22];
        iconAnchor = [11, 11];
        zIndex = 60;
        iconHtml = `
          <div class="custom-marker incomplete-marker ${isSelected ? 'selected' : ''}" title="${station.station_name} (Evaluasi Tidak Lengkap)">
            <div class="marker-core incomplete-core">?</div>
            ${argTagHtml}
          </div>
        `;
      } else {
        // NORMAL / AMAN
        iconSize = [18, 18];
        iconAnchor = [9, 9];
        zIndex = 100;
        iconHtml = `
          <div class="custom-marker normal-marker ${isSelected ? 'selected' : ''}" title="${station.station_name} (NORMAL / AMAN)">
            <div class="marker-core normal-core"></div>
            ${argTagHtml}
          </div>
        `;
      }

      const customIcon = L.divIcon({
        html: iconHtml,
        className: 'dsspik-leaflet-div-icon',
        iconSize: iconSize,
        iconAnchor: iconAnchor,
        popupAnchor: [0, -iconAnchor[1] - 4],
      });

      const marker = L.marker([lat, lng], {
        icon: customIcon,
        title: `${station.station_name} (${isIncomplete ? 'Tidak Lengkap' : level})`,
        zIndexOffset: zIndex + (isSelected ? 500 : 0),
      });

      // Build popup content
      const displayStatus = isIncomplete ? 'TIDAK LENGKAP' : level;
      const badgeClass = isIncomplete ? 'popup-badge level-incomplete' : `popup-badge level-${level.toLowerCase()}`;
      const popupArgBadge = '';

      const popupContent = document.createElement('div');
      popupContent.className = 'marker-popup-content';
      popupContent.innerHTML = `
        <div class="popup-header">
          <div class="popup-header-tags">
            <span class="${badgeClass}">${displayStatus}</span>
            ${popupArgBadge}
          </div>
          <span class="popup-hazard">${isIncomplete ? 'DATA PARSIAL' : (activeHazard === 'PDCHT' ? 'PDCHT — Curah Hujan Tinggi' : 'PDKM — Kekeringan')}</span>
        </div>
        <h4 class="popup-station-name">${station.station_name}</h4>
        <div class="popup-details">
          <div class="popup-row">
            <span class="popup-k">ID:</span>
            <span class="popup-v font-mono">${station.station_id}</span>
          </div>
          <div class="popup-row">
            <span class="popup-k">Wilayah:</span>
            <span class="popup-v">${station.kabupaten}</span>
          </div>
          <div class="popup-row">
            <span class="popup-k">Jenis Pos:</span>
            <span class="popup-v">Stasiun Pengamatan</span>
          </div>
          <div class="popup-row">
            <span class="popup-k">ZOM / NOZOM:</span>
            <span class="popup-v font-mono">${String(station.station_id || '').trim().toLowerCase() === '21050101a' ? '<span style="color:#b45309;font-weight:600;">Belum terpetakan / Tidak masuk poligon ZOM</span>' : (station.nozom_prov ? `ZOM ${station.nozom_prov}` : 'Tidak tersedia')}</span>
          </div>
          <div class="popup-row">
            <span class="popup-k">HTH Terpantau:</span>
            <span class="popup-v font-mono bold">${station.hth_days_current != null ? `${station.hth_days_current} hari` : '—'}</span>
          </div>
          
          <div class="popup-row">
            <span class="popup-k">Target:</span>
            <span class="popup-v text-xs">${station.target_period_start || ''} s/d ${station.target_period_end || ''}</span>
          </div>
        </div>
        <button class="popup-btn-detail" id="btn-detail-${station.station_id}">
          Lihat Detail Stasiun &rarr;
        </button>
      `;

      // Attach button click inside popup
      popupContent.querySelector(`#btn-detail-${station.station_id}`).addEventListener('click', (e) => {
        e.stopPropagation();
        onSelectStation(station);
      });

      marker.bindPopup(popupContent, {
        closeButton: true,
        className: 'dsspik-leaflet-popup',
        maxWidth: 290,
      });

      marker.on('click', () => {
        onSelectStation(station);
      });

      marker.addTo(markersLayer);
    });

    // Auto-fit if there are filtered stations
    if (bounds.length > 0 && stations.length < 57) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
    }
  }, [stations, selectedStation, onSelectStation, activeHazard]);

  // Center on selected station if it changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !selectedStation) return;
    if (selectedStation.latitude != null && selectedStation.longitude != null) {
      map.flyTo([selectedStation.latitude, selectedStation.longitude], Math.max(map.getZoom(), 9), {
        duration: 1.0,
      });
    }
  }, [selectedStation]);

  // Recenter to full Kepri extent when focusTrigger updates (e.g. clicking "Total Stasiun" KPI card)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (focusTrigger > 0 && map) {
      map.fitBounds(KEPRI_BOUNDS, { padding: [20, 20], animate: true, duration: 0.8 });
    }
  }, [focusTrigger]);

  const handleRecenter = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    // Bounding box of all 57 Kepri stations (Lingga to Natuna, Karimun to Serasan)
    map.fitBounds(KEPRI_BOUNDS, { padding: [20, 20], animate: true, duration: 0.8 });
  };

  return (
    <div className="map-wrapper">
      <div ref={mapContainerRef} className="leaflet-map-element" id="dsspik-map" />

      {/* Map Control Overlay */}
      <div className="map-floating-controls">
        {/* Dual Hazard Mode Switcher */}
        <div className="map-hazard-mode-selector bg-white/95 backdrop-blur-xs p-1 rounded-lg border border-slate-300 shadow-md flex items-center space-x-1">
          <button
            type="button"
            className={`px-2.5 py-1 rounded text-xs font-bold transition flex items-center space-x-1.5 ${
              activeHazard === 'PDKM'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
            onClick={() => onSelectHazard && onSelectHazard('PDKM')}
            title="Tampilkan peta layer PDKM (Kekeringan Meteorologis)"
          >
            <span>☀️ PDKM</span>
          </button>
          <button
            type="button"
            className={`px-2.5 py-1 rounded text-xs font-bold transition flex items-center space-x-1.5 ${
              activeHazard === 'PDCHT'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
            onClick={() => onSelectHazard && onSelectHazard('PDCHT')}
            title="Tampilkan peta layer PDCHT (Curah Hujan Tinggi)"
          >
            <span>🌧️ PDCHT</span>
          </button>
        </div>

        <div className="map-layer-toggles">
          <label className="layer-toggle-label" title="Tampilkan batas administratif Kabupaten/Kota (resmi KEPRI.shp)">
            <input
              type="checkbox"
              checked={showKabkot}
              onChange={(e) => setShowKabkot(e.target.checked)}
            />
            <span>Kab/Kota</span>
          </label>
          <label className="layer-toggle-label" title="Tampilkan batas administratif Kecamatan">
            <input
              type="checkbox"
              checked={showKecamatan}
              onChange={(e) => setShowKecamatan(e.target.checked)}
            />
            <span>Kecamatan</span>
          </label>
          <label className="layer-toggle-label" title="Tampilkan poligon Zona Musim (ZOM BMKG)">
            <input
              type="checkbox"
              checked={showZom}
              onChange={(e) => setShowZom(e.target.checked)}
            />
            <span>Zona Musim (ZOM)</span>
          </label>
        </div>

        <button
          className="btn-map-control"
          onClick={handleRecenter}
          title="Fokuskan kembali ke seluruh wilayah Kepulauan Riau"
        >
          <Maximize2 size={15} />
          <span>Fokus Kepri</span>
        </button>
      </div>
    </div>
  );
}
