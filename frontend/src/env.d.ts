/// <reference types="electron-vite/node" />

// Vite asset imports
declare module '*?asset' {
  const src: string
  export default src
}

declare module '*.png?asset' {
  const src: string
  export default src
}

declare module '*.svg?asset' {
  const src: string
  export default src
}

declare module '*.jpg?asset' {
  const src: string
  export default src
}

declare module '*.ico?asset' {
  const src: string
  export default src
}

// Regular SVG imports (as URL strings)
declare module '*.svg' {
  const src: string
  export default src
}
