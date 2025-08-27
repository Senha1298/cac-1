/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Rawline', 'sans-serif'],
      },
      colors: {
        'military': {
          'green': '#2D5A27',
          'dark': '#1A3B19',
          'light': '#4A7A44'
        }
      }
    }
  },
  plugins: [],
}
