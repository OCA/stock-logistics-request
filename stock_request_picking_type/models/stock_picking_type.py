# Copyright 2019 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    code = fields.Selection(
        selection_add=[("stock_request_order", "Stock Request Order")],
        ondelete={"stock_request_order": "cascade"},
    )
    count_sr_todo = fields.Integer(string="To Do", compute="_compute_sr_count")
    count_sr_open = fields.Integer(string="In Progress", compute="_compute_sr_count")
    count_sr_late = fields.Integer(string="Late", compute="_compute_sr_count")

    def _compute_sr_count(self):
        domains = {
            "count_sr_todo": [("state", "=", "submitted")],
            "count_sr_open": [("state", "=", "open")],
            "count_sr_late": [
                ("expected_date", "<", fields.Date.today()),
                ("state", "in", ("submitted", "open")),
            ],
        }
        for field_name, domain in domains.items():
            data = self.env["stock.request.order"]._read_group(
                domain
                + [
                    ("state", "not in", ("done", "cancel")),
                    ("picking_type_id", "in", self.ids),
                ],
                ["picking_type_id"],
                ["__count"],
            )
            counts = {picking_type.id: count for picking_type, count in data}
            for record in self:
                record[field_name] = counts.get(record.id, 0)

    def get_stock_request_order_picking_type_action(self):
        return self._get_action("stock_request_picking_type.action_picking_dashboard")

    @api.depends("code")
    def _compute_show_picking_type(self):
        res = super()._compute_show_picking_type()
        for record in self:
            if record.code == "stock_request_order":
                record.show_picking_type = True
        return res
