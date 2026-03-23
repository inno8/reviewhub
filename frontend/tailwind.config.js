export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#58A6FF',
        'primary-hover': '#6CAEFF',
        'primary-light': '#A2C9FF',
        secondary: '#5F799C',
        'secondary-light': '#7992B7',
        tertiary: '#DA9600',
        'tertiary-light': '#FFBA42',
        border: '#30363D',
        bg: {
          darkest: '#0D1117',
          dark: '#181C22',
          card: '#161B22',
          elevated: '#2D3137',
        },
        text: {
          primary: '#FFFFFF',
          secondary: '#8B949E',
          muted: '#6E7681',
        },
        dark: {
          bg: '#0D1117',
          card: '#161B22',
          border: '#30363D',
        },
        success: '#3FB950',
        error: '#F85149',
        warning: '#D29922',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
