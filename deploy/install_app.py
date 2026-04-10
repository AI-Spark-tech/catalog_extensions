#!/usr/bin/env python3
"""
Automated Catalog Extensions App Installer
Installs and configures the catalog_extensions app without human intervention
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path

REQUIRED_APPS = ("erpnext", "payments", "webshop")
OPTIONAL_APPS = ("erpnext_shipping_extended",)


def run_bench_command(command, cwd=None, site=None):
    """Execute a bench command safely."""
    if site:
        full_command = f"bench --site {site} {command}"
    else:
        full_command = f"bench {command}"
    
    try:
        result = subprocess.run(
            full_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def get_python_path(bench_path):
    env_python = Path(bench_path) / "env" / "bin" / "python"
    return str(env_python) if env_python.exists() else sys.executable


def get_site_apps(site, bench_path):
    success, stdout, stderr = run_bench_command(
        "list-apps --format json",
        cwd=bench_path,
        site=site,
    )
    if not success:
        return None, stderr or stdout

    try:
        parsed = json.loads(stdout)
    except Exception:
        parsed = [line.strip() for line in stdout.splitlines() if line.strip()]

    apps = []
    for row in parsed:
        if isinstance(row, dict):
            app_name = row.get("name")
        else:
            app_name = row
        if app_name:
            apps.append(app_name)
    return apps, ""


def check_site_dependencies(site, bench_path):
    print(f"[STEP] Checking required site dependencies for {site}...")
    apps, error = get_site_apps(site, bench_path)
    if apps is None:
        print(f"[ERROR] Could not read installed apps for {site}: {error}")
        return False

    missing_required = [app for app in REQUIRED_APPS if app not in apps]
    if missing_required:
        print(
            "[ERROR] Missing required apps on site "
            f"{site}: {', '.join(missing_required)}. Install them before catalog_extensions."
        )
        return False

    missing_optional = [app for app in OPTIONAL_APPS if app not in apps]
    for app in missing_optional:
        print(
            f"[WARNING] Optional app '{app}' is not installed. "
            "Shipping-rate automation and reverse-pickup automation will stay in manual mode."
        )

    print("[SUCCESS] Site dependency check passed")
    return True


def run_setup_script(script_name, site, bench_path):
    python_path = get_python_path(bench_path)
    script_path = Path(bench_path) / "apps" / "catalog_extensions" / "deploy" / script_name
    result = subprocess.run(
        [python_path, str(script_path), "--site", site],
        cwd=bench_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode == 0:
        print(result.stdout.strip())
        return True

    print(result.stdout.strip())
    print(f"[ERROR] {script_name} failed: {result.stderr}")
    return False


def verify_setup(site, bench_path):
    print(f"[STEP] Verifying setup artifacts on {site}...")
    success, stdout, stderr = run_bench_command(
        "execute catalog_extensions.install_support.assert_setup_complete",
        cwd=bench_path,
        site=site,
    )
    if success:
        warnings = stdout.strip()
        if warnings and warnings != "[]":
            print(f"[WARNING] Optional dependency notices: {warnings}")
        print("[SUCCESS] Setup verification passed")
        return True

    print(f"[ERROR] Setup verification failed: {stderr or stdout}")
    return False


def check_app_installed(site, bench_path, app_name):
    """Check if app is already installed on site."""
    success, stdout, stderr = run_bench_command(
        f"list-apps --format json",
        cwd=bench_path,
        site=site
    )
    if success:
        try:
            apps = json.loads(stdout)
            return app_name in [a.get('name') for a in apps]
        except:
            return app_name in stdout
    return False


def install_app(site, bench_path, app_name="catalog_extensions"):
    """Install the catalog_extensions app on the site."""
    print(f"[STEP] Installing {app_name} on site {site}...")
    
    # Check if already installed
    if check_app_installed(site, bench_path, app_name):
        print(f"[INFO] {app_name} is already installed on {site}")
        return True
    
    # Install the app
    success, stdout, stderr = run_bench_command(
        f"install-app {app_name}",
        cwd=bench_path,
        site=site
    )
    
    if success:
        print(f"[SUCCESS] {app_name} installed successfully")
        return True
    else:
        print(f"[ERROR] Failed to install {app_name}: {stderr}")
        return False


def migrate_site(site, bench_path):
    """Run migration to create DocTypes."""
    print(f"[STEP] Running migration for {site}...")
    
    success, stdout, stderr = run_bench_command(
        "migrate",
        cwd=bench_path,
        site=site
    )
    
    if success:
        print("[SUCCESS] Migration completed")
        return True
    else:
        print(f"[ERROR] Migration failed: {stderr}")
        return False


def clear_cache(site, bench_path):
    """Clear site cache."""
    print(f"[STEP] Clearing cache...")
    
    success, stdout, stderr = run_bench_command(
        "clear-cache",
        cwd=bench_path,
        site=site
    )
    
    if success:
        print("[SUCCESS] Cache cleared")
        return True
    else:
        print(f"[WARNING] Cache clear failed: {stderr}")
        return False


def restart_bench(bench_path):
    """Restart bench services."""
    print(f"[STEP] Restarting bench...")
    
    success, stdout, stderr = run_bench_command(
        "restart",
        cwd=bench_path
    )
    
    if success:
        print("[SUCCESS] Bench restarted")
        return True
    else:
        print(f"[WARNING] Bench restart failed: {stderr}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Automated Catalog Extensions App Installer"
    )
    parser.add_argument(
        "--site",
        required=True,
        help="Site name to install on"
    )
    parser.add_argument(
        "--bench-path",
        default=os.getcwd(),
        help="Path to bench directory (default: current directory)"
    )
    parser.add_argument(
        "--skip-restart",
        action="store_true",
        help="Skip bench restart"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("CATALOG EXTENSIONS - AUTOMATED INSTALLER")
    print("=" * 60)
    print(f"Site: {args.site}")
    print(f"Bench Path: {args.bench_path}")
    print("=" * 60)
    
    # Verify bench path
    bench_path = Path(args.bench_path)
    if not (bench_path / "sites").exists():
        print(f"[ERROR] Invalid bench path: {args.bench_path}")
        sys.exit(1)

    if not check_site_dependencies(args.site, str(bench_path)):
        sys.exit(1)
    
    # Step 1: Install app
    if not install_app(args.site, str(bench_path)):
        sys.exit(1)
    
    # Step 2: Migrate to create DocTypes
    if not migrate_site(args.site, str(bench_path)):
        sys.exit(1)

    if not run_setup_script("setup_doctypes.py", args.site, str(bench_path)):
        sys.exit(1)

    if not run_setup_script("setup_custom_fields.py", args.site, str(bench_path)):
        sys.exit(1)

    if not verify_setup(args.site, str(bench_path)):
        sys.exit(1)
    
    # Step 3: Clear cache
    clear_cache(args.site, str(bench_path))
    
    # Step 4: Restart (optional)
    if not args.skip_restart:
        restart_bench(str(bench_path))
    
    print("=" * 60)
    print("[COMPLETE] Installation finished!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Configure Catalog Price Ranges in Desk")
    print("2. Review webshop checkout settings and website item setup")
    print("3. Install erpnext_shipping_extended later if you want automated shipping enhancements")


if __name__ == "__main__":
    main()
