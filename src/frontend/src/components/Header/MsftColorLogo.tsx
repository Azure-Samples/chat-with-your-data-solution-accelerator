/**
 * Microsoft 4-square color logo as an inline SVG component. Mirrors
 * the reference architecture's color-logo component. Used as the
 * brand icon inside the header `<Avatar shape="square">`.
 *
 * Inline (not a static `.svg` import) so the logo participates in
 * theme-agnostic CSS: the brand colors are intentionally hard-coded
 * to Microsoft's brand palette and must not shift with light/dark
 * mode.
 *
 * Brand colors: red #F25022, green #7FBA00, blue #00A4EF, yellow #FFB900.
 */
import { type JSX, type SVGAttributes } from "react";

export interface MsftColorLogoProps extends SVGAttributes<SVGSVGElement> {
  size?: number;
}

export function MsftColorLogo({
  size = 24,
  ...rest
}: MsftColorLogoProps): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 23 23"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Microsoft"
      {...rest}
    >
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="12" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="12" width="10" height="10" fill="#00A4EF" />
      <rect x="12" y="12" width="10" height="10" fill="#FFB900" />
    </svg>
  );
}
