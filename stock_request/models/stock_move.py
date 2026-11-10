# Copyright 2017-2020 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    allocation_ids = fields.One2many(
        comodel_name="stock.request.allocation",
        inverse_name="stock_move_id",
        string="Stock Request Allocation",
    )

    stock_request_ids = fields.One2many(
        comodel_name="stock.request",
        string="Stock Requests",
        compute="_compute_stock_request_ids",
    )

    @api.depends("allocation_ids")
    def _compute_stock_request_ids(self):
        for rec in self:
            rec.stock_request_ids = rec.allocation_ids.mapped("stock_request_id")

    def _merge_moves_fields(self):
        res = super()._merge_moves_fields()
        res["allocation_ids"] = [(4, m.id) for m in self.mapped("allocation_ids")]
        return res

    @api.constrains("company_id")
    def _check_company_stock_request(self):
        if any(
            self.env["stock.request.allocation"].search(
                [
                    ("company_id", "!=", rec.company_id.id),
                    ("stock_move_id", "=", rec.id),
                ],
                limit=1,
            )
            for rec in self
        ):
            raise ValidationError(
                self.env._(
                    "The company of the stock request must match with "
                    "that of the location."
                )
            )

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        for move, vals in zip(self, vals_list, strict=True):
            vals["allocation_ids"] = list(
                vals.get("allocation_ids", [])
            ) + move._prepare_copy_allocation_vals(vals)
        return vals_list

    def _prepare_copy_allocation_vals(self, vals):
        """A copy of a done move (a return or a push) takes the quantity
        allocated to it. A copy of an open move (a split) takes the open
        quantity that the original move does not keep."""
        self.ensure_one()
        product_uom = self.product_id.uom_id
        if self.state == "done":
            qtys = [
                (alloc, alloc.allocated_product_qty) for alloc in self.allocation_ids
            ]
        else:
            uom = self.env["uom.uom"].browse(vals.get("uom_id")) or self.uom_id
            to_copy = uom._compute_quantity(
                vals.get("product_uom_qty", self.product_uom_qty), product_uom
            )
            to_keep = max(self.product_qty - to_copy, 0.0)
            qtys = []
            for alloc in self.allocation_ids:
                kept_qty = min(alloc.open_product_qty, to_keep)
                to_keep -= kept_qty
                qty = min(alloc.open_product_qty - kept_qty, to_copy)
                to_copy -= qty
                qtys.append((alloc, qty))
        return [
            Command.create(
                {
                    "stock_request_id": alloc.stock_request_id.id,
                    "requested_product_uom_qty": product_uom._compute_quantity(
                        qty, alloc.product_uom_id, rounding_method="HALF-UP"
                    ),
                }
            )
            for alloc, qty in qtys
            if not product_uom.is_zero(qty)
        ]

    def _action_cancel(self):
        """Apply sudo to prevent requests ACL errors if the user does not have
        permissions (example: productions)."""
        res = super()._action_cancel()
        self.mapped("allocation_ids.stock_request_id").sudo().check_cancel()
        return res

    def _action_done(self, cancel_backorder=False):
        """Apply sudo to prevent requests ACL errors if the user does not have
        permissions (example: productions)."""
        res = super()._action_done(cancel_backorder=cancel_backorder)
        self.mapped("allocation_ids.stock_request_id").sudo().check_done()
        return res
