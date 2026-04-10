from contextlib import contextmanager

import frappe
from frappe.utils import get_url

# Reuse existing webshop cart logic; do not duplicate it
from erpnext.accounts.doctype.payment_request.payment_request import (
	get_amount as core_get_payment_request_amount,
	get_gateway_details as core_get_gateway_details,
	make_payment_request as core_make_payment_request,
)
from catalog_extensions.stock_guard import enrich_cart_item
from webshop.webshop.shopping_cart import cart as core_cart
from webshop.webshop.doctype.webshop_settings.webshop_settings import get_shopping_cart_settings

PAYMENT_MODE_PREPAID = "PREPAID"
PAYMENT_MODE_COD = "COD"
PAYMENT_MODE_OPTIONS = (PAYMENT_MODE_PREPAID, PAYMENT_MODE_COD)


def get_payment_mode_for_doc(doc) -> str:
	"""Return the effective webshop payment mode for a sales document."""
	mode = ""
	if doc:
		mode = getattr(doc, "webshop_payment_mode", "") or doc.get("webshop_payment_mode")
	mode = str(mode or "").strip().upper()
	return mode if mode in PAYMENT_MODE_OPTIONS else PAYMENT_MODE_PREPAID


def is_simple_checkout_enabled() -> bool:
	"""Return whether checkout overrides are active for this site."""
	settings = _get_settings()
	return _requires_checkout_overrides(settings)


def _is_simple_checkout_active(settings=None) -> bool:
	"""Return whether catalog_extensions should apply checkout overrides."""
	if settings is None:
		settings = _get_settings()
	return _requires_checkout_overrides(settings)


def _get_settings():
	"""Fetch webshop checkout settings if the doctype exists.

	Returns None if the doctype/record is missing so that core behaviour is preserved.
	"""
	doctype = "Webshop Simple Checkout Settings"
	try:
		return frappe.get_cached_doc(doctype)
	except (frappe.DoesNotExistError, frappe.PermissionError):
		# Settings not configured; behave like core
		return None


def _is_shipping_section_disabled(settings=None) -> bool:
	if settings is None:
		settings = _get_settings()
	return bool(settings and getattr(settings, "hide_shipping_on_webshop", 0))


def _is_payment_section_disabled(settings=None) -> bool:
	if settings is None:
		settings = _get_settings()
	return bool(settings and getattr(settings, "hide_payment_on_webshop", 0))


def _requires_checkout_overrides(settings=None) -> bool:
	return _is_shipping_section_disabled(settings) or _is_payment_section_disabled(settings)


def _get_enabled_payment_modes(settings=None) -> list[str]:
	settings = settings or _get_settings()
	if _is_payment_section_disabled(settings):
		return []
	enable_prepaid = True if not settings else bool(getattr(settings, "enable_prepaid", 1))
	enable_cod = bool(settings and getattr(settings, "enable_cod", 0))

	modes = []
	if enable_prepaid:
		modes.append(PAYMENT_MODE_PREPAID)
	if enable_cod:
		modes.append(PAYMENT_MODE_COD)

	return modes or [PAYMENT_MODE_PREPAID]


def _get_default_payment_mode(settings=None, enabled_modes=None) -> str:
	settings = settings or _get_settings()
	enabled_modes = enabled_modes or _get_enabled_payment_modes(settings)
	if not enabled_modes:
		return PAYMENT_MODE_PREPAID
	default_mode = str(getattr(settings, "default_payment_mode", "") or "").strip().upper()
	if default_mode in enabled_modes:
		return default_mode
	if PAYMENT_MODE_PREPAID in enabled_modes:
		return PAYMENT_MODE_PREPAID
	return enabled_modes[0]


def _set_checkout_payment_mode(doc, payment_mode: str) -> str:
	payment_mode = str(payment_mode or "").strip().upper()
	if payment_mode not in PAYMENT_MODE_OPTIONS:
		payment_mode = PAYMENT_MODE_PREPAID

	setattr(doc, "webshop_payment_mode", payment_mode)
	if hasattr(doc, "_values") and isinstance(getattr(doc, "_values"), dict):
		doc._values["webshop_payment_mode"] = payment_mode
	return payment_mode


def _persist_checkout_payment_mode(doc, payment_mode: str) -> str:
	payment_mode = _set_checkout_payment_mode(doc, payment_mode)
	docname = getattr(doc, "name", None) or (doc.get("name") if doc else None)
	doctype = getattr(doc, "doctype", None) or (doc.get("doctype") if doc else None)
	if not docname or not doctype:
		return payment_mode

	if hasattr(doc, "db_set"):
		doc.db_set("webshop_payment_mode", payment_mode, update_modified=False)
	else:
		frappe.db.set_value(doctype, docname, "webshop_payment_mode", payment_mode, update_modified=False)

	return payment_mode


