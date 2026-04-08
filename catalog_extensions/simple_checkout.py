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


def is_simple_checkout_enabled() -> bool:
	"""Return whether custom simple checkout is enabled for this site."""
	settings = _get_settings()
	return bool(settings and getattr(settings, "enable_simple_checkout", 0))


def _is_simple_checkout_active(settings=None) -> bool:
	"""Return whether catalog_extensions should apply custom checkout behavior."""
	if settings is None:
		settings = _get_settings()
	return bool(settings and getattr(settings, "enable_simple_checkout", 0))


def _get_settings():
	"""Fetch simple checkout settings if the doctype exists.

	Returns None if the doctype/record is missing so that core behaviour is preserved.
	"""
	doctype = "Webshop Simple Checkout Settings"
	try:
		return frappe.get_cached_doc(doctype)
	except (frappe.DoesNotExistError, frappe.PermissionError):
		# Settings not configured; behave like core
		return None


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

	# 1) Ensure a default address so core validations pass.
	if not (getattr(quotation, "shipping_address_name", None) or getattr(quotation, "customer_address", None)):
		party = core_cart.get_party()
		address_docs = _ensure_minimal_address(party)

		default_type = getattr(settings, "default_shipping_address_type", None)
		chosen_doc = None

		if default_type in ("Shipping", "Billing"):
			chosen_doc = next(
				(a for a in address_docs if getattr(a, "address_type", None) == default_type),
				None,
			)

		# Fallback: first address of any type
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

	# 2) Ensure default payment terms template is set on the quotation
	if getattr(settings, "default_payment_term_template", None) and not getattr(quotation, "payment_terms_template", None):
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
	if settings and _is_simple_checkout_active(settings):
		_ensure_defaults_on_quotation(quotation, settings)
	quotation = _expire_stale_payment_requests(quotation)
	if settings and _is_simple_checkout_active(settings):
		_ensure_defaults_on_quotation(quotation, settings)
	return quotation


def _validate_checkout_readiness(quotation):
	if not quotation.get("items"):
		frappe.throw(frappe._("Your cart is empty."))

	if not (quotation.shipping_address_name or quotation.customer_address):
		frappe.throw(frappe._("Set Shipping Address or Billing Address"))

	if not quotation.company:
		quotation.company = frappe.db.get_single_value("Webshop Settings", "company")


def _get_quotation_payment_amount(quotation):
	grand_total = quotation.get("rounded_total") or quotation.get("grand_total") or 0
	return frappe.utils.flt(grand_total)


def _build_payment_request_for_quotation(quotation):
	args = frappe._dict(
		{
			"company": quotation.company,
			"order_type": "Shopping Cart",
			"party_type": "Customer",
			"party": quotation.party_name,
			"party_name": quotation.customer_name,
			"recipient_id": quotation.contact_email or frappe.session.user,
			"mode_of_payment": None,
		}
	)
	gateway_account = core_get_gateway_details(args) or frappe._dict()
	grand_total = _get_quotation_payment_amount(quotation)
	if not grand_total:
		frappe.throw(frappe._("Unable to start payment for an empty checkout."))

	pr = frappe.new_doc("Payment Request")
	party_account_currency = quotation.get("party_account_currency") or quotation.get("currency")
	pr.update(
		{
			"payment_gateway_account": gateway_account.get("name"),
			"payment_gateway": gateway_account.get("payment_gateway"),
			"payment_account": gateway_account.get("payment_account"),
			"payment_channel": gateway_account.get("payment_channel"),
			"payment_request_type": "Inward",
			"currency": quotation.currency,
			"party_account_currency": party_account_currency,
			"grand_total": grand_total,
			"outstanding_amount": grand_total,
			"mode_of_payment": None,
			"email_to": quotation.contact_email or frappe.session.user,
			"subject": frappe._("Payment Request for {0}").format(quotation.name),
			"message": gateway_account.get("message") or quotation.name,
			"reference_doctype": "Quotation",
			"reference_name": quotation.name,
			"company": quotation.company,
			"party_type": "Customer",
			"party": quotation.party_name,
			"party_name": quotation.customer_name,
			"mute_email": 1,
		}
	)
	pr.flags.ignore_permissions = True
	pr.insert(ignore_permissions=True)
	pr.submit()
	return pr


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

	When simple checkout is enabled, ensure defaults are applied, then
	delegate back to core for all heavy logic. Image sync is handled by
	our decorate_quotation_doc override.
	"""
	settings = _get_settings()

	# If settings are missing or feature is disabled, just delegate to core
	if not _is_simple_checkout_active(settings):
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
	"""Expose simple checkout visibility flags for webshop JS.

	If settings are missing, this returns all False so UI behaves as core.
	"""
	settings = _get_settings()

	if not _is_simple_checkout_active(settings):
		return {
			"enable_simple_checkout": False,
			"hide_shipping_on_webshop": False,
			"hide_payment_on_webshop": False,
		}

	return {
		"enable_simple_checkout": True,
		"hide_shipping_on_webshop": bool(getattr(settings, "hide_shipping_on_webshop", 0)),
		"hide_payment_on_webshop": bool(getattr(settings, "hide_payment_on_webshop", 0)),
	}


@frappe.whitelist()
def place_order():
	"""Run the core webshop checkout flow in deferred-payment mode.

	This keeps the cart as a Shopping Cart quotation, starts payment,
	and creates the Sales Order only after payment authorization.
	"""
	quotation = _get_checkout_quotation()
	_validate_checkout_readiness(quotation)
	quotation.flags.ignore_permissions = True
	quotation.save()

	existing_order = _get_existing_sales_order_for_quotation(quotation.name)
	if existing_order:
		frappe.session["last_order_id"] = existing_order
		return {
			"checkout_state": "order_created",
			"order_id": existing_order,
			"redirect_to": f"/order-success?order_id={existing_order}",
		}

	pr = _build_payment_request_for_quotation(quotation)
	redirect_to = pr.get_payment_url()
	frappe.session["pending_checkout_quotation"] = quotation.name
	frappe.session["pending_payment_request"] = pr.name
	return {
		"checkout_state": "payment_pending",
		"payment_request": pr.name,
		"redirect_to": redirect_to,
	}


def _redirect_to_order(order_id: str):
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = get_url(f"/orders/{order_id}")
	return {"redirect_to": frappe.local.response["location"], "already_paid": True}


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

	ref_doc = args.get("ref_doc") or frappe.get_doc(args.dt, args.dn)
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
