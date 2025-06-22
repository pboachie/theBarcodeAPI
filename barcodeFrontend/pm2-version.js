const pmx = require('@pm2/io');

pmx.initModule({
  widget: {
    type: 'generic',
    logo: 'https://app.pm2.io/icons/cpu.png',
    theme: ['#111111', '#1B2228', '#31C2F1'],
    el: {
      probes: [
        {
          name: 'Version',
          value: () => process.env.NEXT_PUBLIC_APP_VERSION || 'N/A'
        }
      ]
    }
  }
});