@contextmanager
def _run_as(user: str):
	session = getattr(frappe, "session", None)
	previous_user = getattr(session, "user", None)
	if previous_user is None and isinstance(session, dict):
		previous_user = session.get("user")
	previous_user = previous_user or "Guest"
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(previous_user)


def _resolve_checkout_payment_mode(quotation=None, settings=None, requested_mode=None) -> str:
	settings = settings or _get_settings()
	if _is_payment_section_disabled(settings):
		return PAYMENT_MODE_PREPAID
	enabled_modes = _get_enabled_payment_modes(settings)

	for candidate in (
		requested_mode,
		get_payment_mode_for_doc(quotation) if quotation else "",
		_get_default_payment_mode(settings, enabled_modes),
	):
		mode = str(candidate or "").strip().upper()
		if mode in enabled_modes:
			return mode

	return enabled_modes[0]


def _ensure_defaults_on_quotation(quotation, settings):
	"""Ensure address and payment defaults are set on the given cart quotation.

	This mutates and saves the quotation in-place, reusing core helpers.
	"""
	if not quotation or not settings:
		return

	def _ensure_minimal_address(party):
		"""Ensure at least one Address exists and is linked to the party.

		Creates a minimal Address for Customer parties when none exist.
		Returns list of address docs (possibly newly created).
		"""
		address_docs = core_cart.get_address_docs(party=party)
		if address_docs:
			return address_docs

		# Only auto-create for Customer (portal user flow)
		if not party or getattr(party, "doctype", None) != "Customer":
			return address_docs

		# Conservative defaults: these satisfy mandatory address fields on most ERPNext setups.
		# If your Address doctype has stricter mandatory fields, adjust here.
		country = frappe.db.get_single_value("System Settings", "country") or "India"
		address_title = (getattr(party, "customer_name", None) or getattr(party, "name", None) or "Customer")

		addr = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": address_title,
				"address_type": "Shipping",
				"address_line1": "Default Address",
				"city": "Default",
				"country": country,
				"links": [
					{
						"link_doctype": "Customer",
						"link_name": party.name,
					}
				],
			}
		)
		addr.flags.ignore_permissions = True
		addr.insert(ignore_permissions=True)
		frappe.db.commit()

		return core_cart.get_address_docs(party=party)

	# 1) Ensure a default address only when shipping has been explicitly disabled.
	if _is_shipping_section_disabled(settings) and not (
		getattr(quotation, "shipping_address_name", None) or getattr(quotation, "customer_address", None)
	):
		party = core_cart.get_party()
		address_docs = _ensure_minimal_address(party)

		default_type = getattr(settings, "default_shipping_address_type", None)
		chosen_doc = None

		if default_type in ("Shipping", "Billing"):
			chosen_doc = next(
				(a for a in address_docs if getattr(a, "address_type", None) == default_type),
				None,
			)

		# Fallback: first address returned by core ordering.
		if not chosen_doc and address_docs:
			chosen_doc = address_docs[0]

		if chosen_doc and getattr(chosen_doc, "name", None):
			quotation.shipping_address_name = chosen_doc.name
			quotation.customer_address = chosen_doc.name
			quotation.flags.ignore_permissions = True
			quotation.save()

			# Re-apply cart settings to update taxes/totals/shipping rules based on address
			core_cart.apply_cart_settings(quotation=quotation)
			quotation.flags.ignore_permissions = True
			quotation.save()

	# 2) Ensure default payment terms only when payment has been explicitly disabled.
	payment_mode = get_payment_mode_for_doc(quotation)
	if (
		payment_mode != PAYMENT_MODE_COD
		and _is_payment_section_disabled(settings)
		and getattr(settings, "default_payment_term_template", None)
		and not getattr(quotation, "payment_terms_template", None)
	):
		quotation.payment_terms_template = settings.default_payment_term_template
		quotation.flags.ignore_permissions = True
		quotation.save()


