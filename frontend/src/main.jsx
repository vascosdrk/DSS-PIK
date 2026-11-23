import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import './App.css';
import './cobalt-theme.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary name="Aplikasi Utama DSS-PIK">
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
