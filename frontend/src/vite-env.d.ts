/// <reference types="vite/client" />

// Swiper's CSS subpath exports (e.g. "swiper/css", "swiper/css/pagination") resolve fine
// at build time via Vite, but the specifiers don't end in a literal ".css" so the
// `declare module '*.css'` ambient type from vite/client doesn't match them. Declare them
// explicitly so `tsc` type-checking succeeds. See https://swiperjs.com/react#styles.
declare module 'swiper/css';
declare module 'swiper/css/*';
