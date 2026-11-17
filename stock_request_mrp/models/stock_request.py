# Copyright 2020-24 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockRequest(models.Model):
    _inherit = "stock.request"

    production_ids = fields.Many2many(
        "mrp.production",
        "mrp_production_stock_request_rel",
        "stock_request_id",
        "mrp_production_id",
        string="Manufacturing Orders",
        readonly=True,
        copy=False,
    )
    production_count = fields.Integer(
        string="Manufacturing Orders count",
        compute="_compute_production_ids",
        readonly=True,
    )

    @api.depends("production_ids")
    def _compute_production_ids(self):
        for request in self:
            request.production_count = len(request.production_ids)

    @api.constrains("production_ids", "company_id")
    def _check_production_company_constrains(self):
        if any(
            any(
                production.company_id != req.company_id
                for production in req.production_ids
            )
            for req in self
        ):
            raise ValidationError(
                self.env._(
                    "You have linked to a Manufacture Order "
                    "that belongs to another company."
                )
            )

    def action_view_mrp_production(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "mrp.mrp_production_action"
        )
        productions = self.mapped("production_ids")
        if len(productions) > 1:
            action["domain"] = [("id", "in", productions.ids)]
        elif productions:
            action["views"] = [
                (self.env.ref("mrp.mrp_production_form_view").id, "form")
            ]
            action["res_id"] = productions.id
        return action

    def _update_production_allocations(self):
        """Spread the quantity of each request over the open finished moves of
        its manufacturing orders, up to the quantity of each move. Call it with
        sudo: the user may not read the productions nor create allocations."""
        allocation_obj = self.env["stock.request.allocation"]
        for request in self:
            product_uom = request.product_id.uom_id
            moves = (
                request.production_ids.move_finished_ids
                | request.allocation_ids.stock_move_id
            ).filtered(
                lambda m, request=request: (
                    m.production_id
                    and m.product_id == request.product_id
                    and not m.byproduct_id
                    and m.state != "cancel"
                )
            )
            allocations = request.allocation_ids.filtered(
                lambda a, moves=moves: a.stock_move_id in moves
            )
            pending_qty = request.product_qty - sum(
                allocations.filtered(lambda a: a.stock_move_id.state == "done").mapped(
                    "allocated_product_qty"
                )
            )
            for move in moves.filtered(lambda m: m.state != "done").sorted("id"):
                allocation = allocations.filtered(
                    lambda a, move=move: a.stock_move_id == move
                )[:1]
                qty = max(min(pending_qty, move.product_qty), 0.0)
                pending_qty -= qty
                requested_qty = product_uom._compute_quantity(
                    allocation.allocated_product_qty + qty,
                    request.product_uom_id,
                    rounding_method="HALF-UP",
                )
                if allocation:
                    if allocation.requested_product_uom_qty != requested_qty:
                        allocation.requested_product_uom_qty = requested_qty
                elif not product_uom.is_zero(qty):
                    allocation_obj.create(
                        {
                            "stock_request_id": request.id,
                            "stock_move_id": move.id,
                            "requested_product_uom_qty": requested_qty,
                        }
                    )
