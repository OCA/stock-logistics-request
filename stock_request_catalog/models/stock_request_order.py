# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models
from odoo.fields import Domain


class StockRequestOrder(models.Model):
    _name = "stock.request.order"
    _inherit = ["stock.request.order", "product.catalog.mixin"]

    def _get_product_catalog_domain(self):
        """Restrict the catalog to products a stock request can actually hold."""
        return super()._get_product_catalog_domain() & Domain(
            "type", "in", ["consu", "product"]
        )

    def _get_product_catalog_record_lines(self, product_ids, **kwargs):
        """Group the order's existing request lines by product for the catalog."""
        grouped_lines = defaultdict(lambda: self.env["stock.request"])
        for line in self.stock_request_ids:
            if line.product_id.id not in product_ids:
                continue
            grouped_lines[line.product_id] |= line
        return grouped_lines

    def _get_product_catalog_order_data(self, products, **kwargs):
        """Add the (price-less) data for products not yet on the order."""
        res = super()._get_product_catalog_order_data(products, **kwargs)
        for product in products:
            res[product.id]["price"] = 0.0
        return res

    def _default_order_line_values(self, child_field=False):
        """Merge the request-line defaults into the catalog's line defaults."""
        default_data = super()._default_order_line_values(child_field)
        default_data.update(self.env["stock.request"]._get_product_catalog_lines_data())
        return default_data

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        """
        Create, re-quantify or drop the request line for a catalog product.
        Return price (always zero for stock.request)
        """
        request = self.stock_request_ids.filtered(
            lambda line: line.product_id.id == product_id
        )
        if request:
            if quantity != 0:
                request.product_uom_qty = quantity
            elif self.state == "draft":
                request.unlink()
        elif quantity > 0:
            product = self.env["product.product"].browse(product_id)
            self.env["stock.request"].create(
                self._prepare_catalog_request_values(product, quantity)
            )
        return 0.0

    def _prepare_catalog_request_values(self, product, quantity):
        """Build a request line, copying the order-level values its lines require.

        Catalog insertion creates the line directly instead of going through
        ``change_childs``, so the shared order fields are set explicitly.
        """
        self.ensure_one()
        return {
            "order_id": self.id,
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "product_uom_qty": quantity,
            "warehouse_id": self.warehouse_id.id,
            "location_id": self.location_id.id,
            "company_id": self.company_id.id,
            "expected_date": self.expected_date,
            "requested_by": self.requested_by.id,
            "picking_policy": self.picking_policy,
            "reference_ids": self.reference_ids.ids,
            "route_id": self.route_id.id,
        }

    def _is_readonly(self):
        """The catalog may only edit the order while it is still a draft."""
        self.ensure_one()
        return self.state != "draft"

    def _is_display_stock_in_catalog(self):
        """Show on-hand stock on the catalog cards"""
        return True
