import React from 'react';

type Variant = 'auto' | 'light' | 'dark' | 'monogram';

interface LogoProps {
  variant?: Variant;
  size?: number | string; // can be number(px) or CSS size
  className?: string;
  ariaHidden?: boolean;
}

// Logo component: chooses inline SVG for accessibility when needed, otherwise uses cached file.
export const Logo: React.FC<LogoProps> = ({ variant = 'auto', size = 48, className, ariaHidden = false }) => {
  const style: React.CSSProperties = typeof size === 'number' ? { width: size, height: 'auto' } : { width: size, height: 'auto' };
  const dataTheme = typeof window !== 'undefined' ? document.documentElement.getAttribute('data-theme') : 'dark';
  let chosen = variant;
  if (variant === 'auto') chosen = (dataTheme === 'light') ? 'light' : 'dark';

  if (chosen === 'monogram') {
    return (
      <img
        src="/brand/logo-monogram.svg"
        alt="BabelBeam"
        style={style}
        className={className}
        aria-hidden={ariaHidden}
      />
    );
  }

  // Inline SVG for themeable wordmark. Keep markup minimal and accessible.
  if (chosen === 'light') {
    return (
      <img
        src="/brand/logo-light.svg"
        alt="BabelBeam"
        style={style}
        className={className}
        aria-hidden={ariaHidden}
      />
    );
  }

  return (
    <img
      src="/brand/logo-full.svg"
      alt="BabelBeam"
      style={style}
      className={className}
      aria-hidden={ariaHidden}
    />
  );
};

export default Logo;
