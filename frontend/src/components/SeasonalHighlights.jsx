import React from 'react';
import ProductCard from './ProductCard';

export default function SeasonalHighlights({ items, onSelectProduct, onNavigate }) {
  // Select seasonal/signature items or top featured items from menu data
  const highlightedItems = React.useMemo(() => {
    if (!items || items.length === 0) return [];
    // Prioritize "Seasonal & Signature Specials" category
    const seasonal = items.filter(
      (i) => i.category_name && i.category_name.toLowerCase().includes('seasonal')
    );
    if (seasonal.length >= 4) {
      return seasonal.slice(0, 4);
    }
    // Fallback: pick diverse items across categories
    const diverse = [];
    const seenCats = new Set();
    for (const item of items) {
      if (!seenCats.has(item.category_id)) {
        seenCats.add(item.category_id);
        diverse.push(item);
        if (diverse.length === 4) break;
      }
    }
    return diverse.length > 0 ? diverse : items.slice(0, 4);
  }, [items]);

  if (highlightedItems.length === 0) return null;

  return (
    <section className="seasonal-highlights-section">
      <div className="seasonal-highlights-inner">
        <div className="section-header-centered">
          <span className="section-eyebrow">Curated Creations</span>
          <h2 className="section-title">Seasonal &amp; Signature Highlights</h2>
          <p className="section-subtitle">
            House-crafted creations celebrating our roasters and pastry chefs.
          </p>
          <div className="gold-accent-line" />
        </div>

        <div className="highlights-grid">
          {highlightedItems.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onSelect={onSelectProduct}
            />
          ))}
        </div>

        <div className="highlights-cta-box">
          <button
            type="button"
            className="view-full-menu-btn"
            onClick={() => onNavigate('/menu')}
          >
            Explore Curated Menu &rarr;
          </button>
        </div>
      </div>
    </section>
  );
}
