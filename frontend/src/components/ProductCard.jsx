import React, { useState } from 'react';
import DishImage from './DishImage';
import { formatUSD } from '../utils/formatters';
import { useCart } from '../context/CartContext';

export default function ProductCard({ product, onSelect }) {
  const { addToCart } = useCart();
  const [justAdded, setJustAdded] = useState(false);

  const handleQuickAdd = (e) => {
    e.stopPropagation();
    if (!product.is_available) return;
    addToCart(product, 1);
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 800);
  };

  return (
    <article
      className="customer-product-card"
      onClick={() => onSelect(product)}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(product);
        }
      }}
      aria-label={`View details for ${product.name}, priced at ${formatUSD(product.price)}`}
    >
      <div className="product-card-media">
        <DishImage
          item={product}
          aspectRatio="16/11"
          className="product-card-image"
        />
        {product.prep_time_minutes && (
          <span className="product-card-badge">
            {product.prep_time_minutes} min prep
          </span>
        )}
      </div>

      <div className="product-card-content">
        <div className="product-card-header">
          {product.category_name && (
            <span className="product-card-cat">{product.category_name}</span>
          )}
          <h3 className="product-card-title">{product.name}</h3>
        </div>

        <p className="product-card-desc">
          {product.description || 'Artisanal recipe prepared fresh with premium ingredients.'}
        </p>

        <div className="product-card-footer">
          <span className="product-card-price">{formatUSD(product.price)}</span>

          <button
            type="button"
            className={`product-card-add-btn ${justAdded ? 'added' : ''}`}
            onClick={handleQuickAdd}
            disabled={!product.is_available}
            aria-label={`Add ${product.name} to cart`}
          >
            {justAdded ? (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>Added</span>
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span>Add</span>
              </>
            )}
          </button>
        </div>
      </div>
    </article>
  );
}
