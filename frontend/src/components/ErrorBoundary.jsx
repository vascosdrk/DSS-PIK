import React from 'react';
import { AlertTriangle, RefreshCw, Home, ChevronDown, ChevronUp } from 'lucide-react';

/**
 * Institutional BMKG Error Boundary Component for DSS-PIK.
 * Prevents runtime rendering exceptions in subtrees from causing blank white pages.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[DSS-PIK ErrorBoundary Caught Error]:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback({
          error: this.state.error,
          resetError: this.handleReset,
        });
      }

      const componentName = this.props.name || 'Komponen Sistem';

      return (
        <div className="error-boundary-container" role="alert">
          <div className="error-boundary-card">
            <div className="error-boundary-header">
              <div className="error-boundary-icon-box">
                <AlertTriangle size={24} className="text-amber-600" />
              </div>
              <div>
                <h3 className="error-boundary-title">
                  Terjadi Kendala pada {componentName}
                </h3>
                <p className="error-boundary-subtitle">
                  Sistem mendeteksi galat saat memuat tampilan ini. Operasional backend dan data tetap aman.
                </p>
              </div>
            </div>

            <div className="error-boundary-body">
              <div className="error-boundary-msg-box">
                <span className="font-semibold text-slate-700">Pesan Kesalahan:</span>
                <p className="font-mono text-xs text-rose-700 mt-1 break-words">
                  {this.state.error?.message || 'Galat rendering antarmuka tidak terduga.'}
                </p>
              </div>

              {this.state.errorInfo && (
                <div className="error-boundary-details-block">
                  <button
                    type="button"
                    className="btn-toggle-error-details"
                    onClick={() => this.setState((prev) => ({ showDetails: !prev.showDetails }))}
                  >
                    <span>{this.state.showDetails ? 'Sembunyikan Detail Teknis' : 'Tampilkan Detail Teknis (Log Stack)'}</span>
                    {this.state.showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>

                  {this.state.showDetails && (
                    <pre className="error-boundary-stack font-mono text-xs">
                      {this.state.error?.stack}
                      {'\n\nKomponen yang terdampak:\n'}
                      {this.state.errorInfo.componentStack}
                    </pre>
                  )}
                </div>
              )}
            </div>

            <div className="error-boundary-actions">
              <button
                type="button"
                className="btn-eb-action btn-eb-retry"
                onClick={this.handleReset}
              >
                <RefreshCw size={14} />
                <span>Coba Muat Ulang Komponen</span>
              </button>

              <button
                type="button"
                className="btn-eb-action btn-eb-reload"
                onClick={this.handleReload}
              >
                <span>Segarkan Seluruh Dashboard</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

