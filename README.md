### Catalog Extensions

Custom catalog logic

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench install-app catalog_extensions
```

Core required apps on the target site:
- `erpnext`
- `payments`
- `webshop`

Optional enhancement app:
- `erpnext_shipping_extended`

If the optional app is missing, `catalog_extensions` still installs and works, but automated shipping-rate lookup, pickup automation, and reverse-pickup automation stay in manual mode.

For another-bench deployment, the recommended path is:

```bash
bash apps/catalog_extensions/deploy/full_deploy.sh --site yoursite.local
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/catalog_extensions
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
