// Up-right arrow used on links and buttons. Decorative: always aria-hidden.
export default function Arrow({ size = 16 }) {
  return (
    <svg
      className="arrow"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
    >
      <path d="M6 18 18 6M8 6h10v10" />
    </svg>
  );
}
