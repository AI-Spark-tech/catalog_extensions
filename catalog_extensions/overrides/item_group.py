from webshop.webshop.doctype.override_doctype.item_group import (
    WebshopItemGroup as CoreWebshopItemGroup,
)

from catalog_extensions.webshop_listing import apply_listing_page_context


class WebshopItemGroup(CoreWebshopItemGroup):
    def get_context(self, context):
        context = super().get_context(context)
        return apply_listing_page_context(context, item_group=self.name)
