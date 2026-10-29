import React, { useState, useEffect } from 'react';
import DishImage from './DishImage';
import { formatUSD } from '../utils/formatters';
import { useCart } from '../context/CartContext';

export default function ProductDetailModal({ product, onClose }) {
  const { addToCart, setIsCartOpen } = useCart();
  const [quantity, setQuantity] = useState(1);
  const [addedNotice, setAddedNotice] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  if (!product) return null;

  const handleAdd = () => {
    addToCart(product, quantity);
    setAddedNotice(true);
    setTimeout(() => {
      setAddedNotice(false);
      onClose();
      setIsCartOpen(true);
    }, 400);
  };

  return (
    <div className="product-modal-backdrop" onClick={onClose}>
      <div
        className="product-modal-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-product-title"
      >
        <button
          type="button"
          className="product-modal-close-btn"
          onClick={onClose}
          aria-label="Close product details"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        <div className="product-modal-grid">
          {/* Product Image */}
          <div className="product-modal-image-col">
            <DishImage
              item={product}
              aspectRatio="4/3"
              className="product-modal-image"
            />
          </div>

          {/* Product Details */}
          <div className="product-modal-details-col">
            <div className="product-modal-meta-top">
              {product.category_name && (
                <span className="product-modal-category">{product.category_name}</span>
              )}
              {product.prep_time_minutes && (
                <span className="product-modal-prep-badge">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  {product.prep_time_minutes} min prep
                </span>
              )}
            </div>

            <h2 id="modal-product-title" className="product-modal-title">
              {product.name}
            </h2>

            <div className="product-modal-price">{formatUSD(product.price)}</div>

            <p className="product-modal-description">
              {product.description || 'Crafted fresh daily with the finest seasonal ingredients by Brew & Co. culinary artisans.'}
            </p>

            {/* Availability Indicator */}
            <div className="product-modal-status">
              {product.is_available ? (
                <span className="product-status-available">
                  <span className="status-dot-pulse" /> Available in Café Today
                </span>
              ) : (
                <span className="product-status-unavailable">
                  Currently Sold Out
                </span>
              )}
            </div>

            {/* Quantity and Add to Cart Button */}
            {product.is_available && (
              <div className="product-modal-cta-row">
                <div className="modal-qty-selector">
                  <button
                    type="button"
                    className="modal-qty-btn"
                    onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                    aria-label="Decrease quantity"
                  >
                    &minus;
                  </button>
                  <span className="modal-qty-value">{quantity}</span>
                  <button
                    type="button"
                    className="modal-qty-btn"
                    onClick={() => setQuantity((q) => q + 1)}
                    aria-label="Increase quantity"
                  >
                    +
                  </button>
                </div>

                <button
                  type="button"
                  className={`product-modal-add-btn ${addedNotice ? 'added' : ''}`}
                  onClick={handleAdd}
                >
                  {addedNotice ? 'Added to Order!' : `Add to Order • ${formatUSD(Number(product.price) * quantity)}`}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
