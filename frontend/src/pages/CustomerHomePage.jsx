import React, { useState, useEffect } from 'react';
import CustomerHero from '../components/CustomerHero';
import BrandStorySection from '../components/BrandStorySection';
import SeasonalHighlights from '../components/SeasonalHighlights';
import ProductDetailModal from '../components/ProductDetailModal';
import { getPublicMenu } from '../services/api';
import { filterCuratedMenu } from '../utils/curatedCatalog';

export default function CustomerHomePage({ onNavigate }) {
  const [menuData, setMenuData] = useState({ categories: [], items: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedProduct, setSelectedProduct] = useState(null);

  useEffect(() => {
    let isMounted = true;
    getPublicMenu()
      .then((data) => {
        if (isMounted) {
          const curated = filterCuratedMenu(data);
          setMenuData(curated);
          setError(null);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error('Failed to load public menu highlights:', err);
          setError('Unable to load current menu highlights.');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="customer-page-container">
      {/* Hero Section */}
      <CustomerHero onNavigate={onNavigate} />

      {/* Category Quick Browse Section */}
      {menuData.categories.length > 0 && (
        <section className="category-browse-section">
          <div className="category-browse-inner">
            <div className="section-header-centered">
              <span className="section-eyebrow">Discover</span>
              <h2 className="section-title">Explore Our 9 Artisanal Departments</h2>
              <div className="gold-accent-line" />
            </div>

            <div className="category-chips-grid">
              {menuData.categories.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  className="category-chip-card"
                  onClick={() => onNavigate(`/menu?category=${cat.id}`)}
                >
                  <span className="cat-chip-name">{cat.name}</span>
                  <span className="cat-chip-count">{cat.item_count} items &rarr;</span>
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Seasonal & Signature Highlights */}
      {!loading && !error && (
        <SeasonalHighlights
          items={menuData.items}
          onSelectProduct={setSelectedProduct}
          onNavigate={onNavigate}
        />
      )}

      {/* Brand Story Section */}
      <BrandStorySection />

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
        />
      )}
    </div>
  );
}
