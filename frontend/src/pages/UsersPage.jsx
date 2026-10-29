import React, { useState, useEffect, useCallback } from 'react';
import { getUsers, createUser, updateUser, deleteUser } from '../services/api';
import { formatDateTime } from '../utils/formatters';

const ROLES = [
  { id: 'admin', label: 'Administrator', desc: 'Full system access & staff management' },
  { id: 'manager', label: 'Store Manager', desc: 'Catalog, floor plan & operational audits' },
  { id: 'cashier', label: 'Lead Cashier', desc: 'POS checkout, seating & ticket inspection' },
  { id: 'kitchen', label: 'Kitchen Chef', desc: 'Kitchen ticket queue & preparation updates' },
];

export default function UsersPage({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    role: 'cashier',
    password: '',
    is_active: true,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [modalError, setModalError] = useState(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load users:', err);
      setError(err.message || 'Unable to load user accounts.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleOpenCreate = () => {
    setEditingUser(null);
    setFormData({
      username: '',
      email: '',
      full_name: '',
      role: 'cashier',
      password: '',
      is_active: true,
    });
    setModalError(null);
    setShowModal(true);
  };

  const handleOpenEdit = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      full_name: user.full_name || '',
      role: user.role,
      password: '',
      is_active: user.is_active,
    });
    setModalError(null);
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setModalError(null);

    try {
      if (editingUser) {
        // Update user
        const updatePayload = {
          email: formData.email.trim(),
          full_name: formData.full_name.trim() || null,
          role: formData.role,
          is_active: formData.is_active,
        };
        if (formData.password.trim()) {
          updatePayload.password = formData.password.trim();
        }

        const updated = await updateUser(editingUser.id, updatePayload);
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
        setSuccessMsg(`Account '${updated.username}' updated successfully.`);
      } else {
        // Create user
        if (!formData.password || formData.password.length < 8) {
          setModalError('Password must be at least 8 characters long.');
          setIsSubmitting(false);
          return;
        }

        const created = await createUser({
          username: formData.username.trim(),
          email: formData.email.trim(),
          full_name: formData.full_name.trim() || null,
          password: formData.password,
          role: formData.role,
          is_active: formData.is_active,
        });
        setUsers((prev) => [...prev, created]);
        setSuccessMsg(`User account '${created.username}' created successfully.`);
      }
      setShowModal(false);
    } catch (err) {
      console.error('Save user failed:', err);
      setModalError(err.message || 'Failed to save user account.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (user) => {
    if (user.id === currentUser?.id) {
      alert('You cannot delete your own logged-in administrator account.');
      return;
    }

    if (!window.confirm(`Are you sure you want to delete user '${user.username}'? This cannot be undone.`)) {
      return;
    }

    try {
      await deleteUser(user.id);
      setUsers((prev) => prev.filter((u) => u.id !== user.id));
      setSuccessMsg(`User '${user.username}' deleted.`);
    } catch (err) {
      console.error('Delete user failed:', err);
      setError(err.message || 'Failed to delete user.');
    }
  };

  return (
    <div className="page-content users-page">
      {/* Top Header */}
      <section className="history-top-bar">
        <div className="history-top-info">
          <h2 className="history-heading">User Accounts & Roles</h2>
          <p className="history-subheading">
            Manage staff credentials, assign station roles, and regulate access permissions.
          </p>
        </div>

        <div className="history-top-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleOpenCreate}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="btn-icon">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Add Staff Member</span>
          </button>
        </div>
      </section>

      {/* Alert Notices */}
      {error && (
        <div className="alert-banner alert-danger mb-4">
          <div className="alert-content">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{error}</span>
          </div>
          <button type="button" className="alert-close" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {successMsg && (
        <div className="alert-banner alert-success mb-4">
          <div className="alert-content">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span>{successMsg}</span>
          </div>
          <button type="button" className="alert-close" onClick={() => setSuccessMsg(null)}>✕</button>
        </div>
      )}

      {/* Users Table */}
      <section className="history-table-container">
        {loading ? (
          <div className="history-state-box">
            <div className="state-spinner" />
            <h3>Loading Staff Accounts...</h3>
          </div>
        ) : (
          <div className="history-table-wrap">
            <table className="history-orders-table">
              <thead>
                <tr>
                  <th>User / Username</th>
                  <th>Full Name</th>
                  <th>Email</th>
                  <th>Assigned Role</th>
                  <th className="text-center">Status</th>
                  <th>Created At</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isCurrent = u.id === currentUser?.id;
                  return (
                    <tr key={u.id} className="history-order-row">
                      <td className="cell-order-number">
                        <div className="order-num-box">
                          <svg className="order-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                            <circle cx="12" cy="7" r="4" />
                          </svg>
                          <span className="order-num-text">{u.username}</span>
                          {isCurrent && <span className="current-user-tag">You</span>}
                        </div>
                      </td>
                      <td className="font-medium">{u.full_name || '—'}</td>
                      <td className="text-muted">{u.email}</td>
                      <td>
                        <span className={`role-badge role-${u.role}`}>
                          {u.role.toUpperCase()}
                        </span>
                      </td>
                      <td className="text-center">
                        <span className={`status-pill ${u.is_active ? 'status-pill-available' : 'status-pill-unavailable'}`}>
                          <span className="pill-dot" />
                          {u.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="cell-timestamp text-muted">
                        {formatDateTime(u.created_at)}
                      </td>
                      <td className="cell-actions text-right">
                        <div className="btn-group-sm">
                          <button
                            type="button"
                            className="btn btn-outline-secondary btn-xs"
                            onClick={() => handleOpenEdit(u)}
                          >
                            Edit
                          </button>
                          {!isCurrent && (
                            <button
                              type="button"
                              className="btn btn-outline-danger btn-xs ml-1"
                              onClick={() => handleDelete(u)}
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Create / Edit User Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {editingUser ? `Edit User: ${editingUser.username}` : 'Add New Staff Member'}
              </h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setShowModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {modalError && (
                  <div className="alert-banner alert-danger mb-3">
                    <div className="alert-content">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="8" x2="12" y2="12" />
                        <line x1="12" y1="16" x2="12.01" y2="16" />
                      </svg>
                      <span>{modalError}</span>
                    </div>
                  </div>
                )}

                {!editingUser && (
                  <div className="form-group mb-3">
                    <label className="form-label">Username</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. chef_john"
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                      required
                    />
                  </div>
                )}

                <div className="form-group mb-3">
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="e.g. staff@restaurant.pos"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group mb-3">
                  <label className="form-label">Full Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. John Doe"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  />
                </div>

                <div className="form-group mb-3">
                  <label className="form-label">
                    {editingUser ? 'Change Password (leave empty to keep current)' : 'Password (min 8 chars)'}
                  </label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder={editingUser ? '••••••••' : 'Enter initial password'}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    required={!editingUser}
                  />
                </div>

                <div className="form-group mb-3">
                  <label className="form-label">Staff Role & Station</label>
                  <select
                    className="form-select"
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  >
                    {ROLES.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.label} — {r.desc}
                      </option>
                    ))}
                  </select>
                </div>

                {editingUser && editingUser.id !== currentUser?.id && (
                  <div className="form-group mb-2">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={formData.is_active}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      />
                      <span>Account Active (permits station sign-in)</span>
                    </label>
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowModal(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Saving...' : editingUser ? 'Update Staff Account' : 'Create Staff Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