def _clone_quotation_for_retry(quotation):
	"""Create a fresh cart quotation when the previous payment attempt expired."""
	party = core_cart.get_party()
	company = frappe.db.get_single_value("Webshop Settings", "company")
	new_quotation = frappe.get_doc(
		{
			"doctype": "Quotation",
			"naming_series": get_shopping_cart_settings().quotation_series or "QTN-CART-",
			"quotation_to": quotation.quotation_to,
			"company": company,
			"order_type": "Shopping Cart",
			"status": "Draft",
			"docstatus": 0,
			"party_name": quotation.party_name or party.name,
			"customer_name": quotation.customer_name,
			"contact_person": quotation.contact_person,
			"contact_email": quotation.contact_email or frappe.session.user,
			"shipping_address_name": quotation.shipping_address_name,
			"customer_address": quotation.customer_address,
			"payment_terms_template": quotation.payment_terms_template,
			"selling_price_list": quotation.selling_price_list,
		}
	)
	new_quotation.flags.ignore_permissions = True
	new_quotation.run_method("set_missing_values")

	for item in quotation.get("items") or []:
		new_quotation.append(
			"items",
			{
				"doctype": "Quotation Item",
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.qty,
				"uom": item.uom,
				"stock_uom": item.stock_uom,
				"warehouse": item.warehouse,
				"additional_notes": item.additional_notes,
			},
		)

	core_cart.apply_cart_settings(party, new_quotation)
	new_quotation.flags.ignore_permissions = True
	new_quotation.insert(ignore_permissions=True)
	return new_quotation


def _get_existing_sales_order_for_quotation(quotation_name: str):
	row = frappe.db.sql(
		"""
		SELECT DISTINCT so.name
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		WHERE so.docstatus < 2
		  AND so.order_type = 'Shopping Cart'
		  AND soi.prevdoc_docname = %s
		ORDER BY so.creation DESC
		LIMIT 1
		""",
		(quotation_name,),
		as_dict=True,
	)
	return row[0]["name"] if row else None


def _expire_stale_payment_requests(quotation):
	"""Cancel stale payment requests and force a fresh quotation after failures."""
	requests = frappe.get_all(
		"Payment Request",
		filters={"reference_doctype": "Quotation", "reference_name": quotation.name, "docstatus": 1},
		fields=["name", "status"],
		order_by="creation desc",
	)

	if not requests:
		return quotation

	if any(pr.status == "Paid" for pr in requests):
		return quotation

	failed_or_cancelled = any(pr.status in ("Failed", "Cancelled") for pr in requests)
	for pr_row in requests:
		if pr_row.status in ("Draft", "Requested", "Initiated", "Partially Paid", "Payment Ordered", "Failed"):
			pr_doc = frappe.get_doc("Payment Request", pr_row.name)
			pr_doc.flags.ignore_permissions = True
			pr_doc.cancel()

	if failed_or_cancelled and not _get_existing_sales_order_for_quotation(quotation.name):
		return _clone_quotation_for_retry(quotation)

	return quotation


def _get_checkout_quotation(settings=None):
	quotation = core_cart._get_cart_quotation()
	if settings:
		_set_checkout_payment_mode(quotation, _resolve_checkout_payment_mode(quotation, settings))
	if settings and _requires_checkout_overrides(settings):
		_ensure_defaults_on_quotation(quotation, settings)
	return quotation


def _validate_checkout_readiness(quotation):
	if not quotation.get("items"):
		frappe.throw(frappe._("Your cart is empty."))

	if not (quotation.shipping_address_name or quotation.customer_address):
		frappe.throw(frappe._("Set Shipping Address or Billing Address"))

	if not quotation.company:
		quotation.company = frappe.db.get_single_value("Webshop Settings", "company")


def decorate_quotation_doc(doc):
	"""Override core decorate_quotation_doc to ensure cart uses the same image as listing.

	Calls core decorate_quotation_doc first to preserve all standard functionality,
	then overrides the thumbnail field on cart items to use website_image instead of the processed thumbnail.
	"""
	# First, let core do its standard decoration
	decorated = core_cart.decorate_quotation_doc(doc)

	# Then override thumbnail to match listing image (website_image from Website Item)
	if not decorated or not getattr(decorated, "items", None):
		return decorated

	for d in decorated.items:
		if not getattr(d, "item_code", None):
			continue

		frappe.logger().info(f"[catalog_extensions] Cart item {d.item_code}: decorated website_image={getattr(d, 'website_image', None)}; thumbnail={getattr(d, 'thumbnail', None)}")

		# If core already set a usable thumbnail, keep it
		if getattr(d, "thumbnail", None):
			frappe.logger().info(f"[catalog_extensions] Cart item {d.item_code}: using existing thumbnail={d.thumbnail}")
			enrich_cart_item(d)
			continue

		# Prefer website_image from Website Item (matches product listing)
		website_image = getattr(d, "website_image", None) or frappe.db.get_value(
			"Website Item",
			{"item_code": d.item_code},
			"website_image",
		)
		if website_image:
			d.thumbnail = website_image
			frappe.logger().info(f"[catalog_extensions] Cart item {d.item_code}: thumbnail set from website_image = {website_image}")
			enrich_cart_item(d)
			continue

		# Fallback: use Item.image for variants or if Website Item missing
		item_image = frappe.db.get_value("Item", d.item_code, "image")
		if item_image:
			d.thumbnail = item_image
			frappe.logger().info(f"[catalog_extensions] Cart item {d.item_code}: thumbnail set from Item.image = {item_image}")
			enrich_cart_item(d)
			continue

		frappe.logger().warning(f"[catalog_extensions] Cart item {d.item_code}: no image found; thumbnail remains falsy")
		enrich_cart_item(d)

	return decorated


