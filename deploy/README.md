# Catalog Extensions - Automated Deployment

Zero-human-intervention deployment scripts for the `catalog_extensions` Frappe app.

Core required apps on the target site:
- `erpnext`
- `payments`
- `webshop`

Optional enhancement app:
- `erpnext_shipping_extended`

If the optional app is missing, deployment still succeeds. Shipping-rate lookup, pickup automation, and reverse-pickup creation stay in manual mode.

## Quick Start

### One-Command Full Deployment

```bash
cd /path/to/your/bench
bash apps/catalog_extensions/deploy/full_deploy.sh --site yoursite.local --restart
```

## Deployment Scripts

### 1. `full_deploy.sh` - Recommended
**One command to deploy everything.**

```bash
# Full deployment (recommended)
bash apps/catalog_extensions/deploy/full_deploy.sh --site yoursite.local

# With bench restart
bash apps/catalog_extensions/deploy/full_deploy.sh --site yoursite.local --restart

# Skip specific steps
bash apps/catalog_extensions/deploy/full_deploy.sh --site yoursite.local --skip-fields
```

**What it does:**
1. ✅ Checks prerequisites (bench directory, site exists)
2. ✅ Fails fast if mandatory apps are missing on the target site
3. ✅ Installs the `catalog_extensions` app
4. ✅ Runs migration to create DocTypes
5. ✅ Creates or updates setup DocTypes and default records
6. ✅ Creates or updates required custom fields and indexes
7. ✅ Clears cache
8. ✅ Restarts bench (optional)
9. ✅ Verifies setup completion and reports optional integration warnings

---

### 2. `install_app.py` - App Installation Only
**Installs the app and runs migration.**

```bash
cd /path/to/bench
python3 apps/catalog_extensions/deploy/install_app.py --site yoursite.local
```

**Options:**
- `--site SITE` - Required. Site to install on
- `--bench-path PATH` - Bench directory (default: current directory)
- `--skip-restart` - Skip bench restart

---

### 3. `setup_doctypes.py` - DocType Setup
**Creates the `Catalog Price Range` DocType and default records.**

```bash
cd /path/to/bench
python3 apps/catalog_extensions/deploy/setup_doctypes.py --site yoursite.local
```

**Options:**
- `--site SITE` - Required. Site to setup
- `--skip-defaults` - Don't create default price ranges

**Default Price Ranges Created:**
- Under $25
- $25 - $50
- $50 - $100
- $100 - $250
- Over $250

---

### 4. `setup_custom_fields.py` - Custom Fields Setup
**Creates all required custom fields.**

```bash
cd /path/to/bench
python3 apps/catalog_extensions/deploy/setup_custom_fields.py --site yoursite.local
```

**Options:**
- `--site SITE` - Required. Site to setup
- `--skip-item` - Skip Item DocType fields
- `--skip-website-item` - Skip Website Item DocType fields

**Fields Created:**

| DocType | Field | Type | Purpose |
|---------|-------|------|---------|
| Item | `custom_consumer_discount` | Percent | Discount % for display |
| Item | `badges` | Table | Item Badge child table |
| Website Item | `custom_consumer_discount` | Percent | Mirrored discount |
| Website Item | `custom_availability` | Select | Stock status |

---

## Prerequisites

Before running deployment scripts, ensure:

1. **Frappe Bench** is installed and configured
2. **Mandatory dependencies are installed on the target site:**
   ```bash
   bench get-app payments
   bench get-app erpnext
   bench get-app webshop
   bench --site yoursite.local install-app webshop
   ```
3. **Optional shipping enhancement app (only if you want automated shipping features):**
   ```bash
   bench get-app erpnext_shipping_extended
   bench --site yoursite.local install-app erpnext_shipping_extended
   ```
4. **This app is in `apps/catalog_extensions/`**

---

## Deployment Scenarios

