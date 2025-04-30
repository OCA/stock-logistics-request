# Copyright 2023 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockRequestOrder(models.Model):
    _inherit = "stock.request.order"

    procurement_group_id = fields.Many2one(
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)

        if not self.env.company.stock_request_allow_separate_picking:
            return orders

        orders_no_group = orders.filtered(lambda o: not o.procurement_group_id)
        if not orders_no_group:
            return orders

        # Create and Assign procurement group
        groups = self.env["procurement.group"].create(
            [{"name": order.name} for order in orders]
        )
        for order, group in zip(orders_no_group, groups, strict=False):
            order.procurement_group_id = group.id

        # Assign procurement group into lines
        all_lines = orders_no_group.mapped("stock_request_ids")
        line_map = {
            order.id: order.procurement_group_id.id for order in orders_no_group
        }
        for line in all_lines:
            if line.order_id.id in line_map:
                line.procurement_group_id = line_map[line.order_id.id]

        return orders
