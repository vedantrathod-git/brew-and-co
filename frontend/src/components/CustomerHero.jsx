import React from 'react';

export default function CustomerHero({ onNavigate }) {
  return (
    <section className="customer-hero">
      <div className="customer-hero-content">
        <span className="customer-hero-badge">Specialty Coffee &bull; French Viennoiserie &bull; Brunch</span>
        <h1 className="customer-hero-title">
          Where Artisanal Craft <br />
          Meets Midnight Espresso
        </h1>
        <p className="customer-hero-subtitle">
          Experience precision single-origin coffee extractions, 18-hour slow Kyoto cold brews,
          and golden laminated butter viennoiserie, crafted fresh every morning in a serene contemporary sanctuary.
        </p>

        <div className="customer-hero-ctas">
          <button
            type="button"
            className="hero-primary-btn"
            onClick={() => onNavigate('/menu')}
          >
            Explore Artisanal Menu &rarr;
          </button>
          <a
            href="#story"
            className="hero-secondary-btn"
            onClick={(e) => {
              e.preventDefault();
              document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' });
            }}
          >
            Our Craft &amp; Story
          </a>
        </div>

        {/* Brand Pillars */}
        <div className="customer-hero-pillars">
          <div className="pillar-item">
            <span className="pillar-number">37</span>
            <span className="pillar-label">Curated Selections</span>
          </div>
          <div className="pillar-divider" />
          <div className="pillar-item">
            <span className="pillar-number">9</span>
            <span className="pillar-label">Café Departments</span>
          </div>
          <div className="pillar-divider" />
          <div className="pillar-item">
            <span className="pillar-number">18h</span>
            <span className="pillar-label">Kyoto Cold Extraction</span>
          </div>
          <div className="pillar-divider" />
          <div className="pillar-item">
            <span className="pillar-number">100%</span>
            <span className="pillar-label">Single-Estate Coffee</span>
          </div>
        </div>
      </div>
    </section>
  );
}