### Scenario 1: Fresh Site
```bash
cd /path/to/bench

# 1. Install mandatory dependencies
bench get-app payments
bench get-app erpnext  
bench get-app webshop

# 2. Create site (if needed)
bench new-site newsite.local

# 3. Install mandatory site apps
bench --site newsite.local install-app erpnext
bench --site newsite.local install-app payments
bench --site newsite.local install-app webshop

# 4. Optional: install automated shipping enhancement
# bench get-app erpnext_shipping_extended
# bench --site newsite.local install-app erpnext_shipping_extended

# 5. Deploy catalog_extensions (ONE COMMAND!)
bash apps/catalog_extensions/deploy/full_deploy.sh --site newsite.local --restart
```

### Scenario 2: Existing Site
```bash
cd /path/to/bench

# Just run the deploy script
bash apps/catalog_extensions/deploy/full_deploy.sh --site existingsite.local --restart
```

### Scenario 3: Multi-Site Deployment
```bash
cd /path/to/bench

# Deploy to multiple sites
for site in site1.local site2.local site3.local; do
    echo "Deploying to $site..."
    bash apps/catalog_extensions/deploy/full_deploy.sh --site $site --restart
done
```

### Scenario 4: CI/CD Pipeline
```bash
#!/bin/bash
# deploy_pipeline.sh

set -e

SITE=${SITE:-"default.local"}
BENCH_PATH=${BENCH_PATH:-"/home/frappe/frappe-bench"}

cd $BENCH_PATH

# Run full deployment
bash apps/catalog_extensions/deploy/full_deploy.sh \
    --site $SITE \
    --restart \
    || exit 1

# Run tests
bench --site $SITE run-tests --app catalog_extensions

echo "Deployment successful!"
```

---

## Troubleshooting

### "Not in a valid bench directory"
Make sure you're running the script from the bench root directory (where `sites/` and `apps/` folders exist).

### "App not found"
The app must be cloned/linked to `apps/catalog_extensions/` before running deployment.

### "Required app is missing"
Install the missing core app on the target site first:
```bash
bench get-app <app_name>
bench --site yoursite.local install-app <app_name>
```

### "Optional app warning"
This is non-fatal. It means shipping-related automation will stay manual until you install:
```bash
bench get-app erpnext_shipping_extended
bench --site yoursite.local install-app erpnext_shipping_extended
```

### "Custom fields not appearing"
Clear cache and restart:
```bash
bench --site yoursite.local clear-cache
bench restart
```

---

## Post-Deployment Configuration

After successful deployment, configure in Desk:

1. **Catalog Price Ranges:**
   - Go to: `Catalog Extensions > Catalog Price Range`
   - Adjust default ranges or create new ones

2. **Scheduled Job:**
   - The `recompute_item_badges` job is already configured in `hooks.py`
   - It runs daily via scheduler
   - Run manually: `bench --site yoursite.local execute catalog_extensions.api.recompute_item_badges`

3. **Webshop Settings:**
   - Configure price list in Webshop Settings
   - Ensure Website Items are published
4. **Optional shipping automation:**
   - Install `erpnext_shipping_extended` only if you want automated shipping-rate and reverse-pickup features

---

## Verification

Check if deployment was successful:

```bash
# Check installed apps
bench --site yoursite.local list-apps

# Check API endpoints
curl https://yoursite.local/api/method/catalog_extensions.api.get_filter_facets

# Check DocType exists
bench --site yoursite.local mariadb -e "SELECT name FROM tabDocType WHERE name='Catalog Price Range'"
```

---

## Script Reference

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `full_deploy.sh` | Complete deployment | Recommended for all deployments |
| `install_app.py` | App + migration only | When DocTypes already exist |
| `setup_doctypes.py` | Create DocTypes | When you need to recreate DocTypes |
| `setup_custom_fields.py` | Create custom fields | When fields need to be recreated |

---

## Security Notes

- All scripts use `ignore_permissions=True` for automated setup
- Scripts must be run from the bench directory
- Ensure proper file permissions on scripts: `chmod +x *.sh *.py`

---

## Support

For issues or questions:
1. Check logs in `sites/{site}/logs/`
2. Verify bench is in developer mode for debugging
3. Run scripts with `--help` for usage information
