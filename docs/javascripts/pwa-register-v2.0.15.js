(() => {
  if (!('serviceWorker' in navigator)) return;

  window.addEventListener('load', async () => {
    const manifest = document.querySelector('link[rel="manifest"]');
    if (!manifest) return;

    const manifestUrl = new URL(manifest.href, window.location.href);
    const serviceWorkerUrl = new URL('service-worker.js', manifestUrl);
    const scopeUrl = new URL('./', manifestUrl);

    try {
      const registration = await navigator.serviceWorker.register(serviceWorkerUrl.href, {
        scope: scopeUrl.pathname,
        updateViaCache: 'none'
      });
      await registration.update();
    } catch (error) {
      console.warn('PWA service worker registration failed', error);
    }
  });
})();
