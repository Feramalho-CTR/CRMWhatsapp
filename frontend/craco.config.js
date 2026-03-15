// Carrega configuração do ambiente ou de um arquivo de config
const path = require('path');

// Sobrescritas por variáveis de ambiente
const config = {
  disableHotReload: process.env.DISABLE_HOT_RELOAD === 'true',
};

module.exports = {
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {
      
  // Desativa hot reload completamente se a variável de ambiente estiver setada
      if (config.disableHotReload) {
  // Remove plugins relacionados ao hot reload
        webpackConfig.plugins = webpackConfig.plugins.filter(plugin => {
          return !(plugin.constructor.name === 'HotModuleReplacementPlugin');
        });
        
  // Desativa o modo watch
        webpackConfig.watch = false;
        webpackConfig.watchOptions = {
          ignored: /.*/, // Ignora todos os arquivos
        };
      } else {
  // Adiciona padrões ignorados para reduzir diretórios monitorados
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
          ],
        };
      }
      
      return webpackConfig;
    },
  },
};