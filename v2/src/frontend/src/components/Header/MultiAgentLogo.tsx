/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — reference-architecture re-skin)
 *
 * Multi-agent brand mark as an inline SVG component. This is the
 * interlocking glyph the reference architecture's multi-agent experience renders for its
 * brand badge (adapted from the reference architecture's logo
 * component). Used as the brand icon
 * inside the header `<Avatar shape="square">`.
 *
 * Inline (not a static `.svg` import) so the mark fills with the Fluent
 * v9 `--colorBrandForeground1` design token and flips with light/dark
 * theme for free.
 */
import { type JSX, type SVGAttributes } from "react";

export interface MultiAgentLogoProps extends SVGAttributes<SVGSVGElement> {
  size?: number;
}

export function MultiAgentLogo({
  size = 24,
  ...rest
}: MultiAgentLogoProps): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 33 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Multi-agent"
      {...rest}
    >
      <path
        d="M8.23352 15.9738C5.76515 13.5949 5.99534 10.2657 7.78417 8.22591C9.4775 6.29505 13.0907 5.33023 16.0316 8.2051C17.2805 6.94275 18.7767 6.27791 20.5851 6.41871C21.9932 6.52891 23.1649 7.12641 24.1347 8.13408C26.2088 10.2915 26.0912 13.1492 23.8163 15.9971C26.139 18.976 26.1904 21.8864 23.9669 24.0426C22.0434 25.9073 18.5772 26.3971 16.0157 23.7781C13.2915 26.4901 9.8791 25.8094 8.05965 24.0475C6.2745 22.3186 5.41375 18.8463 8.23474 15.9738H8.23352ZM12.7099 11.7436C12.4173 12.0313 12.1026 12.2186 11.9777 12.4917C11.7842 12.9141 12.0193 13.2496 12.3866 13.5275C14.2991 14.9723 14.2991 17.0146 12.3879 18.4569C12.045 18.7165 11.7928 19.0336 11.9618 19.434C12.072 19.6935 12.3879 20.0266 12.6217 20.0351C12.9229 20.0462 13.3331 19.8417 13.5241 19.5956C14.9774 17.7357 17.0161 17.7161 18.4584 19.5491C18.6629 19.8099 19.084 20.0388 19.3963 20.0302C19.6326 20.0229 20.0366 19.6164 20.0427 19.3801C20.0501 19.0666 19.8126 18.6663 19.5567 18.4447C18.9714 17.9378 18.4523 17.4088 18.2857 16.6301C17.9931 15.2588 18.5918 14.2817 19.6583 13.4773C19.8909 13.3022 20.088 12.8921 20.0599 12.6153C20.0354 12.3705 19.6926 12.0019 19.4563 11.9738C19.1587 11.9383 18.6861 12.1023 18.5318 12.3386C17.3258 14.1887 14.8415 14.3601 13.4947 12.3386C13.3441 12.1121 13.0405 11.9872 12.7087 11.7436H12.7099Z"
        fill="var(--colorBrandForeground1)"
        fillRule="evenodd"
        clipRule="evenodd"
      />
    </svg>
  );
}
