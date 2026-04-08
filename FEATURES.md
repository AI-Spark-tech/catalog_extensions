# Catalog Extensions Features

This document summarizes the implemented features in the `catalog_extensions` custom app, grouped by functional area.

## Frontend Features

| Feature | Description | Main Files |
|---|---|---|
| Contextual facet sidebar | Adds dynamic webshop facets for item groups, brands, price ranges, offers, and badges based on the current listing context. | `catalog_extensions/api.py`, `catalog_extensions/public/js/catalog_facets.js`, `catalog_extensions/hooks.py` |
| Infinite scroll | Loads additional products on webshop listing pages for both grid and list layouts while preserving current filters and search state. | `catalog_extensions/public/js/infinite_scroll.js` |
| Search-on-Enter | Submits listing search when the user presses Enter and injects the search term into webshop query filters. | `catalog_extensions/public/js/catalog_search_enter.js` |
| Listing quantity controls | Adds quantity increment/decrement controls directly on product cards and syncs updates with the webshop cart. | `catalog_extensions/public/js/listing_quantity.js` |
| Product offer display | Shows available offers on product cards using `Website Offer` data. | `catalog_extensions/public/js/product_offers.js`, `catalog_extensions/api.py` |
| Product brand display | Injects brand labels into listing cards by fetching brand data for visible items. | `catalog_extensions/public/js/product_brand.js`, `catalog_extensions/api.py` |
| Product badge display | Renders badges such as `New`, `Bestseller`, `On Sale`, and `Low Stock` on product cards. | `catalog_extensions/public/js/badges.js`, `catalog_extensions/api.py` |
| Image zoom | Adds hover or tap zoom for product detail images and product listing images. | `catalog_extensions/public/js/image_zoom_hover.js`, `catalog_extensions/public/js/image_zoom.js`, `catalog_extensions/zoom_config.py` |
| Simple checkout UI controls | Optionally hides shipping and payment UI on the cart page when simplified checkout is enabled. | `catalog_extensions/public/js/simple_checkout.js`, `catalog_extensions/simple_checkout.py` |
| Cart mobile fixes | Adjusts cart page layout and address visibility for small screens. | `catalog_extensions/public/js/cart_fixes.js`, `catalog_extensions/public/css/catalog_overrides.css` |
| Order success redirect | Redirects users to a custom order success page after placing an order. | `catalog_extensions/public/js/order_success_redirect.js`, `catalog_extensions/www/order-success/index.html`, `catalog_extensions/www/order-success/index.py` |
| Portal delivery tracking UI | Adds a delivery-tracking block to portal order pages with milestone and shipment information. | `catalog_extensions/public/js/delivery_tracking.js`, `catalog_extensions/public/css/delivery_tracking.css`, `catalog_extensions/api.py` |
| Catalog visual overrides | Applies custom responsive styling across listing, filter, cart, zoom, and tracking interfaces. | `catalog_extensions/public/css/catalog_overrides.css`, `catalog_extensions/public/css/image_zoom_hover.css`, `catalog_extensions/public/css/delivery_tracking.css` |

## Backend Features

| Feature | Description | Main Files |
|---|---|---|
| Webshop API overrides | Replaces core webshop product listing, search, product info, and cart methods with custom logic. | `catalog_extensions/hooks.py` |
| Customer-group brand restriction | Limits visible brands and products based on customer group mappings and blocks unauthorized product access. | `catalog_extensions/brand_filtering.py`, `catalog_extensions/api.py` |
| Price range filtering | Filters products by price bounds and supports configurable price buckets. | `catalog_extensions/api.py`, `catalog_extensions/doctype/catalog_price_range/catalog_price_range.py` |
| Contextual facet computation | Computes filter counts for categories, brands, price ranges, offers, and badges from the current result set. | `catalog_extensions/api.py` |
| Product search override | Reimplements product search and product-list retrieval while respecting custom brand restrictions. | `catalog_extensions/api.py` |
| Offer and badge filtering sync | Mirrors offers and badges into filterable child-table fields so the product query engine can filter them reliably. | `catalog_extensions/api.py` |
| Consumer discount sync | Syncs `custom_consumer_discount` from `Item` into linked `Website Item` records. | `catalog_extensions/api.py` |
| Badge retrieval APIs | Exposes backend methods for item badges, item offers, item brands, consumer discounts, and template variant ranges. | `catalog_extensions/api.py` |
| Automatic badge generation | Recomputes auto badges such as `New`, `Bestseller`, `On Sale`, and `Low Stock` from business data. | `catalog_extensions/api.py` |
| Scheduled badge maintenance | Runs badge recomputation daily through the scheduler. | `catalog_extensions/hooks.py`, `catalog_extensions/api.py` |
| Simple checkout backend | Applies default address and payment-term behavior and preserves core checkout flow with simplified controls. | `catalog_extensions/simple_checkout.py` |
| Portal order operations | Supports order cancellation, return initiation, refund requests, and safe order tracking for portal users. | `catalog_extensions/api.py` |
| Website item image override | Allows external HTTP(S) image URLs for `Website Item.website_image` instead of only Frappe File records. | `catalog_extensions/overrides/website_item.py`, `catalog_extensions/hooks.py` |
| Zoom asset API | Returns the correct zoom asset bundle based on current site configuration. | `catalog_extensions/zoom_config.py` |

## Admin and Setup Features

| Feature | Description | Main Files |
|---|---|---|
| Install and migrate bootstrapping | Automatically creates required DocTypes and custom-field setup on install and migrate. | `catalog_extensions/install.py`, `deploy/setup_doctypes.py`, `deploy/setup_custom_fields.py` |
| Catalog Price Range DocType | Provides admin-managed price buckets used by listing filters and facet counts. | `deploy/setup_doctypes.py`, `catalog_extensions/doctype/catalog_price_range/catalog_price_range.json` |
| Item Badge child table | Defines badge metadata with badge type, source, and validity dates. | `catalog_extensions/doctype/item_badge/item_badge.json` |
| Webshop Simple Checkout Settings DocType | Lets admins enable simplified checkout and choose address/payment visibility defaults. | `deploy/setup_doctypes.py` |
| Customer Group Brand Mapping DocType | Lets admins map leaf customer groups to allowed brands and cache those restrictions. | `deploy/setup_doctypes.py`, `catalog_extensions/brand_filtering.py` |
| Default price-range seeding | Seeds a starter set of price bands when no `Catalog Price Range` records exist. | `deploy/setup_doctypes.py` |
| Validation rules | Validates customer-group brand mappings and price-range boundaries. | `catalog_extensions/brand_filtering.py`, `catalog_extensions/doctype/catalog_price_range/catalog_price_range.py` |
| Deployment helpers | Includes scripts and notes for app install, DocType setup, and deployment to another bench. | `deploy/install_app.py`, `deploy/full_deploy.sh`, `deploy/README.md`, `deploy/INSTALL_TO_ANOTHER_BENCH.md` |

## Main Custom Models

| Model | Purpose |
|---|---|
| `Catalog Price Range` | Configurable price buckets for filtering and facets |
| `Item Badge` | Child table storing manual and auto badge metadata |
| `Webshop Simple Checkout Settings` | Site-level settings for simplified checkout behavior |
| `Customer Group Brand Mapping` | Customer-group-to-brand restriction rules |
