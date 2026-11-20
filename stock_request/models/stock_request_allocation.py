# Copyright 2017-2020 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class StockRequestAllocation(models.Model):
    _name = "stock.request.allocation"
    _description = "Stock Request Allocation"

    stock_request_id = fields.Many2one(
        comodel_name="stock.request",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
        readonly=True,
        related="stock_request_id.company_id",
        store=True,
    )
    stock_move_id = fields.Many2one(
        comodel_name="stock.move",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        string="Product",
        comodel_name="product.product",
        related="stock_request_id.product_id",
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        string="UoM",
        comodel_name="uom.uom",
        related="stock_request_id.product_uom_id",
        readonly=True,
    )
    requested_product_uom_qty = fields.Float(
        "Requested Quantity (UoM)",
        help="Quantity of the stock request allocated to the stock move, "
        "in the UoM of the Stock Request",
    )
    requested_product_qty = fields.Float(
        "Requested Quantity",
        help="Quantity of the stock request allocated to the stock move, "
        "in the default UoM of the product",
        compute="_compute_requested_product_qty",
    )
    allocated_product_qty = fields.Float(
        "Allocated Quantity",
        copy=False,
        help="Quantity of the stock request allocated to the stock move, "
        "in the default UoM of the product",
    )
    open_product_qty = fields.Float(
        "Open Quantity",
        compute="_compute_open_product_qty",
    )

    @api.depends(
        "stock_request_id.product_id",
        "stock_request_id.product_uom_id",
        "requested_product_uom_qty",
    )
    def _compute_requested_product_qty(self):
        for rec in self:
            rec.requested_product_qty = rec.product_uom_id._compute_quantity(
                rec.requested_product_uom_qty,
                rec.product_id.uom_id,
                rounding_method="HALF-UP",
            )

    @api.depends(
        "requested_product_qty",
        "allocated_product_qty",
        "stock_move_id",
        "stock_move_id.state",
    )
    def _compute_open_product_qty(self):
        for rec in self:
            if rec.stock_move_id.state in ["cancel", "done"]:
                rec.open_product_qty = 0.0
            else:
                rec.open_product_qty = (
                    rec.requested_product_qty - rec.allocated_product_qty
                )
                rec.open_product_qty = max(rec.open_product_qty, 0.0)

    def _get_done_sign(self):
        """1 if the allocated quantity fulfills the request, -1 if it undoes
        it (a return) and 0 if a next move of the chain counts it instead."""
        self.ensure_one()
        move = self.stock_move_id
        if move.origin_returned_move_id:
            origin = move.origin_returned_move_id.allocation_ids.filtered(
                lambda a: a.stock_request_id == self.stock_request_id
            )[:1]
            return -origin._get_done_sign() if origin else -1
        next_moves = move.move_dest_ids.filtered(
            lambda m: (
                m.state != "cancel"
                and not m.origin_returned_move_id
                and self.stock_request_id in m.allocation_ids.stock_request_id
            )
        )
        return 0 if next_moves else 1
