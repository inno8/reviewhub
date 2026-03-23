export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#58A6FF',
        secondary: '#5F799C',
        tertiary: '#DA9600',
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
