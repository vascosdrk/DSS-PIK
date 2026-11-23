import React, { useState, useEffect, useMemo } from 'react';
import { Activity, AlertCircle, RefreshCw, Calendar, TrendingDown } from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import { formatDateIndo } from '../utils/formatters';

export default function StationSpiTrendChart({ stationId, defaultScale = 'DASARIAN' }) {
  const [scale, setScale] = useState(defaultScale); // 'DASARIAN' | 'HARIAN' | 'BULANAN'
  const [months, setMonths] = useState(12); // 6 | 12 | 24
  const [trendData, setTrendData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hoveredPoint, setHoveredPoint] = useState(null);

  useEffect(() => {
    if (!stationId) return;
    setLoading(true);
    setError(null);
    setHoveredPoint(null);

    authFetch(API_ENDPOINTS.STATION_SPI_TREND(stationId, months))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat tren SPI`);
        return res.json();
      })
      .then((data) => {
        setTrendData(data);
      })
      .catch((err) => {
        console.error('Error fetching station SPI trend:', err);
        setError('Gagal memuat histori SPI stasiun.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [stationId, months]);

  // Extract relevant series based on selected scale
  const activeSeries = useMemo(() => {
    if (!trendData) return { primary: [], companion: null, title: '' };

    if (scale === 'DASARIAN') {
      const dates = trendData.dasarian?.dates || [];
      const pVals = trendData.dasarian?.spi_30d || [];
      const cVals = trendData.dasarian?.spi_90d || [];
      return {
        primary: dates.map((d, i) => ({ date: d, value: pVals[i] ?? null })),
        primaryLabel: 'SPI Dasarian 30D (Pemicu Utama)',
        primaryColor: '#0284c7', // sky-600
        companion: dates.map((d, i) => ({ date: d, value: cVals[i] ?? null })),
        companionLabel: 'SPI Dasarian 90D (Pendamping)',
        companionColor: '#6366f1', // indigo-500
      };
    } else if (scale === 'HARIAN') {
      const dates = trendData.harian?.dates || [];
      const pVals = trendData.harian?.spi_30d || [];
      const cVals = trendData.harian?.spi_90d || [];
      return {
        primary: dates.map((d, i) => ({ date: d, value: pVals[i] ?? null })),
        primaryLabel: 'SPI Harian 30D (Monitoring)',
        primaryColor: '#059669', // emerald-600
        companion: dates.map((d, i) => ({ date: d, value: cVals[i] ?? null })),
        companionLabel: 'SPI Harian 90D (Monitoring)',
        companionColor: '#10b981', // emerald-500
      };
    } else {
      // BULANAN
      const dates = trendData.bulanan?.dates || [];
      const vals = trendData.bulanan?.spi || [];
      return {
        primary: dates.map((d, i) => ({ date: d, value: vals[i] ?? null })),
        primaryLabel: 'SPI Bulanan (1 Bulan - Konteks Klimatologi)',
        primaryColor: '#8b5cf6', // purple-500
        companion: null,
        companionLabel: '',
        companionColor: '',
      };
    }
  }, [trendData, scale]);

  // Chart Dimensions & Coordinate Math
  const chartConfig = useMemo(() => {
    const width = 640;
    const height = 230;
    const padding = { top: 25, right: 35, bottom: 35, left: 50 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;

    // Collect all valid values to compute scale limits
    const allVals = [];
    if (activeSeries.primary) {
      activeSeries.primary.forEach((p) => {
        if (p.value !== null && p.value !== undefined) allVals.push(p.value);
      });
    }
    if (activeSeries.companion) {
      activeSeries.companion.forEach((p) => {
        if (p.value !== null && p.value !== undefined) allVals.push(p.value);
      });
    }

    // Default min/max boundaries, ensuring thresholds (-2.0, -1.5, -1.0, 0.0) are always visible
    let minY = -2.5;
    let maxY = 2.0;

    if (allVals.length > 0) {
      const minObs = Math.min(...allVals);
      const maxObs = Math.max(...allVals);
      if (minObs < minY) minY = Math.floor(minObs * 10) / 10 - 0.2;
      if (maxObs > maxY) maxY = Math.ceil(maxObs * 10) / 10 + 0.2;
    }

    const getY = (val) => {
      if (val === null || val === undefined) return null;
      const ratio = (val - minY) / (maxY - minY);
      return padding.top + innerHeight * (1 - ratio);
    };

    const count = activeSeries.primary ? activeSeries.primary.length : 0;
    const getX = (idx) => {
      if (count <= 1) return padding.left + innerWidth / 2;
      return padding.left + (idx / (count - 1)) * innerWidth;
    };

    return { width, height, padding, innerWidth, innerHeight, minY, maxY, getY, getX, count };
  }, [activeSeries]);

  // Helper to build SVG paths with segment separation to prevent false interpolation over gaps
  const buildDisjointPaths = (dataList) => {
    if (!dataList || dataList.length === 0) return [];
    const segments = [];
    let currentSegment = [];

    dataList.forEach((point, idx) => {
      if (point.value !== null && point.value !== undefined) {
        const x = chartConfig.getX(idx);
        const y = chartConfig.getY(point.value);
        currentSegment.push({ x, y, point, idx });
      } else {
        if (currentSegment.length > 0) {
          segments.push(currentSegment);
          currentSegment = [];
        }
      }
    });

    if (currentSegment.length > 0) {
      segments.push(currentSegment);
    }

    return segments.map((seg) => {
      if (seg.length === 1) {
        // Single point segment
        return `M ${seg[0].x} ${seg[0].y} l 0.01 0`;
      }
      return seg.reduce((acc, curr, i) => {
        return i === 0 ? `M ${curr.x} ${curr.y}` : `${acc} L ${curr.x} ${curr.y}`;
      }, '');
    });
  };

  const primaryPaths = useMemo(
    () => buildDisjointPaths(activeSeries.primary),
    [activeSeries.primary, chartConfig]
  );
  const companionPaths = useMemo(
    () => buildDisjointPaths(activeSeries.companion),
    [activeSeries.companion, chartConfig]
  );

  // Classify SPI condition
  const getSpiLabel = (val) => {
    if (val === null || val === undefined) return 'Tidak Ada Data';
    if (val <= -2.0) return 'AWAS (Sangat Kering)';
    if (val <= -1.5) return 'SIAGA (Kering Sedang)';
    if (val <= -1.0) return 'WASPADA (Kering Ringan)';
    if (val >= 2.0) return 'Sangat Basah';
    if (val >= 1.5) return 'Basah Sedang';
    if (val >= 1.0) return 'Agak Basah';
    return 'Normal';
  };

  if (trendData?.is_arg) {
    return (
      <div className="spi-trend-chart-card">
        <div className="arg-profile-card">
          <div className="arg-profile-header">
            <span className="badge-arg-tag-lg">STASIUN PENGAMATAN</span>
          </div>
          <p className="arg-profile-narrative text-xs">
            Data deret waktu SPI historis tidak tersedia untuk stasiun ini. Sistem operasional mengevaluasi pos ini berdasarkan indikator operasional yang tersedia.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="spi-trend-chart-card">
      {/* Header & Controls */}
      <div className="spi-trend-header">
        <div>
          <h4 className="spi-trend-title">
            <Activity size={14} className="inline-icon text-sky-600" />
            <span>Tren Indeks SPI Stasiun</span>
          </h4>
          <p className="spi-trend-subtitle">
            Visualisasi historis tanpa interpolasi data kosong. Ambang kekeringan BMKG: -1.00, -1.50, -2.00.
          </p>
        </div>

        <div className="spi-trend-controls">
          {/* Scale Switcher */}
          <div className="segmented-switch-sm" role="group" aria-label="Skala SPI">
            <button
              type="button"
              className={`switch-btn-sm ${scale === 'DASARIAN' ? 'active' : ''}`}
              onClick={() => setScale('DASARIAN')}
            >
              Dasarian
            </button>
            <button
              type="button"
              className={`switch-btn-sm ${scale === 'HARIAN' ? 'active' : ''}`}
              onClick={() => setScale('HARIAN')}
            >
              Harian
            </button>
            <button
              type="button"
              className={`switch-btn-sm ${scale === 'BULANAN' ? 'active' : ''}`}
              onClick={() => setScale('BULANAN')}
            >
              Bulanan
            </button>
          </div>

          {/* Horizon Months Switcher */}
          <select
            className="spi-trend-select-months"
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            title="Rentang Waktu Riwayat"
          >
            <option value={6}>6 Bulan Terakhir</option>
            <option value={12}>12 Bulan Terakhir</option>
            <option value={24}>24 Bulan Terakhir</option>
          </select>
        </div>
      </div>

      {/* Legend & Threshold Notes */}
      <div className="spi-trend-legend-row">
        <div className="spi-legend-item">
          <span className="legend-line-solid" style={{ backgroundColor: activeSeries.primaryColor }}></span>
          <span className="legend-text">{activeSeries.primaryLabel}</span>
        </div>
        {activeSeries.companion && (
          <div className="spi-legend-item">
            <span className="legend-line-dashed" style={{ borderColor: activeSeries.companionColor }}></span>
            <span className="legend-text">{activeSeries.companionLabel}</span>
          </div>
        )}
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="spi-trend-loading">
          <div className="spin spinner-sm"></div>
          <span>Memuat deret waktu SPI...</span>
        </div>
      )}

      {error && !loading && (
        <div className="spi-trend-error">
          <AlertCircle size={15} />
          <span>{error}</span>
        </div>
      )}

      {/* Main SVG Chart Area */}
      {!loading && !error && chartConfig.count > 0 && (
        <div className="spi-svg-container">
          <svg
            viewBox={`0 0 ${chartConfig.width} ${chartConfig.height}`}
            className="spi-trend-svg"
            preserveAspectRatio="xMidYMid meet"
          >
            {/* Background Grid & Threshold Lines */}
            {/* 0.00 Normal Line */}
            {chartConfig.getY(0.0) != null && (
              <g className="grid-line normal-line">
                <line
                  x1={chartConfig.padding.left}
                  y1={chartConfig.getY(0.0)}
                  x2={chartConfig.width - chartConfig.padding.right}
                  y2={chartConfig.getY(0.0)}
                  stroke="#94a3b8"
                  strokeWidth="1"
                  strokeDasharray="2,2"
                />
                <text
                  x={chartConfig.padding.left - 6}
                  y={chartConfig.getY(0.0) + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="#64748b"
                >
                  0.00
                </text>
              </g>
            )}

            {/* -1.00 WASPADA Line */}
            {chartConfig.getY(-1.0) != null && (
              <g className="grid-line threshold-waspada">
                <line
                  x1={chartConfig.padding.left}
                  y1={chartConfig.getY(-1.0)}
                  x2={chartConfig.width - chartConfig.padding.right}
                  y2={chartConfig.getY(-1.0)}
                  stroke="#eab308"
                  strokeWidth="1.2"
                  strokeDasharray="4,3"
                />
                <text
                  x={chartConfig.padding.left - 6}
                  y={chartConfig.getY(-1.0) + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="#ca8a04"
                  fontWeight="bold"
                >
                  -1.00
                </text>
                <text
                  x={chartConfig.width - chartConfig.padding.right + 4}
                  y={chartConfig.getY(-1.0) + 3}
                  textAnchor="start"
                  fontSize="8"
                  fill="#ca8a04"
                >
                  Waspada
                </text>
              </g>
            )}

            {/* -1.50 SIAGA Line */}
            {chartConfig.getY(-1.5) != null && (
              <g className="grid-line threshold-siaga">
                <line
                  x1={chartConfig.padding.left}
                  y1={chartConfig.getY(-1.5)}
                  x2={chartConfig.width - chartConfig.padding.right}
                  y2={chartConfig.getY(-1.5)}
                  stroke="#f97316"
                  strokeWidth="1.2"
                  strokeDasharray="4,3"
                />
                <text
                  x={chartConfig.padding.left - 6}
                  y={chartConfig.getY(-1.5) + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="#ea580c"
                  fontWeight="bold"
                >
                  -1.50
                </text>
                <text
                  x={chartConfig.width - chartConfig.padding.right + 4}
                  y={chartConfig.getY(-1.5) + 3}
                  textAnchor="start"
                  fontSize="8"
                  fill="#ea580c"
                >
                  Siaga
                </text>
              </g>
            )}

            {/* -2.00 AWAS Line */}
            {chartConfig.getY(-2.0) != null && (
              <g className="grid-line threshold-awas">
                <line
                  x1={chartConfig.padding.left}
                  y1={chartConfig.getY(-2.0)}
                  x2={chartConfig.width - chartConfig.padding.right}
                  y2={chartConfig.getY(-2.0)}
                  stroke="#ef4444"
                  strokeWidth="1.2"
                  strokeDasharray="4,3"
                />
                <text
                  x={chartConfig.padding.left - 6}
                  y={chartConfig.getY(-2.0) + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="#dc2626"
                  fontWeight="bold"
                >
                  -2.00
                </text>
                <text
                  x={chartConfig.width - chartConfig.padding.right + 4}
                  y={chartConfig.getY(-2.0) + 3}
                  textAnchor="start"
                  fontSize="8"
                  fill="#dc2626"
                >
                  Awas
                </text>
              </g>
            )}

            {/* +1.00 & +2.00 Wet Reference Lines */}
            {chartConfig.getY(1.0) != null && chartConfig.getY(1.0) >= chartConfig.padding.top && (
              <g className="grid-line wet-line">
                <line
                  x1={chartConfig.padding.left}
                  y1={chartConfig.getY(1.0)}
                  x2={chartConfig.width - chartConfig.padding.right}
                  y2={chartConfig.getY(1.0)}
                  stroke="#cbd5e1"
                  strokeWidth="1"
                  strokeDasharray="2,2"
                />
                <text
                  x={chartConfig.padding.left - 6}
                  y={chartConfig.getY(1.0) + 3}
                  textAnchor="end"
                  fontSize="8"
                  fill="#94a3b8"
                >
                  +1.00
                </text>
              </g>
            )}

            {/* Companion Series Path (e.g. 90D dashed) */}
            {companionPaths.map((dStr, idx) => (
              <path
                key={`comp-${idx}`}
                d={dStr}
                fill="none"
                stroke={activeSeries.companionColor}
                strokeWidth="1.8"
                strokeDasharray="4,3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}

            {/* Primary Series Path (e.g. 30D solid) */}
            {primaryPaths.map((dStr, idx) => (
              <path
                key={`prim-${idx}`}
                d={dStr}
                fill="none"
                stroke={activeSeries.primaryColor}
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}

            {/* Data Point Circles for Primary */}
            {activeSeries.primary.map((p, idx) => {
              if (p.value === null || p.value === undefined) return null;
              const cx = chartConfig.getX(idx);
              const cy = chartConfig.getY(p.value);
              const isDry = p.value <= -1.0;
              return (
                <circle
                  key={`pt-${idx}`}
                  cx={cx}
                  cy={cy}
                  r={hoveredPoint?.idx === idx && hoveredPoint?.series === 'primary' ? 5 : 2.5}
                  fill={isDry ? (p.value <= -1.5 ? '#ef4444' : '#f97316') : activeSeries.primaryColor}
                  stroke="#ffffff"
                  strokeWidth="1"
                  style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
                  onMouseEnter={() =>
                    setHoveredPoint({
                      idx,
                      series: 'primary',
                      label: activeSeries.primaryLabel,
                      date: p.date,
                      value: p.value,
                      x: cx,
                      y: cy,
                    })
                  }
                  onMouseLeave={() => setHoveredPoint(null)}
                />
              );
            })}

            {/* X-Axis Tick Labels (Sample 4 to 6 evenly spaced labels) */}
            {(() => {
              const count = activeSeries.primary.length;
              if (count === 0) return null;
              const step = Math.max(1, Math.floor(count / 5));
              const ticks = [];
              for (let i = 0; i < count; i += step) {
                ticks.push(i);
              }
              if (ticks[ticks.length - 1] !== count - 1) {
                ticks.push(count - 1);
              }
              return ticks.map((i) => {
                const pt = activeSeries.primary[i];
                if (!pt) return null;
                const cx = chartConfig.getX(i);
                // Simple date string: "Sep 2026" or "10/09"
                const parts = pt.date.split('-');
                let label = pt.date;
                if (parts.length === 3) {
                  label = `${parts[2]}/${parts[1]}`;
                } else if (parts.length === 2) {
                  label = `${parts[1]}/${parts[0].slice(2)}`;
                }
                return (
                  <text
                    key={`xtick-${i}`}
                    x={cx}
                    y={chartConfig.height - 12}
                    textAnchor="middle"
                    fontSize="9"
                    fill="#64748b"
                    fontFamily="monospace"
                  >
                    {label}
                  </text>
                );
              });
            })()}

            {/* Hover Tooltip Overlay */}
            {hoveredPoint && (
              <g className="chart-tooltip-group">
                <rect
                  x={Math.min(chartConfig.width - 150, Math.max(10, hoveredPoint.x - 70))}
                  y={Math.max(10, hoveredPoint.y - 45)}
                  width="140"
                  height="38"
                  rx="4"
                  fill="#1e293b"
                  opacity="0.95"
                />
                <text
                  x={Math.min(chartConfig.width - 150, Math.max(10, hoveredPoint.x - 70)) + 8}
                  y={Math.max(10, hoveredPoint.y - 45) + 14}
                  fontSize="9"
                  fill="#cbd5e1"
                  fontFamily="monospace"
                >
                  {formatDateIndo(hoveredPoint.date)}
                </text>
                <text
                  x={Math.min(chartConfig.width - 150, Math.max(10, hoveredPoint.x - 70)) + 8}
                  y={Math.max(10, hoveredPoint.y - 45) + 28}
                  fontSize="10"
                  fill="#38bdf8"
                  fontWeight="bold"
                >
                  SPI: {hoveredPoint.value >= 0 ? `+${hoveredPoint.value.toFixed(2)}` : hoveredPoint.value.toFixed(2)} ({getSpiLabel(hoveredPoint.value)})
                </text>
              </g>
            )}
          </svg>
        </div>
      )}
    </div>
  );
}
