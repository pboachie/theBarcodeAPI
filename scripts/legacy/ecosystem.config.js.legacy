// PM2 ecosystem configuration for theBarcodeAPI frontend
// This configuration ensures process management by name instead of ID

module.exports = {
  apps: [
    {
      name: `thebarcodeapi-frontend-${process.env.ENVIRONMENT || 'production'}`,
      script: 'npm',
      args: 'start',
      cwd: `/opt/thebarcodeapi/${process.env.ENVIRONMENT || 'production'}/current`,
      instances: 2,
      exec_mode: 'cluster',
      
      // Environment variables
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
        NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION || '0.1.0',
      },
      
      // Logging
      log_file: `/opt/thebarcodeapi/${process.env.ENVIRONMENT || 'production'}/logs/combined.log`,
      out_file: `/opt/thebarcodeapi/${process.env.ENVIRONMENT || 'production'}/logs/out.log`,
      error_file: `/opt/thebarcodeapi/${process.env.ENVIRONMENT || 'production'}/logs/error.log`,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      
      // Process management
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      
      // Graceful shutdown
      kill_timeout: 5000,
      listen_timeout: 3000,
      
      // Health monitoring
      min_uptime: '10s',
      max_restarts: 10,
      
      // Source map support
      source_map_support: true,
      
      // Merge logs from different instances
      merge_logs: true,
      
      // PM2+ monitoring
      pmx: true,
      
      // Custom startup delay to avoid rapid restarts
      restart_delay: 4000,
    }
  ]
};