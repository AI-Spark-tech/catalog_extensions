import frappe

# Reuse existing webshop cart logic; do not duplicate it
from webshop.webshop.shopping_cart import cart as core_cart


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


@frappe.whitelist()
def get_cart_quotation(doc=None):
	"""Thin wrapper around core get_cart_quotation.

	When simple checkout is enabled, ensure defaults are applied, then
	delegate back to core for all heavy logic.
	"""
	settings = _get_settings()

	# If settings are missing or feature is disabled, just delegate to core
	if not settings or not getattr(settings, "enable_simple_checkout", 0):
		return core_cart.get_cart_quotation(doc)

	# Start with the standard context from webshop
	context = core_cart.get_cart_quotation(doc)
	quotation = context.get("doc")

	if not quotation:
		return context

	_ensure_defaults_on_quotation(quotation, settings)

	# Reload context so downstream templates see updated values
	return core_cart.get_cart_quotation(doc)


@frappe.whitelist(allow_guest=True)
def get_simple_checkout_flags():
	"""Expose simple checkout visibility flags for webshop JS.

	If settings are missing, this returns all False so UI behaves as core.
	"""
	settings = _get_settings()

	if not settings:
		return {
			"enable_simple_checkout": False,
			"hide_shipping_on_webshop": False,
			"hide_payment_on_webshop": False,
		}

	return {
		"enable_simple_checkout": bool(getattr(settings, "enable_simple_checkout", 0)),
		"hide_shipping_on_webshop": bool(getattr(settings, "hide_shipping_on_webshop", 0)),
		"hide_payment_on_webshop": bool(getattr(settings, "hide_payment_on_webshop", 0)),
	}


@frappe.whitelist()
def place_order():
	"""Thin wrapper around core place_order.

	When simple checkout is enabled, ensure defaults are set on the cart
	quotation first, then delegate to core.place_order so we don't
	duplicate any of its logic.
	"""
	settings = _get_settings()

	# If settings are missing or feature is disabled, call core directly
	if not settings or not getattr(settings, "enable_simple_checkout", 0):
		return core_cart.place_order()

	# Get the current cart quotation and apply defaults to it
	quotation = core_cart._get_cart_quotation()
	_ensure_defaults_on_quotation(quotation, settings)

	# Now let core place_order run with a fully-populated quotation
	return core_cart.place_order()
