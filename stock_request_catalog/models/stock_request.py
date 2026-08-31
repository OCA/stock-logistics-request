# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class StockRequest(models.Model):
    _inherit = "stock.request"

    @api.readonly
    def action_add_from_catalog(self):
        """Open the catalog from the lines list, delegating to the order."""
        order = self.env["stock.request.order"].browse(self.env.context.get("order_id"))
        return order.with_context(
            child_field="stock_request_ids"
        ).action_add_from_catalog()

    def _get_product_catalog_lines_data(self, **kwargs):
        """Return the catalog qty/uom for the request line(s) of one product.

        One line returns its own quantity; several lines of the same product are
        aggregated and marked read-only; an empty recordset yields the defaults.
        """
        if len(self) == 1:
            return {
                "quantity": self.product_uom_qty,
                "price": 0.0,
                "readOnly": self.order_id._is_readonly(),
                "uomDisplayName": self.product_uom_id.display_name,
            }
        elif self:
            self.product_id.ensure_one()
            line = self[0]
            return {
                "quantity": sum(
                    self.mapped(
                        lambda request: request.product_uom_id._compute_quantity(
                            qty=request.product_uom_qty,
                            to_unit=line.product_uom_id,
                        )
                    )
                ),
                "price": 0.0,
                "readOnly": True,
                "uomDisplayName": line.product_uom_id.display_name,
            }
        return {
            "quantity": 0.0,
            "price": 0.0,
        }
