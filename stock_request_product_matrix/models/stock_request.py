# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockRequest(models.Model):
    _inherit = "stock.request"

    # Mirrors the sale order line pattern
    product_template_id = fields.Many2one(
        "product.template",
        compute="_compute_product_template_id",
        search="_search_product_template_id",
        readonly=False,
        domain=[("type", "in", ["product", "consu"])],
    )
    is_configurable_product = fields.Boolean(
        related="product_template_id.has_configurable_attributes",
        depends=["product_template_id"],
    )
    product_template_attribute_value_ids = fields.Many2many(
        related="product_id.product_template_attribute_value_ids",
        depends=["product_id"],
    )

    @api.depends("product_id")
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [("product_id.product_tmpl_id", operator, value)]