@frappe.whitelist()
def get_cart_quotation(doc=None):
	"""Thin wrapper around core get_cart_quotation.

	When checkout overrides are active, ensure defaults are applied, then
	delegate back to core for all heavy logic. Image sync is handled by
	our decorate_quotation_doc override.
	"""
	settings = _get_settings()

	# If settings are missing or feature is disabled, just delegate to core
	if not _requires_checkout_overrides(settings):
		return core_cart.get_cart_quotation(doc)

	# When enabled, ensure defaults and then delegate to core.
	# Our decorate_quotation_doc override will adjust images.
	if not doc:
		quotation = _get_checkout_quotation(settings)
		core_cart.set_cart_count(quotation)
	else:
		quotation = doc

	_ensure_defaults_on_quotation(quotation, settings)

	# Let core return the context; our decorate_quotation_doc override will run automatically
	return core_cart.get_cart_quotation(quotation)


@frappe.whitelist(allow_guest=True)
def get_simple_checkout_flags():
	"""Expose webshop checkout visibility flags for frontend JS.

	If settings are missing, this returns all False so UI behaves as core.
	"""
	settings = _get_settings()
	shipping_hidden = _is_shipping_section_disabled(settings)
	payment_hidden = _is_payment_section_disabled(settings)
	checkout_overrides_active = shipping_hidden or payment_hidden
	enabled_modes = _get_enabled_payment_modes(settings)
	default_mode = _get_default_payment_mode(settings, enabled_modes)
	selected_mode = default_mode

	try:
		quotation = core_cart._get_cart_quotation()
		selected_mode = _resolve_checkout_payment_mode(quotation, settings)
	except Exception:
		quotation = None

	effective_enable_prepaid = PAYMENT_MODE_PREPAID in enabled_modes
	effective_enable_cod = PAYMENT_MODE_COD in enabled_modes
	show_payment_mode_selector = len(enabled_modes) > 1
	show_online_payment_ui = selected_mode == PAYMENT_MODE_PREPAID and not payment_hidden and effective_enable_prepaid

	if not checkout_overrides_active:
		return {
			"enable_simple_checkout": False,
			"hide_shipping_on_webshop": False,
			"hide_payment_on_webshop": False,
			"enable_cancel_order": False,
			"enable_prepaid": effective_enable_prepaid,
			"enable_cod": effective_enable_cod,
			"default_payment_mode": default_mode,
			"selected_payment_mode": selected_mode,
			"show_payment_mode_selector": show_payment_mode_selector,
			"show_online_payment_ui": show_online_payment_ui,
		}

	return {
		"enable_simple_checkout": True,
		"hide_shipping_on_webshop": shipping_hidden,
		"hide_payment_on_webshop": payment_hidden,
		"enable_cancel_order": bool(getattr(settings, "enable_cancel_order", 0)),
		"enable_prepaid": effective_enable_prepaid,
		"enable_cod": effective_enable_cod,
		"default_payment_mode": default_mode,
		"selected_payment_mode": selected_mode,
		"show_payment_mode_selector": show_payment_mode_selector,
		"show_online_payment_ui": show_online_payment_ui,
	}


@frappe.whitelist(allow_guest=True)
def set_checkout_payment_mode(payment_mode: str):
	"""Persist the selected checkout payment mode on the cart quotation."""
	settings = _get_settings()
	quotation = _get_checkout_quotation(settings)
	selected_mode = _resolve_checkout_payment_mode(quotation, settings, payment_mode)
	_persist_checkout_payment_mode(quotation, selected_mode)
	return {
		"selected_payment_mode": selected_mode,
		"show_online_payment_ui": selected_mode == PAYMENT_MODE_PREPAID and not _is_payment_section_disabled(settings),
	}


