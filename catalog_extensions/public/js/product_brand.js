frappe.ready(function () {
  var maxRetries = 5;
  var retryCount = 0;
  var brandsCache = {};
  var inflightRequest = false;

  function getOrCreateMetaRow(card, categoryEl, titleRow) {
    var existingMetaRow = card.querySelector('.product-meta-row');
    if (existingMetaRow) {
      return existingMetaRow;
    }

    var metaRow = document.createElement('div');
    metaRow.className = 'product-meta-row';

    if (categoryEl) {
      categoryEl.classList.add('product-meta-category');
    }

    if (titleRow && titleRow.parentNode) {
      titleRow.parentNode.insertBefore(metaRow, titleRow);
    } else if (categoryEl && categoryEl.parentNode) {
      categoryEl.parentNode.insertBefore(metaRow, categoryEl);
    } else {
      var cardBody = card.querySelector('.card-body');
      if (!cardBody) {
        return null;
      }
      cardBody.insertBefore(metaRow, cardBody.firstChild);
    }

    if (categoryEl) {
      metaRow.appendChild(categoryEl);
    }

    return metaRow;
  }

  function normalizeCategoryText(categoryEl) {
    if (!categoryEl) {
      return '';
    }

    var categoryText = (categoryEl.textContent || '').replace(/\s+/g, ' ').trim();
    categoryEl.textContent = categoryText;
    return categoryText;
  }
  
  function injectProductBrands() {
    var listing = document.getElementById('product-listing');
    if (!listing) {
      retryCount++;
      if (retryCount < maxRetries) {
        setTimeout(injectProductBrands, 500);
      }
      return;
    }

    // Only process cards that haven't been processed yet
    var cards = listing.querySelectorAll('.item-card');
    var unprocessedCards = Array.prototype.filter.call(cards, function (card) {
      return !card.hasAttribute('data-brand-injected');
    });

    if (!unprocessedCards.length) {
      return;
    }

    // Collect item codes from unprocessed cards
    var codesSet = new Set();
    unprocessedCards.forEach(function (card) {
      var codeEl = card.querySelector('[data-item-code]');
      if (!codeEl) return;
      var code = codeEl.getAttribute('data-item-code');
      if (code) codesSet.add(code);
    });

    var itemCodes = Array.from(codesSet);
    if (!itemCodes.length) {
      retryCount++;
      if (retryCount < maxRetries) {
        setTimeout(injectProductBrands, 500);
      }
      return;
    }

    // If we already have cache for all codes, inject directly without an API call
    var missingCodes = itemCodes.filter(function (c) { return !brandsCache[c]; });
    function applyBrands() {
      unprocessedCards.forEach(function (card) {
        var codeEl = card.querySelector('[data-item-code]');
        var code = codeEl ? codeEl.getAttribute('data-item-code') : null;
        if (!code) return;
        var brand = brandsCache[code];
        if (!brand) return;

        var nameEl = card.querySelector('.product-title');
        var titleLink = nameEl ? nameEl.closest('a') : null;
        var titleRow = titleLink ? titleLink.parentNode : null;
        var categoryEl = card.querySelector('.product-category');
        var categoryText = normalizeCategoryText(categoryEl);
        var metaRow = getOrCreateMetaRow(card, categoryEl, titleRow);
        if (!metaRow) return;

        var brandDiv = metaRow.querySelector('.brand-container');
        if (!brandDiv) {
          brandDiv = document.createElement('div');
          brandDiv.className = 'brand-container mb-1';
          metaRow.insertBefore(brandDiv, metaRow.firstChild);
        }
        brandDiv.innerHTML = '<span class="brand-badge">' + __(brand) + '</span>';

        var separator = metaRow.querySelector('.product-meta-separator');
        if (categoryText) {
          if (!separator) {
            separator = document.createElement('span');
            separator.className = 'product-meta-separator';
            separator.textContent = '•';
          }
          if (brandDiv.nextSibling !== separator) {
            metaRow.insertBefore(separator, categoryEl || null);
          }
          if (categoryEl) {
            categoryEl.textContent = categoryText;
          }
        } else if (separator) {
          separator.remove();
        }

        card.setAttribute('data-brand-injected', '1');
      });
    }

    if (!missingCodes.length) {
      applyBrands();
      return;
    }

    if (inflightRequest) {
      return;
    }

    inflightRequest = true;

    frappe.call({
      method: 'catalog_extensions.api.get_item_brands',
      args: { item_codes: missingCodes },
      callback: function (r) {
        inflightRequest = false;
        if (r && r.message) {
          Object.keys(r.message).forEach(function (code) {
            brandsCache[code] = r.message[code];
          });
        }
        applyBrands();
      },
      error: function(err) {
        inflightRequest = false;
        console.error('[Brand] API error:', err);
      }
    });
  }

  // Initial try after grid renders
  setTimeout(injectProductBrands, 800);

  // Re-run after infinite scroll appends items
  document.addEventListener('products-loaded', function () {
    setTimeout(injectProductBrands, 50);
  });

  // Observe product listing for changes (e.g. filters, sorting) and re-inject.
  var observerInitialized = false;
  function setupBrandObserver() {
    if (observerInitialized) return;
    var listing = document.getElementById('product-listing');
    if (!listing || !window.MutationObserver) return;

    observerInitialized = true;
    var timeoutId = null;
    var observer = new MutationObserver(function () {
      // Debounce rapid DOM changes into a single inject call
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(injectProductBrands, 600);
    });

    observer.observe(listing, { childList: true, subtree: true });
  }

  setTimeout(setupBrandObserver, 1000);
});
