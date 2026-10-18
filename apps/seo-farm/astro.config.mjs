import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://mch-seo-farm.vercel.app',
  output: 'static',
  build: {
    inlineStylesheets: 'always',
  },
  vite: {
    assetsInclude: ['**/*.md'],
  },
});
