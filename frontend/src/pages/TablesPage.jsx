import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getTables, getQRToken, generateQRToken, revokeQRToken } from '../services/api';

export default function TablesPage({ currentUser }) {
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'available', 'occupied', 'reserved'
  const [searchQuery, setSearchQuery] = useState('');

  // QR Modal State
  const [selectedTable, setSelectedTable] = useState(null);
  const [isQRModalOpen, setIsQRModalOpen] = useState(false);
  const [qrData, setQrData] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [qrActionLoading, setQrActionLoading] = useState(false);
  const [qrError, setQrError] = useState(null);
  const [copied, setCopied] = useState(false);

  const isManagerOrAdmin = currentUser?.role === 'manager' || currentUser?.role === 'admin';

  const loadTables = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getTables();
      setTables(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load tables:', err);
      setError(err.message || 'Failed to connect to table management service.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTables();
  }, [loadTables]);

  // Derived floor status metrics calculated from fetched records
  const totalTables = tables.length;
  const availableCount = tables.filter((t) => t.status === 'available').length;
  const occupiedCount = tables.filter((t) => t.status === 'occupied').length;
  const reservedCount = tables.filter((t) => t.status === 'reserved').length;
  const totalCapacity = tables.reduce((sum, t) => sum + (Number(t.capacity) || 0), 0);

  // Filtered tables for floor grid display
  const filteredTables = useMemo(() => {
    return tables.filter((table) => {
      if (statusFilter !== 'all' && table.status !== statusFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchesNumber = table.table_number && table.table_number.toLowerCase().includes(query);
        const matchesStatus = table.status && table.status.toLowerCase().includes(query);
        return matchesNumber || matchesStatus;
      }
      return true;
    });
  }, [tables, statusFilter, searchQuery]);

  // QR Code Modal Handlers
  const handleOpenQRModal = async (table) => {
    setSelectedTable(table);
    setIsQRModalOpen(true);
    setQrLoading(true);
    setQrError(null);
    setCopied(false);

    try {
      const data = await getQRToken(table.id);
      setQrData(data);
    } catch (err) {
      if (err.status === 404) {
        setQrData(null); // No token generated yet
      } else {
        setQrError(err.message || 'Failed to load QR token details.');
      }
    } finally {
      setQrLoading(false);
    }
  };

  const handleCloseQRModal = () => {
    setIsQRModalOpen(false);
    setSelectedTable(null);
    setQrData(null);
    setQrError(null);
    setCopied(false);
  };

  const handleGenerateQR = async () => {
    if (!selectedTable) return;
    setQrActionLoading(true);
    setQrError(null);

    try {
      const data = await generateQRToken(selectedTable.id);
      setQrData(data);
      // Update table item in local state
      setTables((prev) =>
        prev.map((t) => (t.id === selectedTable.id ? { ...t, qr_token: data.qr_token } : t))
      );
    } catch (err) {
      setQrError(err.message || 'Failed to generate QR token.');
    } finally {
      setQrActionLoading(false);
    }
  };

  const handleRevokeQR = async () => {
    if (!selectedTable) return;
    if (!window.confirm(`Revoke QR code for Table ${selectedTable.table_number}? Scans of the physical printout will no longer work.`)) {
      return;
    }
    setQrActionLoading(true);
    setQrError(null);

    try {
      await revokeQRToken(selectedTable.id);
      setQrData(null);
      // Update table item in local state
      setTables((prev) =>
        prev.map((t) => (t.id === selectedTable.id ? { ...t, qr_token: null } : t))
      );
    } catch (err) {
      setQrError(err.message || 'Failed to revoke QR token.');
    } finally {
      setQrActionLoading(false);
    }
  };

  const handleCopyURL = () => {
    if (!qrData?.order_url) return;
    const fullUrl = qrData.order_url.startsWith('http')
      ? qrData.order_url
      : `${window.location.origin}${qrData.order_url}`;
    navigator.clipboard.writeText(fullUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }).catch(() => {
      setCopied(false);
    });
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="page-content">
      {/* Floor Overview KPI Metric Cards */}
      <section className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Dining Tables</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 18v3" />
                <path d="M20 18v3" />
                <path d="M2 14h20" />
                <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : totalTables}</div>
          <div className="metric-subtext">{loading ? 'Loading...' : `${totalCapacity} total seat capacity`}</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Available Tables</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : availableCount}</div>
          <div className="metric-subtext">Ready for walk-in seating</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Occupied</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : occupiedCount}</div>
          <div className="metric-subtext">Active dining parties</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Reserved</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
                <line x1="16" x2="16" y1="2" y2="6" />
                <line x1="8" x2="8" y1="2" y2="6" />
                <line x1="3" x2="21" y1="10" y2="10" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : reservedCount}</div>
          <div className="metric-subtext">Booked for upcoming party</div>
        </div>
      </section>

      {/* Toolbar: Search, Refresh & Status Filter Segmented Pills */}
      <section className="filters-section">
        <div className="filters-top-row">
          <div className="search-bar">
            <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Search by table number (e.g. T-1, Patio, Booth)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery('')}
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          <div className="header-actions">
            <button
              type="button"
              className="btn btn-secondary btn-icon"
              onClick={loadTables}
              disabled={loading}
              title="Refresh table occupancy from server"
            >
              <svg
                className={`refresh-icon ${loading ? 'spin' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <path d="M3 3v5h5" />
                <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
                <path d="M16 16h5v5" />
              </svg>
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Status Filter Segmented Pills */}
        <div className="category-pills-bar">
          <button
            type="button"
            className={`category-pill ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            All Tables ({loading ? '…' : totalTables})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'available' ? 'active' : ''}`}
            onClick={() => setStatusFilter('available')}
          >
            Available ({loading ? '…' : availableCount})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'occupied' ? 'active' : ''}`}
            onClick={() => setStatusFilter('occupied')}
          >
            Occupied ({loading ? '…' : occupiedCount})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'reserved' ? 'active' : ''}`}
            onClick={() => setStatusFilter('reserved')}
          >
            Reserved ({loading ? '…' : reservedCount})
          </button>
        </div>
      </section>

      {/* Floor Overview Grid or State Views */}
      {error ? (
        <div className="state-card state-error">
          <div className="state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div className="state-body">
            <h3>Unable to Load Tables</h3>
            <p className="state-message">{error}</p>
            <button type="button" className="btn btn-primary" onClick={loadTables}>
              Retry Connection
            </button>
          </div>
        </div>
      ) : loading ? (
        <div className="tables-grid">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="table-card skeleton-card">
              <div className="skeleton-line skeleton-badge" />
              <div className="skeleton-line skeleton-title" />
              <div className="skeleton-line skeleton-desc short" />
              <div className="skeleton-footer">
                <div className="skeleton-line skeleton-pill" />
                <div className="skeleton-line skeleton-pill" />
              </div>
            </div>
          ))}
        </div>
      ) : tables.length === 0 ? (
        <div className="state-card state-empty">
          <div className="state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 18v3" />
              <path d="M20 18v3" />
              <path d="M2 14h20" />
              <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
            </svg>
          </div>
          <div className="state-body">
            <h3>No Tables Configured</h3>
            <p className="state-message">
              There are currently no dining tables in the database.
            </p>
            <button type="button" className="btn btn-secondary" onClick={loadTables}>
              Refresh Floor Plan
            </button>
          </div>
        </div>
      ) : filteredTables.length === 0 ? (
        <div className="state-card state-empty">
          <div className="state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <div className="state-body">
            <h3>No Tables Match Your Filter</h3>
            <p className="state-message">
              No tables currently match the status <strong>"{statusFilter}"</strong>
              {searchQuery ? ` and search "${searchQuery}"` : ''}.
            </p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setStatusFilter('all');
                setSearchQuery('');
              }}
            >
              Clear Filters
            </button>
          </div>
        </div>
      ) : (
        <div className="tables-grid">
          {filteredTables.map((table) => {
            const statusConfig = {
              available: {
                label: 'Available',
                badgeClass: 'status-pill-available',
                cardClass: 'table-card-available',
                desc: 'Ready for guest seating',
              },
              occupied: {
                label: 'Occupied',
                badgeClass: 'status-pill-occupied',
                cardClass: 'table-card-occupied',
                desc: 'Dining party currently seated',
              },
              reserved: {
                label: 'Reserved',
                badgeClass: 'status-pill-reserved',
                cardClass: 'table-card-reserved',
                desc: 'Reserved for upcoming booking',
              },
            }[table.status] || {
              label: table.status,
              badgeClass: 'status-pill-unavailable',
              cardClass: '',
              desc: 'Status unknown',
            };

            const hasActiveQR = Boolean(table.qr_token);

            return (
              <article key={table.id} className={`table-card ${statusConfig.cardClass}`}>
                <header className="table-card-top">
                  <div className="table-number-wrap">
                    <span className="table-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M4 18v3" />
                        <path d="M20 18v3" />
                        <path d="M2 14h20" />
                        <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
                      </svg>
                    </span>
                    <h3 className="table-title">{table.table_number}</h3>
                  </div>

                  <span className={`status-pill ${statusConfig.badgeClass}`}>
                    <span className="pill-dot" />
                    {statusConfig.label}
                  </span>
                </header>

                <div className="table-card-body">
                  <div className="table-capacity-row">
                    <span className="capacity-label">Capacity:</span>
                    <span className="capacity-badge">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                        <circle cx="9" cy="7" r="4" />
                      </svg>
                      <strong>{table.capacity}</strong> {table.capacity === 1 ? 'Guest' : 'Guests'}
                    </span>
                  </div>
                  <p className="table-status-desc">{statusConfig.desc}</p>
                </div>

                <footer className="table-card-bottom" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="table-id-tag">#{table.id}</span>
                    <button
                      type="button"
                      className={`btn-table-qr-badge ${hasActiveQR ? 'has-qr' : 'no-qr'}`}
                      onClick={() => handleOpenQRModal(table)}
                      title="Manage QR Code Ordering for this table"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13">
                        <rect x="3" y="3" width="6" height="6" rx="1" />
                        <rect x="15" y="3" width="6" height="6" rx="1" />
                        <rect x="3" y="15" width="6" height="6" rx="1" />
                        <path d="M15 15h2v2h-2z" />
                        <path d="M19 19h2v2h-2z" />
                        <path d="M15 19h2v2h-2z" />
                        <path d="M19 15h2v2h-2z" />
                      </svg>
                      <span>{hasActiveQR ? 'QR Active' : 'QR Setup'}</span>
                    </button>
                  </div>

                  <span className="table-meta">
                    {table.updated_at
                      ? `${new Date(table.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                      : 'Active'}
                  </span>
                </footer>
              </article>
            );
          })}
        </div>
      )}

      {/* Staff QR Code Management Modal */}
      {isQRModalOpen && selectedTable && (
        <div className="modal-backdrop" onClick={handleCloseQRModal}>
          <div className="modal-dialog qr-mgmt-modal" onClick={(e) => e.stopPropagation()}>
            <header className="modal-header">
              <div>
                <h3 className="modal-title">QR Ordering · {selectedTable.table_number}</h3>
                <p className="modal-subtitle">
                  {selectedTable.capacity} Seats · Status: <span style={{ textTransform: 'capitalize' }}>{selectedTable.status}</span>
                </p>
              </div>
              <button type="button" className="modal-close-btn" onClick={handleCloseQRModal}>
                ✕
              </button>
            </header>

            <div className="modal-body qr-mgmt-body">
              {qrLoading ? (
                <div style={{ padding: '3rem', textAlign: 'center' }}>
                  <div className="state-spinner" />
                  <p style={{ marginTop: '1rem', color: '#888' }}>Loading QR token details…</p>
                </div>
              ) : qrError ? (
                <div className="state-card state-error" style={{ margin: '1rem 0' }}>
                  <p className="state-message">{qrError}</p>
                </div>
              ) : qrData?.qr_token ? (
                <>
                  {/* Active QR View */}
                  <div className="qr-mgmt-card-wrap">
                    {/* Printable Card Area */}
                    <div className="qr-print-card" id="qr-printable-area">
                      <div className="qr-print-brand">Brew &amp; Co.</div>
                      <div className="qr-print-tagline">Artisanal Café &amp; Bakery</div>
                      <div className="qr-print-table-title">{selectedTable.table_number}</div>
                      <div className="qr-print-code-box">
                        <img
                          src={`https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(
                            qrData.order_url.startsWith('http')
                              ? qrData.order_url
                              : `${window.location.origin}${qrData.order_url}`
                          )}`}
                          alt={`QR code for Table ${selectedTable.table_number}`}
                          className="qr-print-image"
                        />
                      </div>
                      <div className="qr-print-instructions">
                        Scan to browse our menu &amp; order from your seat.
                      </div>
                      <div className="qr-print-subtext">No app download required</div>
                    </div>

                    {/* Metadata & Direct URL */}
                    <div className="qr-mgmt-details">
                      <div className="qr-mgmt-detail-row">
                        <span className="qr-mgmt-label">Status:</span>
                        <span className="qr-status-pill qr-status-pill-served">Active</span>
                      </div>
                      {qrData.qr_token_created_at && (
                        <div className="qr-mgmt-detail-row">
                          <span className="qr-mgmt-label">Created:</span>
                          <span>{new Date(qrData.qr_token_created_at).toLocaleString()}</span>
                        </div>
                      )}
                      <div className="qr-mgmt-detail-row">
                        <span className="qr-mgmt-label">Order URL:</span>
                        <span className="qr-url-text" title={qrData.order_url}>
                          {qrData.order_url}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="qr-mgmt-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-icon"
                      onClick={handleCopyURL}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                      </svg>
                      <span>{copied ? 'Copied Link!' : 'Copy Link'}</span>
                    </button>

                    <button
                      type="button"
                      className="btn btn-primary btn-icon"
                      onClick={handlePrint}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
                        <polyline points="6 9 6 2 18 2 18 9" />
                        <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                        <rect x="6" y="14" width="12" height="8" />
                      </svg>
                      <span>Print Stand Card</span>
                    </button>
                  </div>

                  {/* Manager / Admin Token Operations */}
                  {isManagerOrAdmin && (
                    <div className="qr-mgmt-danger-zone">
                      <div className="qr-mgmt-danger-title">Manager Actions</div>
                      <div className="qr-mgmt-danger-buttons">
                        <button
                          type="button"
                          className="btn btn-outline-warning"
                          onClick={handleGenerateQR}
                          disabled={qrActionLoading}
                        >
                          {qrActionLoading ? 'Rotating…' : 'Rotate / Regenerate Token'}
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline-danger"
                          onClick={handleRevokeQR}
                          disabled={qrActionLoading}
                        >
                          {qrActionLoading ? 'Revoking…' : 'Revoke QR Code'}
                        </button>
                      </div>
                      <small className="qr-mgmt-help-text">
                        Rotating or revoking will immediately deactivate previously printed QR codes for this table.
                      </small>
                    </div>
                  )}
                </>
              ) : (
                /* No Active Token View */
                <div className="qr-mgmt-empty">
                  <div className="qr-mgmt-empty-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
                      <rect x="3" y="3" width="7" height="7" />
                      <rect x="14" y="3" width="7" height="7" />
                      <rect x="3" y="14" width="7" height="7" />
                      <rect x="14" y="14" width="7" height="7" />
                    </svg>
                  </div>
                  <h4>No Active QR Token</h4>
                  <p>
                    Table {selectedTable.table_number} does not have an active QR ordering token.
                    Generate one to allow customers to scan and place dine-in orders directly from their seats.
                  </p>

                  {isManagerOrAdmin ? (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleGenerateQR}
                      disabled={qrActionLoading}
                    >
                      {qrActionLoading ? 'Generating…' : 'Generate QR Code Now'}
                    </button>
                  ) : (
                    <p style={{ color: '#888', fontStyle: 'italic', fontSize: '0.85rem' }}>
                      Manager or administrator privileges are required to generate QR codes.
                    </p>
                  )}
                </div>
              )}
            </div>

            <footer className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={handleCloseQRModal}>
                Close
              </button>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
