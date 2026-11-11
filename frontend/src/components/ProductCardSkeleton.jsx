import React from 'react';

/**
 * Individual product card skeleton placeholder that matches CustomerProductCard's
 * exact dimensions, typography rhythm, media aspect ratio, and layout.
 */
export default function ProductCardSkeleton() {
  return (
    <article className="customer-product-card customer-product-card-skeleton" aria-hidden="true">
      <div className="product-card-media skeleton-media-box">
        <div className="skeleton-line skeleton-media" />
      </div>

      <div className="product-card-content">
        <div className="product-card-header">
          <div className="skeleton-line skeleton-cat-badge" />
          <div className="skeleton-line skeleton-title" />
        </div>

        <div className="skeleton-line skeleton-desc" />
        <div className="skeleton-line skeleton-desc short" />

        <div className="product-card-footer">
          <div className="skeleton-line skeleton-price" />
          <div className="skeleton-line skeleton-btn" />
        </div>
      </div>
    </article>
  );
}
