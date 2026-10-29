import React from 'react';

export default function CustomerFooter({ onNavigate }) {
  const handleNav = (route, e) => {
    e.preventDefault();
    onNavigate(route);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="customer-footer">
      <div className="customer-footer-inner">
        <div className="customer-footer-brand">
          <div className="customer-footer-logo">
            <span className="customer-footer-name">Brew &amp; Co.</span>
            <span className="customer-footer-tagline">Specialty Coffeehouse &amp; Bakery</span>
          </div>
          <p className="customer-footer-bio">
            An artisanal specialty coffeehouse dedicated to single-origin bean extractions,
            precision slow-drip brews, and traditional French laminated viennoiserie baked fresh daily.
          </p>
        </div>

        <div className="customer-footer-links-group">
          <h4 className="customer-footer-heading">Navigation</h4>
          <ul className="customer-footer-list">
            <li>
              <a href="/" onClick={(e) => handleNav('/', e)}>
                Home
              </a>
            </li>
            <li>
              <a href="/menu" onClick={(e) => handleNav('/menu', e)}>
                Artisanal Menu
              </a>
            </li>
            <li>
              <a
                href="#story"
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' });
                }}
              >
                Our Story
              </a>
            </li>
          </ul>
        </div>

        <div className="customer-footer-links-group">
          <h4 className="customer-footer-heading">Experience</h4>
          <ul className="customer-footer-list">
            <li>Specialty Coffee &amp; Espresso</li>
            <li>18-Hour Slow Kyoto Cold Brew</li>
            <li>Handcrafted French Viennoiserie</li>
            <li>Artisanal Brunch &amp; Toasties</li>
          </ul>
        </div>

        <div className="customer-footer-links-group">
          <h4 className="customer-footer-heading">Operations</h4>
          <ul className="customer-footer-list">
            <li>
              <a href="/staff" onClick={(e) => handleNav('/staff', e)} className="customer-footer-staff-link">
                Staff Operations Portal &rarr;
              </a>
            </li>
            <li>
              <span className="customer-footer-muted">POS Terminal &bull; Kitchen Display &bull; Floor Plan</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="customer-footer-bottom">
        <p>&copy; {new Date().getFullYear()} Brew &amp; Co. All rights reserved. Crafted with precision &amp; passion.</p>
      </div>
    </footer>
  );
}
