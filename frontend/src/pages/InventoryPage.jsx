import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  getInventorySummary,
  getIngredients,
  createIngredient,
  updateIngredient,
  deleteIngredient,
  adjustIngredientStock,
  getStockMovements,
  getRecipes,
  createRecipeItem,
  deleteRecipeItem,
} from '../services/api';

const STATUS_PILL_CONFIG = {
  in_stock: { label: 'In Stock', className: 'status-pill-available' },
  low_stock: { label: 'Low Stock', className: 'status-pill-reserved' },
  out_of_stock: { label: 'Out of Stock', className: 'status-pill-occupied' },
};

export default function InventoryPage({ currentUser }) {
  const isManagerOrAdmin = currentUser && ['admin', 'manager'].includes(currentUser.role);

  // Active View Tab: 'ingredients' | 'recipes' | 'movements'
  const [activeSubTab, setActiveSubTab] = useState('ingredients');

  // Summary Metrics
  const [summary, setSummary] = useState({
    total_active_ingredients: 0,
    low_stock_count: 0,
    out_of_stock_count: 0,
    total_movements_recorded: 0,
  });

  // Ingredients State
  const [ingredients, setIngredients] = useState([]);
  const [loadingIngredients, setLoadingIngredients] = useState(true);
  const [ingredientSearch, setIngredientSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'in_stock', 'low_stock', 'out_of_stock'

  // Recipes State
  const [recipesList, setRecipesList] = useState([]);
  const [loadingRecipes, setLoadingRecipes] = useState(false);
  const [recipeSearch, setRecipeSearch] = useState('');
  const [recipeFilter, setRecipeFilter] = useState('all'); // 'all', 'configured', 'missing'

  // Movements State
  const [movements, setMovements] = useState([]);
  const [loadingMovements, setLoadingMovements] = useState(false);
  const [movementTypeFilter, setMovementTypeFilter] = useState('all');

  // Global Notification / Error
  const [actionSuccess, setActionSuccess] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Modals
  const [ingredientModalOpen, setIngredientModalOpen] = useState(false);
  const [editingIngredient, setEditingIngredient] = useState(null); // null = create
  const [ingredientFormData, setIngredientFormData] = useState({
    name: '',
    description: '',
    unit: 'g',
    initial_stock: '0',
    minimum_stock: '100',
    unit_cost: '',
  });

  const [adjustModalOpen, setAdjustModalOpen] = useState(false);
  const [adjustingIngredient, setAdjustingIngredient] = useState(null);
  const [adjustFormData, setAdjustFormData] = useState({
    adjustment_type: 'restock', // 'restock', 'waste', 'manual_correction'
    quantity: '',
    reason: '',
  });
  const [confirmingAdjust, setConfirmingAdjust] = useState(false);

  const [recipeModalOpen, setRecipeModalOpen] = useState(false);
  const [selectedMenuItemForRecipe, setSelectedMenuItemForRecipe] = useState(null);
  const [recipeFormData, setRecipeFormData] = useState({
    ingredient_id: '',
    quantity: '',
    unit: 'g',
  });

  // ── Data Loading Callbacks ──────────────────────────────────────────────

  const loadSummary = useCallback(async () => {
    try {
      const data = await getInventorySummary();
      setSummary(data);
    } catch (err) {
      console.warn('Failed to load inventory summary:', err);
    }
  }, []);

  const loadIngredients = useCallback(async () => {
    setLoadingIngredients(true);
    try {
      const data = await getIngredients();
      setIngredients(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load ingredients:', err);
      setActionError('Unable to load ingredient stock balances.');
    } finally {
      setLoadingIngredients(false);
    }
  }, []);

  const loadRecipes = useCallback(async () => {
    setLoadingRecipes(true);
    try {
      const data = await getRecipes();
      setRecipesList(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load recipes:', err);
      setActionError('Unable to load recipe catalog.');
    } finally {
      setLoadingRecipes(false);
    }
  }, []);

  const loadMovements = useCallback(async () => {
    setLoadingMovements(true);
    try {
      const params = movementTypeFilter !== 'all' ? { movement_type: movementTypeFilter } : {};
      const data = await getStockMovements(params);
      setMovements(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load stock movements:', err);
      setActionError('Unable to load movement ledger.');
    } finally {
      setLoadingMovements(false);
    }
  }, [movementTypeFilter]);

  // Initial load & Tab switching
  useEffect(() => {
    loadSummary();
    loadIngredients();
  }, [loadSummary, loadIngredients]);

  useEffect(() => {
    if (activeSubTab === 'recipes') {
      loadRecipes();
    } else if (activeSubTab === 'movements') {
      loadMovements();
    }
  }, [activeSubTab, loadRecipes, loadMovements]);

  // Auto-dismiss alert banner after 5s
  useEffect(() => {
    if (actionSuccess) {
      const timer = setTimeout(() => setActionSuccess(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [actionSuccess]);

  // ── Filtered Ingredients ────────────────────────────────────────────────

  const filteredIngredients = useMemo(() => {
    return ingredients.filter((item) => {
      if (statusFilter !== 'all' && item.stock_status !== statusFilter) {
        return false;
      }
      if (ingredientSearch.trim()) {
        const q = ingredientSearch.toLowerCase().trim();
        const matchName = item.name && item.name.toLowerCase().includes(q);
        const matchDesc = item.description && item.description.toLowerCase().includes(q);
        return matchName || matchDesc;
      }
      return true;
    });
  }, [ingredients, statusFilter, ingredientSearch]);

  // ── Filtered Recipes ────────────────────────────────────────────────────

  const filteredRecipes = useMemo(() => {
    return recipesList.filter((item) => {
      if (recipeFilter === 'configured' && !item.has_recipe) return false;
      if (recipeFilter === 'missing' && item.has_recipe) return false;
      if (recipeSearch.trim()) {
        const q = recipeSearch.toLowerCase().trim();
        const matchName = item.menu_item_name && item.menu_item_name.toLowerCase().includes(q);
        const matchCat = item.category_name && item.category_name.toLowerCase().includes(q);
        return matchName || matchCat;
      }
      return true;
    });
  }, [recipesList, recipeFilter, recipeSearch]);

  // ── Ingredient Modal Handlers ───────────────────────────────────────────

  const handleOpenCreateIngredient = () => {
    setEditingIngredient(null);
    setIngredientFormData({
      name: '',
      description: '',
      unit: 'g',
      initial_stock: '0',
      minimum_stock: '100',
      unit_cost: '',
    });
    setIngredientModalOpen(true);
  };

  const handleOpenEditIngredient = (ing) => {
    setEditingIngredient(ing);
    setIngredientFormData({
      name: ing.name,
      description: ing.description || '',
      unit: ing.unit,
      initial_stock: String(ing.current_stock),
      minimum_stock: String(ing.minimum_stock),
      unit_cost: ing.unit_cost !== null ? String(ing.unit_cost) : '',
    });
    setIngredientModalOpen(true);
  };

  const handleSaveIngredient = async (e) => {
    e.preventDefault();
    setActionError(null);

    const payload = {
      name: ingredientFormData.name.trim(),
      description: ingredientFormData.description.trim() || null,
      unit: ingredientFormData.unit,
      minimum_stock: parseFloat(ingredientFormData.minimum_stock) || 0,
      unit_cost: ingredientFormData.unit_cost ? parseFloat(ingredientFormData.unit_cost) : null,
    };

    try {
      if (editingIngredient) {
        await updateIngredient(editingIngredient.id, payload);
        setActionSuccess(`Updated ingredient "${payload.name}".`);
      } else {
        payload.initial_stock = parseFloat(ingredientFormData.initial_stock) || 0;
        await createIngredient(payload);
        setActionSuccess(`Created new ingredient "${payload.name}".`);
      }
      setIngredientModalOpen(false);
      loadIngredients();
      loadSummary();
    } catch (err) {
      console.error('Error saving ingredient:', err);
      setActionError(err.message || 'Failed to save ingredient.');
    }
  };

  const handleDeleteIngredient = async (ing) => {
    if (!window.confirm(`Are you sure you want to remove or deactivate "${ing.name}"?`)) {
      return;
    }
    setActionError(null);
    try {
      await deleteIngredient(ing.id);
      setActionSuccess(`Ingredient "${ing.name}" processed successfully.`);
      loadIngredients();
      loadSummary();
    } catch (err) {
      console.error('Error deleting ingredient:', err);
      setActionError(err.message || 'Failed to delete ingredient.');
    }
  };

  // ── Stock Adjustment Handlers ───────────────────────────────────────────

  const handleOpenAdjustModal = (ing, defaultType = 'restock') => {
    setAdjustingIngredient(ing);
    setAdjustFormData({
      adjustment_type: defaultType,
      quantity: '',
      reason: defaultType === 'restock' ? 'Delivery from roastery/supplier' : 'Kitchen waste/spoilage',
    });
    setConfirmingAdjust(false);
    setAdjustModalOpen(true);
  };

  const handleSaveAdjustment = async (e) => {
    e.preventDefault();
    if (!confirmingAdjust) {
      setConfirmingAdjust(true);
      return;
    }

    setActionError(null);
    const qty = parseFloat(adjustFormData.quantity);
    if (!qty || qty <= 0) {
      setActionError('Please enter a valid quantity greater than zero.');
      setConfirmingAdjust(false);
      return;
    }

    try {
      await adjustIngredientStock(adjustingIngredient.id, {
        adjustment_type: adjustFormData.adjustment_type,
        quantity: qty,
        reason: adjustFormData.reason.trim() || undefined,
      });

      const label = adjustFormData.adjustment_type === 'restock' ? 'Restocked' : 'Waste recorded for';
      setActionSuccess(`${label} ${qty} ${adjustingIngredient.unit} of "${adjustingIngredient.name}".`);
      setAdjustModalOpen(false);
      setConfirmingAdjust(false);
      loadIngredients();
      loadSummary();
      if (activeSubTab === 'movements') loadMovements();
    } catch (err) {
      console.error('Adjustment failed:', err);
      setActionError(err.message || 'Failed to complete stock adjustment.');
      setConfirmingAdjust(false);
    }
  };

  // ── Recipe Modal Handlers ───────────────────────────────────────────────

  const handleOpenRecipeModal = (menuItem) => {
    setSelectedMenuItemForRecipe(menuItem);
    // Find first active ingredient as default
    const firstIng = ingredients[0];
    setRecipeFormData({
      ingredient_id: firstIng ? String(firstIng.id) : '',
      quantity: '10',
      unit: firstIng ? firstIng.unit : 'g',
    });
    setRecipeModalOpen(true);
  };

  const handleIngredientSelectChange = (e) => {
    const ingId = parseInt(e.target.value, 10);
    const found = ingredients.find((i) => i.id === ingId);
    setRecipeFormData((prev) => ({
      ...prev,
      ingredient_id: e.target.value,
      unit: found ? found.unit : 'g',
    }));
  };

  const handleAddRecipeItem = async (e) => {
    e.preventDefault();
    setActionError(null);

    const ingId = parseInt(recipeFormData.ingredient_id, 10);
    const qty = parseFloat(recipeFormData.quantity);

    if (!ingId || !qty || qty <= 0) {
      setActionError('Please select an ingredient and enter a positive quantity.');
      return;
    }

    try {
      await createRecipeItem({
        menu_item_id: selectedMenuItemForRecipe.menu_item_id,
        ingredient_id: ingId,
        quantity: qty,
        unit: recipeFormData.unit,
      });

      setActionSuccess(`Added ingredient to "${selectedMenuItemForRecipe.menu_item_name}".`);
      setRecipeModalOpen(false);
      loadRecipes();
    } catch (err) {
      console.error('Error adding recipe item:', err);
      setActionError(err.message || 'Failed to add recipe line.');
    }
  };

  const handleDeleteRecipeItem = async (recipeItemId, menuItemName) => {
    if (!window.confirm('Remove this ingredient from the recipe?')) return;
    setActionError(null);
    try {
      await deleteRecipeItem(recipeItemId);
      setActionSuccess(`Removed ingredient line from "${menuItemName}".`);
      loadRecipes();
    } catch (err) {
      console.error('Error deleting recipe item:', err);
      setActionError(err.message || 'Failed to delete recipe line.');
    }
  };

  return (
    <div className="page-content inventory-page-layout">
      {/* ── Top Header & Sub-Navigation Tabs ── */}
      <section className="inventory-top-bar">
        <div className="inventory-header-left">
          <h2 className="inventory-heading">Café Inventory &amp; Supplies</h2>
          <p className="inventory-subheading">
            Track artisanal beans, dairy, dry goods, recipe consumption, and kitchen stock balances.
          </p>
        </div>

        <div className="inventory-tab-buttons">
          <button
            type="button"
            className={`tab-btn ${activeSubTab === 'ingredients' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('ingredients')}
          >
            Ingredients &amp; Stock
          </button>
          <button
            type="button"
            className={`tab-btn ${activeSubTab === 'recipes' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('recipes')}
          >
            Recipe Mappings
          </button>
          {isManagerOrAdmin && (
            <button
              type="button"
              className={`tab-btn ${activeSubTab === 'movements' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('movements')}
            >
              Stock Ledger
            </button>
          )}
        </div>
      </section>

      {/* ── Notification Banners ── */}
      {actionSuccess && (
        <div className="alert-banner alert-success" role="status">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="alert-banner alert-danger" role="alert">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{actionError}</span>
          <button type="button" className="alert-close-btn" onClick={() => setActionError(null)}>
            &times;
          </button>
        </div>
      )}

      {/* ── Metrics Cards (Always visible) ── */}
      <div className="inventory-metrics-grid">
        <div className="inventory-metric-card">
          <div className="metric-icon-box metric-icon-gold">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
              <path d="m3.3 7 8.7 5 8.7-5" />
              <path d="M12 22V12" />
            </svg>
          </div>
          <div className="metric-info">
            <span className="metric-label">Active Ingredients</span>
            <span className="metric-number">{summary.total_active_ingredients}</span>
          </div>
        </div>

        <div className="inventory-metric-card">
          <div className="metric-icon-box metric-icon-amber">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>
          <div className="metric-info">
            <span className="metric-label">Low Stock Warnings</span>
            <span className="metric-number text-amber">{summary.low_stock_count}</span>
          </div>
        </div>

        <div className="inventory-metric-card">
          <div className="metric-icon-box metric-icon-red">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
            </svg>
          </div>
          <div className="metric-info">
            <span className="metric-label">Out of Stock</span>
            <span className="metric-number text-red">{summary.out_of_stock_count}</span>
          </div>
        </div>

        <div className="inventory-metric-card">
          <div className="metric-icon-box metric-icon-sage">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="20" x2="12" y2="10" />
              <line x1="18" y1="20" x2="18" y2="4" />
              <line x1="6" y1="20" x2="6" y2="16" />
            </svg>
          </div>
          <div className="metric-info">
            <span className="metric-label">Ledger Movements</span>
            <span className="metric-number">{summary.total_movements_recorded}</span>
          </div>
        </div>
      </div>

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── TAB 1: INGREDIENTS & STOCK                                   ── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {activeSubTab === 'ingredients' && (
        <section className="inventory-tab-content">
          {/* Controls Bar: Search + Status Filter + Add Button */}
          <div className="inventory-controls-bar">
            <div className="inventory-search-box">
              <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="search"
                className="form-input search-input"
                placeholder="Search ingredients..."
                value={ingredientSearch}
                onChange={(e) => setIngredientSearch(e.target.value)}
              />
            </div>

            <div className="inventory-filter-pills">
              <button
                type="button"
                className={`filter-pill ${statusFilter === 'all' ? 'active' : ''}`}
                onClick={() => setStatusFilter('all')}
              >
                All ({ingredients.length})
              </button>
              <button
                type="button"
                className={`filter-pill ${statusFilter === 'in_stock' ? 'active' : ''}`}
                onClick={() => setStatusFilter('in_stock')}
              >
                In Stock ({ingredients.filter((i) => i.stock_status === 'in_stock').length})
              </button>
              <button
                type="button"
                className={`filter-pill ${statusFilter === 'low_stock' ? 'active' : ''}`}
                onClick={() => setStatusFilter('low_stock')}
              >
                Low Stock ({ingredients.filter((i) => i.stock_status === 'low_stock').length})
              </button>
              <button
                type="button"
                className={`filter-pill ${statusFilter === 'out_of_stock' ? 'active' : ''}`}
                onClick={() => setStatusFilter('out_of_stock')}
              >
                Out of Stock ({ingredients.filter((i) => i.stock_status === 'out_of_stock').length})
              </button>
            </div>

            {isManagerOrAdmin && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleOpenCreateIngredient}
              >
                + New Ingredient
              </button>
            )}
          </div>

          {/* Table Container */}
          <div className="table-container">
            {loadingIngredients ? (
              <div className="loading-state">
                <div className="state-spinner" />
                <p>Loading ingredient balances...</p>
              </div>
            ) : filteredIngredients.length === 0 ? (
              <div className="empty-state">
                <p className="empty-title">No ingredients match your criteria</p>
                <p className="empty-subtext">
                  {ingredientSearch ? `No matches for "${ingredientSearch}".` : 'Start by creating your café ingredients.'}
                </p>
              </div>
            ) : (
              <table className="data-table inventory-table">
                <thead>
                  <tr>
                    <th>Ingredient Name</th>
                    <th>Current Balance</th>
                    <th>Min Threshold</th>
                    <th>Stock Status</th>
                    <th>Unit Cost</th>
                    {isManagerOrAdmin && <th className="text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {filteredIngredients.map((ing) => {
                    const pill = STATUS_PILL_CONFIG[ing.stock_status] || STATUS_PILL_CONFIG.in_stock;
                    return (
                      <tr key={ing.id} className={!ing.is_active ? 'row-deactivated' : ''}>
                        <td>
                          <div className="ingredient-title-cell">
                            <span className="ing-name">{ing.name}</span>
                            {ing.description && <span className="ing-desc">{ing.description}</span>}
                            {!ing.is_active && <span className="deactivated-tag">Deactivated</span>}
                          </div>
                        </td>
                        <td>
                          <span className="stock-balance-val">
                            {parseFloat(ing.current_stock).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 3 })} {ing.unit}
                          </span>
                        </td>
                        <td>
                          <span className="threshold-val">
                            {parseFloat(ing.minimum_stock).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 3 })} {ing.unit}
                          </span>
                        </td>
                        <td>
                          <span className={`status-pill ${pill.className}`}>
                            <span className="pill-dot" />
                            {pill.label}
                          </span>
                        </td>
                        <td>
                          <span className="cost-val">
                            {ing.unit_cost !== null ? `$${parseFloat(ing.unit_cost).toFixed(2)} / ${ing.unit}` : '—'}
                          </span>
                        </td>
                        {isManagerOrAdmin && (
                          <td className="text-right">
                            <div className="table-actions">
                              <button
                                type="button"
                                className="btn-action-pill btn-action-restock"
                                onClick={() => handleOpenAdjustModal(ing, 'restock')}
                                title="Record delivery / restock"
                              >
                                Restock
                              </button>
                              <button
                                type="button"
                                className="btn-action-pill btn-action-waste"
                                onClick={() => handleOpenAdjustModal(ing, 'waste')}
                                title="Record kitchen waste or spoilage"
                              >
                                Waste
                              </button>
                              <button
                                type="button"
                                className="btn-action-icon"
                                onClick={() => handleOpenEditIngredient(ing)}
                                title="Edit thresholds / details"
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                                  <path d="M12 20h9" />
                                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                                </svg>
                              </button>
                              <button
                                type="button"
                                className="btn-action-icon btn-action-delete"
                                onClick={() => handleDeleteIngredient(ing)}
                                title="Deactivate or delete"
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                                  <polyline points="3 6 5 6 21 6" />
                                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                </svg>
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── TAB 2: RECIPE MAPPINGS                                       ── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {activeSubTab === 'recipes' && (
        <section className="inventory-tab-content">
          <div className="inventory-controls-bar">
            <div className="inventory-search-box">
              <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="search"
                className="form-input search-input"
                placeholder="Search menu items..."
                value={recipeSearch}
                onChange={(e) => setRecipeSearch(e.target.value)}
              />
            </div>

            <div className="inventory-filter-pills">
              <button
                type="button"
                className={`filter-pill ${recipeFilter === 'all' ? 'active' : ''}`}
                onClick={() => setRecipeFilter('all')}
              >
                All Menu Items ({recipesList.length})
              </button>
              <button
                type="button"
                className={`filter-pill ${recipeFilter === 'configured' ? 'active' : ''}`}
                onClick={() => setRecipeFilter('configured')}
              >
                Configured Recipes ({recipesList.filter((r) => r.has_recipe).length})
              </button>
              <button
                type="button"
                className={`filter-pill ${recipeFilter === 'missing' ? 'active' : ''}`}
                onClick={() => setRecipeFilter('missing')}
              >
                No Recipe Yet ({recipesList.filter((r) => !r.has_recipe).length})
              </button>
            </div>
          </div>

          <div className="recipes-grid">
            {loadingRecipes ? (
              <div className="loading-state">
                <div className="state-spinner" />
                <p>Loading recipe mappings...</p>
              </div>
            ) : filteredRecipes.length === 0 ? (
              <div className="empty-state">
                <p className="empty-title">No menu items found</p>
              </div>
            ) : (
              filteredRecipes.map((menuItem) => (
                <div key={menuItem.menu_item_id} className="recipe-card">
                  <div className="recipe-card-header">
                    <div>
                      <span className="recipe-cat-badge">{menuItem.category_name || 'General'}</span>
                      <h3 className="recipe-dish-title">{menuItem.menu_item_name}</h3>
                    </div>
                    {menuItem.has_recipe ? (
                      <span className="status-pill status-pill-available">
                        <span className="pill-dot" />
                        {menuItem.recipe_items.length} Ingredients
                      </span>
                    ) : (
                      <span className="status-pill status-pill-occupied">
                        <span className="pill-dot" />
                        No Recipe
                      </span>
                    )}
                  </div>

                  <div className="recipe-card-body">
                    {menuItem.recipe_items && menuItem.recipe_items.length > 0 ? (
                      <ul className="recipe-items-list">
                        {menuItem.recipe_items.map((line) => (
                          <li key={line.id} className="recipe-line-item">
                            <span className="recipe-ing-name">{line.ingredient_name}</span>
                            <div className="recipe-line-right">
                              <span className="recipe-ing-qty">
                                {parseFloat(line.quantity)} {line.unit}
                              </span>
                              {isManagerOrAdmin && (
                                <button
                                  type="button"
                                  className="btn-remove-line"
                                  onClick={() => handleDeleteRecipeItem(line.id, menuItem.menu_item_name)}
                                  title="Remove from recipe"
                                >
                                  &times;
                                </button>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="recipe-empty-hint">
                        No ingredients configured. Orders for this dish will not deduct inventory until ingredients are added.
                      </p>
                    )}
                  </div>

                  {isManagerOrAdmin && (
                    <div className="recipe-card-footer">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleOpenRecipeModal(menuItem)}
                      >
                        + Add Ingredient
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── TAB 3: STOCK LEDGER                                          ── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {activeSubTab === 'movements' && isManagerOrAdmin && (
        <section className="inventory-tab-content">
          <div className="inventory-controls-bar">
            <div className="inventory-filter-pills">
              <button
                type="button"
                className={`filter-pill ${movementTypeFilter === 'all' ? 'active' : ''}`}
                onClick={() => setMovementTypeFilter('all')}
              >
                All Movements
              </button>
              <button
                type="button"
                className={`filter-pill ${movementTypeFilter === 'order_consumption' ? 'active' : ''}`}
                onClick={() => setMovementTypeFilter('order_consumption')}
              >
                Order Consumption
              </button>
              <button
                type="button"
                className={`filter-pill ${movementTypeFilter === 'order_reversal' ? 'active' : ''}`}
                onClick={() => setMovementTypeFilter('order_reversal')}
              >
                Reversals
              </button>
              <button
                type="button"
                className={`filter-pill ${movementTypeFilter === 'restock' ? 'active' : ''}`}
                onClick={() => setMovementTypeFilter('restock')}
              >
                Restock Deliveries
              </button>
              <button
                type="button"
                className={`filter-pill ${movementTypeFilter === 'waste' ? 'active' : ''}`}
                onClick={() => setMovementTypeFilter('waste')}
              >
                Waste &amp; Spoilage
              </button>
            </div>
          </div>

          <div className="table-container">
            {loadingMovements ? (
              <div className="loading-state">
                <div className="state-spinner" />
                <p>Loading ledger movements...</p>
              </div>
            ) : movements.length === 0 ? (
              <div className="empty-state">
                <p className="empty-title">No stock movements found</p>
              </div>
            ) : (
              <table className="data-table ledger-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Ingredient</th>
                    <th>Movement Type</th>
                    <th>Quantity Delta</th>
                    <th>Staff / Actor</th>
                    <th>Reason / Reference</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.map((m) => {
                    const delta = parseFloat(m.quantity_delta);
                    const isPositive = delta > 0;
                    return (
                      <tr key={m.id}>
                        <td>
                          <span className="timestamp-text">
                            {new Date(m.created_at).toLocaleString([], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </td>
                        <td>
                          <span className="ledger-ing-name">{m.ingredient_name || `ID ${m.ingredient_id}`}</span>
                        </td>
                        <td>
                          <span className={`movement-type-tag type-${m.movement_type}`}>
                            {m.movement_type.replace('_', ' ')}
                          </span>
                        </td>
                        <td>
                          <span className={`delta-val ${isPositive ? 'delta-positive' : 'delta-negative'}`}>
                            {isPositive ? `+${delta.toFixed(3)}` : delta.toFixed(3)} {m.ingredient_unit}
                          </span>
                        </td>
                        <td>
                          <span className="actor-text">{m.user_name || 'System / Auto'}</span>
                        </td>
                        <td>
                          <span className="reason-text">{m.reason || (m.order_id ? `Order #${m.order_id}` : '—')}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── MODAL: CREATE / EDIT INGREDIENT                              ── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {ingredientModalOpen && (
        <div className="modal-backdrop" onClick={() => setIngredientModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} role="dialog">
            <div className="modal-header">
              <h3 className="modal-title">
                {editingIngredient ? `Edit "${editingIngredient.name}"` : 'Create New Ingredient'}
              </h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setIngredientModalOpen(false)}
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSaveIngredient}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Ingredient Name *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="e.g., Whole Milk, Arabica Coffee Beans, Butter"
                    value={ingredientFormData.name}
                    onChange={(e) =>
                      setIngredientFormData((p) => ({ ...p, name: e.target.value }))
                    }
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Unit of Measure *</label>
                    <select
                      className="form-select"
                      value={ingredientFormData.unit}
                      onChange={(e) =>
                        setIngredientFormData((p) => ({ ...p, unit: e.target.value }))
                      }
                      disabled={!!editingIngredient}
                    >
                      <option value="g">Grams (g)</option>
                      <option value="ml">Milliliters (ml)</option>
                      <option value="each">Units / Each (count)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Min Threshold *</label>
                    <input
                      type="number"
                      step="0.001"
                      min="0"
                      required
                      className="form-input"
                      placeholder="e.g. 100"
                      value={ingredientFormData.minimum_stock}
                      onChange={(e) =>
                        setIngredientFormData((p) => ({ ...p, minimum_stock: e.target.value }))
                      }
                    />
                  </div>
                </div>

                {!editingIngredient && (
                  <div className="form-group">
                    <label className="form-label">Initial Stock on Hand</label>
                    <input
                      type="number"
                      step="0.001"
                      min="0"
                      className="form-input"
                      placeholder="0"
                      value={ingredientFormData.initial_stock}
                      onChange={(e) =>
                        setIngredientFormData((p) => ({ ...p, initial_stock: e.target.value }))
                      }
                    />
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Unit Cost (USD, optional)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className="form-input"
                    placeholder="e.g. 0.05"
                    value={ingredientFormData.unit_cost}
                    onChange={(e) =>
                      setIngredientFormData((p) => ({ ...p, unit_cost: e.target.value }))
                    }
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Description / Storage Notes</label>
                  <textarea
                    rows={2}
                    className="form-textarea"
                    placeholder="e.g., Farm fresh pasteurized 3.5% fat milk. Store chilled under 4°C."
                    value={ingredientFormData.description}
                    onChange={(e) =>
                      setIngredientFormData((p) => ({ ...p, description: e.target.value }))
                    }
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIngredientModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingIngredient ? 'Save Changes' : 'Create Ingredient'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── MODAL: STOCK ADJUSTMENT (Restock / Waste)                     ── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {adjustModalOpen && adjustingIngredient && (
        <div className="modal-backdrop" onClick={() => setAdjustModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} role="dialog">
            <div className="modal-header">
              <h3 className="modal-title">
                {adjustFormData.adjustment_type === 'restock' ? 'Restock Delivery' : 'Record Waste / Spoilage'}:{' '}
                {adjustingIngredient.name}
              </h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setAdjustModalOpen(false)}
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSaveAdjustment}>
              <div className="modal-body">
                <div className="inventory-adjustment-meta">
                  <span>Current Stock:</span>
                  <strong>
                    {parseFloat(adjustingIngredient.current_stock).toFixed(3)} {adjustingIngredient.unit}
                  </strong>
                </div>

                <div className="form-group">
                  <label className="form-label">Adjustment Type *</label>
                  <select
                    className="form-select"
                    value={adjustFormData.adjustment_type}
                    onChange={(e) => {
                      const t = e.target.value;
                      setAdjustFormData((p) => ({
                        ...p,
                        adjustment_type: t,
                        reason: t === 'restock' ? 'Delivery from roastery/supplier' : 'Kitchen waste/spoilage',
                      }));
                      setConfirmingAdjust(false);
                    }}
                  >
                    <option value="restock">Restock Delivery (+)</option>
                    <option value="waste">Waste / Spoilage (-)</option>
                    <option value="manual_correction">Audited Manual Correction (+/-)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Quantity to {adjustFormData.adjustment_type === 'restock' ? 'Add' : 'Deduct'} ({adjustingIngredient.unit}) *
                  </label>
                  <input
                    type="number"
                    step="0.001"
                    min="0.001"
                    required
                    className="form-input"
                    placeholder="Enter quantity..."
                    value={adjustFormData.quantity}
                    onChange={(e) => {
                      setAdjustFormData((p) => ({ ...p, quantity: e.target.value }));
                      setConfirmingAdjust(false);
                    }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Reason / Delivery Slip / Notes *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="e.g. Invoice #PO-9482 or Dropped batch during preparation"
                    value={adjustFormData.reason}
                    onChange={(e) => setAdjustFormData((p) => ({ ...p, reason: e.target.value }))}
                  />
                </div>

                {confirmingAdjust && (
                  <div className="confirmation-warning-box">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    <div>
                      <strong>Confirm {adjustFormData.adjustment_type.toUpperCase()}:</strong>
                      <p>
                        Are you sure you want to adjust {adjustFormData.quantity} {adjustingIngredient.unit} of{' '}
                        {adjustingIngredient.name}? This will immediately update stock balances and write to the audit ledger.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setAdjustModalOpen(false);
                    setConfirmingAdjust(false);
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`btn ${confirmingAdjust ? 'btn-danger' : 'btn-primary'}`}
                >
                  {confirmingAdjust ? 'Yes, Confirm Adjustment' : 'Review & Confirm'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── MODAL: ADD INGREDIENT TO RECIPE                              ── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {recipeModalOpen && selectedMenuItemForRecipe && (
        <div className="modal-backdrop" onClick={() => setRecipeModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} role="dialog">
            <div className="modal-header">
              <h3 className="modal-title">
                Add Ingredient to Recipe: {selectedMenuItemForRecipe.menu_item_name}
              </h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setRecipeModalOpen(false)}
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleAddRecipeItem}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Select Ingredient *</label>
                  <select
                    className="form-select"
                    value={recipeFormData.ingredient_id}
                    onChange={handleIngredientSelectChange}
                    required
                  >
                    {ingredients.map((ing) => (
                      <option key={ing.id} value={ing.id}>
                        {ing.name} ({ing.unit}) — Current: {parseFloat(ing.current_stock).toFixed(1)} {ing.unit}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Quantity per Dish Prepared *</label>
                    <input
                      type="number"
                      step="0.001"
                      min="0.001"
                      required
                      className="form-input"
                      placeholder="e.g. 18.000"
                      value={recipeFormData.quantity}
                      onChange={(e) =>
                        setRecipeFormData((p) => ({ ...p, quantity: e.target.value }))
                      }
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Measurement Unit</label>
                    <input
                      type="text"
                      disabled
                      className="form-input input-disabled"
                      value={recipeFormData.unit}
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setRecipeModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Add to Recipe
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
