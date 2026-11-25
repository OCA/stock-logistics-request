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

    def _get_allocation_qtys(self):
        """A kit is procured through its components, so the allocations are
        on the component moves and their quantities are of the component.
        Count the complete kits that each component gives and keep the
        lowest one, as Odoo does with the delivered quantity of a kit."""
        self.ensure_one()
        allocations = self.allocation_ids.filtered(
            lambda a: a.stock_move_id.bom_line_id
            and a.stock_move_id.product_id != self.product_id
        )
        bom = (
            allocations
            and self.env["mrp.bom"]._bom_find(
                self.product_id, company_id=self.company_id.id, bom_type="phantom"
            )[self.product_id]
        )
        if not bom:
            return super()._get_allocation_qtys()
        kit_qty = (
            self.product_id.uom_id._compute_quantity(
                1.0, bom.product_uom_id, round=False
            )
            / bom.product_qty
        )
        ratios = []
        for bom_line, line_data in bom.explode(self.product_id, kit_qty)[1]:
            line_allocations = allocations.filtered(
                lambda a, line=bom_line: a.stock_move_id.bom_line_id == line
            )
            uom = bom_line.product_id.uom_id
            qty_per_kit = bom_line.product_uom_id._compute_quantity(
                line_data["qty"], uom, round=False
            )
            if not line_allocations or uom.is_zero(qty_per_kit):
                continue
            done_qty = fulfilled_qty = open_qty = 0.0
            for allocation in line_allocations:
                sign = allocation._get_done_sign()
                done_qty += sign * allocation.allocated_product_qty
                if sign > 0:
                    fulfilled_qty += allocation.allocated_product_qty
                    open_qty += allocation.open_product_qty
            ratios.append(
                [
                    uom.round(max(done_qty, 0.0) / qty_per_kit),
                    uom.round(fulfilled_qty / qty_per_kit),
                    uom.round((fulfilled_qty + open_qty) / qty_per_kit),
                ]
            )
        if not ratios:
            return super()._get_allocation_qtys()
        # A partial kit does not count: keep only complete kits.
        done_kits, fulfilled_kits, reached_kits = (
            min(ratio[i] for ratio in ratios) // 1 for i in range(3)
        )
        return done_kits, fulfilled_kits, max(reached_kits - fulfilled_kits, 0.0)

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