@frappe.whitelist()
def place_order(payment_mode: str | None = None):
	"""Prepare the cart quotation, then delegate order creation to core webshop."""
	settings = _get_settings()
	quotation = _get_checkout_quotation(settings)
	selected_mode = _resolve_checkout_payment_mode(quotation, settings, payment_mode)
	_persist_checkout_payment_mode(quotation, selected_mode)

	if not _requires_checkout_overrides(settings):
		order_name = core_cart.place_order()
	else:
		quotation = _get_checkout_quotation(settings)
		_validate_checkout_readiness(quotation)
		quotation.company = quotation.company or frappe.db.get_single_value("Webshop Settings", "company")

		order_name = core_cart.place_order()

	order_doc = frappe.get_doc("Sales Order", order_name)
	_persist_checkout_payment_mode(order_doc, selected_mode)

	if _is_payment_section_disabled(settings):
		return _build_checkout_redirect_payload(order_doc, selected_mode, skip_payment_workflow=True)

	if selected_mode == PAYMENT_MODE_COD:
		from catalog_extensions.order_fulfillment import automate_webshop_order_fulfillment_if_allowed

		with _run_as("Administrator"):
			order_doc = frappe.get_doc("Sales Order", order_name)
			automate_webshop_order_fulfillment_if_allowed(order_doc)

	return _build_checkout_redirect_payload(order_doc, selected_mode)


def _redirect_to_order(order_id: str):
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = get_url(f"/orders/{order_id}")
	return {"redirect_to": frappe.local.response["location"], "already_paid": True}


def _build_checkout_redirect_payload(order_doc, payment_mode: str, skip_payment_workflow: bool = False) -> dict:
	"""Return the next-step redirect payload for the selected checkout mode."""
	order_id = getattr(order_doc, "name", None) or order_doc.get("name")
	order_redirect = get_url(f"/orders/{order_id}")

	if skip_payment_workflow or payment_mode == PAYMENT_MODE_COD:
		return {
			"order_id": order_id,
			"payment_mode": payment_mode,
			"payment_required": False,
			"redirect_to": get_url(f"/order-success?order_id={order_id}"),
			"order_redirect": order_redirect,
		}

	response = getattr(frappe.local, "response", None)
	original_type = response.get("type") if isinstance(response, dict) else None
	original_location = response.get("location") if isinstance(response, dict) else None
	try:
		payment_request = core_make_payment_request(
			dt="Sales Order",
			dn=order_id,
			submit_doc=1,
			order_type="Shopping Cart",
			company=order_doc.company,
			return_doc=True,
		)
	finally:
		if isinstance(response, dict):
			if original_type is None:
				response.pop("type", None)
			else:
				response["type"] = original_type

			if original_location is None:
				response.pop("location", None)
			else:
				response["location"] = original_location
	return {
		"order_id": order_id,
		"payment_mode": payment_mode,
		"payment_required": True,
		"redirect_to": payment_request.get_payment_url(),
		"order_redirect": order_redirect,
		"payment_request": payment_request.name,
	}


@frappe.whitelist(allow_guest=True)
def make_payment_request(**args):
	"""Wrap core Payment Request creation for webshop orders.

	If a Shopping Cart order is already fully settled, redirect back to the order
	page instead of surfacing ERPNext's "Payment Entry is already created" error.
	"""
	args = frappe._dict(args)

	if (
		args.get("order_type") != "Shopping Cart"
		or not args.get("dt")
		or not args.get("dn")
	):
		return core_make_payment_request(**args)

	settings = _get_settings()
	if _is_payment_section_disabled(settings):
		raise frappe.ValidationError(frappe._("Payment is disabled for this checkout flow."))

	ref_doc = args.get("ref_doc") or frappe.get_doc(args.dt, args.dn)
	if get_payment_mode_for_doc(ref_doc) == PAYMENT_MODE_COD:
		raise frappe.ValidationError(frappe._("Online payment is disabled for Cash on Delivery orders."))

	if not args.get("company"):
		args.company = ref_doc.company

	gateway_account = core_get_gateway_details(args) or frappe._dict()
	grand_total = core_get_payment_request_amount(ref_doc, gateway_account.get("payment_account"))

	if not grand_total:
		return _redirect_to_order(ref_doc.name)

	try:
		return core_make_payment_request(**args)
	except frappe.ValidationError as exc:
		if "Payment Entry is already created" in frappe.as_unicode(exc):
			return _redirect_to_order(ref_doc.name)
		raise
