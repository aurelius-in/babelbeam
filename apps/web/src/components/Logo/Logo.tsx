export type LogoVariant = "dark" | "light" | "monogram";

type LogoProps = {
  variant?: LogoVariant;
  size?: number;
  className?: string;
  decorative?: boolean;
};

const sources: Record<LogoVariant, string> = {
  dark: "/brand/logo-full.png",
  light: "/brand/logo-light.png",
  monogram: "/brand/icon.png",
};

/** dark: navy wordmark for light surfaces. light: ice wordmark for dark surfaces. */
export function Logo({ variant = "light", size = 280, className, decorative = false }: LogoProps) {
  return (
    <img
      src={sources[variant]}
      alt={decorative ? "" : "BabelBeam"}
      width={size}
      className={className}
      style={{ width: size, height: "auto" }}
      aria-hidden={decorative ? true : undefined}
    />
  );
}
