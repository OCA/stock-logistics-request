# Copyright 2017-2020 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


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
                _(
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
            uom = (
                self.env["uom.uom"].browse(vals.get("product_uom")) or self.product_uom
            )
            qtys = self._get_split_allocation_qtys(
                uom._compute_quantity(
                    vals.get("product_uom_qty", self.product_uom_qty), product_uom
                )
            )
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
            if not float_is_zero(qty, precision_rounding=product_uom.rounding)
        ]

    def _get_split_allocation_qtys(self, to_copy):
        self.ensure_one()
        to_keep = max(self.product_qty - to_copy, 0.0)
        qtys = []
        for alloc in self.allocation_ids:
            kept_qty = min(alloc.open_product_qty, to_keep)
            to_keep -= kept_qty
            qty = min(alloc.open_product_qty - kept_qty, to_copy)
            to_copy -= qty
            qtys.append((alloc, qty))
        return qtys

    def _split(self, qty, restrict_partner_id=False):
        split_qtys = self.allocation_ids and self._get_split_allocation_qtys(qty)
        new_move_vals = super()._split(qty, restrict_partner_id=restrict_partner_id)
        if new_move_vals and split_qtys:
            self._reduce_allocations(split_qtys)
        return new_move_vals

    def _reduce_allocations(self, qtys):
        to_unlink = self.env["stock.request.allocation"].sudo()
        for alloc, qty in qtys:
            alloc = alloc.sudo()
            product_uom = alloc.product_id.uom_id
            if float_is_zero(qty, precision_rounding=product_uom.rounding):
                continue
            remaining_qty = alloc.requested_product_qty - qty
            if float_is_zero(remaining_qty, precision_rounding=product_uom.rounding):
                to_unlink |= alloc
            else:
                alloc.requested_product_uom_qty = product_uom._compute_quantity(
                    remaining_qty, alloc.product_uom_id, rounding_method="HALF-UP"
                )
        to_unlink.unlink()

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
