# Copyright 2017 ForgeFlow S.L.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from markupsafe import Markup

from odoo import _, api, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model
    def _stock_request_confirm_done_message_content(self, message_data):
        title = Markup("<h3>%s</h3>") % _(
            "Receipt confirmation %(picking_name)s for your Request "
            "%(request_name)s",
            picking_name=message_data["picking_name"],
            request_name=message_data["request_name"],
        )

        body = Markup("<p>%s</p>") % _(
            "The following requested items from Stock Request %(request_name)s "
            "have now been received in %(location_name)s using Picking "
            "%(picking_name)s:",
            request_name=message_data["request_name"],
            location_name=message_data["location_name"],
            picking_name=message_data["picking_name"],
        )

        items = Markup("<ul><li><b>%s</b></li></ul>") % _(
            "%(product_name)s : Transferred quantity %(product_qty)s %(product_uom)s",
            product_name=message_data["product_name"],
            product_qty=message_data["product_qty"],
            product_uom=message_data["product_uom"],
        )

        message = title + body + items

        return message

    def _prepare_message_data(self, ml, request, allocated_qty):
        return {
            "request_name": request.name,
            "picking_name": ml.picking_id.name,
            "product_name": ml.product_id.display_name,
            "product_qty": allocated_qty,
            "product_uom": ml.product_uom_id.name,
            "location_name": ml.location_dest_id.display_name,
        }

    def _action_done(self):
        res = super()._action_done()
        for ml in self.filtered(lambda m: m.exists() and m.move_id.allocation_ids):
            qty_done = ml.product_uom_id._compute_quantity(
                ml.quantity, ml.product_id.uom_id
            )

            # We do sudo because potentially the user that completes the move
            #  may not have permissions for stock.request.
            to_allocate_qty = qty_done
            for allocation in ml.move_id.allocation_ids.sudo():
                allocated_qty = 0.0
                if allocation.open_product_qty:
                    allocated_qty = min(allocation.open_product_qty, to_allocate_qty)
                    allocation.allocated_product_qty += allocated_qty
                    to_allocate_qty -= allocated_qty
                if allocated_qty:
                    request = allocation.stock_request_id
                    message_data = self._prepare_message_data(
                        ml, request, allocated_qty
                    )
                    message = self._stock_request_confirm_done_message_content(
                        message_data
                    )
                    request.message_post(body=message, subtype_xmlid="mail.mt_comment")
                    request.check_done()
        return res
