import React from 'react';

export default function BrandStorySection() {
  return (
    <section id="story" className="brand-story-section">
      <div className="brand-story-inner">
        <div className="brand-story-header">
          <span className="section-eyebrow">The Philosophy</span>
          <h2 className="section-title">The Art &amp; Soul of Brew &amp; Co.</h2>
          <div className="gold-accent-line" />
        </div>

        <div className="brand-story-grid">
          <div className="story-card">
            <div className="story-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z" />
                <path d="M12 6v6l4 2" />
              </svg>
            </div>
            <h3 className="story-card-title">Single-Estate Coffee</h3>
            <p className="story-card-text">
              Directly sourced from high-altitude Chikmagalur estates. Every batch is micro-roasted
              to unlock delicate floral notes, vibrant cacao undertones, and velvety crema.
            </p>
          </div>

          <div className="story-card">
            <div className="story-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                <line x1="7" y1="7" x2="7.01" y2="7" />
              </svg>
            </div>
            <h3 className="story-card-title">Laminated Viennoiserie</h3>
            <p className="story-card-text">
              27 delicate honeycomb layers folded with pure French cultured butter. Hand-rolled,
              slow-proofed, and baked fresh every dawn for incomparable shatter and softness.
            </p>
          </div>

          <div className="story-card">
            <div className="story-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
              </svg>
            </div>
            <h3 className="story-card-title">Whole Scratch Brunch</h3>
            <p className="story-card-text">
              From house-simmered shakshuka skillets and poached farm eggs to 36-hour fermented sourdough,
              every plate is prepared with culinary reverence and genuine warmth.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
