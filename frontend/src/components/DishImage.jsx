import React, { useState } from 'react';
import { getDishImageMeta, DEFAULT_FALLBACK_IMAGE } from '../utils/dishImages.js';

/**
 * Reusable DishImage component with graceful loading and fallback states.
 * Guarantees zero layout jumps and prevents broken image icons.
 */
export default function DishImage({
  item,
  className = '',
  aspectRatio = '16/10',
  height,
  width,
  showBadge = false,
  badgeText,
}) {
  const [hasError, setHasError] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  const imageMeta = getDishImageMeta(item);
  const initialUrl = imageMeta.url;
  const altText = imageMeta.alt || (item?.name ? `${item.name} dish presentation` : 'Culinary dish presentation');

  const handleError = () => {
    setHasError(true);
  };

  const handleLoad = () => {
    setIsLoaded(true);
  };

  return (
    <div
      className={`dish-image-wrapper ${className}`}
      style={{
        aspectRatio,
        height: height || 'auto',
        width: width || '100%',
        position: 'relative',
        overflow: 'hidden',
        backgroundColor: 'var(--color-bg-ivory-warm, #f8f6f0)',
      }}
    >
      {/* Background shimmer placeholder while loading */}
      {!isLoaded && !hasError && <div className="dish-image-shimmer" />}

      {hasError ? (
        /* Graceful Culinary Fallback Placeholder */
        <div className="dish-image-fallback-box">
          <svg
            className="dish-fallback-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
            <path d="M7 2v20" />
            <path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
          </svg>
          <span className="dish-fallback-label">{item?.name || 'Restaurant Dish'}</span>
        </div>
      ) : (
        <img
          src={initialUrl}
          alt={altText}
          loading="lazy"
          onLoad={handleLoad}
          onError={handleError}
          className={`dish-image-element ${isLoaded ? 'dish-image-loaded' : 'dish-image-loading'}`}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: 'block',
            transition: 'opacity 0.25s ease, transform 0.3s ease',
          }}
        />
      )}

      {showBadge && badgeText && (
        <span className="dish-image-badge">{badgeText}</span>
      )}
    </div>
  );
}

export { DishImage };
