# Copyright 2019-2020 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, models
from odoo.exceptions import UserError


class StockRequestOrder(models.Model):
    _name = "stock.request.order"
    _inherit = ["stock.request.order", "tier.validation"]
    _state_from = ["draft"]
    _state_to = ["open"]

    _tier_validation_manual_config = False

    @api.model
    def _get_under_validation_exceptions(self):
        res = super()._get_under_validation_exceptions()
        res.append("route_id")
        return res

    def action_confirm(self):
        for order in self:
            if order.validation_status == "rejected":
                raise UserError(
                    _(
                        "You cannot confirm a stock request order that has been rejected."
                    )
                )
            if order.validation_status == "pending":
                order.validate_tier()
        return super().action_confirm()
