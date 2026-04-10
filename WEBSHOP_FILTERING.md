# Webshop Filtering

This document explains how catalog filtering works in `catalog_extensions` for the ERPNext/Webshop storefront.

## Goal

The storefront must:

- restrict products by customer-group allowed brands
- apply the restriction at query level, not only in the UI
- keep sidebar facets aligned with the actual result set
- avoid showing brand choices the current customer cannot access

## Main Components

- `catalog_extensions.brand_filtering`
  - resolves the active customer group
  - reads allowed brands from `Customer Group Brand Mapping`
  - caches mappings
  - validates mapping records
- `catalog_extensions.api`
  - overrides webshop listing, detail, and search APIs
  - builds contextual facet queries
  - applies brand filtering before product data is returned
- `catalog_extensions/public/js/catalog_facets.js`
  - loads custom facet data from the backend
  - updates the visible sidebar
  - prunes core webshop Brand and Item Group options using contextual facet data

## Data Model

### Customer Group Brand Mapping

The DocType `Customer Group Brand Mapping` stores the allowed brands per customer group.

Fields:

- `customer_group` (`Link / Customer Group`)
- `brand` (`Link / Brand`)
- `enabled` (`Check`)

Rules:

- if a customer group has one or more enabled mappings, only those brands are allowed
- if a customer group has no enabled mappings, all brands are allowed
- duplicate `customer_group + brand` combinations are rejected
- non-leaf customer groups are rejected in validation

## Request Flow

### 1. Resolve the active customer group

`catalog_extensions.brand_filtering.get_current_customer_group()` uses:

1. the logged-in website user's linked `Customer.customer_group`
2. fallback to `Webshop Settings.default_customer_group`

### 2. Resolve allowed brands

`get_allowed_brands_for_customer_group()` loads the mapped brands for that customer group and caches them in Redis.

Cache key:

- `catalog_extensions:customer_group_brand_filters`

Cache is cleared on mapping update/delete through `doc_events`.

### 3. Enforce filtering at query level

`apply_brand_filter()` is the main enforcement helper.

Behavior:

- if no mappings exist for the active customer group, do not restrict brands
- if mappings exist and no brand was selected by the user, inject all allowed brands
- if mappings exist and the user selected brands, intersect user-selected brands with allowed brands
- if intersection is empty, return a no-match state so the result set is empty

This keeps access control in the backend and prevents disallowed products from leaking through search, direct listing, or sidebar filters.

## Product APIs

### Listing API

Override:

- `webshop.webshop.api.get_product_filter_data`
  - mapped to `catalog_extensions.api.get_products`

Responsibilities:

- normalize incoming `field_filters`
- merge top-level `brand` into `field_filters`
- apply customer-group brand restriction
- preserve existing custom filters like price, offers, badges
- pass final filters into `ProductQuery`

### Product Detail API

Override:

- `webshop.webshop.shopping_cart.product_info.get_product_info_for_website`
  - mapped to `catalog_extensions.api.get_product_info`

Responsibilities:

- call `assert_item_allowed(item_code)` before returning product info

This ensures a disallowed product cannot be accessed just by opening its route or calling the detail API.

### Search APIs

Overrides:

- `webshop.templates.pages.product_search.search`
- `webshop.templates.pages.product_search.product_search`
- `webshop.templates.pages.product_search.get_product_list`

Responsibilities:

- query `Website Item` only from the allowed result set
- keep product search aligned with listing restrictions

## Facet Strategy

Facet behavior is built in `catalog_extensions.api.get_filter_facets()`.

The backend computes facet data using `_build_facet_where_clause()`.

### Brand facet

Brand facet logic excludes only the current brand filter:

- customer-group allowed brands still apply
- item group still applies
- search still applies
- price still applies
- offers still apply
- badges still apply

This allows the brand sidebar to show only brands that are valid for the current result set.

### Price facet

Price facet logic excludes only the current price filter:

- customer-group allowed brands still apply
- brand still applies
- item group still applies
- search still applies
- offers still apply
- badges still apply

This keeps min/max bounds and configured price-range counts contextual to the current filtered dataset.

### Offers and badges

Offers and badges are also computed from the active filtered dataset.

### Item Group facet

Item Group counts are computed from the active filtered dataset with the current brand restriction applied. The visible options are later pruned in the frontend.

## Frontend Strategy

The visible Brand and Item Group blocks are still rendered by the core webshop templates using core filter metadata.

That means backend facet filtering alone is not enough.

`catalog_extensions/public/js/catalog_facets.js` does two things:

1. requests contextual facet data from `catalog_extensions.api.get_filter_facets`
2. updates the visible core filter blocks

For Brand and Item Group:

- options missing from the contextual facet response are hidden
- counts are rewritten from the backend facet response
- blocks with no valid options are hidden

This is necessary because the core webshop sidebar is rendered before our custom facet API runs.

## Supported Filters in `_build_facet_where_clause()`

The facet/query builder currently understands:

- `brand`
- `item_group`
- `search`
- `price_from`
- `price_to`
- `offers` / `offers_title`
- `badges`
- `item_code`

It also applies the customer-group brand restriction automatically.

## Why Query-Level Enforcement Matters

UI-only filtering is not sufficient because users can still:

- call APIs directly
- use search endpoints
- open product URLs directly
- combine filters in ways the UI did not anticipate

For that reason the access restriction is enforced in backend methods first, then reflected in the sidebar.

## Files to Review

- `apps/catalog_extensions/catalog_extensions/brand_filtering.py`
- `apps/catalog_extensions/catalog_extensions/api.py`
- `apps/catalog_extensions/catalog_extensions/public/js/catalog_facets.js`
- `apps/catalog_extensions/catalog_extensions/hooks.py`
- `apps/catalog_extensions/deploy/setup_doctypes.py`
- `apps/catalog_extensions/deploy/setup_custom_fields.py`

## Operational Notes

After changing DocType setup or hooks, run:

```bash
bench --site <site> migrate
bench --site <site> clear-cache
```

If the sidebar still shows stale options after a code change, also check:

- built assets
- browser cache / hard refresh
- whether the site is loading the latest `catalog_facets.js`

## Extension Guidance

If you add a new storefront filter:

1. support it in `_build_facet_where_clause()`
2. apply it in product listing/search APIs
3. decide whether its facet should exclude only itself or use the fully filtered dataset
4. update the frontend facet rendering if the core UI still renders stale options

Keep the rule simple:

- enforce access in backend
- compute facets from the filtered dataset
- use frontend only to reconcile the already-rendered core sidebar
