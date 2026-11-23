import React, { useState } from 'react';
import {
  Lock,
  User,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  ShieldCheck,
} from 'lucide-react';
import { API_ENDPOINTS, INSTITUTION_SHORT_NAME, setStoredAuthToken } from '../config';

export default function LoginPage({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setErrorMsg('Harap masukkan username dan kata sandi.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const res = await fetch(API_ENDPOINTS.LOGIN, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          username: username.trim(),
          password: password,
        }),
      });

      if (!res.ok) {
        if (res.status === 401) {
          throw new Error('Username atau kata sandi tidak valid. Silakan periksa kembali kredensial Anda.');
        } else {
          throw new Error(`Terjadi kesalahan pada server (HTTP ${res.status}).`);
        }
      }

      const data = await res.json();
      if (data.success) {
        if (data.token) {
          setStoredAuthToken(data.token);
        }
        if (onLoginSuccess) {
          onLoginSuccess(data);
        }
      } else {
        throw new Error(data.message || 'Gagal masuk.');
      }
    } catch (err) {
      setErrorMsg(err.message || 'Gagal melakukan autentikasi.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page-container">
      <div className="login-card-surface">
        {/* Institutional Branding: Logo DSS-PIK & Identitas */}
        <div className="login-header-block">
          <div className="login-logo-wrapper">
            <img
              src="/DSS_PIK_logo_hitam.png"
              alt="Logo DSS-PIK"
              className="login-bmkg-logo"
            />
          </div>
          <div className="login-title-row">
            <h1 className="login-brand-title">DSS-PIK</h1>
          </div>
          <h2 className="login-app-title">
            <em>Decision Support System</em> - Peringatan Iklim Kepri
          </h2>
          <p className="login-institution-subtitle">
            {INSTITUTION_SHORT_NAME}
          </p>
        </div>

        {/* Error Alert Banner */}
        {errorMsg && (
          <div className="login-error-banner" role="alert">
            <AlertCircle size={18} className="login-error-icon" />
            <div className="login-error-text">{errorMsg}</div>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field-group">
            <label htmlFor="login-username" className="login-label">
              Username Operator
            </label>
            <div className="login-input-wrapper">
              <User size={16} className="login-input-icon" />
              <input
                id="login-username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Masukkan username"
                className="login-input"
                disabled={loading}
                autoFocus
                required
              />
            </div>
          </div>

          <div className="login-field-group">
            <label htmlFor="login-password" className="login-label">
              Kata Sandi
            </label>
            <div className="login-input-wrapper">
              <Lock size={16} className="login-input-icon" />
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Masukkan kata sandi"
                className="login-input"
                disabled={loading}
                required
              />
              <button
                type="button"
                className="btn-toggle-password"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                title={showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="btn-login-submit"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 size={16} className="spin" />
                <span>Memverifikasi Kredensial...</span>
              </>
            ) : (
              <>
                <ShieldCheck size={18} />
                <span>Masuk ke Sistem</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
