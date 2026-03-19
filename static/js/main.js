document.addEventListener('DOMContentLoaded', function () {
  const params = new URLSearchParams(window.location.search);
  if (params.get('open_cart') === '1') {
    const canvas = document.getElementById('cartCanvas');
    if (canvas && window.bootstrap) {
      const instance = new bootstrap.Offcanvas(canvas);
      instance.show();
      params.delete('open_cart');
      const query = params.toString();
      const newUrl = `${window.location.pathname}${query ? '?' + query : ''}${window.location.hash}`;
      window.history.replaceState({}, '', newUrl);
    }
  }

  const toastClose = document.querySelector('[data-close-cart]');
  if (toastClose) {
    toastClose.addEventListener('click', function () {
      const canvas = document.getElementById('cartCanvas');
      if (canvas && window.bootstrap) {
        bootstrap.Offcanvas.getOrCreateInstance(canvas).hide();
      }
    });
  }
});
