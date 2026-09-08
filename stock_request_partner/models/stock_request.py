# Copyright 2020 Jarsa Sistemas, S.A. de C.V.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockRequest(models.Model):
    _inherit = "stock.request"

    partner_id = fields.Many2one(
        "res.partner",
    )

    def _prepare_procurement_values(self, reference_ids=False):
        res = super()._prepare_procurement_values(reference_ids=reference_ids)
        if self.partner_id:
            res["partner_id"] = self.partner_id.id
        return res

    @api.constrains("order_id", "partner_id")
    def check_order_partner_id(self):
        for rec in self:
            if rec.order_id and rec.order_id.partner_id != rec.partner_id:
                raise ValidationError(self.env._("Partner must be equal to the order"))
